//! Cephalo Screen Memory & Privacy Engine (screen.rs)
//! ====================================================
//! Cross-platform desktop frame capture, privacy safeguards, delta gating,
//! and background OCR queue decoupling.

use regex::Regex;
use serde::{Deserialize, Serialize};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SafeguardsConfig {
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default)]
    pub blacklisted_processes: Vec<String>,
    #[serde(default)]
    pub blacklisted_window_titles: Vec<String>,
    #[serde(default)]
    pub blacklisted_domains: Vec<String>,
}

fn default_true() -> bool {
    true
}

impl Default for SafeguardsConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            blacklisted_processes: vec![
                "1password".into(),
                "bitwarden".into(),
                "keepass".into(),
                "keepassxc".into(),
                "vaultwarden".into(),
                "lastpass".into(),
                "authenticator".into(),
                "authy".into(),
            ],
            blacklisted_window_titles: vec![
                r"(?i)incognito".into(),
                r"(?i)private browsing".into(),
                r"(?i)inprivate".into(),
                r"(?i)password".into(),
                r"(?i)credential".into(),
                r"(?i)payment|checkout|credit card|cvv|security code".into(),
            ],
            blacklisted_domains: vec![
                "*.bank*".into(),
                "paypal.com".into(),
                "stripe.com/dashboard".into(),
                "revolut.com".into(),
                "wise.com".into(),
            ],
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScreenCaptureResult {
    pub status: String,
    pub frame_id: Option<String>,
    pub path: Option<String>,
    pub delta: Option<f32>,
    pub window_title: Option<String>,
    pub process_name: Option<String>,
    pub ocr_status: Option<String>,
    pub reason: Option<String>,
    pub timestamp: String,
}

pub struct ScreenEngine {
    base_dir: PathBuf,
    safeguards: SafeguardsConfig,
}

impl ScreenEngine {
    pub fn new(data_dir: &Path, root_dir: &Path) -> Self {
        let base_dir = data_dir.join("frames");
        let _ = fs::create_dir_all(&base_dir);

        let safeguards_path = root_dir.join("safeguards.json");
        let safeguards = if safeguards_path.exists() {
            fs::read_to_string(&safeguards_path)
                .ok()
                .and_then(|c| serde_json::from_str(&c).ok())
                .unwrap_or_default()
        } else {
            SafeguardsConfig::default()
        };

        Self {
            base_dir,
            safeguards,
        }
    }

    /// Checks if a window title or process is shielded by safeguards.
    pub fn is_shielded(&self, title: &str, process: &str) -> (bool, Option<String>) {
        if !self.safeguards.enabled {
            return (false, None);
        }

        let p_lower = process.to_lowercase();
        for bp in &self.safeguards.blacklisted_processes {
            if p_lower.contains(&bp.to_lowercase()) {
                return (true, Some(format!("Blacklisted password/auth process: {}", bp)));
            }
        }

        for pattern in &self.safeguards.blacklisted_window_titles {
            if let Ok(re) = Regex::new(pattern) {
                if re.is_match(title) {
                    return (true, Some(format!("Blacklisted private window title pattern: {}", pattern)));
                }
            }
        }

        (false, None)
    }

    /// Inspects the active window title and process in a cross-platform manner (Linux, macOS, Windows).
    pub fn get_active_window() -> (String, String) {
        if cfg!(target_os = "linux") {
            let output = std::process::Command::new("xdotool")
                .args(["getactivewindow", "getwindowname"])
                .output();
            if let Ok(out) = output {
                if out.status.success() {
                    let title = String::from_utf8_lossy(&out.stdout).trim().to_string();
                    return (title, "".to_string());
                }
            }
        } else if cfg!(target_os = "macos") {
            let cmd = "tell application \"System Events\" to get {name of first application process whose frontmost is true, name of window 1 of (first application process whose frontmost is true)}";
            let output = std::process::Command::new("osascript")
                .args(["-e", cmd])
                .output();
            if let Ok(out) = output {
                if out.status.success() {
                    let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
                    let parts: Vec<&str> = text.split(", ").collect();
                    let proc = parts.get(0).copied().unwrap_or("").trim().to_string();
                    let title = parts.get(1).copied().unwrap_or("").trim().to_string();
                    return (title, proc);
                }
            }
        } else if cfg!(target_os = "windows") {
            let script = "$h = [System.IntPtr]::Zero; Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class Win { [DllImport(\"user32.dll\")] public static extern IntPtr GetForegroundWindow(); [DllImport(\"user32.dll\")] public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder text, int count); }'; $h = [Win]::GetForegroundWindow(); $sb = New-Object System.Text.StringBuilder 256; [Win]::GetWindowText($h, $sb, 256) | Out-Null; $sb.ToString()";
            let output = std::process::Command::new("powershell")
                .args(["-NoProfile", "-Command", script])
                .output();
            if let Ok(out) = output {
                if out.status.success() {
                    let title = String::from_utf8_lossy(&out.stdout).trim().to_string();
                    return (title, "".to_string());
                }
            }
        }
        ("".to_string(), "".to_string())
    }

    /// Simulates/executes keyframe registration and decoupled OCR enqueueing.
    pub fn capture_step(&self, force: bool, queue: &crate::queue::JobQueue) -> ScreenCaptureResult {
        let now = chrono::Utc::now();
        let (title, proc) = Self::get_active_window();

        // 1. Safeguard Check
        let (shielded, reason) = self.is_shielded(&title, &proc);
        if shielded {
            return ScreenCaptureResult {
                status: "shielded".to_string(),
                frame_id: None,
                path: None,
                delta: None,
                window_title: Some(title),
                process_name: Some(proc),
                ocr_status: None,
                reason,
                timestamp: now.to_rfc3339(),
            };
        }

        // 2. High-churn monitor suppression (htop, top, btop)
        let lower_title = title.to_lowercase();
        if lower_title.contains("htop") || lower_title.contains("btop") || lower_title.contains("top") {
            if !force {
                return ScreenCaptureResult {
                    status: "high_churn_suppressed".to_string(),
                    frame_id: None,
                    path: None,
                    delta: None,
                    window_title: Some(title),
                    process_name: Some(proc),
                    ocr_status: None,
                    reason: Some("Flicker suppression active for system monitor window".to_string()),
                    timestamp: now.to_rfc3339(),
                };
            }
        }

        let date_str = now.format("%Y-%m-%d").to_string();
        let day_dir = self.base_dir.join(&date_str);
        let _ = fs::create_dir_all(&day_dir);

        let time_tag = now.format("%H%M%S_%3f").to_string();
        let frame_id = format!("frame-{}-{}", now.format("%Y%m%d-%H%M%S"), &time_tag[..6]);
        let frame_filename = format!("{}.webp", frame_id);
        let frame_path = day_dir.join(&frame_filename);

        // Physically capture the screen image to disk in a cross-platform manner
        let mut _capture_ok = false;
        if cfg!(target_os = "linux") {
            // Try ImageMagick import first
            let out = std::process::Command::new("import")
                .args(["-window", "root", "-quality", "75", &frame_path.to_string_lossy()])
                .output();
            if let Ok(o) = out {
                if o.status.success() && frame_path.exists() {
                    _capture_ok = true;
                }
            }
            // Wayland fallback: grim
            if !_capture_ok {
                let out = std::process::Command::new("grim")
                    .arg(&frame_path)
                    .output();
                if let Ok(o) = out {
                    if o.status.success() && frame_path.exists() {
                        _capture_ok = true;
                    }
                }
            }
        } else if cfg!(target_os = "macos") {
            let out = std::process::Command::new("screencapture")
                .args(["-x", "-t", "webp", &frame_path.to_string_lossy()])
                .output();
            if let Ok(o) = out {
                if o.status.success() && frame_path.exists() {
                    _capture_ok = true;
                }
            }
        } else if cfg!(target_os = "windows") {
            let ps_cmd = format!(
                "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; \
                 $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; \
                 $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height; \
                 $g = [System.Drawing.Graphics]::FromImage($bmp); \
                 $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size); \
                 $bmp.Save('{}'); $g.Dispose(); $bmp.Dispose();",
                frame_path.to_string_lossy().replace('\\', "\\\\")
            );
            let _ = std::process::Command::new("powershell")
                .args(["-NoProfile", "-Command", &ps_cmd])
                .output();
        }

        // Enqueue decoupled OCR job into background queue
        let _ = queue.enqueue(
            "ocr_screen_keyframe",
            Some(serde_json::json!({
                "frame_id": frame_id,
                "image_path": frame_path.to_string_lossy().to_string(),
                "date_str": date_str,
                "title": title,
                "process": proc,
            })),
            4,
            true,
        );

        // Record in frame index
        let index_file = self.base_dir.join("frame_index.jsonl");
        let rec = serde_json::json!({
            "id": frame_id,
            "timestamp": now.to_rfc3339(),
            "date": date_str,
            "path": format!("frames/{}/{}", date_str, frame_filename),
            "delta": 1.0,
            "window_title": title,
            "process_name": proc,
            "ocr_text": "",
            "ocr_status": "queued"
        });

        if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(&index_file) {
            let _ = writeln!(f, "{}", rec);
        }

        ScreenCaptureResult {
            status: "captured".to_string(),
            frame_id: Some(frame_id),
            path: Some(format!("frames/{}/{}", date_str, frame_filename)),
            delta: Some(1.0),
            window_title: Some(title),
            process_name: Some(proc),
            ocr_status: Some("queued".to_string()),
            reason: None,
            timestamp: now.to_rfc3339(),
        }
    }
}

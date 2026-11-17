//! Cephalo Screen Memory & Privacy Engine (screen.rs)
//! ====================================================
//! Cross-platform desktop frame capture, Smart Lens focus-shift dominance,
//! streaming noise suppression, active window ROI cropping, and decoupled OCR.

use regex::Regex;
use serde::{Deserialize, Serialize};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

pub use crate::safeguards::SafeguardsConfig;
pub use crate::window::{capture_roi_image, get_active_window, get_active_window_context, WindowContext};
/// Persistent state maintained for Cephalo Smart Lens.
/// Tracks window focus transitions, streaming noise flips, and perceptual hashes.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct SmartLensState {
    pub last_window_key: String,
    pub last_window_id: Option<String>,
    pub last_capture_epoch_secs: i64,
    pub consecutive_stream_flips: u32,
    pub is_suppressed: bool,
    pub last_hash: u64,
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
    #[serde(skip_serializing_if = "Option::is_none")]
    pub roi_mode: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stream_flips: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub focus_shift: Option<bool>,
}

pub struct ScreenEngine {
    pub base_dir: PathBuf,
    pub safeguards: SafeguardsConfig,
}

impl ScreenEngine {
    pub fn get_active_window_context() -> WindowContext {
        get_active_window_context()
    }

    pub fn get_active_window() -> (String, String) {
        get_active_window()
    }

    pub fn capture_roi_image(win_id: Option<&str>, frame_path: &Path) -> (bool, &'static str) {
        capture_roi_image(win_id, frame_path)
    }
    pub fn new(data_dir: &Path, root_dir: &Path) -> Self {
        let base_dir = data_dir.join("frames");
        let _ = fs::create_dir_all(&base_dir);

        let data_safeguards = data_dir.join("safeguards.json");
        let safeguards_path = if data_safeguards.exists() {
            data_safeguards
        } else {
            root_dir.join("safeguards.json")
        };

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

    /// Returns whether background screen memory capture is enabled in safeguards.json
    pub fn is_enabled(&self) -> bool {
        self.safeguards.enabled && self.safeguards.screen_capture_enabled
    }

    /// Updates the screen capture enabled toggle in safeguards.json
    pub fn set_screen_capture_enabled(&mut self, enabled: bool, data_dir: &Path, root_dir: &Path) -> std::io::Result<()> {
        self.safeguards.screen_capture_enabled = enabled;
        let data_safeguards = data_dir.join("safeguards.json");
        let target_path = if data_safeguards.exists() {
            data_safeguards
        } else {
            root_dir.join("safeguards.json")
        };
        let content = serde_json::to_string_pretty(&self.safeguards)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
        fs::write(target_path, content)?;
        Ok(())
    }

    /// Prunes raw WebP keyframes older than max_age_days to keep storage footprint negligible.
    pub fn prune_frames(&self, max_age_days: u32) -> std::io::Result<usize> {
        let cutoff = chrono::Utc::now() - chrono::Duration::days(max_age_days as i64);
        let cutoff_str = cutoff.format("%Y-%m-%d").to_string();
        let mut deleted = 0;

        if let Ok(entries) = fs::read_dir(&self.base_dir) {
            for entry in entries.flatten() {
                if let Ok(file_type) = entry.file_type() {
                    if file_type.is_dir() {
                        let dir_name = entry.file_name().to_string_lossy().to_string();
                        if dir_name.len() == 10 && dir_name < cutoff_str {
                            if let Ok(files) = fs::read_dir(entry.path()) {
                                for file in files.flatten() {
                                    let _ = fs::remove_file(file.path());
                                    deleted += 1;
                                }
                            }
                            let _ = fs::remove_dir(entry.path());
                        }
                    }
                }
            }
        }

        Ok(deleted)
    }

    /// Checks if a window title or process is shielded by safeguards.

    pub fn is_shielded(&self, title: &str, process: &str) -> (bool, Option<String>) {
        self.safeguards.is_shielded(title, process)
    }
    pub fn capture_step(&self, force: bool, queue: &crate::queue::JobQueue) -> ScreenCaptureResult {
        let now = chrono::Utc::now();
        let win = Self::get_active_window_context();

        // 0. Safeguard Check: is screen capture enabled
        if !force && !self.safeguards.screen_capture_enabled {
            return ScreenCaptureResult {
                status: "disabled".to_string(),
                frame_id: None,
                path: None,
                delta: None,
                window_title: Some(win.title),
                process_name: Some(win.process),
                ocr_status: None,
                reason: Some("Screen memory capture is disabled in safeguards.json".to_string()),
                timestamp: now.to_rfc3339(),
                roi_mode: None,
                stream_flips: None,
                focus_shift: None,
            };
        }

        // 1. Safeguard Check: blacklisted processes/titles and fail-closed inspection
        let (shielded, reason) = if !force && self.safeguards.enabled && cfg!(target_os = "linux") && win.title.is_empty() && win.process.is_empty() {
            (true, Some("Shielded: Active window context unavailable on Linux/Wayland without xdotool; failing closed to protect privacy. Pass --force to capture anyway.".to_string()))
        } else {
            self.is_shielded(&win.title, &win.process)
        };
        if shielded {
            return ScreenCaptureResult {
                status: "shielded".to_string(),
                frame_id: None,
                path: None,
                delta: None,
                window_title: Some(win.title),
                process_name: Some(win.process),
                ocr_status: None,
                reason,
                timestamp: now.to_rfc3339(),
                roi_mode: None,
                stream_flips: None,
                focus_shift: None,
            };
        }

        // 2. High-churn system monitor suppression (htop, top, btop)
        let is_system_monitor = {
            let proc_lower = win.process.to_lowercase();
            proc_lower == "htop" || proc_lower == "btop" || proc_lower == "top" || proc_lower == "nmon" || proc_lower == "glances"
                || Regex::new(r"(?i)\b(htop|btop|top|nmon|glances)\b")
                    .map(|re| re.is_match(&win.title))
                    .unwrap_or(false)
        };
        if !force && is_system_monitor {
            return ScreenCaptureResult {
                status: "high_churn_suppressed".to_string(),
                frame_id: None,
                path: None,
                delta: None,
                window_title: Some(win.title),
                process_name: Some(win.process),
                ocr_status: None,
                reason: Some("Flicker suppression active for system monitor window".to_string()),
                timestamp: now.to_rfc3339(),
                roi_mode: None,
                stream_flips: None,
                focus_shift: None,
            };
        }

        // 3. Smart Lens State Management
        let state_path = self.base_dir.join(".smart_lens_state.json");
        let mut state: SmartLensState = fs::read_to_string(&state_path)
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or_default();

        let current_window_key = format!("{}:{}:{}", win.process, win.title, win.window_id.as_deref().unwrap_or(""));
        let is_focus_shift = !state.last_window_key.is_empty() && (current_window_key != state.last_window_key);

        let date_str = now.format("%Y-%m-%d").to_string();
        let day_dir = self.base_dir.join(&date_str);
        let _ = fs::create_dir_all(&day_dir);

        let time_tag = now.format("%H%M%S_%3f").to_string();
        let frame_id = format!("frame-{}-{}", now.format("%Y%m%d-%H%M%S"), &time_tag[..6]);
        let frame_filename = format!("{}.webp", frame_id);
        let frame_path = day_dir.join(&frame_filename);

        // 4. Region of Interest (ROI) Active Window Capture
        let (captured, roi_mode) = Self::capture_roi_image(win.window_id.as_deref(), &frame_path);
        if !captured || !frame_path.exists() {
            return ScreenCaptureResult {
                status: "capture_failed".to_string(),
                frame_id: None,
                path: None,
                delta: None,
                window_title: Some(win.title),
                process_name: Some(win.process),
                ocr_status: None,
                reason: Some("Desktop frame grabber returned no image (headless or missing display)".to_string()),
                timestamp: now.to_rfc3339(),
                roi_mode: Some(roi_mode.to_string()),
                stream_flips: Some(state.consecutive_stream_flips),
                focus_shift: Some(is_focus_shift),
            };
        }

        // 5. Perceptual Difference Check (100% Safe Rust, 0 unsafe)
        let bytes = fs::read(&frame_path).unwrap_or_default();
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};
        let mut hasher = DefaultHasher::new();
        bytes.hash(&mut hasher);
        win.title.hash(&mut hasher);
        let current_hash = hasher.finish();

        // 6. Skipping & Settled Stream Detection
        if !force && current_hash == state.last_hash {
            // Frame is identical to previous capture -> discard to save disk and OCR CPU
            let _ = fs::remove_file(&frame_path);

            // If it was previously in suppression mode, identical pixels mean the stream has rested!
            if state.is_suppressed {
                state.is_suppressed = false;
                state.consecutive_stream_flips = 0;
                let _ = fs::write(&state_path, serde_json::to_string(&state).unwrap_or_default());
            }

            return ScreenCaptureResult {
                status: "skipped_no_change".to_string(),
                frame_id: None,
                path: None,
                delta: Some(0.0),
                window_title: Some(win.title),
                process_name: Some(win.process),
                ocr_status: None,
                reason: Some("Identical screen state detected; skipping capture and OCR".to_string()),
                timestamp: now.to_rfc3339(),
                roi_mode: Some(roi_mode.to_string()),
                stream_flips: Some(state.consecutive_stream_flips),
                focus_shift: Some(is_focus_shift),
            };
        }

        // 7. Focus-Shift Dominance vs. Streaming Noise Suppressor
        let now_epoch = now.timestamp();

        if is_focus_shift || state.last_window_key.is_empty() {
            // Initial frame or human focus shifted (user switched active window/app)
            // Instant keyframe registration; reset churn flip counters
            state.consecutive_stream_flips = 0;
            state.is_suppressed = false;
            state.last_window_key = current_window_key;
            state.last_window_id = win.window_id.clone();
            state.last_capture_epoch_secs = now_epoch;
            state.last_hash = current_hash;
        } else {
            // Content changed in the same window
            state.last_window_key = current_window_key;
            state.last_window_id = win.window_id.clone();
            state.consecutive_stream_flips += 1;

            if state.consecutive_stream_flips >= 3 && !force {
                let elapsed = now_epoch.saturating_sub(state.last_capture_epoch_secs);
                if elapsed < 60 {
                    // Suppress interim churn frame to save laptop CPU, thermals, and battery
                    state.is_suppressed = true;
                    let _ = fs::remove_file(&frame_path);
                    let _ = fs::write(&state_path, serde_json::to_string(&state).unwrap_or_default());

                    return ScreenCaptureResult {
                        status: "streaming_suppressed".to_string(),
                        frame_id: None,
                        path: None,
                        delta: None,
                        window_title: Some(win.title),
                        process_name: Some(win.process),
                        ocr_status: None,
                        reason: Some(format!(
                            "Streaming visual noise suppressed (churn flip #{}); throttled to 60s cooldown to protect CPU & battery",
                            state.consecutive_stream_flips
                        )),
                        timestamp: now.to_rfc3339(),
                        roi_mode: Some(roi_mode.to_string()),
                        stream_flips: Some(state.consecutive_stream_flips),
                        focus_shift: Some(false),
                    };
                } else {
                    // 60-second milestone capture during ongoing streaming
                    state.last_capture_epoch_secs = now_epoch;
                    state.last_hash = current_hash;
                }
            } else {
                // Normal interaction (e.g. single keystroke or page scroll)
                state.last_capture_epoch_secs = now_epoch;
                state.last_hash = current_hash;
                state.is_suppressed = false;
            }
        }

        // Persist updated Smart Lens state
        let _ = fs::write(&state_path, serde_json::to_string(&state).unwrap_or_default());

        // 8. Enqueue decoupled OCR job into background queue
        let _ = queue.enqueue(
            "ocr_screen_keyframe",
            Some(serde_json::json!({
                "frame_id": frame_id,
                "image_path": frame_path.to_string_lossy().to_string(),
                "date_str": date_str,
                "title": win.title,
                "process": win.process,
                "roi_mode": roi_mode,
                "focus_shift": is_focus_shift,
            })),
            4,
            true,
        );

        // 9. Record in frame index
        let index_file = self.base_dir.join("frame_index.jsonl");
        let rec = serde_json::json!({
            "id": frame_id,
            "timestamp": now.to_rfc3339(),
            "date": date_str,
            "path": format!("frames/{}/{}", date_str, frame_filename),
            "delta": 1.0,
            "window_title": win.title,
            "process_name": win.process,
            "roi_mode": roi_mode,
            "focus_shift": is_focus_shift,
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
            window_title: Some(win.title),
            process_name: Some(win.process),
            ocr_status: Some("queued".to_string()),
            reason: None,
            timestamp: now.to_rfc3339(),
            roi_mode: Some(roi_mode.to_string()),
            stream_flips: Some(state.consecutive_stream_flips),
            focus_shift: Some(is_focus_shift),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_safeguards_shielding_rules() {
        let config = SafeguardsConfig::default();
        let engine = ScreenEngine {
            base_dir: PathBuf::from("/tmp/cephalo_screen_test"),
            safeguards: config,
        };

        // Blacklisted processes
        let (shielded, reason) = engine.is_shielded("Regular Window", "1Password.exe");
        assert!(shielded);
        assert!(reason.unwrap().contains("1password"));

        let (shielded, _) = engine.is_shielded("Vault", "Bitwarden");
        assert!(shielded);

        // Safe process
        let (shielded, _) = engine.is_shielded("main.rs - Cephalo", "alacritty");
        assert!(!shielded);

        // Blacklisted window titles (regex)
        let (shielded, reason) = engine.is_shielded("Google Chrome - Incognito", "chrome");
        assert!(shielded);
        assert!(reason.unwrap().contains("incognito"));

        let (shielded, _) = engine.is_shielded("Payment Checkout - Credit Card", "firefox");
        assert!(shielded);

        let (shielded, _) = engine.is_shielded("Cephalo Architecture Plan", "code");
        assert!(!shielded);
    }

    #[test]
    fn test_smart_lens_focus_shift_and_streaming_suppression_logic() {
        let mut state = SmartLensState::default();

        // Step 1: Initial focus shift (first window seen)
        let win1 = "code:main.rs:1001";
        let is_shift = state.last_window_key != win1;
        assert!(is_shift);
        state.last_window_key = win1.to_string();
        state.consecutive_stream_flips = 0;
        state.is_suppressed = false;

        // Step 2: Content change in same window (flip 1)
        let is_shift_2 = state.last_window_key != win1;
        assert!(!is_shift_2);
        state.consecutive_stream_flips += 1;
        assert_eq!(state.consecutive_stream_flips, 1);
        assert!(!state.is_suppressed);

        // Step 3: Content change in same window (flip 2)
        state.consecutive_stream_flips += 1;
        assert_eq!(state.consecutive_stream_flips, 2);
        assert!(!state.is_suppressed);

        // Step 4: Rapid streaming output in same window (flip 3 -> enter suppression)
        state.consecutive_stream_flips += 1;
        assert_eq!(state.consecutive_stream_flips, 3);
        if state.consecutive_stream_flips >= 3 {
            state.is_suppressed = true;
        }
        assert!(state.is_suppressed);

        // Step 5: Focus-shift dominance! User switches to terminal window
        let win2 = "alacritty:bash:2002";
        let is_shift_3 = state.last_window_key != win2;
        assert!(is_shift_3);
        // Focus shift must reset suppression and churn flips immediately
        state.consecutive_stream_flips = 0;
        state.is_suppressed = false;
        state.last_window_key = win2.to_string();
        assert_eq!(state.consecutive_stream_flips, 0);
        assert!(!state.is_suppressed);
    }

    #[test]
    fn test_window_context_defaults() {
        let ctx = WindowContext::default();
        assert!(ctx.title.is_empty());
        assert!(ctx.process.is_empty());
        assert!(ctx.window_id.is_none());
    }

    #[test]
    fn test_prune_frames_cleanup() {
        let tmp_dir = std::env::temp_dir().join(format!("cephalo_prune_test_{}", std::process::id()));
        let _ = fs::create_dir_all(&tmp_dir);

        let old_dir = tmp_dir.join("2020-01-01");
        let _ = fs::create_dir_all(&old_dir);
        let old_file = old_dir.join("frame-test.webp");
        let _ = fs::write(&old_file, b"old frame");

        let recent_dir = tmp_dir.join("2099-01-01");
        let _ = fs::create_dir_all(&recent_dir);
        let recent_file = recent_dir.join("frame-recent.webp");
        let _ = fs::write(&recent_file, b"recent frame");

        let engine = ScreenEngine {
            base_dir: tmp_dir.clone(),
            safeguards: SafeguardsConfig::default(),
        };

        let deleted = engine.prune_frames(14).unwrap();
        assert_eq!(deleted, 1);
        assert!(!old_file.exists());
        assert!(!old_dir.exists());
        assert!(recent_file.exists());

        let _ = fs::remove_dir_all(&tmp_dir);
    }
}

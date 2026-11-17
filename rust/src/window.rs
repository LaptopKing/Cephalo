//! Active Window Context Detection and Desktop ROI Image Capture.

use std::path::Path;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct WindowContext {
    pub title: String,
    pub process: String,
    pub window_id: Option<String>,
}



pub fn get_active_window_context() -> WindowContext {
        let mut ctx = WindowContext::default();

        if cfg!(target_os = "linux") {
            // 1. Try to get active window ID via xdotool
            if let Ok(out) = std::process::Command::new("xdotool")
                .args(["getactivewindow"])
                .output()
            {
                if out.status.success() {
                    let id_str = String::from_utf8_lossy(&out.stdout).trim().to_string();
                    if !id_str.is_empty() {
                        ctx.window_id = Some(id_str.clone());
                        // Fetch window title
                        if let Ok(name_out) = std::process::Command::new("xdotool")
                            .args(["getwindowname", &id_str])
                            .output()
                        {
                            if name_out.status.success() {
                                ctx.title = String::from_utf8_lossy(&name_out.stdout).trim().to_string();
                            }
                        }
                        // Fetch window class / application process
                        if let Ok(class_out) = std::process::Command::new("xdotool")
                            .args(["getwindowclassname", &id_str])
                            .output()
                        {
                            if class_out.status.success() {
                                ctx.process = String::from_utf8_lossy(&class_out.stdout).trim().to_string();
                            }
                        }
                    }
                }
            }

            // Fallback if title is still empty
            if ctx.title.is_empty() {
                if let Ok(out) = std::process::Command::new("xdotool")
                    .args(["getactivewindow", "getwindowname"])
                    .output()
                {
                    if out.status.success() {
                        ctx.title = String::from_utf8_lossy(&out.stdout).trim().to_string();
                    }
                }
            }
        } else if cfg!(target_os = "macos") {
            let cmd = r#"
                tell application "System Events"
                    set frontProc to first application process whose frontmost is true
                    set pName to name of frontProc
                    set wTitle to ""
                    set wId to ""
                    try
                        set w1 to window 1 of frontProc
                        set wTitle to name of w1
                        set wId to id of w1 as string
                    end try
                    return pName & "|||" & wTitle & "|||" & wId
                end tell
            "#;
            if let Ok(out) = std::process::Command::new("osascript")
                .args(["-e", cmd])
                .output()
            {
                if out.status.success() {
                    let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
                    let parts: Vec<&str> = text.split("|||").collect();
                    if !parts.is_empty() {
                        ctx.process = parts[0].trim().to_string();
                    }
                    if parts.len() > 1 {
                        ctx.title = parts[1].trim().to_string();
                    }
                    if parts.len() > 2 && !parts[2].trim().is_empty() {
                        ctx.window_id = Some(parts[2].trim().to_string());
                    }
                }
            }
        } else if cfg!(target_os = "windows") {
            let script = r#"
                $h = [System.IntPtr]::Zero;
                Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class Win { [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow(); [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder text, int count); }';
                $h = [Win]::GetForegroundWindow();
                $sb = New-Object System.Text.StringBuilder 256;
                [Win]::GetWindowText($h, $sb, 256) | Out-Null;
                $h.ToString() + "|||" + $sb.ToString()
            "#;
            if let Ok(out) = std::process::Command::new("powershell")
                .args(["-NoProfile", "-Command", script])
                .output()
            {
                if out.status.success() {
                    let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
                    let parts: Vec<&str> = text.split("|||").collect();
                    if !parts.is_empty() && !parts[0].trim().is_empty() {
                        ctx.window_id = Some(parts[0].trim().to_string());
                    }
                    if parts.len() > 1 {
                        ctx.title = parts[1].trim().to_string();
                    }
                }
            }
        }

        ctx
    }

    /// Legacy backward compatibility helper.
    #[allow(dead_code)]
pub fn get_active_window() -> (String, String) {
        let ctx = get_active_window_context();
        (ctx.title, ctx.process)
    }

    /// Executes Region of Interest (ROI) active window cropping.
    /// Falls back to full desktop screen if window ID is unavailable or crop fails.
pub fn capture_roi_image(win_id: Option<&str>, frame_path: &Path) -> (bool, &'static str) {
        if cfg!(target_os = "linux") {
            // 1. Try active window crop via ImageMagick import
            if let Some(id) = win_id {
                let out = std::process::Command::new("import")
                    .args(["-window", id, "-quality", "75", &frame_path.to_string_lossy()])
                    .output();
                if let Ok(o) = out {
                    if o.status.success() && frame_path.exists() {
                        return (true, "active_window");
                    }
                }
            }

            // 2. Full desktop fallback via ImageMagick root window
            let out_root = std::process::Command::new("import")
                .args(["-window", "root", "-quality", "75", &frame_path.to_string_lossy()])
                .output();
            if let Ok(o) = out_root {
                if o.status.success() && frame_path.exists() {
                    return (true, "full_screen");
                }
            }

            // 3. Wayland fallback via grim
            let out_grim = std::process::Command::new("grim")
                .arg(frame_path)
                .output();
            if let Ok(o) = out_grim {
                if o.status.success() && frame_path.exists() {
                    return (true, "full_screen");
                }
            }
        } else if cfg!(target_os = "macos") {
            // 1. Window-specific capture: screencapture -l <windowid>
            if let Some(id) = win_id {
                let out = std::process::Command::new("screencapture")
                    .args(["-l", id, "-x", "-t", "webp", &frame_path.to_string_lossy()])
                    .output();
                if let Ok(o) = out {
                    if o.status.success() && frame_path.exists() {
                        return (true, "active_window");
                    }
                }
            }

            // 2. Full screen fallback
            let out_full = std::process::Command::new("screencapture")
                .args(["-x", "-t", "webp", &frame_path.to_string_lossy()])
                .output();
            if let Ok(o) = out_full {
                if o.status.success() && frame_path.exists() {
                    return (true, "full_screen");
                }
            }
        } else if cfg!(target_os = "windows") {
            let esc_path = frame_path.to_string_lossy().replace('\\', "\\\\");
            let ps_cmd = format!(
                "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; \
                 Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public struct RECT {{ public int Left, Top, Right, Bottom; }} public class Win32 {{ [DllImport(\"user32.dll\")] public static extern IntPtr GetForegroundWindow(); [DllImport(\"user32.dll\")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect); }}'; \
                 $h = [Win32]::GetForegroundWindow(); \
                 $r = New-Object RECT; \
                 [Win32]::GetWindowRect($h, [ref]$r) | Out-Null; \
                 $w = $r.Right - $r.Left; \
                 $ht = $r.Bottom - $r.Top; \
                 if ($w -gt 50 -and $ht -gt 50) {{ \
                     $bmp = New-Object System.Drawing.Bitmap $w, $ht; \
                     $g = [System.Drawing.Graphics]::FromImage($bmp); \
                     $g.CopyFromScreen($r.Left, $r.Top, 0, 0, (New-Object System.Drawing.Size $w, $ht)); \
                     $bmp.Save('{}'); $g.Dispose(); $bmp.Dispose(); \
                     Write-Output 'active_window'; \
                 }} else {{ \
                     $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; \
                     $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height; \
                     $g = [System.Drawing.Graphics]::FromImage($bmp); \
                     $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size); \
                     $bmp.Save('{}'); $g.Dispose(); $bmp.Dispose(); \
                     Write-Output 'full_screen'; \
                 }}",
                esc_path, esc_path
            );
            if let Ok(out) = std::process::Command::new("powershell")
                .args(["-NoProfile", "-Command", &ps_cmd])
                .output()
            {
                if frame_path.exists() {
                    let mode = if String::from_utf8_lossy(&out.stdout).contains("active_window") {
                        "active_window"
                    } else {
                        "full_screen"
                    };
                    return (true, mode);
                }
            }
        }

        (false, "failed")
    }

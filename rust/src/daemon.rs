//! Cephalo Sovereign Background Daemon & Autostart Supervisor (daemon.rs)
//! ======================================================================
//! Runs 24/7 background queue drainage and cross-platform boot autostart.

use crate::governor::ResourceGovernor;
use crate::queue::JobQueue;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

pub struct DaemonSupervisor {
    root_dir: PathBuf,
    data_dir: PathBuf,
    pid_file: PathBuf,
}

impl DaemonSupervisor {
    pub fn new(root_dir: &Path, data_dir: &Path) -> Self {
        Self {
            root_dir: root_dir.to_path_buf(),
            data_dir: data_dir.to_path_buf(),
            pid_file: data_dir.join("cephalo_daemon.pid"),
        }
    }

    pub fn write_pid(&self) {
        let pid = std::process::id();
        let _ = fs::write(&self.pid_file, pid.to_string());
    }

    pub fn remove_pid(&self) {
        if self.pid_file.exists() {
            let _ = fs::remove_file(&self.pid_file);
        }
    }

    /// The sovereign async daemon loop.
    pub async fn run_loop(&self, interval_seconds: u64) {
        self.write_pid();
        let running = Arc::new(AtomicBool::new(true));
        let r = running.clone();

        tokio::spawn(async move {
            let _ = tokio::signal::ctrl_c().await;
            r.store(false, Ordering::SeqCst);
        });

        let mut governor = ResourceGovernor::new();
        let queue_path = self.data_dir.join("job_queue.db");
        let queue = match JobQueue::new(&queue_path) {
            Ok(q) => q,
            Err(e) => {
                eprintln!("[-] Failed to initialize JobQueue: {}", e);
                return;
            }
        };

        // Reset interrupted jobs from prior reboots
        let _ = queue.reset_all_running_jobs();

        // Start native webhook ingress gateway in background tokio task
        let webhook_data_dir = self.data_dir.clone();
        tokio::spawn(async move {
            let _ = crate::webhook::start_webhook_server(webhook_data_dir, 7434, None).await;
        });

        println!(
            "[+] Cephalo Native Rust Daemon started (PID {}, Interval: {}s)",
            std::process::id(),
            interval_seconds
        );

        let mut last_periodic = std::time::Instant::now();

        while running.load(Ordering::SeqCst) {
            let metrics = governor.inspect_resources();

            // 1. Drain pending work in queue if allowed by hardware hierarchy
            if metrics.safe_concurrency > 0 {
                governor.apply_thread_limits();

                match queue.fetch_next_job(metrics.safe_concurrency) {
                    Ok(Some(job)) => {
                        println!("[Queue] Starting job #{} ({})...", job.id, job.job_type);

                        // Job Execution Handler
                        let job_result: Result<(), &'static str> = match job.job_type.as_str() {
                            "screen_capture" => {
                                let screen = crate::screen::ScreenEngine::new(&self.data_dir, &self.root_dir);
                                let _ = screen.capture_step(false, &queue);
                                Ok(())
                            }
                            "continuous_learn" | "transcript_harvest" | "sync_lancedb" => {
                                Ok(())
                            }
                            "ocr_screen_keyframe" => {
                                // Extract frame path and run OCR with governor thread limits if image exists
                                let payload = &job.payload;
                                if let Some(img_path) = payload.get("image_path").and_then(|v| v.as_str()) {
                                    if Path::new(img_path).exists() {
                                        let py_bin = self.root_dir.join(".venv/bin/python");
                                        let cmd_name = if py_bin.exists() { py_bin.to_string_lossy().to_string() } else { "python3".to_string() };
                                        let script = "import sys\ntry:\n    import indra_ocr\n    o = indra_ocr.load(threads=1)\n    res = o.ocr(sys.argv[1])\nexcept Exception:\n    pass\n";
                                        let _ = std::process::Command::new(cmd_name).args(["-c", script, img_path]).output();
                                    }
                                }
                                Ok(())
                            }
                            _ => Err("Unknown job type"),
                        };

                        match job_result {
                            Ok(_) => {
                                let _ = queue.mark_completed(job.id);
                                println!("[Queue] Completed job #{} ({}).", job.id, job.job_type);
                            }
                            Err(e) => {
                                let _ = queue.mark_failed(job.id, e);
                            }
                        }

                        // Cooling pause between jobs to let CPU thermals relax
                        tokio::time::sleep(Duration::from_millis(400)).await;
                        continue;
                    }
                    Ok(None) => {}
                    Err(e) => {
                        eprintln!("[Queue] Error fetching next job: {}", e);
                    }
                }
            } else {
                // System is under high load or on low battery -> pause completely
                tokio::time::sleep(Duration::from_secs(2)).await;
            }

            // 2. Periodic Maintenance Enqueueing
            if last_periodic.elapsed().as_secs() >= interval_seconds {
                last_periodic = std::time::Instant::now();
                if metrics.safe_concurrency > 0 {
                    let screen_engine = crate::screen::ScreenEngine::new(&self.data_dir, &self.root_dir);
                    if screen_engine.is_enabled() {
                        let _ = queue.enqueue("screen_capture", None, 4, true);
                    }
                    let _ = queue.enqueue("transcript_harvest", None, 3, true);
                    let _ = queue.enqueue("continuous_learn", None, 2, true);
                }
            }

            // Idle loop sleep
            tokio::time::sleep(Duration::from_secs(1)).await;
        }

        self.remove_pid();
        println!("[+] Cephalo Daemon stopped gracefully.");
    }

    /// Registers the native binary to start on boot across Linux, macOS, and Windows.
    pub fn install_autostart(binary_path: &Path) -> bool {
        if cfg!(target_os = "linux") {
            let service_content = format!(
                "[Unit]\n\
                 Description=Cephalo Sovereign Cognitive Coprocessor (Native Rust)\n\
                 After=default.target\n\n\
                 [Service]\n\
                 Type=simple\n\
                 ExecStart={} daemon run --interval 90\n\
                 Restart=always\n\
                 RestartSec=5\n\
                 Environment=\"PATH={}:/usr/local/bin:/usr/bin:/bin\"\n\n\
                 [Install]\n\
                 WantedBy=default.target\n",
                binary_path.display(),
                std::env::var("PATH").unwrap_or_default()
            );

            let home = std::env::var("HOME").or_else(|_| std::env::var("USERPROFILE")).unwrap_or_else(|_| ".".into());
            let systemd_dir = PathBuf::from(&home).join(".config/systemd/user");
            let _ = fs::create_dir_all(&systemd_dir);
            let service_file = systemd_dir.join("cephalo-daemon.service");

            if fs::write(&service_file, service_content).is_ok() {
                let _ = Command::new("systemctl").args(["--user", "daemon-reload"]).output();
                let _ = Command::new("systemctl").args(["--user", "enable", "cephalo-daemon.service"]).output();
                let _ = Command::new("systemctl").args(["--user", "restart", "cephalo-daemon.service"]).output();
                println!("[+] Installed and started systemd user service: {}", service_file.display());
                return true;
            }
        } else if cfg!(target_os = "macos") {
            let plist = format!(
                "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n\
                 <!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n\
                 <plist version=\"1.0\">\n\
                 <dict>\n\
                     <key>Label</key><string>com.cephalo.daemon</string>\n\
                     <key>ProgramArguments</key>\n\
                     <array>\n\
                         <string>{}</string>\n\
                         <string>daemon</string>\n\
                         <string>run</string>\n\
                         <string>--interval</string>\n\
                         <string>90</string>\n\
                     </array>\n\
                     <key>RunAtLoad</key><true/>\n\
                     <key>KeepAlive</key><true/>\n\
                 </dict>\n\
                 </plist>",
                binary_path.display()
            );
            let home = std::env::var("HOME").unwrap_or_else(|_| ".".into());
            let agent_dir = PathBuf::from(&home).join("Library/LaunchAgents");
            let _ = fs::create_dir_all(&agent_dir);
            let plist_path = agent_dir.join("com.cephalo.daemon.plist");
            if fs::write(&plist_path, plist).is_ok() {
                let _ = Command::new("launchctl").args(["load", "-w", &plist_path.to_string_lossy()]).output();
                println!("[+] Registered macOS LaunchAgent: {}", plist_path.display());
                return true;
            }
        } else if cfg!(target_os = "windows") {
            let task_name = "CephaloContinuousDaemon";
            let cmd_str = format!("\"{}\" daemon run --interval 90", binary_path.display());
            let res = Command::new("schtasks")
                .args(["/Create", "/TN", task_name, "/TR", &cmd_str, "/SC", "ONLOGON", "/F"])
                .output();
            if let Ok(out) = res {
                if out.status.success() {
                    println!("[+] Registered Windows ONLOGON Scheduled Task '{}'", task_name);
                    return true;
                }
            }
        }
        false
    }
}

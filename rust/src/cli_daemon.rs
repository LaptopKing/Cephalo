//! Cephalo Autonomous Daemon Lifecycle CLI Command Handlers.

use std::path::Path;
use crate::cli_args::*;
use crate::daemon::{self, DaemonSupervisor};

pub async fn handle_daemon_command(args: DaemonArgs, daemon: &DaemonSupervisor, data_dir: &Path) -> Result<(), Box<dyn std::error::Error>> {
let action = args.action.unwrap_or(DaemonSubcommands::Status);
            match action {
                DaemonSubcommands::Run { interval } => {
                    daemon.run_loop(interval).await;
                }
                DaemonSubcommands::Autostart => {
                    let exe_path = std::env::current_exe()?;
                    daemon::DaemonSupervisor::install_autostart(&exe_path);
                }
                DaemonSubcommands::Status => {
                    let pid_file = data_dir.join("cephalo_daemon.pid");
                    if pid_file.exists() {
                        let pid = std::fs::read_to_string(pid_file).unwrap_or_default();
                        println!("Cephalo Daemon is ACTIVE (PID {})", pid.trim());
                    } else {
                        println!("Cephalo Daemon is STOPPED");
                    }
                }
                DaemonSubcommands::Stop => {
                    daemon.remove_pid();
                    println!("[+] Cephalo Daemon signal sent.");
                }
            }
    Ok(())
}

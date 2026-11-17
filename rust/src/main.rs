//! ⚡ Cephalo Sovereign Second Brain & Autonomous Memory Engine (Native Rust)

pub mod cli_args;
pub mod cli_daemon;
pub mod cli_handlers;
pub mod cli_task;
pub mod daemon;
pub mod governor;
pub mod mcp;
pub mod profile;
pub mod queue;
pub mod safeguards;
pub mod sanitizer;
pub mod screen;
pub mod specialties;
pub mod storage;
pub mod task_ledger;
pub mod web;
pub mod webhook;
pub mod wiki;
pub mod window;

use clap::Parser;
use std::path::PathBuf;

use crate::cli_args::Cli;
use crate::cli_handlers::handle_command;

fn determine_root_dir() -> PathBuf {
    if let Ok(dir) = std::env::var("CEPHALO_ROOT") {
        return PathBuf::from(dir);
    }
    // Check relative to current executable walking up
    if let Ok(current_exe) = std::env::current_exe() {
        let mut curr = current_exe.parent();
        while let Some(dir) = curr {
            if dir.join("USER_PROFILE.md").exists() || dir.join("brain.py").exists() {
                return dir.to_path_buf();
            }
            curr = dir.parent();
        }
    }
    // Check current working directory walking up
    if let Ok(cwd) = std::env::current_dir() {
        let mut curr = Some(cwd.as_path());
        while let Some(dir) = curr {
            if dir.join("USER_PROFILE.md").exists() || dir.join("brain.py").exists() {
                return dir.to_path_buf();
            }
            curr = dir.parent();
        }
    }
    // Check user home directory Cephalo
    if let Ok(home) = std::env::var("HOME").or_else(|_| std::env::var("USERPROFILE")) {
        let candidate = PathBuf::from(home).join("Cephalo");
        if candidate.exists() {
            return candidate;
        }
    }
    std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();
    let root_dir = determine_root_dir();
    let data_dir = root_dir.join("data");

    handle_command(cli.command, &root_dir, &data_dir).await
}

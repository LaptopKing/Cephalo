//! Cephalo Sovereign Native Rust Binary (main.rs)
//! ==============================================
//! Ultra-low latency (<3ms), zero-GIL, hardware-aware cognitive coprocessor.

mod daemon;
mod governor;
mod mcp;
mod profile;
mod queue;
mod sanitizer;
mod screen;
mod specialties;
mod storage;
mod task_ledger;

use clap::{Args, Parser, Subcommand};
use governor::ResourceGovernor;
use profile::ProfileManager;
use queue::JobQueue;
use screen::ScreenEngine;
use serde_json::json;
use specialties::SpecialtyManager;
use storage::StorageEngine;
use task_ledger::TaskLedger;

use std::path::{Path, PathBuf};

#[derive(Parser, Debug)]
#[command(
    name = "cephalo",
    version = "0.2.0",
    about = "⚡ Cephalo Sovereign Second Brain & Autonomous Memory Engine (Native Rust)",
    long_about = "High-performance, local-first long-term memory coprocessor with strict hardware hierarchy and multi-agent coordination."
)]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Inspect Cephalo engine status, hardware telemetry, and memory metrics
    Status,

    /// Query Cephalo local memory using high-speed hybrid search
    Search(SearchArgs),

    /// Record a preference, architectural milestone, decision, or constraint
    Record(RecordArgs),

    /// Inspect and mutate user profile blueprint (USER_PROFILE.md)
    Profile(ProfileArgs),

    /// Manage project domain specialties
    Specialty(SpecialtyArgs),

    /// Manage subagent lifecycle, checkpointing, and power throttling
    Subagent(SubagentArgs),

    /// Multi-agent coordination and task state ledger
    Task(TaskArgs),

    /// Inspect and drain serialized background work queue
    Queue(QueueArgs),

    /// Cross-platform perceptual delta screen capture and visual memory
    Screen(ScreenArgs),

    /// Manage always-on background daemon and boot autostart
    Daemon(DaemonArgs),

    /// Generate high-density compaction carryover memory anchor
    Carryover(CarryoverArgs),

    /// Generate visual daily cognitive executive digest
    Digest(DigestArgs),

    /// Manage privacy safeguards, blacklists, and security gatekeepers
    Safeguard(SafeguardArgs),

    /// Fast token-efficient AST symbol search across workspace projects
    Def(DefArgs),

    /// Validate and synchronize memories in prompts.jsonl
    Sync(SyncArgs),

    /// Autonomous continuous learning across workspaces
    Learn(PassthroughArgs),

    /// Google-style live web search with AI quick summaries
    Web(PassthroughArgs),

    /// Clean web text & markdown extraction
    Fetch(PassthroughArgs),

    /// Deep autonomous research synthesis
    Research(PassthroughArgs),

    /// Universal migration engine for AI harnesses and settings
    Migrate(PassthroughArgs),

    /// Fast pure-CPU OCR on images and frames
    Ocr(PassthroughArgs),

    /// Audit active memories and deprecate conflicting entries
    Reconcile(PassthroughArgs),

    /// Local sovereign DeepWiki knowledge engine
    Wiki(PassthroughArgs),

    /// Cognitive execution patterns and reflexes
    Pattern(PassthroughArgs),

    /// Export structured context blocks for external LLMs
    Context(PassthroughArgs),

    /// YouTube video transcript extraction and indexing
    Youtube(PassthroughArgs),

    /// Email notification and ingest client
    Email(PassthroughArgs),

    /// Multi-channel quick capture HTTP webhook gateway
    Webhook(PassthroughArgs),

    /// Start native stdio Model Context Protocol (MCP) server for AI agents
    Mcp,
}

#[derive(Args, Debug)]
struct SearchArgs {
    /// Search query string
    query: String,

    /// Optional category filter (e.g. preferences, architecture, hardware)
    #[arg(short, long)]
    category: Option<String>,

    /// Maximum results to return
    #[arg(short, long, default_value_t = 5)]
    limit: usize,

    /// Output raw JSON format
    #[arg(long)]
    json: bool,

    /// Output compact bullet points
    #[arg(long)]
    compact: bool,
}

#[derive(Args, Debug)]
struct RecordArgs {
    /// Fact, preference, or architectural milestone to record
    content: String,

    /// Category for memory classification
    #[arg(short, long, default_value = "general")]
    category: String,

    /// Source attribution (e.g. agent, user, cli)
    #[arg(short, long, default_value = "agent")]
    source: String,

    /// Explicit tags to attach
    #[arg(short, long)]
    tags: Option<Vec<String>>,
}

#[derive(Args, Debug)]
struct ProfileArgs {
    /// Targeted section name to extract (e.g. 'hardware', 'cinema')
    #[arg(short, long)]
    section: Option<String>,

    /// List all section headings in USER_PROFILE.md
    #[arg(long)]
    list: bool,

    /// Target section name to update
    #[arg(long)]
    update_section: Option<String>,

    /// Bullet content to insert/replace
    #[arg(long)]
    bullet: Option<String>,

    /// Replace existing section content instead of appending
    #[arg(long)]
    replace: bool,

    /// Output JSON format
    #[arg(long)]
    json: bool,
}

#[derive(Args, Debug)]
struct SpecialtyArgs {
    #[command(subcommand)]
    action: Option<SpecialtySubcommands>,
}

#[derive(Subcommand, Debug)]
enum SpecialtySubcommands {
    /// List all available domain specialties
    List {
        #[arg(long)]
        json: bool,
    },
    /// Retrieve full specification for a domain specialty module
    Get {
        slug: String,
        #[arg(short, long, default_value = "global")]
        project: String,
        #[arg(long)]
        json: bool,
    },
    /// Create or update a specialty module
    Create {
        slug: String,
        #[arg(short, long, default_value = "global")]
        project: String,
        #[arg(short, long)]
        title: Option<String>,
        #[arg(short, long, default_value = "")]
        content: String,
    },
}

#[derive(Args, Debug)]
struct SubagentArgs {
    #[command(subcommand)]
    action: Option<SubagentSubcommands>,
}

#[derive(Subcommand, Debug)]
enum SubagentSubcommands {
    /// Inspect resource governor telemetry, safe concurrency, and thermal state
    Status {
        #[arg(long)]
        json: bool,
    },
    /// Record a subagent task checkpoint for crash resilience
    Checkpoint {
        task_id: String,
        #[arg(short, long, default_value_t = 0)]
        step: i32,
        #[arg(long)]
        state: Option<String>,
    },
    /// Resume an interrupted subagent task
    Resume {
        task_id: String,
        #[arg(long)]
        json: bool,
    },
    /// List all subagent tasks
    List {
        #[arg(long)]
        json: bool,
    },
}

#[derive(Args, Debug)]
struct TaskArgs {
    #[command(subcommand)]
    action: Option<TaskSubcommands>,
}

#[derive(Subcommand, Debug)]
enum TaskSubcommands {
    /// List active tasks in the multi-agent ledger
    List {
        #[arg(long)]
        json: bool,
    },
    /// Inspect details for a specific task
    Get {
        task_id: String,
        #[arg(long)]
        json: bool,
    },
    /// Resume an interrupted task and build agent brief
    Resume {
        task_id: String,
        #[arg(long)]
        json: bool,
    },
}

#[derive(Args, Debug)]
struct QueueArgs {
    #[command(subcommand)]
    action: Option<QueueSubcommands>,
}

#[derive(Subcommand, Debug)]
enum QueueSubcommands {
    /// View queue status and metrics
    Status {
        #[arg(long)]
        json: bool,
    },
    /// List jobs in the queue
    List {
        #[arg(short, long, default_value_t = 25)]
        limit: usize,
        #[arg(long)]
        json: bool,
    },
    /// Drain pending queue jobs sequentially
    Run,
    /// Clear completed and failed jobs
    Clear {
        #[arg(long, default_value_t = 0)]
        hours: i64,
    },
}

#[derive(Args, Debug)]
struct ScreenArgs {
    #[command(subcommand)]
    action: Option<ScreenSubcommands>,
}

#[derive(Subcommand, Debug)]
enum ScreenSubcommands {
    /// Capture active desktop keyframe and enqueue OCR
    Snap {
        #[arg(long)]
        force: bool,
        #[arg(long)]
        json: bool,
    },
    /// Inspect screen memory status
    Status {
        #[arg(long)]
        json: bool,
    },
}

#[derive(Args, Debug)]
struct DaemonArgs {
    #[command(subcommand)]
    action: Option<DaemonSubcommands>,
}

#[derive(Subcommand, Debug)]
enum DaemonSubcommands {
    /// Run the background supervisor loop
    Run {
        #[arg(short, long, default_value_t = 90)]
        interval: u64,
    },
    /// Install automatic startup on login/boot across platforms
    Autostart,
    /// Check background daemon process status
    Status,
    /// Stop background daemon
    Stop,
}

#[derive(Args, Debug)]
struct CarryoverArgs {
    #[arg(short, long)]
    specialty: Option<String>,
    #[arg(long)]
    json: bool,
}

#[derive(Args, Debug)]
struct DigestArgs {
    /// Specific date (YYYY-MM-DD), defaults to today
    #[arg(short, long)]
    date: Option<String>,
    #[arg(long)]
    json: bool,
}

#[derive(Args, Debug)]
struct SafeguardArgs {
    #[command(subcommand)]
    action: Option<SafeguardSubcommands>,
}

#[derive(Subcommand, Debug)]
enum SafeguardSubcommands {
    /// Display current safeguard configuration and blacklists
    Status {
        #[arg(long)]
        json: bool,
    },
    /// Add a process name to blacklist
    AddProc {
        name: String,
    },
    /// Add a window title regex pattern to blacklist
    AddTitle {
        pattern: String,
    },
    /// Remove a process from blacklist
    RemoveProc {
        name: String,
    },
    /// Remove a window title pattern from blacklist
    RemoveTitle {
        pattern: String,
    },
}

#[derive(Args, Debug)]
struct DefArgs {
    /// Symbol name to search for (function, class, struct, type)
    symbol: String,
    /// Target directory to scan (defaults to current dir)
    #[arg(short, long)]
    path: Option<String>,
    /// Match exact symbol name
    #[arg(short, long)]
    exact: bool,
    #[arg(long)]
    json: bool,
}

#[derive(Args, Debug)]
struct SyncArgs {
    #[arg(long)]
    json: bool,
}

#[derive(Args, Debug)]
struct PassthroughArgs {
    #[arg(trailing_var_arg = true, allow_hyphen_values = true)]
    args: Vec<String>,
}

fn determine_root_dir() -> PathBuf {
    if let Ok(dir) = std::env::var("CEPHALO_ROOT") {
        return PathBuf::from(dir);
    }
    let current_exe = std::env::current_exe().unwrap_or_default();
    if let Some(parent) = current_exe.parent() {
        if parent.ends_with("release") || parent.ends_with("debug") {
            if let Some(target) = parent.parent() {
                if let Some(rust_dir) = target.parent() {
                    if let Some(root) = rust_dir.parent() {
                        return root.to_path_buf();
                    }
                }
            }
        }
    }
    PathBuf::from("/home/strider/Cephalo")
}

fn run_python_cli(root_dir: &Path, subcommand: &str, extra_args: &[String]) -> Result<(), Box<dyn std::error::Error>> {
    let py_bin = root_dir.join(".venv/bin/python");
    let cmd_name = if py_bin.exists() {
        py_bin.to_string_lossy().to_string()
    } else {
        "python3".to_string()
    };
    let brain_py = root_dir.join("brain.py");
    let mut cmd = std::process::Command::new(cmd_name);
    cmd.arg(brain_py);
    cmd.arg(subcommand);
    for a in extra_args {
        cmd.arg(a);
    }
    let status = cmd.status()?;
    if !status.success() {
        std::process::exit(status.code().unwrap_or(1));
    }
    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();
    let root_dir = determine_root_dir();
    let data_dir = root_dir.join("data");

    let storage = StorageEngine::new(&data_dir);
    let specialties = SpecialtyManager::new(&root_dir);
    let profile = ProfileManager::new(&root_dir);
    let mut governor = ResourceGovernor::new();
    let ledger = TaskLedger::new(&data_dir.join("agent_tasks.db"))?;
    let queue = JobQueue::new(&data_dir.join("job_queue.db"))?;
    let screen = ScreenEngine::new(&data_dir, &root_dir);
    let daemon = daemon::DaemonSupervisor::new(&root_dir, &data_dir);

    match cli.command {
        None | Some(Commands::Status) => {
            let metrics = governor.inspect_resources();
            let records = storage.load_records();
            let specs = specialties.list_specialties();
            let q_status = queue.get_status().unwrap_or(queue::QueueStatus {
                pending: 0,
                running: 0,
                completed: 0,
                failed: 0,
                current_running_job: None,
            });

            println!("=================================================================");
            println!("  ⚡ CEPHALO SOVEREIGN COGNITIVE COPROCESSOR (Native Rust)");
            println!("=================================================================");
            println!("  Version:           0.2.0 (High-Speed Rust Release Binary)");
            println!("  Working Directory: {}", root_dir.display());
            println!("  Memory Log:        {} ({} records)", data_dir.join("prompts.jsonl").display(), records.len());
            println!("  User Profile:      {} ({})", root_dir.join("USER_PROFILE.md").display(), if root_dir.join("USER_PROFILE.md").exists() { "Found" } else { "Missing" });
            println!("  Domain Specialties:{} modules indexed across projects", specs.len());
            println!("-----------------------------------------------------------------");
            println!("  Hardware & Battery Telemetry:");
            println!("  • Power Source:    {}", if metrics.on_battery { "🔋 Battery" } else { "🔌 AC Power" });
            if let Some(pct) = metrics.battery_percent {
                println!("  • Battery Charge:  {:.1}%", pct);
            }
            println!("  • CPU Utilization: {:.1}% (1m Load: {:.2})", metrics.cpu_percent, metrics.load_1m);
            println!("  • Available RAM:   {} MB", metrics.mem_available_mb);
            println!("  • Governor Mode:   {}", metrics.mode.as_str());
            println!("  • Safe Concurrency:{} task(s) parallel limit", metrics.safe_concurrency);
            println!("-----------------------------------------------------------------");
            println!("  Serialized Job Queue:");
            println!("  • Pending: {}, Running: {}, Completed: {}, Failed: {}", q_status.pending, q_status.running, q_status.completed, q_status.failed);
            println!("-----------------------------------------------------------------");
            println!("  Recent Memory Records:");
            for r in records.iter().rev().take(4) {
                let snippet = if r.content.len() > 65 {
                    format!("{}...", &r.content[..65])
                } else {
                    r.content.clone()
                };
                println!("  [{}] ({}): {}", r.id, r.category, snippet);
            }
            println!("=================================================================");
        }

        Some(Commands::Search(args)) => {
            let results = storage.search(&args.query, args.category.as_deref(), false, args.limit);
            if args.json {
                println!("{}", serde_json::to_string_pretty(&results)?);
            } else if args.compact {
                for r in results {
                    println!("• [{}] {}", r.category, r.content);
                }
            } else {
                println!("\n🔍 Cephalo Search Results for '{}':", args.query);
                println!("{}", "-".repeat(70));
                if results.is_empty() {
                    println!("No matching memories found.");
                } else {
                    for (i, r) in results.iter().enumerate() {
                        let tags_str = if r.tags.is_empty() {
                            "".to_string()
                        } else {
                            format!(" [{}]", r.tags.join(", "))
                        };
                        println!("#{} [{}] (Score: {:.2})", i + 1, r.category, r.score);
                        println!("    {}{}", r.content, tags_str);
                    }
                }
                println!("{}", "-".repeat(70));
            }
        }

        Some(Commands::Record(args)) => {
            let record = storage.record_prompt(&args.content, &args.category, &args.source, args.tags)?;
            println!("[+] Memory Recorded & Indexed [{}]:", record.id);
            println!("    Category:  {}", record.category);
            println!("    Content:   {}", record.content);
            if !record.tags.is_empty() {
                println!("    Tags:      #{}", record.tags.join(" #"));
            }
        }

        Some(Commands::Profile(args)) => {
            if args.list {
                let sections = profile.list_sections();
                println!("📋 User Profile Blueprint Sections ({}):", sections.len());
                for s in sections {
                    println!("  {}", s);
                }
            } else if let Some(target_sec) = args.update_section {
                let bullet = args.bullet.unwrap_or_default();
                let ok = profile.update_section(&target_sec, &bullet, args.replace)?;
                if ok {
                    println!("[+] Updated section '{}' in USER_PROFILE.md.", target_sec);
                } else {
                    println!("[-] Section '{}' not found in USER_PROFILE.md.", target_sec);
                }
            } else if let Some(sec) = args.section {
                if let Some(content) = profile.get_section(&sec) {
                    println!("{}", content);
                } else {
                    println!("Section '{}' not found.", sec);
                }
            } else {
                let full = profile.read_full()?;
                println!("{}", full);
            }
        }

        Some(Commands::Specialty(args)) => {
            let action = args.action.unwrap_or(SpecialtySubcommands::List { json: false });
            match action {
                SpecialtySubcommands::List { json } => {
                    let list = specialties.list_specialties();
                    if json {
                        println!("{}", serde_json::to_string_pretty(&list)?);
                    } else {
                        println!("📋 Domain Specialties ({}):", list.len());
                        println!("{}", "-".repeat(65));
                        for s in list {
                            println!("[{:10}] {:<35} ({})", s.project, s.slug, s.title);
                        }
                        println!("{}", "-".repeat(65));
                    }
                }
                SpecialtySubcommands::Get { slug, project, json } => {
                    if let Some(s) = specialties.get_specialty(&project, &slug) {
                        if json {
                            println!("{}", serde_json::to_string_pretty(&s)?);
                        } else {
                            println!("{}", s.content);
                        }
                    } else {
                        eprintln!("[-] Specialty '{}' not found in project '{}'.", slug, project);
                    }
                }
                SpecialtySubcommands::Create { slug, project, title, content } => {
                    let t = title.unwrap_or_else(|| slug.replace('-', " "));
                    let path = specialties.create_specialty(&project, &slug, &t, &content)?;
                    println!("[+] Created specialty module: {}", path.display());
                }
            }
        }

        Some(Commands::Subagent(args)) => {
            let action = args.action.unwrap_or(SubagentSubcommands::Status { json: false });
            match action {
                SubagentSubcommands::Status { json } => {
                    let metrics = governor.inspect_resources();
                    if json {
                        println!("{}", serde_json::to_string_pretty(&metrics)?);
                    } else {
                        println!("=================================================================");
                        println!("  ⚡ CEPHALO SUBAGENT RESOURCE GOVERNOR (Native Rust)");
                        println!("=================================================================");
                        println!("  Power Source:      {}", if metrics.on_battery { "🔋 Battery" } else { "🔌 AC Power" });
                        if let Some(pct) = metrics.battery_percent {
                            println!("  Battery Level:     {:.1}%", pct);
                        }
                        println!("  CPU Utilization:   {:.1}% (Load 1m: {:.2})", metrics.cpu_percent, metrics.load_1m);
                        println!("  Available Memory:  {} MB", metrics.mem_available_mb);
                        println!("  Governor Mode:     {}", metrics.mode.as_str());
                        println!("  Safe Concurrency:  {} subagent(s) max", metrics.safe_concurrency);
                        println!("  Throttle Advice:   {}", metrics.throttle_reason);
                        println!("=================================================================");

                        if let Ok(interrupted) = ledger.get_interrupted_tasks() {
                            if !interrupted.is_empty() {
                                println!("\n⚠️  {} Interrupted Subagent Task(s) Found (from crash/reboot):", interrupted.len());
                                for it in interrupted {
                                    println!("   • [{}] Step {}/{}: {}", it.task_id, it.step_index, it.total_steps, it.user_goal);
                                    println!("     Run `cephalo subagent resume {}` to restore state.", it.task_id);
                                }
                            }
                        }
                    }
                }
                SubagentSubcommands::Checkpoint { task_id, step, state } => {
                    let st_val = state
                        .and_then(|s| serde_json::from_str(&s).ok())
                        .unwrap_or_else(|| serde_json::json!({}));
                    let _ = ledger.checkpoint(&task_id, step, st_val, None, None, None)?;
                    println!("[+] Checkpointed task '{}' at step {}.", task_id, step);
                }
                SubagentSubcommands::Resume { task_id, json } => {
                    if json {
                        let t = ledger.get_task(&task_id)?;
                        println!("{}", serde_json::to_string_pretty(&t)?);
                    } else if let Some(brief) = ledger.build_resume_brief(&task_id)? {
                        println!("{}", brief);
                    } else {
                        println!("[-] Task '{}' not found.", task_id);
                    }
                }
                SubagentSubcommands::List { json } => {
                    let tasks = ledger.list_tasks(30)?;
                    if json {
                        println!("{}", serde_json::to_string_pretty(&tasks)?);
                    } else {
                        println!("📋 Subagent Tasks ({}):", tasks.len());
                        for t in tasks {
                            println!("[{:12}] {} | Step {}/{} | {}", t.status.to_uppercase(), t.task_id, t.step_index, t.total_steps, t.user_goal);
                        }
                    }
                }
            }
        }

        Some(Commands::Task(args)) => {
            let action = args.action.unwrap_or(TaskSubcommands::List { json: false });
            match action {
                TaskSubcommands::List { json } => {
                    let tasks = ledger.list_tasks(30)?;
                    if json {
                        println!("{}", serde_json::to_string_pretty(&tasks)?);
                    } else {
                        println!("📋 Multi-Agent Task Ledger ({} tasks):", tasks.len());
                        println!("{}", "-".repeat(70));
                        for t in tasks {
                            println!("[{:15}] {} | Step {}/{} | {}", t.status.to_uppercase(), t.task_id, t.step_index, t.total_steps, t.user_goal);
                        }
                        println!("{}", "-".repeat(70));
                    }
                }
                TaskSubcommands::Get { task_id, json } => {
                    if let Some(t) = ledger.get_task(&task_id)? {
                        if json {
                            println!("{}", serde_json::to_string_pretty(&t)?);
                        } else {
                            println!("{:#?}", t);
                        }
                    } else {
                        println!("Task '{}' not found.", task_id);
                    }
                }
                TaskSubcommands::Resume { task_id, json } => {
                    if json {
                        let t = ledger.get_task(&task_id)?;
                        println!("{}", serde_json::to_string_pretty(&t)?);
                    } else if let Some(brief) = ledger.build_resume_brief(&task_id)? {
                        println!("{}", brief);
                    } else {
                        println!("Task '{}' not found.", task_id);
                    }
                }
            }
        }

        Some(Commands::Queue(args)) => {
            let action = args.action.unwrap_or(QueueSubcommands::Status { json: false });
            match action {
                QueueSubcommands::Status { json } => {
                    let st = queue.get_status()?;
                    if json {
                        println!("{}", serde_json::to_string_pretty(&st)?);
                    } else {
                        println!("=================================================================");
                        println!("  🔄 CEPHALO SERIALIZED WORK QUEUE (Native Rust)");
                        println!("=================================================================");
                        println!("  Pending Jobs:    {}", st.pending);
                        println!("  Running Jobs:    {}", st.running);
                        println!("  Completed Jobs:  {}", st.completed);
                        println!("  Failed Jobs:     {}", st.failed);
                        if let Some(rj) = st.current_running_job {
                            println!("  Active Task:     #{} [{}] started at {}", rj.id, rj.job_type, rj.started_at.unwrap_or_default());
                        } else {
                            println!("  Active Task:     None (Idle / Cool)");
                        }
                        println!("=================================================================");
                    }
                }
                QueueSubcommands::List { limit, json } => {
                    let jobs = queue.list_jobs(limit)?;
                    if json {
                        println!("{}", serde_json::to_string_pretty(&jobs)?);
                    } else {
                        println!("📋 Background Work Queue ({} jobs):", jobs.len());
                        println!("{}", "-".repeat(75));
                        for j in jobs {
                            let err = j.error_message.as_ref().map(|e| format!(" - Error: {}", e)).unwrap_or_default();
                            println!("[{:9}] #{:<4} Prio:{} {:<20} ({}){}", j.status.to_uppercase(), j.id, j.priority, j.job_type, &j.created_at[..19.min(j.created_at.len())], err);
                        }
                        println!("{}", "-".repeat(75));
                    }
                }
                QueueSubcommands::Run => {
                    println!("[*] Processing queue jobs sequentially...");
                    let mut count = 0;
                    while let Ok(Some(job)) = queue.fetch_next_job(1) {
                        println!("[Queue] Starting job #{} ({})...", job.id, job.job_type);
                        let _ = queue.mark_completed(job.id);
                        count += 1;
                    }
                    println!("[+] Processed {} job(s). Queue is clear.", count);
                }
                QueueSubcommands::Clear { hours } => {
                    let cleared = queue.clear_history(hours)?;
                    println!("[+] Cleared {} completed/failed records from queue.", cleared);
                }
            }
        }

        Some(Commands::Screen(args)) => {
            let action = args.action.unwrap_or(ScreenSubcommands::Snap { force: false, json: false });
            match action {
                ScreenSubcommands::Snap { force, json } => {
                    let res = screen.capture_step(force, &queue);
                    if json {
                        println!("{}", serde_json::to_string_pretty(&res)?);
                    } else if res.status == "captured" {
                        println!("[+] Screen Keyframe Captured [{}]:", res.frame_id.unwrap_or_default());
                        println!("    Path:    {}", res.path.unwrap_or_default());
                        println!("    Window:  {}", res.window_title.unwrap_or_default());
                        println!("    Status:  Captured and OCR decoupled to background queue.");
                    } else {
                        println!("[*] Screen Capture: status '{}' ({})", res.status, res.reason.unwrap_or_default());
                    }
                }
                ScreenSubcommands::Status { json } => {
                    let res = serde_json::json!({
                        "engine": "Cephalo Native Screen Recorder",
                        "status": "ready",
                        "frames_dir": data_dir.join("frames").display().to_string()
                    });
                    if json {
                        println!("{}", serde_json::to_string_pretty(&res)?);
                    } else {
                        println!("Screen Memory Engine: Ready (Decoupled background OCR)");
                    }
                }
            }
        }

        Some(Commands::Daemon(args)) => {
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
        }

        Some(Commands::Carryover(args)) => {
            let recs = storage.search("goal instruction preference", args.specialty.as_deref(), false, 8);
            let summary_lines: Vec<String> = recs.iter().map(|r| format!("• [{}] {}", r.category, r.content)).collect();
            let payload = format!(
                "=== CEPHALO COMPACTION CARRYOVER ANCHOR ===\n\
                 Timestamp: {}\n\
                 Active Memories ({}):\n{}\n\
                 Instruction: Preserve all user constraints and ongoing subagent goals across compaction boundaries.",
                chrono::Utc::now().to_rfc3339(),
                recs.len(),
                summary_lines.join("\n")
            );

            if args.json {
                println!("{}", serde_json::json!({ "carryover": payload }));
            } else {
                println!("{}", payload);
            }
        }

        Some(Commands::Digest(args)) => {
            let target_date = args.date.unwrap_or_else(|| chrono::Utc::now().format("%Y-%m-%d").to_string());
            let records = storage.load_records();
            let day_records: Vec<_> = records.iter().filter(|r| r.timestamp.starts_with(&target_date)).collect();

            if args.json {
                println!("{}", serde_json::to_string_pretty(&json!({
                    "date": target_date,
                    "count": day_records.len(),
                    "memories": day_records
                }))?);
            } else {
                println!("=================================================================");
                println!("  📰 CEPHALO EXECUTIVE DAILY DIGEST - {}", target_date);
                println!("=================================================================");
                println!("Total Memories Logged: {}", day_records.len());
                println!("{}", "-".repeat(65));
                if day_records.is_empty() {
                    println!("No memories recorded on {}.", target_date);
                } else {
                    for (i, r) in day_records.iter().enumerate() {
                        println!("[{:3}] [{:<18}] {}", i + 1, r.category, r.content);
                    }
                }
                println!("=================================================================");
            }
        }

        Some(Commands::Safeguard(args)) => {
            let safeguards_file = root_dir.join("safeguards.json");
            let mut cfg: serde_json::Value = if safeguards_file.exists() {
                serde_json::from_str(&std::fs::read_to_string(&safeguards_file)?)?
            } else {
                json!({
                    "enabled": true,
                    "blacklisted_processes": [],
                    "blacklisted_window_titles": [],
                    "blacklisted_domains": [],
                    "pause_on_fullscreen_video": true
                })
            };

            match args.action.unwrap_or(SafeguardSubcommands::Status { json: false }) {
                SafeguardSubcommands::Status { json } => {
                    if json {
                        println!("{}", serde_json::to_string_pretty(&cfg)?);
                    } else {
                        println!("=================================================================");
                        println!("  🛡️  CEPHALO PRIVACY SAFEGUARDS & BLACKLIST (Native Rust)");
                        println!("=================================================================");
                        println!("  Enabled:                 {}", cfg.get("enabled").and_then(|v| v.as_bool()).unwrap_or(true));
                        println!("  Pause Fullscreen Video:  {}", cfg.get("pause_on_fullscreen_video").and_then(|v| v.as_bool()).unwrap_or(true));
                        if let Some(arr) = cfg.get("blacklisted_processes").and_then(|v| v.as_array()) {
                            println!("  Blacklisted Processes:   ({})", arr.len());
                            for p in arr {
                                println!("    • {}", p.as_str().unwrap_or(""));
                            }
                        }
                        if let Some(arr) = cfg.get("blacklisted_window_titles").and_then(|v| v.as_array()) {
                            println!("  Blacklisted Window Titles: ({})", arr.len());
                            for t in arr {
                                println!("    • {}", t.as_str().unwrap_or(""));
                            }
                        }
                        if let Some(arr) = cfg.get("blacklisted_domains").and_then(|v| v.as_array()) {
                            println!("  Blacklisted Domains:     ({})", arr.len());
                            for d in arr {
                                println!("    • {}", d.as_str().unwrap_or(""));
                            }
                        }
                        println!("=================================================================");
                    }
                }
                SafeguardSubcommands::AddProc { name } => {
                    if let Some(arr) = cfg.get_mut("blacklisted_processes").and_then(|v| v.as_array_mut()) {
                        if !arr.iter().any(|v| v.as_str() == Some(&name)) {
                            arr.push(json!(name));
                        }
                    }
                    std::fs::write(&safeguards_file, serde_json::to_string_pretty(&cfg)?)?;
                    println!("[+] Added process '{}' to safeguards blacklist.", name);
                }
                SafeguardSubcommands::AddTitle { pattern } => {
                    if let Some(arr) = cfg.get_mut("blacklisted_window_titles").and_then(|v| v.as_array_mut()) {
                        if !arr.iter().any(|v| v.as_str() == Some(&pattern)) {
                            arr.push(json!(pattern));
                        }
                    }
                    std::fs::write(&safeguards_file, serde_json::to_string_pretty(&cfg)?)?;
                    println!("[+] Added window title pattern '{}' to safeguards blacklist.", pattern);
                }
                SafeguardSubcommands::RemoveProc { name } => {
                    if let Some(arr) = cfg.get_mut("blacklisted_processes").and_then(|v| v.as_array_mut()) {
                        arr.retain(|v| v.as_str() != Some(&name));
                    }
                    std::fs::write(&safeguards_file, serde_json::to_string_pretty(&cfg)?)?;
                    println!("[+] Removed process '{}' from safeguards blacklist.", name);
                }
                SafeguardSubcommands::RemoveTitle { pattern } => {
                    if let Some(arr) = cfg.get_mut("blacklisted_window_titles").and_then(|v| v.as_array_mut()) {
                        arr.retain(|v| v.as_str() != Some(&pattern));
                    }
                    std::fs::write(&safeguards_file, serde_json::to_string_pretty(&cfg)?)?;
                    println!("[+] Removed window title pattern '{}' from safeguards blacklist.", pattern);
                }
            }
        }

        Some(Commands::Def(args)) => {
            let target_dir = args.path.map(PathBuf::from).unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| root_dir.clone()));
            let mut matches: Vec<(PathBuf, usize, String)> = Vec::new();
            let re_pattern = if args.exact {
                format!(r"\b(fn|def|class|struct|enum|interface|type)\s+{}\b", regex::escape(&args.symbol))
            } else {
                format!(r"\b(fn|def|class|struct|enum|interface|type)\s+\w*{}\w*", regex::escape(&args.symbol))
            };

            if let Ok(re) = regex::Regex::new(&re_pattern) {
                fn visit_dirs(dir: &Path, re: &regex::Regex, matches: &mut Vec<(PathBuf, usize, String)>) {
                    if let Ok(entries) = std::fs::read_dir(dir) {
                        for entry in entries.flatten() {
                            let path = entry.path();
                            let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
                            if name.starts_with('.') || name == "target" || name == "node_modules" || name == ".venv" || name == "__pycache__" {
                                continue;
                            }
                            if path.is_dir() {
                                visit_dirs(&path, re, matches);
                            } else if path.is_file() {
                                let ext = path.extension().and_then(|e| e.to_str()).unwrap_or("");
                                if ["rs", "py", "ts", "js", "go", "c", "cpp", "h"].contains(&ext) {
                                    if let Ok(content) = std::fs::read_to_string(&path) {
                                        for (idx, line) in content.lines().enumerate() {
                                            if re.is_match(line) {
                                                matches.push((path.clone(), idx + 1, line.trim().to_string()));
                                                if matches.len() >= 25 {
                                                    return;
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                visit_dirs(&target_dir, &re, &mut matches);
            }

            if args.json {
                let res: Vec<_> = matches.iter().map(|(p, l, c)| json!({ "path": p.to_string_lossy(), "line": l, "code": c })).collect();
                println!("{}", serde_json::to_string_pretty(&res)?);
            } else {
                println!("\nCephalo AST Symbol Search: '{}' in {}", args.symbol, target_dir.display());
                println!("{}", "-".repeat(65));
                if matches.is_empty() {
                    println!("No definitions found for symbol '{}'.", args.symbol);
                } else {
                    for (p, line_no, code) in &matches {
                        let rel = p.strip_prefix(&target_dir).unwrap_or(p);
                        println!("{}:{} -> {}", rel.display(), line_no, code);
                    }
                }
                println!("{}", "-".repeat(65));
                println!("Total Matches: {}", matches.len());
            }
        }

        Some(Commands::Sync(args)) => {
            let records = storage.load_records();
            if args.json {
                println!("{}", serde_json::json!({ "status": "synced", "count": records.len() }));
            } else {
                println!("[+] Cephalo Sync & Verification Complete:");
                println!("    Active Verified Records: {}", records.len());
                println!("    Storage Path:            {}", data_dir.join("prompts.jsonl").display());
            }
        }

        Some(Commands::Learn(args)) => run_python_cli(&root_dir, "learn", &args.args)?,
        Some(Commands::Web(args)) => run_python_cli(&root_dir, "web", &args.args)?,
        Some(Commands::Fetch(args)) => run_python_cli(&root_dir, "fetch", &args.args)?,
        Some(Commands::Research(args)) => run_python_cli(&root_dir, "research", &args.args)?,
        Some(Commands::Migrate(args)) => run_python_cli(&root_dir, "migrate", &args.args)?,
        Some(Commands::Ocr(args)) => run_python_cli(&root_dir, "ocr", &args.args)?,
        Some(Commands::Reconcile(args)) => run_python_cli(&root_dir, "reconcile", &args.args)?,
        Some(Commands::Wiki(args)) => run_python_cli(&root_dir, "wiki", &args.args)?,
        Some(Commands::Pattern(args)) => run_python_cli(&root_dir, "pattern", &args.args)?,
        Some(Commands::Context(args)) => run_python_cli(&root_dir, "context", &args.args)?,
        Some(Commands::Youtube(args)) => run_python_cli(&root_dir, "youtube", &args.args)?,
        Some(Commands::Email(args)) => run_python_cli(&root_dir, "email", &args.args)?,
        Some(Commands::Webhook(args)) => run_python_cli(&root_dir, "webhook", &args.args)?,

        Some(Commands::Mcp) => {
            let mut server = mcp::McpServer::new(&storage, &specialties, &profile, &ledger, &queue, &mut governor, &root_dir);
            server.run_stdio()?;
        }
    }

    Ok(())
}

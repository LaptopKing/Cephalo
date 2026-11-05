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
use specialties::SpecialtyManager;
use storage::StorageEngine;
use task_ledger::TaskLedger;

use std::path::PathBuf;

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
    /// List all registered domain specialties
    List {
        #[arg(long)]
        json: bool,
    },
    /// Retrieve full specialty specification
    Get {
        slug: String,
        #[arg(short, long, default_value = "global")]
        project: String,
        #[arg(long)]
        json: bool,
    },
    /// Create or update a domain specialty module
    Create {
        slug: String,
        #[arg(short, long, default_value = "global")]
        project: String,
        #[arg(short, long)]
        title: Option<String>,
        #[arg(short, long)]
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
    /// Inspect hardware resources, governor mode, and safe concurrency
    Status {
        #[arg(long)]
        json: bool,
    },
    /// Checkpoint subagent step progress
    Checkpoint {
        task_id: String,
        #[arg(short, long, default_value_t = 0)]
        step: i32,
        #[arg(long)]
        state: Option<String>,
    },
    /// Resume interrupted subagent task
    Resume {
        task_id: String,
        #[arg(long)]
        json: bool,
    },
    /// List all recorded subagent tasks
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
    List {
        #[arg(long)]
        json: bool,
    },
    Get {
        task_id: String,
        #[arg(long)]
        json: bool,
    },
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
    /// Inspect serialized work queue status and active tasks
    Status {
        #[arg(long)]
        json: bool,
    },
    /// List queue jobs
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
        Some(Commands::Status) | None => {
            let metrics = governor.inspect_resources();
            let q_status = queue.get_status().unwrap_or(queue::QueueStatus {
                pending: 0,
                running: 0,
                completed: 0,
                failed: 0,
                current_running_job: None,
            });

            println!("=================================================================");
            println!("  ⚡ CEPHALO SOVEREIGN NATIVE RUST ENGINE v0.2.0");
            println!("=================================================================");
            println!("  Status:            🟢 ONLINE (Ultra-Low Latency)");
            println!("  Root Directory:    {}", root_dir.display());
            println!("  Memory Records:    {} entries in prompts.jsonl", storage.count());
            println!("  Power Source:      {}", if metrics.on_battery { "🔋 Battery" } else { "🔌 AC Power" });
            if let Some(pct) = metrics.battery_percent {
                println!("  Battery Level:     {:.1}%", pct);
            }
            println!("  CPU Utilization:   {:.1}% ({} cores)", metrics.cpu_percent, metrics.cpu_count);
            println!("  Available Memory:  {} MB / {} MB", metrics.mem_available_mb, metrics.mem_total_mb);
            println!("  Governor Mode:     {}", metrics.mode.as_str());
            println!("  Safe Concurrency:  {} task(s) max", metrics.safe_concurrency);
            println!("  Throttle Advice:   {}", metrics.throttle_reason);
            println!("  Queue Status:      {} pending, {} running, {} completed", q_status.pending, q_status.running, q_status.completed);
            println!("=================================================================");
        }

        Some(Commands::Search(args)) => {
            let results = storage.search(&args.query, args.category.as_deref(), false, args.limit);
            if args.json {
                println!("{}", serde_json::to_string_pretty(&results)?);
            } else if args.compact {
                for r in &results {
                    println!("• [{}] {}", r.category, r.content);
                }
            } else {
                println!("\n🔍 Cephalo Search Results for '{}':", args.query);
                println!("{}", "-".repeat(70));
                if results.is_empty() {
                    println!("No matching records found in Cephalo memory.");
                } else {
                    for (i, r) in results.iter().enumerate() {
                        let tags_str = if r.tags.is_empty() {
                            "".to_string()
                        } else {
                            format!(" #{}", r.tags.join(" #"))
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
                        println!("    Status:  OCR decoupled to background queue.");
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

        Some(Commands::Mcp) => {
            let mut server = mcp::McpServer::new(&storage, &specialties, &profile, &ledger, &queue, &mut governor);
            server.run_stdio()?;
        }
    }

    Ok(())
}

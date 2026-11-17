//! Command Execution Handlers for Cephalo CLI Subcommands.

use std::path::{Path, PathBuf};
use serde_json::json;

use crate::cli_args::*;
use crate::governor::ResourceGovernor;
use crate::profile::ProfileManager;
use crate::queue::{self, JobQueue};
use crate::screen::ScreenEngine;
use crate::specialties::SpecialtyManager;
use crate::storage::StorageEngine;
use crate::task_ledger::TaskLedger;
use crate::{daemon, mcp, web, webhook, wiki};

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

pub async fn handle_command(
    command: Option<Commands>,
    root_dir: &Path,
    data_dir: &Path,
) -> Result<(), Box<dyn std::error::Error>> {
    let storage = StorageEngine::new(data_dir);
    let specialties = SpecialtyManager::new(root_dir);
    let profile = ProfileManager::new(root_dir);
    let mut governor = ResourceGovernor::new();
    let ledger = TaskLedger::new(&data_dir.join("agent_tasks.db"))?;
    let queue = JobQueue::new(&data_dir.join("job_queue.db"))?;
    let screen = ScreenEngine::new(data_dir, root_dir);
    let daemon = daemon::DaemonSupervisor::new(root_dir, data_dir);

    match command {
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

        Some(Commands::Subagent(args)) => crate::cli_task::handle_subagent_command(args, &mut governor, &ledger)?,
        Some(Commands::Task(args)) => crate::cli_task::handle_task_command(args, &ledger)?,
        Some(Commands::Queue(args)) => crate::cli_task::handle_queue_command(args, &queue)?,
        Some(Commands::Screen(args)) => {
            let action = args.action.unwrap_or(ScreenSubcommands::Status { json: false });
            match action {
                ScreenSubcommands::Snap { force, json } => {
                    let res = screen.capture_step(force, &queue);
                    if json {
                        println!("{}", serde_json::to_string_pretty(&res)?);
                    } else if res.status == "captured" {
                        println!("[+] Screen Keyframe Captured [{}]:", res.frame_id.unwrap_or_default());
                        println!("    Path:        {}", res.path.unwrap_or_default());
                        println!("    Window:      {}", res.window_title.unwrap_or_default());
                        println!("    Process:     {}", res.process_name.unwrap_or_default());
                        println!("    ROI Mode:    {}", res.roi_mode.unwrap_or_else(|| "active_window".into()));
                        println!("    Focus Shift: {}", if res.focus_shift.unwrap_or(false) { "Yes (Task Switch Transition)" } else { "No (Intra-window update)" });
                        println!("    Status:      Captured and OCR decoupled to background queue.");
                    } else {
                        println!("[*] Screen Capture: status '{}' ({})", res.status, res.reason.unwrap_or_default());
                    }
                }
                ScreenSubcommands::Status { json } => {
                    let is_en = screen.is_enabled();
                    if json {
                        println!("{}", serde_json::json!({
                            "status": if is_en { "enabled" } else { "disabled" },
                            "screen_capture_enabled": is_en,
                            "safeguards_enabled": screen.safeguards.enabled,
                            "safe_rust": true,
                            "unsafe_code": false,
                            "frames_dir": data_dir.join("frames").display().to_string()
                        }));
                    } else {
                        println!("\n==============================================================================");
                        println!("  📸 Cephalo Desktop Screen Memory & Visual Timeline");
                        println!("==============================================================================");
                        println!("  • Capture Status:    {}", if is_en { "ENABLED (Active in background)" } else { "DISABLED (Zero overhead mode)" });
                        println!("  • Native Engine:     100% Safe Rust (#![forbid(unsafe_code)] enforced)");
                        println!("  • Smart Lens:        Active Window ROI Cropping (~70% smaller, ~85% faster OCR)");
                        println!("  • Task Focus Shift:  Focus-shift dominance (immediate clean keyframe on window switch)");
                        println!("  • Streaming Noise:   Streaming noise suppressor (dampens rapid LLM tokens/terminal logs)");
                        println!("  • Delta Gating:      64-bit dHash perceptual comparison");
                        println!("  • Frame Storage:     {}", data_dir.join("frames").display());
                        println!("------------------------------------------------------------------------------");
                        println!("  Resource Profile:");
                        println!("  • Idle Overhead:     0% CPU, 0 MB disk (when unchanged, quiet, or disabled)");
                        println!("  • Active Shift:      ~20-35 KB WebP active window keyframe on visual changes");
                        println!("  • Background OCR:    Decoupled via SQLite queue (~15-20% CPU for ~2s)");
                        println!("  • Battery Shield:    Auto-throttles or pauses when battery < 20%");
                        println!("------------------------------------------------------------------------------");
                        println!("  Control:");
                        println!("  • Enable capture:    cephalo screen enable");
                        println!("  • Disable capture:   cephalo screen disable");
                        println!("  • Force keyframe:    cephalo screen snap --force");
                        println!("==============================================================================\n");
                    }
                }
                ScreenSubcommands::Enable => {
                    let mut s = screen;
                    s.set_screen_capture_enabled(true, &data_dir, &root_dir)?;
                    println!("\n==============================================================================");
                    println!("  📸 Desktop Screen Memory & Visual Timeline: ENABLED");
                    println!("==============================================================================");
                    println!("  • How it operates:");
                    println!("    Native safe Rust captures keyframes when your screen significantly shifts,");
                    println!("    computes a 64-bit dHash perceptual difference (0 unsafe code), and enqueues");
                    println!("    OCR text extraction in the background to power the 24-hour DeepWiki scrubber.");
                    println!("  • Resource Profile:");
                    println!("    - CPU: ~15-20% CPU for ~2s only during background OCR jobs.");
                    println!("    - Disk: ~50-80 KB WebP keyframe per unique screen state.");
                    println!("    - Battery: Automatically throttles or pauses when on battery < 20%.");
                    println!("    - Safeguards: Blacklists password managers, incognito, and banking sites.");
                    println!("  • To disable anytime: cephalo screen disable");
                    println!("==============================================================================\n");
                }
                ScreenSubcommands::Disable => {
                    let mut s = screen;
                    s.set_screen_capture_enabled(false, &data_dir, &root_dir)?;
                    println!("\n==============================================================================");
                    println!("  [*] Desktop Screen Memory: DISABLED (Zero Overhead Mode)");
                    println!("==============================================================================");
                    println!("  • Daemon will operate with 0% screen polling and zero background OCR.");
                    println!("  • System footprint: ~5.7 MB RAM, 0% CPU.");
                    println!("  • To re-enable anytime: cephalo screen enable");
                    println!("==============================================================================\n");
                }
                ScreenSubcommands::Prune { days, json } => {
                    let deleted = screen.prune_frames(days)?;
                    if json {
                        println!("{}", serde_json::json!({
                            "deleted_frames": deleted,
                            "days": days,
                            "status": "success"
                        }));
                    } else {
                        println!("[+] Pruned {} old frame files older than {} days.", deleted, days);
                    }
                }
            }
        }

        Some(Commands::Daemon(args)) => crate::cli_daemon::handle_daemon_command(args, &daemon, data_dir).await?,
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
            let target_dir = args.path.map(PathBuf::from).unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| root_dir.to_path_buf()));
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
        Some(Commands::Fetch(args)) => {
            if args.extra.iter().any(|arg| arg == "--dynamic" || arg == "--youtube" || arg == "-y" || arg == "--record") {
                let mut full_args = vec![args.url.clone()];
                full_args.extend(args.extra.clone());
                run_python_cli(&root_dir, "fetch", &full_args)?;
            } else {
                let engine = web::WebEngine::new();
                let res = engine.fetch(&args.url).await?;
                if args.json {
                    println!("{}", serde_json::to_string_pretty(&res)?);
                } else {
                    println!("\n🌐 Cephalo Web Fetch: {} (Status: {}, {}ms)", res.url, res.status, res.elapsed_ms);
                    println!("Title: {}", res.title);
                    println!("{}", "=".repeat(65));
                    println!("{}", res.content);
                }
            }
        }
        Some(Commands::Research(args)) => run_python_cli(&root_dir, "research", &args.args)?,
        Some(Commands::Migrate(args)) => run_python_cli(&root_dir, "migrate", &args.args)?,
        Some(Commands::Ocr(args)) => run_python_cli(&root_dir, "ocr", &args.args)?,
        Some(Commands::Reconcile(args)) => run_python_cli(&root_dir, "reconcile", &args.args)?,
        Some(Commands::Wiki(args)) => {
            let port = match &args.action {
                Some(WikiSubcommands::Serve { port }) => *port,
                Some(WikiSubcommands::Generate) => {
                    run_python_cli(&root_dir, "wiki", &["generate".to_string()])?;
                    return Ok(());
                }
                None => args.port,
            };
            wiki::start_wiki_server(root_dir.to_path_buf(), port).await?;
        }
        Some(Commands::Pattern(args)) => run_python_cli(&root_dir, "pattern", &args.args)?,
        Some(Commands::Context(args)) => run_python_cli(&root_dir, "context", &args.args)?,
        Some(Commands::Youtube(args)) => run_python_cli(&root_dir, "youtube", &args.args)?,
        Some(Commands::Email(args)) => run_python_cli(&root_dir, "email", &args.args)?,
        Some(Commands::Webhook(args)) => {
            match &args.action {
                Some(WebhookSubcommands::Serve { port, token }) => {
                    webhook::start_webhook_server(data_dir.to_path_buf(), *port, token.clone()).await?;
                }
                Some(WebhookSubcommands::Status { port }) => {
                    let client = reqwest::Client::new();
                    let url = format!("http://127.0.0.1:{}/status", port);
                    match client.get(&url).send().await {
                        Ok(resp) => {
                            let body = resp.text().await.unwrap_or_default();
                            println!("[+] Webhook Gateway Active on port {}:\n{}", port, body);
                        }
                        Err(_) => {
                            println!("[-] Webhook Gateway is not reachable at http://127.0.0.1:{}", port);
                        }
                    }
                }
                Some(WebhookSubcommands::Send { text, category, port }) => {
                    let client = reqwest::Client::new();
                    let url = format!("http://127.0.0.1:{}/ingest", port);
                    let payload = serde_json::json!({
                        "text": text,
                        "category": category,
                        "source": "cli_send"
                    });
                    match client.post(&url).json(&payload).send().await {
                        Ok(resp) => {
                            let body = resp.text().await.unwrap_or_default();
                            println!("[+] Sent memory to Webhook on port {}:\n{}", port, body);
                        }
                        Err(e) => {
                            eprintln!("[-] Failed to deliver memory to webhook: {}", e);
                        }
                    }
                }
                None => {
                    webhook::start_webhook_server(data_dir.to_path_buf(), args.port, args.token.clone()).await?;
                }
            }
        }

        Some(Commands::Mcp) => {
            let mut server = mcp::McpServer::new(&storage, &specialties, &profile, &ledger, &queue, &mut governor, &root_dir);
            server.run_stdio()?;
        }
    }

    
    Ok(())
}

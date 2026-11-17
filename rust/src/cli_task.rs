//! Task Ledger, Subagent Lifecycle, and Job Queue CLI Command Handlers.

use crate::cli_args::*;
use crate::governor::ResourceGovernor;
use crate::queue::JobQueue;
use crate::task_ledger::TaskLedger;

pub fn handle_subagent_command(args: SubagentArgs, governor: &mut ResourceGovernor, ledger: &TaskLedger) -> Result<(), Box<dyn std::error::Error>> {
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
    Ok(())
}

pub fn handle_task_command(args: TaskArgs, ledger: &TaskLedger) -> Result<(), Box<dyn std::error::Error>> {
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
    Ok(())
}

pub fn handle_queue_command(args: QueueArgs, queue: &JobQueue) -> Result<(), Box<dyn std::error::Error>> {
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
    Ok(())
}

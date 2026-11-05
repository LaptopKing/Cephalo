//! Cephalo Native Model Context Protocol (MCP) Server (mcp.rs)
//! ============================================================
//! High-performance JSON-RPC 2.0 stdio server connecting Cephalo directly
//! to frontier AI agent harnesses (Antigravity, Claude Code, Cursor).

use crate::governor::ResourceGovernor;
use crate::profile::ProfileManager;
use crate::queue::JobQueue;
use crate::specialties::SpecialtyManager;
use crate::storage::StorageEngine;
use crate::task_ledger::TaskLedger;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::io::{self, BufRead, Write};
use std::path::{Path, PathBuf};
use std::process::Command;

#[derive(Debug, Serialize, Deserialize)]
struct JsonRpcRequest {
    jsonrpc: String,
    id: Option<Value>,
    method: String,
    params: Option<Value>,
}

#[derive(Debug, Serialize, Deserialize)]
struct JsonRpcResponse {
    jsonrpc: String,
    id: Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<Value>,
}

pub struct McpServer<'a> {
    storage: &'a StorageEngine,
    specialties: &'a SpecialtyManager,
    profile: &'a ProfileManager,
    ledger: &'a TaskLedger,
    queue: &'a JobQueue,
    governor: &'a mut ResourceGovernor,
    root_dir: PathBuf,
}

impl<'a> McpServer<'a> {
    pub fn new(
        storage: &'a StorageEngine,
        specialties: &'a SpecialtyManager,
        profile: &'a ProfileManager,
        ledger: &'a TaskLedger,
        queue: &'a JobQueue,
        governor: &'a mut ResourceGovernor,
        root_dir: &Path,
    ) -> Self {
        Self {
            storage,
            specialties,
            profile,
            ledger,
            queue,
            governor,
            root_dir: root_dir.to_path_buf(),
        }
    }

    pub fn run_stdio(&mut self) -> io::Result<()> {
        let stdin = io::stdin();
        let mut stdout = io::stdout();
        let reader = stdin.lock();

        for line in reader.lines() {
            let line = line?;
            if line.trim().is_empty() {
                continue;
            }

            if let Ok(req) = serde_json::from_str::<JsonRpcRequest>(&line) {
                let resp = self.handle_request(req);
                let out_json = serde_json::to_string(&resp).unwrap();
                writeln!(stdout, "{}", out_json)?;
                stdout.flush()?;
            }
        }
        Ok(())
    }

    fn run_python_helper(&self, args: &[&str]) -> Value {
        let py_bin = self.root_dir.join(".venv/bin/python");
        let cmd_name = if py_bin.exists() {
            py_bin.to_string_lossy().to_string()
        } else {
            "python3".to_string()
        };

        let brain_py = self.root_dir.join("brain.py");
        let mut full_args = vec![brain_py.to_string_lossy().to_string()];
        for a in args {
            full_args.push(a.to_string());
        }

        let output = Command::new(cmd_name).args(&full_args).output();

        match output {
            Ok(out) => {
                let stdout = String::from_utf8_lossy(&out.stdout).trim().to_string();
                if let Ok(val) = serde_json::from_str::<Value>(&stdout) {
                    val
                } else {
                    json!({
                        "status": if out.status.success() { "success" } else { "error" },
                        "output": stdout,
                        "stderr": String::from_utf8_lossy(&out.stderr).trim().to_string()
                    })
                }
            }
            Err(e) => json!({ "status": "error", "message": e.to_string() }),
        }
    }

    fn handle_request(&mut self, req: JsonRpcRequest) -> JsonRpcResponse {
        let id = req.id.unwrap_or(json!(null));

        match req.method.as_str() {
            "initialize" => JsonRpcResponse {
                jsonrpc: "2.0".to_string(),
                id,
                result: Some(json!({
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "cephalo-native-rust",
                        "version": "0.2.0"
                    },
                    "capabilities": {
                        "tools": {}
                    }
                })),
                error: None,
            },

            "notifications/initialized" => JsonRpcResponse {
                jsonrpc: "2.0".to_string(),
                id,
                result: Some(json!({})),
                error: None,
            },

            "tools/list" => JsonRpcResponse {
                jsonrpc: "2.0".to_string(),
                id,
                result: Some(json!({
                    "tools": [
                        {
                            "name": "cephalo_search",
                            "description": "Searches Cephalo local memory and project specialties using hybrid retrieval.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": { "type": "string", "description": "Search query terms" },
                                    "category": { "type": "string", "description": "Optional category filter" },
                                    "limit": { "type": "integer", "description": "Max results to return (default 5)" }
                                },
                                "required": ["query"]
                            }
                        },
                        {
                            "name": "cephalo_record",
                            "description": "Records user preferences, decisions, and constraints into Cephalo with automatic secret sanitization.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "content": { "type": "string", "description": "Fact or decision to remember" },
                                    "category": { "type": "string", "description": "Category (e.g. preferences, architecture, hardware)" },
                                    "source": { "type": "string", "description": "Source attribution (default 'agent')" }
                                },
                                "required": ["content"]
                            }
                        },
                        {
                            "name": "cephalo_get_profile",
                            "description": "Reads user profile blueprint or extracts targeted sections.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "section": { "type": "string", "description": "Optional section name to extract (e.g. 'hardware')" }
                                }
                            }
                        },
                        {
                            "name": "cephalo_list_specialties",
                            "description": "Lists all available domain specialties across projects.",
                            "inputSchema": { "type": "object", "properties": {} }
                        },
                        {
                            "name": "cephalo_get_specialty",
                            "description": "Retrieves the full specification for a domain specialty module.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "slug": { "type": "string", "description": "Specialty slug name" },
                                    "project": { "type": "string", "description": "Project namespace (default 'global')" }
                                },
                                "required": ["slug"]
                            }
                        },
                        {
                            "name": "cephalo_auto_create_specialty",
                            "description": "Autonomously synthesizes and registers a new specialty module for any novel technology or framework.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "topic": { "type": "string", "description": "Technology or methodology name" },
                                    "project": { "type": "string", "description": "Target project namespace (default 'global')" }
                                },
                                "required": ["topic"]
                            }
                        },
                        {
                            "name": "cephalo_continuous_learn",
                            "description": "Triggers an autonomous continuous learning cycle across all project workspaces.",
                            "inputSchema": { "type": "object", "properties": {} }
                        },
                        {
                            "name": "cephalo_learning_status",
                            "description": "Queries current continuous learning state, tracked projects, hardware governor metrics, and queue status.",
                            "inputSchema": { "type": "object", "properties": {} }
                        },
                        {
                            "name": "cephalo_deep_research",
                            "description": "Executes autonomous deep research on any topic using first principles, industry standards, and top GitHub repos.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "topic": { "type": "string", "description": "Technology, domain, or methodology to research" },
                                    "project": { "type": "string", "description": "Target project namespace (default 'global')" },
                                    "create_specialty": { "type": "boolean", "description": "If true, registers as a Cephalo specialty" }
                                },
                                "required": ["topic"]
                            }
                        },
                        {
                            "name": "cephalo_web_search",
                            "description": "Performs Google-style web search with an AI Quick Summary, organic web results, and social/discussion blocks.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": { "type": "string", "description": "Natural language search query" },
                                    "limit": { "type": "integer", "description": "Max organic search results (default 5)" }
                                },
                                "required": ["query"]
                            }
                        },
                        {
                            "name": "cephalo_web_fetch",
                            "description": "Extracts clean readable markdown/text from a webpage URL.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "url": { "type": "string", "description": "Target webpage URL to crawl" },
                                    "max_chars": { "type": "integer", "description": "Maximum characters to extract (default 15000)" }
                                },
                                "required": ["url"]
                            }
                        },
                        {
                            "name": "cephalo_run_sandboxed",
                            "description": "Safely executes code or scripts in an isolated sandbox with resource governor limits.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "code": { "type": "string", "description": "Code to execute" },
                                    "language": { "type": "string", "description": "Execution language runtime (python, bash, javascript)" }
                                },
                                "required": ["code"]
                            }
                        },
                        {
                            "name": "cephalo_task_checkpoint",
                            "description": "Checkpoints subagent state in the task ledger for crash resilience.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "task_id": { "type": "string" },
                                    "step_index": { "type": "integer" },
                                    "state": { "type": "object" },
                                    "pause_reason": { "type": "string" }
                                },
                                "required": ["task_id", "step_index", "state"]
                            }
                        },
                        {
                            "name": "cephalo_task_resume",
                            "description": "Resumes an interrupted or rate-limited subagent task from its last checkpoint.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "task_id": { "type": "string" }
                                },
                                "required": ["task_id"]
                            }
                        },
                        {
                            "name": "cephalo_task_list",
                            "description": "Lists subagent tasks, current step status, paused reasons, and token usage.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "limit": { "type": "integer", "description": "Max tasks to list (default 20)" }
                                }
                            }
                        },
                        {
                            "name": "cephalo_migrate",
                            "description": "Universal migration engine for Cephalo and AI agent harnesses (export, restore, inspect, list).",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "action": { "type": "string", "description": "export, restore, inspect, or list (default: export)" },
                                    "scope": { "type": "string", "description": "settings or all (default: settings)" }
                                }
                            }
                        }
                    ]
                })),
                error: None,
            },

            "tools/call" => {
                let params = req.params.unwrap_or_else(|| json!({}));
                let tool_name = params.get("name").and_then(|v| v.as_str()).unwrap_or("");
                let default_args = json!({});
                let args = params.get("arguments").unwrap_or(&default_args);

                let tool_result = match tool_name {
                    "cephalo_search" => {
                        let q = args.get("query").and_then(|v| v.as_str()).unwrap_or("");
                        let cat = args.get("category").and_then(|v| v.as_str());
                        let limit = args.get("limit").and_then(|v| v.as_u64()).unwrap_or(5) as usize;
                        let res = self.storage.search(q, cat, false, limit);
                        json!({ "query": q, "results": res, "count": res.len() })
                    }
                    "cephalo_record" => {
                        let content = args.get("content").and_then(|v| v.as_str()).unwrap_or("");
                        let cat = args.get("category").and_then(|v| v.as_str()).unwrap_or("general");
                        let src = args.get("source").and_then(|v| v.as_str()).unwrap_or("agent");
                        match self.storage.record_prompt(content, cat, src, None) {
                            Ok(rec) => json!({ "status": "recorded", "record": rec }),
                            Err(e) => json!({ "status": "error", "message": e.to_string() }),
                        }
                    }
                    "cephalo_get_profile" => {
                        if let Some(sec) = args.get("section").and_then(|v| v.as_str()) {
                            match self.profile.get_section(sec) {
                                Some(txt) => json!({ "section": sec, "content": txt }),
                                None => json!({ "section": sec, "content": "Section not found." }),
                            }
                        } else {
                            match self.profile.read_full() {
                                Ok(full) => json!({ "profile": full }),
                                Err(e) => json!({ "error": e.to_string() }),
                            }
                        }
                    }
                    "cephalo_list_specialties" => {
                        let list = self.specialties.list_specialties();
                        json!({ "specialties": list, "count": list.len() })
                    }
                    "cephalo_get_specialty" => {
                        let slug = args.get("slug").and_then(|v| v.as_str()).unwrap_or("");
                        let proj = args.get("project").and_then(|v| v.as_str()).unwrap_or("global");
                        match self.specialties.get_specialty(proj, slug) {
                            Some(spec) => json!({ "specialty": spec }),
                            None => json!({ "error": format!("Specialty '{}' not found in '{}'", slug, proj) }),
                        }
                    }
                    "cephalo_auto_create_specialty" => {
                        let topic = args.get("topic").and_then(|v| v.as_str()).unwrap_or("");
                        let proj = args.get("project").and_then(|v| v.as_str()).unwrap_or("global");
                        let slug = topic.to_lowercase().replace(' ', "-");
                        let title = topic.to_string();
                        let initial_content = format!(
                            "# {}\n\n## Overview\nAutonomous specialty module for {}.\n\n## Core Principles\n- Verified engineering discipline\n- Anti-AI-slop craftsmanship\n",
                            title, topic
                        );
                        match self.specialties.create_specialty(proj, &slug, &title, &initial_content) {
                            Ok(p) => json!({ "status": "success", "action": "created", "path": p.to_string_lossy(), "topic": topic }),
                            Err(e) => json!({ "status": "error", "message": e.to_string() }),
                        }
                    }
                    "cephalo_continuous_learn" => {
                        let _ = self.queue.enqueue("continuous_learn", Some(json!({"source": "mcp"})), 3, true);
                        json!({
                            "status": "success",
                            "message": "Continuous learning cycle scheduled in Cephalo work queue."
                        })
                    }
                    "cephalo_learning_status" => {
                        let metrics = self.governor.inspect_resources();
                        let q_status = self.queue.get_status().unwrap_or(crate::queue::QueueStatus {
                            pending: 0,
                            running: 0,
                            completed: 0,
                            failed: 0,
                            current_running_job: None,
                        });
                        json!({
                            "status": "active",
                            "governor_mode": metrics.mode.as_str(),
                            "safe_concurrency": metrics.safe_concurrency,
                            "on_battery": metrics.on_battery,
                            "battery_percent": metrics.battery_percent,
                            "cpu_percent": metrics.cpu_percent,
                            "queue": q_status
                        })
                    }
                    "cephalo_deep_research" => {
                        let topic = args.get("topic").and_then(|v| v.as_str()).unwrap_or("");
                        let proj = args.get("project").and_then(|v| v.as_str()).unwrap_or("global");
                        self.run_python_helper(&["research", topic, "--project", proj, "--json"])
                    }
                    "cephalo_web_search" => {
                        let q = args.get("query").and_then(|v| v.as_str()).unwrap_or("");
                        self.run_python_helper(&["web", q, "--json"])
                    }
                    "cephalo_web_fetch" => {
                        let url = args.get("url").and_then(|v| v.as_str()).unwrap_or("");
                        self.run_python_helper(&["fetch", url, "--json"])
                    }
                    "cephalo_run_sandboxed" => {
                        let code = args.get("code").and_then(|v| v.as_str()).unwrap_or("");
                        let lang = args.get("language").and_then(|v| v.as_str()).unwrap_or("python");
                        let allow_net = args.get("allow_network").and_then(|v| v.as_bool()).unwrap_or(false);
                        let timeout = args.get("timeout_seconds").and_then(|v| v.as_u64()).unwrap_or(30);

                        let py_bin = self.root_dir.join(".venv/bin/python");
                        let cmd_name = if py_bin.exists() {
                            py_bin.to_string_lossy().to_string()
                        } else {
                            "python3".to_string()
                        };

                        let runner_script = "import sys, json\nfrom cephalo.services.sandboxed_runner import SandboxedRunner\nr = SandboxedRunner()\na = json.loads(sys.argv[1])\nres = r.run_code(a.get('code',''), a.get('language','python'), a.get('allow_network',False), a.get('timeout_seconds',30))\nprint(json.dumps(res))\n";
                        let args_json = serde_json::to_string(&json!({
                            "code": code,
                            "language": lang,
                            "allow_network": allow_net,
                            "timeout_seconds": timeout,
                        })).unwrap_or_default();

                        let output = Command::new(cmd_name)
                            .args(["-c", runner_script, &args_json])
                            .output();

                        match output {
                            Ok(out) => {
                                let stdout = String::from_utf8_lossy(&out.stdout).trim().to_string();
                                if let Ok(val) = serde_json::from_str::<Value>(&stdout) {
                                    val
                                } else {
                                    json!({
                                        "status": if out.status.success() { "success" } else { "failed" },
                                        "stdout": stdout,
                                        "stderr": String::from_utf8_lossy(&out.stderr).trim().to_string(),
                                        "exit_code": out.status.code()
                                    })
                                }
                            }
                            Err(e) => json!({ "status": "error", "message": e.to_string() }),
                        }
                    }
                    "cephalo_task_checkpoint" => {
                        let tid = args.get("task_id").and_then(|v| v.as_str()).unwrap_or("");
                        let step = args.get("step_index").and_then(|v| v.as_i64()).unwrap_or(0) as i32;
                        let state = args.get("state").cloned().unwrap_or(json!({}));
                        let pause = args.get("pause_reason").and_then(|v| v.as_str());
                        match self.ledger.checkpoint(tid, step, state, None, pause, None) {
                            Ok(task) => json!({ "status": "checkpointed", "task": task }),
                            Err(e) => json!({ "status": "error", "message": e.to_string() }),
                        }
                    }
                    "cephalo_task_resume" => {
                        let tid = args.get("task_id").and_then(|v| v.as_str()).unwrap_or("");
                        match self.ledger.build_resume_brief(tid) {
                            Ok(Some(brief)) => json!({ "status": "resumed", "brief": brief }),
                            _ => json!({ "status": "not_found", "task_id": tid }),
                        }
                    }
                    "cephalo_task_list" => {
                        let limit = args.get("limit").and_then(|v| v.as_u64()).unwrap_or(20) as usize;
                        match self.ledger.list_tasks(limit) {
                            Ok(tasks) => json!({ "status": "success", "tasks": tasks, "count": tasks.len() }),
                            Err(e) => json!({ "status": "error", "message": e.to_string() }),
                        }
                    }
                    "cephalo_migrate" => {
                        let act = args.get("action").and_then(|v| v.as_str()).unwrap_or("export");
                        let scp = args.get("scope").and_then(|v| v.as_str()).unwrap_or("settings");
                        self.run_python_helper(&["migrate", act, "--scope", scp, "--json"])
                    }
                    _ => json!({ "error": format!("Unknown tool: {}", tool_name) }),
                };

                JsonRpcResponse {
                    jsonrpc: "2.0".to_string(),
                    id,
                    result: Some(json!({
                        "content": [{
                            "type": "text",
                            "text": tool_result.to_string()
                        }]
                    })),
                    error: None,
                }
            }

            _ => JsonRpcResponse {
                jsonrpc: "2.0".to_string(),
                id,
                result: None,
                error: Some(json!({
                    "code": -32601,
                    "message": format!("Method not found: {}", req.method)
                })),
            },
        }
    }
}

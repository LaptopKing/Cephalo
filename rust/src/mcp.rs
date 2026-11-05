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
}

impl<'a> McpServer<'a> {
    pub fn new(
        storage: &'a StorageEngine,
        specialties: &'a SpecialtyManager,
        profile: &'a ProfileManager,
        ledger: &'a TaskLedger,
        queue: &'a JobQueue,
        governor: &'a mut ResourceGovernor,
    ) -> Self {
        Self {
            storage,
            specialties,
            profile,
            ledger,
            queue,
            governor,
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

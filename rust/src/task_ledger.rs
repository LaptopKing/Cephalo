//! Cephalo Multi-Agent Coordination & Checkpoint Ledger (task_ledger.rs)
//! ======================================================================
//! SQLite-backed state ledger enabling zero-loss task resumption,
//! subagent coordination, and rate-limit recovery.

use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentTask {
    pub task_id: String,
    pub conversation_id: String,
    pub parent_task_id: Option<String>,
    pub assignee_agent: String,
    pub user_goal: String,
    pub step_index: i32,
    pub total_steps: i32,
    pub status: String,
    pub dependencies: Value,
    pub checkpoint_state: Value,
    pub token_usage: Value,
    pub pause_reason: Option<String>,
    pub rate_limit_reset_at: Option<String>,
    pub result_summary: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

pub struct TaskLedger {
    db_path: PathBuf,
}

impl TaskLedger {
    pub fn new(db_path: &Path) -> Result<Self, rusqlite::Error> {
        if let Some(parent) = db_path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        let ledger = Self {
            db_path: db_path.to_path_buf(),
        };
        ledger.init_db()?;
        Ok(ledger)
    }

    fn get_conn(&self) -> Result<Connection, rusqlite::Error> {
        let conn = Connection::open(&self.db_path)?;
        conn.execute_batch(
            "PRAGMA journal_mode = WAL;
             PRAGMA synchronous = NORMAL;
             PRAGMA busy_timeout = 30000;",
        )?;
        Ok(conn)
    }

    fn init_db(&self) -> Result<(), rusqlite::Error> {
        let conn = self.get_conn()?;
        conn.execute(
            "CREATE TABLE IF NOT EXISTS agent_task_ledger (
                task_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                parent_task_id TEXT,
                assignee_agent TEXT NOT NULL,
                user_goal TEXT NOT NULL,
                step_index INTEGER DEFAULT 0,
                total_steps INTEGER DEFAULT 1,
                status TEXT CHECK(status IN ('pending', 'running', 'rate_limited_paused', 'completed', 'failed')),
                dependencies JSON,
                checkpoint_state JSON,
                token_usage JSON,
                pause_reason TEXT,
                rate_limit_reset_at TEXT,
                result_summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )",
            [],
        )?;
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_task_status ON agent_task_ledger (status)",
            [],
        )?;
        Ok(())
    }

    pub fn register_task(
        &self,
        task_id: &str,
        conversation_id: &str,
        parent_task_id: Option<&str>,
        assignee_agent: &str,
        user_goal: &str,
        total_steps: i32,
        initial_state: Option<Value>,
    ) -> Result<AgentTask, rusqlite::Error> {
        let conn = self.get_conn()?;
        let now = chrono::Utc::now().to_rfc3339();
        let state_val = initial_state.unwrap_or_else(|| serde_json::json!({}));
        let empty_tokens = serde_json::json!({"input_tokens": 0, "output_tokens": 0});

        conn.execute(
            "INSERT INTO agent_task_ledger (
                task_id, conversation_id, parent_task_id, assignee_agent,
                user_goal, step_index, total_steps, status, dependencies,
                checkpoint_state, token_usage, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 0, ?, 'running', '[]', ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                step_index = 0,
                status = 'running',
                updated_at = excluded.updated_at",
            params![
                task_id,
                conversation_id,
                parent_task_id,
                assignee_agent,
                user_goal,
                total_steps,
                state_val.to_string(),
                empty_tokens.to_string(),
                now,
                now,
            ],
        )?;

        self.get_task(task_id)?
            .ok_or(rusqlite::Error::QueryReturnedNoRows)
    }

    pub fn checkpoint(
        &self,
        task_id: &str,
        step_index: i32,
        checkpoint_state: Value,
        token_usage: Option<Value>,
        pause_reason: Option<&str>,
        reset_seconds: Option<i64>,
    ) -> Result<AgentTask, rusqlite::Error> {
        let conn = self.get_conn()?;
        let now = chrono::Utc::now().to_rfc3339();

        let mut status = "running";
        let mut reset_at = None;

        if let Some(reason) = pause_reason {
            if reason.to_lowercase().contains("rate_limit") || reason.contains("429") {
                status = "rate_limited_paused";
                if let Some(sec) = reset_seconds {
                    let r_time = chrono::Utc::now() + chrono::Duration::seconds(sec);
                    reset_at = Some(r_time.to_rfc3339());
                }
            }
        }

        conn.execute(
            "UPDATE agent_task_ledger
             SET step_index = ?,
                 checkpoint_state = ?,
                 token_usage = COALESCE(?, token_usage),
                 status = ?,
                 pause_reason = ?,
                 rate_limit_reset_at = ?,
                 updated_at = ?
             WHERE task_id = ?",
            params![
                step_index,
                checkpoint_state.to_string(),
                token_usage.map(|t| t.to_string()),
                status,
                pause_reason,
                reset_at,
                now,
                task_id,
            ],
        )?;

        self.get_task(task_id)?
            .ok_or(rusqlite::Error::QueryReturnedNoRows)
    }

    pub fn complete_task(
        &self,
        task_id: &str,
        result_summary: &str,
        token_usage: Option<Value>,
    ) -> Result<AgentTask, rusqlite::Error> {
        let conn = self.get_conn()?;
        let now = chrono::Utc::now().to_rfc3339();
        conn.execute(
            "UPDATE agent_task_ledger
             SET status = 'completed',
                 result_summary = ?,
                 token_usage = COALESCE(?, token_usage),
                 updated_at = ?
             WHERE task_id = ?",
            params![result_summary, token_usage.map(|t| t.to_string()), now, task_id],
        )?;

        self.get_task(task_id)?
            .ok_or(rusqlite::Error::QueryReturnedNoRows)
    }

    pub fn get_task(&self, task_id: &str) -> Result<Option<AgentTask>, rusqlite::Error> {
        let conn = self.get_conn()?;
        let mut stmt = conn.prepare(
            "SELECT task_id, conversation_id, parent_task_id, assignee_agent,
                    user_goal, step_index, total_steps, status, dependencies,
                    checkpoint_state, token_usage, pause_reason, rate_limit_reset_at,
                    result_summary, created_at, updated_at
             FROM agent_task_ledger WHERE task_id = ?",
        )?;

        let row = stmt
            .query_row(params![task_id], |r| {
                let dep_str: String = r.get(8)?;
                let state_str: String = r.get(9)?;
                let tok_str: Option<String> = r.get(10)?;
                Ok(AgentTask {
                    task_id: r.get(0)?,
                    conversation_id: r.get(1)?,
                    parent_task_id: r.get(2)?,
                    assignee_agent: r.get(3)?,
                    user_goal: r.get(4)?,
                    step_index: r.get(5)?,
                    total_steps: r.get(6)?,
                    status: r.get(7)?,
                    dependencies: serde_json::from_str(&dep_str).unwrap_or(serde_json::json!([])),
                    checkpoint_state: serde_json::from_str(&state_str).unwrap_or(serde_json::json!({})),
                    token_usage: tok_str
                        .and_then(|s| serde_json::from_str(&s).ok())
                        .unwrap_or(serde_json::json!({})),
                    pause_reason: r.get(11)?,
                    rate_limit_reset_at: r.get(12)?,
                    result_summary: r.get(13)?,
                    created_at: r.get(14)?,
                    updated_at: r.get(15)?,
                })
            })
            .optional()?;

        Ok(row)
    }

    pub fn list_tasks(&self, limit: usize) -> Result<Vec<AgentTask>, rusqlite::Error> {
        let conn = self.get_conn()?;
        let mut stmt = conn.prepare(
            "SELECT task_id, conversation_id, parent_task_id, assignee_agent,
                    user_goal, step_index, total_steps, status, dependencies,
                    checkpoint_state, token_usage, pause_reason, rate_limit_reset_at,
                    result_summary, created_at, updated_at
             FROM agent_task_ledger
             ORDER BY updated_at DESC LIMIT ?",
        )?;

        let rows = stmt.query_map([limit as i64], |r| {
            let dep_str: String = r.get(8)?;
            let state_str: String = r.get(9)?;
            let tok_str: Option<String> = r.get(10)?;
            Ok(AgentTask {
                task_id: r.get(0)?,
                conversation_id: r.get(1)?,
                parent_task_id: r.get(2)?,
                assignee_agent: r.get(3)?,
                user_goal: r.get(4)?,
                step_index: r.get(5)?,
                total_steps: r.get(6)?,
                status: r.get(7)?,
                dependencies: serde_json::from_str(&dep_str).unwrap_or(serde_json::json!([])),
                checkpoint_state: serde_json::from_str(&state_str).unwrap_or(serde_json::json!({})),
                token_usage: tok_str
                    .and_then(|s| serde_json::from_str(&s).ok())
                    .unwrap_or(serde_json::json!({})),
                pause_reason: r.get(11)?,
                rate_limit_reset_at: r.get(12)?,
                result_summary: r.get(13)?,
                created_at: r.get(14)?,
                updated_at: r.get(15)?,
            })
        })?;

        let mut res = Vec::new();
        for r in rows.flatten() {
            res.push(r);
        }
        Ok(res)
    }

    pub fn get_interrupted_tasks(&self) -> Result<Vec<AgentTask>, rusqlite::Error> {
        let conn = self.get_conn()?;
        let mut stmt = conn.prepare(
            "SELECT task_id, conversation_id, parent_task_id, assignee_agent,
                    user_goal, step_index, total_steps, status, dependencies,
                    checkpoint_state, token_usage, pause_reason, rate_limit_reset_at,
                    result_summary, created_at, updated_at
             FROM agent_task_ledger
             WHERE status = 'running' OR status = 'rate_limited_paused'
             ORDER BY updated_at DESC",
        )?;

        let rows = stmt.query_map([], |r| {
            let dep_str: String = r.get(8)?;
            let state_str: String = r.get(9)?;
            let tok_str: Option<String> = r.get(10)?;
            Ok(AgentTask {
                task_id: r.get(0)?,
                conversation_id: r.get(1)?,
                parent_task_id: r.get(2)?,
                assignee_agent: r.get(3)?,
                user_goal: r.get(4)?,
                step_index: r.get(5)?,
                total_steps: r.get(6)?,
                status: r.get(7)?,
                dependencies: serde_json::from_str(&dep_str).unwrap_or(serde_json::json!([])),
                checkpoint_state: serde_json::from_str(&state_str).unwrap_or(serde_json::json!({})),
                token_usage: tok_str
                    .and_then(|s| serde_json::from_str(&s).ok())
                    .unwrap_or(serde_json::json!({})),
                pause_reason: r.get(11)?,
                rate_limit_reset_at: r.get(12)?,
                result_summary: r.get(13)?,
                created_at: r.get(14)?,
                updated_at: r.get(15)?,
            })
        })?;

        let mut res = Vec::new();
        for r in rows.flatten() {
            res.push(r);
        }
        Ok(res)
    }

    pub fn build_resume_brief(&self, task_id: &str) -> Result<Option<String>, rusqlite::Error> {
        if let Some(task) = self.get_task(task_id)? {
            let brief = format!(
                "🔄 Task Checkpoint Brief for '{}'\n\
                 - User Goal: {}\n\
                 - Assignee: {}\n\
                 - Status: {}\n\
                 - Progress: Step {} of {}\n\
                 - Checkpoint State:\n{}\n\
                 - Instruction: Continue from step {} without restarting completed work.",
                task.task_id,
                task.user_goal,
                task.assignee_agent,
                task.status,
                task.step_index,
                task.total_steps,
                serde_json::to_string_pretty(&task.checkpoint_state).unwrap_or_default(),
                task.step_index + 1
            );
            Ok(Some(brief))
        } else {
            Ok(None)
        }
    }
}

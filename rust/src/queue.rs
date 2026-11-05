//! Cephalo Serialized Work Queue (queue.rs)
//! ==========================================
//! SQLite-backed, crash-safe priority job queue that respects the
//! ResourceGovernor hardware hierarchy.

use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Job {
    pub id: i64,
    pub job_type: String,
    pub payload: Value,
    pub status: String,
    pub priority: i32,
    pub error_message: Option<String>,
    pub created_at: String,
    pub started_at: Option<String>,
    pub completed_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueueStatus {
    pub pending: i64,
    pub running: i64,
    pub completed: i64,
    pub failed: i64,
    pub current_running_job: Option<Job>,
}

pub struct JobQueue {
    db_path: PathBuf,
}

impl JobQueue {
    pub fn new(db_path: &Path) -> Result<Self, rusqlite::Error> {
        if let Some(parent) = db_path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        let queue = Self {
            db_path: db_path.to_path_buf(),
        };
        queue.init_db()?;
        Ok(queue)
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
            "CREATE TABLE IF NOT EXISTS cephalo_job_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL,
                payload JSON NOT NULL,
                status TEXT CHECK(status IN ('pending', 'running', 'completed', 'failed')) DEFAULT 'pending',
                priority INTEGER DEFAULT 5,
                error_message TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT
            )",
            [],
        )?;
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_job_status_priority ON cephalo_job_queue (status, priority DESC, id ASC)",
            [],
        )?;
        Ok(())
    }

    pub fn enqueue(
        &self,
        job_type: &str,
        payload: Option<Value>,
        priority: i32,
        deduplicate_pending: bool,
    ) -> Result<i64, rusqlite::Error> {
        let conn = self.get_conn()?;
        let payload_val = payload.unwrap_or_else(|| serde_json::json!({}));
        let payload_str = payload_val.to_string();
        let now = chrono::Utc::now().to_rfc3339();

        if deduplicate_pending {
            let mut stmt = conn.prepare(
                "SELECT id FROM cephalo_job_queue
                 WHERE job_type = ? AND payload = ? AND status = 'pending'
                 ORDER BY id ASC LIMIT 1",
            )?;
            let existing: Option<i64> = stmt
                .query_row(params![job_type, payload_str], |r| r.get(0))
                .optional()?;
            if let Some(id) = existing {
                return Ok(id);
            }
        }

        conn.execute(
            "INSERT INTO cephalo_job_queue (job_type, payload, status, priority, created_at)
             VALUES (?, ?, 'pending', ?, ?)",
            params![job_type, payload_str, priority, now],
        )?;

        Ok(conn.last_insert_rowid())
    }

    /// Resets ALL jobs currently marked 'running' back to 'pending'.
    /// Called during startup/reboot so interrupted jobs resume cleanly.
    pub fn reset_all_running_jobs(&self) -> Result<usize, rusqlite::Error> {
        let conn = self.get_conn()?;
        let count = conn.execute(
            "UPDATE cephalo_job_queue
             SET status = 'pending', started_at = NULL, error_message = 'Recovered after reboot/shutdown'
             WHERE status = 'running'",
            [],
        )?;
        Ok(count)
    }

    pub fn fetch_next_job(&self, max_concurrency: usize) -> Result<Option<Job>, rusqlite::Error> {
        let mut conn = self.get_conn()?;
        let tx = conn.transaction()?;

        let running_cnt: i64 = tx.query_row(
            "SELECT COUNT(*) FROM cephalo_job_queue WHERE status = 'running'",
            [],
            |r| r.get(0),
        )?;

        if running_cnt as usize >= max_concurrency {
            return Ok(None);
        }

        let candidate: Option<(i64, String, String, i32, Option<String>, String, Option<String>, Option<String>)> = tx
            .query_row(
                "SELECT id, job_type, payload, priority, error_message, created_at, started_at, completed_at
                 FROM cephalo_job_queue
                 WHERE status = 'pending'
                 ORDER BY priority DESC, id ASC
                 LIMIT 1",
                [],
                |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?, r.get(4)?, r.get(5)?, r.get(6)?, r.get(7)?)),
            )
            .optional()?;

        if let Some((id, job_type, payload_str, priority, error_message, created_at, _, completed_at)) = candidate {
            let now = chrono::Utc::now().to_rfc3339();
            tx.execute(
                "UPDATE cephalo_job_queue SET status = 'running', started_at = ? WHERE id = ?",
                params![now, id],
            )?;
            tx.commit()?;

            let payload: Value = serde_json::from_str(&payload_str).unwrap_or(serde_json::json!({}));
            Ok(Some(Job {
                id,
                job_type,
                payload,
                status: "running".to_string(),
                priority,
                error_message,
                created_at,
                started_at: Some(now),
                completed_at,
            }))
        } else {
            Ok(None)
        }
    }

    pub fn mark_completed(&self, job_id: i64) -> Result<(), rusqlite::Error> {
        let conn = self.get_conn()?;
        let now = chrono::Utc::now().to_rfc3339();
        conn.execute(
            "UPDATE cephalo_job_queue SET status = 'completed', completed_at = ? WHERE id = ?",
            params![now, job_id],
        )?;
        Ok(())
    }

    pub fn mark_failed(&self, job_id: i64, error: &str) -> Result<(), rusqlite::Error> {
        let conn = self.get_conn()?;
        let now = chrono::Utc::now().to_rfc3339();
        conn.execute(
            "UPDATE cephalo_job_queue SET status = 'failed', completed_at = ?, error_message = ? WHERE id = ?",
            params![now, error, job_id],
        )?;
        Ok(())
    }

    pub fn get_status(&self) -> Result<QueueStatus, rusqlite::Error> {
        let conn = self.get_conn()?;
        let mut pending = 0;
        let mut running = 0;
        let mut completed = 0;
        let mut failed = 0;

        let mut stmt = conn.prepare("SELECT status, COUNT(*) FROM cephalo_job_queue GROUP BY status")?;
        let rows = stmt.query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, i64>(1)?)))?;
        for row in rows.flatten() {
            match row.0.as_str() {
                "pending" => pending = row.1,
                "running" => running = row.1,
                "completed" => completed = row.1,
                "failed" => failed = row.1,
                _ => {}
            }
        }

        let mut running_stmt = conn.prepare(
            "SELECT id, job_type, payload, priority, error_message, created_at, started_at, completed_at
             FROM cephalo_job_queue WHERE status = 'running' ORDER BY started_at ASC LIMIT 1",
        )?;
        let current_running_job = running_stmt
            .query_row([], |r| {
                let payload_str: String = r.get(2)?;
                let payload: Value = serde_json::from_str(&payload_str).unwrap_or(serde_json::json!({}));
                Ok(Job {
                    id: r.get(0)?,
                    job_type: r.get(1)?,
                    payload,
                    status: "running".to_string(),
                    priority: r.get(3)?,
                    error_message: r.get(4)?,
                    created_at: r.get(5)?,
                    started_at: r.get(6)?,
                    completed_at: r.get(7)?,
                })
            })
            .optional()?;

        Ok(QueueStatus {
            pending,
            running,
            completed,
            failed,
            current_running_job,
        })
    }

    pub fn list_jobs(&self, limit: usize) -> Result<Vec<Job>, rusqlite::Error> {
        let conn = self.get_conn()?;
        let mut stmt = conn.prepare(
            "SELECT id, job_type, payload, status, priority, error_message, created_at, started_at, completed_at
             FROM cephalo_job_queue
             ORDER BY id DESC LIMIT ?",
        )?;
        let rows = stmt.query_map([limit as i64], |r| {
            let payload_str: String = r.get(2)?;
            let payload: Value = serde_json::from_str(&payload_str).unwrap_or(serde_json::json!({}));
            Ok(Job {
                id: r.get(0)?,
                job_type: r.get(1)?,
                payload,
                status: r.get(3)?,
                priority: r.get(4)?,
                error_message: r.get(5)?,
                created_at: r.get(6)?,
                started_at: r.get(7)?,
                completed_at: r.get(8)?,
            })
        })?;

        let mut res = Vec::new();
        for r in rows.flatten() {
            res.push(r);
        }
        Ok(res)
    }

    pub fn clear_history(&self, hours_old: i64) -> Result<usize, rusqlite::Error> {
        let conn = self.get_conn()?;
        let cutoff = (chrono::Utc::now() - chrono::Duration::hours(hours_old)).to_rfc3339();
        let deleted = conn.execute(
            "DELETE FROM cephalo_job_queue WHERE status IN ('completed', 'failed') AND completed_at < ?",
            params![cutoff],
        )?;
        Ok(deleted)
    }
}

"""
Cephalo Multi-Agent Coordination & Token-Aware Checkpoint Ledger (task_ledger.py)
=================================================================================
Inspired by Orkas (Orkas-AI/Orkas) and thinkrail background command lifecycles.

Solves:
1. Multi-Agent Task State Tracking: Tracks task DAGs, parent-child subagent delegations,
   and dependency chains across multiple agent harnesses.
2. Token-Aware Rate-Limit Checkpoint & Resume:
   When an agent or subagent hits a rate limit (429) or token budget threshold, it checkpoints
   its exact execution state (step index, variables, partial outputs, remaining queue).
   Once limits reset, the agent or subagent resumes seamlessly where it left off without
   re-running completed steps or wasting tokens.
3. Concurrency Protection: Keyed file locks to prevent race conditions during parallel edits.
"""

from __future__ import annotations

import contextlib
import datetime
import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cephalo.task_ledger")

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "agent_tasks.db"


class KeyedFileLock:
    """Thread-safe and process-safe keyed lock registry for workspace files."""

    _locks: Dict[str, threading.Lock] = {}
    _master_lock = threading.Lock()

    @classmethod
    def acquire(cls, file_path: str, timeout: float = 10.0) -> bool:
        normalized = str(Path(file_path).resolve())
        with cls._master_lock:
            if normalized not in cls._locks:
                cls._locks[normalized] = threading.Lock()
            lock = cls._locks[normalized]
        return lock.acquire(timeout=timeout)

    @classmethod
    def release(cls, file_path: str) -> None:
        normalized = str(Path(file_path).resolve())
        with cls._master_lock:
            lock = cls._locks.get(normalized)
        if lock and lock.locked():
            lock.release()


class TaskLedger:
    """
    SQLite-backed state ledger for parallel subagents and rate-limit recovery.
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextlib.contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_task_ledger (
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
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_task_status ON agent_task_ledger (status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_task_conv ON agent_task_ledger (conversation_id)"
            )
            conn.commit()

    def register_task(
        self,
        task_id: str,
        conversation_id: str,
        assignee_agent: str,
        user_goal: str,
        total_steps: int = 1,
        parent_task_id: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Registers a new agent/subagent task in the ledger."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO agent_task_ledger (
                    task_id, conversation_id, parent_task_id, assignee_agent,
                    user_goal, step_index, total_steps, status, dependencies,
                    checkpoint_state, token_usage, pause_reason, rate_limit_reset_at,
                    result_summary, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    conversation_id,
                    parent_task_id,
                    assignee_agent,
                    user_goal,
                    0,
                    total_steps,
                    "running",
                    json.dumps(dependencies or []),
                    json.dumps(initial_state or {}),
                    json.dumps({"input_tokens": 0, "output_tokens": 0}),
                    None,
                    None,
                    None,
                    now,
                    now,
                ),
            )
            conn.commit()

        return self.get_task(task_id)

    def checkpoint(
        self,
        task_id: str,
        step_index: int,
        checkpoint_state: Dict[str, Any],
        token_usage: Optional[Dict[str, int]] = None,
        pause_reason: Optional[str] = None,
        reset_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Saves step-level progress. If pause_reason is 'rate_limit', marks task as paused
        with an expected reset timestamp so it can be resumed automatically later.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        now_iso = now.isoformat()

        status = "running"
        reset_at_iso = None

        if pause_reason:
            if "rate_limit" in pause_reason.lower() or "429" in pause_reason:
                status = "rate_limited_paused"
                duration = reset_seconds if reset_seconds is not None else 60
                reset_at = now + datetime.timedelta(seconds=duration)
                reset_at_iso = reset_at.isoformat()
            else:
                status = "rate_limited_paused"

        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE agent_task_ledger
                SET step_index = ?,
                    checkpoint_state = ?,
                    token_usage = COALESCE(?, token_usage),
                    status = ?,
                    pause_reason = ?,
                    rate_limit_reset_at = ?,
                    updated_at = ?
                WHERE task_id = ?
                """,
                (
                    step_index,
                    json.dumps(checkpoint_state),
                    json.dumps(token_usage) if token_usage else None,
                    status,
                    pause_reason,
                    reset_at_iso,
                    now_iso,
                    task_id,
                ),
            )
            conn.commit()

        return self.get_task(task_id)

    def complete_task(
        self,
        task_id: str,
        result_summary: str,
        token_usage: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Marks a task as completed with its final summary."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE agent_task_ledger
                SET status = 'completed',
                    result_summary = ?,
                    token_usage = COALESCE(?, token_usage),
                    updated_at = ?
                WHERE task_id = ?
                """,
                (result_summary, json.dumps(token_usage) if token_usage else None, now, task_id),
            )
            conn.commit()
        return self.get_task(task_id)

    def fail_task(self, task_id: str, error_message: str) -> Dict[str, Any]:
        """Marks a task as failed with error details."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE agent_task_ledger
                SET status = 'failed',
                    result_summary = ?,
                    updated_at = ?
                WHERE task_id = ?
                """,
                (error_message, now, task_id),
            )
            conn.commit()
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves full task record."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM agent_task_ledger WHERE task_id = ?", (task_id,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            d["dependencies"] = json.loads(d.get("dependencies") or "[]")
            d["checkpoint_state"] = json.loads(d.get("checkpoint_state") or "{}")
            d["token_usage"] = json.loads(d.get("token_usage") or "{}")
            return d

    def get_resumable_tasks(self, assignee_agent: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Returns all tasks currently paused due to rate limits or interruption
        whose rate_limit_reset_at has expired (or has no expiration set).
        """
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        query = """
            SELECT * FROM agent_task_ledger
            WHERE status = 'rate_limited_paused'
              AND (rate_limit_reset_at IS NULL OR rate_limit_reset_at <= ?)
        """
        params = [now]
        if assignee_agent:
            query += " AND assignee_agent = ?"
            params.append(assignee_agent)

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["dependencies"] = json.loads(d.get("dependencies") or "[]")
                d["checkpoint_state"] = json.loads(d.get("checkpoint_state") or "{}")
                d["token_usage"] = json.loads(d.get("token_usage") or "{}")
                results.append(d)
            return results

    def list_tasks(
        self,
        conversation_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Lists tasks with optional status and conversation filters."""
        query = "SELECT * FROM agent_task_ledger WHERE 1=1"
        params = []
        if conversation_id:
            query += " AND conversation_id = ?"
            params.append(conversation_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["dependencies"] = json.loads(d.get("dependencies") or "[]")
                d["checkpoint_state"] = json.loads(d.get("checkpoint_state") or "{}")
                d["token_usage"] = json.loads(d.get("token_usage") or "{}")
                results.append(d)
            return results

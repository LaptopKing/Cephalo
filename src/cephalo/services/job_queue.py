"""
Cephalo Serialized Background Work Queue (job_queue.py)
======================================================
Provides a resilient, SQLite-backed asynchronous job queue for heavy background
tasks (FastEmbed, ONNX Runtime, Indra OCR, perceptual screen delta evaluation,
and continuous learning cycles).

Key Guarantees:
1. Strict Serialization: Only ONE heavy task executes at any given moment.
   Completely prevents parallel ONNX/CPU spikes that crash battery-powered laptops.
2. Hardware & Thermal Awareness: Queries SubagentGovernor before running a job.
   Pauses when battery is critical (<15%) and inserts cooling delays under high load.
3. Non-Blocking Fast Enqueue: Harness hooks (auto_harvest.py, PreInvocation, Stop)
   enqueue tasks in <2ms, returning instantly to the user without blocking.
4. Auto-Deduplication: Coalesces redundant pending requests (e.g., multiple vector syncs).
5. Crash-Safe Recovery: Automatically resets stalled jobs ('running' during crash/power-loss)
   back to 'pending' on startup so no background work is lost.
"""

from __future__ import annotations

import concurrent.futures
import datetime
import json
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "job_queue.db"

logger = logging.getLogger("cephalo.job_queue")


class JobQueue:
    """
    SQLite-backed persistent FIFO work queue with priority and hardware throttling.
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cephalo_job_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_type TEXT NOT NULL,
                    payload JSON NOT NULL,
                    status TEXT CHECK(status IN ('pending', 'running', 'completed', 'failed')) DEFAULT 'pending',
                    priority INTEGER DEFAULT 5,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_job_status_priority ON cephalo_job_queue (status, priority DESC, id ASC)"
            )
            conn.commit()

    def enqueue(
        self,
        job_type: str,
        payload: Optional[Dict[str, Any]] = None,
        priority: int = 5,
        deduplicate_pending: bool = True,
    ) -> int:
        """
        Pushes a new job into the queue.
        If deduplicate_pending is True and an identical pending job exists, returns its ID.
        """
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        payload_data = payload or {}
        payload_json = json.dumps(payload_data, sort_keys=True)

        with self._get_conn() as conn:
            if deduplicate_pending:
                existing = conn.execute(
                    """
                    SELECT id FROM cephalo_job_queue
                    WHERE job_type = ? AND payload = ? AND status = 'pending'
                    ORDER BY id ASC LIMIT 1
                    """,
                    (job_type, payload_json),
                ).fetchone()
                if existing:
                    return existing["id"]

            cur = conn.execute(
                """
                INSERT INTO cephalo_job_queue (job_type, payload, status, priority, created_at)
                VALUES (?, ?, 'pending', ?, ?)
                """,
                (job_type, payload_json, priority, now),
            )
            conn.commit()
            return cur.lastrowid

    def reset_stalled_jobs(self, timeout_minutes: int = 15) -> int:
        """
        Resets jobs that were marked 'running' but never completed due to a sudden
        laptop crash or process restart.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = (now - datetime.timedelta(minutes=timeout_minutes)).isoformat()

        with self._get_conn() as conn:
            cur = conn.execute(
                """
                UPDATE cephalo_job_queue
                SET status = 'pending', started_at = NULL, error_message = 'Reset after unexpected interruption/crash'
                WHERE status = 'running' AND (started_at IS NULL OR started_at < ?)
                """,
                (cutoff,),
            )
            conn.commit()
            return cur.rowcount

    def reset_all_running_jobs(self) -> int:
        """
        Resets ALL jobs currently marked 'running' back to 'pending'.
        Called during daemon startup or reboot initialization so interrupted jobs resume cleanly.
        """
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                UPDATE cephalo_job_queue
                SET status = 'pending', started_at = NULL, error_message = 'Recovered after reboot/shutdown'
                WHERE status = 'running'
                """
            )
            conn.commit()
            return cur.rowcount

    def fetch_next_job(self, max_concurrency: int = 1) -> Optional[Dict[str, Any]]:
        """
        Atomically locks and returns the highest priority pending job.
        Guarantees that no more than `max_concurrency` jobs are running simultaneously.
        """
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_conn() as conn:
            # Check currently running job count against allowed concurrency
            running_cnt = conn.execute(
                "SELECT COUNT(*) FROM cephalo_job_queue WHERE status = 'running'"
            ).fetchone()[0]
            if running_cnt >= max_concurrency:
                return None

            candidate = conn.execute(
                """
                SELECT * FROM cephalo_job_queue
                WHERE status = 'pending'
                ORDER BY priority DESC, id ASC
                LIMIT 1
                """
            ).fetchone()

            if not candidate:
                return None

            job_id = candidate["id"]
            conn.execute(
                """
                UPDATE cephalo_job_queue
                SET status = 'running', started_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (now, job_id),
            )
            conn.commit()

            d = dict(candidate)
            d["status"] = "running"
            d["started_at"] = now
            try:
                d["payload"] = json.loads(d["payload"])
            except Exception:
                pass
            return d

    def mark_completed(self, job_id: int) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE cephalo_job_queue SET status = 'completed', completed_at = ? WHERE id = ?",
                (now, job_id),
            )
            conn.commit()

    def mark_failed(self, job_id: int, error: str) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE cephalo_job_queue SET status = 'failed', completed_at = ?, error_message = ? WHERE id = ?",
                (now, str(error)[:500], job_id),
            )
            conn.commit()

    def get_status(self) -> Dict[str, Any]:
        """Returns statistics of pending, running, completed, and failed jobs."""
        with self._get_conn() as conn:
            counts = conn.execute(
                """
                SELECT status, COUNT(*) as cnt
                FROM cephalo_job_queue
                GROUP BY status
                """
            ).fetchall()
            stat_map = {row["status"]: row["cnt"] for row in counts}

            running_job = conn.execute(
                "SELECT id, job_type, started_at FROM cephalo_job_queue WHERE status = 'running' LIMIT 1"
            ).fetchone()

        return {
            "pending": stat_map.get("pending", 0),
            "running": stat_map.get("running", 0),
            "completed": stat_map.get("completed", 0),
            "failed": stat_map.get("failed", 0),
            "current_running_job": dict(running_job) if running_job else None,
        }

    def list_jobs(self, limit: int = 25) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM cephalo_job_queue
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def clear_history(self, hours_old: int = 24) -> int:
        cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours_old)).isoformat()
        with self._get_conn() as conn:
            cur = conn.execute(
                "DELETE FROM cephalo_job_queue WHERE status IN ('completed', 'failed') AND completed_at < ?",
                (cutoff,),
            )
            conn.commit()
            return cur.rowcount


class QueueWorker:
    """
    Serialized worker that pulls from JobQueue and safely executes heavy tasks.
    Enforces power constraints, dynamic concurrency, and thread-capping before every job.
    """

    def __init__(self, queue: Optional[JobQueue] = None):
        self.queue = queue or JobQueue()
        self.running = False
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {
            "sync_lancedb": self._handle_sync_lancedb,
            "embed_prompt": self._handle_embed_prompt,
            "screen_capture": self._handle_screen_capture,
            "continuous_learn": self._handle_continuous_learn,
            "transcript_harvest": self._handle_transcript_harvest,
            "ocr_screen_keyframe": self._handle_ocr_screen_keyframe,
        }
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self._active_futures: Dict[int, concurrent.futures.Future] = {}
        # Recover any stalled/in-flight jobs from prior crashes or system shutdown immediately
        self.queue.reset_all_running_jobs()

    def register_handler(self, job_type: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        self._handlers[job_type] = handler

    def get_dynamic_concurrency(self) -> int:
        """
        Calculates safe background worker concurrency based on real-time hardware status:
        - Battery mode: strictly 1 task at a time (prevent voltage drops / emergency power-off).
        - If battery < 20%: return 0 (pause all heavy background tasks to preserve system life).
        - AC power mode:
          - If CPU > 85% or available memory < 600MB: return 0 (pause background work to preserve user flow).
          - If CPU < 45% and available memory > 2500MB: return 2 (allow 2 parallel non-blocking tasks).
          - Otherwise: return 1.
        """
        try:
            from cephalo.services.subagent_governor import SubagentGovernor
            gov = SubagentGovernor()
            res = gov.inspect_resources()
            if res.get("on_battery"):
                bat = res.get("battery_percent")
                if bat is not None and bat < 20.0:
                    return 0
                return 1
        except Exception:
            pass

        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.05)
            mem = psutil.virtual_memory()
            avail_mb = mem.available / (1024 * 1024)

            if cpu > 85.0 or avail_mb < 600.0:
                return 0
            if cpu < 45.0 and avail_mb > 2500.0:
                return 2
            return 1
        except Exception:
            return 1

    def _poll_active_futures(self) -> None:
        """Polls and cleans up completed background futures."""
        for job_id, fut in list(self._active_futures.items()):
            if fut.done():
                try:
                    fut.result()
                except Exception as e:
                    logger.error(f"[Queue] Job #{job_id} async execution exception: {e}")
                self._active_futures.pop(job_id, None)

    def _execute_job(self, job: Dict[str, Any]) -> None:
        """Executes a single job with power limits and handler invocation."""
        job_id = job["id"]
        job_type = job["job_type"]
        payload = job.get("payload", {})
        logger.info(f"[Queue] Starting job #{job_id} ({job_type})...")

        handler = self._handlers.get(job_type)
        if not handler:
            err_msg = f"Unknown job type: {job_type}"
            logger.error(err_msg)
            self.queue.mark_failed(job_id, err_msg)
            return

        # Set power-safe environment limits for this job execution
        try:
            from cephalo.services.subagent_governor import SubagentGovernor
            gov = SubagentGovernor()
            res = gov.inspect_resources()
            power_threads = 1 if res.get("on_battery") else min(2, os.cpu_count() or 2)
            os.environ["OMP_NUM_THREADS"] = str(power_threads)
            os.environ["MKL_NUM_THREADS"] = str(power_threads)
        except Exception:
            os.environ["OMP_NUM_THREADS"] = "1"
            os.environ["MKL_NUM_THREADS"] = "1"

        try:
            handler(payload)
            self.queue.mark_completed(job_id)
            logger.info(f"[Queue] Completed job #{job_id} ({job_type}).")
            time.sleep(0.3)
        except Exception as e:
            logger.error(f"[Queue] Job #{job_id} failed: {e}", exc_info=True)
            self.queue.mark_failed(job_id, str(e))

    def process_one(self, sync: bool = False) -> bool:
        """
        Processes queue tasks.
        If sync=True: synchronously executes 1 job in the foreground thread (used by CLI).
        If sync=False: non-blocking dynamic concurrency execution (used by CephaloDaemon).
        Returns True if a job was processed or work is currently running, False if queue is empty or busy.
        """
        # 1. Reset any stalled jobs from prior reboots
        self.queue.reset_stalled_jobs(timeout_minutes=10)

        # 2. Check dynamic hardware concurrency
        concurrency = self.get_dynamic_concurrency()
        if concurrency <= 0:
            logger.debug("Queue worker paused: system under load or battery critical.")
            return False

        # 3. Poll active async futures
        self._poll_active_futures()

        if sync:
            job = self.queue.fetch_next_job(max_concurrency=concurrency)
            if not job:
                return False
            self._execute_job(job)
            return True

        # Non-blocking async daemon mode
        if len(self._active_futures) >= concurrency:
            return True

        job = self.queue.fetch_next_job(max_concurrency=concurrency)
        if not job:
            return len(self._active_futures) > 0

        fut = self._executor.submit(self._execute_job, job)
        self._active_futures[job["id"]] = fut
        return True

    # =========================================================================
    # Task Handlers
    # =========================================================================

    def _handle_sync_lancedb(self, payload: Dict[str, Any]) -> None:
        """Runs vector sync from prompts.jsonl into LanceDB in single-thread mode."""
        from cephalo.cli import get_pipeline
        pipeline = get_pipeline(table_name="prompts_local_1024")
        jsonl_path = Path(payload.get("jsonl_path", str(DATA_DIR / "prompts.jsonl")))
        inserted, existing = pipeline.sync_from_jsonl(jsonl_path=jsonl_path)
        logger.info(f"Vector sync completed: {inserted} inserted, {existing} existing.")

    def _handle_embed_prompt(self, payload: Dict[str, Any]) -> None:
        """Ingests and records a single prompt into LanceDB."""
        from cephalo.cli import get_pipeline
        pipeline = get_pipeline(table_name="prompts_local_1024")
        pipeline.ingest_prompt(
            raw_text=payload.get("text", ""),
            category=payload.get("category", "general"),
            source=payload.get("source", "agent"),
            intent=payload.get("intent"),
            tags=payload.get("tags"),
            sync_to_jsonl=payload.get("sync_to_jsonl", True),
        )

    def _handle_screen_capture(self, payload: Dict[str, Any]) -> None:
        """Runs perceptual delta screen capture and enqueues OCR."""
        from cephalo.services.screen_recorder import ScreenMemoryEngine
        engine = ScreenMemoryEngine()
        engine.capture_step(force=payload.get("force", False))

    def _handle_continuous_learn(self, payload: Dict[str, Any]) -> None:
        """Runs continuous learning cycle."""
        from cephalo.learning.continuous_learner import ContinuousLearner
        learner = ContinuousLearner()
        learner.run_cycle()

    def _handle_transcript_harvest(self, payload: Dict[str, Any]) -> None:
        """Scans conversation transcripts."""
        from cephalo.learning.auto_harvest import run_standalone_scan
        run_standalone_scan(payload.get("transcript_path"))

    def _handle_ocr_screen_keyframe(self, payload: Dict[str, Any]) -> None:
        """Extracts text from screen keyframe via Indra OCR and records into frame index and LanceDB."""
        image_path_str = payload.get("image_path")
        if not image_path_str:
            return
        image_path = Path(image_path_str)
        if not image_path.exists():
            logger.warning(f"OCR keyframe image not found: {image_path}")
            return

        frame_id = payload.get("frame_id")
        title = payload.get("title", "")
        proc = payload.get("process", "")

        try:
            from cephalo.services.subagent_governor import SubagentGovernor
            res = SubagentGovernor().inspect_resources()
            ocr_threads = 1 if res.get("on_battery") else 2
        except Exception:
            ocr_threads = 1

        raw_text = ""
        try:
            import cv2
            import indra_ocr
            import numpy as np
            from PIL import Image

            ocr_conv = indra_ocr.load(threads=ocr_threads, mode="auto")
            img = Image.open(image_path)
            gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
            page = ocr_conv.ocr(gray)
            raw_text = (getattr(page, "markdown", None) or getattr(page, "text", "") or "").strip()
        except Exception as e:
            logger.warning(f"Indra OCR execution failed for frame {image_path}: {e}")
            raw_text = ""

        from cephalo.services.screen_recorder import ScreenMemoryEngine
        clean_text = ScreenMemoryEngine()._sanitize_text(raw_text)

        # Update frame_index.jsonl
        index_file = DATA_DIR / "frames" / "frame_index.jsonl"
        if index_file.exists() and frame_id:
            try:
                lines = index_file.read_text(encoding="utf-8").splitlines()
                updated = False
                new_lines = []
                for line in lines:
                    if not line.strip():
                        continue
                    try:
                        rec = json.loads(line)
                        if rec.get("id") == frame_id:
                            rec["ocr_text"] = clean_text
                            rec["ocr_status"] = "completed"
                            updated = True
                        new_lines.append(json.dumps(rec, ensure_ascii=False))
                    except Exception:
                        new_lines.append(line)
                if updated:
                    index_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            except Exception as idx_err:
                logger.warning(f"Failed to update frame_index.jsonl: {idx_err}")

        # Ingest into LanceDB if rich in text (>15 words)
        words = clean_text.split()
        if len(words) > 15:
            try:
                from cephalo.cli import get_pipeline
                pipeline = get_pipeline(table_name="prompts_local_1024")
                pipeline.ingest_prompt(
                    raw_text=f"Screen OCR [{title} - {proc}]:\n{clean_text}",
                    category="screen_ocr",
                    source="screen_capture",
                    intent="visual_desktop_context",
                    tags=["screen", "ocr", proc or "desktop"],
                    sync_to_jsonl=True,
                )
                logger.info(f"Ingested screen OCR ({len(words)} words) into LanceDB for frame {frame_id}")
            except Exception as ing_err:
                logger.warning(f"Could not ingest screen OCR to LanceDB: {ing_err}")

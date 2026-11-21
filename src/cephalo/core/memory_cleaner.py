#!/usr/bin/env python3
"""
Cephalo Memory Cleaner & Deduplication Engine (memory_cleaner.py)
================================================================
Autonomously purges empty prompt entries, deduplicates redundant records,
and synchronizes LanceDB vector storage.

Runs on demand via `cephalo clean` and on a 1-hour recurring schedule
via Cephalo's background daemon and lifecycle hooks.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("cephalo.cleaner")

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
PROMPTS_FILE = DATA_DIR / "prompts.jsonl"
LANCEDB_DIR = DATA_DIR / "lancedb"
STATE_FILE = DATA_DIR / "clean_state.json"


class MemoryCleaner:
    """Purges empty records and collapses duplicate memories across Cephalo."""

    def __init__(self, prompts_file: Path = PROMPTS_FILE, lancedb_dir: Path = LANCEDB_DIR):
        self.prompts_file = prompts_file
        self.lancedb_dir = lancedb_dir

    def clean_records(self) -> Dict[str, int]:
        """
        Reads prompts.jsonl, filters out empty content, deduplicates identical
        memories, writes back atomically, and resyncs LanceDB.
        """
        if not self.prompts_file.exists():
            return {"empty_removed": 0, "duplicates_removed": 0, "total_retained": 0}

        records: List[Dict[str, Any]] = []
        try:
            with open(self.prompts_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Failed to read {self.prompts_file}: {e}")
            return {"empty_removed": 0, "duplicates_removed": 0, "total_retained": 0}

        empty_removed = 0
        non_empty: List[Dict[str, Any]] = []

        # 1. Filter out empty records
        for r in records:
            content = r.get("content", "")
            if not isinstance(content, str) or not content.strip():
                empty_removed += 1
                continue
            non_empty.append(r)

        # 2. Deduplicate identical content
        # Group records by normalized content
        seen_contents: Dict[str, List[Dict[str, Any]]] = {}
        for r in non_empty:
            norm = " ".join(r["content"].strip().lower().split())
            seen_contents.setdefault(norm, []).append(r)

        duplicates_removed = 0
        retained: List[Dict[str, Any]] = []

        for norm, group in seen_contents.items():
            if len(group) == 1:
                retained.append(group[0])
            else:
                # Rank group records to select the best canonical entry:
                # Priority:
                # 1. Active over deprecated (is_deprecated is False/None > True)
                # 2. Non-quarantined over quarantined
                # 3. User/agent over webhook/auto
                # 4. Longest metadata / tags
                # 5. Latest timestamp
                def score_record(rec: Dict[str, Any]) -> Tuple[int, int, int, str]:
                    not_dep = 1 if not rec.get("is_deprecated") else 0
                    not_quar = 1 if not rec.get("is_quarantined") else 0
                    tags_len = len(rec.get("tags") or [])
                    ts = rec.get("timestamp") or ""
                    return (not_dep, not_quar, tags_len, ts)

                group.sort(key=score_record, reverse=True)
                canonical = group[0]
                retained.append(canonical)
                duplicates_removed += len(group) - 1

        # 3. If no modifications needed, record state and return early
        if empty_removed == 0 and duplicates_removed == 0:
            self._record_clean_state(0, 0, len(retained))
            return {
                "empty_removed": 0,
                "duplicates_removed": 0,
                "total_retained": len(retained),
            }

        # Preserve original relative order by ID / timestamp
        retained.sort(key=lambda x: x.get("timestamp") or "")

        # 4. Write back atomically in same directory to prevent cross-device link errors
        target_dir = self.prompts_file.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        temp_fd, temp_path = tempfile.mkstemp(dir=target_dir, prefix="prompts_clean_", suffix=".jsonl")
        try:
            with open(temp_fd, "w", encoding="utf-8") as f:
                for r in retained:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            shutil.move(temp_path, self.prompts_file)
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error(f"Failed to atomically write cleaned prompts.jsonl: {e}")
            raise e

        # 5. Resync LanceDB only if records were purged or stale entries exist
        retained_ids = {r["id"] for r in retained}
        if empty_removed > 0 or duplicates_removed > 0:
            self._resync_lancedb(retained_ids)

        # 6. Record clean state
        self._record_clean_state(empty_removed, duplicates_removed, len(retained))

        return {
            "empty_removed": empty_removed,
            "duplicates_removed": duplicates_removed,
            "total_retained": len(retained),
        }

    def _resync_lancedb(self, retained_ids: Optional[Set[str]] = None) -> None:
        """Fully re-synchronizes the LanceDB tables from the cleaned prompts.jsonl."""
        try:
            from cephalo.commands.common import get_pipeline
            pipeline = get_pipeline()
            store = pipeline.store
            # Delete stale records that are no longer in retained_ids
            if retained_ids is not None:
                existing_ids = store.get_existing_ids()
                stale_ids = existing_ids - retained_ids
                if stale_ids:
                    store.delete_records(stale_ids)
            # Also purge any empty/blank content records in store
            if "content" in store.table.schema.names:
                try:
                    store.table.delete("content = '' OR content IS NULL")
                except Exception:
                    pass
            # Sync any new prompts
            if self.prompts_file.exists():
                pipeline.sync_from_jsonl(self.prompts_file)
        except Exception as e:
            logger.warning(f"LanceDB re-sync warning during cleanup: {e}")

    def _record_clean_state(self, empty_cnt: int, dup_cnt: int, total_cnt: int) -> None:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            state = {
                "last_clean_timestamp": time.time(),
                "last_clean_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "empty_removed": empty_cnt,
                "duplicates_removed": dup_cnt,
                "total_retained": total_cnt,
            }
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    @staticmethod
    def should_run_periodic_clean(interval_seconds: int = 3600) -> bool:
        """Returns True if more than interval_seconds have passed since last cleanup."""
        if not STATE_FILE.exists():
            return True
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            last_ts = state.get("last_clean_timestamp", 0)
            return (time.time() - last_ts) >= interval_seconds
        except Exception:
            return True


def run_cleanup() -> Dict[str, int]:
    """Convenience helper to run cleanup immediately."""
    cleaner = MemoryCleaner()
    return cleaner.clean_records()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    res = run_cleanup()
    print(f"[+] Cephalo Memory Cleanup Complete:")
    print(f"    - Removed empty records:      {res['empty_removed']}")
    print(f"    - Removed duplicate records:  {res['duplicates_removed']}")
    print(f"    - Clean memories retained:    {res['total_retained']}")

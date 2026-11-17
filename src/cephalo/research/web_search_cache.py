"""
SQLite Cache Layer for Web Search SERP and Raw Pages.
"""

import datetime
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional

from cephalo.config import DATA_DIR
from cephalo.research.serp_renderer import CephaloSERP, SearchItem

logger = logging.getLogger("cephalo.research.web_search_cache")
DEFAULT_SERP_CACHE_DB = DATA_DIR / "serp_cache.db"


class WebSearchCache:
    """Thread-safe SQLite persistent cache for SERP queries and scraped HTML pages."""

    def __init__(self, db_path: Path = DEFAULT_SERP_CACHE_DB):
        self.db_path = db_path
        self._init_cache_db()

    def _init_cache_db(self) -> None:
        """Initializes SQLite cache database to preserve monthly API quota and accelerate retrieval."""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(CACHE_DB_PATH) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS serp_cache (
                        cache_key TEXT PRIMARY KEY,
                        query TEXT NOT NULL,
                        serp_json TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        expires_at REAL NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS page_cache (
                        url_hash TEXT PRIMARY KEY,
                        url TEXT NOT NULL,
                        content TEXT NOT NULL,
                        engine TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        expires_at REAL NOT NULL
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.debug(f"Failed to initialize search cache DB: {e}")

    def _get_page_from_cache(self, url: str) -> Optional[str]:
        """Retrieves cached page content if still fresh."""
        try:
            url_hash = hashlib.sha256(url.strip().encode("utf-8")).hexdigest()
            now = time.time()
            with sqlite3.connect(CACHE_DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT content FROM page_cache WHERE url_hash = ? AND expires_at > ?",
                    (url_hash, now),
                )
                row = cur.fetchone()
                if row:
                    return row[0]
        except Exception as e:
            logger.debug(f"Page cache lookup failed: {e}")
        return None

    def _save_page_to_cache(self, url: str, content: str, engine: str = "scrapling", ttl_hours: float = 24.0) -> None:
        """Persists extracted page markdown/text to SQLite cache."""
        try:
            url_hash = hashlib.sha256(url.strip().encode("utf-8")).hexdigest()
            now = time.time()
            expires = now + (ttl_hours * 3600)
            with sqlite3.connect(CACHE_DB_PATH) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO page_cache (url_hash, url, content, engine, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (url_hash, url.strip(), content, engine, now, expires),
                )
                conn.commit()
        except Exception as e:
            logger.debug(f"Failed to cache page content: {e}")

    def _get_from_cache(self, query: str) -> Optional[CephaloSERP]:
        """Retrieves cached SERP result if still fresh."""
        try:
            cache_key = hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()
            now = time.time()
            with sqlite3.connect(CACHE_DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT serp_json FROM serp_cache WHERE cache_key = ? AND expires_at > ?",
                    (cache_key, now),
                )
                row = cur.fetchone()
                if row:
                    data = json.loads(row[0])
                    organic = [SearchItem(**item) for item in data.get("organic_results", [])]
                    social = [SearchItem(**item) for item in data.get("social_blocks", [])]
                    return CephaloSERP(
                        query=data.get("query", query),
                        quick_summary=data.get("quick_summary", ""),
                        key_takeaways=data.get("key_takeaways", []),
                        citations=data.get("citations", []),
                        organic_results=organic,
                        social_blocks=social,
                        execution_time_seconds=0.01,
                        engine_used=data.get("engine_used", "Cache") + " (Cached)",
                    )
        except Exception as e:
            logger.debug(f"Cache lookup failed: {e}")
        return None

    def _save_to_cache(self, serp: CephaloSERP, ttl_hours: float = 24.0) -> None:
        """Persists SERP result to SQLite cache."""
        try:
            cache_key = hashlib.sha256(serp.query.strip().lower().encode("utf-8")).hexdigest()
            now = time.time()
            expires = now + (ttl_hours * 3600)
            data_str = json.dumps(serp.to_dict(), ensure_ascii=False)
            with sqlite3.connect(CACHE_DB_PATH) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO serp_cache (cache_key, query, serp_json, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                    (cache_key, serp.query, data_str, now, expires),
                )
                conn.commit()
        except Exception as e:
            logger.debug(f"Failed to cache search result: {e}")


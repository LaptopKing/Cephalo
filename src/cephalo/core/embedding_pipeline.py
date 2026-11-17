#!/usr/bin/env python3
"""
Personal Second Brain - Clean, Production-Ready Embedding & Vector Storage Pipeline
===================================================================================
Features:
1. Sanitization First: All inputs (prompts, queries, batch files) are processed through
   Presidio (PII redaction) + deterministic regex rules before reaching embedding models
   or vector storage.
2. Dual Embedding Support:
   - Mode A (Local / Zero-Leak): Lightweight, local ONNX embeddings via FastEmbed
     (e.g., 'BAAI/bge-small-en-v1.5' [384d] or 'nomic-ai/nomic-embed-text-v1.5' [768d]).
   - Mode B (Google Cloud): Google 'text-embedding-004' via Google GenAI SDK with
     automatic HTTP REST fallback. Full Matryoshka dimension truncation (e.g., 768 -> 256).
3. Storage: High-performance, columnar vector storage in LanceDB with native PyArrow schema,
   metadata preservation, and automatic ID deduplication.
4. Python 3.12.10 verified and production-ready.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import math
import os
import re
import sys
import time
import ctypes
import warnings

warnings.filterwarnings("ignore", category=FutureWarning, module="torch.jit")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="fastembed")
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Load environment variables if python-dotenv is present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pyarrow as pa
import lancedb

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("second_brain.pipeline")
logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)

# Default Base Paths
ROOT_DIR = Path(__file__).resolve().parents[3]
BASE_DIR = ROOT_DIR
DATA_DIR = ROOT_DIR / "data"
PROMPTS_FILE = DATA_DIR / "prompts.jsonl"
DEFAULT_LANCEDB_DIR = DATA_DIR / "lancedb"

TAG_REGEX = re.compile(r'(?<!\S)#([a-zA-Z][a-zA-Z0-9_\-\/]*)\b')



from cephalo.core.sanitizer import (
    Sanitizer,
    calculate_shannon_entropy,
    extract_tags,
    is_code_line,
)
from cephalo.core.embedders import (
    BaseEmbedder,
    FastEmbedEmbedder,
    GoogleEmbedder,
    create_embedder,
    get_safe_onnx_providers,
)
from cephalo.core.lancedb_store import LanceDBStore

class EmbeddingPipeline:
    """Coordinates Sanitization -> Embedding -> LanceDB Storage."""

    def __init__(
        self,
        embedder: BaseEmbedder,
        db_path: Path = DEFAULT_LANCEDB_DIR,
        table_name: Optional[str] = None,
        sanitizer: Optional[Sanitizer] = None,
    ):
        self.sanitizer = sanitizer or Sanitizer(enable_gliner=False)
        self.embedder = embedder
        self.db_path = Path(db_path)

        # Default table name incorporates mode and dimension to avoid vector dimension conflicts
        if not table_name:
            table_name = f"prompts_{self.embedder.mode}_{self.embedder.dimension}"

        self.store = LanceDBStore(
            db_path=self.db_path,
            table_name=table_name,
            dimension=self.embedder.dimension,
        )

    def ingest_prompt(
        self,
        raw_text: str,
        prompt_id: Optional[str] = None,
        source: str = "cli",
        category: str = "general",
        intent: str = "",
        traits: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        supersedes: Optional[str] = None,
        relates_to: Optional[List[str]] = None,
        sync_to_jsonl: bool = True,
        auto_reconcile: bool = True,
    ) -> Dict[str, Any]:
        """Sanitizes, embeds, and stores a single prompt with tag extraction, contextual reconciliation, and supersession tracking."""
        clean_text = self.sanitizer.sanitize(raw_text.strip())
        traits = traits or []

        # Extract inline tags and combine with explicit tags
        inline_tags = extract_tags(raw_text)
        merged_tags = list(dict.fromkeys((tags or []) + inline_tags))
        merged_tags = [t.lstrip("#").strip().lower() for t in merged_tags if t.strip()]

        if not prompt_id:
            count = self.store.count() + 1
            prompt_id = f"prompt-{count:03d}"

        superseded_records: List[str] = []

        # If this prompt explicitly supersedes an existing memory, deprecate the older one
        if supersedes:
            self.store.deprecate_record(supersedes, superseded_by=prompt_id, sync_to_jsonl=sync_to_jsonl)
            superseded_records.append(supersedes)

        # Autonomous Contextual Reconciliation for preferences and stateful rules
        if auto_reconcile and self.store.count() > 0:
            try:
                from cephalo.core.preference_reconciler import PreferenceReconciler
                reconciler = PreferenceReconciler()
                if reconciler.is_stateful_candidate(category, clean_text):
                    candidates = self.search(
                        raw_query=clean_text,
                        query_type="hybrid",
                        limit=8,
                        include_deprecated=False,
                    )
                    found_superseded = reconciler.find_superseded_records(
                        new_text=clean_text,
                        candidate_records=candidates,
                        category=category,
                        current_id=prompt_id,
                    )
                    for item in found_superseded:
                        old_id = item["id"]
                        if old_id and old_id not in superseded_records:
                            self.store.deprecate_record(old_id, superseded_by=prompt_id, sync_to_jsonl=sync_to_jsonl)
                            superseded_records.append(old_id)
                            logger.info(f"[Reconciler] Auto-superseded memory '{old_id}': {item['reason']}")
            except Exception as e:
                logger.warning(f"Autonomous reconciliation check encountered error: {e}")

        effective_supersedes = supersedes or (",".join(superseded_records) if superseded_records else "")

        timestamp = datetime.datetime.now().astimezone().isoformat()
        vector = self.embedder.embed_query(clean_text)

        record = {
            "id": prompt_id,
            "vector": vector,
            "content": clean_text,
            "category": category,
            "source": source,
            "timestamp": timestamp,
            "embedding_model": f"{self.embedder.mode}:{self.embedder.model_name}",
            "dimension": self.embedder.dimension,
            "extracted_intent": intent,
            "learned_traits": traits,
            "tags": merged_tags,
            "supersedes": effective_supersedes,
            "superseded_by": "",
            "relates_to": relates_to or [],
            "is_deprecated": False,
            "sanitized": True,
        }

        self.store.add_records([record])

        # Optionally append to prompts.jsonl to keep text store synchronized
        if sync_to_jsonl:
            PROMPTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            jsonl_entry = {
                "id": prompt_id,
                "timestamp": timestamp,
                "source": source,
                "category": category,
                "tags": merged_tags,
                "supersedes": effective_supersedes,
                "superseded_by": "",
                "relates_to": relates_to or [],
                "is_deprecated": False,
                "content": clean_text,
                "extracted_intent": intent,
                "learned_traits": traits,
            }
            with open(PROMPTS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(jsonl_entry, ensure_ascii=False) + "\n")

        record_copy = dict(record)
        record_copy["superseded_records"] = superseded_records
        return record_copy

    def sync_from_jsonl(self, jsonl_path: Path = PROMPTS_FILE) -> Tuple[int, int]:
        """Ingests entries from prompts.jsonl into the LanceDB vector store."""
        jsonl_path = Path(jsonl_path)
        if not jsonl_path.exists():
            logger.warning(f"File not found: {jsonl_path}")
            return 0, 0

        existing_ids = self.store.get_existing_ids()
        to_process: List[Dict[str, Any]] = []

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("id") not in existing_ids:
                        to_process.append(entry)
                except Exception as e:
                    logger.error(f"Error parsing jsonl line: {e}")

        if not to_process:
            logger.info("Vector database is already up-to-date with prompts.jsonl.")
            return 0, len(existing_ids)

        logger.info(f"Processing {len(to_process)} new prompts for vector storage...")

        # 1. Sanitize all contents
        sanitized_texts = [
            self.sanitizer.sanitize(item.get("content", "")) for item in to_process
        ]

        # 2. Batch embed with hardware & battery throttling
        logger.info(
            f"Generating embeddings via [{self.embedder.mode.upper()}] "
            f"model='{self.embedder.model_name}' dim={self.embedder.dimension}..."
        )

        try:
            from cephalo.services.subagent_governor import SubagentGovernor
            res = SubagentGovernor().inspect_resources()
            on_battery = res.get("on_battery", False)
            bat_pct = res.get("battery_percent")
            if on_battery and bat_pct is not None and bat_pct < 20.0:
                logger.warning(
                    f"Vector sync deferred: battery critically low ({bat_pct:.1f}% on battery). "
                    "Pausing ONNX batch embedding to prevent laptop emergency power-off."
                )
                return 0, len(existing_ids)
            chunk_size = 5 if on_battery else 25
            cooldown_sleep = 0.5 if on_battery else 0.05
        except Exception:
            chunk_size = 5
            cooldown_sleep = 0.3

        vectors: List[List[float]] = []
        for i in range(0, len(sanitized_texts), chunk_size):
            chunk = sanitized_texts[i : i + chunk_size]
            chunk_vecs = self.embedder.embed_texts(chunk)
            vectors.extend(chunk_vecs)
            if cooldown_sleep > 0 and (i + chunk_size < len(sanitized_texts)):
                time.sleep(cooldown_sleep)

        # 3. Assemble LanceDB records
        records = []
        for i, item in enumerate(to_process):
            raw_traits = item.get("learned_traits", [])
            if isinstance(raw_traits, str):
                traits_list = [t.strip() for t in raw_traits.split(",") if t.strip()]
            elif isinstance(raw_traits, list):
                traits_list = [str(t) for t in raw_traits]
            else:
                traits_list = []

            inline_tags = extract_tags(item.get("content", ""))
            item_tags = item.get("tags", [])
            if isinstance(item_tags, str):
                item_tags = [t.strip() for t in item_tags.split(",") if t.strip()]
            combined_tags = list(dict.fromkeys(item_tags + inline_tags))
            clean_tags = [t.lstrip("#").strip().lower() for t in combined_tags if t.strip()]

            records.append({
                "id": item.get("id", f"prompt-{i+1:03d}"),
                "vector": vectors[i],
                "content": sanitized_texts[i],
                "category": item.get("category", "general"),
                "source": item.get("source", "jsonl_import"),
                "timestamp": item.get("timestamp", datetime.datetime.now().astimezone().isoformat()),
                "embedding_model": f"{self.embedder.mode}:{self.embedder.model_name}",
                "dimension": self.embedder.dimension,
                "extracted_intent": item.get("extracted_intent", ""),
                "learned_traits": traits_list,
                "tags": clean_tags,
                "supersedes": str(item.get("supersedes", "")),
                "superseded_by": str(item.get("superseded_by", "")),
                "relates_to": list(item.get("relates_to", [])),
                "is_deprecated": bool(item.get("is_deprecated", False)),
                "sanitized": True,
            })

        inserted = self.store.add_records(records)
        return inserted, len(existing_ids)

    def search(
        self,
        raw_query: str,
        query_type: str = "hybrid",
        where: Optional[str] = None,
        limit: int = 5,
        tag: Optional[str] = None,
        include_deprecated: bool = False,
    ) -> List[Dict[str, Any]]:
        """Sanitizes query, generates query vector, and executes hybrid, vector, or FTS search."""
        # Sanitize query before embedding (Zero-Leak)
        clean_query = self.sanitizer.sanitize(raw_query.strip())
        query_vector = self.embedder.embed_query(clean_query)
        results = self.store.search(
            query_vector=query_vector,
            query_text=clean_query,
            query_type=query_type,
            where=where,
            limit=limit,
            tag=tag,
            include_deprecated=include_deprecated,
        )
        return results


# ==============================================================================
# 5. CLI & Factory Helper
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Personal Second Brain - Vector Ingestion & Semantic Search Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Global options
    parser.add_argument(
        "--mode",
        choices=["local", "google"],
        default="local",
        help="Embedding mode: 'local' (FastEmbed, zero-leak) or 'google' (Google Cloud text-embedding-004).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Embedding model identifier (default: 'Qwen/Qwen3-Embedding-0.6B-Q' [32k tokens, Apache 2.0] for local).",
    )
    parser.add_argument(
        "--dim",
        type=int,
        default=None,
        help="Embedding dimensionality (useful for Matryoshka dimension truncation on Google Cloud: e.g. 768, 256, 128).",
    )
    parser.add_argument(
        "--table",
        type=str,
        default=None,
        help="LanceDB table name (defaults to 'prompts_local' or 'prompts_google').",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Google API Key (can also be set via GEMINI_API_KEY or GOOGLE_API_KEY environment variable).",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=str(DEFAULT_LANCEDB_DIR),
        help=f"Path to local LanceDB storage directory (default: {DEFAULT_LANCEDB_DIR}).",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Command: sync
    sync_p = subparsers.add_parser("sync", help="Sync prompts.jsonl into the vector database.")
    sync_p.add_argument(
        "--file",
        type=str,
        default=str(PROMPTS_FILE),
        help=f"Path to prompts jsonl file (default: {PROMPTS_FILE}).",
    )

    # Command: add
    add_p = subparsers.add_parser("add", help="Sanitize, embed, and store a new prompt directly.")
    add_p.add_argument("text", type=str, help="Raw prompt content to ingest.")
    add_p.add_argument("--category", type=str, default="general", help="Prompt category.")
    add_p.add_argument("--source", type=str, default="cli", help="Source of prompt.")
    add_p.add_argument("--intent", type=str, default="", help="Extracted intent.")

    # Command: search
    search_p = subparsers.add_parser("search", help="Perform hybrid, vector, or keyword search against stored records.")
    search_p.add_argument("query", type=str, help="Search query string.")
    search_p.add_argument(
        "--type",
        choices=["hybrid", "vector", "fts"],
        default="hybrid",
        help="Search mode: 'hybrid' (vector + BM25 keyword), 'vector' (semantic only), or 'fts' (BM25 keyword only). Default: hybrid.",
    )
    search_p.add_argument(
        "--where",
        type=str,
        default=None,
        help="SQL filter expression (e.g. \"category = 'code'\" or \"timestamp >= '2026-10-20'\").",
    )
    search_p.add_argument("--limit", type=int, default=3, help="Max results to return (default: 3).")

    # Command: status
    subparsers.add_parser("status", help="Print vector store status, table names, and record counts.")

    args = parser.parse_args()

    # Determine command
    cmd = args.command or "status"

    # Initialize embedder and pipeline
    try:
        embedder = create_embedder(
            mode=args.mode,
            model=args.model,
            dimension=args.dim,
            api_key=args.api_key,
        )
        pipeline = EmbeddingPipeline(
            embedder=embedder,
            db_path=Path(args.db_path),
            table_name=args.table,
        )
    except Exception as init_err:
        print(f"\n[ERROR] Pipeline initialization failed: {init_err}")
        sys.exit(1)

    # Execute subcommand
    if cmd == "sync":
        print("=" * 60)
        print("  SECOND BRAIN - VECTOR STORE SYNC")
        print("=" * 60)
        print(f"Source JSONL:     {args.file}")
        print(f"Embedding Engine: {embedder.mode.upper()} ({embedder.model_name}, dim={embedder.dimension})")
        print(f"LanceDB Path:     {pipeline.db_path}")
        print(f"Table Name:       {pipeline.store.table_name}")
        print("-" * 60)
        inserted, existing = pipeline.sync_from_jsonl(jsonl_path=Path(args.file))
        print(f"[+] Sync Complete: {inserted} new records inserted ({existing} already indexed).")
        print(f"[+] Total table records: {pipeline.store.count()}")
        print("=" * 60)

    elif cmd == "add":
        record = pipeline.ingest_prompt(
            raw_text=args.text,
            category=args.category,
            source=args.source,
            intent=args.intent,
        )
        print(f"[+] Recorded & Indexed [{record['id']}]:")
        print(f"    Sanitized Content: {record['content']}")
        print(f"    Model:             {record['embedding_model']} (dim={record['dimension']})")
        print(f"    Table:             {pipeline.store.table_name}")

    elif cmd == "search":
        print(f"\nSearching for: '{args.query}' (Mode: {embedder.mode.upper()}, Type: {args.type.upper()}, Dim: {embedder.dimension})")
        if args.where:
            print(f"SQL Filter:     {args.where}")
        results = pipeline.search(
            raw_query=args.query,
            query_type=args.type,
            where=args.where,
            limit=args.limit,
        )
        if not results:
            print("No matching records found. (Have you run 'sync' first?)")
            return

        print("-" * 70)
        for rank, res in enumerate(results, 1):
            if "_relevance_score" in res:
                score_str = f"Relevance: {res['_relevance_score']:.4f}"
            elif "_distance" in res:
                score_str = f"Distance: {res['_distance']:.4f}"
            elif "_score" in res:
                score_str = f"Score: {res['_score']:.4f}"
            else:
                score_str = "Match"

            pid = res.get("id", "N/A")
            cat = res.get("category", "general")
            content = res.get("content", "")
            preview = (content[:95] + "...") if len(content) > 95 else content
            print(f"  #{rank} [{score_str}] [{pid}] ({cat})")
            print(f"      {preview}")
        print("-" * 70)

    elif cmd == "status":
        sanitizer = pipeline.sanitizer
        print("=" * 60)
        print("  PERSONAL SECOND BRAIN - VECTOR STORAGE STATUS")
        print("=" * 60)
        print(f"LanceDB Directory: {pipeline.db_path}")
        print(f"Active Table:      {pipeline.store.table_name} ({pipeline.store.count()} records)")
        table_list = list(getattr(pipeline.store.db.list_tables(), 'tables', pipeline.store.db.list_tables()))
        print(f"All Tables:        {table_list}")
        print(f"Embedding Mode:    {embedder.mode.upper()}")
        print(f"Model Name:        {embedder.model_name}")
        print(f"Vector Dimension:  {embedder.dimension}")
        print(f"Presidio Engine:   {'Active (Spacy en_core_web_lg)' if sanitizer.presidio_available else 'Fallback Regex'}")
        print("=" * 60)


if __name__ == "__main__":
    main()


__all__ = [
    "Sanitizer",
    "extract_tags",
    "calculate_shannon_entropy",
    "is_code_line",
    "BaseEmbedder",
    "FastEmbedEmbedder",
    "GoogleEmbedder",
    "create_embedder",
    "get_safe_onnx_providers",
    "LanceDBStore",
    "EmbeddingPipeline",
]

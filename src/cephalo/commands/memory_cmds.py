from __future__ import annotations

import datetime
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from cephalo.commands.common import (
    BASE_DIR,
    DATA_DIR,
    DEFAULT_LANCEDB_DIR,
    PROFILE_FILE,
    PROMPTS_FILE,
    ROOT_DIR,
    get_pipeline,
    parse_profile_sections,
    resolve_cli_input,
)

logger = logging.getLogger("cephalo.cli")

def cmd_search(args) -> None:
    """Performs hybrid, vector, or keyword search across LanceDB."""
    query = resolve_cli_input(
        args,
        field_name="query",
        allow_stdin=True,
        error_message="Error: No search query provided. Provide query as argument or pipe via stdin.",
    )

    tag = getattr(args, "tag", None)
    include_deprecated = getattr(args, "include_deprecated", False)

    pipeline = get_pipeline(table_name=args.table)
    results = pipeline.search(
        raw_query=query,
        query_type=args.type,
        where=args.where,
        limit=args.limit,
        tag=tag,
        include_deprecated=include_deprecated,
    )

    min_score = getattr(args, "min_score", None)
    if min_score is not None:
        filtered = []
        for r in results:
            if "_relevance_score" in r:
                if float(r["_relevance_score"]) >= min_score:
                    filtered.append(r)
            elif "_score" in r:
                if float(r["_score"]) >= min_score:
                    filtered.append(r)
            elif "_distance" in r:
                dist = float(r["_distance"])
                if min_score >= 1.0:
                    if dist <= min_score:
                        filtered.append(r)
                else:
                    sim = 1.0 / (1.0 + dist)
                    if sim >= min_score:
                        filtered.append(r)
            else:
                filtered.append(r)
        results = filtered

    if getattr(args, "copy", False):
        from cephalo.utils.clipboard_utils import set_clipboard_text
        if args.json:
            clean_results = [{k: v for k, v in r.items() if k != "vector"} for r in results]
            set_clipboard_text(json.dumps(clean_results, indent=2, ensure_ascii=False))
        else:
            text_lines = [f"Cephalo Search Results for '{query}':"]
            for rank, res in enumerate(results, 1):
                text_lines.append(f"#{rank} [{res.get('category', 'general')}]: {res.get('content', '')}")
            set_clipboard_text("\n\n".join(text_lines))
        if not args.json:
            print("[+] Search results copied to clipboard.")

    if args.json:
        if getattr(args, "compact", False):
            compact_results = [
                {
                    "category": r.get("category", "general"),
                    "content": r.get("content", ""),
                    "score": round(float(r.get("_relevance_score", r.get("_distance", 0.0))), 4)
                }
                for r in results
            ]
            print(json.dumps({"query": args.query, "count": len(compact_results), "results": compact_results}, ensure_ascii=False))
            return

        # Strip internal pyarrow formats if any for clean JSON serialization
        clean_results = []
        for r in results:
            clean_r = {k: v for k, v in r.items() if k != "vector"}
            clean_results.append(clean_r)
        print(json.dumps({"query": args.query, "type": args.type, "count": len(clean_results), "results": clean_results}, indent=2, ensure_ascii=False))
        return

    if getattr(args, "compact", False):
        if not results:
            print("No matching records found in LanceDB.")
            return
        for r in results:
            cat = r.get("category", "general")
            content = r.get("content", "")
            print(f"• [{cat}] {content}")
        return

    print(f"\nSearching for: '{args.query}' (Type: {args.type.upper()})")
    if args.where:
        print(f"Filter:         {args.where}")

    if not results:
        print("No matching records found in LanceDB.")
        return

    print("-" * 70)
    for rank, res in enumerate(results, 1):
        score_str = "Match"
        if "_relevance_score" in res:
            score_str = f"Relevance: {res['_relevance_score']:.4f}"
        elif "_distance" in res:
            score_str = f"Distance: {res['_distance']:.4f}"
        elif "_score" in res:
            score_str = f"Score: {res['_score']:.4f}"

        pid = res.get("id", "N/A")
        cat = res.get("category", "general")
        tags_str = (" " + " ".join([f"#{t}" for t in res.get("tags", [])])) if res.get("tags") else ""
        dep_str = " [DEPRECATED]" if res.get("is_deprecated") else ""
        super_str = f" [Supersedes {res['supersedes']}]" if res.get("supersedes") else ""
        content = res.get("content", "")
        preview = (content[:95] + "...") if len(content) > 95 else content
        print(f"  #{rank} [{score_str}] [{pid}] ({cat}){tags_str}{dep_str}{super_str}")
        print(f"      {preview}")
    print("-" * 70)

def cmd_def(args) -> None:
    """Token-efficient AST symbol search across workspace projects (inspired by XERJ 'def')."""
    symbol = resolve_cli_input(
        args,
        field_name="symbol",
        allow_stdin=True,
        error_message="Error: No symbol provided. Specify a symbol name (e.g. cephalo def search).",
    )

    target_path = Path(args.path) if getattr(args, "path", None) else None
    from cephalo.core.symbol_extractor import CodeSymbolIndexer
    indexer = CodeSymbolIndexer(root_dir=target_path)

    results = indexer.find_definitions(
        symbol_name=symbol,
        target_dir=target_path,
        exact=getattr(args, "exact", False),
        max_results=getattr(args, "limit", 20),
    )

    if getattr(args, "copy", False):
        from cephalo.utils.clipboard_utils import set_clipboard_text
        if args.json:
            set_clipboard_text(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False))
        else:
            set_clipboard_text("\n\n".join([r.to_markdown(base_dir=indexer.root_dir) for r in results]))
        if not args.json:
            print("[+] Symbol definitions copied to clipboard.")

    if getattr(args, "json", False):
        print(json.dumps({
            "query": symbol,
            "exact": getattr(args, "exact", False),
            "target": str(indexer.root_dir),
            "count": len(results),
            "definitions": [r.to_dict() for r in results],
        }, indent=2, ensure_ascii=False))
        sys.stdout.flush()
        return

    print(f"\nCephalo AST Symbol Search: '{symbol}' (Matches: {len(results)})")
    if target_path:
        print(f"Target Path:    {target_path}")
    print("-" * 70)
    if not results:
        print(f"No symbol definitions matching '{symbol}' found.")
    else:
        for r in results:
            print(r.to_markdown(base_dir=indexer.root_dir))
    print("-" * 70)
    sys.stdout.flush()


def cmd_record(args) -> None:
    """Sanitizes, embeds, and records a new prompt/decision into LanceDB and prompts.jsonl."""
    raw_text = resolve_cli_input(
        args,
        field_name="text",
        allow_clip=True,
        allow_stdin=True,
        error_message="Error: No text provided. Provide text as argument, pipe via stdin ('cat file | cephalo record'), or use --clip.",
    )

    tags = getattr(args, "tags", None)
    supersedes = getattr(args, "supersedes", None)
    relates_to = getattr(args, "relates_to", None)

    pipeline = get_pipeline(table_name=args.table)
    record = pipeline.ingest_prompt(
        raw_text=raw_text,
        category=args.category,
        source=args.source,
        intent=args.intent,
        tags=tags,
        supersedes=supersedes,
        relates_to=relates_to,
        sync_to_jsonl=True,
    )

    if args.json:
        clean_record = {k: v for k, v in record.items() if k != "vector"}
        print(json.dumps(clean_record, indent=2, ensure_ascii=False))
        return

    print(f"[+] Memory Recorded & Indexed [{record['id']}]:")
    print(f"    Category:   {record['category']}")
    if record.get("tags"):
        print(f"    Tags:       {' '.join(['#' + t for t in record['tags']])}")
    if record.get("supersedes"):
        print(f"    Supersedes: {record['supersedes']}")
    if record.get("superseded_records"):
        print(f"    Auto-Superseded: {', '.join(record['superseded_records'])}")
    if record.get("relates_to"):
        print(f"    Relates To: {', '.join(record['relates_to'])}")
    print(f"    Sanitized:  {record['content']}")
    print(f"    Model:      {record['embedding_model']} (dim={record['dimension']})")
    print(f"    Table:      {pipeline.store.table_name}")


def cmd_sync(args) -> None:
    """Syncs unindexed entries from prompts.jsonl into LanceDB."""
    pipeline = get_pipeline(table_name=args.table)
    inserted, existing = pipeline.sync_from_jsonl(jsonl_path=Path(args.file))

    if args.json:
        print(json.dumps({
            "inserted": inserted,
            "already_indexed": existing,
            "total": pipeline.store.count(),
        }, indent=2))
        return

    print(f"[+] Sync Complete: {inserted} new records inserted ({existing} already indexed).")
    print(f"[+] Total table records: {pipeline.store.count()}")



def cmd_harvest(args) -> None:
    """Scans conversation transcripts and harvests preferences/critiques."""
    from cephalo.learning.auto_harvest import run_standalone_harvest
    run_standalone_harvest(transcript_path=args.transcript)


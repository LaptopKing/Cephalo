#!/usr/bin/env python3
"""
Cephalo - Unified Agent & User Memory Interface (brain.py)
==========================================================
Universal CLI entrypoint for humans and AI agents (Antigravity, Claude Code, Codex, Cursor).
- Sanitizes all inputs automatically via multi-tier local filter.
- Performs hybrid semantic (Qwen 1024d) + BM25 keyword search in LanceDB.
- Appends and tracks entries in prompts.jsonl and USER_PROFILE.md.
- Outputs human-readable markdown tables or machine-readable JSON (--json).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Force UTF-8 on Windows terminal
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Base Paths
PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
ROOT_DIR = SRC_DIR.parent
BASE_DIR = ROOT_DIR

for p in (str(ROOT_DIR), str(SRC_DIR), str(PACKAGE_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

DATA_DIR = ROOT_DIR / "data"
PROMPTS_FILE = DATA_DIR / "prompts.jsonl"
DEFAULT_LANCEDB_DIR = DATA_DIR / "lancedb"
PROFILE_FILE = ROOT_DIR / "USER_PROFILE.md"


def get_pipeline(table_name: Optional[str] = None):
    """Lazy loader for EmbeddingPipeline to keep light commands (status, profile) sub-second."""
    from cephalo.core.embedding_pipeline import EmbeddingPipeline, create_embedder
    embedder = create_embedder(mode="local")
    return EmbeddingPipeline(embedder=embedder, db_path=DEFAULT_LANCEDB_DIR, table_name=table_name)


def parse_profile_sections(content: str) -> List[Dict[str, Any]]:
    """Splits USER_PROFILE.md into markdown sections delineated by '## '."""
    sections = []
    current_title = "Preamble"
    current_lines: List[str] = []

    for line in content.splitlines():
        if line.startswith("## "):
            if current_lines:
                sec_text = "\n".join(current_lines).strip()
                sections.append({
                    "title": current_title,
                    "content": sec_text,
                    "tokens_est": round(len(sec_text) / 3.8)
                })
            current_title = line.lstrip("#").strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sec_text = "\n".join(current_lines).strip()
        sections.append({
            "title": current_title,
            "content": sec_text,
            "tokens_est": round(len(sec_text) / 3.8)
        })
    return sections


def cmd_profile(args) -> None:
    """Reads or extracts sections from USER_PROFILE.md with token-efficient filters."""
    if not PROFILE_FILE.exists():
        if args.json:
            print(json.dumps({"error": "USER_PROFILE.md not found"}, indent=2))
        else:
            print("Error: USER_PROFILE.md not found.")
        return

    content = PROFILE_FILE.read_text(encoding="utf-8")
    sections = parse_profile_sections(content)

    if getattr(args, "list_sections", False):
        if args.json:
            sec_meta = [{"title": s["title"], "tokens_est": s["tokens_est"]} for s in sections]
            print(json.dumps({"total_sections": len(sec_meta), "sections": sec_meta}, indent=2, ensure_ascii=False))
        else:
            print(f"Available Sections in USER_PROFILE.md ({len(sections)} sections):")
            print("-" * 65)
            for idx, s in enumerate(sections, 1):
                print(f"  [{idx:02d}] {s['title']} (~{s['tokens_est']} tokens)")
            print("\nTip: Retrieve a specific section via `cephalo profile --section <name|index>`")
        return

    req_section = getattr(args, "section", None)
    if req_section:
        req_clean = req_section.strip().lower()
        matched = None
        if req_clean.isdigit():
            idx = int(req_clean)
            if 1 <= idx <= len(sections):
                matched = sections[idx - 1]
        if not matched:
            for s in sections:
                if req_clean in s["title"].lower():
                    matched = s
                    break

        if not matched:
            avail = [s["title"] for s in sections]
            if args.json:
                print(json.dumps({"error": f"Section '{req_section}' not found", "available_sections": avail}, indent=2))
            else:
                print(f"Error: Section '{req_section}' not found in USER_PROFILE.md.")
                print(f"Available sections: {', '.join(avail[:6])}...")
            return

        content = matched["content"]
        if getattr(args, "copy", False):
            from cephalo.utils.clipboard_utils import set_clipboard_text
            set_clipboard_text(content)
            if not args.json:
                print(f"[+] Profile section '{matched['title']}' copied to clipboard.")

        if args.json:
            print(json.dumps({
                "section": matched["title"],
                "tokens_est": matched["tokens_est"],
                "content": content
            }, indent=2, ensure_ascii=False))
        else:
            print(content)
        return

    # Default: full profile
    if getattr(args, "copy", False):
        from cephalo.utils.clipboard_utils import set_clipboard_text
        set_clipboard_text(content)
        if not args.json:
            print("[+] Profile copied to clipboard.")

    if args.json:
        print(json.dumps({
            "profile_path": str(PROFILE_FILE),
            "tokens_est": round(len(content) / 3.8),
            "content": content
        }, indent=2, ensure_ascii=False))
    else:
        print(content)


def get_system_status() -> Dict[str, Any]:
    """Collects system health, LanceDB table stats, and prompt log counts as pure data."""
    # Count prompts.jsonl
    prompt_count = 0
    recent_prompts = []
    if PROMPTS_FILE.exists():
        with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    prompt_count += 1
                    try:
                        recent_prompts.append(json.loads(line))
                    except Exception:
                        pass
        recent_prompts = recent_prompts[-3:]

    # Check LanceDB tables quickly without loading embedding models
    lancedb_exists = DEFAULT_LANCEDB_DIR.exists()
    table_stats = {}
    if lancedb_exists:
        try:
            import lancedb
            db = lancedb.connect(str(DEFAULT_LANCEDB_DIR))
            raw_tables = db.list_tables()
            table_names = list(getattr(raw_tables, "tables", raw_tables))
            for tname in table_names:
                tbl = db.open_table(tname)
                table_stats[tname] = tbl.count_rows()
        except Exception as e:
            table_stats["error"] = str(e)

    return {
        "working_directory": str(BASE_DIR),
        "prompts_file": str(PROMPTS_FILE),
        "prompts_logged": prompt_count,
        "profile_file": str(PROFILE_FILE),
        "profile_exists": PROFILE_FILE.exists(),
        "lancedb_dir": str(DEFAULT_LANCEDB_DIR),
        "lancedb_tables": table_stats,
        "recent_prompts": recent_prompts,
    }


def cmd_status(args) -> None:
    """Prints system health, LanceDB table status, and prompt counts."""
    status_data = get_system_status()

    if getattr(args, "json", False):
        print(json.dumps(status_data, indent=2, ensure_ascii=False))
        return

    prompt_count = status_data["prompts_logged"]
    table_stats = status_data["lancedb_tables"]
    recent_prompts = status_data["recent_prompts"]

    print("=" * 65)
    print("  CEPHALO (SECOND BRAIN) - STATUS")
    print("=" * 65)
    print(f"Working Directory:    {BASE_DIR}")
    print(f"Prompt Log:           {PROMPTS_FILE} ({prompt_count} records)")
    print(f"Profile:              {PROFILE_FILE} ({'Found' if PROFILE_FILE.exists() else 'Missing'})")
    print(f"LanceDB Directory:    {DEFAULT_LANCEDB_DIR}")
    for tname, count in table_stats.items():
        print(f"  • Table '{tname}': {count} vectors")
    print("-" * 65)
    print("Recent Prompts Logged:")
    for p in recent_prompts:
        preview = p.get("content", "")[:75] + ("..." if len(p.get("content", "")) > 75 else "")
        print(f"  [{p.get('id', 'N/A')}] ({p.get('category', 'general')}): {preview}")
    print("=" * 65)


def resolve_cli_input(
    args: Any,
    field_name: str = "text",
    allow_clip: bool = False,
    allow_stdin: bool = True,
    error_message: Optional[str] = None,
) -> str:
    """Consistently resolves CLI input from argument, clipboard (--clip), or piped stdin."""
    val = getattr(args, field_name, None)

    if allow_clip and getattr(args, "clip", False):
        from cephalo.utils.clipboard_utils import get_clipboard_text
        clip_content = get_clipboard_text()
        if clip_content:
            return clip_content
        print("Error: System clipboard is empty.")
        sys.exit(1)

    if allow_stdin and (not val or val == "-"):
        if not sys.stdin.isatty():
            val = sys.stdin.read().strip()

    if not val:
        default_err = f"Error: No {field_name} provided. Provide via argument or pipe via stdin."
        print(error_message or default_err)
        sys.exit(1)

    return val


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

def _handle_specialty_list(mgr, args) -> None:
    items = mgr.list_specialties(project=args.project)
    if getattr(args, "json", False):
        print(json.dumps(items, indent=2, ensure_ascii=False))
        return
    if not items:
        print(f"No specialties found{f' for project {args.project}' if args.project else ''}.")
        return
    print("=" * 65)
    print("  PERSONAL SECOND BRAIN - ACTIVE SPECIALTIES")
    print("=" * 65)
    for s in items:
        print(f"  • [{s.get('project')}] {s.get('name')} (id: {s.get('id')})")
        if s.get("github_repos"):
            print(f"    GitHub Repos: {len(s.get('github_repos'))} curated")
        if s.get("key_takeaways"):
            print(f"    Takeaways:    {len(s.get('key_takeaways'))} core principles")
    print("=" * 65)


def _handle_specialty_read(mgr, args) -> None:
    data = mgr.get_specialty(args.name, project=args.project)
    if not data:
        if getattr(args, "json", False):
            print(json.dumps({"error": f"Specialty '{args.name}' not found"}, indent=2))
        else:
            print(f"Error: Specialty '{args.name}' not found.")
        return
    if getattr(args, "json", False):
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    print(data["knowledge_content"])


def _handle_specialty_create(mgr, args) -> None:
    repos = []
    if getattr(args, "repos", None):
        try:
            repos = json.loads(args.repos)
        except Exception:
            pass
    takeaways = [t.strip() for t in args.takeaways.split(";")] if getattr(args, "takeaways", None) else []
    prefs = [p.strip() for p in args.preferences.split(",")] if getattr(args, "preferences", None) else []
    fund = args.fundamentals or f"Core verified fundamentals for {args.name}."

    result = mgr.create_specialty(
        name=args.name,
        project=args.project,
        fundamentals=fund,
        github_repos=repos,
        key_takeaways=takeaways,
        user_preferences=prefs,
        sync_to_vector_db=True,
    )
    if getattr(args, "json", False):
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print(f"[+] Created and Indexed Specialty: '{args.name}' under Project: '{args.project}'")
    print(f"    Manifest:  {result['path']}\\manifest.json")
    print(f"    Knowledge: {result['knowledge_path']}")


def _handle_specialty_edit(mgr, args) -> None:
    res = mgr.edit_specialty(
        name=args.name,
        project=args.project,
        fundamentals=getattr(args, "fundamentals", None),
        notes=getattr(args, "notes", None),
    )
    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return
    print(f"[+] Updated Specialty '{args.name}'.")


def _handle_specialty_delete(mgr, args) -> None:
    confirmed = args.confirm
    if not confirmed and sys.stdin.isatty():
        ans = input(f"Are you sure you want to delete specialty '{args.name}'? Type 'yes' to confirm: ")
        confirmed = (ans.strip().lower() == "yes")

    try:
        mgr.delete_specialty(args.name, project=args.project, confirmed=confirmed)
        if getattr(args, "json", False):
            print(json.dumps({"deleted": True, "specialty": args.name}, indent=2))
        else:
            print(f"[+] Successfully deleted specialty '{args.name}'.")
    except PermissionError as pe:
        if getattr(args, "json", False):
            print(json.dumps({"error": str(pe)}, indent=2))
        else:
            print(f"Error: {pe}")


def _handle_specialty_auto_create(mgr, args) -> None:
    prefs = [p.strip() for p in args.preferences.split(",")] if getattr(args, "preferences", None) else None
    res = mgr.auto_create_specialty(topic=args.topic, project=args.project, user_preferences=prefs)
    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return
    if res.get("already_exists"):
        print(f"[i] Specialty '{res['manifest'].get('name')}' already exists in project '{res['manifest'].get('project')}'.")
        print(f"    Path: {res['path']}")
    else:
        print(f"[+] Autonomously Synthesized & Created Specialty: '{res['manifest'].get('name')}' under Project: '{res['manifest'].get('project')}'")
        print(f"    Manifest:  {res['path']}\\manifest.json")
        print(f"    Knowledge: {res['knowledge_path']}")


def _handle_specialty_discover(mgr, args) -> None:
    content = getattr(args, "text", None) or ""
    if getattr(args, "file", None):
        fpath = Path(args.file)
        if fpath.exists():
            content += "\n" + fpath.read_text(encoding="utf-8")
    if not content.strip():
        print("Error: Provide --text or --file to auto-discover technologies.")
        return
    results = mgr.auto_discover_and_create(text_or_items=content, project=args.project)
    if getattr(args, "json", False):
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return
    print(f"[+] Auto-Discovery Complete: Processed {len(results)} technologies.")
    for r in results:
        status = "Created" if r.get("created") else "Already Exists"
        print(f"  • [{status}] {r['manifest'].get('name')} ({r['manifest'].get('slug')}) in '{r['manifest'].get('project')}'")


def _handle_specialty_research(mgr, args) -> None:
    res = mgr.research_and_create_specialty(
        topic=args.topic,
        project=args.project,
        subtopics=getattr(args, "subtopics", None),
        notes=getattr(args, "notes", None),
        sync_to_vector_db=True,
    )
    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return
    synth = res["synthesized"]
    print("=" * 70)
    print(f"[+] Researched & Created Specialty: '{synth['name']}' in Project: '{synth['project']}'")
    print("=" * 70)
    print(f"Manifest:   {res['path']}\\manifest.json")
    print(f"Knowledge:  {res['knowledge_path']}")
    print(f"Subtopics:  {', '.join(synth.get('subtopics', []))}")


def cmd_specialty(args) -> None:
    """Handles CRUD operations for the Specialties domain layer."""
    from cephalo.learning.specialties_manager import SpecialtiesManager
    mgr = SpecialtiesManager()
    action = getattr(args, "specialty_action", None) or "list"

    handlers = {
        "list": _handle_specialty_list,
        "read": _handle_specialty_read,
        "create": _handle_specialty_create,
        "edit": _handle_specialty_edit,
        "delete": _handle_specialty_delete,
        "auto-create": _handle_specialty_auto_create,
        "auto": _handle_specialty_auto_create,
        "auto-discover": _handle_specialty_discover,
        "discover": _handle_specialty_discover,
        "research": _handle_specialty_research,
    }

    handler = handlers.get(action)
    if handler:
        handler(mgr, args)
    else:
        print(f"Unknown specialty action: {action}")
        print(f"Repositories ({len(synth.get('github_repos', []))}):")
        for r in synth.get("github_repos", []):
            print(f"  * {r['name']} (Stars: {r['stars']}): {r['description'][:80]}...")
        print("=" * 70)


def cmd_research(args) -> None:
    """Executes deep research on a topic, finding best practices, industry standards, and top GitHub repos."""
    from cephalo.research.research_engine import DeepResearchEngine
    engine = DeepResearchEngine()
    synth = engine.synthesize_specialty(
        topic=args.topic,
        project=args.project,
        subtopics=getattr(args, "subtopics", None),
        custom_notes=getattr(args, "notes", None),
    )

    if getattr(args, "create", False):
        from cephalo.learning.specialties_manager import SpecialtiesManager
        sm = SpecialtiesManager()
        created = sm.create_specialty(
            name=synth["name"],
            project=synth["project"],
            fundamentals=synth["fundamentals"],
            github_repos=synth["github_repos"],
            key_takeaways=synth["key_takeaways"],
            user_preferences=synth["user_preferences"],
            tags=synth["tags"],
            slug=synth["slug"],
            sync_to_vector_db=True,
        )
        if args.json:
            print(json.dumps({**synth, "created": True, "path": created["path"]}, indent=2, ensure_ascii=False))
            return
        print(f"[+] Researched and registered specialty '{synth['name']}' at {created['path']}")
        return

    if args.json:
        print(json.dumps(synth, indent=2, ensure_ascii=False))
        return

    print("=" * 70)
    print(f"  CEPHALO DEEP RESEARCH REPORT: {synth['name']}")
    print("=" * 70)
    print(f"Project:     {synth['project']}")
    print(f"Slug:        {synth['slug']}")
    print(f"Subtopics:   {', '.join(synth.get('subtopics', []))}")
    print(f"Repositories ({len(synth.get('github_repos', []))}):")
    for r in synth.get("github_repos", []):
        print(f"  * {r['name']} (Stars: {r['stars']}): {r['description'][:80]}...")
    print(f"Key Takeaways ({len(synth.get('key_takeaways', []))}):")
    for t in synth.get("key_takeaways", [])[:5]:
        print(f"  - {t}")
    print("=" * 70)


def cmd_email(args) -> None:
    """Delegates to EmailClient."""
    from cephalo.services.email_client import EmailClient
    client = EmailClient()
    action = getattr(args, "email_action", None) or "status"

    if action == "status":
        status = client.get_status()
        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print("=" * 60)
            print("  SECOND BRAIN - EMAIL CLIENT STATUS")
            print("=" * 60)
            print(f"Status:          {'CONFIGURED (Ready)' if status['configured'] else 'NOT CONFIGURED (Missing SMTP credentials)'}")
            print(f"SMTP Host:       {status['smtp_host']}:{status['smtp_port']}")
            print(f"Account:         {status['smtp_user_masked']}")
            print(f"Password:        {'Set (' + str(status['smtp_pass_length']) + ' chars)' if status['smtp_pass_set'] else 'Missing'}")
            print(f"TLS Active:      {status['use_tls']}")
            print(f".env File:       {'Found' if status['env_file_found'] else 'Not found (Create .env from .env.example)'}")
            print("=" * 60)

    elif action == "send":
        body = args.body or ""
        if getattr(args, "body_file", None):
            bf = Path(args.body_file)
            if bf.exists():
                body = bf.read_text(encoding="utf-8")
            else:
                print(f"Error: Body file '{args.body_file}' not found.")
                sys.exit(1)

        confirmed = args.confirm
        if not confirmed and sys.stdin.isatty():
            ans = input(f"Send email to '{args.to}'? Type 'yes' to confirm: ")
            confirmed = (ans.strip().lower() == "yes")

        try:
            res = client.send_email(
                to_address=args.to,
                subject=args.subject,
                body=body,
                confirmed=confirmed,
            )
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print(f"[+] Email successfully sent to '{args.to}'.")
        except Exception as e:
            if args.json:
                print(json.dumps({"error": str(e)}, indent=2))
            else:
                print(f"Error: {e}")



def cmd_web(args) -> None:
    """Searches the live web via WebSearchEngine with Google-style SERP, Quick Summary, and Social Blocks."""
    from cephalo.research.web_search import WebSearchEngine
    engine = WebSearchEngine()
    include_social = not getattr(args, "no_social", False)
    serp = engine.search_serp(args.query, max_results=args.limit, include_social=include_social)

    # 1. Output machine-readable JSON if requested
    if args.json:
        print(json.dumps(serp.to_dict(), indent=2, ensure_ascii=False))
        return

    # 2. Output clean native Markdown SERP card if requested
    if getattr(args, "markdown", False):
        print(serp.to_markdown())
        return

    # 2. Render Google-Style SERP via rich or elegant terminal layout
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        console = Console()

        console.print(f"\n[bold blue]✦ Cephalo Search[/bold blue] [dim]•[/dim] [bold]{serp.query}[/bold] [dim]({len(serp.organic_results) + len(serp.social_blocks)} results in {serp.execution_time_seconds:.2f}s via {serp.engine_used})[/dim]")

        # Quick Summary Box (AI Overview)
        summary_body = f"[bold]{serp.quick_summary}[/bold]\n"
        if serp.key_takeaways:
            summary_body += "\n[dim]Key Takeaways:[/dim]\n"
            for t in serp.key_takeaways:
                summary_body += f" [green]•[/green] {t}\n"
        if serp.citations:
            citation_str = " ".join([r"[" + c.get('domain', 'source') + r"]" for c in serp.citations])
            summary_body += f"\n[dim]Key Sources:[/dim] {citation_str}"

        console.print(Panel(
            summary_body.strip(),
            title="[bold blue]Quick Summary[/bold blue] (AI Overview)",
            border_style="blue",
            padding=(1, 2),
        ))

        # Organic Web Results
        console.print("\n[bold]Web Results[/bold]")
        for idx, r in enumerate(serp.organic_results, 1):
            clean_snip = re.sub(r'```[\s\S]*?```', '', r.snippet)
            clean_snip = re.sub(r'\{/\*[\s\S]*?\*/\}', '', clean_snip)
            clean_snip = re.sub(r'\s+', ' ', clean_snip).strip()
            if len(clean_snip) > 220:
                clean_snip = clean_snip[:220].rsplit(' ', 1)[0] + "..."

            console.print(f"  [bold cyan]{idx}. {r.title}[/bold cyan]")
            console.print(f"     [dim]{r.display_url or r.url}[/dim]")
            if clean_snip:
                console.print(f"     {clean_snip}")
            console.print()

        # Social & Community Blocks
        if serp.social_blocks:
            console.print("[bold]Discussions & Community Highlights[/bold]")
            social_table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 1))
            social_table.add_column("Platform", width=14)
            social_table.add_column("Title / Discussion", style="bold")
            social_table.add_column("URL", style="dim")

            for s in serp.social_blocks:
                p_name = (s.social_type or "Community").capitalize()
                social_table.add_row(f"[{p_name}]", s.title, s.url)
            console.print(social_table)

    except Exception:
        # Fallback to standard clean terminal output if rich fails
        print("=" * 65)
        print(f"  CEPHALO SEARCH: '{serp.query}' ({serp.engine_used})")
        print("=" * 65)
        print("\n--- QUICK SUMMARY (AI OVERVIEW) ---")
        print(serp.quick_summary)
        if serp.key_takeaways:
            print("\nKey Takeaways:")
            for t in serp.key_takeaways:
                print(f"  • {t}")
        print("\n--- WEB RESULTS ---")
        for idx, r in enumerate(serp.organic_results, 1):
            print(f"[{idx}] {r.title}")
            print(f"    URL: {r.url}")
            print(f"    {r.snippet}\n")
        if serp.social_blocks:
            print("--- DISCUSSIONS & COMMUNITY ---")
            for s in serp.social_blocks:
                print(f"  [{s.social_type or 'Community'}] {s.title} ({s.url})")
        print("=" * 65)

    # 3. HTML artifact generation & browser preview
    html_flag = getattr(args, "html", False)
    open_flag = getattr(args, "open", False)
    if html_flag or open_flag:
        slug = re.sub(r'[^a-z0-9]+', '-', args.query.lower()).strip('-')[:40] or "search"
        html_path = DATA_DIR / "serp_cache" / f"{slug}.html"
        engine.render_serp_html(serp, output_path=html_path, standalone=True)
        print(f"\n[+] Interactive SERP generated: {html_path}")
        if open_flag:
            import webbrowser
            webbrowser.open(str(html_path.resolve()))

    # 4. Record to LanceDB if requested
    if getattr(args, "record", False) and (serp.organic_results or serp.quick_summary):
        combined = f"Web Search for '{args.query}':\nSummary: {serp.quick_summary}\n\nTop Results:\n"
        combined += "\n".join([f"- {r.title} ({r.url}): {r.snippet}" for r in serp.organic_results[:3]])
        pipeline = get_pipeline(table_name=args.table)
        rec = pipeline.record(text=combined, category=args.category, source="web_search", intent=args.query)
        if not args.json:
            print(f"[+] Search results sanitized & indexed into LanceDB [{rec.get('id')}].")


def cmd_fetch(args) -> None:
    """Fetches clean text from a URL (static, dynamic Chromium, or YouTube) and optionally records it."""
    from cephalo.research.web_search import WebSearchEngine
    engine = WebSearchEngine()
    display_title = f"CEPHALO WEB FETCH: {args.url}"
    try:
        if getattr(args, "youtube", False) or engine.is_youtube_url(args.url):
            yt_res = engine.fetch_youtube_transcript(args.url, max_chars=args.max_chars)
            page_text = yt_res["content"]
            display_title = f"CEPHALO YOUTUBE TRANSCRIPT: {yt_res['url']} ({yt_res['language']})"
        else:
            page_text = engine.fetch_url(
                args.url,
                max_chars=args.max_chars,
                dynamic=getattr(args, "dynamic", False),
                headless=not getattr(args, "headed", False),
                persistent=getattr(args, "persistent", False),
            )
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print(f"Error fetching URL: {e}")
        return

    # Optional pattern transformation
    pattern_name = getattr(args, "pattern", None)
    if pattern_name and page_text:
        try:
            from cephalo.core.patterns_manager import PatternsManager
            pm = PatternsManager()
            page_text = pm.assemble_prompt(pattern_name, page_text)
            display_title += f" [Pattern: {pattern_name}]"
        except Exception as pe:
            print(f"Warning: Pattern assembly failed: {pe}")

    if getattr(args, "copy", False) and page_text:
        from cephalo.utils.clipboard_utils import set_clipboard_text
        set_clipboard_text(page_text)
        if not args.json:
            print("[+] Content copied to clipboard.")

    if args.json:
        print(json.dumps({"url": args.url, "content": page_text}, indent=2, ensure_ascii=False))
    else:
        print("=" * 65)
        print(f"  {display_title}")
        print("=" * 65)
        preview = page_text[:800] + ("\n... [Truncated for display]" if len(page_text) > 800 else "")
        print(preview)
        print("=" * 65)

    if getattr(args, "record", False) and page_text:
        pipeline = get_pipeline(table_name=args.table)
        summary = f"Web Content from {args.url}:\n\n{page_text}"
        rec = pipeline.record(text=summary, category=args.category, source="web_fetch", intent=f"Fetched {args.url}")
        if not args.json:
            print(f"[+] Page content sanitized & indexed into LanceDB [{rec.get('id')}].")


def cmd_learn(args) -> None:
    """Executes continuous learning across workspaces, stacks, and episodic memory."""
    from cephalo.learning.continuous_learner import ContinuousLearner
    learner = ContinuousLearner()
    action = getattr(args, "learn_action", None) or "run"

    if action == "run":
        report = learner.run_cycle()
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print("=" * 65)
            print("  CEPHALO CONTINUOUS LEARNING CYCLE")
            print("=" * 65)
            print(f"Timestamp:        {report['timestamp']}")
            print(f"Cycle Duration:   {report['duration_seconds']}s")
            print(f"Projects Scanned: {report['scanned_projects_count']}")
            print(f"Technologies:     {len(report['discovered_technologies'])} discovered")
            if report['newly_synthesized_specialties']:
                print(f"New Specialties:  {', '.join(report['newly_synthesized_specialties'])}")
            else:
                print("New Specialties:  All current stacks covered.")
            print(f"Consolidated:     {len(report['consolidated_insights'])} high-level insights")
            print("=" * 65)
    elif action == "status":
        state = learner.state
        if args.json:
            print(json.dumps(state, indent=2, ensure_ascii=False))
        else:
            print("=" * 65)
            print("  CEPHALO CONTINUOUS LEARNING STATUS")
            print("=" * 65)
            print(f"Total Cycles Run:     {state.get('total_cycles_run', 0)}")
            print(f"Last Cycle:           {state.get('last_cycle_timestamp', 'Never')}")
            print(f"Tracked Projects:     {len(state.get('tracked_projects', {}))}")
            for pname, techs in state.get('tracked_projects', {}).items():
                print(f"  • {pname}: {', '.join(techs) if techs else 'no standard manifests'}")
            print(f"Discovered Stacks:    {len(state.get('discovered_technologies', []))}")
            print(f"Synthesized Modules:  {len(state.get('synthesized_specialties', []))}")
            print("=" * 65)
    elif action == "watch":
        learner.watch(interval_seconds=getattr(args, "interval", 120))


def cmd_mcp(args) -> None:
    """Launches native Model Context Protocol (MCP) stdio server."""
    from cephalo.services.mcp_server import run_stdio_server
    run_stdio_server()


def cmd_daemon(args) -> None:
    """Manages the always-on background daemon."""
    from cephalo.services.cephalo_daemon import (
        CephaloDaemon,
        get_daemon_status,
        start_daemon_detached,
        stop_daemon,
        install_windows_task,
        uninstall_windows_task,
    )
    action = getattr(args, "daemon_action", None) or "status"
    interval = getattr(args, "interval", 90)

    if action == "run":
        daemon = CephaloDaemon(interval_seconds=interval)
        daemon.run_foreground()
    elif action == "start":
        start_daemon_detached(interval=interval)
    elif action == "stop":
        stop_daemon()
    elif action == "status":
        info = get_daemon_status()
        if args.json:
            print(json.dumps(info, indent=2, ensure_ascii=False))
        else:
            print("=" * 65)
            print("  CEPHALO ALWAYS-ON DAEMON STATUS")
            print("=" * 65)
            print(f"Status:        {'RUNNING (Active)' if info['running'] else 'STOPPED'}")
            if info["pid"]:
                print(f"Process PID:   {info['pid']}")
            detail = info.get("detail", {})
            if detail:
                print(f"Last Heartbeat: {detail.get('last_heartbeat', 'N/A')}")
                print(f"Interval:       {detail.get('interval_seconds', 90)}s")
                last_c = detail.get("last_cycle", {})
                if "learning" in last_c:
                    l = last_c["learning"]
                    print(f"Last Learning:  {l.get('scanned_projects_count', 0)} projects, {len(l.get('discovered_technologies', []))} stacks")
                if "git_pushed" in last_c:
                    print(f"GitHub Sync:    {'Pushed' if last_c['git_pushed'] else 'Up to date'}")
            print("=" * 65)
    elif action == "install-task":
        install_windows_task()
    elif action == "uninstall-task":
        uninstall_windows_task()


def maybe_auto_learn() -> None:
    if '-h' in sys.argv or '--help' in sys.argv:
        return
    """Opportunistic continuous learning trigger.
    Runs a fast sub-second learning cycle if more than 10 minutes have elapsed since the last cycle.
    Guarantees continuous learning across all agent harnesses without requiring manual commands.
    """
    try:
        from cephalo.learning.continuous_learner import ContinuousLearner
        learner = ContinuousLearner()
        last_str = learner.state.get("last_cycle_timestamp")
        should_run = False
        if not last_str:
            should_run = True
        else:
            try:
                last_dt = datetime.datetime.fromisoformat(last_str)
                elapsed = (datetime.datetime.now().astimezone() - last_dt).total_seconds()
                if elapsed > 600:  # 10 minutes
                    should_run = True
            except Exception:
                should_run = True

        if should_run:
            learner.run_cycle()
    except Exception:
        pass


def cmd_pattern(args) -> None:
    """Manages cognitive execution patterns ('Reflexes')."""
    from cephalo.core.patterns_manager import PatternsManager
    pm = PatternsManager()
    action = getattr(args, "pattern_action", None) or "list"

    if action == "list":
        items = pm.list_patterns()
        if getattr(args, "copy", False):
            from cephalo.utils.clipboard_utils import set_clipboard_text
            set_clipboard_text(json.dumps(items, indent=2))
            if not args.json:
                print("[+] Pattern list copied to clipboard.")
        if args.json:
            print(json.dumps(items, indent=2, ensure_ascii=False))
            return
        print("=" * 65)
        print("  CEPHALO COGNITIVE PATTERNS (REFLEXES)")
        print("=" * 65)
        for p in items:
            tier_badge = "[CORE]" if p["tier"] == "core" else "[CUSTOM]"
            print(f"  • {p['name']:<22} {tier_badge} {p['summary']}")
        print("=" * 65)

    elif action == "show":
        p = pm.get_pattern(args.name)
        if not p:
            if args.json:
                print(json.dumps({"error": f"Pattern '{args.name}' not found"}, indent=2))
            else:
                print(f"Error: Pattern '{args.name}' not found.")
            return
        if getattr(args, "copy", False):
            from cephalo.utils.clipboard_utils import set_clipboard_text
            set_clipboard_text(p["content"])
            if not args.json:
                print("[+] Pattern prompt copied to clipboard.")
        if args.json:
            print(json.dumps(p, indent=2, ensure_ascii=False))
            return
        print(p["content"])

    elif action == "run":
        input_text = getattr(args, "text", None)
        if getattr(args, "clip", False):
            from cephalo.utils.clipboard_utils import get_clipboard_text
            input_text = get_clipboard_text()
        elif (not input_text or input_text == "-") and not sys.stdin.isatty():
            input_text = sys.stdin.read().strip()

        if not input_text:
            print("Error: No input text provided. Pass text as argument, pipe via stdin ('cat file | cephalo pattern run <name>'), or use --clip.")
            sys.exit(1)

        context_text = None
        if getattr(args, "context", None):
            from cephalo.core.context_manager import ContextManager
            cm = ContextManager()
            context_text = cm.export_context(specialty=args.context)

        try:
            full_prompt = pm.assemble_prompt(args.name, input_text, context_text=context_text)
        except Exception as e:
            print(f"Error assembling pattern: {e}")
            sys.exit(1)

        if getattr(args, "copy", False):
            from cephalo.utils.clipboard_utils import set_clipboard_text
            set_clipboard_text(full_prompt)
            if not args.json:
                print("[+] Assembled prompt copied to clipboard.")

        if getattr(args, "record", False):
            pipeline = get_pipeline(table_name=args.table)
            rec = pipeline.record(
                text=full_prompt,
                category=args.category,
                source="pattern_run",
                intent=f"Executed pattern {args.name}",
            )
            if not args.json:
                print(f"[+] Pattern output sanitized & indexed into LanceDB [{rec.get('id')}].")

        if args.json:
            print(json.dumps({
                "pattern": args.name,
                "input_length": len(input_text),
                "prompt": full_prompt,
            }, indent=2, ensure_ascii=False))
        else:
            print(full_prompt)


def cmd_context(args) -> None:
    """Exports structured context blocks for external LLMs or agents."""
    from cephalo.core.context_manager import ContextManager
    cm = ContextManager()
    action = getattr(args, "context_action", None) or "export"

    if action == "export":
        payload = cm.export_context(
            project=getattr(args, "project", None),
            specialty=getattr(args, "specialty", None),
            include_hardware=not getattr(args, "no_hardware", False),
            include_cinema=getattr(args, "cinema", False),
        )
        if getattr(args, "copy", False):
            from cephalo.utils.clipboard_utils import set_clipboard_text
            set_clipboard_text(payload)
            if not args.json:
                print("[+] Context payload copied to clipboard.")

        if args.json:
            print(json.dumps({"context": payload}, indent=2, ensure_ascii=False))
        else:
            print(payload)


def cmd_wiki(args) -> None:
    """Manages the sovereign local DeepWiki engine."""
    from cephalo.research.wiki_generator import WikiGenerator
    wg = WikiGenerator()
    action = getattr(args, "wiki_action", None) or "generate"

    if action == "generate":
        files = wg.generate_all()
        if getattr(args, "copy", False):
            from cephalo.utils.clipboard_utils import set_clipboard_text
            summary_text = "\n".join([f"- {f.name}" for f in files])
            set_clipboard_text(summary_text)
            if not args.json:
                print("[+] Wiki file list copied to clipboard.")

        if args.json:
            print(json.dumps({
                "status": "success",
                "output_dir": str(wg.output_dir),
                "generated_files": [f.name for f in files],
            }, indent=2))
        else:
            print("=" * 65)
            print("  CEPHALO SOVEREIGN DEEPWIKI GENERATED")
            print("=" * 65)
            print(f"Output Directory: {wg.output_dir}")
            for f in files:
                print(f"  • {f.name:<24} ({f.stat().st_size:,} bytes)")
            print("=" * 65)
            print("[+] Open docs/wiki/README.md or run 'cephalo wiki serve' to view.")

    elif action == "serve":
        port = getattr(args, "port", 7433)
        from cephalo.research.wiki_generator import run_deepwiki_server
        run_deepwiki_server(port=port, open_browser=getattr(args, "open", True))




def cmd_webhook(args) -> None:
    """Manages the multi-channel quick capture HTTP webhook and ingress gateway."""
    action = getattr(args, "webhook_action", None) or "status"
    port = getattr(args, "port", 7434)
    host = getattr(args, "host", "127.0.0.1")

    if action == "serve":
        from cephalo.services.webhook_server import WebhookServer
        server = WebhookServer(host=host, port=port, auth_token=getattr(args, "token", None))
        server.start(background=False)

    elif action == "status":
        import urllib.request
        url = f"http://{host}:{port}/health"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if args.json:
                    print(json.dumps(data, indent=2))
                else:
                    print(f"[+] Webhook Gateway is ONLINE at http://{host}:{port}/")
                    print(f"    Service:        {data.get('service')}")
                    print(f"    Prompts Logged: {data.get('prompts_logged')}")
        except Exception:
            if args.json:
                print(json.dumps({"status": "offline", "url": url}, indent=2))
            else:
                print(f"[-] Webhook Gateway is OFFLINE at http://{host}:{port}/")
                print("    Start it with: cephalo webhook serve (or start cephalo daemon)")

    elif action == "send":
        from cephalo.services.webhook_server import send_quick_memory
        text = getattr(args, "text", "")
        cat = getattr(args, "category", "quick_note")
        try:
            res = send_quick_memory(text=text, category=cat, host=host, port=port)
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print(f"[+] Memory Sent via Webhook [{res.get('id', 'N/A')}]:")
                print(f"    Category:  {res.get('category')}")
                print(f"    Sanitized: {res.get('sanitized')}")
        except Exception as e:
            print(f"[-] Error sending memory to webhook: {e}")

def cmd_youtube(args) -> None:
    """Extracts a YouTube video transcript directly, with optional pattern and indexing."""
    from cephalo.research.web_search import WebSearchEngine
    engine = WebSearchEngine()
    try:
        yt_res = engine.fetch_youtube_transcript(args.url)
        content = yt_res["content"]
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print(f"Error extracting YouTube transcript: {e}")
        return

    pattern_name = getattr(args, "pattern", None)
    if pattern_name:
        try:
            from cephalo.core.patterns_manager import PatternsManager
            pm = PatternsManager()
            content = pm.assemble_prompt(pattern_name, content)
        except Exception as pe:
            print(f"Warning: Pattern assembly failed: {pe}")

    if getattr(args, "copy", False):
        from cephalo.utils.clipboard_utils import set_clipboard_text
        set_clipboard_text(content)
        if not args.json:
            print("[+] YouTube transcript copied to clipboard.")

    if args.json:
        out = dict(yt_res)
        out["content"] = content
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print("=" * 65)
        print(f"  CEPHALO YOUTUBE TRANSCRIPT: {yt_res['url']} ({yt_res['language']})")
        print("=" * 65)
        preview = content[:800] + ("\n... [Truncated for display]" if len(content) > 800 else "")
        print(preview)
        print("=" * 65)

    if getattr(args, "record", False) and content:
        pipeline = get_pipeline(table_name=args.table)
        rec = pipeline.record(
            text=f"YouTube Transcript ({yt_res['url']}):\n\n{content}",
            category=args.category,
            source="youtube",
            intent=f"Ingested {yt_res['url']}",
        )
        if not args.json:
            print(f"[+] Transcript sanitized & indexed into LanceDB [{rec.get('id')}].")


def cmd_safeguard(args) -> None:
    """Manages configurable privacy safeguards, blacklists, and security gatekeepers."""
    from cephalo.core.safeguards import (
        add_blacklisted_process,
        add_blacklisted_title,
        is_shielded,
        load_safeguards_config,
        remove_blacklisted_process,
        remove_blacklisted_title,
    )

    action = getattr(args, "safeguard_action", None) or "status"

    if action == "status":
        cfg = load_safeguards_config()
        if args.json:
            print(json.dumps(cfg, indent=2, ensure_ascii=False))
        else:
            print("=" * 65)
            print("  🛡️  CEPHALO PRIVACY SAFEGUARDS & BLACKLIST")
            print("=" * 65)
            print(f"  Enabled:                  {cfg.get('enabled')}")
            print(f"  Pause Fullscreen Video:   {cfg.get('pause_on_fullscreen_video')}")
            print(f"  Blacklisted Processes:    ({len(cfg.get('blacklisted_processes', []))})")
            for p in cfg.get("blacklisted_processes", []):
                print(f"    • {p}")
            print(f"  Blacklisted Window Titles:({len(cfg.get('blacklisted_window_titles', []))})")
            for t in cfg.get("blacklisted_window_titles", []):
                print(f"    • {t}")
            print(f"  Blacklisted Domains:      ({len(cfg.get('blacklisted_domains', []))})")
            for d in cfg.get("blacklisted_domains", []):
                print(f"    • {d}")
            print("=" * 65)

    elif action == "add-proc":
        cfg = add_blacklisted_process(args.name)
        if args.json:
            print(json.dumps({"status": "added", "process": args.name}, indent=2))
        else:
            print(f"[+] Added process '{args.name}' to safeguards blacklist.")

    elif action == "add-title":
        cfg = add_blacklisted_title(args.pattern)
        if args.json:
            print(json.dumps({"status": "added", "pattern": args.pattern}, indent=2))
        else:
            print(f"[+] Added window title pattern '{args.pattern}' to safeguards blacklist.")

    elif action == "remove-proc":
        ok = remove_blacklisted_process(args.name)
        if args.json:
            print(json.dumps({"status": "removed" if ok else "not_found", "process": args.name}, indent=2))
        else:
            print(f"[{'+' if ok else '-'}] Process '{args.name}' {'removed' if ok else 'not found'}.")

    elif action == "remove-title":
        ok = remove_blacklisted_title(args.pattern)
        if args.json:
            print(json.dumps({"status": "removed" if ok else "not_found", "pattern": args.pattern}, indent=2))
        else:
            print(f"[{'+' if ok else '-'}] Window pattern '{args.pattern}' {'removed' if ok else 'not found'}.")

    elif action == "test":
        shielded, reason = is_shielded(window_title=args.title, process_name=getattr(args, "process", ""))
        res = {"shielded": shielded, "reason": reason, "title": args.title, "process": getattr(args, "process", "")}
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            status_tag = "🔴 SHIELDED (BLOCKED)" if shielded else "🟢 ALLOWED (SAFE)"
            print(f"Test Result: {status_tag}")
            if reason:
                print(f"Reason:      {reason}")


def cmd_screen(args) -> None:
    """Manages cross-platform perceptual delta screen capture and visual memory."""
    from cephalo.services.screen_recorder import ScreenMemoryEngine, get_active_window_context

    action = getattr(args, "screen_action", None) or "status"
    engine = ScreenMemoryEngine()

    if action == "snap":
        force = getattr(args, "force", False)
        res = engine.capture_step(force=force)
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            st = res.get("status")
            if st == "captured":
                print(f"[+] Screen Keyframe Captured [{res.get('frame_id')}]:")
                print(f"    Path:    {res.get('path')}")
                print(f"    Delta:   {res.get('delta')} (Threshold exceeded)")
                print(f"    Size:    {res.get('size_kb')} KB (WebP)")
                print(f"    Window:  {res.get('window_title') or 'N/A'}")
                print(f"    Process: {res.get('process_name') or 'N/A'}")
            elif st == "skipped_no_change":
                print(f"[*] Screen Unchanged: delta {res.get('delta')} < threshold {res.get('threshold')}. No disk write.")
            elif st == "shielded":
                print(f"[!] Capture Blocked by Safeguard Shield:")
                print(f"    Reason:  {res.get('reason')}")
            else:
                print(f"[-] Screen capture status: {st} ({res.get('error', 'unknown')})")

    elif action == "status":
        ctx = get_active_window_context()
        frames = engine.get_daily_frames()
        data = {
            "today_frames": len(frames),
            "active_window": ctx.get("title"),
            "active_process": ctx.get("process"),
            "platform": ctx.get("platform"),
            "frames_dir": str(engine.base_dir),
        }
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print("=" * 65)
            print("  📸  CEPHALO SCREEN MEMORY ENGINE STATUS")
            print("=" * 65)
            print(f"  Frames Logged Today:  {len(frames)}")
            print(f"  Active Window Title:  {ctx.get('title') or '(None / Headless)'}")
            print(f"  Active Process:       {ctx.get('process') or '(None / Headless)'}")
            print(f"  Platform:             {ctx.get('platform')}")
            print(f"  Storage Directory:    {engine.base_dir}")
            print("=" * 65)

    elif action == "prune":
        days = getattr(args, "days", 14)
        res = engine.prune_frames(max_age_days=days)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"[+] Pruned {res.get('deleted_frames', 0)} old frames older than {days} days.")
            print(f"[+] Created {res.get('thumbnails_created', 0)} micro-thumbnails for DeepWiki scrubbing.")


def cmd_digest(args) -> None:
    """Generates a visual, anti-AI-slop daily cognitive executive digest."""
    from cephalo.core.daily_digest import DailyDigestGenerator, check_and_offer_daily_digest

    if getattr(args, "check_offer", False):
        offer = check_and_offer_daily_digest(date_str=getattr(args, "date", None))
        if args.json:
            print(json.dumps({"offer_available": offer is not None, "offer_text": offer}, indent=2))
        elif offer:
            print(offer)
        return

    target_date = getattr(args, "date", None)
    gen = DailyDigestGenerator()
    digest_data = gen.generate_digest(date_str=target_date)

    if getattr(args, "copy", False):
        from cephalo.utils.clipboard_utils import set_clipboard_text
        md_text = gen.render_markdown(digest_data)
        set_clipboard_text(md_text)
        if not args.json:
            print("[+] Daily digest markdown copied to clipboard.")

    if args.json:
        print(json.dumps(digest_data, indent=2, ensure_ascii=False))
    else:
        print(gen.render_markdown(digest_data))


def main():
    maybe_auto_learn()

    # Common parent parser so flags like --json and --table work before or after subcommands
    shared_parser = argparse.ArgumentParser(add_help=False)
    shared_parser.add_argument("--json", action="store_true", help="Output results in machine-readable JSON format for agents.")
    shared_parser.add_argument("--table", type=str, default=None, help="LanceDB table name override.")
    shared_parser.add_argument("--copy", "-c", action="store_true", help="Copy command output directly to system clipboard.")

    parser = argparse.ArgumentParser(
        description="Cephalo - Agent & User Memory CLI",
        parents=[shared_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Status
    subparsers.add_parser("status", parents=[shared_parser], help="Display memory status, counts, and health.")

    # Profile
    profile_p = subparsers.add_parser("profile", parents=[shared_parser], help="Display or read USER_PROFILE.md.")
    profile_p.add_argument("--section", "-s", type=str, default=None, help="Extract specific section by title keyword or index (e.g. cinema, hardware, car, rules).")
    profile_p.add_argument("--list-sections", action="store_true", help="List all available sections and token estimates in USER_PROFILE.md.")

    # Search
    search_p = subparsers.add_parser("search", parents=[shared_parser], help="Search memory using hybrid, vector, or keyword matching.")
    search_p.add_argument("query", nargs="?", default=None, help="Search query string (or pipe via stdin).")
    search_p.add_argument("--type", choices=["hybrid", "vector", "fts"], default="hybrid", help="Search mode.")
    search_p.add_argument("--where", type=str, default=None, help="SQL filter expression.")
    search_p.add_argument("--limit", type=int, default=3, help="Max results to return (default: 3).")
    search_p.add_argument("--compact", action="store_true", help="Output high-density, token-efficient results (strips verbose IDs and metadata).")
    search_p.add_argument("--tag", type=str, default=None, help="Filter results by tag (e.g. #cinema/hdr or cinema).")
    search_p.add_argument("--all", "--include-deprecated", dest="include_deprecated", action="store_true", help="Include superseded/deprecated memories in search results.")

    # AST Code Definition Search (inspired by XERJ)
    def_p = subparsers.add_parser("def", parents=[shared_parser], help="AST code symbol and definition search across workspace projects.")
    def_p.add_argument("symbol", nargs="?", default=None, help="Symbol name to search for (function, class, interface, type, struct).")
    def_p.add_argument("--path", "-p", type=str, default=None, help="Root directory or file to search (default: current workspace).")
    def_p.add_argument("--exact", "-e", action="store_true", help="Match exact symbol name rather than substring.")
    def_p.add_argument("--limit", "-n", type=int, default=20, help="Maximum number of matches to return (default: 20).")

    # Record
    rec_p = subparsers.add_parser("record", parents=[shared_parser], help="Sanitize, embed, and store a prompt or memory.")
    rec_p.add_argument("text", nargs="?", default=None, help="Content to record (or pipe via stdin).")
    rec_p.add_argument("--clip", action="store_true", help="Record text directly from system clipboard.")
    rec_p.add_argument("--category", type=str, default="general", help="Category label.")
    rec_p.add_argument("--source", type=str, default="agent", help="Source identifier.")
    rec_p.add_argument("--intent", type=str, default="", help="Extracted intent.")
    rec_p.add_argument("--tag", "--tags", dest="tags", nargs="+", default=None, help="Explicit tags to associate with this memory.")
    rec_p.add_argument("--supersedes", type=str, default=None, help="ID of previous memory record this entry supersedes and deprecates.")
    rec_p.add_argument("--relates-to", dest="relates_to", nargs="+", default=None, help="IDs of related memory records or specialties.")

    # Sync
    sync_p = subparsers.add_parser("sync", parents=[shared_parser], help="Synchronize prompts.jsonl with LanceDB.")
    sync_p.add_argument("--file", type=str, default=str(PROMPTS_FILE), help="Source JSONL file.")

    # Harvest
    harv_p = subparsers.add_parser("harvest", parents=[shared_parser], help="Autonomously harvest preferences from transcripts.")
    harv_p.add_argument("--transcript", type=str, default=None, help="Specific transcript file to scan.")

    # Specialty
    spec_p = subparsers.add_parser("specialty", parents=[shared_parser], help="Manage project specialties (create, read, edit, delete, list).")
    spec_sub = spec_p.add_subparsers(dest="specialty_action", help="Specialty action")

    # specialty list
    spec_list_p = spec_sub.add_parser("list", parents=[shared_parser], help="List all specialties.")
    spec_list_p.add_argument("--project", type=str, default=None, help="Filter by project.")

    # specialty read
    spec_read_p = spec_sub.add_parser("read", parents=[shared_parser], help="Read a specialty.")
    spec_read_p.add_argument("name", type=str, help="Specialty name or slug.")
    spec_read_p.add_argument("--project", type=str, default=None, help="Project name.")

    # specialty create
    spec_create_p = spec_sub.add_parser("create", parents=[shared_parser], help="Create a new specialty.")
    spec_create_p.add_argument("name", type=str, help="Specialty name.")
    spec_create_p.add_argument("--project", type=str, required=True, help="Parent project.")
    spec_create_p.add_argument("--fundamentals", type=str, default=None, help="Core verified fundamentals text.")
    spec_create_p.add_argument("--repos", type=str, default=None, help="JSON list of curated GitHub repos.")
    spec_create_p.add_argument("--takeaways", type=str, default=None, help="Semicolon-separated key takeaways.")
    spec_create_p.add_argument("--preferences", type=str, default=None, help="Comma-separated user preference bindings.")

    # specialty edit
    spec_edit_p = spec_sub.add_parser("edit", parents=[shared_parser], help="Edit an existing specialty.")
    spec_edit_p.add_argument("name", type=str, help="Specialty name or slug.")
    spec_edit_p.add_argument("--project", type=str, default=None, help="Project name.")
    spec_edit_p.add_argument("--fundamentals", type=str, default=None, help="Updated fundamentals.")
    spec_edit_p.add_argument("--notes", type=str, default=None, help="Additional notes or updates.")

    # specialty delete
    spec_del_p = spec_sub.add_parser("delete", parents=[shared_parser], help="Delete a specialty (requires confirmation).")
    spec_del_p.add_argument("name", type=str, help="Specialty name or slug.")
    spec_del_p.add_argument("--project", type=str, default=None, help="Project name.")
    spec_del_p.add_argument("--confirm", action="store_true", help="Explicit user confirmation token for deletion.")

    # specialty auto-create
    spec_auto_p = spec_sub.add_parser("auto-create", parents=[shared_parser], help="Autonomously synthesize and create a specialty.")
    spec_auto_p.add_argument("topic", type=str, help="Technology, tool, or methodology to synthesize.")
    spec_auto_p.add_argument("--project", type=str, default="global", help="Target project (default: global).")
    spec_auto_p.add_argument("--preferences", type=str, default=None, help="Comma-separated user preference bindings.")

    # specialty auto-discover
    spec_disc_p = spec_sub.add_parser("auto-discover", parents=[shared_parser], help="Discover technologies from text/file and create missing specialties.")
    spec_disc_p.add_argument("--text", type=str, default=None, help="Text to scan for technologies/methodologies.")
    spec_disc_p.add_argument("--file", type=str, default=None, help="File path to scan.")
    spec_disc_p.add_argument("--project", type=str, default="global", help="Target project (default: global).")

    # specialty research
    spec_res_p = spec_sub.add_parser("research", parents=[shared_parser], help="Deep research topic, query GitHub repos, and synthesize specialty.")
    spec_res_p.add_argument("topic", type=str, help="Technology or domain topic to research.")
    spec_res_p.add_argument("--project", type=str, default="global", help="Target project (default: global).")
    spec_res_p.add_argument("--subtopics", nargs="+", default=None, help="Specific subtopics to decompose.")
    spec_res_p.add_argument("--notes", type=str, default=None, help="Custom notes or directives.")

    # Deep Research
    res_p = subparsers.add_parser("research", parents=[shared_parser], help="Conduct deep research, benchmark industry standards & GitHub repos, and optionally create specialty.")
    res_p.add_argument("topic", type=str, help="Technology or domain topic to research.")
    res_p.add_argument("--project", type=str, default="global", help="Target project (default: global).")
    res_p.add_argument("--subtopics", nargs="+", default=None, help="Specific subtopics to decompose.")
    res_p.add_argument("--notes", type=str, default=None, help="Custom notes or directives.")
    res_p.add_argument("--create", action="store_true", help="Automatically create and persist as a specialty in Cephalo.")

    # Email
    email_p = subparsers.add_parser("email", parents=[shared_parser], help="Outbound email operations (status, send).")
    email_sub = email_p.add_subparsers(dest="email_action", help="Email action")

    # email status
    email_sub.add_parser("status", parents=[shared_parser], help="Check email configuration.")

    # email send
    email_send_p = email_sub.add_parser("send", parents=[shared_parser], help="Send an email.")
    email_send_p.add_argument("--to", type=str, required=True, help="Recipient email address.")
    email_send_p.add_argument("--subject", type=str, required=True, help="Email subject.")
    email_send_p.add_argument("--body", type=str, default=None, help="Email body text.")
    email_send_p.add_argument("--body-file", type=str, default=None, help="Path to body file.")
    email_send_p.add_argument("--confirm", action="store_true", help="Explicit user confirmation token.")

    # Web Search
    web_p = subparsers.add_parser("web", parents=[shared_parser], help="Search the live web with Google-style Quick Summary, organic results, and social blocks.")
    web_p.add_argument("query", type=str, help="Search query string.")
    web_p.add_argument("--limit", type=int, default=5, help="Maximum number of search results (default: 5).")
    web_p.add_argument("--markdown", action="store_true", help="Output clean native Markdown SERP card (ideal for piping to agents).")
    web_p.add_argument("--record", action="store_true", help="Automatically sanitize and index results into LanceDB.")
    web_p.add_argument("--category", type=str, default="web_research", help="Category for recorded memory.")
    web_p.add_argument("--html", action="store_true", help="Generate an interactive Google-style HTML SERP interface.")
    web_p.add_argument("--open", action="store_true", help="Generate and open the HTML SERP in your default web browser.")
    web_p.add_argument("--no-social", action="store_true", help="Exclude social and discussion blocks.")

    # Web Fetch
    fetch_p = subparsers.add_parser("fetch", parents=[shared_parser], help="Extract clean readable text from a URL (supports static, dynamic Chromium, and YouTube) and optionally record it.")
    fetch_p.add_argument("url", type=str, help="Target webpage or YouTube URL.")
    fetch_p.add_argument("--youtube", "-y", action="store_true", help="Extract YouTube video transcript directly.")
    fetch_p.add_argument("--pattern", "-p", type=str, default=None, help="Apply cognitive pattern template (e.g. extract_wisdom).")
    fetch_p.add_argument("--dynamic", action="store_true", help="Render JavaScript dynamic SPAs using Playwright Chromium.")
    fetch_p.add_argument("--headed", action="store_true", help="Launch visible Chromium browser window instead of headless.")
    fetch_p.add_argument("--persistent", action="store_true", help="Use persistent browser profile in data/chromium_profile (preserves cookies/sessions).")
    fetch_p.add_argument("--max-chars", type=int, default=25000, help="Maximum characters to extract.")
    fetch_p.add_argument("--record", action="store_true", help="Automatically sanitize and index content into LanceDB.")
    fetch_p.add_argument("--category", type=str, default="web_research", help="Category for recorded memory.")

    # Pattern (Cognitive Reflexes)
    pat_p = subparsers.add_parser("pattern", parents=[shared_parser], help="Run and manage modular cognitive execution patterns.")
    pat_sub = pat_p.add_subparsers(dest="pattern_action", help="Pattern action")

    # pattern list
    pat_sub.add_parser("list", parents=[shared_parser], help="List all available patterns.")

    # pattern show
    pat_show_p = pat_sub.add_parser("show", parents=[shared_parser], help="Show the prompt template of a pattern.")
    pat_show_p.add_argument("name", type=str, help="Pattern name (e.g. extract_wisdom, review_code).")

    # pattern run
    pat_run_p = pat_sub.add_parser("run", parents=[shared_parser], help="Execute a pattern on text, clipboard, or stdin.")
    pat_run_p.add_argument("name", type=str, help="Pattern name to execute.")
    pat_run_p.add_argument("text", nargs="?", default=None, help="Input text to process (or pipe via stdin).")
    pat_run_p.add_argument("--clip", action="store_true", help="Read input directly from system clipboard.")
    pat_run_p.add_argument("--context", "-C", type=str, default=None, help="Inject domain specialty context.")
    pat_run_p.add_argument("--record", action="store_true", help="Automatically record and index pattern output in LanceDB.")
    pat_run_p.add_argument("--category", type=str, default="pattern_run", help="Category for recorded memory.")

    # Context (Dynamic Assembler)
    ctx_p = subparsers.add_parser("context", parents=[shared_parser], help="Assemble and export consolidated context for external LLMs.")
    ctx_sub = ctx_p.add_subparsers(dest="context_action", help="Context action")
    ctx_exp_p = ctx_sub.add_parser("export", parents=[shared_parser], help="Export consolidated context markdown.")
    ctx_exp_p.add_argument("--project", type=str, default=None, help="Target project.")
    ctx_exp_p.add_argument("--specialty", "-s", type=str, default=None, help="Domain specialty to include.")
    ctx_exp_p.add_argument("--no-hardware", action="store_true", help="Exclude hardware profile.")
    ctx_exp_p.add_argument("--cinema", action="store_true", help="Include cinema & entertainment aesthetic preferences.")

    # Wiki (Sovereign DeepWiki Engine)
    wiki_p = subparsers.add_parser("wiki", parents=[shared_parser], help="Sovereign codebase DeepWiki & codemap engine.")
    wiki_sub = wiki_p.add_subparsers(dest="wiki_action", help="Wiki action")
    wiki_sub.add_parser("generate", parents=[shared_parser], help="Generate offline Markdown documentation with Mermaid charts.")
    wiki_serve_p = wiki_sub.add_parser("serve", parents=[shared_parser], help="Serve generated DeepWiki on local HTTP server.")
    wiki_serve_p.add_argument("--port", type=int, default=7433, help="Port to serve on (default: 7433).")
    wiki_serve_p.add_argument("--no-open", dest="open", action="store_false", help="Do not automatically open browser.")

    # YouTube (Standalone Direct Ingestor)
    yt_p = subparsers.add_parser("youtube", parents=[shared_parser], help="Extract transcripts directly from YouTube videos.")
    yt_p.add_argument("url", type=str, help="YouTube video URL or 11-character video ID.")
    yt_p.add_argument("--pattern", "-p", type=str, default=None, help="Apply cognitive pattern template (e.g. extract_wisdom).")
    yt_p.add_argument("--record", action="store_true", help="Automatically record and index transcript in LanceDB.")
    yt_p.add_argument("--category", type=str, default="youtube", help="Category for recorded memory.")

    # Learn (Continuous Learning)
    learn_p = subparsers.add_parser("learn", parents=[shared_parser], help="Autonomous continuous learning across codebases, manifests, and memory.")
    learn_sub = learn_p.add_subparsers(dest="learn_action", help="Continuous learning action")

    # learn run
    learn_sub.add_parser("run", parents=[shared_parser], help="Execute a one-shot continuous learning cycle.")

    # learn status
    learn_sub.add_parser("status", parents=[shared_parser], help="Display continuous learning health and tracked topics.")

    # learn watch
    learn_watch_p = learn_sub.add_parser("watch", parents=[shared_parser], help="Run background continuous watcher.")
    learn_watch_p.add_argument("--interval", type=int, default=120, help="Interval between cycles in seconds (default: 120).")

    # Webhook
    wb_p = subparsers.add_parser("webhook", parents=[shared_parser], help="Multi-channel quick capture HTTP webhook and ingress gateway.")
    wb_sub = wb_p.add_subparsers(dest="webhook_action", help="Webhook action")
    wb_serve_p = wb_sub.add_parser("serve", parents=[shared_parser], help="Start foreground HTTP webhook receiver.")
    wb_serve_p.add_argument("--port", type=int, default=7434, help="Webhook port (default: 7434).")
    wb_serve_p.add_argument("--host", type=str, default="127.0.0.1", help="Webhook host interface (default: 127.0.0.1).")
    wb_serve_p.add_argument("--token", type=str, default=None, help="Optional Bearer authentication token.")
    wb_status_p = wb_sub.add_parser("status", parents=[shared_parser], help="Check webhook receiver status.")
    wb_status_p.add_argument("--port", type=int, default=7434, help="Webhook port.")
    wb_status_p.add_argument("--host", type=str, default="127.0.0.1", help="Webhook host.")
    wb_send_p = wb_sub.add_parser("send", parents=[shared_parser], help="Send a quick memory directly to the webhook receiver.")
    wb_send_p.add_argument("text", type=str, help="Text content to send.")
    wb_send_p.add_argument("--category", type=str, default="quick_note", help="Category label.")
    wb_send_p.add_argument("--port", type=int, default=7434, help="Target webhook port.")
    wb_send_p.add_argument("--host", type=str, default="127.0.0.1", help="Target webhook host.")

    # MCP (Model Context Protocol) Server
    subparsers.add_parser("mcp", help="Launch native Model Context Protocol (MCP) server for Claude Code, Cursor, Windsurf, Zed, etc.")

    # Daemon (Always-On Background Worker)
    daemon_p = subparsers.add_parser("daemon", parents=[shared_parser], help="Manage always-on background continuous learning daemon.")
    daemon_sub = daemon_p.add_subparsers(dest="daemon_action", help="Daemon action")
    daemon_run_p = daemon_sub.add_parser("run", parents=[shared_parser], help="Run daemon in foreground.")
    daemon_run_p.add_argument("--interval", type=int, default=90, help="Interval in seconds.")
    daemon_start_p = daemon_sub.add_parser("start", parents=[shared_parser], help="Start daemon as detached background process.")
    daemon_start_p.add_argument("--interval", type=int, default=90, help="Interval in seconds.")
    daemon_sub.add_parser("stop", parents=[shared_parser], help="Stop running background daemon.")
    daemon_sub.add_parser("status", parents=[shared_parser], help="Check daemon status and last cycle.")
    daemon_sub.add_parser("install-task", parents=[shared_parser], help="Install Windows Scheduled Task (auto-start on logon).")
    daemon_sub.add_parser("uninstall-task", parents=[shared_parser], help="Uninstall Windows Scheduled Task.")

    # Safeguard (Privacy & Blacklist Filter)
    safe_p = subparsers.add_parser("safeguard", parents=[shared_parser], help="Manage privacy safeguards and blacklists.")
    safe_sub = safe_p.add_subparsers(dest="safeguard_action", help="Safeguard action")
    safe_sub.add_parser("status", parents=[shared_parser], help="View current safeguards.")
    
    add_proc_p = safe_sub.add_parser("add-proc", parents=[shared_parser], help="Add process to blacklist.")
    add_proc_p.add_argument("name", type=str, help="Process name to blacklist (e.g. bitwarden)")

    add_title_p = safe_sub.add_parser("add-title", parents=[shared_parser], help="Add regex pattern to title blacklist.")
    add_title_p.add_argument("pattern", type=str, help="Regex pattern (e.g. (?i)private)")

    rem_proc_p = safe_sub.add_parser("remove-proc", parents=[shared_parser], help="Remove process from blacklist.")
    rem_proc_p.add_argument("name", type=str, help="Process name to unblock")

    rem_title_p = safe_sub.add_parser("remove-title", parents=[shared_parser], help="Remove regex pattern from title blacklist.")
    rem_title_p.add_argument("pattern", type=str, help="Regex pattern to unblock")

    test_safe_p = safe_sub.add_parser("test", parents=[shared_parser], help="Test whether a title/process is shielded.")
    test_safe_p.add_argument("title", type=str, help="Window title to test")
    test_safe_p.add_argument("--process", type=str, default="", help="Process name to test")

    # Screen Memory & Perceptual Delta Capture
    screen_p = subparsers.add_parser("screen", parents=[shared_parser], help="Manage screen memory and perceptual delta capture.")
    screen_sub = screen_p.add_subparsers(dest="screen_action", help="Screen memory action")
    
    snap_p = screen_sub.add_parser("snap", parents=[shared_parser], help="Evaluate and capture a perceptual delta keyframe.")
    snap_p.add_argument("--force", action="store_true", help="Force keyframe capture even if delta < threshold.")
    snap_p.add_argument("--ocr", action="store_true", help="Extract and index OCR text into vector memory.")

    screen_sub.add_parser("status", parents=[shared_parser], help="View screen memory and active window status.")
    
    prune_p = screen_sub.add_parser("prune", parents=[shared_parser], help="Prune old keyframes while preserving thumbnails.")
    prune_p.add_argument("--days", type=int, default=14, help="Max frame age in days (default: 14).")

    # Anti-AI-Slop Daily Cognitive Executive Digest
    digest_p = subparsers.add_parser("digest", parents=[shared_parser], help="Generate visual, anti-AI-slop daily cognitive executive digest.")
    digest_p.add_argument("--today", action="store_true", help="Generate digest for today.")
    digest_p.add_argument("--date", type=str, default=None, help="Target date in YYYY-MM-DD format.")
    digest_p.add_argument("--check-offer", action="store_true", help="Check if daily digest is available and should be offered.")

    args = parser.parse_args()

    COMMAND_HANDLERS = {
        "status": cmd_status,
        "profile": cmd_profile,
        "search": cmd_search,
        "def": cmd_def,
        "record": cmd_record,
        "sync": cmd_sync,
        "harvest": cmd_harvest,
        "specialty": cmd_specialty,
        "research": cmd_research,
        "learn": cmd_learn,
        "webhook": cmd_webhook,
        "mcp": cmd_mcp,
        "daemon": cmd_daemon,
        "email": cmd_email,
        "web": cmd_web,
        "fetch": cmd_fetch,
        "pattern": cmd_pattern,
        "context": cmd_context,
        "wiki": cmd_wiki,
        "youtube": cmd_youtube,
        "safeguard": cmd_safeguard,
        "screen": cmd_screen,
        "digest": cmd_digest,
    }

    if not args.command:
        cmd_status(args)
    elif args.command in COMMAND_HANDLERS:
        COMMAND_HANDLERS[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

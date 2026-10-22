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
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROMPTS_FILE = DATA_DIR / "prompts.jsonl"
DEFAULT_LANCEDB_DIR = DATA_DIR / "lancedb"
PROFILE_FILE = BASE_DIR / "USER_PROFILE.md"


def get_pipeline(table_name: Optional[str] = None):
    """Lazy loader for EmbeddingPipeline to keep light commands (status, profile) sub-second."""
    from embedding_pipeline import EmbeddingPipeline, create_embedder
    embedder = create_embedder(mode="local")
    return EmbeddingPipeline(embedder=embedder, db_path=DEFAULT_LANCEDB_DIR, table_name=table_name)


def cmd_profile(args) -> None:
    """Reads or updates USER_PROFILE.md."""
    if not PROFILE_FILE.exists():
        if args.json:
            print(json.dumps({"error": "USER_PROFILE.md not found"}, indent=2))
        else:
            print("Error: USER_PROFILE.md not found.")
        return

    content = PROFILE_FILE.read_text(encoding="utf-8")
    if args.json:
        print(json.dumps({"profile_path": str(PROFILE_FILE), "content": content}, indent=2, ensure_ascii=False))
    else:
        print(content)


def cmd_status(args) -> None:
    """Prints system health, LanceDB table status, and prompt counts."""
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

    status_data = {
        "working_directory": str(BASE_DIR),
        "prompts_file": str(PROMPTS_FILE),
        "prompts_logged": prompt_count,
        "profile_file": str(PROFILE_FILE),
        "profile_exists": PROFILE_FILE.exists(),
        "lancedb_dir": str(DEFAULT_LANCEDB_DIR),
        "lancedb_tables": table_stats,
        "recent_prompts": recent_prompts,
    }

    if args.json:
        print(json.dumps(status_data, indent=2, ensure_ascii=False))
        return

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


def cmd_search(args) -> None:
    """Performs hybrid, vector, or keyword search across LanceDB."""
    pipeline = get_pipeline(table_name=args.table)
    results = pipeline.search(
        raw_query=args.query,
        query_type=args.type,
        where=args.where,
        limit=args.limit,
    )

    if args.json:
        # Strip internal pyarrow formats if any for clean JSON serialization
        clean_results = []
        for r in results:
            clean_r = {k: v for k, v in r.items() if k != "vector"}
            clean_results.append(clean_r)
        print(json.dumps({"query": args.query, "type": args.type, "count": len(clean_results), "results": clean_results}, indent=2, ensure_ascii=False))
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
        content = res.get("content", "")
        preview = (content[:95] + "...") if len(content) > 95 else content
        print(f"  #{rank} [{score_str}] [{pid}] ({cat})")
        print(f"      {preview}")
    print("-" * 70)


def cmd_record(args) -> None:
    """Sanitizes, embeds, and records a new prompt/decision into LanceDB and prompts.jsonl."""
    pipeline = get_pipeline(table_name=args.table)
    record = pipeline.ingest_prompt(
        raw_text=args.text,
        category=args.category,
        source=args.source,
        intent=args.intent,
        sync_to_jsonl=True,
    )

    if args.json:
        clean_record = {k: v for k, v in record.items() if k != "vector"}
        print(json.dumps(clean_record, indent=2, ensure_ascii=False))
        return

    print(f"[+] Memory Recorded & Indexed [{record['id']}]:")
    print(f"    Category:  {record['category']}")
    print(f"    Sanitized: {record['content']}")
    print(f"    Model:     {record['embedding_model']} (dim={record['dimension']})")
    print(f"    Table:     {pipeline.store.table_name}")


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
    from auto_harvest import run_standalone_harvest
    run_standalone_harvest(transcript_path=args.transcript)

def cmd_specialty(args) -> None:
    """Handles CRUD operations for the Specialties domain layer."""
    from specialties_manager import SpecialtiesManager
    mgr = SpecialtiesManager()
    action = getattr(args, "specialty_action", None) or "list"

    if action == "list":
        items = mgr.list_specialties(project=args.project)
        if args.json:
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

    elif action == "read":
        data = mgr.get_specialty(args.name, project=args.project)
        if not data:
            if args.json:
                print(json.dumps({"error": f"Specialty '{args.name}' not found"}, indent=2))
            else:
                print(f"Error: Specialty '{args.name}' not found.")
            return
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return
        print(data["knowledge_content"])

    elif action == "create":
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
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return
        print(f"[+] Created and Indexed Specialty: '{args.name}' under Project: '{args.project}'")
        print(f"    Manifest:  {result['path']}\\manifest.json")
        print(f"    Knowledge: {result['knowledge_path']}")

    elif action == "edit":
        res = mgr.edit_specialty(
            name=args.name,
            project=args.project,
            fundamentals=getattr(args, "fundamentals", None),
            notes=getattr(args, "notes", None),
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return
        print(f"[+] Updated Specialty '{args.name}'.")

    elif action == "delete":
        confirmed = args.confirm
        if not confirmed and sys.stdin.isatty():
            ans = input(f"Are you sure you want to delete specialty '{args.name}'? Type 'yes' to confirm: ")
            confirmed = (ans.strip().lower() == "yes")

        try:
            mgr.delete_specialty(args.name, project=args.project, confirmed=confirmed)
            if args.json:
                print(json.dumps({"deleted": True, "specialty": args.name}, indent=2))
            else:
                print(f"[+] Successfully deleted specialty '{args.name}'.")
        except PermissionError as pe:
            if args.json:
                print(json.dumps({"error": str(pe)}, indent=2))
            else:
                print(f"Error: {pe}")

    elif action in ("auto-create", "auto"):
        prefs = [p.strip() for p in args.preferences.split(",")] if getattr(args, "preferences", None) else None
        res = mgr.auto_create_specialty(topic=args.topic, project=args.project, user_preferences=prefs)
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return
        if res.get("already_exists"):
            print(f"[i] Specialty '{res['manifest'].get('name')}' already exists in project '{res['manifest'].get('project')}'.")
            print(f"    Path: {res['path']}")
        else:
            print(f"[+] Autonomously Synthesized & Created Specialty: '{res['manifest'].get('name')}' under Project: '{res['manifest'].get('project')}'")
            print(f"    Manifest:  {res['path']}\\manifest.json")
            print(f"    Knowledge: {res['knowledge_path']}")

    elif action in ("auto-discover", "discover"):
        content = getattr(args, "text", None) or ""
        if getattr(args, "file", None):
            fpath = Path(args.file)
            if fpath.exists():
                content += "\n" + fpath.read_text(encoding="utf-8")
        if not content.strip():
            print("Error: Provide --text or --file to auto-discover technologies.")
            return
        results = mgr.auto_discover_and_create(text_or_items=content, project=args.project)
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
            return
        print(f"[+] Auto-Discovery Complete: Processed {len(results)} technologies.")
        for r in results:
            status = "Created" if r.get("created") else "Already Exists"
            print(f"  • [{status}] {r['manifest'].get('name')} ({r['manifest'].get('slug')}) in '{r['manifest'].get('project')}'")


def cmd_email(args) -> None:
    """Delegates to EmailClient."""
    from email_client import EmailClient
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
    """Searches the live web via WebSearchEngine with optional direct indexing."""
    from web_search import WebSearchEngine
    engine = WebSearchEngine()
    results = engine.search(args.query, max_results=args.limit)

    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False))
    else:
        print("=" * 65)
        print(f"  CEPHALO WEB SEARCH: '{args.query}' ({len(results)} results)")
        print("=" * 65)
        for idx, r in enumerate(results, 1):
            print(f"[{idx}] {r.title}")
            print(f"    URL: {r.url}")
            print(f"    {r.snippet}\n")
        print("=" * 65)

    if getattr(args, "record", False) and results:
        combined = f"Web Search for '{args.query}':\n" + "\n".join([f"- {r.title} ({r.url}): {r.snippet}" for r in results])
        pipeline = get_pipeline(table_name=args.table)
        rec = pipeline.record(text=combined, category=args.category, source="web_search", intent=args.query)
        if not args.json:
            print(f"[+] Search results sanitized & indexed into LanceDB [{rec.get('id')}].")


def cmd_fetch(args) -> None:
    """Fetches clean text from a URL (static or dynamic Chromium) and optionally records it."""
    from web_search import WebSearchEngine
    engine = WebSearchEngine()
    try:
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

    if args.json:
        print(json.dumps({"url": args.url, "content": page_text}, indent=2, ensure_ascii=False))
    else:
        print("=" * 65)
        print(f"  CEPHALO WEB FETCH: {args.url}")
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
    from continuous_learner import ContinuousLearner
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
    from mcp_server import run_stdio_server
    run_stdio_server()


def cmd_daemon(args) -> None:
    """Manages the always-on background daemon."""
    from cephalo_daemon import (
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


def main():
    # Common parent parser so flags like --json and --table work before or after subcommands
    shared_parser = argparse.ArgumentParser(add_help=False)
    shared_parser.add_argument("--json", action="store_true", help="Output results in machine-readable JSON format for agents.")
    shared_parser.add_argument("--table", type=str, default=None, help="LanceDB table name override.")

    parser = argparse.ArgumentParser(
        description="Cephalo - Agent & User Memory CLI",
        parents=[shared_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Status
    subparsers.add_parser("status", parents=[shared_parser], help="Display memory status, counts, and health.")

    # Profile
    subparsers.add_parser("profile", parents=[shared_parser], help="Display or read USER_PROFILE.md.")

    # Search
    search_p = subparsers.add_parser("search", parents=[shared_parser], help="Search memory using hybrid, vector, or keyword matching.")
    search_p.add_argument("query", type=str, help="Search query string.")
    search_p.add_argument("--type", choices=["hybrid", "vector", "fts"], default="hybrid", help="Search mode.")
    search_p.add_argument("--where", type=str, default=None, help="SQL filter expression.")
    search_p.add_argument("--limit", type=int, default=3, help="Max results to return (default: 3).")

    # Record
    rec_p = subparsers.add_parser("record", parents=[shared_parser], help="Sanitize, embed, and store a prompt or memory.")
    rec_p.add_argument("text", type=str, help="Content to record.")
    rec_p.add_argument("--category", type=str, default="general", help="Category label.")
    rec_p.add_argument("--source", type=str, default="agent", help="Source identifier.")
    rec_p.add_argument("--intent", type=str, default="", help="Extracted intent.")

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
    web_p = subparsers.add_parser("web", parents=[shared_parser], help="Search the live web and optionally record results.")
    web_p.add_argument("query", type=str, help="Search query string.")
    web_p.add_argument("--limit", type=int, default=5, help="Maximum number of search results (default: 5).")
    web_p.add_argument("--record", action="store_true", help="Automatically sanitize and index results into LanceDB.")
    web_p.add_argument("--category", type=str, default="web_research", help="Category for recorded memory.")

    # Web Fetch
    fetch_p = subparsers.add_parser("fetch", parents=[shared_parser], help="Extract clean readable text from a URL (supports static and dynamic Chromium) and optionally record it.")
    fetch_p.add_argument("url", type=str, help="Target webpage URL.")
    fetch_p.add_argument("--dynamic", action="store_true", help="Render JavaScript dynamic SPAs using Playwright Chromium.")
    fetch_p.add_argument("--headed", action="store_true", help="Launch visible Chromium browser window instead of headless.")
    fetch_p.add_argument("--persistent", action="store_true", help="Use persistent browser profile in data/chromium_profile (preserves cookies/sessions).")
    fetch_p.add_argument("--max-chars", type=int, default=25000, help="Maximum characters to extract.")
    fetch_p.add_argument("--record", action="store_true", help="Automatically sanitize and index content into LanceDB.")
    fetch_p.add_argument("--category", type=str, default="web_research", help="Category for recorded memory.")

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

    args = parser.parse_args()

    if not args.command or args.command == "status":
        cmd_status(args)
    elif args.command == "profile":
        cmd_profile(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "record":
        cmd_record(args)
    elif args.command == "sync":
        cmd_sync(args)
    elif args.command == "harvest":
        cmd_harvest(args)
    elif args.command == "specialty":
        cmd_specialty(args)
    elif args.command == "learn":
        cmd_learn(args)
    elif args.command == "mcp":
        cmd_mcp(args)
    elif args.command == "daemon":
        cmd_daemon(args)
    elif args.command == "email":
        cmd_email(args)
    elif args.command == "web":
        cmd_web(args)
    elif args.command == "fetch":
        cmd_fetch(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

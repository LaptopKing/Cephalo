"""
Cephalo - Sovereign Autonomous Second Brain & Long-Term Memory Engine
Command Line Interface (CLI) Dispatcher & Argument Parser
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure Cephalo root and src are on sys.path
ROOT_DIR = Path(__file__).resolve().parents[2]
BASE_DIR = ROOT_DIR
DATA_DIR = ROOT_DIR / "data"
PROMPTS_FILE = DATA_DIR / "prompts.jsonl"
DEFAULT_LANCEDB_DIR = DATA_DIR / "lancedb"
PROFILE_FILE = ROOT_DIR / "USER_PROFILE.md"

for p in (str(ROOT_DIR), str(ROOT_DIR / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from cephalo.commands.common import get_pipeline, parse_profile_sections, resolve_cli_input
from cephalo.commands.profile_cmds import cmd_profile, cmd_status, get_system_status, cmd_reconcile
from cephalo.commands.memory_cmds import cmd_search, cmd_def, cmd_record, cmd_sync, cmd_harvest, cmd_clean
from cephalo.commands.specialty_cmds import cmd_specialty
from cephalo.commands.research_cmds import (
    cmd_daemon,
    cmd_email,
    cmd_fetch,
    cmd_learn,
    cmd_mcp,
    cmd_research,
    cmd_web,
    maybe_auto_learn,
)
from cephalo.commands.system_cmds import cmd_pattern, cmd_context, cmd_wiki, cmd_webhook, cmd_youtube, cmd_safeguard, cmd_screen, cmd_digest, cmd_carryover
from cephalo.commands.task_cmds import cmd_task, cmd_subagent, cmd_queue, cmd_ocr
from cephalo.commands.maintenance_cmds import cmd_migrate, cmd_update, cmd_integrate, cmd_gatekeeper

logger = logging.getLogger("cephalo.cli")

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

    # Reconcile (Autonomous Contextual Preference Reconciler)
    reconcile_p = subparsers.add_parser("reconcile", parents=[shared_parser], help="Audit active memories and automatically deprecate superseded/conflicting preferences.")
    reconcile_p.add_argument("--dry-run", action="store_true", help="Inspect superseded memories without writing deprecations to disk.")
    reconcile_p.add_argument("--category", type=str, default=None, help="Filter reconciliation to specific category.")

    # Profile
    profile_p = subparsers.add_parser("profile", parents=[shared_parser], help="Display, extract, or update USER_PROFILE.md.")
    profile_p.add_argument("--section", "-s", type=str, default=None, help="Extract specific section by title keyword or index (e.g. cinema, hardware, car, rules).")
    profile_p.add_argument("--list-sections", action="store_true", help="List all available sections and token estimates in USER_PROFILE.md.")
    profile_p.add_argument("--update-section", type=str, default=None, help="Section title keyword or index to update (e.g. cinema, rules, 2).")
    profile_p.add_argument("--append", type=str, default=None, help="Text bullet or note to append to the target section.")
    profile_p.add_argument("--replace", type=str, default=None, help="New content to completely replace the target section body.")

    # Search
    search_p = subparsers.add_parser("search", parents=[shared_parser], help="Search memory using hybrid, vector, or keyword matching.")
    search_p.add_argument("query", nargs="?", default=None, help="Search query string (or pipe via stdin).")
    search_p.add_argument("--type", choices=["hybrid", "vector", "fts"], default="hybrid", help="Search mode.")
    search_p.add_argument("--where", type=str, default=None, help="SQL filter expression.")
    search_p.add_argument("--limit", type=int, default=3, help="Max results to return (default: 3).")
    search_p.add_argument("--compact", action="store_true", help="Output high-density, token-efficient results (strips verbose IDs and metadata).")
    search_p.add_argument("--min-score", "--threshold", dest="min_score", type=float, default=None, help="Relevance score floor or max distance threshold to prune low-confidence noise.")
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

    # Clean
    clean_p = subparsers.add_parser("clean", parents=[shared_parser], help="Purge empty entries and deduplicate redundant memories.")

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
    daemon_sub.add_parser("autostart", parents=[shared_parser], help="Configure daemon to automatically start on boot across Linux, macOS, and Windows.")
    daemon_sub.add_parser("install-autostart", parents=[shared_parser], help="Install cross-platform boot autostart service.")
    daemon_sub.add_parser("uninstall-autostart", parents=[shared_parser], help="Uninstall cross-platform boot autostart service.")
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
    screen_sub.add_parser("enable", parents=[shared_parser], help="Enable continuous background desktop screen memory.")
    screen_sub.add_parser("disable", parents=[shared_parser], help="Disable continuous background desktop screen memory.")
    
    prune_p = screen_sub.add_parser("prune", parents=[shared_parser], help="Prune old keyframes while preserving thumbnails.")
    prune_p.add_argument("--days", type=int, default=14, help="Max frame age in days (default: 14).")

    # Anti-AI-Slop Daily Cognitive Executive Digest
    digest_p = subparsers.add_parser("digest", parents=[shared_parser], help="Generate visual, anti-AI-slop daily cognitive executive digest.")
    digest_p.add_argument("--today", action="store_true", help="Generate digest for today.")
    digest_p.add_argument("--date", type=str, default=None, help="Target date in YYYY-MM-DD format.")
    digest_p.add_argument("--check-offer", action="store_true", help="Check if daily digest is available and should be offered.")

    
    # Carryover (Context Compaction Defense)
    carry_p = subparsers.add_parser("carryover", parents=[shared_parser], help="Output high-density compaction carryover memory anchor.")
    carry_p.add_argument("--specialty", type=str, default=None, help="Active project specialty to include.")

    # Subagent (Resource Governor & State Recovery)
    subagent_p = subparsers.add_parser("subagent", parents=[shared_parser], help="Manage subagent concurrency, hardware governor, and state recovery.")
    subagent_sub = subagent_p.add_subparsers(dest="subagent_action", help="Subagent action")
    subagent_sub.add_parser("status", parents=[shared_parser], help="Inspect battery, CPU load, and safe subagent concurrency.")
    subagent_sub.add_parser("governor", parents=[shared_parser], help="Run hardware governor inspection.")
    subagent_sub.add_parser("list", parents=[shared_parser], help="List all tracked subagent tasks.")
    
    subagent_res_p = subagent_sub.add_parser("resume", parents=[shared_parser], help="Resume an interrupted subagent task from its last checkpoint.")
    subagent_res_p.add_argument("task_id", type=str, help="Task ID to resume.")

    subagent_chk_p = subagent_sub.add_parser("checkpoint", parents=[shared_parser], help="Checkpoint subagent step progress.")
    subagent_chk_p.add_argument("task_id", type=str, help="Task ID to checkpoint.")
    subagent_chk_p.add_argument("--step", type=int, default=0, help="Step index completed.")
    subagent_chk_p.add_argument("--state", type=str, default="{}", help="JSON checkpoint state.")

    # Queue (Serialized Work Queue for Heavy Background Tasks)
    queue_p = subparsers.add_parser("queue", parents=[shared_parser], help="Manage serialized work queue for FastEmbed, ONNX, and OCR tasks.")
    queue_sub = queue_p.add_subparsers(dest="queue_action", help="Queue action")
    queue_sub.add_parser("status", parents=[shared_parser], help="View queued, running, and completed tasks.")
    queue_sub.add_parser("list", parents=[shared_parser], help="List recent background jobs.")
    queue_sub.add_parser("run", parents=[shared_parser], help="Process pending jobs immediately.")
    queue_sub.add_parser("clear", parents=[shared_parser], help="Clear completed/failed job history.")

    # Task (Multi-Agent Coordination & Checkpoint Ledger)
    task_p = subparsers.add_parser("task", parents=[shared_parser], help="Manage multi-agent task coordination and rate-limit recovery ledger.")
    task_sub = task_p.add_subparsers(dest="task_action", help="Task action")
    task_sub.add_parser("list", parents=[shared_parser], help="List active and paused tasks.")
    task_res_p = task_sub.add_parser("resume", parents=[shared_parser], help="Resume a paused subagent task.")
    task_res_p.add_argument("task_id", type=str, help="Task ID to resume.")

    # OCR (Indra OCR Document & Image Parser)
    ocr_p = subparsers.add_parser("ocr", parents=[shared_parser], help="Ultra-fast pure-CPU OCR using Indra (45+ pages/sec).")
    ocr_p.add_argument("file_path", type=str, help="Image or PDF file path to extract text from.")
    ocr_p.add_argument("--record", action="store_true", help="Automatically record and index in LanceDB.")
    ocr_p.add_argument("--category", type=str, default="ocr_document", help="Category for recorded memory.")

    # Migrate (Universal Multi-Harness Settings & Data Migration)
    mig_p = subparsers.add_parser("migrate", parents=[shared_parser], help="Migrate all settings (default) or all settings + data + projects (--all) across harnesses.")
    mig_p.add_argument("--all", "-a", action="store_true", help="Migrate Cephalo vector data, prompt memory, SQLite DBs, and all workspace projects in addition to settings.")
    mig_p.add_argument("--output", "-o", type=str, default=None, help="Output destination archive path.")
    mig_p.add_argument("--format", "-f", type=str, choices=["xz", "gz", "zip"], default="xz", help="Compression format (default: xz for maximum lossless compression).")
    mig_p.add_argument("--include-build-artifacts", action="store_true", help="Include build caches (target/, .venv/) in project archives.")
    mig_p.add_argument("--include-secrets", action="store_true", help="Include secrets and sensitive environment files (.env) in export archive.")
    mig_p.add_argument("--fast", action="store_true", help="Ultra-fast export (uses high-throughput preset).")
    mig_p.add_argument("--preset", type=int, default=6, help="LZMA compression preset (0-9, default: 6).")

    mig_sub = mig_p.add_subparsers(dest="migrate_action", help="Migration action (export, restore, inspect, list)")

    # migrate export
    mig_exp_p = mig_sub.add_parser("export", parents=[shared_parser], help="Export and compress settings or all data.")
    mig_exp_p.add_argument("--all", "-a", action="store_true", help="Include Cephalo data (LanceDB, prompts) and scratch projects.")
    mig_exp_p.add_argument("--output", "-o", type=str, default=None, help="Output destination archive path.")
    mig_exp_p.add_argument("--format", "-f", type=str, choices=["xz", "gz", "zip"], default="xz", help="Compression format (default: xz).")
    mig_exp_p.add_argument("--include-build-artifacts", action="store_true", help="Include compiler build artifacts.")
    mig_exp_p.add_argument("--include-secrets", action="store_true", help="Include secrets and sensitive environment files (.env) in export archive.")
    mig_exp_p.add_argument("--fast", action="store_true", help="Ultra-fast export (uses high-throughput preset).")
    mig_exp_p.add_argument("--preset", type=int, default=6, help="LZMA compression preset (0-9, default: 6).")

    # migrate restore
    mig_res_p = mig_sub.add_parser("restore", parents=[shared_parser], help="Restore a migration archive and set up all harnesses with a single command.")
    mig_res_p.add_argument("archive", type=str, help="Path to migration archive (.cephalo.tar.xz, .zip, etc.).")
    mig_res_p.add_argument("--yes", "-y", action="store_true", help="Skip interactive confirmation.")
    mig_res_p.add_argument("--dry-run", action="store_true", help="Preview restore actions without modifying files on disk.")
    mig_res_p.add_argument("--no-backup", action="store_true", help="Do not create .bak.<ts> safety backups.")
    mig_res_p.add_argument("--only-cephalo", action="store_true", help="Restore Cephalo settings/data only (skip other harness configs).")
    mig_res_p.add_argument("--only-harnesses", action="store_true", help="Restore agent harness configs only (skip Cephalo core).")

    # migrate inspect
    mig_ins_p = mig_sub.add_parser("inspect", parents=[shared_parser], help="Inspect archive contents, manifest, and compression ratio without extracting.")
    mig_ins_p.add_argument("archive", type=str, help="Path to migration archive.")

    # migrate list
    mig_sub.add_parser("list", parents=[shared_parser], help="List available migration archives in data/migrations.")

    # Gatekeeper (Tsetlin Machine Propositional Intent & Preference Rule Gatekeeper)
    gk_p = subparsers.add_parser("gatekeeper", aliases=["tsetlin"], parents=[shared_parser], help="Deterministic Tsetlin Machine Propositional Intent & Preference Rule Gatekeeper.")
    gk_sub = gk_p.add_subparsers(dest="gatekeeper_action", help="Gatekeeper action")

    # gatekeeper route <text>
    gk_route_p = gk_sub.add_parser("route", parents=[shared_parser], help="High-speed intent routing (<1ms) with propositional clause explanation.")
    gk_route_p.add_argument("text", type=str, help="Prompt or text to route.")

    # gatekeeper rules [--category <name>]
    gk_rules_p = gk_sub.add_parser("rules", parents=[shared_parser], help="Display learned propositional logic Boolean rules.")
    gk_rules_p.add_argument("--category", "--class", dest="category", type=str, default=None, help="Filter rules to specific category.")
    gk_rules_p.add_argument("--limit", type=int, default=8, help="Max rules per category (default: 8).")

    # gatekeeper train [--epochs <n>] [--seed-only]
    gk_train_p = gk_sub.add_parser("train", parents=[shared_parser], help="Retrain Tsetlin Machine model from Cephalo memory and seed dataset.")
    gk_train_p.add_argument("--epochs", type=int, default=40, help="Training epochs (default: 40).")
    gk_train_p.add_argument("--seed-only", action="store_true", help="Train strictly on curated seed data.")

    # gatekeeper cinema <description>
    gk_cin_p = gk_sub.add_parser("cinema", parents=[shared_parser], help="Evaluate cinema recommendation against user TCL 65T8B 4K preference rules.")
    gk_cin_p.add_argument("text", type=str, help="Movie or entertainment description to evaluate.")

    # Update (Auto-Updater & Release Tracking)
    up_p = subparsers.add_parser("update", parents=[shared_parser], help="Manage Cephalo background auto-updates and release synchronization.")
    up_sub = up_p.add_subparsers(dest="update_action", help="Update action")

    up_check_p = up_sub.add_parser("check", parents=[shared_parser], help="Check GitHub for newer Cephalo release.")
    up_check_p.add_argument("--force", action="store_true", help="Bypass throttling cache and check GitHub immediately.")

    up_apply_p = up_sub.add_parser("apply", aliases=["run"], parents=[shared_parser], help="Apply available release update.")
    up_apply_p.add_argument("--sync", action="store_true", help="Run update synchronously instead of in background.")
    up_apply_p.add_argument("--target", type=str, help="Specific target tag/version to install.")

    up_pol_p = up_sub.add_parser("policy", parents=[shared_parser], help="Configure auto-update policy (auto, notify, off).")
    up_pol_p.add_argument("policy_mode", nargs="?", choices=["auto", "notify", "off"], help="Auto-update mode.")

    up_sub.add_parser("status", parents=[shared_parser], help="Show auto-update and release tracker status.")

    # Integrate (Ecosystem Adaptive Integrator)
    int_p = subparsers.add_parser("integrate", parents=[shared_parser], help="Non-destructively integrate Cephalo into developer ecosystems.")
    int_sub = int_p.add_subparsers(dest="integrate_action", help="Target ecosystem")
    int_sub.add_parser("all", parents=[shared_parser], help="Integrate into all detected ecosystems (shells, harnesses, IDEs).")
    int_sub.add_parser("shells", parents=[shared_parser], help="Integrate into Bash, Zsh, and Fish shells.")
    int_sub.add_parser("antigravity", parents=[shared_parser], help="Integrate into Google Antigravity & Gemini CLI.")
    int_sub.add_parser("claude", parents=[shared_parser], help="Integrate into Claude Code.")
    int_sub.add_parser("cursor", parents=[shared_parser], help="Integrate into Cursor IDE.")
    int_sub.add_parser("windsurf", parents=[shared_parser], help="Integrate into Windsurf Cascade.")
    int_sub.add_parser("cline", aliases=["vscode", "roo"], parents=[shared_parser], help="Integrate into VS Code Cline / Roo Code.")
    int_proj_p = int_sub.add_parser("project", parents=[shared_parser], help="Integrate Cephalo grounding into a local project directory.")
    int_proj_p.add_argument("path", nargs="?", default=".", help="Target project root directory.")
    int_sub.add_parser("status", aliases=["doctor"], parents=[shared_parser], help="Inspect integration health across all ecosystems.")

    # Doctor
    subparsers.add_parser("doctor", parents=[shared_parser], help="Inspect Cephalo ecosystem integration health.")

    args = parser.parse_args()

    COMMAND_HANDLERS = {
        "status": cmd_status,
        "reconcile": cmd_reconcile,
        "profile": cmd_profile,
        "search": cmd_search,
        "def": cmd_def,
        "record": cmd_record,
        "sync": cmd_sync,
        "clean": cmd_clean,
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
        "carryover": cmd_carryover,
        "task": cmd_task,
        "subagent": cmd_subagent,
        "queue": cmd_queue,
        "ocr": cmd_ocr,
        "migrate": cmd_migrate,
        "gatekeeper": cmd_gatekeeper,
        "tsetlin": cmd_gatekeeper,
        "update": cmd_update,
        "integrate": cmd_integrate,
        "doctor": cmd_integrate,
    }

    if not args.command:
        cmd_status(args)
    elif args.command in COMMAND_HANDLERS:
        COMMAND_HANDLERS[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

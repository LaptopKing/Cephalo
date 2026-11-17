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
)

logger = logging.getLogger("cephalo.cli")

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
    """Manages the always-on background daemon via native Rust engine."""
    action = getattr(args, "daemon_action", None) or "status"
    interval = str(getattr(args, "interval", 90))
    cmd = ["cephalo", "daemon", action]
    if action == "run":
        cmd.extend(["--interval", interval])
        try:
            subprocess.run(cmd, check=False)
        except Exception as e:
            print(f"[-] Failed to execute cephalo daemon: {e}")
    elif action in ("install-task", "install-autostart", "autostart"):
        install_autostart()
    elif action in ("uninstall-task", "uninstall-autostart"):
        uninstall_autostart()


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



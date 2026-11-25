from __future__ import annotations

import datetime
import json
import logging
import os
import subprocess
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
        rust_bin = ROOT_DIR / "rust" / "target" / "release" / ("cephalo.exe" if sys.platform == "win32" else "cephalo")
        if not rust_bin.exists():
            print("[-] Cephalo native Rust engine binary is not built. Run 'cd rust && cargo build --release' to enable the high-performance webhook gateway.")
            return
        cmd = [str(rust_bin), "webhook", "serve", "--port", str(port)]
        if getattr(args, "token", None):
            cmd.extend(["--token", args.token])
        subprocess.run(cmd, check=False)

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
        import urllib.request
        text = getattr(args, "text", "")
        cat = getattr(args, "category", "quick_note")
        payload = json.dumps({"text": text, "category": cat}).encode("utf-8")
        req = urllib.request.Request(f"http://{host}:{port}/ingest", data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                res = json.loads(resp.read().decode("utf-8"))
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
    """Manages desktop screen memory and visual timeline via sovereign native Rust engine."""
    action = getattr(args, "screen_action", None) or "status"
    rust_bin = ROOT_DIR / "rust" / "target" / "release" / ("cephalo.exe" if sys.platform == "win32" else "cephalo")
    if not rust_bin.exists():
        print("[-] Cephalo native Rust engine binary is not built. Run 'cd rust && cargo build --release' to enable desktop screen capture.")
        return
    cmd = [str(rust_bin), "screen", action]
    if getattr(args, "force", False):
        cmd.append("--force")
    if getattr(args, "json", False):
        cmd.append("--json")
    try:
        subprocess.run(cmd, check=False)
    except Exception as e:
        print(f"[-] Error executing cephalo screen: {e}")


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




def cmd_carryover(args):
    """Generates high-density compaction carryover memory anchor."""
    from cephalo.learning.auto_harvest import CompactionCarryover
    cc = CompactionCarryover()
    payload = cc.build_carryover_payload(active_specialty=getattr(args, "specialty", None))
    if getattr(args, "json", False):
        print(json.dumps({"carryover": payload}, ensure_ascii=False))
    else:
        print(payload)



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
    from cephalo.core.embedding_pipeline import Sanitizer
    sanitizer = Sanitizer()
    takeaways = [sanitizer.sanitize(t.strip()) for t in args.takeaways.split(";")] if getattr(args, "takeaways", None) else []
    prefs = [sanitizer.sanitize(p.strip()) for p in args.preferences.split(",")] if getattr(args, "preferences", None) else []
    fund = sanitizer.sanitize(args.fundamentals) if args.fundamentals else f"Core verified fundamentals for {args.name}."

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
    from cephalo.core.embedding_pipeline import Sanitizer
    sanitizer = Sanitizer()
    fund = sanitizer.sanitize(args.fundamentals) if getattr(args, "fundamentals", None) else None
    notes = sanitizer.sanitize(args.notes) if getattr(args, "notes", None) else None
    res = mgr.edit_specialty(
        name=args.name,
        project=args.project,
        fundamentals=fund,
        notes=notes,
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
        sys.exit(1)



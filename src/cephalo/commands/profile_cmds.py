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

def cmd_profile(args) -> None:
    """Reads, extracts, or atomically mutates sections in USER_PROFILE.md with token-efficient filters."""
    if not PROFILE_FILE.exists():
        if args.json:
            print(json.dumps({"error": "USER_PROFILE.md not found"}, indent=2))
        else:
            print("Error: USER_PROFILE.md not found.")
        return

    content = PROFILE_FILE.read_text(encoding="utf-8")
    sections = parse_profile_sections(content)

    # 1. Sectional Profile Mutator (--update-section)
    target_update = getattr(args, "update_section", None)
    if target_update:
        append_text = getattr(args, "append", None)
        replace_text = getattr(args, "replace", None)

        if not append_text and not replace_text:
            msg = "Error: Must specify either --append <text> or --replace <text> with --update-section."
            if args.json:
                print(json.dumps({"error": msg}, indent=2))
            else:
                print(msg)
            return

        req_clean = target_update.strip().lower()
        matched_idx = None
        if req_clean.isdigit():
            idx = int(req_clean)
            if 1 <= idx <= len(sections):
                matched_idx = idx - 1
        if matched_idx is None:
            for i, s in enumerate(sections):
                if req_clean in s["title"].lower():
                    matched_idx = i
                    break

        if matched_idx is None:
            avail = [s["title"] for s in sections]
            if args.json:
                print(json.dumps({"error": f"Section '{target_update}' not found", "available_sections": avail}, indent=2))
            else:
                print(f"Error: Section '{target_update}' not found in USER_PROFILE.md.")
                print(f"Available sections: {', '.join(avail[:6])}...")
            return

        matched = sections[matched_idx]
        old_content = matched["content"]

        from cephalo.core.embedding_pipeline import Sanitizer
        sanitizer = Sanitizer()

        if replace_text:
            header_prefix = f"## {matched['title']}"
            rep = sanitizer.sanitize(replace_text.strip())
            if not rep.startswith("## "):
                body = f"{header_prefix}\n\n{rep}"
            else:
                body = rep
            while body.endswith("---"):
                body = body[:-3].strip()
            new_sec_text = body
            action_desc = "replaced"
        else:
            addition = sanitizer.sanitize(append_text.strip())
            from cephalo.core.preference_reconciler import PreferenceReconciler
            new_sec_text, was_replaced, old_bullet = PreferenceReconciler.reconcile_markdown_section(
                old_content, addition
            )
            if was_replaced:
                action_desc = f"reconciled (replaced '{old_bullet}')"
            else:
                action_desc = "appended"

        sections[matched_idx]["content"] = new_sec_text
        sections[matched_idx]["tokens_est"] = round(len(new_sec_text) / 3.8)

        # Atomic backup and safe disk write
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        bak_file = PROFILE_FILE.parent / f"USER_PROFILE.md.bak.{timestamp}"
        try:
            bak_file.write_text(content, encoding="utf-8")
        except Exception:
            pass

        reconstructed = "\n\n---\n\n".join(s["content"].strip() for s in sections) + "\n"
        temp_file = PROFILE_FILE.parent / f"USER_PROFILE.md.tmp.{os.getpid()}"
        temp_file.write_text(reconstructed, encoding="utf-8")
        temp_file.replace(PROFILE_FILE)

        if args.json:
            print(json.dumps({
                "status": "success",
                "action": action_desc,
                "section": matched["title"],
                "tokens_est": sections[matched_idx]["tokens_est"],
                "backup_path": str(bak_file)
            }, indent=2, ensure_ascii=False))
        else:
            print(f"[+] Successfully {action_desc} content to section '{matched['title']}' in USER_PROFILE.md (~{sections[matched_idx]['tokens_est']} tokens).")
            print(f"[+] Safety backup saved to: {bak_file.name}")
        return

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


def cmd_reconcile(args) -> None:
    """Audits active LanceDB memories and automatically deprecates superseded or conflicting entries."""
    pipeline = get_pipeline(table_name=args.table)
    table = pipeline.store.table
    if table.count_rows() == 0:
        if args.json:
            print(json.dumps({"status": "empty", "message": "Vector database is empty."}))
        else:
            print("Vector database is empty.")
        return

    arrow_tbl = table.to_arrow()
    records = arrow_tbl.to_pylist()
    # Exclude specialties and already deprecated records
    active_records = [
        r for r in records
        if not r.get("is_deprecated") and not str(r.get("category", "")).startswith("specialty:")
    ]

    from cephalo.core.preference_reconciler import PreferenceReconciler
    reconciler = PreferenceReconciler()

    dry_run = getattr(args, "dry_run", False)
    category_filter = getattr(args, "category", None)

    active_records.sort(key=lambda x: x.get("timestamp", ""))

    superseded_pairs = []
    seen_older_ids = set()

    for newer_rec in active_records:
        n_cat = newer_rec.get("category", "")
        if category_filter and n_cat != category_filter:
            continue
        n_text = newer_rec.get("content", "")
        if not reconciler.is_stateful_candidate(n_cat, n_text):
            continue

        # Use stored vector directly to eliminate CPU embedding recomputation (sub-second execution)
        vec = newer_rec.get("vector")
        candidates = pipeline.store.search(
            query_vector=vec,
            query_text=n_text,
            query_type="hybrid" if vec is not None else "fts",
            limit=6,
            include_deprecated=False,
        )

        for cand in candidates:
            cand_id = cand.get("id")
            if not cand_id or cand_id == newer_rec["id"] or cand_id in seen_older_ids:
                continue

            # Only older records can be superseded by a newer record
            if cand.get("timestamp", "") >= newer_rec.get("timestamp", ""):
                continue

            cand_text = cand.get("content", "")
            cand_cat = cand.get("category", "")
            distance = cand.get("_distance")

            is_sup, reason, conf = reconciler.detect_supersession(
                new_text=n_text,
                cand_text=cand_text,
                category=n_cat,
                cand_category=cand_cat,
                distance=distance,
            )
            if is_sup and conf >= 0.75:
                superseded_pairs.append({
                    "older_id": cand_id,
                    "older_content": cand_text[:90],
                    "newer_id": newer_rec["id"],
                    "newer_content": n_text[:90],
                    "reason": reason,
                    "confidence": conf,
                })
                seen_older_ids.add(cand_id)
                if not dry_run:
                    pipeline.store.deprecate_record(cand_id, superseded_by=newer_rec["id"], sync_to_jsonl=True)

    if args.json:
        print(json.dumps({
            "dry_run": dry_run,
            "total_active_scanned": len(active_records),
            "superseded_count": len(superseded_pairs),
            "reconciliations": superseded_pairs,
        }, indent=2, ensure_ascii=False))
        return

    print(f"[*] Scanned {len(active_records)} active memories for contextual supersessions.")
    if not superseded_pairs:
        print("[+] All active preferences and memories are clean and non-conflicting.")
        return

    mode_str = "[DRY-RUN] Found" if dry_run else "[+] Successfully deprecated"
    print(f"{mode_str} {len(superseded_pairs)} superseded memories:")
    for item in superseded_pairs:
        print(f"  - [{item['older_id']}] superseded by [{item['newer_id']}] (Confidence: {item['confidence']:.0%})")
        print(f"    Reason: {item['reason']}")
        print(f"    Old: {item['older_content']}...")
        print(f"    New: {item['newer_content']}...\n")

    if dry_run:
        print("Tip: Run `cephalo reconcile` without --dry-run to commit deprecations to LanceDB and prompts.jsonl.")


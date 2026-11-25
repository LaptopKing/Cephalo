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

def cmd_migrate(args):
    """
    Universal Multi-Harness Settings & Data Migration Engine.
    Handles export (default), restore, inspect, and list actions.
    """
    from cephalo.core.migration import (
        MigrationManager,
        MigrationScope,
        CompressionFormat,
    )
    manager = MigrationManager()
    action = getattr(args, "migrate_action", None)

    # 1. LIST ACTION
    if action == "list":
        archives = manager.list_migrations()
        if getattr(args, "json", False):
            print(json.dumps({"archives": archives, "count": len(archives)}, indent=2, ensure_ascii=False))
            return
        print("=" * 65)
        print("  CEPHALO MIGRATION ARCHIVES (AVAILABLE BACKUPS)")
        print("=" * 65)
        if not archives:
            print(f"No migration archives found in {manager.migrations_dir}")
            print("Tip: Run 'cephalo migrate' to create a settings migration archive.")
            print("     Run 'cephalo migrate --all' to create a full data + projects archive.")
            print("=" * 65)
            return
        for a in archives:
            print(f"📦 {a['filename']}")
            print(f"   Path:        {a['path']}")
            print(f"   Scope:       {a.get('scope', 'unknown').upper()} | Size: {a.get('size_formatted', '0 B')} | Files: {a.get('files_count', 0)}")
            if a.get("created_at"):
                print(f"   Created At:  {a['created_at']}")
            if a.get("harnesses"):
                print(f"   Harnesses:   {', '.join(a['harnesses'])}")
            print("-" * 65)
        print(f"Total Archives: {len(archives)}")
        print("=" * 65)
        return

    # 2. INSPECT ACTION
    if action == "inspect":
        archive_path = Path(args.archive)
        try:
            info = manager.inspect_migration(archive_path)
            if getattr(args, "json", False):
                print(json.dumps(info, indent=2, ensure_ascii=False))
                return
            print("=" * 65)
            print("  CEPHALO MIGRATION ARCHIVE INSPECTION")
            print("=" * 65)
            print(f"Archive:            {info.get('archive_path')}")
            print(f"Scope:              {info.get('scope', 'unknown').upper()}")
            print(f"Created At:         {info.get('created_at')}")
            print(f"Source System:      {info.get('source_host')} ({info.get('source_os')})")
            print(f"Python Version:     {info.get('source_python')}")
            print(f"Source Cephalo:     {info.get('source_cephalo_dir')}")
            print("-" * 65)
            print(f"Total Files:        {info.get('total_files', 0):,}")
            print(f"Uncompressed Size:  {info.get('total_uncompressed_bytes', 0):,} bytes")
            print(f"Compressed Archive: {info.get('compressed_size_formatted')} ({info.get('compression_ratio')})")
            print(f"Harnesses Included: {', '.join(info.get('harnesses_detected', []))}")
            if info.get("projects_detected"):
                print(f"Projects Included:  {', '.join(info.get('projects_detected', []))}")
            print("=" * 65)
            print("To restore and set up everything from this archive, run:")
            print(f'  cephalo migrate restore "{archive_path}"')
            print("=" * 65)
        except Exception as e:
            print(f"Error inspecting migration archive: {e}")
        return

    # 3. RESTORE ACTION
    if action == "restore":
        archive_path = Path(args.archive)
        dry_run = getattr(args, "dry_run", False)
        auto_backup = not getattr(args, "no_backup", False)
        only_cephalo = getattr(args, "only_cephalo", False)
        only_harnesses = getattr(args, "only_harnesses", False)

        try:
            print("=" * 65)
            print("  CEPHALO UNIVERSAL MIGRATION - SINGLE-COMMAND RESTORATION")
            print("=" * 65)
            print(f"Archive:       {archive_path}")
            print(f"Mode:          {'DRY RUN (Simulation)' if dry_run else 'LIVE RESTORE'}")
            print(f"Safety Backup: {'Enabled (.bak.<ts>)' if auto_backup else 'Disabled'}")
            print("Verifying archive integrity and restoring...")
            print("-" * 65)

            res = manager.restore_migration(
                archive_path=archive_path,
                dry_run=dry_run,
                auto_backup=auto_backup,
                only_cephalo=only_cephalo,
                only_harnesses=only_harnesses,
            )

            if getattr(args, "json", False):
                print(json.dumps(res, indent=2, ensure_ascii=False))
                return

            if dry_run:
                print("[*] Dry run completed successfully! No files were modified.")
                print(f"    • Files that would be restored: {res.get('files_to_restore', 0)}")
                print(f"    • Uncompressed bytes: {res.get('total_uncompressed_bytes', 0):,}")
                print(f"    • Harnesses in backup: {', '.join(res.get('harnesses_in_backup', []))}")
                print(f"    • Integrity status: {res.get('integrity')}")
                return

            print("[+] Cephalo Migration Restored & Configured Successfully!")
            print(f"    • Restored Files:       {res.get('restored_files_count', 0):,} files")
            print(f"    • Safety Backups:       {res.get('backups_created_count', 0):,} files")
            print(f"    • Configured Harnesses: {', '.join(res.get('harnesses_configured', []))}")
            health = res.get("health", {})
            print(f"    • User Profile Status:  {'Loaded & Active' if health.get('profile_loaded') else 'Missing'}")
            print(f"    • Prompts In Memory:    {health.get('prompts_record_count', 0)} records")
            if health.get("lancedb_tables"):
                print(f"    • LanceDB Tables:       {', '.join(health.get('lancedb_tables', []))}")
            print(f"    • Execution Time:       {res.get('duration_seconds')}s")
            print("=" * 65)
            print("Everything has been set up! Cephalo and all agent harnesses are ready.")
        except Exception as e:
            print(f"[-] Migration restoration failed: {e}")
            if getattr(args, "json", False):
                print(json.dumps({"status": "error", "error": str(e)}, indent=2))
        return

    # 4. EXPORT ACTION (Default if action is None or 'export')
    is_all = getattr(args, "all", False)
    scope = MigrationScope.ALL if is_all else MigrationScope.SETTINGS
    out_path = Path(args.output) if getattr(args, "output", None) else None
    fmt_str = getattr(args, "format", "xz") or "xz"
    fmt = CompressionFormat(fmt_str)
    inc_build = getattr(args, "include_build_artifacts", False)

    try:
        print("=" * 65)
        print("  CEPHALO UNIVERSAL MIGRATION - EXPORT & COMPACT")
        print("=" * 65)
        print(f"Scope:           {scope.value.upper()} ({'Settings + Vector Data + Projects' if is_all else 'All Harness & Cephalo Settings'})")
        print(f"Lossless Format: {fmt.value.upper()} (LZMA2 extreme maximum compression)")
        print("Scanning harnesses, settings, rules, and memory...")
        print("-" * 65)

        preset = getattr(args, "preset", 6)
        fast = getattr(args, "fast", False)
        inc_secrets = getattr(args, "include_secrets", False)

        res = manager.create_migration(
            scope=scope,
            output_path=out_path,
            compression_format=fmt,
            include_build_artifacts=inc_build,
            include_secrets=inc_secrets,
            preset=preset,
            fast=fast,
        )

        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return

        print("[+] Migration Archive Created Successfully!")
        print(f"    • Archive Path:         {res['archive_path']}")
        print(f"    • Total Files Packaged: {res['files_count']:,}")
        print(f"    • Uncompressed Size:    {res['uncompressed_bytes']:,} bytes ({manager._format_bytes(res['uncompressed_bytes'])})")
        print(f"    • Compressed Size:      {res['compressed_bytes']:,} bytes ({manager._format_bytes(res['compressed_bytes'])})")
        print(f"    • Compression Ratio:    {res['compression_ratio_pct']}% reduction (Lossless)")
        print(f"    • Included Harnesses:   {', '.join(res['harnesses'])}")
        if res.get("projects"):
            print(f"    • Included Projects:    {', '.join(res['projects'])}")
        print(f"    • Export Time:          {res['duration_seconds']}s")
        print("=" * 65)
        print("To restore and set up everything on any machine with a single command:")
        print(f'  cephalo migrate restore "{res['archive_path']}"')
        print("=" * 65)
    except Exception as e:
        print(f"[-] Migration export failed: {e}")
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "error": str(e)}, indent=2))


def cmd_update(args):
    """Manage Cephalo auto-updates, releases, and background synchronization."""
    from cephalo.services.updater import (
        check_for_updates,
        apply_update_background,
        execute_update_sync,
        load_update_state,
        save_update_state,
        acquire_update_lock,
        release_update_lock,
        is_update_locked,
    )

    action = getattr(args, "update_action", None)
    is_json = getattr(args, "json", False)

    if action == "check":
        force = getattr(args, "force", False)
        res = check_for_updates(force=force)
        if is_json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print("=" * 64)
            print("  ⚡ CEPHALO RELEASE TRACKER")
            print("=" * 64)
            print(f"  Current Version:  {res.get('current_version')}")
            print(f"  Latest Release:   {res.get('latest_version')}")
            print(f"  Update Available: {'YES (Ready to update)' if res.get('update_available') else 'NO (Up to date)'}")
            print(f"  Last Checked:     {res.get('checked_at')}")
            if res.get('release_url'):
                print(f"  Release URL:      {res.get('release_url')}")
            print("=" * 64)

    elif action == "apply" or action == "run":
        target = getattr(args, "target", None)
        sync_mode = getattr(args, "sync", False)

        if sync_mode:
            if not acquire_update_lock():
                print("[-] Error: Another update is currently in progress.")
                return
            try:
                ok, msg = execute_update_sync(target)
                print(f"[+] {msg}")
            finally:
                release_update_lock()
        else:
            res = apply_update_background(target)
            if is_json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print(f"[+] {res['message']}")
                print(f"    Follow live logs: tail -f {res.get('log_file')}")

    elif action == "policy":
        new_pol = getattr(args, "policy_mode", None)
        if new_pol:
            state = load_update_state()
            state["policy"] = new_pol
            save_update_state(state)
            print(f"[+] Cephalo background auto-update policy set to: {new_pol}")
        else:
            state = load_update_state()
            print(f"Current update policy: {state.get('policy', 'notify')}")

    else:
        # Status / default
        state = load_update_state()
        if is_json:
            print(json.dumps(state, indent=2, ensure_ascii=False))
        else:
            print("=" * 64)
            print("  ⚡ CEPHALO UPDATE & RELEASE STATUS")
            print("=" * 64)
            print(f"  Current Version:      {state.get('current_version')}")
            print(f"  Latest Known Release: {state.get('latest_version')}")
            print(f"  Update Available:     {state.get('update_available')}")
            print(f"  Update Policy:        {state.get('policy', 'notify')} (Options: notify, off)")
            print(f"  Last Checked:         {state.get('last_checked_at') or 'Never'}")
            print(f"  Last Update Applied:  {state.get('last_update_applied_at') or 'None'}")
            print(f"  Update Lock Active:   {is_update_locked()}")
            print("=" * 64)
            print("Commands:")
            print("  cephalo update check          Check for newer release on GitHub")
            print("  cephalo update apply          Apply update in background")
            print("  cephalo update policy notify  Set release check policy")
            print("=" * 64)


def cmd_integrate(args):
    """Seamlessly integrate Cephalo into shell, editor, or agent environments."""
    from cephalo.services.integrator import (
        run_all_integrations,
        integrate_shells,
        integrate_antigravity,
        integrate_claude,
        integrate_cursor,
        integrate_windsurf,
        integrate_vscode_cline_roo,
        integrate_project,
        inspect_status,
    )

    action = getattr(args, "integrate_action", None) or "all"
    is_json = getattr(args, "json", False)

    if action == "status" or action == "doctor" or getattr(args, "command", "") == "doctor":
        status = inspect_status()
        if is_json:
            print(json.dumps(status, indent=2, ensure_ascii=False))
        else:
            print("=" * 64)
            print("  🩺 CEPHALO ECOSYSTEM INTEGRATION DOCTOR")
            print("=" * 64)
            print(f"  Cephalo Root:     {status['cephalo_dir']}")
            print(f"  Python Runtime:   {status['python_exe']}")
            print("-" * 64)
            print("  Shells:")
            for sh, present in status['shells'].items():
                print(f"    • {sh:16}: {'✓ Present' if present else '- Not detected'}")
            print("-" * 64)
            print("  AI Agent Harnesses & IDEs:")
            print(f"    • Antigravity / Gemini : {'✓ Configured' if status['antigravity']['plugin_installed'] else '- Not detected'}")
            print(f"    • Claude Code          : {'✓ Detected' if status['claude']['detected'] else '- Not detected'}")
            print(f"    • Cursor IDE           : {'✓ Detected' if status['cursor']['detected'] else '- Not detected'}")
            print(f"    • Windsurf Cascade     : {'✓ Detected' if status['windsurf']['detected'] else '- Not detected'}")
            print(f"    • Herdr                : {'✓ Detected' if status['herdr']['detected'] else '- Not detected'}")
            print("=" * 64)
        return

    if action == "shells":
        res = integrate_shells()
    elif action == "antigravity":
        res = integrate_antigravity()
    elif action == "claude":
        res = integrate_claude()
    elif action == "cursor":
        res = integrate_cursor()
    elif action == "windsurf":
        res = integrate_windsurf()
    elif action == "vscode" or action == "cline":
        res = integrate_vscode_cline_roo()
    elif action == "project":
        path = Path(getattr(args, "path", ".") or ".")
        res = integrate_project(path)
    else:
        res = run_all_integrations()

    if is_json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print("=" * 64)
        print("  🧩 CEPHALO ECOSYSTEM INTEGRATION APPLIED")
        print("=" * 64)
        print("  Non-destructive integration complete. Zero existing configs overwritten.")
        print("=" * 64)


def cmd_gatekeeper(args):
    """Deterministic Tsetlin Machine Propositional Intent & Preference Rule Gatekeeper."""
    from cephalo.learning.tsetlin_gatekeeper import get_gatekeeper, TsetlinGatekeeper, INTENT_CATEGORIES

    action = getattr(args, "gatekeeper_action", None)
    if not action:
        if getattr(args, "text", None):
            action = "route"
        else:
            action = "rules"

    gk = get_gatekeeper()

    if action == "route":
        text = getattr(args, "text", "")
        if not text:
            print("Error: Prompt or text to route is required.")
            return

        res = gk.route(text)
        if getattr(args, "json", False):
            print(json.dumps(res.to_dict(), indent=2, ensure_ascii=False))
        else:
            print("=" * 68)
            print("  ⚡ TSETLIN MACHINE INTENT GATEKEEPER")
            print("=" * 68)
            print(f"  Input:             \"{res.text}\"")
            print(f"  Predicted Intent:  {res.category}")
            print(f"  Confidence:        {res.confidence:.2f} (Vote Margin: {res.vote_margin:+d})")
            print(f"  Triggered Rule:    {res.triggered_clause or 'None'}")
            print(f"  Inference Time:    {res.execution_time_ms:.3f} ms")
            print("-" * 68)
            print("  Category Vote Breakdown:")
            sorted_votes = sorted(res.votes.items(), key=lambda x: -x[1])
            for cat, vote in sorted_votes:
                marker = "→" if cat == res.category else " "
                print(f"    {marker} {cat:24} : {vote:+d}")
            print("=" * 68)

    elif action == "rules":
        category_filter = getattr(args, "category", None) or getattr(args, "class_name", None)
        limit = getattr(args, "limit", 8) or 8
        rules = gk.rules(class_name=category_filter, limit_per_class=limit)

        if getattr(args, "json", False):
            print(json.dumps(rules, indent=2, ensure_ascii=False))
        else:
            print("=" * 68)
            print("  📜 LEARNED PROPOSITIONAL BOOLEAN RULES")
            print("=" * 68)
            for cat, r_list in rules.items():
                print(f"\n  [{cat.upper()}] ({len(r_list)} rules):")
                if not r_list:
                    print("    (no active rules)")
                for r in r_list:
                    print(f"    • {r}")
            print("\n" + "=" * 68)

    elif action == "train":
        epochs = getattr(args, "epochs", 40) or 40
        seed_only = getattr(args, "seed_only", False)
        print(f"🧠 Training Tsetlin Machine Gatekeeper (epochs={epochs}, seed_only={seed_only})...")
        stats = gk.train(epochs=epochs, use_cephalo_memory=not seed_only, save_on_complete=True)

        if getattr(args, "json", False):
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        else:
            print("✓ Training Complete!")
            print(f"  • Training Samples:  {stats['samples_count']}")
            print(f"  • Vocabulary Size:   {stats['vocabulary_size']} tokens")
            print(f"  • Learned Clauses:   {stats['clause_count']}")
            print(f"  • Accuracy:          {stats['accuracy']*100:.1f}%")
            print(f"  • Training Time:     {stats['train_duration_sec']}s")
            print(f"  • Saved Path:        {gk.model_path}")

    elif action == "cinema" or action == "evaluate":
        item = getattr(args, "text", "")
        if not item:
            print("Error: Movie description or item to evaluate is required.")
            return

        res = gk.evaluate_cinema(item)
        if getattr(args, "json", False):
            print(json.dumps(res.to_dict(), indent=2, ensure_ascii=False))
        else:
            print("=" * 68)
            print("  🎬 CINEMA PREFERENCE INDUCTION (LEARNED USER PROFILE)")
            print("=" * 68)
            print(f"  Item:             \"{res.item}\"")
            print(f"  Verdict:          {res.verdict}")
            print(f"  Confidence:       {res.confidence:.2f} (Score: {res.score:+d})")
            print(f"  Triggered Rule:   {res.triggered_rule or 'None'}")
            print("=" * 68)



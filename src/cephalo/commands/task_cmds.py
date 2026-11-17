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

def cmd_task(args):
    """Manages multi-agent coordination and rate-limit recovery ledger."""
    from cephalo.core.task_ledger import TaskLedger
    ledger = TaskLedger()
    action = getattr(args, "task_action", "list") or "list"

    if action == "list":
        tasks = ledger.list_tasks(limit=30)
        if getattr(args, "json", False):
            print(json.dumps({"tasks": tasks, "count": len(tasks)}, indent=2, ensure_ascii=False))
        else:
            if not tasks:
                print("No tasks recorded in multi-agent ledger.")
                return
            print(f"📋 Multi-Agent Task Ledger ({len(tasks)} tasks):")
            print("-" * 75)
            for t in tasks:
                reset_info = f" [Resets: {t['rate_limit_reset_at'][:19]}]" if t.get("rate_limit_reset_at") else ""
                print(f"[{t['status'].upper():20}] {t['task_id']} | Step {t['step_index']}/{t['total_steps']} | {t['assignee_agent']}: {t['user_goal'][:40]}{reset_info}")
            print("-" * 75)

    elif action == "resume":
        task_id = args.task_id
        task = ledger.get_task(task_id)
        if not task:
            print(f"Task '{task_id}' not found.")
            return
        if getattr(args, "json", False):
            print(json.dumps({"task": task}, indent=2, ensure_ascii=False))
        else:
            print(f"🔄 Resuming Task: {task_id}")
            print(f"   Goal: {task['user_goal']}")
            print(f"   Step: {task['step_index']} of {task['total_steps']}")
            print(f"   Assignee: {task['assignee_agent']}")
            print("   Saved Checkpoint State:")
            print(json.dumps(task.get("checkpoint_state", {}), indent=4))


def cmd_subagent(args):
    """Manages subagent lifecycle, checkpointing, power throttling, and crash recovery."""
    from cephalo.services.subagent_governor import SubagentGovernor
    gov = SubagentGovernor()
    action = getattr(args, "subagent_action", "status") or "status"

    if action == "status" or action == "governor":
        metrics = gov.inspect_resources()
        if getattr(args, "json", False):
            print(json.dumps(metrics, indent=2, ensure_ascii=False))
            return

        print("=" * 65)
        print("  ⚡ CEPHALO SUBAGENT RESOURCE GOVERNOR")
        print("=" * 65)
        print(f"  Power Source:      {'🔋 Battery' if metrics['on_battery'] else '🔌 AC Power'}")
        if metrics.get("battery_percent") is not None:
            print(f"  Battery Level:     {metrics['battery_percent']}%")
        print(f"  CPU Utilization:   {metrics['cpu_percent']}% (Load 1m: {metrics['load_1m']})")
        print(f"  Available Memory:  {metrics['mem_available_mb']} MB")
        print(f"  Governor Mode:     {metrics['mode']}")
        print(f"  Safe Concurrency:  {metrics['safe_concurrency']} subagent(s) max")
        print(f"  Throttle Advice:   {metrics['throttle_reason']}")
        print("=" * 65)

        interrupted = gov.get_interrupted_tasks()
        if interrupted:
            print(f"\n⚠️  {len(interrupted)} Interrupted Subagent Task(s) Found (from crash/reboot):")
            for it in interrupted:
                print(f"   • [{it['task_id']}] Step {it['step_index']}/{it['total_steps']}: {it['user_goal']}")
                print(f"     Run `cephalo subagent resume {it['task_id']}` to restore state.")

    elif action == "checkpoint":
        task_id = args.task_id
        step = getattr(args, "step", 0)
        state_raw = getattr(args, "state", "{}")
        try:
            state_dict = json.loads(state_raw)
        except Exception:
            state_dict = {"raw_state": state_raw}
        res = gov.checkpoint_subagent(task_id=task_id, step_index=step, checkpoint_state=state_dict)
        print(f"[+] Checkpointed task {task_id} at step {step}.")

    elif action == "resume":
        task_id = args.task_id
        brief = gov.build_resume_brief(task_id)
        if not brief:
            print(f"[-] Task '{task_id}' not found.")
            return
        if getattr(args, "json", False):
            task = gov.ledger.get_task(task_id)
            print(json.dumps(task, indent=2, ensure_ascii=False))
        else:
            print(brief)

    elif action == "list":
        tasks = gov.ledger.list_tasks(limit=30)
        if getattr(args, "json", False):
            print(json.dumps(tasks, indent=2, ensure_ascii=False))
        else:
            print(f"📋 Subagent Tasks ({len(tasks)}):")
            for t in tasks:
                print(f"[{t['status'].upper():12}] {t['task_id']} | Step {t['step_index']}/{t['total_steps']} | {t['user_goal'][:45]}")


def cmd_queue(args):
    """Manages the serialized background work queue (FastEmbed, ONNX, OCR, Learning)."""
    from cephalo.services.job_queue import JobQueue, QueueWorker
    queue = JobQueue()
    action = getattr(args, "queue_action", "status") or "status"

    if action == "status":
        st = queue.get_status()
        if getattr(args, "json", False):
            print(json.dumps(st, indent=2, ensure_ascii=False))
            return

        print("=" * 65)
        print("  🔄 CEPHALO SERIALIZED WORK QUEUE")
        print("=" * 65)
        print(f"  Pending Jobs:    {st['pending']}")
        print(f"  Running Jobs:    {st['running']}")
        print(f"  Completed Jobs:  {st['completed']}")
        print(f"  Failed Jobs:     {st['failed']}")
        if st.get("current_running_job"):
            rj = st["current_running_job"]
            print(f"  Active Task:     #{rj['id']} [{rj['job_type']}] started at {rj['started_at']}")
        else:
            print("  Active Task:     None (Idle / Cool)")
        print("=" * 65)

    elif action == "list":
        jobs = queue.list_jobs(limit=30)
        if getattr(args, "json", False):
            print(json.dumps(jobs, indent=2, ensure_ascii=False))
            return
        print(f"📋 Background Work Queue ({len(jobs)} jobs):")
        print("-" * 75)
        for j in jobs:
            err = f" - Error: {j['error_message'][:30]}" if j.get("error_message") else ""
            print(f"[{j['status'].upper():9}] #{j['id']:<4} Prio:{j['priority']} {j['job_type']:<20} ({j['created_at'][:19]}){err}")
        print("-" * 75)

    elif action == "run":
        worker = QueueWorker(queue)
        print("[*] Processing queue jobs sequentially...")
        count = 0
        while worker.process_one(sync=True):
            count += 1
        print(f"[+] Processed {count} job(s). Queue is now clear.")

    elif action == "clear":
        cleared = queue.clear_history(hours_old=0)
        print(f"[+] Cleared {cleared} completed/failed history records from queue.")


def cmd_ocr(args):
    """Runs ultra-fast pure-CPU Indra OCR on image or document."""
    file_path = Path(args.file_path)
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return

    import indra_ocr
    conv = indra_ocr.load(threads=4, mode="auto")
    text_parts = []

    if file_path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
        from PIL import Image
        import cv2
        import numpy as np
        img = Image.open(file_path).convert("RGB")
        gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
        page = conv.ocr(gray)
        text = (getattr(page, "markdown", None) or getattr(page, "text", "") or "").strip()
        text_parts.append(text)
    else:
        for page_idx, page in conv.convert(str(file_path)):
            if page.markdown:
                text_parts.append(page.markdown)

    combined = "\n\n".join(text_parts)
    if getattr(args, "json", False):
        print(json.dumps({"file": str(file_path), "text": combined}, ensure_ascii=False))
    else:
        print(combined)

    if getattr(args, "record", False):
        from brain import get_pipeline
        pipeline = get_pipeline()
        pipeline.ingest_prompt(
            raw_text=combined,
            category=args.category,
            source=f"ocr:{file_path.name}",
            tags=["ocr", file_path.suffix.lstrip(".")],
            sync_to_jsonl=True,
        )
        print(f"Recorded OCR content into LanceDB under category '{args.category}'.")



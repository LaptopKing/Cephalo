#!/usr/bin/env python3
"""
Cephalo Autonomous Memory Harvester & Dynamic Context Injector (auto_harvest.py)
================================================================================
Universal lifecycle processor for agent harnesses (Google Antigravity, Claude Code, Cursor, Codex).

Core Principles:
1. Complete Prompt Auditing:
   - Tracks and records EVERY single user prompt into prompts.jsonl.
   - Categorizes preferences, hardware, critiques, or general prompts automatically.
2. Token-Efficient Context Injection (PreInvocation):
   - Only ever injects context when past discussions/constraints are genuinely relevant.
   - If a prompt touches completely new topics never discussed before, stays 100% SILENT (0 tokens wasted).
   - Injects minimal, high-density ephemeral context only when relevant (e.g. TV hardware, cinema constraints).
3. Host-Level Autonomous Execution:
   - Executes via harness lifecycle hooks (PreInvocation, Stop, SessionStart) without requiring model compliance.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Force UTF-8 on Windows terminal/pipes
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Base Paths
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
PROMPTS_FILE = DATA_DIR / "prompts.jsonl"
STATE_FILE = DATA_DIR / "harvest_state.json"
PROFILE_FILE = SCRIPT_DIR / "USER_PROFILE.md"
LANCEDB_DIR = DATA_DIR / "lancedb"

# Threshold for Qwen 1024d L2 distance (<= 1.22 indicates strong semantic relevance to personal knowledge)
RELEVANCE_DISTANCE_THRESHOLD = 1.22

# Regular expression cues indicating persistent preferences or feedback
PREFERENCE_SIGNALS = [
    # Dislikes / Critiques
    (r"\b(found it boring|too slow|too grey|waste our time|didn't like|dislike|hated?|terrible|not what we were looking for)\b", "critique_negative_filter"),
    # Preferences / Likes
    (r"\b(we loved?|prefer|preference|favorite|really liked?|enjoyed|looking for)\b", "user_preference"),
    # Hardware / Device setup
    (r"\b(my tv is|my monitor is|my setup|hardware|graphics card|gpu|resolution|screen size|tcl|qled)\b", "hardware_spec"),
    # Directives / Workflows
    (r"\b(should always|never do|always use|my rule is|by default|from now on)\b", "workflow_rule"),
    # First language / regional
    (r"\b(first language|native language|hungarian|magyar|marketplace)\b", "language_locale"),
    # Entertainment / Media
    (r"\b(movie|film|series|watch|show|cinema|director|bullet train|gentlemen)\b", "entertainment_preferences"),
    # Specialty trigger / Technology adoption
    (r"\b(specialt(y|ies)|need specialties|build up our specialties|technolog(y|ies)|stack|architecture)\b", "specialty_domain_learning"),
]


def load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"processed_conversations": {}}


def save_state(state: Dict[str, Any]) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def extract_user_messages(transcript_path: Path, last_step_index: int = -1) -> List[Dict[str, Any]]:
    """Extract user prompts from transcript.jsonl."""
    if not transcript_path.exists():
        return []

    new_messages = []
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    step_idx = obj.get("step_index", 0)
                    if step_idx > last_step_index and obj.get("type") == "USER_INPUT":
                        content = obj.get("content", "")
                        # Strip outer system wrapper tags if present
                        clean_content = re.sub(r"<USER_REQUEST>\s*", "", content)
                        clean_content = re.sub(r"\s*</USER_REQUEST>.*", "", clean_content, flags=re.DOTALL)
                        clean_content = clean_content.strip()
                        if clean_content:
                            new_messages.append({
                                "step_index": step_idx,
                                "timestamp": obj.get("created_at", ""),
                                "content": clean_content
                            })
                except Exception:
                    continue
    except Exception:
        pass
    return new_messages


def harvest_all_user_prompts(messages: List[Dict[str, Any]], conversation_id: str = "") -> int:
    """
    Records EVERY user prompt into prompts.jsonl.
    If it contains preference/critique cues, categorizes it accordingly.
    Otherwise logs it under 'user_prompt'.
    """
    if not messages:
        return 0

    harvested_count = 0
    existing_contents = set()
    if PROMPTS_FILE.exists():
        try:
            with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        p = json.loads(line)
                        existing_contents.add(p.get("content", "").strip())
                    except Exception:
                        pass
        except Exception:
            pass

    for msg in messages:
        text = msg["content"]
        if text in existing_contents:
            continue

        detected_categories = []
        for pattern, cat in PREFERENCE_SIGNALS:
            if re.search(pattern, text, re.IGNORECASE):
                detected_categories.append(cat)

        primary_cat = detected_categories[0] if detected_categories else "user_prompt"
        prompt_id = f"prompt-auto-{abs(hash(text)) % 1000000:06d}"

        entry = {
            "id": prompt_id,
            "timestamp": msg.get("timestamp") or datetime.datetime.now().astimezone().isoformat(),
            "source": "auto_harvester",
            "category": primary_cat,
            "conversation_id": conversation_id,
            "step_index": msg.get("step_index"),
            "content": text,
            "extracted_intent": f"User prompt recorded: {primary_cat}",
            "detected_signals": detected_categories,
        }

        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(PROMPTS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            existing_contents.add(text)
            harvested_count += 1

            # Autonomous Specialty creation for unknown technologies/methodologies
            if "specialty_domain_learning" in detected_categories:
                try:
                    from specialties_manager import SpecialtiesManager
                    sm = SpecialtiesManager()
                    sm.auto_discover_and_create(text, project="global")
                except Exception:
                    pass
        except Exception:
            pass

    return harvested_count


def query_relevant_memory(query_text: str) -> Optional[Tuple[str, str, float]]:
    """
    Performs ultra-fast local vector search directly in LanceDB.
    Returns (id, content_snippet, distance) if relevant, or None if unrelated.
    Token-efficiency guarantee: If distance > RELEVANCE_DISTANCE_THRESHOLD, returns None.
    """
    if not LANCEDB_DIR.exists():
        return None

    try:
        import lancedb
        from fastembed import TextEmbedding

        db = lancedb.connect(str(LANCEDB_DIR))
        raw_tables = db.list_tables()
        table_names = list(getattr(raw_tables, "tables", raw_tables))
        table_name = "prompts_local_1024" if "prompts_local_1024" in table_names else (table_names[0] if table_names else None)

        if not table_name:
            return None

        tbl = db.open_table(table_name)
        if tbl.count_rows() == 0:
            return None

        embedder = TextEmbedding(model_name="Qwen/Qwen3-Embedding-0.6B-Q")
        vec = list(embedder.embed([query_text]))[0]

        results = tbl.search(vec).limit(1).to_list()
        if not results:
            return None

        top = results[0]
        dist = top.get("_distance", 2.0)

        # Ignore if category is generic chat without actionable facts
        cat = top.get("category", "")
        if cat in ("user_prompt", "general") and dist > 1.15:
            return None

        if dist <= RELEVANCE_DISTANCE_THRESHOLD:
            content = top.get("content", "")
            return (top.get("id", ""), content, dist)

    except Exception:
        pass

    return None


def handle_session_start(input_data: Dict[str, Any]) -> None:
    """
    SessionStart Hook Handler:
    Injects Cephalo orientation into the agent's persistent conversation trajectory.
    """
    profile_summary = ""
    if PROFILE_FILE.exists():
        profile_summary = " User profile active with cinema preferences (TCL 65T8B TV), hardware specs, and project specialties."

    welcome_text = (
        "🧠 Cephalo Second Brain is active and mounted at "
        r"C:\Users\strider-desktop\.gemini\antigravity\scratch\second-brain."
        + profile_summary +
        " Ground decisions in USER_PROFILE.md and use `cephalo search` / `cephalo specialty` commands."
    )

    response = {
        "injectSteps": [
            {
                "systemMessage": {
                    "systemMessage": welcome_text
                }
            }
        ]
    }
    print(json.dumps(response, ensure_ascii=False))


def handle_pre_invocation(input_data: Dict[str, Any]) -> None:
    """
    PreInvocation Hook Handler:
    1. Harvests every user prompt from the transcript into prompts.jsonl.
    2. Checks if latest prompt touches known preferences/hardware.
    3. If NO: stays 100% silent (outputs {"injectSteps": []}) -> 0 tokens wasted.
    4. If YES: injects a compact, 1-line ephemeral context snippet.
    """
    conv_id = input_data.get("conversationId", "unknown")
    transcript_path_str = input_data.get("transcriptPath", "")

    latest_user_text = ""
    if transcript_path_str:
        tpath = Path(transcript_path_str)
        if tpath.exists():
            state = load_state()
            conv_state = state.get("processed_conversations", {}).get(conv_id, {"last_step": -1})
            last_step = conv_state.get("last_step", -1)

            new_msgs = extract_user_messages(tpath, last_step)
            if new_msgs:
                max_step = max(m["step_index"] for m in new_msgs)
                harvest_all_user_prompts(new_msgs, conv_id)
                if "processed_conversations" not in state:
                    state["processed_conversations"] = {}
                state["processed_conversations"][conv_id] = {
                    "last_step": max_step,
                }
                save_state(state)
                latest_user_text = new_msgs[-1]["content"]

    inject_steps = []
    if latest_user_text:
        match = query_relevant_memory(latest_user_text)
        if match:
            mid, content, dist = match
            # Format clean, compact 1-line memory snippet
            snippet = content[:180] + ("..." if len(content) > 180 else "")
            inject_steps.append({
                "ephemeralMessage": f"🧠 [Cephalo Active Memory | {mid}]: {snippet}"
            })

    # Output strictly token-efficient response
    print(json.dumps({"injectSteps": inject_steps}, ensure_ascii=False))


def handle_stop_hook(input_data: Dict[str, Any]) -> None:
    """Stop Hook Handler: Final harvest sweep on turn completion."""
    conv_id = input_data.get("conversationId", "unknown")
    transcript_path_str = input_data.get("transcriptPath", "")

    if transcript_path_str:
        tpath = Path(transcript_path_str)
        if tpath.exists():
            state = load_state()
            conv_state = state.get("processed_conversations", {}).get(conv_id, {"last_step": -1})
            last_step = conv_state.get("last_step", -1)
            new_msgs = extract_user_messages(tpath, last_step)
            if new_msgs:
                max_step = max(m["step_index"] for m in new_msgs)
                harvest_all_user_prompts(new_msgs, conv_id)
                if "processed_conversations" not in state:
                    state["processed_conversations"] = {}
                state["processed_conversations"][conv_id] = {
                    "last_step": max_step,
                }
                save_state(state)

    print(json.dumps({}))


def run_standalone_scan(transcript_path: Optional[str] = None) -> None:
    """Scans conversation transcripts across the workspace and logs all user prompts."""
    state = load_state()
    total_new = 0

    if transcript_path:
        tpath = Path(transcript_path)
        if not tpath.exists():
            print(f"Transcript path not found: {tpath}")
            return
        conv_id = tpath.parent.parent.parent.name
        new_msgs = extract_user_messages(tpath, -1)
        count = harvest_all_user_prompts(new_msgs, conv_id)
        print(f"Scanned {tpath.name}: {count} user prompts harvested into Cephalo.")
        return

    brain_dir = Path(r"C:\Users\strider-desktop\.gemini\antigravity\brain")
    if not brain_dir.exists():
        print("Brain directory not found.")
        return

    transcripts = list(brain_dir.glob("*/.system_generated/logs/transcript.jsonl"))
    print(f"Scanning {len(transcripts)} conversation transcripts for user prompts...")

    for tpath in transcripts:
        conv_id = tpath.parent.parent.parent.name
        conv_state = state.get("processed_conversations", {}).get(conv_id, {"last_step": -1})
        last_step = conv_state.get("last_step", -1)
        new_msgs = extract_user_messages(tpath, last_step)
        if new_msgs:
            max_step = max(m["step_index"] for m in new_msgs)
            count = harvest_all_user_prompts(new_msgs, conv_id)
            if "processed_conversations" not in state:
                state["processed_conversations"] = {}
            state["processed_conversations"][conv_id] = {
                "last_step": max_step,
            }
            total_new += count

    save_state(state)
    print(f"Cephalo Audit Complete: {total_new} user prompts indexed and tracked.")


def main():
    parser = argparse.ArgumentParser(description="Cephalo Harvester & Context Injector")
    parser.add_argument("--hook", action="store_true", help="Auto-detect hook payload on stdin")
    parser.add_argument("--session-start", action="store_true", help="Run in SessionStart hook mode")
    parser.add_argument("--pre-invocation", action="store_true", help="Run in PreInvocation hook mode")
    parser.add_argument("--stop-hook", action="store_true", help="Run in Stop hook mode")
    parser.add_argument("--scan", action="store_true", help="Scan and audit all past transcripts")
    parser.add_argument("--transcript", type=str, help="Specific transcript file to scan")
    args = parser.parse_args()

    # Read stdin if in a hook mode
    if args.hook or args.session_start or args.pre_invocation or args.stop_hook or (not sys.stdin.isatty() and not args.scan and not args.transcript):
        input_data = {}
        try:
            raw = sys.stdin.read()
            if raw.strip():
                input_data = json.loads(raw)
        except Exception:
            pass

        if args.session_start:
            handle_session_start(input_data)
        elif args.pre_invocation or "invocationNum" in input_data:
            handle_pre_invocation(input_data)
        else:
            handle_stop_hook(input_data)
    else:
        run_standalone_scan(args.transcript)


if __name__ == "__main__":
    main()

run_standalone_harvest = run_standalone_scan

#!/usr/bin/env python3
"""
Cephalo Autonomous Memory Harvester (auto_harvest.py)
====================================================
Designed to run automatically via Antigravity lifecycle hooks (Stop / PostInvocation)
or on-demand via `cephalo harvest` / `python auto_harvest.py`.

Zero-friction memory capture:
- Analyzes conversation transcripts for user preferences, dislikes, hardware specs, and decisions.
- Automatically logs detected insights into prompts.jsonl and syncs with LanceDB.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Base Paths
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
PROMPTS_FILE = DATA_DIR / "prompts.jsonl"
STATE_FILE = DATA_DIR / "harvest_state.json"
PROFILE_FILE = SCRIPT_DIR / "USER_PROFILE.md"

# Regular expression cues indicating persistent preferences or feedback
PREFERENCE_SIGNALS = [
    # Dislikes / Critiques
    (r"\b(found it boring|too slow|too grey|waste our time|didn't like|dislike|hated?|terrible|not what we were looking for)\b", "critique_negative_filter"),
    # Preferences / Likes
    (r"\b(we loved?|prefer|preference|favorite|really liked?|enjoyed|looking for)\b", "user_preference"),
    # Hardware / Device setup
    (r"\b(my tv is|my monitor is|my setup|hardware|graphics card|gpu|resolution|screen size)\b", "hardware_spec"),
    # Directives / Workflows
    (r"\b(should always|never do|always use|my rule is|by default|from now on)\b", "workflow_rule"),
    # First language / regional
    (r"\b(first language|native language|hungarian|magyar|marketplace)\b", "language_locale"),
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
    """Extract unprocessed USER_INPUT steps from transcript.jsonl."""
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
                        # Strip outer tags
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


def analyze_and_harvest(messages: List[Dict[str, Any]], conversation_id: str = "") -> int:
    """Analyze messages for signals and record into prompts.jsonl."""
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
        detected_categories = []
        for pattern, cat in PREFERENCE_SIGNALS:
            if re.search(pattern, text, re.IGNORECASE):
                detected_categories.append(cat)

        if detected_categories:
            primary_cat = detected_categories[0]
            # Check if identical content already recorded
            if text in existing_contents:
                continue

            # Create prompt entry
            prompt_id = f"prompt-auto-{abs(hash(text)) % 1000000:06d}"
            entry = {
                "id": prompt_id,
                "timestamp": msg.get("timestamp") or "",
                "source": "auto_harvester",
                "category": primary_cat,
                "conversation_id": conversation_id,
                "content": text,
                "extracted_intent": f"Autonomously harvested from conversation turn: {primary_cat}",
                "detected_signals": detected_categories,
            }

            try:
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                with open(PROMPTS_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                existing_contents.add(text)
                harvested_count += 1
            except Exception:
                pass

    return harvested_count


def process_hook_payload() -> None:
    """Reads stdin from Antigravity lifecycle hook and executes harvesting."""
    input_data = {}
    try:
        raw_input = sys.stdin.read()
        if raw_input.strip():
            input_data = json.loads(raw_input)
    except Exception:
        pass

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
                harvested = analyze_and_harvest(new_msgs, conv_id)
                if "processed_conversations" not in state:
                    state["processed_conversations"] = {}
                state["processed_conversations"][conv_id] = {
                    "last_step": max_step,
                    "last_harvested": harvested,
                }
                save_state(state)

    # Output valid hook response to stdout
    print(json.dumps({}))


def run_standalone_harvest(transcript_path: Optional[str] = None) -> None:
    """Scan past conversation transcripts."""
    state = load_state()
    total_new = 0

    if transcript_path:
        tpath = Path(transcript_path)
        if not tpath.exists():
            print(f"Transcript path not found: {tpath}")
            return
        conv_id = tpath.parent.parent.parent.name
        new_msgs = extract_user_messages(tpath, -1)
        count = analyze_and_harvest(new_msgs, conv_id)
        print(f"Scanned {tpath.name}: {count} new preference items harvested.")
        return

    brain_dir = Path(r"C:\Users\strider-desktop\.gemini\antigravity\brain")
    if not brain_dir.exists():
        print("Brain directory not found.")
        return

    transcripts = list(brain_dir.glob("*/.system_generated/logs/transcript.jsonl"))
    print(f"Scanning {len(transcripts)} conversation transcripts for unharvested preferences...")

    for tpath in transcripts:
        conv_id = tpath.parent.parent.parent.name
        conv_state = state.get("processed_conversations", {}).get(conv_id, {"last_step": -1})
        last_step = conv_state.get("last_step", -1)
        new_msgs = extract_user_messages(tpath, last_step)
        if new_msgs:
            max_step = max(m["step_index"] for m in new_msgs)
            count = analyze_and_harvest(new_msgs, conv_id)
            if "processed_conversations" not in state:
                state["processed_conversations"] = {}
            state["processed_conversations"][conv_id] = {
                "last_step": max_step,
                "last_harvested": count,
            }
            total_new += count

    save_state(state)
    print(f"Autonomous Harvest Complete: {total_new} new memory items captured into Cephalo.")


def main():
    parser = argparse.ArgumentParser(description="Cephalo Autonomous Harvester")
    parser.add_argument("--hook", action="store_true", help="Run in Antigravity lifecycle hook mode (reads JSON from stdin)")
    parser.add_argument("--transcript", type=str, help="Specific transcript file to scan and harvest")
    args = parser.parse_args()

    if args.hook:
        process_hook_payload()
    else:
        run_standalone_harvest(args.transcript)


if __name__ == "__main__":
    main()

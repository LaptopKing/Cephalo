# Claude Code Configuration & Cephalo Protocol

This file informs **Claude Code** (and compatible agent harnesses) on how to operate inside the user's **Cephalo** sovereign memory environment.

## Environment & Commands

- **Root Directory:** `C:\Users\strider-desktop\.gemini\antigravity\scratch\second-brain`
- **Main CLI Entrypoint:** `cephalo` (or `python brain.py`)

## Common Commands

- Check Cephalo Health: `cephalo status`
- Query Memory (Hybrid Search): `cephalo search "<query>" --json`
- Audit & Ingest Transcripts: `cephalo harvest`
- Live Web Research: `cephalo web "<query>" --limit 5`
- Dynamic Page Scraping: `cephalo fetch "<url>" --dynamic`
- Manage Specialties: `cephalo specialty [list|read|create|edit|delete]`
- Outbound Email: `cephalo email [status|send]`
- Save New Insight / Decision: `cephalo record "<text>" --category "<cat>"`
- Read User Profile: `cephalo profile`
- Run Tests: `python -m unittest discover -s . -p "test_*.py"`

## Core Autonomous Invariants

1. **Zero-Friction Autonomous Learning:** Cephalo learns automatically. If the user expresses a preference, taste, hardware spec, critique, or decision, record it immediately via `cephalo record` or update `USER_PROFILE.md`. The user should never have to manually instruct the agent to save preferences.
2. **Token Efficiency & Silence Rule:** When consulting past context, only inject memories when they directly add concrete, relevant value to the current query. If a user brings up a completely new topic never discussed before, stay silent (zero context tokens wasted) while still logging the prompt into Cephalo's memory.
3. **Read `USER_PROFILE.md`:** Ground your reasoning in the user's verified hardware (TCL 65T8B 4K QLED TV, Acer display), communication tone (direct, technical, objective, minimal fluff), and language baseline (Hungarian & English).
4. **Never bypass `cephalo` for storage:** All entries must pass through the multi-tier local sanitizer before touching LanceDB or JSONL logs.

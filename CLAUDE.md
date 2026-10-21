# Claude Code Configuration & Cephalo Protocol

This file informs **Claude Code** on how to operate inside the user's **Cephalo** environment.

## Environment & Commands

- **Root Directory:** `C:\Users\strider-desktop\.gemini\antigravity\scratch\second-brain`
- **Main CLI Entrypoint:** `cephalo` (or `python brain.py`)

## Common Commands

- Check Cephalo Health: `cephalo status`
- Query Memory (Hybrid Search): `cephalo search "<query>" --json`
- Live Web Research: `cephalo web "<query>" --limit 5`
- Dynamic Page Scraping: `cephalo fetch "<url>" --dynamic`
- Manage Specialties: `cephalo specialty [list|read|create|edit|delete]`
- Outbound Email: `cephalo email [status|send]`
- Save New Insight / Decision: `cephalo record "<text>" --category "<cat>"`
- Run Tests: `python -m unittest discover -s . -p "test_*.py"`
- Read User Profile: `cephalo profile`

## Memory & Behavior Directives

1. **Read `USER_PROFILE.md` first:** Align with user's tone (direct, technical, objective, minimal fluff) and language preferences (Hungarian + English).
2. **Read `AGENTS.md`:** Contains full agent protocol details.
3. **Never bypass `cephalo` for storage:** All entries must pass through the multi-tier local sanitizer before touching LanceDB or JSONL logs.

# Claude Code Configuration & Cephalo Memory Protocol

This file informs **Claude Code** on how to operate inside the user's **Cephalo** Second Brain environment.

## Environment & Commands

- **Python Runtime:** `C:\Users\strider-desktop\AppData\Local\Programs\Python\Python312\python.exe`
- **Working Directory:** `C:\Users\strider-desktop\.gemini\antigravity\scratch\second-brain`
- **Main Interface:** `brain.py`

## Common Commands

- Check Brain Status: `python brain.py status`
- Query Memory (Hybrid Search): `python brain.py search "<query>" --json`
- Manage Specialties: `python brain.py specialty [list|read|create|edit|delete]`
- Outbound Email: `python brain.py email [status|send]`
- Save New Insight / Decision: `python brain.py record "<text>" --category "<cat>"`
- Run Tests: `python -m unittest test_embedding_pipeline.py`
- Read User Profile: `python brain.py profile`

## Memory & Behavior Directives

1. **Read `USER_PROFILE.md` first:** Align with user's tone (direct, technical, objective, minimal fluff) and language (Hungarian + English).
2. **Read `AGENTS.md`:** Contains full agent protocol details.
3. **Never bypass `brain.py` for storage:** All entries must pass through the multi-tier local sanitizer before touching LanceDB or JSONL logs.

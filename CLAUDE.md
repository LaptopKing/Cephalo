# Claude Code Configuration & Cephalo Protocol

This file informs **Claude Code** (and compatible agent harnesses) on how to operate inside the user's sovereign **Cephalo** second brain environment.

---

## 1. Environment & Connectivity

- **Root Directory:** `C:\Users\strider-desktop\.gemini\antigravity\scratch\second-brain`
- **Main CLI Entrypoint:** `cephalo` (or `python brain.py`)
- **Native MCP Server:** `python C:\Users\strider-desktop\.gemini\antigravity\scratch\second-brain\mcp_server.py`
  - Add to Claude Code via: `claude mcp add cephalo python "C:\Users\strider-desktop\.gemini\antigravity\scratch\second-brain\mcp_server.py"`

---

## 2. Common Commands

| Task | Command |
| :--- | :--- |
| **Check System & Memory Status** | `cephalo status` |
| **Hybrid Search (Dense + Keyword)** | `cephalo search "<query>" --json` |
| **Record Decision / Preference** | `cephalo record "<statement>" --category "<category>"` |
| **User Profile Blueprint** | `cephalo profile` |
| **Continuous Learning Cycle** | `cephalo learn run` |
| **Continuous Learning Status** | `cephalo learn status` |
| **Always-On Background Daemon** | `cephalo daemon [start\|status\|stop]` |
| **Launch MCP Server** | `cephalo mcp` |
| **List Domain Specialties** | `cephalo specialty list` |
| **Read Specialty Knowledge** | `cephalo specialty read <slug> --project <proj>` |
| **Auto-Synthesize Specialty** | `cephalo specialty auto-create "<technology>"` |

---

## 3. Core Autonomous Invariants

1. **Autonomous Continuous Learning:** Cephalo learns automatically. If the user expresses a preference, hardware constraint, negative critique (*"too slow"*, *"too grey"*, *"not what we wanted"*), or makes an architectural decision, record it immediately via `cephalo record` or update `USER_PROFILE.md`. The user should NEVER have to say "did you save this?".
2. **Grounding in User Profile:** Ground your reasoning in [`USER_PROFILE.md`](USER_PROFILE.md):
   - Living room display: **TCL 65T8B** (65-inch 4K QLED Google TV).
   - Cinema aesthetic: Eye-popping, vibrant, high-saturation 4K; instant velocity from minute 1; anti-grey/anti-slowburn.
   - Communication: Direct, technical, pragmatic, clean markdown, no fluff.
   - Language: Hungarian (native primary) & English.
3. **Anti-Slop Software Engineering Discipline:** Strictly follow the `global:coding-craftsmanship` specialty:
   - Matt Pocock rules: specs before tickets, tickets before code, vertical slices.
   - Linux kernel rules: functions fit on 1-2 screens, maximum 3 levels of indentation, explicit error handling at call sites, no swallowed exceptions, zero dead code.
4. **Token Efficiency:** When consulting past context, only inject memories when they directly add concrete value. If a query touches completely new topics never discussed before, stay silent while still logging the prompt.

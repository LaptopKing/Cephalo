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
| **Deep Research Topic** | `cephalo research "<topic>" [--create]` |
| **Research & Create Specialty** | `cephalo specialty research "<topic>"` |
| **List Domain Specialties** | `cephalo specialty list` |
| **Read Specialty Knowledge** | `cephalo specialty read <slug> --project <proj>` |
| **Auto-Synthesize Specialty** | `cephalo specialty auto-create "<technology>"` |

---

## 3. Core Autonomous Invariants

1. **Autonomous Continuous Learning & Research by Default:** Cephalo continuously learns and triggers research and specialty creation **by default and on demand**. When a new technology, framework, architecture, or subtopic is introduced in conversation, project manifests, or specs, Cephalo proactively investigates it using the user's standards (first principles, industry standards, anti-slop engineering, top GitHub projects with stars) and registers a specialty.
2. **The User's Deep Research Methodology:**
   - Matt Pocock "Skills for Real Engineers" (specs before tickets, tickets before code, vertical slices, structured grilling).
   - Linux Kernel conventions (functions on 1-2 screens, max 3 indent levels, early returns, minimal indirection, explicit error handling, strict type boundaries, Rule of Three).
   - Top GitHub projects: automated search and API verification of stars, descriptions, and reference patterns.
   - UI/UX & Human-Centered heuristics (when applicable): WCAG 2.1 AA, 4 states (skeleton/error/empty/populated), 44px tap targets, bottom thumb zone, stone/pastel palette.
3. **Automatic by Default (Zero-Manual-Trigger Invariant):** Any new feature added to Cephalo MUST work automatically without requiring manual commands or intervention, unless explicitly instructed or designed as an interactive CLI command.
3. **English Language Invariant:** ALWAYS respond in English across all sessions. All projects, codebases, documentation, and user interfaces must be developed in English by default, unless explicitly requested otherwise.
4. **Grounding in User Profile:** Ground your reasoning in [`USER_PROFILE.md`](USER_PROFILE.md):
   - Living room display: **TCL 65T8B** (65-inch 4K QLED Google TV).
   - Cinema aesthetic: Eye-popping, vibrant, high-saturation 4K; instant velocity from minute 1; anti-grey/anti-slowburn.
   - Communication: Direct, technical, pragmatic, clean markdown, no fluff.
5. **Anti-Slop Software Engineering Discipline:** Strictly follow the `global:coding-craftsmanship` specialty:
   - Matt Pocock rules: specs before tickets, tickets before code, vertical slices.
   - Linux kernel rules: functions fit on 1-2 screens, maximum 3 levels of indentation, explicit error handling at call sites, no swallowed exceptions, zero dead code.
6. **Token Efficiency:** When consulting past context, only inject memories when they directly add concrete value. If a query touches completely new topics never discussed before, stay silent while still logging the prompt.

# Universal Agent Protocol & Cephalo Sovereign Memory Interface

> **Universal Standard for All AI Agent Harnesses**
> **Compatible with: Google Antigravity, Claude Code, Cursor IDE, Windsurf, OpenAI Codex, GitHub Copilot CLI, Aider, Zed, Continue.dev**

Welcome, AI Agent. This repository is the user's sovereign, local-first cognitive coprocessor and memory core, named **Cephalo**. It stores long-term memory, technical decisions, preferences, domain specialties, and dynamic blueprints.

---

## 1. Core Principles (Non-Negotiable)

1. **Agent-Agnostic Portability:** Cephalo is designed to be completely sovereign and operable by ANY modern AI harness via:
   - **Model Context Protocol (MCP):** Connect directly via `python mcp_server.py`.
   - **Deterministic CLI Tooling:** Run `cephalo <command>` (or `python brain.py <command>`).
   - **Cross-Harness Configurations:** Native `.cursorrules`, `.windsurfrules`, `CLAUDE.md`, and `integrations/`.
2. **Autonomous Continuous Learning:** Cephalo's primary goal during development is to continuously and autonomously learn the user's coding style, workflow preferences, and personal tastes. If the user expresses a preference, taste, hardware spec, negative critique (*"too slow"*, *"too grey"*, *"not what we wanted"*), or makes an architectural decision, record it immediately via `cephalo record` or via MCP `cephalo_record`. The user should NEVER have to manually remind you to save preferences.
3. **Automatic Features by Default:** Whenever adding any new feature or capability to Cephalo, it MUST function automatically in the background without requiring manual triggering or human intervention, unless explicitly designed as a manual command.
4. **English Language Invariant:** The AI agent MUST ALWAYS respond in English across all sessions. All projects, codebases, documentation, and user interfaces must be developed in English by default, unless explicitly requested otherwise.
5. **Security & Data Sovereignty First:** 100% local-first. Never leak un-sanitized credentials, tokens, or PII into external logs, third-party clouds, or public repositories. All data passes through the multi-tier local sanitizer before storage.
6. **Token Efficiency & Silence Invariant:** Only inject past memories when they directly add concrete, relevant value to the current query. If a user brings up a completely new topic never discussed before, stay silent (zero context tokens wasted) while still logging the prompt into Cephalo's memory.
7. **Grounding in User Profile:** Read [`USER_PROFILE.md`](USER_PROFILE.md). Adhere strictly to the user's communication style (direct, technical, pragmatic, minimal fluff), verified hardware (TCL 65T8B 4K QLED TV, Acer monitor), and language preferences (Hungarian native primary & English).

---

## 2. Universal Agent Interfaces

### A. Model Context Protocol (MCP) — Recommended for All Modern IDEs & Agents

Cephalo includes a built-in stdio MCP server (`mcp_server.py`). Compatible out-of-the-box with **Claude Code**, **Cursor**, **Windsurf**, **Zed**, and **Claude Desktop**:

```bash
# Add to Claude Code:
claude mcp add cephalo python "C:\Users\strider-desktop\.gemini\antigravity\scratch\second-brain\mcp_server.py"

# Test or launch stdio server:
cephalo mcp
```

**Exposed MCP Tools:**
- `cephalo_search`: Hybrid dense Qwen vector + BM25 keyword search.
- `cephalo_record`: Sanitize, embed, and permanently store decisions/preferences.
- `cephalo_get_profile`: Retrieve `USER_PROFILE.md`.
- `cephalo_deep_research`: Autonomous deep research into topics/subtopics (fundamentals, standards, GitHub repos).
- `cephalo_list_specialties`: Enumerate active domain engineering modules.
- `cephalo_get_specialty`: Fetch verified fundamentals, key takeaways, and anti-slop rules.
- `cephalo_auto_create_specialty`: Autonomously synthesize a specialty for any novel technology.
- `cephalo_continuous_learn`: Run a continuous learning cycle across workspaces & manifests.
- `cephalo_learning_status`: Check continuous learning health and tracked stacks.

---

### B. CLI Interface (Any Shell, Terminal Agent, or Subprocess)

All operations can be executed via `cephalo` (or `python brain.py`):

```bash
# Search memory:
cephalo search "vector database" --json --limit 5

# Deep research topic & GitHub projects:
cephalo research "threejs-pbr-rendering" --create

# Research and create specialty module:
cephalo specialty research "temporal-workflows" --project "global"

# Record decision:
cephalo record "Using BullMQ with Redis for background queueing" --category "architecture"

# Run continuous learning cycle:
cephalo learn run

# Check continuous learning status:
cephalo learn status

# Always-On Background Daemon:
cephalo daemon status
cephalo daemon start
cephalo daemon stop
cephalo daemon install-task    # Auto-starts on Windows login

# Read profile:
cephalo profile

# List or create specialties:
cephalo specialty list
cephalo specialty auto-create "fastapi"
```

---

## 3. Harness Integrations Directory

See dedicated configuration templates in `integrations/`:
- `integrations/mcp/` — Standard MCP configuration.
- `integrations/claude-code/` — 1-click Claude Code setup.
- `integrations/cursor/` — `.cursorrules` and `.cursor/mcp.json`.
- `integrations/windsurf/` — `.windsurfrules` and Cascade config.
- `integrations/copilot/` — GitHub Copilot instructions.
- `integrations/aider/` — Aider pair programming configuration.
- `integrations/antigravity/` — Antigravity skill & hook bindings.

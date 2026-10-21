# User Profile & Preference Blueprint (Template)

> **Instructions for Setup:**
> 1. Copy this template to `USER_PROFILE.md`:
>    ```bash
>    cp USER_PROFILE.template.md USER_PROFILE.md
>    ```
> 2. Fill in your preferred values, hardware specs, language preferences, and principles.
> 3. `USER_PROFILE.md` is strictly ignored by `.gitignore` to safeguard your personal blueprint from public repositories.
> 4. AI agents (Antigravity, Claude Code, Cursor, Codex) read and update this profile via `python brain.py profile`.

---

## 1. Core Principles & Non-Negotiables
- **Security & Data Integrity First:** Absolute priority. Uncontrolled cloud logging, leaky third-party syncs, or un-sanitized credentials in memory databases are unacceptable.
- **Automated Privacy Filtering:** PII redaction and secret stripping must execute deterministically and locally, without relying on manual vigilance.
- **Incremental & Practical Architecture:** Tangible, working building blocks over over-engineered, theoretical monoliths.
- **Agent-Agnostic Portability:** Cephalo must remain fully operable by any AI agent harness via standard CLI commands (`brain.py`) and protocol files (`AGENTS.md`, `CLAUDE.md`).
- **Productivity & Life Automation:** Automate repetitive research, memory management, and context recall so human time focuses on creative, high-leverage tasks.

---

## 2. Communication & Response Style
- **Tone:** Direct, technical, pragmatic, and objective. [Customize: e.g., Academic / Conversational / Bulleted]
- **Structure:** Clean GitHub markdown, structured comparison tables, concise bullet points, and zero filler or unnecessary pleasantries.
- **Approach:** Challenge technical flaws or security oversights directly; propose concrete, actionable alternatives with verified code snippets.

---

## 3. Local Environment & Language Baseline
- **Primary Languages:** [e.g., English, Hungarian / Magyar, German, Japanese]
  - Multilingual semantic search and localized PII sanitization enabled.
- **Operating System:** [e.g., Windows 10/11, macOS Sequoia, Ubuntu 22.04 LTS]
- **Hardware Profile:**
  - **RAM:** [e.g., 8 GB / 16 GB / 32 GB]
  - **GPU / Accelerator:** [e.g., Integrated Intel Iris / NVIDIA GTX 1050 Ti (4GB VRAM) / Apple M-series / CPU-only]
  - **Python Runtime:** Python 3.10+ (Recommended: Python 3.12)
- **Embedding Strategy:** 100% Local-only via FastEmbed (e.g., `Qwen/Qwen3-Embedding-0.6B-Q` [1024d] or `BAAI/bge-small-en-v1.5` [384d]) and LanceDB. Zero cloud embedding calls required.
- **Agent Orchestrator:** Frontier AI agents (Antigravity, Claude Code, Codex, Cursor) running as the reasoning harness, querying the local LanceDB memory store via CLI.

---

## 4. Evolving Focus Areas & Projects
- **Current Objective:** [e.g., Bootstrapping personal knowledge base, automated code audit pipeline, research workflow]
- **Active Technical Topics:**
  - [e.g., Local vector databases & hybrid search with LanceDB]
  - [e.g., Multi-tier PII sanitization & credential entropy filtering]
  - [e.g., Multilingual embeddings & context compression]

---

## 5. Working Invariants
- **Storage Rule:** Never bypass `brain.py` when saving persistent insights.
- **Memory Deduplication:** Re-index unindexed files via `python brain.py sync`.
- **Search Rule:** Prefer `--json` output when feeding search results into automated agent context windows.

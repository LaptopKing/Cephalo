# Agent Protocol & Cephalo Memory Interface

> **Universal Standard for AI Agents (Antigravity, Claude Code, OpenAI Codex, Cursor, etc.)**

Welcome, AI Agent. This repository is the user's sovereign, local-first cognitive coprocessor and memory core, named **Cephalo**. It stores long-term memory, technical decisions, preferences, domain specialties, and dynamic blueprints.

---

## 1. Core Principles (Non-Negotiable)

1. **Security & Data Sovereignty First:** Never leak un-sanitized credentials, tokens, or PII into external logs, third-party clouds, or public repositories.
2. **Automated Sanitization:** Always use `cephalo` for reading and writing memories. It automatically scrubs Hungarian & international PII, passwords, and developer tokens locally before storage.
3. **Zero-Friction Autonomous Learning:** Cephalo learns automatically. If the user expresses a preference, taste, hardware spec, critique, or decision, record it immediately via `cephalo record` or update `USER_PROFILE.md`. The user should never have to manually remind you to save preferences.
4. **Token Efficiency & Silence Invariant:** Only inject past memories when they directly add concrete, relevant value to the current query. If a user brings up a completely new topic never discussed before, stay silent (zero context tokens wasted) while still logging the prompt into Cephalo's memory.
5. **Grounding in User Profile:** Read [`USER_PROFILE.md`](USER_PROFILE.md). Adhere strictly to the user's communication style (direct, technical, pragmatic, minimal fluff), verified hardware (TCL 65T8B 4K QLED TV, Acer monitor), and language preferences (Hungarian & English).

---

## 2. CLI Interface for Agents

All agent operations are executed via deterministic CLI commands using `cephalo` (or `python brain.py`).

### A. Recalling Context & Memories (Search)
Before answering questions about past decisions, preferences, or technical configurations, query Cephalo's vector database:

```bash
# Default: Hybrid search (Dense Qwen vectors + BM25 keyword matching)
cephalo search "marketplace watchdog"

# Machine-readable JSON output (recommended for automated agent pipelines)
cephalo search "vector database" --json --limit 5

# Pure keyword search (BM25 only)
cephalo search "FastAPI" --type fts

# With SQL metadata filtering
cephalo search "architecture" --where "category = 'security_constraint'"
```

### B. Ingesting New Memory (Record)
When the user expresses a new preference, makes a technical decision, or asks to remember something:

```bash
# Ingests, sanitizes locally, embeds via FastEmbed Qwen (1024d), and stores in LanceDB + prompts.jsonl
cephalo record "We decided to use Antigravity as the central orchestrator" --category "architecture" --source "agent"
```

### C. Auditing Transcripts & Capturing Prompts (Harvest)
Cephalo automatically audits conversation transcripts to keep track of every user prompt:

```bash
# Audits all workspace transcripts and extracts unindexed prompts and feedback:
cephalo harvest

# Scans a specific transcript:
cephalo harvest --transcript "path/to/transcript.jsonl"
```

### D. Live Web Research & Dynamic Crawling
When you need to research a topic or inspect an external URL:

```bash
# Zero-key live web search
cephalo web "LanceDB hybrid search tutorial" --limit 5 --json

# Search and automatically sanitize + record into Cephalo
cephalo web "Qwen embedding models" --record --category "ai_research"

# Static clean webpage fetch
cephalo fetch "https://example.com" --json

# Dynamic JavaScript-rendered page fetch (via Playwright Chromium)
cephalo fetch "https://example.com/spa" --dynamic --record
```

### E. Managing Domain Specialties (Specialties Layer)
Cephalo organizes domain expertise in a 3-tier hierarchy:
`Project` -> `Specialties (1-to-many)` -> `User Preferences (inherited constraints)`.

```bash
# List all active specialties
cephalo specialty list
cephalo specialty list --project "ecommerce" --json

# Read a specialty's verified knowledge & manifest
cephalo specialty read "pricing-strategy" --project "ecommerce" --json

# Create a new specialty
cephalo specialty create "pricing-strategy" --project "ecommerce" \
  --fundamentals "Core unit economics, elasticity, VAT handling..." \
  --takeaways "Start with value-based pricing; Monitor competitor APIs" \
  --preferences "security_first,hungarian_market_support"

# Edit an existing specialty
cephalo specialty edit "pricing-strategy" --notes "Updated unit margin targets"

# Delete a specialty (CRITICAL: MUST CONFIRM WITH USER)
cephalo specialty delete "pricing-strategy" --confirm
```

> **DELETION SAFETY CONTRACT:** Never execute `specialty delete` without direct, explicit confirmation from the human user.

### F. Outbound Email Communications (Email Layer)
Cephalo can send outbound emails (e.g. to sellers, partners, or daily summaries) via secure local SMTP using an App Password.

```bash
# Check email configuration
cephalo email status --json

# Send an email (requires --confirm)
cephalo email send --to "seller@example.com" --subject "Parts Inquiry" --body "Hello..." --confirm
```

> **TRANSMISSION SAFETY CONTRACT:** Never execute `email send` without direct, explicit confirmation from the human user.

### G. System Status & Health Check
```bash
cephalo status --json
```

---

## 3. How You Should Operate As An Agent

1. **At Conversation Start:**
   - Review [`USER_PROFILE.md`](USER_PROFILE.md) to understand active projects, display hardware, and language requirements.
2. **When Answering Inquiries:**
   - If the task depends on past user context, run `cephalo search "<topic>" --json` to retrieve relevant records from LanceDB.
3. **When Learning New Knowledge:**
   - When the user expresses a preference, critique, hardware spec, or architectural decision, run `cephalo record "<text>" --category "<cat>"`.

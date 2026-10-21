# Agent Protocol & Cephalo Memory Interface

> **Universal Standard for AI Agents (Antigravity, Claude Code, OpenAI Codex, Cursor, etc.)**

Welcome, AI Agent. This repository is the user's private, local-first Second Brain, codenamed **Cephalo** (orchestrator core + decentralized subagent arms). It stores their long-term memory, technical decisions, preferences, notes, and dynamic blueprints.

---

## 1. Core Principles (Non-Negotiable)

1. **Security & Data Integrity First:** Never leak un-sanitized credentials, tokens, or PII into external logs or third-party syncs.
2. **Automated Sanitization:** Always use `python brain.py` for reading and writing memories. It automatically scrubs Hungarian PII, passwords, and developer tokens locally before storage.
3. **Grounding in User Profile:** Before taking major architectural or workflow decisions, read [`USER_PROFILE.md`](file:///C:/Users/strider-desktop/.gemini/antigravity/scratch/second-brain/USER_PROFILE.md). Adhere strictly to the user's communication style (direct, technical, pragmatic, minimal fluff) and language preferences (Hungarian & English).

---

## 2. CLI Interface for Agents

All agent operations are executed via deterministic CLI commands using `python brain.py`.

```powershell
# Always use the local Python 3.12 environment
& "C:\Users\strider-desktop\AppData\Local\Programs\Python\Python312\python.exe" brain.py <command>
```

### A. Recalling Context & Memories (Search)
Before answering questions about past decisions, preferences, or technical configurations, query the vector database:

```powershell
# Default: Hybrid search (Dense Qwen vectors + BM25 keyword matching)
python brain.py search "Hungarian marketplace watchdog"

# Machine-readable JSON output (recommended for automated agent pipelines)
python brain.py search "vector database" --json --limit 5

# Pure keyword search (BM25 only)
python brain.py search "FastAPI" --type fts

# With SQL metadata filtering
python brain.py search "architecture" --where "category = 'security_constraint'"
```

### B. Ingesting New Memory (Record)
When the user expresses a new preference, makes a technical decision, or asks to remember something:

```powershell
# Ingests, sanitizes locally, embeds via FastEmbed Qwen (1024d), and stores in LanceDB + prompts.jsonl
python brain.py record "We decided to use Antigravity as the central orchestrator" --category "architecture" --source "agent"
```

### C. Managing Project Specialties (Specialties Layer)
The Second Brain organizes domain expertise in a 3-tier hierarchy:
`Project` -> `Specialties (1-to-many)` -> `User Preferences (inherited constraints)`.

```powershell
# List all active specialties
python brain.py specialty list
python brain.py specialty list --project "ecommerce" --json

# Read a specialty's verified knowledge & manifest
python brain.py specialty read "pricing-strategy" --project "ecommerce"
python brain.py specialty read "pricing-strategy" --json

# Create a new specialty (registers fundamentals, curated GitHub repos, and binds user preferences)
python brain.py specialty create "Pricing Strategy" --project "ecommerce" \
  --fundamentals "Core unit economics, elasticity, Hungarian VAT handling..." \
  --repos '[{"name": "pricing-engine", "url": "https://github.com/...", "stars": 850}]' \
  --takeaways "Start with value-based pricing; Monitor competitor APIs" \
  --preferences "security_first,hungarian_market_support"

# Edit an existing specialty
python brain.py specialty edit "pricing-strategy" --notes "Updated unit margin targets"

# Delete a specialty (CRITICAL: MUST CONFIRM WITH USER)
python brain.py specialty delete "pricing-strategy" --confirm
```

> **DELETION SAFETY CONTRACT:** Never execute `specialty delete` without direct, explicit confirmation from the human user.

### D. Outbound Email Communications (Email Layer)
The Second Brain can send outbound emails (e.g. to sellers, partners, or daily summaries) via secure local SMTP using an App Password.

```powershell
# Check email configuration
python brain.py email status
python brain.py email status --json

# Send an email (requires --confirm)
python brain.py email send --to "seller@example.com" --subject "Subaru Parts Inquiry" --body "Hello..." --confirm
python brain.py email send --to "seller@example.com" --subject "Subaru Parts Inquiry" --body-file "draft.txt" --confirm
```

> **TRANSMISSION SAFETY CONTRACT:** Never execute `email send` without direct, explicit confirmation from the human user.

### E. System Status & Health Check
```powershell
python brain.py status
python brain.py status --json
```

### F. Reading the User Blueprint
```powershell
python brain.py profile
```

---

## 3. How You Should Operate As An Agent

1. **At Conversation Start:**
   - Review [`USER_PROFILE.md`](file:///C:/Users/strider-desktop/.gemini/antigravity/scratch/second-brain/USER_PROFILE.md) to understand active projects, language requirements, and constraints.
2. **When Answering User Inquiries:**
   - If the inquiry depends on personal context, run `python brain.py search "<topic>" --json` to retrieve relevant records from LanceDB.
3. **When Evolving the System:**
   - If the user changes an invariant principle or completes a major project milestone, update [`USER_PROFILE.md`](file:///C:/Users/strider-desktop/.gemini/antigravity/scratch/second-brain/USER_PROFILE.md) and record a prompt entry in LanceDB.

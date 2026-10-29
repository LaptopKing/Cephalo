# Cephalo CLI Reference

Cephalo is controlled entirely through deterministic, scriptable 1-line commands via `cephalo` (or `python brain.py`).

## Summary of Commands

| Command | Subcommands / Flags | Description |
| :--- | :--- | :--- |
| **`cephalo status`** | `--json` | Health check, table counts, and recent prompts. |
| **`cephalo record`** | `[text]`, `--clip`, `--category`, `--tag`, `--supersedes`, `--relates-to`, `--table` | Sanitize, embed, and store memory into LanceDB with automatic inline `#tag` extraction. |
| **`cephalo search`** | `[query]`, `--type hybrid\|vector\|fts`, `--tag`, `--limit`, `--all`, `--copy` | Search memory using hybrid dense + BM25 keyword matching with tag and supersession filtering. |
| **`cephalo webhook`** | `serve [--port]`, `status`, `send [text] [--category]` | Multi-channel quick capture HTTP webhook gateway (port 7434) for iOS, curl, and bots. |
| **`cephalo wiki`** | `generate`, `ask "<query>"`, `serve [--port]` | Sovereign codebase documentation, Q&A engine, and interactive timeline dashboard with 52-week heatmap. |
| **`cephalo pattern`** | `list`, `show <name>`, `run <name> [text] [--clip] [--copy]` | Execute cognitive prompt templates ("Reflexes"). |
| **`cephalo context`** | `export [--project <p>] [--specialty <s>] [--cinema] [--copy]` | Assemble consolidated system prompt context blocks. |
| **`cephalo youtube`** | `<url>`, `--pattern <p>`, `--record`, `--copy` | Extract YouTube video transcript and apply patterns. |
| **`cephalo fetch`** | `<url>`, `--dynamic`, `--youtube`, `--pattern`, `--record` | Clean webpage / SPA scraper with Chromium support. |
| **`cephalo web`** | `<query>`, `--limit`, `--markdown`, `--html`, `--open`, `--record` | Live web search with AI quick overview and SERP card. |
| **`cephalo specialty`** | `list`, `read <name>`, `create <name>`, `delete <name>` | Domain knowledge layer (`Project -> Specialties -> Preferences`). |
| **`cephalo daemon`** | `run`, `start`, `stop`, `status`, `install-task` | Always-on background continuous learning daemon with embedded webhook server. |
| **`cephalo mcp`** | | Model Context Protocol (MCP) stdio server for Claude Code / Cursor. |

---

## 1. Tagging Taxonomy & Hierarchical Tags

Cephalo automatically extracts inline `#tags` and hierarchical `#category/subcategory` tags directly from prompt text:

```bash
# Ingest with automatic inline tag extraction:
cephalo record "Switched production cache to Redis 7 with cluster mode enabled #backend/cache #infra #redis" --category "tech_stack"

# Explicitly attach tags via CLI flag:
cephalo record "PostgreSQL connection pooling tuned to max 50" --category "tech_stack" --tag "db/postgres" --tag "production"

# Filter searches strictly by tag:
cephalo search "connection pooling" --tag "db/postgres"

# Tag matching is case-insensitive and supports parent tags:
cephalo search "caching strategies" --tag "backend/cache"
```

Tags are indexed directly as Apache Arrow list columns in LanceDB (`tags: list<string>`) and can be filtered natively via `array_has(tags, '<tag>')`.

---

## 2. Memory Relations & Supersession Links

When decisions change or architectural patterns are upgraded, older memories can be explicitly linked and superseded:

```bash
# Record an upgrade that supersedes an earlier decision:
cephalo record "Migrated auth from JWT in cookies to WebAuthn passkeys #auth/security" \
  --category "architecture" \
  --supersedes "prompt-042" \
  --relates-to "prompt-015,prompt-088"
```

- **Automatic Deprecation:** Specifying `--supersedes <id>` immediately flags the target record in LanceDB with `is_deprecated = true` and updates its `superseded_by` pointer.
- **Search Filtering:** `cephalo search` automatically hides deprecated memories so agents only retrieve active, current ground-truth.
- **Full History Access:** Pass `--all` or `--include-deprecated` to search historical/superseded records:
  ```bash
  cephalo search "authentication method" --all
  ```

---

## 3. Multi-Channel Quick Capture HTTP Webhook Gateway

Cephalo provides a sovereign, local-first HTTP webhook ingress server running on port `7434`:

```bash
# Start standalone webhook server:
cephalo webhook serve --port 7434

# Check health and connectivity:
cephalo webhook status

# Quick capture via CLI helper:
cephalo webhook send "Remember to test LanceDB FTS index compaction #database" --category "todo"
```

### Ingress via cURL (Local or LAN)
```bash
curl -X POST http://127.0.0.1:7434/ingest \
  -H "Content-Type: application/json" \
  -d '{"text": "Refactored crawler to retry with exponential jitter #crawler/resilience", "category": "architecture"}'
```

### Remote Capture Integrations
- **iOS Shortcuts / Android Tasker:** Send notes directly from mobile share sheet to `http://<your-machine-ip>:7434/ingest`.
- **Raycast / Alfred:** Instant system-wide shortcut to capture fleeting thoughts into LanceDB.
- **Always-On Daemon:** When `cephalo daemon start` or `cephalo daemon run` is active, the webhook server runs automatically in the background.

---

## 4. Interactive DeepWiki & Activity Heatmap

Launch the sovereign DeepWiki dashboard with a 52-week GitHub/Memos-style contribution heatmap and reverse-chronological memory feed:

```bash
# 1. Regenerate Markdown documentation and index.html:
cephalo wiki generate

# 2. Launch dynamic DeepWiki server (opens in browser at http://127.0.0.1:7433):
cephalo wiki serve
```

### Dashboard Features
- **52-Week Activity Heatmap:** Visual SVG grid of daily memory ingestions over the past 365 days.
- **Reverse-Chronological Memory Feed:** Card-based browsing of memories with category badges, clickable `#tag` pills, and copy-to-clipboard buttons.
- **Live Tag & Category Filter:** Click any tag pill (e.g. `#tech_stack`, `#cinema/hdr`) to instantly filter the feed.
- **Zero-Latency In-Browser Quick Capture:** Ingest new memories directly from the dashboard (`Ctrl+Enter` to submit).
- **Embedded DeepWiki Documentation:** Read architecture specs, module reference, and privacy shields without leaving the dashboard.

---

## 5. Piping & Ergonomics

All commands natively support standard input and Windows clipboard:
```bash
# 1. Pipe git diff into sanitized memory:
git diff | cephalo record --category git_changes

# 2. Record text directly from Windows clipboard:
cephalo record --clip --category quick_note

# 3. Copy search results directly to clipboard:
cephalo search "PostgreSQL optimizations" --copy

# 4. Run cognitive pattern on clipboard text:
cephalo pattern run review_code --clip --copy
```

# Cephalo CLI Reference

Cephalo is controlled entirely through deterministic, scriptable 1-line commands via `cephalo` (or `python brain.py`).

## Summary of Commands

| Command | Subcommands / Flags | Description |
| :--- | :--- | :--- |
| **`cephalo status`** | `--json` | Health check, table counts, and recent prompts. |
| **`cephalo record`** | `[text]`, `--clip`, `--category`, `--table` | Sanitize, embed, and store memory into LanceDB. |
| **`cephalo search`** | `[query]`, `--type hybrid\|vector\|fts`, `--limit`, `--copy` | Search memory using hybrid dense + BM25 keyword matching. |
| **`cephalo pattern`** | `list`, `show <name>`, `run <name> [text] [--clip] [--copy]` | Execute cognitive prompt templates ("Reflexes"). |
| **`cephalo context`** | `export [--project <p>] [--specialty <s>] [--cinema] [--copy]` | Assemble consolidated system prompt context blocks. |
| **`cephalo youtube`** | `<url>`, `--pattern <p>`, `--record`, `--copy` | Extract YouTube video transcript and apply patterns. |
| **`cephalo fetch`** | `<url>`, `--dynamic`, `--youtube`, `--pattern`, `--record` | Clean webpage / SPA scraper with Chromium support. |
| **`cephalo web`** | `<query>`, `--limit`, `--markdown`, `--html`, `--open`, `--record` | Live web search with AI quick overview and SERP card. |
| **`cephalo specialty`** | `list`, `read <name>`, `create <name>`, `delete <name>` | Domain knowledge layer (`Project -> Specialties -> Preferences`). |
| **`cephalo wiki`** | `generate`, `ask "<query>"`, `serve` | Sovereign codebase documentation and local Q&A engine. |
| **`cephalo daemon`** | `run`, `start`, `stop`, `status`, `install-task` | Always-on background continuous learning daemon. |
| **`cephalo mcp`** | | Model Context Protocol (MCP) stdio server for Claude Code / Cursor. |

## Piping & Ergonomics

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

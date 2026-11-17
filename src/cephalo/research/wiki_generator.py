#!/usr/bin/env python3
"""
Cephalo - Sovereign Codebase Wiki & Codemap Engine (wiki_generator.py)
=====================================================================
Generates offline, private, interactive documentation and architectural codemaps
for Cephalo and user projects without leaking proprietary code to third-party clouds.

Features:
- AST-driven code inspection (classes, functions, typing, docstrings).
- Automatic Mermaid sequence and flowchart generation.
- Generates structured, publication-grade documentation under `docs/wiki/`.
- Local offline code Q&A via LanceDB hybrid search.
"""

from __future__ import annotations

import ast
import json
import logging
import datetime
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[3]
BASE_DIR = ROOT_DIR
DOCS_WIKI_DIR = ROOT_DIR / "docs" / "wiki"
DATA_DIR = ROOT_DIR / "data"
PROMPTS_FILE = DATA_DIR / "prompts.jsonl"
DEFAULT_LANCEDB_DIR = DATA_DIR / "lancedb"

logger = logging.getLogger("cephalo.wiki")


class CodeInspector:
    """Parses Python source code AST to extract architecture, signatures, and docstrings."""

    def analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """Inspects a single Python file and returns structured symbols."""
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except Exception as e:
            logger.warning("AST parse failed for %s: %s", file_path, e)
            return {"file": file_path.name, "error": str(e), "classes": [], "functions": []}

        module_doc = ast.get_docstring(tree) or ""
        classes = []
        functions = []
        imports = []

        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)

            elif isinstance(node, ast.ClassDef):
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append({
                            "name": item.name,
                            "doc": (ast.get_docstring(item) or "").split("\n")[0],
                            "args": [a.arg for a in item.args.args if a.arg != "self"],
                        })
                classes.append({
                    "name": node.name,
                    "doc": ast.get_docstring(node) or "",
                    "methods": methods,
                })

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append({
                    "name": node.name,
                    "doc": (ast.get_docstring(node) or "").split("\n")[0],
                    "args": [a.arg for a in node.args.args],
                })

        return {
            "file": file_path.name,
            "path": str(file_path),
            "doc": module_doc.strip(),
            "lines": len(source.splitlines()),
            "classes": classes,
            "functions": functions,
            "imports": sorted(list(set(imports))),
        }


class WikiGenerator:
    """Synthesizes structured documentation, codemaps, and Mermaid charts."""

    def __init__(self, root_dir: Optional[Path] = None, output_dir: Optional[Path] = None):
        self.root_dir = root_dir or BASE_DIR
        self.output_dir = output_dir or DOCS_WIKI_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.inspector = CodeInspector()

    def generate_all(self) -> List[Path]:
        """Generates the full suite of documentation files."""
        modules = self._scan_modules()

        gen_files = []
        gen_files.append(self._write_architecture(modules))
        gen_files.append(self._write_modules(modules))
        gen_files.append(self._write_cli_reference())
        gen_files.append(self._write_privacy_shield())
        gen_files.append(self._write_index(modules))
        gen_files.append(self._write_timeline_dashboard())

        return gen_files

    def _scan_modules(self) -> List[Dict[str, Any]]:
        """Scans all primary Python modules in the repository."""
        modules = []
        for p in sorted(self.root_dir.glob("*.py")):
            if p.name.startswith("test_") or p.name.startswith("patch_"):
                continue
            modules.append(self.inspector.analyze_file(p))
        return modules

    def _write_index(self, modules: List[Dict[str, Any]]) -> Path:
        """Writes docs/wiki/README.md."""
        target = self.output_dir / "README.md"
        lines = [
            "# Cephalo Sovereign DeepWiki",
            "",
            "> **Agent-Agnostic, Local-First Cognitive Coprocessor & Memory Engine**",
            "",
            "Welcome to the offline, sovereign architecture documentation and codemap for **Cephalo**.",
            "",
            "## Table of Contents",
            "- [1. System Architecture & Component Flow](ARCHITECTURE.md)",
            "- [2. Core Python Modules & API Reference](MODULES.md)",
            "- [3. Universal CLI & Command Reference](CLI_REFERENCE.md)",
            "- [4. Multi-Tier Zero-Leak Privacy Shield](SECURITY_PRIVACY.md)",
            "",
            "## Codebase Summary",
            f"- **Active Python Modules:** {len(modules)} core modules",
            f"- **Total Source Lines:** {sum(m.get('lines', 0) for m in modules):,} LOC",
            "- **Vector Storage:** Embedded LanceDB Columnar (Apache Arrow)",
            "- **Embeddings:** FastEmbed ONNX Runtime (Qwen 1024d Local)",
            "- **Subprocess Discipline:** Strictly enforces `CREATE_NO_WINDOW` (`0x08000000`) on Windows",
            "",
            "---",
            "*Generated autonomously by Cephalo Sovereign Wiki Engine.*",
        ]
        target.write_text("\n".join(lines), encoding="utf-8")
        return target

    def _write_architecture(self, modules: List[Dict[str, Any]]) -> Path:
        """Writes docs/wiki/ARCHITECTURE.md with Mermaid diagrams."""
        target = self.output_dir / "ARCHITECTURE.md"
        content = """# Cephalo System Architecture

Cephalo strictly decouples **high-order agent reasoning** (Antigravity, Claude Code, Cursor) from **sovereign local data storage, multi-tier privacy scrubbing, and cognitive reflex execution**.

## High-Level Execution Topology

```mermaid
flowchart TD
    User["User / Agent Prompt"] --> Harness["AI Agent Harness\n(Antigravity / Claude Code / Cursor)"]
    
    subgraph SovereignCore ["Cephalo Sovereign Core (Local Hardware)"]
        Harness --> CLI["Universal CLI (brain.py)"]
        
        CLI --> Sanitizer["Multi-Tier Privacy Shield\n(Regex + Entropy + AST + GLiNER)"]
        
        Sanitizer --> FastEmbed["FastEmbed Local ONNX\n(Qwen 1024d / Zero Cloud API)"]
        FastEmbed --> LanceDB[("LanceDB Columnar Vector Store\n(Native Dense + BM25 FTS)")]
        
        CLI --> Patterns["Cognitive Patterns Engine\n(extract_wisdom, review_code, etc.)"]
        CLI --> WebCrawler["Dynamic Web & YouTube Crawler\n(Playwright Chromium / Transcript API)"]
        CLI --> Context["Dynamic Context Assembler\n(USER_PROFILE.md + Specialties)"]
        
        WebCrawler --> Sanitizer
    end
    
    LanceDB -->|"Injected Context / JSON"| Harness
```

## Key Architectural Principles

1. **Local-First Sovereignty:**
   All vector computations (FastEmbed Qwen 1024d) and tabular storage (LanceDB) execute directly in-process via ONNX Runtime and Apache Arrow zero-copy memory. Zero monthly bills, zero per-token embedding costs, zero data leaving your machine.

2. **Zero-Leak Privacy Shield:**
   Every string ingested into Cephalo passes through a deterministic regex filter (tax IDs, IBANs, Hungarian PII), Shannon entropy guards (stripping high-entropy API tokens), and local named-entity masking before writing to disk.

3. **Unix-Philosophy Ergonomics:**
   All commands support `stdin` streaming (`cat file | cephalo record`), Windows clipboard reading/writing (`--clip`, `--copy`), and structured output (`--json`).
"""
        target.write_text(content, encoding="utf-8")
        return target

    def _write_modules(self, modules: List[Dict[str, Any]]) -> Path:
        """Writes docs/wiki/MODULES.md."""
        target = self.output_dir / "MODULES.md"
        lines = [
            "# Core Python Modules & API Reference",
            "",
            "Complete structural breakdown of Cephalo's active core modules.",
            "",
        ]

        for mod in modules:
            fname = mod["file"]
            lines.append(f"## [`{fname}`]({fname})")
            lines.append(f"**Lines of Code:** {mod.get('lines', 0)} | **Imports:** {len(mod.get('imports', []))}")
            if mod.get("doc"):
                first_doc = mod["doc"].split("\n\n")[0].strip()
                lines.append(f"\n> {first_doc}\n")

            if mod.get("classes"):
                lines.append("### Classes")
                for c in mod["classes"]:
                    lines.append(f"- **`{c['name']}`**")
                    if c.get("doc"):
                        lines.append(f"  *{c['doc'].splitlines()[0]}*")
                    if c.get("methods"):
                        lines.append("  **Methods:** " + ", ".join([f"`{m['name']}()`" for m in c["methods"][:6]]))

            if mod.get("functions"):
                lines.append("### Key Functions")
                for f in mod["functions"][:8]:
                    args_str = ", ".join(f.get("args", []))
                    lines.append(f"- `def {f['name']}({args_str})` — *{f.get('doc', 'No docstring')}*")

            lines.append("\n---\n")

        target.write_text("\n".join(lines), encoding="utf-8")
        return target

    def _write_cli_reference(self) -> Path:
        """Writes docs/wiki/CLI_REFERENCE.md."""
        target = self.output_dir / "CLI_REFERENCE.md"
        content = r"""# Cephalo CLI Reference

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
"""
        target.write_text(content, encoding="utf-8")
        return target

    def _write_privacy_shield(self) -> Path:
        """Writes docs/wiki/SECURITY_PRIVACY.md."""
        target = self.output_dir / "SECURITY_PRIVACY.md"
        content = """# Zero-Leak Privacy & Sanitization Shield

Cephalo guarantees that private notes, personal details, and sensitive credentials never leak to external model APIs, third-party vector databases, or public repositories.

## Multi-Tier Sanitization Architecture

```mermaid
flowchart LR
    Raw["Raw Prompt / Web Content"] --> T1A["Tier 1A: Regex Shield\n(PII, Tax IDs, IBANs, Phone, IPs)"]
    T1A --> T1B["Tier 1B: Entropy Guard\n(High-entropy API keys & tokens)"]
    T1B --> T1C["Tier 1C: AST Code Shield\n(Protects code syntax from NLP mangling)"]
    T1C --> T2["Tier 2: GLiNER / Presidio\n(Local Named-Entity Masking)"]
    T2 --> Clean["Sanitized Safe Payload\n(LanceDB & prompts.jsonl)"]
```

## Hungarian + English PII Redaction
Cephalo specifically handles:
- **Hungarian Tax Numbers (Adóazonosító):** 10-digit format (`8XXXXXXXXX`).
- **Hungarian IBANs:** Standard 28-character format.
- **Hungarian Phone Numbers:** Mobile and landline formats (`+36 20/30/70 ...`).
- **High-Entropy Tokens:** Base64, hex, and random tokens with Shannon entropy $> 4.3$.
"""
        target.write_text(content, encoding="utf-8")
        return target

    def _write_timeline_dashboard(self) -> Path:
        """Writes docs/wiki/index.html — the interactive Memory Timeline & Activity Heatmap dashboard."""
        target = self.output_dir / "index.html"
        style_target = self.output_dir / "style.css"

        templates_dir = Path(__file__).resolve().parent / "templates"
        css_content = (templates_dir / "dashboard_style.css").read_text(encoding="utf-8")
        html_content = (templates_dir / "dashboard_index.html").read_text(encoding="utf-8")

        style_target.write_text(css_content, encoding="utf-8")
        target.write_text(html_content, encoding="utf-8")
        return target


from cephalo.research.wiki_server import (
    DeepWikiServerHandler,
    get_heatmap_data,
    get_timeline_records,
    run_deepwiki_server,
)

__all__ = [
    "CodeInspector",
    "WikiGenerator",
    "DeepWikiServerHandler",
    "get_heatmap_data",
    "get_timeline_records",
    "run_deepwiki_server",
]

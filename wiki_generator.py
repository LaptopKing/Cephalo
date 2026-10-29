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

BASE_DIR = Path(__file__).resolve().parent
DOCS_WIKI_DIR = BASE_DIR / "docs" / "wiki"
DATA_DIR = BASE_DIR / "data"
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
        html = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Cephalo — Memory Timeline & Activity Heatmap</title>
  <style>
    :root {
      --bg: #090d16;
      --card-bg: #111827;
      --card-hover: #162032;
      --card-border: #1f293d;
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --accent: #10b981;
      --accent-glow: rgba(16, 185, 129, 0.2);
      --accent-cyan: #06b6d4;
      --tag-bg: #1e293b;
      --tag-text: #38bdf8;
      --deprecated-bg: #3f1d24;
      --deprecated-text: #f87171;
      --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text-main);
      font-family: var(--font-family);
      line-height: 1.5;
      padding-bottom: 60px;
    }
    a { color: var(--accent-cyan); text-decoration: none; }
    a:hover { text-decoration: underline; }

    /* Header */
    header {
      background: rgba(17, 24, 39, 0.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--card-border);
      position: sticky;
      top: 0;
      z-index: 100;
      padding: 14px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand h1 {
      font-size: 1.25rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .brand .badge-pulse {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.75rem;
      color: var(--accent);
      background: rgba(16, 185, 129, 0.1);
      padding: 3px 8px;
      border-radius: 999px;
      border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .brand .pulse-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--accent);
      box-shadow: 0 0 8px var(--accent);
    }
    .nav-tabs {
      display: flex;
      gap: 8px;
    }
    .nav-btn {
      background: transparent;
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      padding: 7px 14px;
      border-radius: 6px;
      font-size: 0.85rem;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .nav-btn:hover {
      background: var(--card-hover);
      color: var(--text-main);
    }
    .nav-btn.active {
      background: var(--accent);
      color: #000;
      border-color: var(--accent);
      font-weight: 600;
    }

    /* Main Container */
    .container {
      max-width: 1100px;
      margin: 24px auto;
      padding: 0 20px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    /* Cards */
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 20px;
    }
    .card-title {
      font-size: 0.95rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      margin-bottom: 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    /* Quick Capture */
    .capture-box {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .capture-textarea {
      width: 100%;
      min-height: 85px;
      background: #090d16;
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 12px 14px;
      color: var(--text-main);
      font-family: inherit;
      font-size: 0.92rem;
      resize: vertical;
      transition: border-color 0.2s;
    }
    .capture-textarea:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 2px var(--accent-glow);
    }
    .capture-actions {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
    }
    .capture-inputs {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .capture-select, .capture-input {
      background: #090d16;
      border: 1px solid var(--card-border);
      color: var(--text-main);
      padding: 6px 10px;
      border-radius: 6px;
      font-size: 0.82rem;
    }
    .btn-primary {
      background: var(--accent);
      color: #052e16;
      font-weight: 600;
      border: none;
      padding: 8px 18px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.88rem;
      transition: opacity 0.15s;
    }
    .btn-primary:hover {
      opacity: 0.9;
    }
    .toast {
      padding: 8px 14px;
      border-radius: 6px;
      font-size: 0.82rem;
      display: none;
    }
    .toast-success {
      background: rgba(16, 185, 129, 0.15);
      color: var(--accent);
      border: 1px solid rgba(16, 185, 129, 0.4);
    }

    /* Activity Heatmap */
    .heatmap-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      flex-wrap: wrap;
      gap: 10px;
    }
    .heatmap-stats {
      display: flex;
      gap: 18px;
      font-size: 0.82rem;
      color: var(--text-muted);
    }
    .heatmap-stats strong {
      color: var(--text-main);
    }
    .heatmap-container {
      overflow-x: auto;
      padding-bottom: 8px;
    }
    .heatmap-grid {
      display: grid;
      grid-template-rows: repeat(7, 13px);
      grid-auto-flow: column;
      grid-auto-columns: 13px;
      gap: 3px;
      width: max-content;
    }
    .heatmap-cell {
      width: 13px;
      height: 13px;
      border-radius: 2px;
      background: #161f30;
      cursor: pointer;
      position: relative;
      transition: transform 0.1s;
    }
    .heatmap-cell:hover {
      transform: scale(1.3);
      z-index: 50;
      outline: 1px solid #fff;
    }
    .heatmap-cell.level-0 { background: #161f30; }
    .heatmap-cell.level-1 { background: #064e3b; }
    .heatmap-cell.level-2 { background: #059669; }
    .heatmap-cell.level-3 { background: #10b981; }
    .heatmap-cell.level-4 { background: #34d399; }
    .heatmap-cell.selected {
      outline: 2px solid var(--accent-cyan);
      transform: scale(1.2);
    }
    .heatmap-legend {
      display: flex;
      align-items: center;
      gap: 5px;
      font-size: 0.75rem;
      color: var(--text-muted);
      margin-top: 10px;
      justify-content: flex-end;
    }
    .legend-box {
      width: 10px;
      height: 10px;
      border-radius: 2px;
    }

    /* Filter Bar */
    .filter-bar {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
      margin-bottom: 16px;
    }
    .search-input {
      flex: 1;
      min-width: 220px;
      background: #090d16;
      border: 1px solid var(--card-border);
      border-radius: 6px;
      padding: 8px 12px;
      color: var(--text-main);
      font-size: 0.88rem;
    }
    .filter-chips {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }
    .chip {
      background: #162032;
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 0.78rem;
      cursor: pointer;
      transition: all 0.15s;
    }
    .chip:hover, .chip.active {
      background: var(--tag-bg);
      color: var(--tag-text);
      border-color: var(--tag-text);
    }
    .active-filter-banner {
      background: rgba(6, 182, 212, 0.1);
      border: 1px solid rgba(6, 182, 212, 0.3);
      color: var(--accent-cyan);
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 0.82rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }
    .active-filter-banner button {
      background: transparent;
      border: none;
      color: var(--accent-cyan);
      font-weight: bold;
      cursor: pointer;
    }

    /* Memory Feed Cards */
    .timeline-stream {
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .memo-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 16px 18px;
      transition: border-color 0.15s, background 0.15s;
      position: relative;
    }
    .memo-card:hover {
      border-color: #2e3e5c;
      background: var(--card-hover);
    }
    .memo-card.deprecated {
      opacity: 0.65;
      border-color: rgba(239, 68, 68, 0.3);
    }
    .memo-meta {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
      font-size: 0.78rem;
      color: var(--text-muted);
      flex-wrap: wrap;
      gap: 6px;
    }
    .memo-badges {
      display: flex;
      gap: 6px;
      align-items: center;
    }
    .badge {
      padding: 2px 7px;
      border-radius: 4px;
      font-size: 0.72rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }
    .badge-id { background: #1e293b; color: #cbd5e1; }
    .badge-cat { background: rgba(16, 185, 129, 0.15); color: #34d399; }
    .badge-source { background: rgba(99, 102, 241, 0.15); color: #a5b4fc; }
    .badge-deprecated { background: var(--deprecated-bg); color: var(--deprecated-text); }
    .memo-content {
      font-size: 0.92rem;
      color: #e2e8f0;
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.6;
    }
    .memo-tags {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-top: 10px;
    }
    .tag-pill {
      background: var(--tag-bg);
      color: var(--tag-text);
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 0.75rem;
      cursor: pointer;
    }
    .tag-pill:hover {
      background: #0284c7;
      color: #fff;
    }
    .memo-relations {
      margin-top: 8px;
      font-size: 0.78rem;
      color: #a3e635;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .memo-footer {
      display: flex;
      justify-content: flex-end;
      margin-top: 8px;
    }
    .btn-copy {
      background: transparent;
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 0.75rem;
      cursor: pointer;
    }
    .btn-copy:hover {
      color: var(--text-main);
      background: #1f293d;
    }

    /* Docs View */
    #docs-view {
      display: none;
    }
    .docs-layout {
      display: grid;
      grid-template-columns: 240px 1fr;
      gap: 20px;
    }
    @media (max-width: 768px) {
      .docs-layout { grid-template-columns: 1fr; }
    }
    .docs-nav {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 12px;
      height: fit-content;
    }
    .docs-nav-link {
      display: block;
      padding: 8px 12px;
      color: var(--text-muted);
      border-radius: 6px;
      font-size: 0.85rem;
      margin-bottom: 4px;
    }
    .docs-nav-link:hover, .docs-nav-link.active {
      background: var(--card-hover);
      color: var(--text-main);
      text-decoration: none;
    }
    .docs-content {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 24px;
      min-height: 400px;
      line-height: 1.7;
    }
    .docs-content h1, .docs-content h2, .docs-content h3 {
      margin: 16px 0 10px;
      color: #fff;
    }
    .docs-content pre {
      background: #090d16;
      padding: 12px;
      border-radius: 6px;
      overflow-x: auto;
      margin: 12px 0;
      border: 1px solid var(--card-border);
      font-size: 0.85rem;
    }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <h1>🧠 CEPHALO</h1>
      <span class="badge-pulse"><span class="pulse-dot"></span> Sovereign Cognitive Coprocessor</span>
    </div>
    <div class="nav-tabs">
      <button class="nav-btn active" id="tab-timeline-btn" onclick="switchTab('timeline')">Feed & Heatmap</button>
      <button class="nav-btn" id="tab-docs-btn" onclick="switchTab('docs')">DeepWiki Docs</button>
    </div>
  </header>

  <div class="container">

    <!-- Timeline & Heatmap Tab Content -->
    <div id="timeline-view">
      
      <!-- Quick Capture -->
      <div class="card">
        <div class="card-title">
          <span>⚡ Quick Capture Memory</span>
          <span id="capture-status" class="toast toast-success">Memory Saved</span>
        </div>
        <div class="capture-box">
          <textarea id="capture-text" class="capture-textarea" placeholder="Capture a thought, architectural decision, or constraint (e.g. #hardware/display TCL 65T8B calibrated to Vivid HDR)..."></textarea>
          <div class="capture-actions">
            <div class="capture-inputs">
              <select id="capture-category" class="capture-select">
                <option value="quick_note">quick_note</option>
                <option value="architecture">architecture</option>
                <option value="tech_stack">tech_stack</option>
                <option value="hardware">hardware</option>
                <option value="cinema_preference">cinema_preference</option>
                <option value="workflow">workflow</option>
              </select>
              <input type="text" id="capture-tags" class="capture-input" placeholder="Tags (e.g. #backend, #db)" />
              <input type="text" id="capture-supersedes" class="capture-input" placeholder="Supersedes ID (optional)" style="width: 140px;" />
            </div>
            <button class="btn-primary" onclick="submitQuickCapture()">Save to Cephalo</button>
          </div>
        </div>
      </div>

      <!-- Activity Heatmap -->
      <div class="card">
        <div class="heatmap-header">
          <div class="card-title" style="margin-bottom: 0;">📅 Memory Activity Heatmap (Last 365 Days)</div>
          <div class="heatmap-stats">
            <span>Logged: <strong id="stat-total">0</strong></span>
            <span>Active Days: <strong id="stat-days">0</strong></span>
            <span>Streak: <strong id="stat-streak">0</strong> days</span>
          </div>
        </div>
        <div class="heatmap-container">
          <div class="heatmap-grid" id="heatmap-grid"></div>
        </div>
        <div class="heatmap-legend">
          <span>Less</span>
          <div class="legend-box level-0"></div>
          <div class="legend-box level-1"></div>
          <div class="legend-box level-2"></div>
          <div class="legend-box level-3"></div>
          <div class="legend-box level-4"></div>
          <span>More</span>
        </div>
      </div>

      <!-- Memory Stream -->
      <div class="card">
        <div class="card-title">
          <span>🧠 Memory Timeline Stream</span>
          <label style="font-size: 0.78rem; text-transform: none; display: flex; align-items: center; gap: 5px; cursor: pointer;">
            <input type="checkbox" id="toggle-deprecated" onchange="renderTimeline()" />
            Include Deprecated
          </label>
        </div>

        <div class="filter-bar">
          <input type="text" id="search-input" class="search-input" placeholder="Search memories, categories, or #tags..." oninput="filterMemos()" />
          <div class="filter-chips" id="category-chips">
            <span class="chip active" onclick="setCategoryFilter('all')">All</span>
            <span class="chip" onclick="setCategoryFilter('tech_stack')">Tech Stack</span>
            <span class="chip" onclick="setCategoryFilter('architecture')">Architecture</span>
            <span class="chip" onclick="setCategoryFilter('hardware')">Hardware</span>
            <span class="chip" onclick="setCategoryFilter('cinema_preference')">Cinema</span>
            <span class="chip" onclick="setCategoryFilter('quick_note')">Quick Notes</span>
          </div>
        </div>

        <div id="active-filter-banner" class="active-filter-banner" style="display: none;">
          <span id="active-filter-text">Filtering</span>
          <button onclick="clearDateFilter()">✕ Clear Date Filter</button>
        </div>

        <div class="timeline-stream" id="timeline-stream">
          <div style="color: var(--text-muted); text-align: center; padding: 20px;">Loading memory timeline...</div>
        </div>
      </div>

    </div>

    <!-- Docs Tab Content -->
    <div id="docs-view">
      <div class="docs-layout">
        <div class="docs-nav" id="docs-nav">
          <a href="#" class="docs-nav-link active" onclick="loadDoc('ARCHITECTURE.md', this)">1. Architecture</a>
          <a href="#" class="docs-nav-link" onclick="loadDoc('MODULES.md', this)">2. Core Modules</a>
          <a href="#" class="docs-nav-link" onclick="loadDoc('CLI_REFERENCE.md', this)">3. CLI Reference</a>
          <a href="#" class="docs-nav-link" onclick="loadDoc('SECURITY_PRIVACY.md', this)">4. Privacy Shield</a>
          <a href="#" class="docs-nav-link" onclick="loadDoc('README.md', this)">5. DeepWiki Index</a>
        </div>
        <div class="docs-content" id="docs-content">
          Loading documentation...
        </div>
      </div>
    </div>

  </div>

  <script>
    let allMemos = [];
    let heatmapData = {};
    let activeCategory = 'all';
    let activeTag = null;
    let activeDate = null;

    // Relative Time Formatter
    function timeAgo(dateString) {
      const date = new Date(dateString);
      const now = new Date();
      const seconds = Math.floor((now - date) / 1000);
      if (isNaN(seconds) || seconds < 0) return dateString;
      if (seconds < 60) return "just now";
      const minutes = Math.floor(seconds / 60);
      if (minutes < 60) return `${minutes}m ago`;
      const hours = Math.floor(minutes / 60);
      if (hours < 24) return `${hours}h ago`;
      const days = Math.floor(hours / 24);
      if (days < 30) return `${days}d ago`;
      return date.toLocaleDateString();
    }

    // Switch Top Tabs
    function switchTab(tab) {
      document.getElementById('timeline-view').style.display = tab === 'timeline' ? 'block' : 'none';
      document.getElementById('docs-view').style.display = tab === 'docs' ? 'block' : 'none';
      document.getElementById('tab-timeline-btn').className = 'nav-btn ' + (tab === 'timeline' ? 'active' : '');
      document.getElementById('tab-docs-btn').className = 'nav-btn ' + (tab === 'docs' ? 'active' : '');
      if (tab === 'docs') {
        loadDoc('ARCHITECTURE.md');
      }
    }

    // Load Heatmap Data
    async function fetchHeatmap() {
      try {
        const res = await fetch('/api/heatmap');
        heatmapData = await res.json();
        document.getElementById('stat-total').textContent = heatmapData.total || 0;
        document.getElementById('stat-days').textContent = heatmapData.active_days || 0;
        document.getElementById('stat-streak').textContent = heatmapData.current_streak || 0;
        renderHeatmapGrid(heatmapData.days || {});
      } catch (e) {
        console.warn("Could not fetch heatmap:", e);
      }
    }

    function renderHeatmapGrid(daysMap) {
      const grid = document.getElementById('heatmap-grid');
      grid.innerHTML = '';

      const today = new Date();
      const numDays = 364; // 52 weeks * 7 days
      const startDate = new Date();
      startDate.setDate(today.getDate() - numDays);

      for (let i = 0; i <= numDays; i++) {
        const d = new Date(startDate);
        d.setDate(startDate.getDate() + i);
        const iso = d.toISOString().split('T')[0];
        const count = daysMap[iso] || 0;

        let level = 0;
        if (count >= 10) level = 4;
        else if (count >= 6) level = 3;
        else if (count >= 3) level = 2;
        else if (count >= 1) level = 1;

        const cell = document.createElement('div');
        cell.className = `heatmap-cell level-${level}` + (activeDate === iso ? ' selected' : '');
        cell.title = `${iso}: ${count} memories`;
        cell.onclick = () => filterByDate(iso, count);
        grid.appendChild(cell);
      }
    }

    function filterByDate(dateStr, count) {
      activeDate = (activeDate === dateStr) ? null : dateStr;
      const banner = document.getElementById('active-filter-banner');
      if (activeDate) {
        banner.style.display = 'flex';
        document.getElementById('active-filter-text').textContent = `Filtered by Date: ${activeDate} (${count} memories)`;
      } else {
        banner.style.display = 'none';
      }
      renderHeatmapGrid(heatmapData.days || {});
      renderTimeline();
    }

    function clearDateFilter() {
      activeDate = null;
      document.getElementById('active-filter-banner').style.display = 'none';
      renderHeatmapGrid(heatmapData.days || {});
      renderTimeline();
    }

    // Fetch Timeline Memories
    async function fetchTimeline() {
      try {
        const res = await fetch('/api/timeline');
        allMemos = await res.json();
        renderTimeline();
      } catch (e) {
        document.getElementById('timeline-stream').innerHTML = '<div style="color: #f87171; text-align: center;">Failed to load timeline records.</div>';
      }
    }

    function setCategoryFilter(cat) {
      activeCategory = cat;
      document.querySelectorAll('#category-chips .chip').forEach(c => {
        c.className = 'chip ' + (c.textContent.toLowerCase().replace(' ', '_') === cat || (cat === 'all' && c.textContent === 'All') ? 'active' : '');
      });
      renderTimeline();
    }

    function setTagFilter(tag) {
      activeTag = (activeTag === tag) ? null : tag;
      document.getElementById('search-input').value = activeTag ? `#${activeTag}` : '';
      renderTimeline();
    }

    function filterMemos() {
      renderTimeline();
    }

    function renderTimeline() {
      const container = document.getElementById('timeline-stream');
      const query = (document.getElementById('search-input').value || '').toLowerCase().trim();
      const showDeprecated = document.getElementById('toggle-deprecated').checked;

      const filtered = allMemos.filter(memo => {
        if (!showDeprecated && memo.is_deprecated) return false;
        if (activeCategory !== 'all' && memo.category !== activeCategory) return false;
        if (activeDate && !memo.timestamp.startsWith(activeDate)) return false;
        if (activeTag && !(memo.tags || []).includes(activeTag)) return false;

        if (query) {
          const matchContent = (memo.content || '').toLowerCase().includes(query);
          const matchCat = (memo.category || '').toLowerCase().includes(query);
          const matchTags = (memo.tags || []).some(t => t.toLowerCase().includes(query.replace('#', '')));
          if (!matchContent && !matchCat && !matchTags) return false;
        }
        return true;
      });

      if (filtered.length === 0) {
        container.innerHTML = '<div style="color: var(--text-muted); text-align: center; padding: 24px;">No matching memory records found.</div>';
        return;
      }

      container.innerHTML = filtered.map(memo => {
        const isDep = memo.is_deprecated;
        const tagsHtml = (memo.tags || []).map(t => `<span class="tag-pill" onclick="setTagFilter('${t}')">#${t}</span>`).join(' ');
        const supersedesHtml = memo.supersedes ? `<div class="memo-relations">↳ Supersedes: <strong>${memo.supersedes}</strong></div>` : '';
        const deprecatedBadge = isDep ? '<span class="badge badge-deprecated">DEPRECATED</span>' : '';

        // Highlight inline #tags in content
        const formattedContent = (memo.content || '').replace(/(#[a-zA-Z][a-zA-Z0-9_\-\/]*)/g, '<span style="color: var(--accent-cyan); font-weight: 500;">$1</span>');

        return `
          <div class="memo-card ${isDep ? 'deprecated' : ''}" id="${memo.id}">
            <div class="memo-meta">
              <div class="memo-badges">
                <span class="badge badge-id">${memo.id}</span>
                <span class="badge badge-cat">${memo.category || 'general'}</span>
                <span class="badge badge-source">${memo.source || 'cli'}</span>
                ${deprecatedBadge}
              </div>
              <span title="${memo.timestamp}">${timeAgo(memo.timestamp)}</span>
            </div>
            <div class="memo-content">${formattedContent}</div>
            ${tagsHtml ? `<div class="memo-tags">${tagsHtml}</div>` : ''}
            ${supersedesHtml}
            <div class="memo-footer">
              <button class="btn-copy" onclick="copyCardText(this, '${memo.id}')">Copy</button>
            </div>
          </div>
        `;
      }).join('');
    }

    function copyCardText(btn, id) {
      const memo = allMemos.find(m => m.id === id);
      if (memo) {
        navigator.clipboard.writeText(memo.content);
        const orig = btn.textContent;
        btn.textContent = "Copied!";
        setTimeout(() => btn.textContent = orig, 1200);
      }
    }

    // Submit Quick Capture
    async function submitQuickCapture() {
      const text = document.getElementById('capture-text').value.trim();
      const category = document.getElementById('capture-category').value;
      const rawTags = document.getElementById('capture-tags').value.trim();
      const supersedes = document.getElementById('capture-supersedes').value.trim();

      if (!text) {
        alert("Please enter a note to record.");
        return;
      }

      const tags = rawTags ? rawTags.split(',').map(t => t.trim().replace('#', '')) : [];

      try {
        const res = await fetch('/api/record', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, category, tags, supersedes: supersedes || null, source: 'web_ui' })
        });
        const data = await res.json();
        if (data.status === 'success' || data.id) {
          // Toast status
          const toast = document.getElementById('capture-status');
          toast.style.display = 'inline-block';
          setTimeout(() => toast.style.display = 'none', 2500);

          // Reset inputs
          document.getElementById('capture-text').value = '';
          document.getElementById('capture-tags').value = '';
          document.getElementById('capture-supersedes').value = '';

          // Refresh timeline & heatmap
          await fetchHeatmap();
          await fetchTimeline();
        } else {
          alert("Error saving: " + (data.error || "Unknown"));
        }
      } catch (err) {
        alert("Network error: " + err);
      }
    }

    // Keyboard shortcut: Ctrl+Enter to save
    document.getElementById('capture-text').addEventListener('keydown', function(e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        submitQuickCapture();
      }
    });

    // Docs Viewer
    async function loadDoc(filename, el) {
      if (el) {
        document.querySelectorAll('.docs-nav-link').forEach(l => l.classList.remove('active'));
        el.classList.add('active');
      }
      const pane = document.getElementById('docs-content');
      pane.innerHTML = 'Loading ' + filename + '...';
      try {
        const res = await fetch('/api/doc?file=' + encodeURIComponent(filename));
        const markdown = await res.text();
        pane.innerHTML = renderMarkdown(markdown);
      } catch (err) {
        pane.innerHTML = '<div style="color: #f87171;">Failed to load doc.</div>';
      }
    }

    function renderMarkdown(md) {
      let html = md
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        .replace(/^\> (.*$)/gim, '<blockquote style="border-left: 3px solid var(--accent); padding-left: 10px; color: var(--text-muted); margin: 8px 0;">$1</blockquote>')
        .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
        .replace(/\*(.*)\*/gim, '<em>$1</em>')
        .replace(/`([^`]+)`/gim, '<code style="background: #1e293b; padding: 2px 6px; border-radius: 4px; font-size: 0.85em;">$1</code>')
        .replace(/```([\s\S]*?)```/gim, '<pre><code>$1</code></pre>')
        .replace(/^\- (.*$)/gim, '<li style="margin-left: 20px;">$1</li>')
        .replace(/\n$/gim, '<br />');
      return html;
    }

    // Initial boot
    fetchHeatmap();
    fetchTimeline();
  </script>
</body>
</html>
"""
        target.write_text(html, encoding="utf-8")
        return target


# ==============================================================================
# Sovereign Timeline & DeepWiki HTTP Server
# ==============================================================================
def get_timeline_records(limit: int = 500) -> List[Dict[str, Any]]:
    """Reads memories from prompts.jsonl in reverse-chronological order."""
    if not PROMPTS_FILE.exists():
        return []

    from embedding_pipeline import extract_tags

    records = []
    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if "tags" not in rec or not rec["tags"]:
                    rec["tags"] = extract_tags(rec.get("content", ""))
                rec.setdefault("is_deprecated", False)
                rec.setdefault("supersedes", "")
                rec.setdefault("relates_to", [])
                records.append(rec)
            except Exception:
                pass

    records.reverse()
    return records[:limit]


def get_heatmap_data() -> Dict[str, Any]:
    """Computes daily ingestion counts over the past 365 days."""
    if not PROMPTS_FILE.exists():
        return {"days": {}, "total": 0, "active_days": 0, "current_streak": 0}

    days_count: Dict[str, int] = {}
    total = 0

    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                ts = data.get("timestamp", "")
                if ts:
                    day_key = ts[:10]
                    days_count[day_key] = days_count.get(day_key, 0) + 1
                    total += 1
            except Exception:
                pass

    today = datetime.date.today()
    streak = 0
    cur_day = today
    while True:
        k = cur_day.isoformat()
        if days_count.get(k, 0) > 0:
            streak += 1
            cur_day -= datetime.timedelta(days=1)
        else:
            break

    return {
        "days": days_count,
        "total": total,
        "active_days": len(days_count),
        "current_streak": streak,
    }


class DeepWikiServerHandler(SimpleHTTPRequestHandler):
    """Dynamic HTTP handler for DeepWiki documentation, timeline feed, and quick capture."""

    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=str(DOCS_WIKI_DIR), **kwargs)

    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            index_file = DOCS_WIKI_DIR / "index.html"
            if not index_file.exists():
                wg = WikiGenerator()
                wg._write_timeline_dashboard()
            return super().do_GET()

        if path == "/api/timeline":
            records = get_timeline_records()
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(records, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/heatmap":
            hdata = get_heatmap_data()
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(hdata, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/stats":
            hdata = get_heatmap_data()
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            stats = {
                "total_memories": hdata["total"],
                "active_days": hdata["active_days"],
                "current_streak": hdata["current_streak"],
                "lancedb_dir": str(DEFAULT_LANCEDB_DIR),
            }
            self.wfile.write(json.dumps(stats, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/doc":
            qs = urllib.parse.parse_qs(parsed.query)
            filename = qs.get("file", ["README.md"])[0]
            safe_filename = Path(filename).name
            doc_file = DOCS_WIKI_DIR / safe_filename
            if doc_file.exists():
                self.send_response(200)
                self._send_cors()
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(doc_file.read_text(encoding="utf-8").encode("utf-8"))
            else:
                self.send_response(404)
                self._send_cors()
                self.end_headers()
                self.wfile.write(b"Document not found")
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/api/record", "/ingest"):
            length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(length)
            try:
                data = json.loads(body_bytes.decode("utf-8"))
                text = data.get("text", "")
                cat = data.get("category", "quick_note")
                tags = data.get("tags", [])
                supersedes = data.get("supersedes")
                source = data.get("source", "web_ui")

                from embedding_pipeline import EmbeddingPipeline, create_embedder
                embedder = create_embedder(mode="local")
                pipeline = EmbeddingPipeline(embedder=embedder)

                rec = pipeline.ingest_prompt(
                    raw_text=text,
                    category=cat,
                    tags=tags,
                    supersedes=supersedes,
                    source=source,
                    sync_to_jsonl=True,
                )

                self.send_response(200)
                self._send_cors()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "success",
                    "id": rec["id"],
                    "tags": rec.get("tags", []),
                    "category": rec["category"],
                    "sanitized": rec["content"],
                }, ensure_ascii=False).encode("utf-8"))
                return
            except Exception as e:
                self.send_response(500)
                self._send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                return

        self.send_response(404)
        self.end_headers()


def run_deepwiki_server(port: int = 7433, open_browser: bool = True) -> None:
    """Runs the integrated Sovereign DeepWiki & Timeline dashboard server."""
    import webbrowser
    wg = WikiGenerator()
    wg._write_timeline_dashboard()
    print(f"[+] Serving Cephalo DeepWiki & Memory Timeline at http://127.0.0.1:{port}/")
    if open_browser:
        webbrowser.open(f"http://127.0.0.1:{port}/")
    with ThreadingHTTPServer(("127.0.0.1", port), DeepWikiServerHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[+] DeepWiki server stopped.")

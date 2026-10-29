# Core Python Modules & API Reference

Complete structural breakdown of Cephalo's active core modules.

## [`auto_harvest.py`](auto_harvest.py)
**Lines of Code:** 437 | **Imports:** 9

> Cephalo Autonomous Memory Harvester & Dynamic Context Injector (auto_harvest.py)
================================================================================
Universal lifecycle processor for agent harnesses (Google Antigravity, Claude Code, Cursor, Codex).

### Key Functions
- `def load_state()` — **
- `def save_state(state)` — **
- `def extract_user_messages(transcript_path, last_step_index)` — *Extract user prompts from transcript.jsonl.*
- `def harvest_all_user_prompts(messages, conversation_id)` — *Records EVERY user prompt into prompts.jsonl.*
- `def query_relevant_memory(query_text)` — *Performs ultra-fast local vector search directly in LanceDB.*
- `def handle_session_start(input_data)` — *SessionStart Hook Handler:*
- `def handle_pre_invocation(input_data)` — *PreInvocation Hook Handler:*
- `def handle_stop_hook(input_data)` — *Stop Hook Handler: Final harvest sweep on turn completion.*

---

## [`brain.py`](brain.py)
**Lines of Code:** 1387 | **Imports:** 9

> Cephalo - Unified Agent & User Memory Interface (brain.py)
==========================================================
Universal CLI entrypoint for humans and AI agents (Antigravity, Claude Code, Codex, Cursor).
- Sanitizes all inputs automatically via multi-tier local filter.
- Performs hybrid semantic (Qwen 1024d) + BM25 keyword search in LanceDB.
- Appends and tracks entries in prompts.jsonl and USER_PROFILE.md.
- Outputs human-readable markdown tables or machine-readable JSON (--json).

### Key Functions
- `def get_pipeline(table_name)` — *Lazy loader for EmbeddingPipeline to keep light commands (status, profile) sub-second.*
- `def cmd_profile(args)` — *Reads or updates USER_PROFILE.md.*
- `def cmd_status(args)` — *Prints system health, LanceDB table status, and prompt counts.*
- `def cmd_search(args)` — *Performs hybrid, vector, or keyword search across LanceDB.*
- `def cmd_record(args)` — *Sanitizes, embeds, and records a new prompt/decision into LanceDB and prompts.jsonl.*
- `def cmd_sync(args)` — *Syncs unindexed entries from prompts.jsonl into LanceDB.*
- `def cmd_harvest(args)` — *Scans conversation transcripts and harvests preferences/critiques.*
- `def cmd_specialty(args)` — *Handles CRUD operations for the Specialties domain layer.*

---

## [`cephalo_daemon.py`](cephalo_daemon.py)
**Lines of Code:** 474 | **Imports:** 12

> Cephalo Always-On Background Daemon (cephalo_daemon.py)
======================================================
Autonomous 24/7 background worker ensuring Cephalo continuously learns across
ALL agent harnesses (Claude Code, Antigravity, Cursor, Windsurf, Copilot, Aider).

### Classes
- **`CephaloDaemon`**
  *Always-on background supervisor for sovereign continuous learning.*
  **Methods:** `__init__()`, `_write_pid()`, `_remove_pid()`, `_update_status()`, `execute_cycle()`, `run_foreground()`
### Key Functions
- `def is_pid_running(pid)` — *Checks if a process ID is actively running on Windows/Linux.*
- `def get_daemon_status()` — *Inspects daemon PID file and status snapshot.*
- `def start_daemon_detached(interval)` — *Spawns the daemon as a detached, persistent background process.*
- `def stop_daemon()` — *Stops the running background daemon.*
- `def install_windows_task()` — *Registers a persistent Windows Scheduled Task running on user login.*
- `def uninstall_windows_task()` — *Unregisters the Windows Scheduled Task.*
- `def main()` — **

---

## [`clipboard_utils.py`](clipboard_utils.py)
**Lines of Code:** 122 | **Imports:** 6

> Cephalo - Cross-Platform Silent Clipboard Utilities (clipboard_utils.py)
========================================================================
Provides zero-dependency, silent clipboard reading and writing across Windows,
macOS, and Linux.

### Key Functions
- `def get_clipboard_text()` — *Reads and returns the current system clipboard text.*
- `def set_clipboard_text(text)` — *Copies text to the system clipboard silently.*

---

## [`context_manager.py`](context_manager.py)
**Lines of Code:** 84 | **Imports:** 5

> Cephalo - Dynamic Context Assembler (context_manager.py)
========================================================
Assembles and exports tailored, consolidated system context blocks from
Cephalo's USER_PROFILE.md, hardware specifications, and domain Specialties.

### Classes
- **`ContextManager`**
  *Consolidates personal identity, hardware profiles, and domain specialties into ready-to-use context payloads.*
  **Methods:** `__init__()`, `export_context()`

---

## [`continuous_learner.py`](continuous_learner.py)
**Lines of Code:** 459 | **Imports:** 11

> Cephalo Continuous Learning Engine (continuous_learner.py)
==========================================================
Autonomous background knowledge harvester and memory consolidation coprocessor.

### Classes
- **`ContinuousLearner`**
  *Orchestrates continuous learning across codebases and episodic memory.*
  **Methods:** `__init__()`, `_load_state()`, `_save_state()`, `scan_workspaces()`, `get_existing_specialty_slugs()`, `audit_and_synthesize_specialties()`
### Key Functions
- `def main()` — **

---

## [`email_client.py`](email_client.py)
**Lines of Code:** 283 | **Imports:** 11

> Personal Second Brain - Secure Local Email Client (email_client.py)
===================================================================
Enables the Second Brain and AI agents to send emails securely via SMTP
using a dedicated App Password (e.g. Gmail / Outlook / custom domain).

### Classes
- **`EmailClient`**
  *Manages secure outbound SMTP communications.*
  **Methods:** `__init__()`, `is_configured()`, `mask_email()`, `get_status()`, `send_email()`
### Key Functions
- `def main()` — **

---

## [`embedding_pipeline.py`](embedding_pipeline.py)
**Lines of Code:** 1087 | **Imports:** 14

> Personal Second Brain - Clean, Production-Ready Embedding & Vector Storage Pipeline
===================================================================================
Features:
1. Sanitization First: All inputs (prompts, queries, batch files) are processed through
   Presidio (PII redaction) + deterministic regex rules before reaching embedding models
   or vector storage.
2. Dual Embedding Support:
   - Mode A (Local / Zero-Leak): Lightweight, local ONNX embeddings via FastEmbed
     (e.g., 'BAAI/bge-small-en-v1.5' [384d] or 'nomic-ai/nomic-embed-text-v1.5' [768d]).
   - Mode B (Google Cloud): Google 'text-embedding-004' via Google GenAI SDK with
     automatic HTTP REST fallback. Full Matryoshka dimension truncation (e.g., 768 -> 256).
3. Storage: High-performance, columnar vector storage in LanceDB with native PyArrow schema,
   metadata preservation, and automatic ID deduplication.
4. Python 3.12.10 verified and production-ready.

### Classes
- **`Sanitizer`**
  *Detects and redacts credentials, secrets, tokens, and PII.*
  **Methods:** `__init__()`, `sanitize_line()`, `sanitize()`
- **`BaseEmbedder`**
  *Abstract interface for embedding models.*
  **Methods:** `mode()`, `model_name()`, `dimension()`, `embed_texts()`, `embed_query()`
- **`FastEmbedEmbedder`**
  *Mode A: Local / Zero-Leak Embedding via FastEmbed.*
  **Methods:** `__init__()`, `mode()`, `model_name()`, `dimension()`, `embed_texts()`, `embed_query()`
- **`GoogleEmbedder`**
  *Mode B: Google Cloud Embeddings via 'text-embedding-004'.*
  **Methods:** `__init__()`, `mode()`, `model_name()`, `dimension()`, `_embed_via_sdk()`, `_embed_via_rest()`
- **`LanceDBStore`**
  *Manages storage and vector retrieval using local LanceDB tables.*
  **Methods:** `__init__()`, `_get_schema()`, `_ensure_columns_exist()`, `_get_or_create_table()`, `deprecate_record()`, `get_existing_ids()`
- **`EmbeddingPipeline`**
  *Coordinates Sanitization -> Embedding -> LanceDB Storage.*
  **Methods:** `__init__()`, `ingest_prompt()`, `sync_from_jsonl()`, `search()`
### Key Functions
- `def extract_tags(text)` — *Extracts inline #tags and hierarchical #tag/subtags from text (e.g. #cinema/hdr, #backend).*
- `def calculate_shannon_entropy(data)` — *Calculates the Shannon entropy of a string.*
- `def is_code_line(line)` — *Detects if a line is likely source code or terminal syntax rather than natural prose.*
- `def create_embedder(mode, model, dimension, api_key)` — *Factory creating either FastEmbed (Local) or Google Cloud embedder.*
- `def main()` — **

---

## [`mcp_server.py`](mcp_server.py)
**Lines of Code:** 564 | **Imports:** 7

> Cephalo Sovereign Memory - Model Context Protocol (MCP) Server
==============================================================
Zero-dependency, high-performance stdio MCP server for universal agent harness compatibility.

### Key Functions
- `def get_tool_definitions()` — *Defines the standard tool catalog compliant with MCP specification 2024-11-05.*
- `def handle_tool_call(name, arguments)` — *Executes the requested Cephalo tool and returns the result.*
- `def send_response(response)` — *Writes a JSON-RPC response to stdout followed by newline.*
- `def run_stdio_server()` — *Main stdio JSON-RPC loop handling MCP requests.*

---

## [`patterns_manager.py`](patterns_manager.py)
**Lines of Code:** 144 | **Imports:** 6

> Cephalo - Cognitive Patterns Manager (patterns_manager.py)
=========================================================
Manages modular, version-controlled execution prompts ("Reflexes") inspired by
Daniel Miessler's Fabric framework, integrated directly with Cephalo's local
memory and user constraints.

### Classes
- **`PatternsManager`**
  *Manages discovery, inspection, and execution prompt assembly for Cephalo patterns.*
  **Methods:** `__init__()`, `list_patterns()`, `get_pattern()`, `assemble_prompt()`, `save_custom_pattern()`, `_extract_summary()`

---

## [`research_engine.py`](research_engine.py)
**Lines of Code:** 467 | **Imports:** 13

> Cephalo Deep Research & Specialty Synthesis Engine (research_engine.py)
======================================================================
Autonomous research engine embodying the user's exact methodology, depth,
and craftsmanship standards for investigating topics and creating specialties.

### Classes
- **`GitHubRepoInfo`**
  **Methods:** `to_dict()`
- **`DeepResearchEngine`**
  *Executes multi-perspective investigation across web search, GitHub repositories,*
  **Methods:** `__init__()`, `_query_github_repo_metadata()`, `search_curated_github_repos()`, `search_industry_best_practices()`, `decompose_subtopics()`, `synthesize_specialty()`
### Key Functions
- `def slugify(text)` — *Converts a string into a clean filesystem slug.*
- `def main()` — **

---

## [`serp_renderer.py`](serp_renderer.py)
**Lines of Code:** 492 | **Imports:** 7

> Cephalo SERP & Generative UI Renderer (serp_renderer.py)
========================================================
Renders accessible, responsive Google-style SERP interfaces and Generative UI widgets
for Antigravity chat (<agent-embed>), Claude Code, Cursor, Windsurf, and web browsers.

### Classes
- **`SearchItem`**
  **Methods:** `to_dict()`
- **`CephaloSERP`**
  **Methods:** `to_dict()`, `to_markdown()`
### Key Functions
- `def get_social_badge(social_type)` — *Returns accessible theme colors and icons for social badges with guaranteed dark-mode contrast.*
- `def render_serp_html(serp, standalone)` — *Renders a Google-style, human-centered SERP interface compatible with Antigravity*

---

## [`specialties_manager.py`](specialties_manager.py)
**Lines of Code:** 454 | **Imports:** 8

> Specialties Manager for Personal Second Brain
==============================================
Manages the domain expertise layer in the Second Brain hierarchy:
    Project -> Specialties (1-to-many) -> User Preferences (inherited constraints)

### Classes
- **`SpecialtiesManager`**
  *Orchestrates CRUD operations, autonomous specialty synthesis, LanceDB syncing, and user preferences mapping.*
  **Methods:** `__init__()`, `_find_specialty_dir()`, `list_specialties()`, `get_specialty()`, `create_specialty()`, `auto_create_specialty()`
### Key Functions
- `def slugify(text)` — *Converts a string into a clean filesystem slug.*

---

## [`specialties_synthesizer.py`](specialties_synthesizer.py)
**Lines of Code:** 818 | **Imports:** 4

> Cephalo Autonomous Specialty Synthesizer & Knowledge Engine
============================================================
Provides automated knowledge synthesis and specialty generation for:
1. Curated foundational technologies, frameworks, UI/UX, and methodologies.
2. Dynamic synthesis for ANY novel or unknown technology/methodology.
3. Automated text discovery & extraction from prompts, docs, or project files.

### Classes
- **`SpecialtySynthesizer`**
  *Intelligently resolves, synthesizes, and generates domain specialties.*
  **Methods:** `resolve_slug()`, `get_curated()`, `synthesize()`, `discover_technologies()`
### Key Functions
- `def slugify(text)` — *Converts a string into a clean filesystem slug.*

---

## [`symbol_extractor.py`](symbol_extractor.py)
**Lines of Code:** 565 | **Imports:** 11

> Cephalo - AST Code Symbol & Definition Indexer (symbol_extractor.py)
===================================================================
Token-efficient Abstract Syntax Tree (AST) code symbol search engine inspired
by XERJ's 'def' primitive. Replaces wasteful full-file grepping by parsing source
code into AST nodes and returning exact definitions, line numbers, and signatures.

### Classes
- **`SymbolDefinition`**
  **Methods:** `to_dict()`, `to_markdown()`
- **`CodeSymbolIndexer`**
  *Traverses codebases, parses AST nodes via Tree-sitter cursors or native ASTs,*
  **Methods:** `__init__()`, `find_definitions()`, `extract_symbols_from_file()`, `extract_symbols_from_content()`, `_walk_source_files()`, `_extract_tree_sitter_symbols()`

---

## [`web_search.py`](web_search.py)
**Lines of Code:** 1155 | **Imports:** 17

> Cephalo - Web Search & Sovereign SERP Intelligence Engine (web_search.py)
========================================================================
Provides multi-engine web search, Google-style SERP synthesis, clean content
extraction, and interactive generative UI rendering.

### Classes
- **`SearchResult`**
  *Legacy dataclass preserved for 100% backward compatibility.*
  **Methods:** `to_dict()`
- **`HTMLTextExtractor`**
  *Clean HTML parser that strips scripts, styles, and extracts readable text.*
  **Methods:** `__init__()`, `handle_starttag()`, `handle_endtag()`, `handle_data()`, `get_text()`
- **`WebSearchEngine`**
  *Orchestrates web search, Google-style SERP synthesis, and content extraction.*
  **Methods:** `__init__()`, `_resolve_exa_key()`, `_init_cache_db()`, `_get_page_from_cache()`, `_save_page_to_cache()`, `_get_from_cache()`
### Key Functions
- `def is_deep_discussion_url(url)` — *Validates whether a URL points to an actual discussion thread, forum topic,*
- `def select_community_targets(query)` — *Selects high-relevance community and forum domains dynamically based on query topic.*

---

## [`webhook_server.py`](webhook_server.py)
**Lines of Code:** 341 | **Imports:** 13

> Cephalo Multi-Channel Quick Capture & Webhook Ingress Gateway (webhook_server.py)
================================================================================
Lightweight, local-first HTTP webhook server and ingestion bridge.
Allows instant quick-capture from:
- iOS Shortcuts / Android Tasker / curl
- Browser extensions / Raycast scripts
- Telegram Bot (polling or webhook)
- Local scripts and external services

### Classes
- **`WebhookRequestHandler`**
  *Handles incoming HTTP webhooks, REST ingest calls, and health checks.*
  **Methods:** `_send_cors_headers()`, `do_OPTIONS()`, `_authenticate()`, `do_GET()`, `do_POST()`, `log_message()`
- **`WebhookServer`**
  *Manages the lifecycle of the quick-capture HTTP ingress server.*
  **Methods:** `__init__()`, `start()`, `stop()`
- **`TelegramIngestBot`**
  *Lightweight zero-dependency Telegram bot polling worker for remote thought capture.*
  **Methods:** `__init__()`, `_api_call()`, `_poll_loop()`, `start()`, `stop()`
### Key Functions
- `def get_pipeline()` — **
- `def send_quick_memory(text, category, host, port)` — *Helper for CLI to post a note to the local webhook gateway.*

---

## [`wiki_generator.py`](wiki_generator.py)
**Lines of Code:** 1416 | **Imports:** 9

> Cephalo - Sovereign Codebase Wiki & Codemap Engine (wiki_generator.py)
=====================================================================
Generates offline, private, interactive documentation and architectural codemaps
for Cephalo and user projects without leaking proprietary code to third-party clouds.

### Classes
- **`CodeInspector`**
  *Parses Python source code AST to extract architecture, signatures, and docstrings.*
  **Methods:** `analyze_file()`
- **`WikiGenerator`**
  *Synthesizes structured documentation, codemaps, and Mermaid charts.*
  **Methods:** `__init__()`, `generate_all()`, `_scan_modules()`, `_write_index()`, `_write_architecture()`, `_write_modules()`
- **`DeepWikiServerHandler`**
  *Dynamic HTTP handler for DeepWiki documentation, timeline feed, and quick capture.*
  **Methods:** `__init__()`, `_send_cors()`, `do_OPTIONS()`, `do_GET()`, `do_POST()`
### Key Functions
- `def get_timeline_records(limit)` — *Reads memories from prompts.jsonl in reverse-chronological order.*
- `def get_heatmap_data()` — *Computes daily ingestion counts over the past 365 days.*
- `def run_deepwiki_server(port, open_browser)` — *Runs the integrated Sovereign DeepWiki & Timeline dashboard server.*

---

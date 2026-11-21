"""MCP Tool Definitions Catalog compliant with MCP specification 2024-11-05."""

from typing import Any, Dict, List

def get_tool_definitions() -> List[Dict[str, Any]]:
    """Defines the standard tool catalog compliant with MCP specification 2024-11-05."""
    return [
        {
            "name": "cephalo_search",
            "description": "Performs hybrid (dense vector + BM25 keyword) search across Cephalo's sovereign memory in LanceDB. Use this to recall past architectural decisions, user preferences, hardware configurations, and established project rules.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of memory results to return (default: 5).",
                        "default": 5,
                    },
                    "type": {
                        "type": "string",
                        "enum": ["hybrid", "vector", "fts"],
                        "description": "Search mode: 'hybrid' (vector + keyword), 'vector' (semantic only), or 'fts' (BM25 only). Default is 'hybrid'.",
                        "default": "hybrid",
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category filter (e.g. 'architecture', 'user_preference', 'hardware_spec').",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "cephalo_record",
            "description": "Permanently saves a user preference, hardware detail, architectural decision, or negative critique into Cephalo. Sanitizes PII and secrets automatically before embedding and storing into LanceDB.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Clear, factual statement of the decision, preference, or constraint (alias: 'content').",
                    },
                    "content": {
                        "type": "string",
                        "description": "Alias for 'text'. Clear, factual statement of the decision, preference, or constraint.",
                    },
                    "category": {
                        "type": "string",
                        "description": "Memory category: 'user_preference', 'architecture', 'hardware_spec', 'critique_negative_filter', 'workflow_rule'.",
                        "default": "general",
                    },
                    "intent": {
                        "type": "string",
                        "description": "Brief summary of user intent or context.",
                        "default": "",
                    },
                    "supersedes": {
                        "type": "string",
                        "description": "Optional ID of a prior memory record this decision explicitly supersedes and deprecates.",
                    },
                    "auto_reconcile": {
                        "type": "boolean",
                        "description": "Whether to automatically detect and deprecate contextually conflicting older preferences (default: true).",
                        "default": True,
                    },
                },
                "required": ["text"],
            },
        },
        {
            "name": "cephalo_get_profile",
            "description": "Retrieves the user's permanent profile blueprint (core principles, hardware profiles like TCL 65T8B TV, communication style, language preferences, active projects). Always consult this to ground reasoning.",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "cephalo_list_specialties",
            "description": "Lists all active domain specialties (curated engineering practices, frameworks, languages, and project-specific knowledge modules).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Optional filter by project name (e.g. 'global', 'getmynews', 'mygarage').",
                    },
                },
            },
        },
        {
            "name": "cephalo_get_specialty",
            "description": "Retrieves the full verified knowledge, key takeaways, anti-slop guidelines, and recommended GitHub repos for a given specialty.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": "Specialty slug (e.g. 'coding-craftsmanship', 'nextjs', 'bullmq', 'html-email-design').",
                    },
                    "project": {
                        "type": "string",
                        "description": "Project namespace (default: 'global').",
                        "default": "global",
                    },
                },
                "required": ["slug"],
            },
        },
        {
            "name": "cephalo_auto_create_specialty",
            "description": "Autonomously synthesizes and registers a new specialty module for any novel or unknown technology, framework, or methodology. Incorporates verified best practices and anti-slop discipline.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Technology or methodology name (e.g. 'zustand', 'hono', 'temporal', 'astro').",
                    },
                    "project": {
                        "type": "string",
                        "description": "Target project namespace (default: 'global').",
                        "default": "global",
                    },
                },
                "required": ["topic"],
            },
        },
        {
            "name": "cephalo_continuous_learn",
            "description": "Triggers an autonomous continuous learning cycle across all project workspaces. Audits manifests, identifies novel technologies, auto-synthesizes missing specialties, and consolidates memory insights.",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "cephalo_learning_status",
            "description": "Queries the current continuous learning state, tracked projects, discovered tech stacks, and cycle statistics.",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "cephalo_deep_research",
            "description": "Executes autonomous deep research on any topic or subtopic using the user's methodology (first principles, industry standards, anti-AI-slop craftsmanship, top GitHub repos with stars). Optionally persists as a permanent specialty.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Technology, domain, or methodology to research.",
                    },
                    "project": {
                        "type": "string",
                        "description": "Target project namespace (default: 'global').",
                        "default": "global",
                    },
                    "subtopics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional specific subtopics to investigate.",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional custom architectural directives.",
                    },
                    "create_specialty": {
                        "type": "boolean",
                        "description": "If true, registers and indexes the researched findings as a Cephalo specialty.",
                        "default": True,
                    },
                },
                "required": ["topic"],
            },
        },
        {
            "name": "cephalo_web_search",
            "description": "Performs Google-style web search with an AI Quick Summary, organic web results, and social/discussion blocks (Reddit, YouTube, GitHub, X). Returns structured SERP data and optionally an interactive HTML Generative UI artifact.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of organic search results (default: 5).",
                        "default": 5,
                    },
                    "include_social": {
                        "type": "boolean",
                        "description": "Whether to extract social & discussion blocks (Reddit, YouTube, GitHub). Default is True.",
                        "default": True,
                    },
                    "html_ui": {
                        "type": "boolean",
                        "description": "If true, generates a self-contained Google-style HTML generative UI widget artifact.",
                        "default": False,
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "cephalo_web_fetch",
            "description": "Extracts clean readable markdown/text from a webpage URL (supports static and dynamic Chromium SPA rendering).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Target webpage URL to crawl.",
                    },
                    "dynamic": {
                        "type": "boolean",
                        "description": "Render JavaScript dynamic SPAs with Playwright Chromium.",
                        "default": False,
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum characters to extract (default: 15000).",
                        "default": 15000,
                    },
                },
                "required": ["url"],
            },
        },
        {
            "name": "cephalo_run_sandboxed",
            "description": "Executes code in an isolated OpenSandbox microVM container (requires OpenSandbox daemon on 127.0.0.1:8080). Refuses unsandboxed local host execution unless CEPHALO_ALLOW_UNSANDBOXED_FALLBACK=1.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The Python, Bash, or JS code to execute.",
                    },
                    "language": {
                        "type": "string",
                        "enum": ["python", "bash", "javascript"],
                        "default": "python",
                        "description": "Execution language runtime.",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "default": 30,
                        "description": "Execution timeout limit.",
                    },
                    "allow_network": {
                        "type": "boolean",
                        "default": False,
                        "description": "Whether outbound network is permitted (default: False / deny-all).",
                    },
                },
                "required": ["code"],
            },
        },
        {
            "name": "cephalo_task_checkpoint",
            "description": "Checkpoints a subagent's execution state when pausing, completing steps, or hitting rate limits/token quotas. Enables seamless resumption without wasting tokens.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Unique task identifier.",
                    },
                    "step_index": {
                        "type": "integer",
                        "description": "Current step index achieved.",
                    },
                    "checkpoint_state": {
                        "type": "object",
                        "description": "Dictionary of saved variables, partial outputs, and pending work.",
                    },
                    "pause_reason": {
                        "type": "string",
                        "description": "Optional reason (e.g. 'rate_limit_429', 'token_budget_pause', 'blocked_on_subagent').",
                    },
                    "reset_seconds": {
                        "type": "integer",
                        "description": "Seconds until rate limit or token budget resets.",
                    },
                    "assignee_agent": {
                        "type": "string",
                        "description": "Agent or subagent role name.",
                    },
                    "user_goal": {
                        "type": "string",
                        "description": "High-level goal of this task.",
                    },
                },
                "required": ["task_id", "checkpoint_state"],
            },
        },
        {
            "name": "cephalo_task_resume",
            "description": "Fetches saved checkpoint state for a paused or rate-limited subagent task, allowing it to continue where it left off.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task identifier to resume (omit to discover all resumable tasks).",
                    },
                    "assignee_agent": {
                        "type": "string",
                        "description": "Filter resumable tasks by agent role.",
                    },
                },
            },
        },
        {
            "name": "cephalo_task_list",
            "description": "Lists subagent tasks, current step status, paused reasons, and token usage.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["running", "rate_limited_paused", "completed", "failed"],
                        "description": "Filter by task status.",
                    },
                    "conversation_id": {
                        "type": "string",
                        "description": "Filter by conversation ID.",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 20,
                        "description": "Max tasks to list.",
                    },
                },
            },
        },
        {
            "name": "cephalo_migrate",
            "description": "Universal migration engine for Cephalo and all AI agent harnesses (Antigravity, Claude Code, Cursor, Windsurf, Aider, Copilot). Exports or restores lossless compressed migration bundles (.cephalo.tar.xz). By default migrates all settings, rules, hooks, and MCP configs; optionally with scope='all' migrates all vector memory, prompt logs, SQLite databases, and workspace projects. Restores everything with a single action.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["export", "restore", "inspect", "list"],
                        "description": "Migration action to execute (default: 'export').",
                        "default": "export",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["settings", "all"],
                        "description": "Migration scope: 'settings' (all harness and Cephalo settings) or 'all' (settings + vector data + projects).",
                        "default": "settings",
                    },
                    "archive_path": {
                        "type": "string",
                        "description": "Path to migration archive file (required for 'restore' and 'inspect').",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview restore operations without modifying files (default: false).",
                        "default": False,
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Optional custom output path for created migration archive.",
                    },
                },
            },
        },
    ]



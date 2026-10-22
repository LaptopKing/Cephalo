#!/usr/bin/env python3
"""
Cephalo Sovereign Memory - Model Context Protocol (MCP) Server
==============================================================
Zero-dependency, high-performance stdio MCP server for universal agent harness compatibility.

Supported Harvesters & Agent Environments:
- Claude Code (`claude mcp add cephalo ...`)
- Cursor IDE (Settings -> Features -> MCP -> Add new MCP server)
- Windsurf Cascade (Codeium MCP configuration)
- Claude Desktop (`claude_desktop_config.json`)
- Zed Editor (Zed AI assistant context)
- Continue.dev (VS Code / JetBrains extension)
- Google Antigravity / Gemini CLI
- OpenAI Codex & GitHub Copilot CLI

Standard Tools Exposed:
1. `cephalo_search`: Hybrid dense vector + BM25 keyword search across personal memory.
2. `cephalo_record`: Sanitize, embed, and permanently store user decisions/preferences.
3. `cephalo_get_profile`: Retrieve the user profile, verified hardware, and communication style.
4. `cephalo_list_specialties`: Enumerate curated & auto-synthesized domain engineering modules.
5. `cephalo_get_specialty`: Fetch the full verified knowledge & anti-slop rules of a specialty.
6. `cephalo_auto_create_specialty`: Autonomously synthesize a specialty for any novel technology.
7. `cephalo_continuous_learn`: Run a full continuous learning cycle across workspaces & manifests.
8. `cephalo_learning_status`: Check continuous learning health, tracked stacks, and cycle stats.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Set up logging to stderr so stdout is strictly preserved for JSON-RPC messages
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [Cephalo:MCP] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger("cephalo.mcp")

# Base paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROFILE_FILE = SCRIPT_DIR / "USER_PROFILE.md"

# Add script directory to sys.path so modules can be imported directly
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


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
                        "description": "Clear, factual statement of the decision, preference, or constraint.",
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
    ]


# =============================================================================
# Tool Execution Handlers
# =============================================================================
def handle_tool_call(name: str, arguments: Dict[str, Any]) -> Any:
    """Executes the requested Cephalo tool and returns the result."""
    try:
        if name == "cephalo_search":
            from brain import get_pipeline
            pipeline = get_pipeline()
            query = arguments.get("query", "")
            limit = arguments.get("limit", 5)
            qtype = arguments.get("type", "hybrid")
            category = arguments.get("category")
            where = f"category = '{category}'" if category else None

            results = pipeline.search(
                raw_query=query,
                query_type=qtype,
                where=where,
                limit=limit,
            )
            # Strip dense vector float array for compact token-friendly output
            clean = []
            for r in results:
                clean_r = {k: v for k, v in r.items() if k != "vector"}
                clean.append(clean_r)
            return {"query": query, "count": len(clean), "results": clean}

        elif name == "cephalo_record":
            from brain import get_pipeline
            pipeline = get_pipeline()
            text = arguments.get("text", "")
            category = arguments.get("category", "general")
            intent = arguments.get("intent", "")

            rec = pipeline.ingest_prompt(
                raw_text=text,
                category=category,
                source="mcp_agent",
                intent=intent,
                sync_to_jsonl=True,
            )
            clean_rec = {k: v for k, v in rec.items() if k != "vector"}
            return {"status": "success", "recorded": clean_rec}

        elif name == "cephalo_get_profile":
            if not PROFILE_FILE.exists():
                return {"error": "USER_PROFILE.md not found"}
            return {"content": PROFILE_FILE.read_text(encoding="utf-8")}

        elif name == "cephalo_list_specialties":
            from specialties_manager import SpecialtiesManager
            sm = SpecialtiesManager()
            project = arguments.get("project")
            items = sm.list_specialties(project=project)
            return {"count": len(items), "specialties": items}

        elif name == "cephalo_get_specialty":
            from specialties_manager import SpecialtiesManager
            sm = SpecialtiesManager()
            slug = arguments.get("slug", "")
            project = arguments.get("project", "global")
            spec = sm.get_specialty(slug, project=project)
            if not spec and project != "global":
                spec = sm.get_specialty(slug, project="global")
            if not spec:
                return {"error": f"Specialty '{slug}' not found."}
            return spec

        elif name == "cephalo_auto_create_specialty":
            from specialties_manager import SpecialtiesManager
            sm = SpecialtiesManager()
            topic = arguments.get("topic", "")
            project = arguments.get("project", "global")
            spec = sm.auto_create_specialty(topic, project=project, sync_to_vector_db=False)
            return {"status": "success", "specialty": spec}

        elif name == "cephalo_continuous_learn":
            from continuous_learner import ContinuousLearner
            learner = ContinuousLearner()
            report = learner.run_cycle()
            return {"status": "success", "report": report}

        elif name == "cephalo_learning_status":
            from continuous_learner import ContinuousLearner
            learner = ContinuousLearner()
            return {"status": "success", "state": learner.state}

        elif name == "cephalo_deep_research":
            from research_engine import DeepResearchEngine
            engine = DeepResearchEngine()
            topic = arguments.get("topic", "")
            project = arguments.get("project", "global")
            subtopics = arguments.get("subtopics")
            notes = arguments.get("notes")
            create = arguments.get("create_specialty", True)

            synth = engine.synthesize_specialty(
                topic=topic,
                project=project,
                subtopics=subtopics,
                custom_notes=notes,
            )

            if create:
                from specialties_manager import SpecialtiesManager
                sm = SpecialtiesManager()
                created = sm.create_specialty(
                    name=synth["name"],
                    project=synth["project"],
                    fundamentals=synth["fundamentals"],
                    github_repos=synth["github_repos"],
                    key_takeaways=synth["key_takeaways"],
                    user_preferences=synth["user_preferences"],
                    tags=synth["tags"],
                    slug=synth["slug"],
                    sync_to_vector_db=True,
                )
                return {
                    "status": "success",
                    "action": "researched_and_created",
                    "specialty_name": synth["name"],
                    "path": created["path"],
                    "repositories": synth["github_repos"],
                    "takeaways": synth["key_takeaways"],
                    "subtopics": synth["subtopics"],
                }
            return {
                "status": "success",
                "action": "researched",
                "research": synth,
            }

        else:
            return {"error": f"Unknown tool: '{name}'"}

    except Exception as e:
        logger.error(f"Error executing tool '{name}': {e}", exc_info=True)
        return {"error": str(e)}


# =============================================================================
# JSON-RPC 2.0 stdio Server Loop
# =============================================================================
def send_response(response: Dict[str, Any]) -> None:
    """Writes a JSON-RPC response to stdout followed by newline."""
    data = json.dumps(response, ensure_ascii=False)
    sys.stdout.write(data + "\n")
    sys.stdout.flush()


def run_stdio_server():
    """Main stdio JSON-RPC loop handling MCP requests."""
    logger.info("Cephalo sovereign MCP server started on stdio.")

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON request.")
                continue

            req_id = request.get("id")
            method = request.get("method")
            params = request.get("params", {})

            # 1. Initialize
            if method == "initialize":
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {},
                        },
                        "serverInfo": {
                            "name": "cephalo-sovereign-memory",
                            "version": "1.0.0",
                        },
                    },
                })

            # 2. Initialized Notification
            elif method == "notifications/initialized":
                # Notification requires no response
                pass

            # 3. Ping
            elif method == "ping":
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {},
                })

            # 4. Tools List
            elif method == "tools/list":
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": get_tool_definitions(),
                    },
                })

            # 5. Tools Call
            elif method == "tools/call":
                tool_name = params.get("name", "")
                tool_args = params.get("arguments", {})

                result_data = handle_tool_call(tool_name, tool_args)
                result_text = json.dumps(result_data, indent=2, ensure_ascii=False)

                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result_text,
                            }
                        ],
                    },
                })

            # 6. Unknown method
            else:
                if req_id is not None:
                    send_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: '{method}'",
                        },
                    })

        except Exception as e:
            logger.error(f"Unhandled error in stdio server loop: {e}", exc_info=True)


if __name__ == "__main__":
    run_stdio_server()

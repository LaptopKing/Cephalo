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

# Force UTF-8 on Windows stdio for JSON-RPC messages
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Set up logging to stderr so stdout is strictly preserved for JSON-RPC messages
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [Cephalo:MCP] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger("cephalo.mcp")

# Base paths
ROOT_DIR = Path(__file__).resolve().parents[3]
SCRIPT_DIR = ROOT_DIR
PROFILE_FILE = ROOT_DIR / "USER_PROFILE.md"

# Add root and src directory to sys.path so modules can be imported directly
for p_dir in (str(ROOT_DIR), str(ROOT_DIR / "src")):
    if p_dir not in sys.path:
        sys.path.insert(0, p_dir)


from cephalo.services.mcp_definitions import get_tool_definitions


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
            supersedes = arguments.get("supersedes")
            auto_reconcile = arguments.get("auto_reconcile", True)

            rec = pipeline.ingest_prompt(
                raw_text=text,
                category=category,
                source="mcp_agent",
                intent=intent,
                supersedes=supersedes,
                sync_to_jsonl=True,
                auto_reconcile=auto_reconcile,
            )
            clean_rec = {k: v for k, v in rec.items() if k != "vector"}
            return {
                "status": "success",
                "recorded": clean_rec,
                "superseded_records": rec.get("superseded_records", []),
            }

        elif name == "cephalo_get_profile":
            if not PROFILE_FILE.exists():
                return {"error": "USER_PROFILE.md not found"}
            return {"content": PROFILE_FILE.read_text(encoding="utf-8")}

        elif name == "cephalo_list_specialties":
            from cephalo.learning.specialties_manager import SpecialtiesManager
            sm = SpecialtiesManager()
            project = arguments.get("project")
            items = sm.list_specialties(project=project)
            return {"count": len(items), "specialties": items}

        elif name == "cephalo_get_specialty":
            from cephalo.learning.specialties_manager import SpecialtiesManager
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
            from cephalo.learning.specialties_manager import SpecialtiesManager
            sm = SpecialtiesManager()
            topic = arguments.get("topic", "")
            project = arguments.get("project", "global")
            spec = sm.auto_create_specialty(topic, project=project, sync_to_vector_db=False)
            return {"status": "success", "specialty": spec}

        elif name == "cephalo_continuous_learn":
            from cephalo.learning.continuous_learner import ContinuousLearner
            learner = ContinuousLearner()
            report = learner.run_cycle()
            return {"status": "success", "report": report}

        elif name == "cephalo_learning_status":
            from cephalo.learning.continuous_learner import ContinuousLearner
            learner = ContinuousLearner()
            return {"status": "success", "state": learner.state}

        elif name == "cephalo_deep_research":
            from cephalo.research.research_engine import DeepResearchEngine
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
                from cephalo.learning.specialties_manager import SpecialtiesManager
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

        elif name == "cephalo_web_search":
            from cephalo.research.web_search import WebSearchEngine
            engine = WebSearchEngine()
            query = arguments.get("query", "")
            limit = arguments.get("limit", 5)
            include_social = arguments.get("include_social", True)
            html_ui = arguments.get("html_ui", False)

            serp = engine.search_serp(query=query, max_results=limit, include_social=include_social)
            res = serp.to_dict()
            if html_ui:
                import re
                slug = re.sub(r'[^a-z0-9]+', '-', query.lower()).strip('-')[:40] or "search"
                out_path = SCRIPT_DIR / "data" / "serp_cache" / f"{slug}.html"
                engine.render_serp_html(serp, output_path=out_path, standalone=True)
                res["html_file"] = str(out_path)
            return res

        elif name == "cephalo_run_sandboxed":
            from cephalo.services.sandboxed_runner import SandboxedRunner
            runner = SandboxedRunner()
            return runner.run_code(
                code=arguments.get("code", ""),
                language=arguments.get("language", "python"),
                allow_network=arguments.get("allow_network", False),
                timeout_seconds=arguments.get("timeout_seconds", 30),
            )

        elif name == "cephalo_task_checkpoint":
            from cephalo.core.task_ledger import TaskLedger
            ledger = TaskLedger()
            task_id = arguments.get("task_id", "")
            if not ledger.get_task(task_id):
                ledger.register_task(
                    task_id=task_id,
                    conversation_id=arguments.get("conversation_id", "default"),
                    assignee_agent=arguments.get("assignee_agent", "subagent"),
                    user_goal=arguments.get("user_goal", "Autonomous subtask"),
                    total_steps=arguments.get("total_steps", 1),
                )
            return ledger.checkpoint(
                task_id=task_id,
                step_index=arguments.get("step_index", 0),
                checkpoint_state=arguments.get("checkpoint_state", {}),
                token_usage=arguments.get("token_usage"),
                pause_reason=arguments.get("pause_reason"),
                reset_seconds=arguments.get("reset_seconds"),
            )

        elif name == "cephalo_task_resume":
            from cephalo.core.task_ledger import TaskLedger
            ledger = TaskLedger()
            task_id = arguments.get("task_id")
            if task_id:
                task = ledger.get_task(task_id)
                return {"task": task}
            else:
                resumable = ledger.get_resumable_tasks(arguments.get("assignee_agent"))
                return {"resumable_tasks": resumable}

        elif name == "cephalo_task_list":
            from cephalo.core.task_ledger import TaskLedger
            ledger = TaskLedger()
            tasks = ledger.list_tasks(
                conversation_id=arguments.get("conversation_id"),
                status=arguments.get("status"),
                limit=arguments.get("limit", 20),
            )
            return {"tasks": tasks, "count": len(tasks)}

        elif name == "cephalo_web_fetch":
            from cephalo.research.web_search import WebSearchEngine
            engine = WebSearchEngine()
            url = arguments.get("url", "")
            dynamic = arguments.get("dynamic", False)
            max_chars = arguments.get("max_chars", 15000)
            text = engine.fetch_url(url, max_chars=max_chars, dynamic=dynamic)
            return {"url": url, "content": text}

        elif name == "cephalo_migrate":
            from cephalo.core.migration import MigrationManager, MigrationScope
            manager = MigrationManager()
            action = arguments.get("action", "export")

            if action == "export":
                scope_str = arguments.get("scope", "settings")
                scope = MigrationScope.ALL if scope_str == "all" else MigrationScope.SETTINGS
                out_p = Path(arguments["output_path"]) if arguments.get("output_path") else None
                inc_secrets = arguments.get("include_secrets", False)
                return manager.create_migration(scope=scope, output_path=out_p, include_secrets=inc_secrets)

            elif action == "restore":
                arch_str = arguments.get("archive_path")
                if not arch_str:
                    return {"error": "'archive_path' is required for restore action."}
                dry_run = arguments.get("dry_run", False)
                return manager.restore_migration(Path(arch_str), dry_run=dry_run)

            elif action == "inspect":
                arch_str = arguments.get("archive_path")
                if not arch_str:
                    return {"error": "'archive_path' is required for inspect action."}
                return manager.inspect_migration(Path(arch_str))

            elif action == "list":
                archives = manager.list_migrations()
                return {"count": len(archives), "archives": archives}

            else:
                return {"error": f"Invalid migration action '{action}'. Choose from export, restore, inspect, list."}

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

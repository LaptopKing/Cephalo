"""
Shared CLI paths, constants, and pipeline helpers.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[3]
BASE_DIR = ROOT_DIR
DATA_DIR = ROOT_DIR / "data"
PROMPTS_FILE = DATA_DIR / "prompts.jsonl"
DEFAULT_LANCEDB_DIR = DATA_DIR / "lancedb"
PROFILE_FILE = ROOT_DIR / "USER_PROFILE.md"
DEFAULT_MCP_CONFIG = ROOT_DIR / ".gemini/config/plugins/cephalo/mcp_config.json"

logger = logging.getLogger("cephalo.cli")

def get_pipeline(table_name: Optional[str] = None):
    """Lazy loader for EmbeddingPipeline to keep light commands (status, profile) sub-second."""
    from cephalo.core.embedding_pipeline import EmbeddingPipeline, create_embedder
    embedder = create_embedder(mode="local")
    return EmbeddingPipeline(embedder=embedder, db_path=DEFAULT_LANCEDB_DIR, table_name=table_name)


def parse_profile_sections(content: str) -> List[Dict[str, Any]]:
    """Splits USER_PROFILE.md into markdown sections delineated by '## '."""
    sections = []
    current_title = "Preamble"
    current_lines: List[str] = []

    for line in content.splitlines():
        if line.startswith("## "):
            if current_lines:
                sec_text = "\n".join(current_lines).strip()
                while sec_text.endswith("---"):
                    sec_text = sec_text[:-3].strip()
                sections.append({
                    "title": current_title,
                    "content": sec_text,
                    "tokens_est": round(len(sec_text) / 3.8)
                })
            current_title = line.lstrip("#").strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sec_text = "\n".join(current_lines).strip()
        while sec_text.endswith("---"):
            sec_text = sec_text[:-3].strip()
        sections.append({
            "title": current_title,
            "content": sec_text,
            "tokens_est": round(len(sec_text) / 3.8)
        })
    return sections


def resolve_cli_input(
    args: Any,
    field_name: str = "text",
    allow_clip: bool = False,
    allow_stdin: bool = True,
    error_message: Optional[str] = None,
) -> str:
    """Consistently resolves CLI input from argument, clipboard (--clip), or piped stdin."""
    val = getattr(args, field_name, None)

    if allow_clip and getattr(args, "clip", False):
        from cephalo.utils.clipboard_utils import get_clipboard_text
        clip_content = get_clipboard_text()
        if clip_content:
            return clip_content
        print("Error: System clipboard is empty.")
        sys.exit(1)

    if allow_stdin and (not val or val == "-"):
        if not sys.stdin.isatty():
            val = sys.stdin.read().strip()

    if not val:
        default_err = f"Error: No {field_name} provided. Provide via argument or pipe via stdin."
        print(error_message or default_err)
        sys.exit(1)

    return val



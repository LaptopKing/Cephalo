"""
Cephalo Sovereign Memory - Universal Migration Engine (migration.py)
====================================================================
High-performance, lossless, multi-harness migration engine for Cephalo
and all integrated AI agent harnesses (Antigravity, Claude Code, Cursor,
Windsurf, Aider, Copilot, etc.).

Features:
- Two Migration Scopes:
  1. `settings` (Default): All Cephalo configuration, user profile, safeguards,
     specialties, patterns, rules, skills, MCP connections, hooks, and multi-harness settings.
  2. `all` (--all): Everything in settings + Cephalo vector database (LanceDB),
     prompt interaction memory, task ledgers, search caches, screen frames,
     all scratch workspace projects, and AI agent harness brains/transcripts.
- Maximum Lossless Compression:
  - Default: LZMA2 (.cephalo.tar.xz) with preset 9 + EXTREME filter for the
    smallest possible lossless archive size.
  - Automatic filtering of non-reproducible ephemeral junk (__pycache__, .pytest_cache,
    .DS_Store, build caches like target/) to maximize compression ratio.
  - Safe atomic SQLite backups via the native SQLite backup API (zero WAL corruption).
- Bit-for-Bit Integrity:
  - SHA-256 checksum generated for every single file before packaging.
  - Full cryptographic verification during restoration.
- Single-Command Setup & Restoration:
  - `cephalo migrate restore <archive>`: Inspects, validates, unpacks losslessly,
    creates automatic safety backups (.bak.<ts>), adaptively merges harness configs
    non-destructively, verifies LanceDB tables, and sets up everything in one shot.
"""

from __future__ import annotations

import concurrent.futures
import dataclasses
import datetime
import enum
import hashlib
import io
import json
import logging
import lzma
import os
import platform
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import time
import zipfile
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from cephalo.config import (
    DATA_DIR,
    DEFAULT_LANCEDB_DIR,
    DOCS_DIR,
    MIGRATIONS_DIR,
    PATTERNS_DIR,
    PROFILE_FILE,
    PROMPTS_FILE,
    ROOT_DIR,
    SPECIALTIES_DIR,
    SRC_DIR,
)

logger = logging.getLogger("cephalo.migration")


class MigrationScope(str, enum.Enum):
    SETTINGS = "settings"
    ALL = "all"


class CompressionFormat(str, enum.Enum):
    XZ = "xz"
    GZ = "gz"
    ZIP = "zip"


# Ephemeral / cache files that must always be excluded from lossless backups
EPHEMERAL_PATTERNS: Set[str] = {
    "__pycache__",
    ".pytest_cache",
    ".coverage",
    "htmlcov",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.tmp",
    "*.sock",
    "*.swp",
    "*.swo",
    "*~",
    "*.db-wal",
    "*.db-shm",
    "*.tar.xz",
    "*.tar.gz",
    "*.tar",
    "*.cephalo.*",
}

# Build directories excluded unless user passes --include-build-artifacts
BUILD_CACHE_DIRECTORIES: Set[str] = {
    "target",        # Rust compiler build dir
    ".venv",         # Python virtual environments (host/OS specific)
    "venv",
    "node_modules",  # Third-party npm dependencies (host/OS specific, restored via npm/bun install)
    ".next",         # Next.js build cache
    ".turbo",        # Turborepo build cache
    ".nuxt",         # Nuxt build cache
    "ms-playwright", # Playwright headless browser binaries
    ".playwright",
    ".cache",
}


@dataclasses.dataclass
class FileEntry:
    archive_path: str
    source_path: str
    category: str
    size: int
    sha256: str
    modified_at: str

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FileEntry:
        return cls(**data)


@dataclasses.dataclass
class MigrationManifest:
    version: str = "1.0.0"
    cephalo_version: str = "1.1.0"
    scope: str = "settings"
    format: str = "xz"
    created_at: str = ""
    source_host: str = ""
    source_os: str = ""
    source_python: str = ""
    source_cephalo_dir: str = ""
    total_files: int = 0
    total_uncompressed_bytes: int = 0
    compressed_bytes: int = 0
    harnesses_detected: List[str] = dataclasses.field(default_factory=list)
    projects_detected: List[str] = dataclasses.field(default_factory=list)
    files: List[Dict[str, Any]] = dataclasses.field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MigrationManifest:
        return cls(**data)


def compute_sha256(path: Path) -> str:
    """Computes SHA-256 hash of a file with streaming chunks."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_bytes_sha256(data: bytes) -> str:
    """Computes SHA-256 hash of in-memory bytes."""
    return hashlib.sha256(data).hexdigest()


def should_exclude(rel_path: str, include_build_artifacts: bool = False) -> bool:
    """Checks whether a relative file path matches ephemeral junk or build caches."""
    parts = Path(rel_path).parts
    for p in parts:
        if p in EPHEMERAL_PATTERNS:
            return True
        if p.endswith((".pyc", ".pyo", ".pyd", ".tmp", ".swp", ".swo", ".db-wal", ".db-shm")):
            return True
        if p.startswith("task-") and p.endswith(".log"):
            return True
        if not include_build_artifacts and p in BUILD_CACHE_DIRECTORIES:
            return True
    if "skills" in parts and ".git" in parts:
        return True
    if "plugins" in parts and ".git" in parts:
        return True
    if ".system_generated" in parts and "tasks" in parts:
        return True
    return False


# =============================================================================
# Multi-Harness Detection & Extraction
# =============================================================================
class HarnessDetector:
    """Discovers and extracts configuration for all supported AI agent harnesses."""

    @staticmethod
    def get_home_dir() -> Path:
        return Path.home()

    @staticmethod
    def detect_antigravity() -> Optional[Dict[str, Any]]:
        """Detects Google Antigravity harness paths and configuration."""
        home = HarnessDetector.get_home_dir()
        base = home / ".gemini"
        if not base.exists():
            return None

        config_dir = base / "config"
        antigravity_dir = base / "antigravity"

        return {
            "name": "antigravity",
            "base": base,
            "config_dir": config_dir,
            "antigravity_dir": antigravity_dir,
            "rules_dir": config_dir / "rules" if config_dir.exists() else None,
            "skills_dir": config_dir / "skills" if config_dir.exists() else None,
            "plugins_dir": config_dir / "plugins" if config_dir.exists() else None,
            "projects_dir": config_dir / "projects" if config_dir.exists() else None,
            "sidecars_dir": config_dir / "sidecars" if config_dir.exists() else None,
            "hooks_file": config_dir / "hooks.json" if config_dir.exists() else None,
            "mcp_file": config_dir / "mcp_config.json" if config_dir.exists() else None,
            "config_file": config_dir / "config.json" if config_dir.exists() else None,
            "agents_md": base / "AGENTS.md" if (base / "AGENTS.md").exists() else None,
            "gemini_md": base / "GEMINI.md" if (base / "GEMINI.md").exists() else None,
            "brain_dir": antigravity_dir / "brain" if antigravity_dir.exists() else None,
            "scratch_dir": antigravity_dir / "scratch" if antigravity_dir.exists() else None,
        }

    @staticmethod
    def detect_claude_code() -> Optional[Dict[str, Any]]:
        """Detects Claude Code CLI harness paths and configuration."""
        home = HarnessDetector.get_home_dir()
        claude_dir = home / ".claude"
        claude_md = claude_dir / "CLAUDE.md"
        config_file = claude_dir / "config.json"
        settings_file = claude_dir / "settings.json"

        if claude_dir.exists() or claude_md.exists():
            return {
                "name": "claude_code",
                "claude_dir": claude_dir,
                "claude_md": claude_md if claude_md.exists() else None,
                "config_file": config_file if config_file.exists() else None,
                "settings_file": settings_file if settings_file.exists() else None,
            }
        return None

    @staticmethod
    def detect_cursor() -> Optional[Dict[str, Any]]:
        """Detects Cursor IDE harness paths, MCP config, and rules."""
        appdata = os.environ.get("APPDATA")
        cursor_mcp = None
        cursor_user = None

        if appdata:
            mcp_p = Path(appdata) / "Cursor" / "User" / "globalStorage" / "rooveterinaryinc.cursor-mcp" / "mcp.json"
            if mcp_p.exists():
                cursor_mcp = mcp_p
            user_p = Path(appdata) / "Cursor" / "User"
            if user_p.exists():
                cursor_user = user_p

        home = HarnessDetector.get_home_dir()
        home_cursor = home / ".cursor"
        home_cursorrules = home / ".cursorrules"

        if cursor_mcp or cursor_user or home_cursor.exists() or home_cursorrules.exists():
            return {
                "name": "cursor",
                "cursor_mcp": cursor_mcp,
                "cursor_user": cursor_user,
                "home_cursor": home_cursor if home_cursor.exists() else None,
                "home_cursorrules": home_cursorrules if home_cursorrules.exists() else None,
            }
        return None

    @staticmethod
    def detect_windsurf() -> Optional[Dict[str, Any]]:
        """Detects Windsurf Cascade harness paths, MCP config, and rules."""
        home = HarnessDetector.get_home_dir()
        windsurf_dir = home / ".codeium" / "windsurf"
        mcp_file = windsurf_dir / "mcp_config.json"
        rules_file = home / ".windsurfrules"

        if windsurf_dir.exists() or rules_file.exists():
            return {
                "name": "windsurf",
                "windsurf_dir": windsurf_dir,
                "mcp_file": mcp_file if mcp_file.exists() else None,
                "rules_file": rules_file if rules_file.exists() else None,
            }
        return None

    @staticmethod
    def detect_aider() -> Optional[Dict[str, Any]]:
        """Detects Aider configuration files in home directory."""
        home = HarnessDetector.get_home_dir()
        conf = home / ".aider.conf.yml"
        model_settings = home / ".aider.model.settings.yml"
        metadata = home / ".aider.model.metadata.json"

        files = [p for p in (conf, model_settings, metadata) if p.exists()]
        if files:
            return {"name": "aider", "files": files}
        return None

    @staticmethod
    def detect_copilot() -> Optional[Dict[str, Any]]:
        """Detects GitHub Copilot instructions and configurations."""
        home = HarnessDetector.get_home_dir()
        copilot_config = home / ".config" / "github-copilot"
        copilot_instructions = home / ".github" / "copilot-instructions.md"

        if copilot_config.exists() or copilot_instructions.exists():
            return {
                "name": "copilot",
                "config_dir": copilot_config if copilot_config.exists() else None,
                "instructions_file": copilot_instructions if copilot_instructions.exists() else None,
            }
        return None

    @classmethod
    def detect_all(cls) -> Dict[str, Dict[str, Any]]:
        """Scans and detects all active agent harnesses on the current system."""
        detectors = {
            "antigravity": cls.detect_antigravity,
            "claude_code": cls.detect_claude_code,
            "cursor": cls.detect_cursor,
            "windsurf": cls.detect_windsurf,
            "aider": cls.detect_aider,
            "copilot": cls.detect_copilot,
        }
        found = {}
        for name, fn in detectors.items():
            res = fn()
            if res:
                found[name] = res
        return found


# =============================================================================
# Migration Manager
# =============================================================================

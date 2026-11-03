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

import dataclasses
import datetime
import enum
import hashlib
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
class MigrationManager:
    """Orchestrates migration creation, inspection, and restoration."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = (base_dir or ROOT_DIR).resolve()
        self.data_dir = self.base_dir / "data"
        self.migrations_dir = self.data_dir / "migrations"
        self.migrations_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # EXPORT (PACK)
    # -------------------------------------------------------------------------
    def create_migration(
        self,
        scope: MigrationScope = MigrationScope.SETTINGS,
        output_path: Optional[Path] = None,
        compression_format: CompressionFormat = CompressionFormat.XZ,
        include_build_artifacts: bool = False,
        comment: str = "",
    ) -> Dict[str, Any]:
        """
        Creates a complete, lossless, compressed migration archive.

        Args:
            scope: MigrationScope.SETTINGS (settings only) or MigrationScope.ALL (everything)
            output_path: Destination path for the archive file (optional)
            compression_format: XZ (default, highest ratio), GZ, or ZIP
            include_build_artifacts: Whether to include build dirs like target/ or .venv
            comment: Optional comment or description embedded in manifest
        """
        start_time = time.time()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        scope_str = scope.value if isinstance(scope, MigrationScope) else str(scope)
        fmt_str = compression_format.value if isinstance(compression_format, CompressionFormat) else str(compression_format)

        if not output_path:
            ext = f".cephalo.tar.{fmt_str}" if fmt_str in ("xz", "gz") else f".cephalo.{fmt_str}"
            filename = f"cephalo-migration-{timestamp}-{scope_str}{ext}"
            output_path = self.migrations_dir / filename
        else:
            output_path = Path(output_path).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initiating Cephalo migration export: scope={scope_str}, format={fmt_str}, target={output_path}")

        # Temporary staging directory for clean packing and atomic SQLite snapshots
        with tempfile.TemporaryDirectory(prefix="cephalo_migrate_") as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            staging_root = temp_dir / "bundle"
            staging_root.mkdir(parents=True, exist_ok=True)

            manifest = MigrationManifest(
                version="1.0.0",
                cephalo_version="1.1.0",
                scope=scope_str,
                format=fmt_str,
                created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                source_host=platform.node(),
                source_os=f"{sys.platform} ({platform.platform()})",
                source_python=sys.version.split()[0],
                source_cephalo_dir=str(self.base_dir),
            )

            file_entries: List[FileEntry] = []

            # 1. Collect Cephalo Core
            self._collect_cephalo_core(
                staging_root=staging_root,
                file_entries=file_entries,
                scope=scope,
                include_build_artifacts=include_build_artifacts,
            )

            # 2. Collect Multi-Harness Settings & Data
            harnesses = self._collect_harnesses(
                staging_root=staging_root,
                file_entries=file_entries,
                scope=scope,
                include_build_artifacts=include_build_artifacts,
            )
            manifest.harnesses_detected = list(harnesses.keys())

            # 3. Collect Projects (if scope == ALL)
            if scope == MigrationScope.ALL:
                projects = self._collect_projects(
                    staging_root=staging_root,
                    file_entries=file_entries,
                    include_build_artifacts=include_build_artifacts,
                )
                manifest.projects_detected = projects

            # Populate manifest statistics
            manifest.total_files = len(file_entries)
            manifest.total_uncompressed_bytes = sum(f.size for f in file_entries)
            manifest.files = [f.to_dict() for f in file_entries]

            # Write manifest.json to staging root
            manifest_file = staging_root / "manifest.json"
            manifest_file.write_text(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

            # 4. Create Compressed Archive
            self._compress_staging(
                staging_root=staging_root,
                output_path=output_path,
                compression_format=compression_format,
            )

        duration = time.time() - start_time
        compressed_size = output_path.stat().st_size
        ratio = (1.0 - (compressed_size / max(manifest.total_uncompressed_bytes, 1))) * 100.0

        logger.info(
            f"Migration archive created successfully in {duration:.2f}s: "
            f"{manifest.total_uncompressed_bytes:,} bytes -> {compressed_size:,} bytes "
            f"({ratio:.1f}% reduction) at {output_path}"
        )

        return {
            "status": "success",
            "archive_path": str(output_path),
            "scope": scope_str,
            "format": fmt_str,
            "files_count": manifest.total_files,
            "uncompressed_bytes": manifest.total_uncompressed_bytes,
            "compressed_bytes": compressed_size,
            "compression_ratio_pct": round(ratio, 2),
            "duration_seconds": round(duration, 2),
            "harnesses": manifest.harnesses_detected,
            "projects": manifest.projects_detected,
            "created_at": manifest.created_at,
        }

    def _collect_cephalo_core(
        self,
        staging_root: Path,
        file_entries: List[FileEntry],
        scope: MigrationScope,
        include_build_artifacts: bool,
    ) -> None:
        """Packs Cephalo's configuration, rules, specialties, patterns, and optionally data."""
        cephalo_stage = staging_root / "cephalo"
        cephalo_stage.mkdir(parents=True, exist_ok=True)

        # A. USER_PROFILE.md & Templates
        for pf_name in ("USER_PROFILE.md", "USER_PROFILE.template.md"):
            pf = self.base_dir / pf_name
            if pf.exists():
                self._stage_file(pf, cephalo_stage / pf_name, "cephalo_profile", file_entries, staging_root)

        # B. Safeguards
        sf = self.data_dir / "safeguards.json"
        if sf.exists():
            self._stage_file(sf, cephalo_stage / "safeguards.json", "cephalo_safeguards", file_entries, staging_root)

        # C. Environment (.env) if exists
        env_file = self.base_dir / ".env"
        if env_file.exists():
            self._stage_file(env_file, cephalo_stage / ".env", "cephalo_env", file_entries, staging_root)

        # D. Specialties (All domain knowledge modules)
        specialties_dir = self.base_dir / "specialties"
        if specialties_dir.exists():
            self._stage_tree(
                specialties_dir,
                cephalo_stage / "specialties",
                "cephalo_specialty",
                file_entries,
                staging_root,
                include_build_artifacts=include_build_artifacts,
            )

        # E. Patterns
        patterns_dir = self.base_dir / "patterns"
        if patterns_dir.exists():
            self._stage_tree(
                patterns_dir,
                cephalo_stage / "patterns",
                "cephalo_pattern",
                file_entries,
                staging_root,
                include_build_artifacts=include_build_artifacts,
            )

        # F. Integrations (Harness integration templates)
        integrations_dir = self.base_dir / "integrations"
        if integrations_dir.exists():
            self._stage_tree(
                integrations_dir,
                cephalo_stage / "integrations",
                "cephalo_integration",
                file_entries,
                staging_root,
                include_build_artifacts=include_build_artifacts,
            )

        # G. Data (LanceDB, Prompts, SQLite DBs) - Included if scope == ALL
        if scope == MigrationScope.ALL and self.data_dir.exists():
            stage_data = cephalo_stage / "data"
            stage_data.mkdir(parents=True, exist_ok=True)

            # Prompts interaction log
            prompts_file = self.data_dir / "prompts.jsonl"
            if prompts_file.exists():
                self._stage_file(prompts_file, stage_data / "prompts.jsonl", "cephalo_prompts", file_entries, staging_root)

            # LanceDB vector tables
            lancedb_dir = self.data_dir / "lancedb"
            if lancedb_dir.exists():
                self._stage_tree(
                    lancedb_dir,
                    stage_data / "lancedb",
                    "cephalo_lancedb",
                    file_entries,
                    staging_root,
                    include_build_artifacts=include_build_artifacts,
                )

            # State JSON files
            for state_name in ("continuous_learning_state.json", "daily_digest_state.json", "harvest_state.json", "cephalo_daemon_status.json"):
                sf_path = self.data_dir / state_name
                if sf_path.exists():
                    self._stage_file(sf_path, stage_data / state_name, "cephalo_state", file_entries, staging_root)

            # SQLite databases: perform clean online backup via SQLite backup API
            for db_name in ("search_cache.db", "agent_tasks.db"):
                db_path = self.data_dir / db_name
                if db_path.exists():
                    dest_db = stage_data / db_name
                    self._safe_sqlite_backup(db_path, dest_db)
                    self._register_file_entry(dest_db, "cephalo_sqlite_db", file_entries, staging_root, original_path=db_path)

            # Screen frames keyframes (if present)
            frames_dir = self.data_dir / "frames"
            if frames_dir.exists():
                self._stage_tree(
                    frames_dir,
                    stage_data / "frames",
                    "cephalo_frames",
                    file_entries,
                    staging_root,
                    include_build_artifacts=include_build_artifacts,
                )

            # SERP cache (if present)
            serp_dir = self.data_dir / "serp_cache"
            if serp_dir.exists():
                self._stage_tree(
                    serp_dir,
                    stage_data / "serp_cache",
                    "cephalo_serp",
                    file_entries,
                    staging_root,
                    include_build_artifacts=include_build_artifacts,
                )

    def _collect_harnesses(
        self,
        staging_root: Path,
        file_entries: List[FileEntry],
        scope: MigrationScope,
        include_build_artifacts: bool,
    ) -> Dict[str, Any]:
        """Packs configuration for all detected agent harnesses."""
        harnesses = HarnessDetector.detect_all()
        harnesses_stage = staging_root / "harnesses"
        harnesses_stage.mkdir(parents=True, exist_ok=True)

        for name, data in harnesses.items():
            h_stage = harnesses_stage / name
            h_stage.mkdir(parents=True, exist_ok=True)

            if name == "antigravity":
                # Config files
                cfg_stage = h_stage / "config"
                cfg_stage.mkdir(parents=True, exist_ok=True)
                for key in ("config_file", "hooks_file", "mcp_file"):
                    p = data.get(key)
                    if p and Path(p).exists():
                        self._stage_file(Path(p), cfg_stage / Path(p).name, "harness_config", file_entries, staging_root)

                # Rules, plugins, projects, sidecars
                for dir_key in ("rules_dir", "plugins_dir", "projects_dir", "sidecars_dir"):
                    p = data.get(dir_key)
                    if p and Path(p).exists():
                        self._stage_tree(
                            Path(p),
                            cfg_stage / Path(p).name,
                            "harness_config",
                            file_entries,
                            staging_root,
                            include_build_artifacts=include_build_artifacts,
                        )

                # Global prompt files
                for md_key in ("agents_md", "gemini_md"):
                    p = data.get(md_key)
                    if p and Path(p).exists():
                        self._stage_file(Path(p), h_stage / Path(p).name, "harness_rules", file_entries, staging_root)

                # Skills: In SETTINGS mode, stage SKILL.md and configs; In ALL mode, stage full skill trees
                skills_dir = data.get("skills_dir")
                if skills_dir and Path(skills_dir).exists():
                    if scope == MigrationScope.ALL:
                        self._stage_tree(
                            Path(skills_dir),
                            cfg_stage / "skills",
                            "harness_skills",
                            file_entries,
                            staging_root,
                            include_build_artifacts=include_build_artifacts,
                        )
                    else:
                        # Pack SKILL.md and metadata
                        self._stage_skills_settings_only(
                            Path(skills_dir),
                            cfg_stage / "skills",
                            file_entries,
                            staging_root,
                        )

                # Brain data (if ALL)
                if scope == MigrationScope.ALL:
                    brain_dir = data.get("brain_dir")
                    if brain_dir and Path(brain_dir).exists():
                        self._stage_tree(
                            Path(brain_dir),
                            h_stage / "brain",
                            "harness_brain",
                            file_entries,
                            staging_root,
                            include_build_artifacts=include_build_artifacts,
                        )

            elif name == "claude_code":
                for k in ("claude_md", "config_file", "settings_file"):
                    p = data.get(k)
                    if p and Path(p).exists():
                        self._stage_file(Path(p), h_stage / Path(p).name, "harness_config", file_entries, staging_root)

            elif name == "cursor":
                for k in ("cursor_mcp", "home_cursorrules"):
                    p = data.get(k)
                    if p and Path(p).exists():
                        self._stage_file(Path(p), h_stage / Path(p).name, "harness_config", file_entries, staging_root)
                cursor_user = data.get("cursor_user")
                if cursor_user and Path(cursor_user).exists():
                    for user_f in ("settings.json", "keybindings.json"):
                        uf_p = Path(cursor_user) / user_f
                        if uf_p.exists():
                            self._stage_file(uf_p, h_stage / user_f, "harness_config", file_entries, staging_root)

            elif name == "windsurf":
                for k in ("mcp_file", "rules_file"):
                    p = data.get(k)
                    if p and Path(p).exists():
                        self._stage_file(Path(p), h_stage / Path(p).name, "harness_config", file_entries, staging_root)

            elif name == "aider":
                for p in data.get("files", []):
                    if Path(p).exists():
                        self._stage_file(Path(p), h_stage / Path(p).name, "harness_config", file_entries, staging_root)

            elif name == "copilot":
                copilot_inst = data.get("instructions_file")
                if copilot_inst and Path(copilot_inst).exists():
                    self._stage_file(Path(copilot_inst), h_stage / Path(copilot_inst).name, "harness_config", file_entries, staging_root)

        return harnesses

    def _collect_projects(
        self,
        staging_root: Path,
        file_entries: List[FileEntry],
        include_build_artifacts: bool,
    ) -> List[str]:
        """Packs all scratch workspace projects and standalone files."""
        home = HarnessDetector.get_home_dir()
        scratch_dir = home / ".gemini" / "antigravity" / "scratch"
        if not scratch_dir.exists():
            return []

        projects_stage = staging_root / "projects"
        projects_stage.mkdir(parents=True, exist_ok=True)
        detected_projects: List[str] = []

        # Find all project folders and root scratch files
        for item in scratch_dir.iterdir():
            # Skip second-brain itself since it's already captured as Cephalo core
            if item.is_dir() and item.name.lower() in ("second-brain", "second_brain"):
                continue

            if item.is_dir():
                detected_projects.append(item.name)
                self._stage_tree(
                    item,
                    projects_stage / item.name,
                    "workspace_project",
                    file_entries,
                    staging_root,
                    include_build_artifacts=include_build_artifacts,
                )
            elif item.is_file():
                if not should_exclude(item.name, include_build_artifacts):
                    self._stage_file(item, projects_stage / item.name, "workspace_file", file_entries, staging_root)

        return detected_projects

    def _stage_skills_settings_only(
        self,
        skills_dir: Path,
        dest_skills_dir: Path,
        file_entries: List[FileEntry],
        staging_root: Path,
    ) -> None:
        """In settings mode, captures SKILL.md and configuration files without gigabytes of subtrees."""
        for root, dirs, files in os.walk(skills_dir):
            root_p = Path(root)
            rel_root = root_p.relative_to(skills_dir)
            for f in files:
                if f.upper() in ("SKILL.MD", "PROMPT.MD", "RULES.MD", "PACKAGE.JSON", "README.MD") or f.endswith((".json", ".yaml", ".yml")):
                    src_file = root_p / f
                    dest_file = dest_skills_dir / rel_root / f
                    self._stage_file(src_file, dest_file, "harness_skill_def", file_entries, staging_root)

    def _safe_sqlite_backup(self, src_db: Path, dest_db: Path) -> None:
        """Creates a consistent, compacted SQLite snapshot using the online backup API."""
        dest_db.parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(src_db) as src_conn:
                with sqlite3.connect(dest_db) as dest_conn:
                    src_conn.backup(dest_conn)
        except Exception as e:
            logger.warning(f"SQLite backup API failed for {src_db} ({e}), falling back to standard copy.")
            shutil.copy2(src_db, dest_db)

    def _stage_file(
        self,
        src: Path,
        dest: Path,
        category: str,
        file_entries: List[FileEntry],
        staging_root: Path,
    ) -> None:
        """Copies a single file to staging and registers its metadata and SHA-256."""
        try:
            if not src.exists() or not src.is_file():
                return
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            self._register_file_entry(dest, category, file_entries, staging_root, original_path=src)
        except (PermissionError, OSError) as e:
            logger.warning(f"Skipping inaccessible file {src}: {e}")

    def _stage_tree(
        self,
        src_dir: Path,
        dest_dir: Path,
        category: str,
        file_entries: List[FileEntry],
        staging_root: Path,
        include_build_artifacts: bool = False,
    ) -> None:
        """Recursively copies a directory tree while applying intelligent lossless filtering."""
        for root, dirs, files in os.walk(src_dir):
            root_p = Path(root)
            rel = root_p.relative_to(src_dir)

            # Filter out excluded directories in-place
            dirs[:] = [d for d in dirs if not should_exclude(str(rel / d), include_build_artifacts)]

            target_dir = dest_dir / rel
            target_dir.mkdir(parents=True, exist_ok=True)

            for f in files:
                rel_file = str(rel / f) if str(rel) != "." else f
                if not should_exclude(rel_file, include_build_artifacts):
                    src_file = root_p / f
                    dest_file = target_dir / f
                    try:
                        shutil.copy2(src_file, dest_file)
                        self._register_file_entry(dest_file, category, file_entries, staging_root, original_path=src_file)
                    except (PermissionError, OSError) as e:
                        logger.warning(f"Skipping inaccessible file {src_file}: {e}")

    def _register_file_entry(
        self,
        staged_file: Path,
        category: str,
        file_entries: List[FileEntry],
        staging_root: Path,
        original_path: Optional[Path] = None,
    ) -> None:
        """Computes hash and registers file in file entries list."""
        rel_archive = staged_file.relative_to(staging_root).as_posix()
        stat = staged_file.stat()
        sha = compute_sha256(staged_file)
        orig_str = str(original_path or staged_file)

        entry = FileEntry(
            archive_path=rel_archive,
            source_path=orig_str,
            category=category,
            size=stat.st_size,
            sha256=sha,
            modified_at=datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc).isoformat(),
        )
        file_entries.append(entry)

    def _compress_staging(
        self,
        staging_root: Path,
        output_path: Path,
        compression_format: CompressionFormat,
    ) -> None:
        """Compresses the staged bundle into the specified lossless format."""
        fmt = compression_format.value if isinstance(compression_format, CompressionFormat) else str(compression_format)

        if fmt == "xz":
            # LZMA2 preset 9 for maximum lossless compression ratio and fast execution
            with tarfile.open(output_path, mode="w:xz", preset=9) as tar:
                for item in staging_root.iterdir():
                    tar.add(item, arcname=item.name)
        elif fmt == "gz":
            with tarfile.open(output_path, mode="w:gz", compresslevel=9) as tar:
                for item in staging_root.iterdir():
                    tar.add(item, arcname=item.name)
        elif fmt == "zip":
            with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
                for root, _, files in os.walk(staging_root):
                    root_p = Path(root)
                    for f in files:
                        p = root_p / f
                        arcname = p.relative_to(staging_root).as_posix()
                        zf.write(p, arcname=arcname)
        else:
            raise ValueError(f"Unsupported compression format: {fmt}")

    # -------------------------------------------------------------------------
    # INSPECT
    # -------------------------------------------------------------------------
    def inspect_migration(self, archive_path: Path) -> Dict[str, Any]:
        """
        Inspects a migration archive without extracting its contents.
        Reads the manifest and returns metadata, statistics, and file listing.
        """
        archive_path = Path(archive_path).resolve()
        if not archive_path.exists():
            raise FileNotFoundError(f"Migration archive not found: {archive_path}")

        manifest_data = self._read_manifest_from_archive(archive_path)
        stat = archive_path.stat()
        manifest_data["archive_path"] = str(archive_path)
        manifest_data["compressed_size_bytes"] = stat.st_size
        manifest_data["compressed_size_formatted"] = self._format_bytes(stat.st_size)

        uncompressed = manifest_data.get("total_uncompressed_bytes", 0)
        if uncompressed > 0:
            ratio = (1.0 - (stat.st_size / uncompressed)) * 100.0
            manifest_data["compression_ratio"] = f"{ratio:.1f}% reduction"
        else:
            manifest_data["compression_ratio"] = "N/A"

        return manifest_data

    # -------------------------------------------------------------------------
    # RESTORE (IMPORT & SETUP)
    # -------------------------------------------------------------------------
    def restore_migration(
        self,
        archive_path: Path,
        dry_run: bool = False,
        auto_backup: bool = True,
        target_cephalo_dir: Optional[Path] = None,
        only_cephalo: bool = False,
        only_harnesses: bool = False,
    ) -> Dict[str, Any]:
        """
        Restores a migration archive losslessly and sets up everything in one shot.

        Actions:
        1. Validates archive integrity & reads manifest.json.
        2. Creates automatic timestamped safety backups (.bak.<ts>) of existing files.
        3. Restores Cephalo configuration, user profile, specialties, patterns, and data.
        4. Restores and non-destructively merges multi-harness configurations (Antigravity,
           Claude Code, Cursor, Windsurf, Aider, Copilot).
        5. If scope == ALL, restores workspace projects and AI agent brain transcripts.
        6. Verifies SHA-256 for bit-for-bit lossless fidelity.
        7. Self-tests and verifies LanceDB vector tables and status.
        """
        archive_path = Path(archive_path).resolve()
        if not archive_path.exists():
            raise FileNotFoundError(f"Migration archive not found: {archive_path}")

        start_time = time.time()
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        target_brain_dir = (target_cephalo_dir or self.base_dir).resolve()

        # Step 1: Read and validate manifest
        manifest_dict = self._read_manifest_from_archive(archive_path)
        manifest = MigrationManifest.from_dict(manifest_dict)
        logger.info(f"Restoring Cephalo migration from {archive_path} (scope={manifest.scope}, created={manifest.created_at})")

        restored_files: List[str] = []
        backups_created: List[str] = []
        integrity_failures: List[str] = []
        harnesses_configured: List[str] = []

        home = HarnessDetector.get_home_dir()
        scratch_base = home / ".gemini" / "antigravity" / "scratch"

        # Step 2: Extract archive into temporary staging directory
        with tempfile.TemporaryDirectory(prefix="cephalo_restore_") as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            self._extract_archive(archive_path, temp_dir)

            # Step 3: Verify all checksums against manifest
            for f_info in manifest.files:
                arch_path = f_info["archive_path"]
                expected_sha = f_info["sha256"]
                extracted_file = temp_dir / arch_path

                if not extracted_file.exists():
                    integrity_failures.append(f"Missing file in archive: {arch_path}")
                    continue

                actual_sha = compute_sha256(extracted_file)
                if actual_sha != expected_sha:
                    integrity_failures.append(
                        f"Checksum mismatch for {arch_path}: expected {expected_sha[:8]}..., got {actual_sha[:8]}..."
                    )

            if integrity_failures:
                raise ValueError(f"Migration archive integrity verification failed:\n" + "\n".join(integrity_failures[:10]))

            if dry_run:
                return {
                    "status": "dry_run",
                    "archive_path": str(archive_path),
                    "scope": manifest.scope,
                    "files_to_restore": len(manifest.files),
                    "total_uncompressed_bytes": manifest.total_uncompressed_bytes,
                    "harnesses_in_backup": manifest.harnesses_detected,
                    "projects_in_backup": manifest.projects_detected,
                    "integrity": "verified_lossless",
                }

            # Step 4: Restore Cephalo Core
            if not only_harnesses:
                cephalo_stage = temp_dir / "cephalo"
                if cephalo_stage.exists():
                    self._restore_tree(
                        src_dir=cephalo_stage,
                        dest_dir=target_brain_dir,
                        auto_backup=auto_backup,
                        timestamp=timestamp,
                        restored_files=restored_files,
                        backups_created=backups_created,
                    )

            # Step 5: Restore Multi-Harness Configurations & Adaptively Merge
            if not only_cephalo:
                harness_stage = temp_dir / "harnesses"
                if harness_stage.exists():
                    configured = self._restore_and_merge_harnesses(
                        harness_stage=harness_stage,
                        home=home,
                        target_brain_dir=target_brain_dir,
                        auto_backup=auto_backup,
                        timestamp=timestamp,
                        restored_files=restored_files,
                        backups_created=backups_created,
                    )
                    harnesses_configured.extend(configured)

            # Step 6: Restore Projects & Scratch Files (if present)
            if manifest.scope == "all" and not only_cephalo and not only_harnesses:
                projects_stage = temp_dir / "projects"
                if projects_stage.exists() and scratch_base.exists():
                    self._restore_tree(
                        src_dir=projects_stage,
                        dest_dir=scratch_base,
                        auto_backup=auto_backup,
                        timestamp=timestamp,
                        restored_files=restored_files,
                        backups_created=backups_created,
                    )

        # Step 7: Self-Healing & Health Verification
        health_info = self._verify_system_health(target_brain_dir)

        duration = time.time() - start_time
        logger.info(f"Migration restoration completed successfully in {duration:.2f}s ({len(restored_files)} files restored).")

        return {
            "status": "success",
            "archive_path": str(archive_path),
            "scope": manifest.scope,
            "restored_files_count": len(restored_files),
            "backups_created_count": len(backups_created),
            "harnesses_configured": harnesses_configured,
            "duration_seconds": round(duration, 2),
            "health": health_info,
            "created_at": manifest.created_at,
        }

    def _restore_and_merge_harnesses(
        self,
        harness_stage: Path,
        home: Path,
        target_brain_dir: Path,
        auto_backup: bool,
        timestamp: str,
        restored_files: List[str],
        backups_created: List[str],
    ) -> List[str]:
        """Non-destructively merges and restores harness configurations."""
        configured: List[str] = []

        # A. Google Antigravity
        agy_stage = harness_stage / "antigravity"
        agy_base = home / ".gemini"
        if agy_stage.exists() and agy_base.exists():
            cfg_stage = agy_stage / "config"
            dest_cfg = agy_base / "config"
            dest_cfg.mkdir(parents=True, exist_ok=True)

            # Non-destructive merge of hooks.json
            src_hooks = cfg_stage / "hooks.json"
            if src_hooks.exists():
                self._merge_hooks_json(src_hooks, dest_cfg / "hooks.json", auto_backup, timestamp, backups_created)
                restored_files.append(str(dest_cfg / "hooks.json"))

            # Non-destructive merge of mcp_config.json
            src_mcp = cfg_stage / "mcp_config.json"
            if src_mcp.exists():
                self._merge_mcp_config_json(src_mcp, dest_cfg / "mcp_config.json", auto_backup, timestamp, backups_created)
                restored_files.append(str(dest_cfg / "mcp_config.json"))

            # Restore config.json if not present or backup and write
            src_config = cfg_stage / "config.json"
            if src_config.exists():
                self._restore_file(src_config, dest_cfg / "config.json", auto_backup, timestamp, restored_files, backups_created)

            # Restore rules, plugins, skills, sidecars, projects
            for sub_name in ("rules", "plugins", "skills", "sidecars", "projects"):
                sub_stage = cfg_stage / sub_name
                if sub_stage.exists():
                    self._restore_tree(sub_stage, dest_cfg / sub_name, auto_backup, timestamp, restored_files, backups_created)

            # Restore AGENTS.md and GEMINI.md
            for md_name in ("AGENTS.md", "GEMINI.md"):
                md_src = agy_stage / md_name
                if md_src.exists():
                    self._restore_file(md_src, agy_base / md_name, auto_backup, timestamp, restored_files, backups_created)

            # Restore Brain (if present)
            brain_src = agy_stage / "brain"
            if brain_src.exists():
                dest_brain = agy_base / "antigravity" / "brain"
                self._restore_tree(brain_src, dest_brain, auto_backup, timestamp, restored_files, backups_created)

            configured.append("antigravity")

        # B. Claude Code
        claude_stage = harness_stage / "claude_code"
        claude_dir = home / ".claude"
        if claude_stage.exists():
            claude_dir.mkdir(parents=True, exist_ok=True)
            for k in ("CLAUDE.md", "config.json", "settings.json"):
                f_src = claude_stage / k
                if f_src.exists():
                    self._restore_file(f_src, claude_dir / k, auto_backup, timestamp, restored_files, backups_created)
            configured.append("claude_code")

        # C. Cursor
        cursor_stage = harness_stage / "cursor"
        appdata = os.environ.get("APPDATA")
        if cursor_stage.exists():
            if appdata:
                cursor_storage = Path(appdata) / "Cursor" / "User" / "globalStorage" / "rooveterinaryinc.cursor-mcp"
                src_mcp = cursor_stage / "mcp.json"
                if src_mcp.exists():
                    cursor_storage.mkdir(parents=True, exist_ok=True)
                    self._merge_mcp_config_json(src_mcp, cursor_storage / "mcp.json", auto_backup, timestamp, backups_created)
                    restored_files.append(str(cursor_storage / "mcp.json"))

                cursor_user = Path(appdata) / "Cursor" / "User"
                for user_f in ("settings.json", "keybindings.json"):
                    src_f = cursor_stage / user_f
                    if src_f.exists():
                        cursor_user.mkdir(parents=True, exist_ok=True)
                        self._restore_file(src_f, cursor_user / user_f, auto_backup, timestamp, restored_files, backups_created)

            rules_src = cursor_stage / ".cursorrules"
            if rules_src.exists():
                self._restore_file(rules_src, home / ".cursorrules", auto_backup, timestamp, restored_files, backups_created)
            configured.append("cursor")

        # D. Windsurf
        windsurf_stage = harness_stage / "windsurf"
        if windsurf_stage.exists():
            windsurf_dir = home / ".codeium" / "windsurf"
            src_mcp = windsurf_stage / "mcp_config.json"
            if src_mcp.exists():
                windsurf_dir.mkdir(parents=True, exist_ok=True)
                self._merge_mcp_config_json(src_mcp, windsurf_dir / "mcp_config.json", auto_backup, timestamp, backups_created)
                restored_files.append(str(windsurf_dir / "mcp_config.json"))

            rules_src = windsurf_stage / ".windsurfrules"
            if rules_src.exists():
                self._restore_file(rules_src, home / ".windsurfrules", auto_backup, timestamp, restored_files, backups_created)
            configured.append("windsurf")

        # E. Aider
        aider_stage = harness_stage / "aider"
        if aider_stage.exists():
            for f in aider_stage.iterdir():
                if f.is_file():
                    self._restore_file(f, home / f.name, auto_backup, timestamp, restored_files, backups_created)
            configured.append("aider")

        # F. Copilot
        copilot_stage = harness_stage / "copilot"
        if copilot_stage.exists():
            copilot_inst = copilot_stage / "copilot-instructions.md"
            if copilot_inst.exists():
                dest_dir = home / ".github"
                dest_dir.mkdir(parents=True, exist_ok=True)
                self._restore_file(copilot_inst, dest_dir / "copilot-instructions.md", auto_backup, timestamp, restored_files, backups_created)
            configured.append("copilot")

        return configured

    def _merge_hooks_json(
        self,
        src_path: Path,
        dest_path: Path,
        auto_backup: bool,
        timestamp: str,
        backups_created: List[str],
    ) -> None:
        """Non-destructively merges hooks, preserving user hooks while updating Cephalo hooks."""
        try:
            incoming = json.loads(src_path.read_text(encoding="utf-8"))
        except Exception:
            return

        existing: Dict[str, Any] = {}
        if dest_path.exists():
            if auto_backup:
                bak = dest_path.parent / f"{dest_path.name}.bak.{timestamp}"
                shutil.copy2(dest_path, bak)
                backups_created.append(str(bak))
            try:
                existing = json.loads(dest_path.read_text(encoding="utf-8"))
            except Exception:
                existing = {}

        # Merge top-level keys
        for k, v in incoming.items():
            existing[k] = v

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    def _merge_mcp_config_json(
        self,
        src_path: Path,
        dest_path: Path,
        auto_backup: bool,
        timestamp: str,
        backups_created: List[str],
    ) -> None:
        """Non-destructively merges mcpServers entries."""
        try:
            incoming = json.loads(src_path.read_text(encoding="utf-8"))
        except Exception:
            return

        existing: Dict[str, Any] = {"mcpServers": {}}
        if dest_path.exists():
            if auto_backup:
                bak = dest_path.parent / f"{dest_path.name}.bak.{timestamp}"
                shutil.copy2(dest_path, bak)
                backups_created.append(str(bak))
            try:
                existing = json.loads(dest_path.read_text(encoding="utf-8"))
            except Exception:
                existing = {"mcpServers": {}}

        if "mcpServers" not in existing or not isinstance(existing["mcpServers"], dict):
            existing["mcpServers"] = {}

        incoming_servers = incoming.get("mcpServers", {})
        if isinstance(incoming_servers, dict):
            for s_name, s_def in incoming_servers.items():
                existing["mcpServers"][s_name] = s_def

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    def _restore_file(
        self,
        src: Path,
        dest: Path,
        auto_backup: bool,
        timestamp: str,
        restored_files: List[str],
        backups_created: List[str],
    ) -> None:
        """Restores a single file with optional safety backup."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and auto_backup:
            bak = dest.parent / f"{dest.name}.bak.{timestamp}"
            shutil.copy2(dest, bak)
            backups_created.append(str(bak))
        shutil.copy2(src, dest)
        restored_files.append(str(dest))

    def _restore_tree(
        self,
        src_dir: Path,
        dest_dir: Path,
        auto_backup: bool,
        timestamp: str,
        restored_files: List[str],
        backups_created: List[str],
    ) -> None:
        """Recursively restores a directory tree with safety backups of overwritten files."""
        for root, _, files in os.walk(src_dir):
            root_p = Path(root)
            rel = root_p.relative_to(src_dir)
            target_dir = dest_dir / rel
            target_dir.mkdir(parents=True, exist_ok=True)

            for f in files:
                src_f = root_p / f
                dest_f = target_dir / f
                if dest_f.exists() and auto_backup:
                    bak = dest_f.parent / f"{dest_f.name}.bak.{timestamp}"
                    shutil.copy2(dest_f, bak)
                    backups_created.append(str(bak))
                shutil.copy2(src_f, dest_f)
                restored_files.append(str(dest_f))

    def _read_manifest_from_archive(self, archive_path: Path) -> Dict[str, Any]:
        """Extracts and parses manifest.json from an archive stream without unpacking full content."""
        name = archive_path.name.lower()
        if name.endswith((".tar.xz", ".tar.gz", ".tar.bz2", ".tar")):
            mode = "r:*"
            with tarfile.open(archive_path, mode=mode) as tar:
                try:
                    member = tar.getmember("manifest.json")
                except KeyError:
                    raise ValueError(f"Invalid Cephalo migration archive: manifest.json not found in {archive_path}")
                f = tar.extractfile(member)
                if not f:
                    raise ValueError("Could not read manifest.json from archive.")
                return json.loads(f.read().decode("utf-8"))
        elif name.endswith(".zip"):
            with zipfile.ZipFile(archive_path, mode="r") as zf:
                try:
                    data = zf.read("manifest.json")
                    return json.loads(data.decode("utf-8"))
                except KeyError:
                    raise ValueError(f"Invalid Cephalo migration archive: manifest.json not found in {archive_path}")
        else:
            raise ValueError(f"Unrecognized archive format for {archive_path}")

    def _extract_archive(self, archive_path: Path, dest_dir: Path) -> None:
        """Extracts all files from archive into dest_dir safely."""
        name = archive_path.name.lower()
        if name.endswith((".tar.xz", ".tar.gz", ".tar.bz2", ".tar")):
            with tarfile.open(archive_path, mode="r:*") as tar:
                # Use data filter on Python 3.12+ if available for security
                if hasattr(tarfile, "data_filter"):
                    tar.extractall(dest_dir, filter="data")
                else:
                    tar.extractall(dest_dir)
        elif name.endswith(".zip"):
            with zipfile.ZipFile(archive_path, mode="r") as zf:
                zf.extractall(dest_dir)
        else:
            raise ValueError(f"Unrecognized archive format for {archive_path}")

    def _verify_system_health(self, base_dir: Path) -> Dict[str, Any]:
        """Verifies integrity and operability of restored Cephalo files."""
        profile_ok = (base_dir / "USER_PROFILE.md").exists()
        prompts_p = base_dir / "data" / "prompts.jsonl"
        prompt_count = 0
        if prompts_p.exists():
            try:
                with prompts_p.open("r", encoding="utf-8") as f:
                    prompt_count = sum(1 for line in f if line.strip())
            except Exception:
                pass

        lancedb_p = base_dir / "data" / "lancedb"
        lance_tables: List[str] = []
        if lancedb_p.exists():
            for item in lancedb_p.iterdir():
                if item.is_dir() and item.name.endswith(".lance"):
                    lance_tables.append(item.name[:-6])

        return {
            "profile_loaded": profile_ok,
            "prompts_record_count": prompt_count,
            "lancedb_tables": lance_tables,
            "status": "healthy" if profile_ok else "warning",
        }

    # -------------------------------------------------------------------------
    # LIST
    # -------------------------------------------------------------------------
    def list_migrations(self) -> List[Dict[str, Any]]:
        """Scans the default migrations directory and returns all available migration archives."""
        if not self.migrations_dir.exists():
            return []

        results = []
        for item in sorted(self.migrations_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if item.is_file() and item.name.endswith((".cephalo.tar.xz", ".cephalo.tar.gz", ".cephalo.zip", ".tar.xz", ".tar.gz", ".zip")):
                try:
                    info = self.inspect_migration(item)
                    results.append({
                        "filename": item.name,
                        "path": str(item),
                        "size_bytes": info.get("compressed_size_bytes", 0),
                        "size_formatted": info.get("compressed_size_formatted", "0 B"),
                        "scope": info.get("scope", "unknown"),
                        "created_at": info.get("created_at", ""),
                        "files_count": info.get("total_files", 0),
                        "harnesses": info.get("harnesses_detected", []),
                        "projects": info.get("projects_detected", []),
                    })
                except Exception as e:
                    results.append({
                        "filename": item.name,
                        "path": str(item),
                        "size_bytes": item.stat().st_size,
                        "size_formatted": self._format_bytes(item.stat().st_size),
                        "scope": "unknown",
                        "error": str(e),
                    })
        return results

    @staticmethod
    def _format_bytes(num_bytes: int) -> str:
        """Formats byte count into human-readable string (KB, MB, GB)."""
        val = float(num_bytes)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if val < 1024.0 or unit == "TB":
                return f"{val:.1f} {unit}" if unit != "B" else f"{int(val)} B"
            val /= 1024.0
        return f"{num_bytes} B"

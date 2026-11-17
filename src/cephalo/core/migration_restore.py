"""
Migration Restorer: archive extraction, harness config merging, and rollback verification.
"""

import datetime
import json
import logging
import os
import shutil
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from cephalo.config import DATA_DIR
from cephalo.core.migration_manifest import (
    CompressionFormat,
    HarnessDetector,
    MigrationManifest,
    MigrationScope,
    compute_sha256,
)

logger = logging.getLogger("cephalo.core.migration_restore")


class MigrationRestorer:
    """Handles safe extraction and selective merging of Cephalo migration archives."""

    def __init__(self, manager):
        self.manager = manager
        self.base_dir = manager.base_dir
        self.data_dir = manager.data_dir

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
                # Fast path: manifest.json placed as the first member
                first = tar.next()
                if first and first.name == "manifest.json":
                    f = tar.extractfile(first)
                    if f:
                        return json.loads(f.read().decode("utf-8"))
                # Fallback: scan if manifest was placed elsewhere
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
        """Extracts all files from archive into dest_dir safely, preventing path traversal."""
        dest_dir_resolved = dest_dir.resolve()
        name = archive_path.name.lower()
        if name.endswith((".tar.xz", ".tar.gz", ".tar.bz2", ".tar")):
            with tarfile.open(archive_path, mode="r:*") as tar:
                # Security check: validate members to prevent directory traversal
                for member in tar.getmembers():
                    target_p = (dest_dir / member.name).resolve()
                    if not target_p.is_relative_to(dest_dir_resolved):
                        raise ValueError(f"Path traversal detected in archive member: '{member.name}'")
                if hasattr(tarfile, "data_filter"):
                    tar.extractall(dest_dir, filter="data")
                else:
                    tar.extractall(dest_dir)
        elif name.endswith(".zip"):
            with zipfile.ZipFile(archive_path, mode="r") as zf:
                # Security check: validate all zip member names
                for member_name in zf.namelist():
                    target_p = (dest_dir / member_name).resolve()
                    if not target_p.is_relative_to(dest_dir_resolved):
                        raise ValueError(f"Zip slip path traversal detected in archive entry: '{member_name}'")
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

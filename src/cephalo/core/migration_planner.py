"""
Migration Planner: scan and assemble files, directories, and harnesses for migration archives.
"""

import logging
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from cephalo.config import DATA_DIR, PROFILE_FILE, ROOT_DIR
from cephalo.core.migration_manifest import (
    CompressionFormat,
    FileEntry,
    HarnessDetector,
    MigrationManifest,
    MigrationScope,
    compute_sha256,
    should_exclude,
)

logger = logging.getLogger("cephalo.core.migration_planner")


class MigrationPlanner:
    """Plans file trees, harnesses, and databases to include in migration packages."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = (base_dir or ROOT_DIR).resolve()
        self.data_dir = self.base_dir / "data"

    def _plan_file(
        self,
        src: Path,
        archive_path: str,
        category: str,
        planned_items: List[Tuple[Path, str, str]],
    ) -> None:
        """Registers a single file to be archived directly without copying."""
        if src.exists() and src.is_file():
            planned_items.append((src, archive_path.replace("\\", "/"), category))

    def _plan_tree(
        self,
        src_dir: Path,
        archive_prefix: str,
        category: str,
        planned_items: List[Tuple[Path, str, str]],
        include_build_artifacts: bool = False,
    ) -> None:
        """Recursively plans a directory tree with intelligent lossless filtering."""
        if not src_dir.exists():
            return
        for root, dirs, files in os.walk(src_dir):
            root_p = Path(root)
            try:
                rel = root_p.relative_to(src_dir)
            except ValueError:
                continue

            # In-place directory exclusion
            dirs[:] = [d for d in dirs if not should_exclude(str(rel / d), include_build_artifacts)]

            for f in files:
                rel_file = str(rel / f) if str(rel) != "." else f
                if not should_exclude(rel_file, include_build_artifacts):
                    src_f = root_p / f
                    arc_f = f"{archive_prefix}/{rel_file}".replace("\\", "/")
                    planned_items.append((src_f, arc_f, category))

    def _plan_skills_settings_only(
        self,
        skills_dir: Path,
        archive_prefix: str,
        planned_items: List[Tuple[Path, str, str]],
    ) -> None:
        """In settings mode, captures SKILL.md and configuration files without gigabytes of subtrees."""
        if not skills_dir.exists():
            return
        for root, dirs, files in os.walk(skills_dir):
            root_p = Path(root)
            try:
                rel_root = root_p.relative_to(skills_dir)
            except ValueError:
                continue
            dirs[:] = [d for d in dirs if not should_exclude(str(rel_root / d))]
            for f in files:
                if f.upper() in ("SKILL.MD", "PROMPT.MD", "RULES.MD", "PACKAGE.JSON", "README.MD") or f.endswith((".json", ".yaml", ".yml")):
                    src_f = root_p / f
                    rel_f = str(rel_root / f) if str(rel_root) != "." else f
                    arc_f = f"{archive_prefix}/{rel_f}".replace("\\", "/")
                    planned_items.append((src_f, arc_f, "harness_skill_def"))

    def _safe_sqlite_backup(self, src_db: Path, dest_db: Path) -> None:
        """Creates a consistent, compacted SQLite snapshot using the online backup API."""
        dest_db.parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(src_db) as src_conn:
                with sqlite3.connect(dest_db) as dest_conn:
                    src_conn.backup(dest_conn)
        except Exception as e:
            logger.warning(f"SQLite backup API failed for {src_db} ({e}), falling back to copy.")
            shutil.copy2(src_db, dest_db)

    def _plan_cephalo_core(
        self,
        planned_items: List[Tuple[Path, str, str]],
        scope: MigrationScope,
        include_build_artifacts: bool,
        include_secrets: bool,
        temp_dir: Path,
    ) -> None:
        """Plans Cephalo's configuration, rules, specialties, patterns, and optionally data."""
        # A. USER_PROFILE.md & Templates
        for pf_name in ("USER_PROFILE.md", "USER_PROFILE.template.md"):
            pf = self.base_dir / pf_name
            self._plan_file(pf, f"cephalo/{pf_name}", "cephalo_profile", planned_items)

        # B. Safeguards
        sf = self.data_dir / "safeguards.json"
        self._plan_file(sf, "cephalo/safeguards.json", "cephalo_safeguards", planned_items)

        # C. Environment (.env) if exists and explicitly authorized
        if include_secrets:
            env_file = self.base_dir / ".env"
            self._plan_file(env_file, "cephalo/.env", "cephalo_env", planned_items)

        # D. Specialties, Patterns, Integrations
        for d_name, cat in [("specialties", "cephalo_specialty"), ("patterns", "cephalo_pattern"), ("integrations", "cephalo_integration")]:
            d = self.base_dir / d_name
            self._plan_tree(d, f"cephalo/{d_name}", cat, planned_items, include_build_artifacts=include_build_artifacts)

        # E. Data (LanceDB, Prompts, SQLite DBs) - Included if scope == ALL
        if scope == MigrationScope.ALL and self.data_dir.exists():
            prompts_file = self.data_dir / "prompts.jsonl"
            self._plan_file(prompts_file, "cephalo/data/prompts.jsonl", "cephalo_prompts", planned_items)

            lancedb_dir = self.data_dir / "lancedb"
            self._plan_tree(lancedb_dir, "cephalo/data/lancedb", "cephalo_lancedb", planned_items, include_build_artifacts=include_build_artifacts)

            for state_name in ("continuous_learning_state.json", "daily_digest_state.json", "harvest_state.json", "cephalo_daemon_status.json"):
                sf_path = self.data_dir / state_name
                self._plan_file(sf_path, f"cephalo/data/{state_name}", "cephalo_state", planned_items)

            for db_name in ("search_cache.db", "agent_tasks.db"):
                db_path = self.data_dir / db_name
                if db_path.exists():
                    dest_db = temp_dir / db_name
                    self._safe_sqlite_backup(db_path, dest_db)
                    planned_items.append((dest_db, f"cephalo/data/{db_name}", "cephalo_sqlite_db"))

            for extra_d, cat in [("frames", "cephalo_frames"), ("serp_cache", "cephalo_serp")]:
                d = self.data_dir / extra_d
                self._plan_tree(d, f"cephalo/data/{extra_d}", cat, planned_items, include_build_artifacts=include_build_artifacts)

    def _plan_harnesses(
        self,
        planned_items: List[Tuple[Path, str, str]],
        scope: MigrationScope,
        include_build_artifacts: bool,
    ) -> Dict[str, Any]:
        """Plans configuration files for all detected agent harnesses."""
        harnesses = HarnessDetector.detect_all()

        for name, data in harnesses.items():
            prefix = f"harnesses/{name}"
            if name == "antigravity":
                cfg_prefix = f"{prefix}/config"
                for key in ("config_file", "hooks_file", "mcp_file"):
                    p = data.get(key)
                    if p and Path(p).exists():
                        self._plan_file(Path(p), f"{cfg_prefix}/{Path(p).name}", "harness_config", planned_items)

                for dir_key in ("rules_dir", "plugins_dir", "projects_dir", "sidecars_dir"):
                    p = data.get(dir_key)
                    if p and Path(p).exists():
                        self._plan_tree(Path(p), f"{cfg_prefix}/{Path(p).name}", "harness_config", planned_items, include_build_artifacts=include_build_artifacts)

                for md_key in ("agents_md", "gemini_md"):
                    p = data.get(md_key)
                    if p and Path(p).exists():
                        self._plan_file(Path(p), f"{prefix}/{Path(p).name}", "harness_rules", planned_items)

                skills_dir = data.get("skills_dir")
                if skills_dir and Path(skills_dir).exists():
                    if scope == MigrationScope.ALL:
                        self._plan_tree(Path(skills_dir), f"{cfg_prefix}/skills", "harness_skills", planned_items, include_build_artifacts=include_build_artifacts)
                    else:
                        self._plan_skills_settings_only(Path(skills_dir), f"{cfg_prefix}/skills", planned_items)

                if scope == MigrationScope.ALL:
                    brain_dir = data.get("brain_dir")
                    if brain_dir and Path(brain_dir).exists():
                        self._plan_tree(Path(brain_dir), f"{prefix}/brain", "harness_brain", planned_items, include_build_artifacts=include_build_artifacts)

            elif name == "claude_code":
                for k in ("claude_md", "config_file", "settings_file"):
                    p = data.get(k)
                    if p and Path(p).exists():
                        self._plan_file(Path(p), f"{prefix}/{Path(p).name}", "harness_config", planned_items)

            elif name == "cursor":
                for k in ("cursor_mcp", "home_cursorrules"):
                    p = data.get(k)
                    if p and Path(p).exists():
                        self._plan_file(Path(p), f"{prefix}/{Path(p).name}", "harness_config", planned_items)
                cursor_user = data.get("cursor_user")
                if cursor_user and Path(cursor_user).exists():
                    for user_f in ("settings.json", "keybindings.json"):
                        uf_p = Path(cursor_user) / user_f
                        self._plan_file(uf_p, f"{prefix}/{user_f}", "harness_config", planned_items)

            elif name == "windsurf":
                for k in ("mcp_file", "rules_file"):
                    p = data.get(k)
                    if p and Path(p).exists():
                        self._plan_file(Path(p), f"{prefix}/{Path(p).name}", "harness_config", planned_items)

            elif name == "aider":
                for p in data.get("files", []):
                    if Path(p).exists():
                        self._plan_file(Path(p), f"{prefix}/{Path(p).name}", "harness_config", planned_items)

            elif name == "copilot":
                copilot_inst = data.get("instructions_file")
                if copilot_inst and Path(copilot_inst).exists():
                    self._plan_file(Path(copilot_inst), f"{prefix}/{Path(copilot_inst).name}", "harness_config", planned_items)

        return harnesses

    def _plan_projects(
        self,
        planned_items: List[Tuple[Path, str, str]],
        include_build_artifacts: bool,
    ) -> List[str]:
        """Plans all scratch workspace projects and standalone files."""
        home = HarnessDetector.get_home_dir()
        scratch_dir = home / ".gemini" / "antigravity" / "scratch"
        if not scratch_dir.exists():
            return []

        detected_projects: List[str] = []
        for item in scratch_dir.iterdir():
            if item.is_dir() and item.name.lower() in ("second-brain", "second_brain"):
                continue

            if item.is_dir():
                if item.name.lower() == "projects":
                    # Scan inside scratch/projects/ for individual named projects (e.g. 02-getmynews)
                    for sub in item.iterdir():
                        if sub.is_dir():
                            detected_projects.append(sub.name)
                            self._plan_tree(
                                sub,
                                f"projects/projects/{sub.name}",
                                f"workspace_project:{sub.name}",
                                planned_items,
                                include_build_artifacts=include_build_artifacts,
                            )
                        elif sub.is_file():
                            if not should_exclude(sub.name, include_build_artifacts):
                                self._plan_file(sub, f"projects/projects/{sub.name}", "workspace_file", planned_items)
                else:
                    detected_projects.append(item.name)
                    self._plan_tree(
                        item,
                        f"projects/{item.name}",
                        f"workspace_project:{item.name}",
                        planned_items,
                        include_build_artifacts=include_build_artifacts,
                    )
            elif item.is_file():
                if not should_exclude(item.name, include_build_artifacts):
                    self._plan_file(item, f"projects/{item.name}", "workspace_file", planned_items)

        return sorted(detected_projects)

    def _hash_planned_items(
        self,
        planned_items: List[Tuple[Path, str, str]],
    ) -> Tuple[List[FileEntry], List[Tuple[Path, str, str]]]:
        """Hashes all planned files in parallel using multi-threaded I/O."""
        def _hash_one(item: Tuple[Path, str, str]) -> Optional[Tuple[FileEntry, Tuple[Path, str, str]]]:
            src, arc, cat = item
            try:
                if not src.exists() or not src.is_file():
                    return None
                st = src.stat()
                sha = compute_sha256(src)
                entry = FileEntry(
                    archive_path=arc,
                    source_path=str(src),
                    category=cat,
                    size=st.st_size,
                    sha256=sha,
                    modified_at=datetime.datetime.fromtimestamp(st.st_mtime, tz=datetime.timezone.utc).isoformat(),
                )
                return entry, item
            except (PermissionError, OSError) as e:
                logger.warning(f"Skipping inaccessible file {src}: {e}")
                return None

        workers = min(16, (os.cpu_count() or 4) * 2)
        file_entries: List[FileEntry] = []
        valid_items: List[Tuple[Path, str, str]] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            results = executor.map(_hash_one, planned_items)
            for res in results:
                if res is not None:
                    entry, item = res
                    file_entries.append(entry)
                    valid_items.append(item)

        return file_entries, valid_items


#!/usr/bin/env python3
"""
Specialties Manager for Personal Second Brain
==============================================
Manages the domain expertise layer in the Second Brain hierarchy:
    Project -> Specialties (1-to-many) -> User Preferences (inherited constraints)

Features:
- On-demand CRUD: Create, Read, Edit, Delete.
- Mandatory User Confirmation on Deletion (safe-by-default).
- Verified Knowledge & GitHub Repositories curation.
- Automatic integration with LanceDB (indexed for hybrid search).
- Human-readable Markdown and machine-readable JSON storage.
"""

from __future__ import annotations

import datetime
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
SPECIALTIES_DIR = BASE_DIR / "specialties"
SPECIALTIES_DIR.mkdir(parents=True, exist_ok=True)


def slugify(text: str) -> str:
    """Converts a string into a clean filesystem slug."""
    text = text.lower().strip()
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'[^a-z0-9\-]', '', text)
    return text or "default"


class SpecialtiesManager:
    """Orchestrates CRUD operations, LanceDB syncing, and user preferences mapping."""

    def __init__(self, root_dir: Path = SPECIALTIES_DIR):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _find_specialty_dir(self, name: str, project: Optional[str] = None) -> Optional[Path]:
        """Locates the directory of a specialty by name and optional project."""
        name_slug = slugify(name)
        if project:
            proj_slug = slugify(project)
            candidate = self.root_dir / proj_slug / name_slug
            if candidate.exists() and candidate.is_dir():
                return candidate
            return None

        # Search across all project folders
        for proj_dir in self.root_dir.iterdir():
            if proj_dir.is_dir():
                candidate = proj_dir / name_slug
                if candidate.exists() and candidate.is_dir():
                    return candidate
        return None

    def list_specialties(self, project: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists all existing specialties, optionally filtered by project."""
        results = []
        if not self.root_dir.exists():
            return results

        proj_dirs = [self.root_dir / slugify(project)] if project else [p for p in self.root_dir.iterdir() if p.is_dir()]

        for p_dir in proj_dirs:
            if not p_dir.exists() or not p_dir.is_dir():
                continue
            for s_dir in p_dir.iterdir():
                if not s_dir.is_dir():
                    continue
                manifest_file = s_dir / "manifest.json"
                if manifest_file.exists():
                    try:
                        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                        results.append(manifest)
                    except Exception:
                        pass
        return results

    def get_specialty(self, name: str, project: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves a specialty by name and returns its manifest and KNOWLEDGE.md content."""
        s_dir = self._find_specialty_dir(name, project)
        if not s_dir:
            return None

        manifest_file = s_dir / "manifest.json"
        knowledge_file = s_dir / "KNOWLEDGE.md"

        manifest = {}
        if manifest_file.exists():
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        knowledge_content = ""
        if knowledge_file.exists():
            knowledge_content = knowledge_file.read_text(encoding="utf-8")

        return {
            "manifest": manifest,
            "knowledge_content": knowledge_content,
            "path": str(s_dir),
        }

    def create_specialty(
        self,
        name: str,
        project: str,
        fundamentals: str,
        github_repos: Optional[List[Dict[str, Any]]] = None,
        key_takeaways: Optional[List[str]] = None,
        user_preferences: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        sync_to_vector_db: bool = True,
    ) -> Dict[str, Any]:
        """Creates a new specialty under a project, persists files, and indexes in LanceDB."""
        from embedding_pipeline import Sanitizer
        sanitizer = Sanitizer()

        proj_slug = slugify(project)
        name_slug = slugify(name)
        s_dir = self.root_dir / proj_slug / name_slug
        s_dir.mkdir(parents=True, exist_ok=True)

        github_repos = github_repos or []
        key_takeaways = key_takeaways or []
        user_preferences = user_preferences or []
        tags = tags or [proj_slug, name_slug]

        # Sanitize text
        clean_fundamentals = sanitizer.sanitize(fundamentals.strip())
        clean_takeaways = [sanitizer.sanitize(t) for t in key_takeaways]

        now = datetime.datetime.now().astimezone().isoformat()
        manifest = {
            "id": f"specialty-{proj_slug}-{name_slug}",
            "name": name,
            "slug": name_slug,
            "project": project,
            "project_slug": proj_slug,
            "created_at": now,
            "updated_at": now,
            "tags": tags,
            "github_repos": github_repos,
            "key_takeaways": clean_takeaways,
            "user_preferences_binding": user_preferences,
        }

        # Write manifest.json
        manifest_path = s_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        # Generate KNOWLEDGE.md
        knowledge_lines = [
            f"# Specialty: {name}",
            f"> **Project:** `{project}` | **Created:** `{now[:10]}`",
            "",
            "## 1. Core Fundamentals & Verified Knowledge",
            clean_fundamentals,
            "",
        ]

        if clean_takeaways:
            knowledge_lines.append("## 2. Key Takeaways & Best Practices")
            for t in clean_takeaways:
                knowledge_lines.append(f"- {t}")
            knowledge_lines.append("")

        if github_repos:
            knowledge_lines.append("## 3. Curated GitHub Projects & Architectures")
            for repo in github_repos:
                r_name = repo.get("name", "Unknown Repo")
                r_url = repo.get("url", "#")
                r_stars = repo.get("stars", "N/A")
                r_desc = repo.get("description", "")
                knowledge_lines.append(f"- **[{r_name}]({r_url})** (⭐ {r_stars}): {r_desc}")
            knowledge_lines.append("")

        if user_preferences:
            knowledge_lines.append("## 4. Bound User Preferences & Constraints")
            for pref in user_preferences:
                knowledge_lines.append(f"- {pref}")
            knowledge_lines.append("")

        knowledge_content = "\n".join(knowledge_lines)
        knowledge_path = s_dir / "KNOWLEDGE.md"
        knowledge_path.write_text(knowledge_content, encoding="utf-8")

        # Index into LanceDB
        if sync_to_vector_db:
            try:
                from brain import get_pipeline
                pipeline = get_pipeline()
                category = f"specialty:{proj_slug}:{name_slug}"
                pipeline.ingest_prompt(
                    raw_text=f"Specialty '{name}' in project '{project}': {clean_fundamentals}",
                    prompt_id=manifest["id"],
                    source="specialty_module",
                    category=category,
                    intent=f"Verified knowledge for {name} ({project})",
                    traits=user_preferences,
                    sync_to_jsonl=False,  # Specialty knowledge is managed in specialty folder
                )
            except Exception as err:
                sys.stderr.write(f"[WARNING] Could not index specialty into LanceDB: {err}\n")

        return {
            "manifest": manifest,
            "path": str(s_dir),
            "knowledge_path": str(knowledge_path),
        }

    def edit_specialty(
        self,
        name: str,
        project: Optional[str] = None,
        fundamentals: Optional[str] = None,
        notes: Optional[str] = None,
        user_preferences: Optional[List[str]] = None,
        github_repos: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Edits an existing specialty, updates files, and re-indexes."""
        s_dir = self._find_specialty_dir(name, project)
        if not s_dir:
            raise FileNotFoundError(f"Specialty '{name}' not found under project '{project or '*'}'")

        manifest_file = s_dir / "manifest.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

        from embedding_pipeline import Sanitizer
        sanitizer = Sanitizer()

        now = datetime.datetime.now().astimezone().isoformat()
        manifest["updated_at"] = now

        if github_repos is not None:
            manifest["github_repos"] = github_repos
        if user_preferences is not None:
            manifest["user_preferences_binding"] = user_preferences

        manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        knowledge_file = s_dir / "KNOWLEDGE.md"
        if fundamentals or notes:
            content = knowledge_file.read_text(encoding="utf-8") if knowledge_file.exists() else ""
            if fundamentals:
                clean_fund = sanitizer.sanitize(fundamentals.strip())
                # Replace fundamentals section if possible, otherwise append
                if "## 1. Core Fundamentals & Verified Knowledge" in content:
                    parts = content.split("## 1. Core Fundamentals & Verified Knowledge")
                    next_sec = parts[1].split("\n## ", 1)
                    after = f"\n## {next_sec[1]}" if len(next_sec) > 1 else ""
                    content = f"{parts[0]}## 1. Core Fundamentals & Verified Knowledge\n{clean_fund}\n{after}"
                else:
                    content += f"\n\n## 1. Core Fundamentals & Verified Knowledge\n{clean_fund}\n"

            if notes:
                clean_notes = sanitizer.sanitize(notes.strip())
                content += f"\n\n### Update ({now[:10]})\n{clean_notes}\n"

            knowledge_file.write_text(content, encoding="utf-8")

        return {"manifest": manifest, "path": str(s_dir)}

    def delete_specialty(
        self,
        name: str,
        project: Optional[str] = None,
        confirmed: bool = False,
    ) -> bool:
        """Deletes a specialty directory. MUST BE EXPLICITLY CONFIRMED BY USER."""
        s_dir = self._find_specialty_dir(name, project)
        if not s_dir:
            raise FileNotFoundError(f"Specialty '{name}' not found.")

        manifest_file = s_dir / "manifest.json"
        sp_name = name
        proj_name = project or "unknown"
        if manifest_file.exists():
            try:
                m = json.loads(manifest_file.read_text(encoding="utf-8"))
                sp_name = m.get("name", name)
                proj_name = m.get("project", proj_name)
            except Exception:
                pass

        if not confirmed:
            raise PermissionError(
                f"SAFETY GUARD: Specialty '{sp_name}' under project '{proj_name}' cannot be deleted without user confirmation.\n"
                f"Pass --confirm flag or verify with the user before executing."
            )

        # Remove directory safely
        shutil.rmtree(s_dir)
        return True

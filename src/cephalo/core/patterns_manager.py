#!/usr/bin/env python3
"""
Cephalo - Cognitive Patterns Manager (patterns_manager.py)
=========================================================
Manages modular, version-controlled execution prompts ("Reflexes") inspired by
Daniel Miessler's Fabric framework, integrated directly with Cephalo's local
memory and user constraints.

Two-tier architecture:
- Core Patterns: version-controlled under `patterns/`
- Custom Patterns: locally isolated under `data/patterns/` (ignored by git)
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[3]
BASE_DIR = ROOT_DIR
CORE_PATTERNS_DIR = ROOT_DIR / "patterns"
DATA_DIR = ROOT_DIR / "data"
CUSTOM_PATTERNS_DIR = DATA_DIR / "patterns"

logger = logging.getLogger("cephalo.patterns")


class PatternsManager:
    """Manages discovery, inspection, and execution prompt assembly for Cephalo patterns."""

    def __init__(self, core_dir: Optional[Path] = None, custom_dir: Optional[Path] = None):
        self.core_dir = core_dir or CORE_PATTERNS_DIR
        self.custom_dir = custom_dir or CUSTOM_PATTERNS_DIR
        self.core_dir.mkdir(parents=True, exist_ok=True)
        self.custom_dir.mkdir(parents=True, exist_ok=True)

    def list_patterns(self) -> List[Dict[str, str]]:
        """Returns a list of all available core and custom patterns."""
        patterns = []
        seen = set()

        # 1. Core patterns
        for path in sorted(self.core_dir.glob("*.md")):
            name = path.stem
            seen.add(name)
            desc = self._extract_summary(path)
            patterns.append({
                "name": name,
                "tier": "core",
                "path": str(path),
                "summary": desc,
            })

        # 2. Custom patterns
        for path in sorted(self.custom_dir.glob("*.md")):
            name = path.stem
            if name in seen:
                continue
            desc = self._extract_summary(path)
            patterns.append({
                "name": name,
                "tier": "custom",
                "path": str(path),
                "summary": desc,
            })

        return patterns

    def get_pattern(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieves pattern metadata and full prompt content by name."""
        clean_name = name.strip().lower()
        if not clean_name.endswith(".md"):
            clean_name += ".md"

        # Check custom first (allows overriding core if desired)
        custom_path = self.custom_dir / clean_name
        if custom_path.exists():
            return {
                "name": custom_path.stem,
                "tier": "custom",
                "path": str(custom_path),
                "content": custom_path.read_text(encoding="utf-8"),
                "summary": self._extract_summary(custom_path),
            }

        core_path = self.core_dir / clean_name
        if core_path.exists():
            return {
                "name": core_path.stem,
                "tier": "core",
                "path": str(core_path),
                "content": core_path.read_text(encoding="utf-8"),
                "summary": self._extract_summary(core_path),
            }

        return None

    def assemble_prompt(
        self,
        pattern_name: str,
        input_text: str,
        context_text: Optional[str] = None,
    ) -> str:
        """
        Combines pattern system instructions, injected user context, and user input
        into a complete, ready-to-run prompt payload.
        """
        pattern = self.get_pattern(pattern_name)
        if not pattern:
            raise ValueError(f"Pattern '{pattern_name}' not found.")

        parts = [pattern["content"].strip()]

        if context_text and context_text.strip():
            parts.append("\n\n---\n\n# INJECTED CEPHALO CONTEXT\n\n" + context_text.strip())

        parts.append("\n\n---\n\n# INPUT\n\n" + input_text.strip())

        return "".join(parts)

    def save_custom_pattern(self, name: str, content: str) -> Path:
        """Saves a new custom pattern to the local-only custom directory."""
        slug = re.sub(r"[^a-z0-9_-]+", "_", name.lower().strip()).strip("_")
        target_path = self.custom_dir / f"{slug}.md"
        target_path.write_text(content.strip(), encoding="utf-8")
        return target_path

    def _extract_summary(self, path: Path) -> str:
        """Extracts the first paragraph or identity summary from a pattern markdown file."""
        try:
            content = path.read_text(encoding="utf-8")
            match = re.search(r"#\s*IDENTITY\s*(?:and|&)?\s*PURPOSE\s*\n+([^#\n][^\n]+)", content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            # Fallback to first non-empty line
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    return line[:120]
        except Exception:
            pass
        return "Cognitive execution pattern"

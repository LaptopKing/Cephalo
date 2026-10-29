#!/usr/bin/env python3
"""
Cephalo - Dynamic Context Assembler (context_manager.py)
========================================================
Assembles and exports tailored, consolidated system context blocks from
Cephalo's USER_PROFILE.md, hardware specifications, and domain Specialties.

Inspired by Fabric's `--context` flag, but grounded in Cephalo's sovereign
personal memory engine.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
BASE_DIR = ROOT_DIR
PROFILE_FILE = ROOT_DIR / "USER_PROFILE.md"

logger = logging.getLogger("cephalo.context")


class ContextManager:
    """Consolidates personal identity, hardware profiles, and domain specialties into ready-to-use context payloads."""

    def __init__(self, profile_path: Optional[Path] = None):
        self.profile_path = profile_path or PROFILE_FILE

    def export_context(
        self,
        project: Optional[str] = None,
        specialty: Optional[str] = None,
        include_hardware: bool = True,
        include_cinema: bool = False,
    ) -> str:
        """Builds a structured markdown context block."""
        sections = []

        # 1. Base Identity & Craftsmanship Rules
        sections.append("## Cephalo User Guidelines & Core Standards\n"
                        "- **Language Invariant:** Respond and author code/documentation in English ALWAYS.\n"
                        "- **Tone:** Direct, technical, pragmatic, structured markdown, zero fluff.\n"
                        "- **Anti-Slop Discipline:** Linux kernel conventions (Linus Torvalds: screen fit, max 3 indents, early returns, minimal indirection, zero swallowed errors).\n"
                        "- **Type & Boundaries:** Strict typing, no 'any', validate runtime boundaries via Zod or Pydantic.\n"
                        "- **The Rule of Three:** Concrete code first; abstract only when 3 distinct call sites share identical invariants.\n"
                        "- **Pre-Recommendation Invariant:** Validate ground truth before recommending. Zero theoretical extrapolation.")

        # 2. Hardware Profiles if requested
        if include_hardware:
            sections.append("## Verified Hardware Profile\n"
                            "- **Living Room Display:** TCL 65T8B (65\" 4K QLED Google TV).\n"
                            "- **Workstation:** Windows 10 IoT Enterprise LTSC, 16 GB RAM, NVIDIA GeForce GTX 1050 Ti (4GB VRAM).\n"
                            "- **Silent Execution Invariant:** All Windows subprocesses and background tasks must enforce CREATE_NO_WINDOW (0x08000000).")

        # 3. Cinema & Aesthetic preferences if requested
        if include_cinema:
            sections.append("## Cinema & Visual Aesthetic\n"
                            "- **Display Target:** TCL 65T8B 4K QLED Google TV.\n"
                            "- **Aesthetic:** Eye-popping, vibrant, high-saturation color grading (neon nightscapes, turquoise Mediterranean sun, high contrast 4K). Anti-grey / anti-drab.\n"
                            "- **Pacing:** Instant narrative velocity from minute 1 (cold-open action, rapid tempo). Anti-slowburn.")

        # 4. Domain Specialty if requested
        if specialty:
            try:
                from specialties_manager import SpecialtiesManager
                mgr = SpecialtiesManager()
                data = mgr.get_specialty(specialty, project=project)
                if data:
                    spec_lines = [f"## Domain Specialty: {data.get('name')} (Project: {data.get('project', 'global')})"]
                    if data.get("fundamentals"):
                        spec_lines.append(f"**Fundamentals:**\n{data['fundamentals']}")
                    if data.get("key_takeaways"):
                        spec_lines.append("**Key Takeaways & Invariants:**")
                        for t in data["key_takeaways"]:
                            spec_lines.append(f"- {t}")
                    if data.get("preferences"):
                        spec_lines.append(f"**Bound Preferences:** {', '.join(data['preferences'])}")
                    sections.append("\n".join(spec_lines))
            except Exception as e:
                logger.warning("Could not load specialty '%s': %s", specialty, e)

        return "\n\n".join(sections)

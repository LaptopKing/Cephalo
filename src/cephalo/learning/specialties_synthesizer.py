#!/usr/bin/env python3
"""
Cephalo Autonomous Specialty Synthesizer & Knowledge Engine
============================================================
Provides automated knowledge synthesis and specialty generation for:
1. Curated foundational technologies, frameworks, UI/UX, and methodologies.
2. Dynamic synthesis for ANY novel or unknown technology/methodology.
3. Automated text discovery & extraction from prompts, docs, or project files.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


def slugify(text: str) -> str:
    """Converts a string into a clean filesystem slug."""
    text = text.lower().strip()
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'[^a-z0-9\-]', '', text)
    return text or "default"


# Curated, battle-tested knowledge bank for core engineering disciplines
from cephalo.learning.curated_specialties import (
    CURATED_SPECIALTIES,
    SPECIALTY_ALIASES,
)

class SpecialtySynthesizer:
    """Intelligently resolves, synthesizes, and generates domain specialties."""

    @staticmethod
    def resolve_slug(topic: str) -> str:
        """Resolves topic string or alias to a canonical specialty slug."""
        raw_slug = slugify(topic)
        # Check alias dictionary
        if raw_slug in SPECIALTY_ALIASES:
            return SPECIALTY_ALIASES[raw_slug]
        # Check direct match
        for key in CURATED_SPECIALTIES:
            if raw_slug == key or raw_slug.replace("-", "") == key.replace("-", ""):
                return key
        return raw_slug

    @classmethod
    def get_curated(cls, topic: str) -> Optional[Dict[str, Any]]:
        """Returns pre-compiled curated data for a topic if available."""
        slug = cls.resolve_slug(topic)
        return CURATED_SPECIALTIES.get(slug)

    @classmethod
    def synthesize(
        cls,
        topic: str,
        project: str = "global",
        custom_fundamentals: Optional[str] = None,
        custom_takeaways: Optional[List[str]] = None,
        custom_repos: Optional[List[Dict[str, Any]]] = None,
        user_preferences: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes a production-grade specialty:
        - If the topic is in the curated bank, utilizes the expert verified content.
        - If unknown, dynamically generates an architectural profile based on domain heuristics.
        """
        slug = cls.resolve_slug(topic)
        curated = CURATED_SPECIALTIES.get(slug)

        if curated:
            name = curated["name"]
            fundamentals = custom_fundamentals or curated["fundamentals"]
            takeaways = custom_takeaways or curated["key_takeaways"]
            repos = custom_repos or curated["github_repos"]
            prefs = user_preferences or curated["user_preferences"]
            tags = curated.get("tags", [slug, project])
        else:
            # Dynamic Autonomous Deep Research for Novel / Unknown Technology or Methodology
            try:
                from cephalo.research.research_engine import DeepResearchEngine
                engine = DeepResearchEngine()
                res = engine.synthesize_specialty(
                    topic=topic,
                    project=project,
                    custom_notes=custom_fundamentals,
                )
                name = res["name"]
                fundamentals = custom_fundamentals or res["fundamentals"]
                takeaways = custom_takeaways or res["key_takeaways"]
                repos = custom_repos or res["github_repos"]
                prefs = user_preferences or res["user_preferences"]
                tags = res["tags"]
            except Exception:
                # Graceful offline heuristic fallback
                clean_title = topic.replace("-", " ").replace("_", " ").title()
                name = f"{clean_title} Architecture & Engineering"
                tags = [slug, project, "autonomous-synthesis"]
                prefs = user_preferences or ["clean_code", "anti_slop", "robust_error_handling", "pragmatic_engineering"]

                fundamentals = custom_fundamentals or (
                    f"Autonomous domain engineering profile for '{clean_title}'. Emphasizes verified fundamentals, "
                    f"clear architectural separation of concerns, minimal indirection, and strict adherence to anti-slop "
                    f"engineering standards. Ensures explicit error paths, deterministic lifecycle management, and high "
                    f"cohesion across all implementations."
                )

                takeaways = custom_takeaways or [
                    f"Architecture boundary discipline: isolate '{clean_title}' operations behind clean, explicit interfaces.",
                    f"Explicit error handling: handle errors at call sites; never swallow exceptions or fail silently.",
                    f"Anti-slop simplicity: avoid premature abstractions and speculative generic wrappers; follow the Rule of Three.",
                    f"Resource cleanup & lifecycle: ensure all connections, timers, and worker handles are deterministically closed.",
                    f"Testing & verification: test critical boundary conditions, invalid payloads, and timeout recovery scenarios."
                ]

                repos = custom_repos or [
                    {
                        "name": f"awesome-{slug}",
                        "url": f"https://github.com/search?q={slug}+awesome",
                        "stars": "Curated",
                        "description": f"Curated list of libraries, architectures, and best practices for {clean_title}."
                    }
                ]

        return {
            "name": name,
            "slug": slug,
            "project": project,
            "fundamentals": fundamentals,
            "key_takeaways": takeaways,
            "github_repos": repos,
            "user_preferences": prefs,
            "tags": tags,
        }

    @classmethod
    def discover_technologies(cls, text: str) -> List[str]:
        """Extracts technology and methodology candidates from a text block."""
        detected = set()
        clean_text = text.lower()

        # Check all known keys and aliases
        for candidate, slug in SPECIALTY_ALIASES.items():
            pattern = r'\b' + re.escape(candidate) + r'\b'
            if re.search(pattern, clean_text):
                detected.add(slug)

        for key in CURATED_SPECIALTIES:
            pattern = r'\b' + re.escape(key.replace("-", " ")) + r'\b'
            if re.search(pattern, clean_text):
                detected.add(key)
            pattern_dash = r'\b' + re.escape(key) + r'\b'
            if re.search(pattern_dash, clean_text):
                detected.add(key)

        return sorted(list(detected))

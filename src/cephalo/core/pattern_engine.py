"""
Cephalo Developer Pattern & Entity Correlation Engine (pattern_engine.py)
========================================================================
Inspired by Situation Monitor (hipcityreg/situation-monitor).

Adapts Situation Monitor's deterministic linguistic algorithms for software developers:
1. "Developer Main Character": Identifies which technology, repository, module, or bug
   is dominating the developer's attention today.
2. Focus Dominance Metric:
   Calculates ratio: Dominance = min(100, round(((top_count / second_count) - 1) * 100))
   Reveals whether developer was in deep single-problem flow (100% dominance)
   or fractured context-switching (low dominance).
3. Cross-Stream Correlation: Correlates user prompts with screen OCR text and code symbols.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Optional


class DeveloperPatternEngine:
    """Calculates focus dominance and cross-stream attention patterns."""

    def __init__(self, tracked_symbols: Optional[List[str]] = None):
        self.tracked_symbols = tracked_symbols or [
            "cephalo", "LanceDB", "FastEmbed", "ONNX", "Indra", "OXR",
            "OpenSandbox", "ThinkRail", "Orkas", "SituationMonitor",
            "car-livery-creator", "movie_discovery", "ascii-reveal",
            "TCL 65T8B", "QLED", "Docker", "Python", "TypeScript",
            "Playwright", "Tree-sitter", "SQLite", "Subaru GF8",
        ]

    def calculate_developer_main_character(self, text_items: List[str]) -> Dict[str, Any]:
        """
        Calculates today's primary focus entity and dominance ratio.
        """
        counts: Counter[str] = Counter()
        for text in text_items:
            for symbol in self.tracked_symbols:
                pattern = rf"\b{re.escape(symbol)}\b"
                matches = len(re.findall(pattern, text, flags=re.IGNORECASE))
                if matches:
                    counts[symbol] += matches

        ranked = counts.most_common()
        if not ranked:
            return {
                "main_character": "General Engineering",
                "top_mentions": 0,
                "dominance_score": 0,
                "focus_state": "distributed",
                "rankings": [],
            }

        top_name, top_count = ranked[0]
        second_count = ranked[1][1] if len(ranked) > 1 else 0

        # Dominance formula adapted from Situation Monitor
        if second_count == 0:
            dominance = 100
        else:
            ratio = top_count / second_count
            dominance = min(100, round((ratio - 1.0) * 100))

        focus_state = "deep_flow" if dominance >= 50 else ("dual_focus" if dominance >= 20 else "fragmented")

        return {
            "main_character": top_name,
            "top_mentions": top_count,
            "second_character": ranked[1][0] if len(ranked) > 1 else None,
            "second_mentions": second_count,
            "dominance_score": dominance,
            "focus_state": focus_state,
            "rankings": [{"name": k, "count": v} for k, v in ranked[:7]],
        }

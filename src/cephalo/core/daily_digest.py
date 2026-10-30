"""
Cephalo Anti-AI-Slop Daily Digest Generator (daily_digest.py)
=============================================================
Synthesizes daily developer milestones, prompt logs, screen keyframes,
and code changes into a high-density, visual executive dashboard.

Non-Negotiable Invariants:
- STRICTLY ANTI-AI-SLOP: No generic conversational filler, no boilerplate fluff.
- VISUAL FIRST: Structured tables, hourly velocity charts (ASCII terminal & Mermaid),
  and clickable artifact links.
"""

from __future__ import annotations

import datetime
import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from cephalo.config import DATA_DIR, PROMPTS_FILE

logger = logging.getLogger("cephalo.digest")

FRAMES_INDEX_FILE = DATA_DIR / "frames" / "frame_index.jsonl"


class DailyDigestGenerator:
    """Aggregates memory logs, AST touches, and screen events into visual briefings."""

    def __init__(
        self,
        prompts_file: Optional[Path] = None,
        frames_file: Optional[Path] = None,
    ):
        self.prompts_file = prompts_file or PROMPTS_FILE
        self.frames_file = frames_file or FRAMES_INDEX_FILE

    def collect_day_data(self, date_str: str) -> Dict[str, Any]:
        """Collects all prompt logs, decisions, and screen frames for the given date (YYYY-MM-DD)."""
        prompt_events: List[Dict[str, Any]] = []
        screen_events: List[Dict[str, Any]] = []

        # 1. Parse prompts.jsonl
        if self.prompts_file.exists():
            with open(self.prompts_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        ts = record.get("timestamp", "")
                        if ts.startswith(date_str):
                            prompt_events.append(record)
                    except Exception:
                        continue

        # 2. Parse frame_index.jsonl
        if self.frames_file.exists():
            with open(self.frames_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        if rec.get("date") == date_str or rec.get("timestamp", "").startswith(date_str):
                            screen_events.append(rec)
                    except Exception:
                        continue

        return {
            "date": date_str,
            "prompts": prompt_events,
            "screens": screen_events,
        }

    def generate_digest(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """Processes collected logs into high-signal metrics and visual charts."""
        target_date = date_str or datetime.date.today().isoformat()
        data = self.collect_day_data(target_date)

        prompts = data["prompts"]
        screens = data["screens"]

        # Hourly Distribution
        hourly_counts: Dict[int, int] = defaultdict(int)
        hourly_breakdown: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        category_counts: Counter[str] = Counter()
        tag_counts: Counter[str] = Counter()
        process_counts: Counter[str] = Counter()

        key_decisions: List[Dict[str, str]] = []

        for p in prompts:
            ts = p.get("timestamp", "")
            cat = p.get("category", "general")
            category_counts[cat] += 1

            for tag in p.get("tags", []):
                tag_counts[tag] += 1

            try:
                dt = datetime.datetime.fromisoformat(ts)
                hour = dt.hour
                hourly_counts[hour] += 1
                hourly_breakdown[hour][cat] += 1
            except Exception:
                pass

            # Extract high-signal decision records
            text = p.get("text") or p.get("sanitized_text", "")
            if text and cat in ("architecture", "tech_stack", "hardware", "user_preference", "decision"):
                key_decisions.append({
                    "id": p.get("id", "prompt"),
                    "category": cat,
                    "summary": (text[:120] + "...") if len(text) > 120 else text,
                })

        for s in screens:
            ts = s.get("timestamp", "")
            proc = s.get("process_name", "")
            if proc:
                process_counts[proc] += 1

            try:
                dt = datetime.datetime.fromisoformat(ts)
                hour = dt.hour
                hourly_counts[hour] += 1
                hourly_breakdown[hour]["screen_capture"] += 1
            except Exception:
                pass

        total_events = len(prompts) + len(screens)
        active_hours = sorted(hourly_counts.keys())

        # Generate Visual Representations
        ascii_chart = self._render_ascii_chart(hourly_counts)
        mermaid_chart = self._render_mermaid_chart(hourly_counts)

        return {
            "date": target_date,
            "total_events": total_events,
            "prompts_count": len(prompts),
            "screen_frames_count": len(screens),
            "active_hours_count": len(active_hours),
            "hourly_counts": dict(hourly_counts),
            "category_distribution": dict(category_counts.most_common(8)),
            "top_tags": dict(tag_counts.most_common(10)),
            "active_processes": dict(process_counts.most_common(6)),
            "key_decisions": key_decisions[:10],
            "ascii_chart": ascii_chart,
            "mermaid_chart": mermaid_chart,
        }

    def _render_ascii_chart(self, hourly_counts: Dict[int, int]) -> str:
        """Renders an ASCII distribution sparkline for terminal presentation."""
        if not hourly_counts:
            return "No activity logged for this date."

        max_val = max(hourly_counts.values()) if hourly_counts else 1
        lines = []
        bar_width = 16

        for hour in range(24):
            count = hourly_counts.get(hour, 0)
            if count == 0 and not any(hourly_counts.get(h, 0) > 0 for h in (hour - 1, hour + 1)):
                continue  # Skip large blocks of quiet night hours

            filled = int((count / max_val) * bar_width) if max_val > 0 else 0
            empty = bar_width - filled
            bar = "█" * filled + "░" * empty
            hour_str = f"{hour:02d}:00"
            lines.append(f"{hour_str} [{bar}] {count:2d} events")

        return "\n".join(lines)

    def _render_mermaid_chart(self, hourly_counts: Dict[int, int]) -> str:
        """Renders a Mermaid xychart-beta block for markdown rendering."""
        if not hourly_counts:
            return ""

        hours_present = [h for h in range(24) if hourly_counts.get(h, 0) > 0]
        if not hours_present:
            return ""

        min_h = min(hours_present)
        max_h = max(hours_present)
        target_hours = list(range(max(0, min_h - 1), min(24, max_h + 2)))

        labels = [f'"{h:02d}:00"' for h in target_hours]
        values = [str(hourly_counts.get(h, 0)) for h in target_hours]
        max_val = max([hourly_counts.get(h, 0) for h in target_hours] or [1])

        mermaid = [
            "```mermaid",
            "xychart-beta",
            f'    title "Hourly Cognitive Velocity ({len(target_hours)} Active Hours)"',
            f'    x-axis [{", ".join(labels)}]',
            f"    y-axis \"Events Logged\" 0 --> {max(max_val + 2, 5)}",
            f'    bar [{", ".join(values)}]',
            "```",
        ]
        return "\n".join(mermaid)

    def render_markdown(self, digest: Dict[str, Any]) -> str:
        """Produces a clean, visual, anti-AI-slop Markdown report."""
        date_str = digest["date"]
        total = digest["total_events"]
        prompts_cnt = digest["prompts_count"]
        screens_cnt = digest["screen_frames_count"]

        md = [
            f"# 🧠 Cephalo Daily Digest — {date_str}",
            "",
            "> **Executive Velocity Metric:** "
            f"`{total} Events` ({prompts_cnt} Prompt Milestones, {screens_cnt} Screen Keyframes) "
            f"across `{digest['active_hours_count']} Active Hours`.",
            "",
            "### 1. Cognitive Velocity & Activity Distribution",
            "",
        ]

        if digest["mermaid_chart"]:
            md.append(digest["mermaid_chart"])
            md.append("")
        else:
            md.append("```")
            md.append(digest["ascii_chart"])
            md.append("```")
            md.append("")

        # Category and Process Breakdown Tables
        md.extend([
            "### 2. Category & Focus Distribution",
            "",
            "| Focus Domain / Category | Events | Relative Velocity |",
            "| :--- | :---: | :--- |",
        ])

        for cat, cnt in digest["category_distribution"].items():
            pct = round((cnt / total) * 100, 1) if total > 0 else 0
            bar = "▓" * max(1, int(pct / 10))
            md.append(f"| `{cat}` | {cnt} | `{bar}` {pct}% |")

        if digest["active_processes"]:
            md.extend([
                "",
                "### 3. Active Workspace Tools",
                "",
                "| Application Process | Screen Keyframes | Workspace Share |",
                "| :--- | :---: | :--- |",
            ])
            for proc, cnt in digest["active_processes"].items():
                pct = round((cnt / screens_cnt) * 100, 1) if screens_cnt > 0 else 0
                md.append(f"| **{proc}** | {cnt} | {pct}% |")

        if digest["key_decisions"]:
            md.extend([
                "",
                "### 4. Verified Architectural Milestones & Decisions",
                "",
                "| ID | Category | Distilled Milestone / Decision |",
                "| :--- | :--- | :--- |",
            ])
            for kd in digest["key_decisions"]:
                md.append(f"| `{kd['id']}` | `{kd['category']}` | {kd['summary']} |")

        md.extend([
            "",
            "---",
            f"*Generated locally by Cephalo Sovereign Core on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}. Zero cloud telemetry.*",
        ])

        return "\n".join(md)


DIGEST_STATE_FILE = DATA_DIR / "daily_digest_state.json"


def check_and_offer_daily_digest(
    date_str: Optional[str] = None,
    state_file: Optional[Path] = None,
    mark_offered: bool = True,
) -> Optional[str]:
    """
    Checks if a daily digest is available and should be offered to the user.
    Respects user attention: offers at most ONCE per day in a respectful, concise 2-line format.
    """
    target_date = date_str or datetime.date.today().isoformat()
    sf = state_file or DIGEST_STATE_FILE

    # Check state
    state = {}
    if sf.exists():
        try:
            state = json.loads(sf.read_text(encoding="utf-8"))
        except Exception:
            state = {}

    if state.get("last_offered_date") == target_date:
        return None  # Already offered today

    generator = DailyDigestGenerator()
    digest = generator.generate_digest(target_date)

    total_events = digest.get("total_events", 0)
    if total_events < 2:
        return None  # Insufficient activity to warrant an offer

    # Update state
    if mark_offered:
        state["last_offered_date"] = target_date
        state["last_offered_at"] = datetime.datetime.now().isoformat()
        try:
            sf.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    prompts_cnt = digest.get("prompts_count", 0)
    screens_cnt = digest.get("screen_frames_count", 0)
    hours_cnt = digest.get("active_hours_count", 1)

    return (
        f"> 🌅 **Daily Digest Available:** `{total_events} events` "
        f"({prompts_cnt} milestones, {screens_cnt} screen frames) logged today across `{hours_cnt} active hours`.\n"
        f"> *Would you like to review today's visual cognitive velocity or open the DeepWiki 24h scrubber?*"
    )

"""
ThinkRail-inspired Context Compaction Defense for Cephalo.
Re-anchors essential user identity, verified hardware specifications,
critical ground-truth invariants, and active project specialties
when an agent session undergoes context window compaction.
"""

from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
PROFILE_FILE = ROOT_DIR / "USER_PROFILE.md"


class CompactionCarryover:
    """
    ThinkRail-inspired Context Compaction Defense for Cephalo.
    Re-anchors essential user identity, verified hardware specifications,
    critical ground-truth invariants, and active project specialties
    when an agent session undergoes context window compaction.
    """

    def __init__(self, profile_file: Path = PROFILE_FILE, root_dir: Path = ROOT_DIR):
        self.profile_file = profile_file
        self.root_dir = root_dir
        self.specialties_dir = root_dir / "specialties"

    def is_compacted_session(self, transcript_path: Path) -> bool:
        """Sniffs transcript for context compaction boundaries or truncation indicators."""
        if not transcript_path.exists():
            return False
        try:
            with open(transcript_path, "r", encoding="utf-8") as f:
                for line in f:
                    if '"compactionSummary"' in line or '"firstKeptEntryId"' in line or '"session_compacted"' in line:
                        return True
        except Exception:
            pass
        return False

    def build_carryover_payload(self, active_specialty: Optional[str] = None) -> str:
        """
        Builds a compact, high-density memory carryover anchor block.
        """
        lines = [
            "🧠 [Cephalo Ground-Truth Memory Carryover | Active Post-Compaction]",
            "<!-- Context compaction detected. Active constraints and core invariants re-anchored below. Follow strictly. -->",
            "- Cephalo-First Front Door (Step 0): Query Cephalo first (`cephalo search \"<query>\" --json` / `cephalo_search`) for ANY investigation, question, concept, or feature. NEVER use grep/rg as first choice.",
            "- Core Invariant: ALWAYS validate ground truth before recommending. Never extrapolate vendor shipping, pricing, or compatibility without verified facts.",
            "- Subagent-First & Governor Invariant: Deploy subagents by default for research/feature tasks. Checkpoint and restore via Cephalo (`cephalo_task_checkpoint`/`cephalo_task_resume`). When on battery, limit concurrency to 1 to protect power.",
            "- Privacy Invariant: Zero-leak privacy; all secrets scrubbed before LanceDB storage.",
        ]

        if self.profile_file.exists():
            try:
                prof_content = self.profile_file.read_text(encoding="utf-8")
                hw_display = None
                cinema_aesthetic = None
                for line in prof_content.splitlines():
                    l_lower = line.lower()
                    if line.startswith("- ") and ("tv" in l_lower or "display" in l_lower) and any(d in l_lower for d in ["tcl", "oled", "qled", "lg", "sony"]):
                        hw_display = line.strip().lstrip("- ").strip()
                    elif line.startswith("- ") and "visual aesthetic" in l_lower:
                        cinema_aesthetic = line.strip().lstrip("- ").strip()

                if hw_display:
                    lines.append(f"- Verified Hardware / Display: {hw_display}")
                else:
                    lines.append("- Verified Hardware / Display: TCL 65T8B (65\" 4K QLED Google TV).")

                if cinema_aesthetic:
                    lines.append(f"- Cinema Aesthetics: {cinema_aesthetic}")
                else:
                    lines.append("- Cinema Aesthetics: Eye-popping, vibrant, high-saturation 4K; instant velocity from minute 1; anti-grey/anti-slowburn.")

                for line in prof_content.splitlines():
                    if line.startswith("- ") and any(k in line.lower() for k in ["hungarian", "direct", "pragmatic", "no fluff"]):
                        lines.append(line)
            except Exception:
                lines.append("- Verified Hardware / Display: TCL 65T8B (65\" 4K QLED Google TV).")
                lines.append("- Cinema Aesthetics: Eye-popping, vibrant, high-saturation 4K; instant velocity from minute 1; anti-grey/anti-slowburn.")
        else:
            lines.append("- Verified Hardware / Display: TCL 65T8B (65\" 4K QLED Google TV).")
            lines.append("- Cinema Aesthetics: Eye-popping, vibrant, high-saturation 4K; instant velocity from minute 1; anti-grey/anti-slowburn.")

        if active_specialty and self.specialties_dir.exists():
            spec_file = self.specialties_dir / f"{active_specialty}.md"
            if spec_file.exists():
                try:
                    spec_content = spec_file.read_text(encoding="utf-8")
                    lines.append(f"\n[Active Project Specialty: {active_specialty}]\n" + spec_content[:800])
                except Exception:
                    pass

        return "\n".join(lines)

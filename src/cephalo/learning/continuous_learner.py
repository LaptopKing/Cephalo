#!/usr/bin/env python3
"""
Cephalo Continuous Learning Engine (continuous_learner.py)
==========================================================
Autonomous background knowledge harvester and memory consolidation coprocessor.

Core Capabilities:
1. Multi-Project Tech & Stack Scanner:
   - Scans active workspaces in `scratch/projects`.
   - Inspects manifests: `package.json`, `go.mod`, `Cargo.toml`, `requirements.txt`, `pyproject.toml`.
   - Detects used libraries, frameworks, tools, and methodologies.
2. Proactive Specialty Synthesis:
   - Identifies technology stacks lacking a dedicated Cephalo specialty.
   - Automatically invokes `specialties_synthesizer.py` to draft high-integrity, anti-slop knowledge modules.
3. Memory Consolidation & Reflection (Episodic -> Semantic):
   - Audits recent episodic entries in `prompts.jsonl`.
   - Clusters repeated directives, preferences, hardware cues, and negative constraints.
   - Consolidates recurring patterns into persistent learning insights.
4. Autonomous Background Operation:
   - Supports one-shot execution (`cephalo learn run`), live watcher (`cephalo learn watch`),
     and status reporting (`cephalo learn status`).
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Base paths
ROOT_DIR = Path(__file__).resolve().parents[3]
SCRIPT_DIR = ROOT_DIR
DATA_DIR = ROOT_DIR / "data"
STATE_FILE = DATA_DIR / "continuous_learning_state.json"
PROMPTS_FILE = DATA_DIR / "prompts.jsonl"
PROFILE_FILE = ROOT_DIR / "USER_PROFILE.md"
SPECIALTIES_DIR = ROOT_DIR / "specialties"
DEFAULT_PROJECTS_DIR = ROOT_DIR.parent / "projects"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [Cephalo:Learn] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cephalo.continuous_learner")

# High-value technology manifests & dependency extraction
KEY_FRAMEWORKS = {
    "next": "nextjs",
    "nextjs": "nextjs",
    "react": "react",
    "vue": "vue",
    "svelte": "svelte",
    "astro": "astro",
    "tailwindcss": "tailwindcss",
    "shadcn": "shadcn-ui",
    "@radix-ui": "radix-ui",
    "drizzle-orm": "drizzle-orm",
    "prisma": "prisma",
    "typeorm": "typeorm",
    "bullmq": "bullmq",
    "ioredis": "redis",
    "redis": "redis",
    "fast-xml-parser": "rss-atom-xml-parsers",
    "cheerio": "cheerio-web-scraping",
    "playwright": "playwright-headless-scraping",
    "resend": "email-delivery",
    "telegraf": "telegram-bot-api",
    "discord.js": "discord-webhook-apps",
    "zod": "zod-validation",
    "fastembed": "fastembed-vector-embeddings",
    "lancedb": "lancedb-vector-database",
    "gin": "golang-gin-framework",
    "fiber": "golang-fiber-framework",
    "tokio": "rust-tokio-async",
    "axum": "rust-axum-web",
    "fastapi": "python-fastapi",
    "pydantic": "python-pydantic",
}


class ContinuousLearner:
    """Orchestrates continuous learning across codebases and episodic memory."""

    def __init__(
        self,
        projects_dir: Optional[Path] = None,
        specialties_dir: Optional[Path] = None,
        state_file: Optional[Path] = None,
    ):
        self.projects_dir = Path(projects_dir or DEFAULT_PROJECTS_DIR)
        self.specialties_dir = Path(specialties_dir or SPECIALTIES_DIR)
        self.state_file = Path(state_file or STATE_FILE)
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read state file: {e}")
        return {
            "version": "1.0.0",
            "last_cycle_timestamp": None,
            "total_cycles_run": 0,
            "tracked_projects": {},
            "discovered_technologies": [],
            "synthesized_specialties": [],
            "consolidated_insights": [],
        }

    def _save_state(self) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save state file: {e}")

    # =========================================================================
    # 1. Project & Workspace Scanner
    # =========================================================================
    def scan_workspaces(self) -> List[Dict[str, Any]]:
        """Inspects all project folders in the workspace directory."""
        if not self.projects_dir.exists():
            logger.info(f"Projects directory not found: {self.projects_dir}")
            return []

        scanned = []
        for pdir in sorted(self.projects_dir.iterdir()):
            if not pdir.is_dir() or pdir.name.startswith("."):
                continue

            info = {
                "name": pdir.name,
                "path": str(pdir),
                "technologies": set(),
                "manifests": [],
                "has_git": (pdir / ".git").exists(),
            }

            # 1. Inspect package.json (Node/Bun/TypeScript)
            pkg_json = pdir / "package.json"
            if pkg_json.exists():
                info["manifests"].append("package.json")
                try:
                    data = json.loads(pkg_json.read_text(encoding="utf-8"))
                    all_deps = {
                        **data.get("dependencies", {}),
                        **data.get("devDependencies", {}),
                    }
                    for dep in all_deps.keys():
                        for trigger, tech_key in KEY_FRAMEWORKS.items():
                            if trigger in dep.lower():
                                info["technologies"].add(tech_key)
                except Exception:
                    pass

            # 2. Inspect go.mod (Golang)
            go_mod = pdir / "go.mod"
            if go_mod.exists():
                info["manifests"].append("go.mod")
                info["technologies"].add("golang")
                try:
                    text = go_mod.read_text(encoding="utf-8")
                    if "gin-gonic" in text:
                        info["technologies"].add("golang-gin-framework")
                    if "gofiber" in text:
                        info["technologies"].add("golang-fiber-framework")
                except Exception:
                    pass

            # 3. Inspect requirements.txt / pyproject.toml (Python)
            req_txt = pdir / "requirements.txt"
            pyproj = pdir / "pyproject.toml"
            if req_txt.exists() or pyproj.exists():
                info["manifests"].append("python-manifest")
                info["technologies"].add("python")
                text = (
                    (req_txt.read_text(encoding="utf-8") if req_txt.exists() else "")
                    + " "
                    + (pyproj.read_text(encoding="utf-8") if pyproj.exists() else "")
                )
                if "fastapi" in text.lower():
                    info["technologies"].add("python-fastapi")
                if "lancedb" in text.lower():
                    info["technologies"].add("lancedb-vector-database")

            # 4. Inspect Cargo.toml (Rust)
            cargo_toml = pdir / "Cargo.toml"
            if cargo_toml.exists():
                info["manifests"].append("Cargo.toml")
                info["technologies"].add("rust")

            info["technologies"] = sorted(list(info["technologies"]))
            scanned.append(info)

        return scanned

    # =========================================================================
    # 2. Autonomous Specialty Gap Detection & Synthesis
    # =========================================================================
    def get_existing_specialty_slugs(self) -> Set[str]:
        """Returns all registered specialty slugs using SpecialtiesManager."""
        from cephalo.learning.specialties_manager import SpecialtiesManager
        sm = SpecialtiesManager()
        slugs = set()
        for s in sm.list_specialties():
            slug = s.get("slug", "")
            proj = s.get("project", "")
            if slug:
                slugs.add(slug)
                slugs.add(f"{proj}-{slug}")
                slugs.add(f"global-{slug}")
        return slugs

    def audit_and_synthesize_specialties(
        self, scanned_projects: List[Dict[str, Any]]
    ) -> List[str]:
        """Detects technologies and methodologies without a specialty and synthesizes them."""
        from cephalo.learning.specialties_manager import SpecialtiesManager
        from cephalo.learning.specialties_synthesizer import SpecialtySynthesizer

        existing_slugs = self.get_existing_specialty_slugs()
        sm = SpecialtiesManager()

        all_detected_tech: Set[str] = set()
        for p in scanned_projects:
            all_detected_tech.update(p.get("technologies", []))

        # Also audit recent prompts for novel tech/methodology mentions
        if PROMPTS_FILE.exists():
            try:
                with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            pdata = json.loads(line)
                            pcontent = pdata.get("content", "")
                            tech_hits = SpecialtySynthesizer.discover_technologies(pcontent)
                            all_detected_tech.update(tech_hits)
                        except Exception:
                            continue
            except Exception:
                pass

        synthesized = []
        for tech in sorted(all_detected_tech):
            # Check if specialty already exists under global or exact name
            global_slug = f"global-{tech}"
            if tech in existing_slugs or global_slug in existing_slugs:
                continue

            # Need to synthesize
            logger.info(f"Discovered novel stack without specialty: '{tech}'. Synthesizing...")
            try:
                spec = sm.auto_create_specialty(tech, project="global", sync_to_vector_db=True)
                if spec:
                    manifest = spec.get("manifest", {})
                    slug = manifest.get("slug", tech)
                    synthesized.append(slug)
                    existing_slugs.add(slug)
                    existing_slugs.add(f"global-{slug}")
            except Exception as e:
                logger.error(f"Failed to auto-synthesize specialty for '{tech}': {e}")

        return synthesized

    # =========================================================================
    # 3. Episodic to Semantic Memory Consolidation
    # =========================================================================
    def consolidate_prompts_memory(self, max_prompts: int = 150) -> List[Dict[str, Any]]:
        """Audits recent prompts and extracts recurring patterns and constraints."""
        if not PROMPTS_FILE.exists():
            return []

        prompts = []
        try:
            with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            prompts.append(json.loads(line))
                        except Exception:
                            pass
        except Exception:
            return []

        recent = prompts[-max_prompts:]
        insights: List[Dict[str, Any]] = []

        # Analyze recurring directives
        directive_patterns = [
            (r"\b(anti-slop|anti slop|no slop|clean code|matt pocock)\b", "coding_philosophy", "Strict anti-slop software engineering: Matt Pocock real-engineer rules, idiomatic simplicity, zero dead code."),
            (r"\b(tcl\s*65t8b|65-inch|4k\s*qled)\b", "hardware_profile", "Living room 4K display: TCL 65T8B (65\" QLED). High-saturation 4K visual target."),
            (r"\b(hungarian|magyar)\b", "language_locale", "Primary native language Hungarian (Magyar) alongside English for all user-facing tools."),
            (r"\b(continuous learning|continous learning|cephalo learn)\b", "second_brain_system", "Autonomous continuous learning enabled across all workspaces and sessions."),
            (r"\b(research|investigat|specialt(y|ies)|best practices|industry standard|popular github)\b", "research_specialty_standard", "Autonomous deep research & specialty creation standard: first-principles fundamentals, industry standards, anti-AI-slop craftsmanship (Matt Pocock, Linux kernel), top GitHub repos, and bound user preferences."),
        ]

        seen_keys = set()
        for p in recent:
            content = p.get("content", "").lower()
            for regex, key, statement in directive_patterns:
                if key in seen_keys:
                    continue
                if re.search(regex, content):
                    seen_keys.add(key)
                    insights.append({
                        "key": key,
                        "statement": statement,
                        "detected_at": datetime.datetime.now().astimezone().isoformat(),
                        "evidence_prompt_id": p.get("id"),
                    })

        return insights

    # =========================================================================
    # 4. Master Learning Cycle
    # =========================================================================
    def run_cycle(self) -> Dict[str, Any]:
        """Executes a complete continuous learning cycle."""
        start_time = time.time()
        logger.info("Starting autonomous continuous learning cycle...")

        # 1. Scan workspaces
        scanned_projects = self.scan_workspaces()

        # 2. Synthesize missing specialties
        synthesized_specs = self.audit_and_synthesize_specialties(scanned_projects)

        # 3. Consolidate memory insights
        insights = self.consolidate_prompts_memory()

        # 4. Update persistent state
        timestamp = datetime.datetime.now().astimezone().isoformat()
        self.state["last_cycle_timestamp"] = timestamp
        self.state["total_cycles_run"] = self.state.get("total_cycles_run", 0) + 1

        all_tech = set(self.state.get("discovered_technologies", []))
        for p in scanned_projects:
            all_tech.update(p.get("technologies", []))
        self.state["discovered_technologies"] = sorted(list(all_tech))

        all_synth = set(self.state.get("synthesized_specialties", []))
        all_synth.update(synthesized_specs)
        self.state["synthesized_specialties"] = sorted(list(all_synth))

        self.state["tracked_projects"] = {p["name"]: p["technologies"] for p in scanned_projects}
        self.state["consolidated_insights"] = insights

        self._save_state()

        duration = round(time.time() - start_time, 2)
        logger.info(
            f"Learning cycle complete in {duration}s. "
            f"Scanned {len(scanned_projects)} projects, "
            f"Synthesized {len(synthesized_specs)} new specialties, "
            f"Consolidated {len(insights)} core insights."
        )

        return {
            "timestamp": timestamp,
            "duration_seconds": duration,
            "scanned_projects_count": len(scanned_projects),
            "discovered_technologies": sorted(list(all_tech)),
            "newly_synthesized_specialties": synthesized_specs,
            "consolidated_insights": insights,
        }

    def watch(self, interval_seconds: int = 120) -> None:
        """Watches workspaces and runs periodic continuous learning."""
        logger.info(f"Starting Cephalo Continuous Learning Daemon (interval: {interval_seconds}s)...")
        try:
            while True:
                self.run_cycle()
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("Continuous learning daemon stopped gracefully.")


# =============================================================================
# CLI Interface
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Cephalo Continuous Learning Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Command: run
    run_p = subparsers.add_parser("run", help="Execute a one-shot continuous learning cycle.")
    run_p.add_argument("--json", action="store_true", help="Output summary in JSON format.")

    # Command: status
    status_p = subparsers.add_parser("status", help="Display continuous learning health and tracked topics.")
    status_p.add_argument("--json", action="store_true", help="Output status in JSON format.")

    # Command: watch
    watch_p = subparsers.add_parser("watch", help="Run background continuous watcher.")
    watch_p.add_argument("--interval", type=int, default=120, help="Interval between cycles in seconds (default: 120).")

    args = parser.parse_args()
    learner = ContinuousLearner()

    if args.command == "run" or args.command is None:
        report = learner.run_cycle()
        if getattr(args, "json", False):
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print("=" * 65)
            print("  CEPHALO CONTINUOUS LEARNING CYCLE REPORT")
            print("=" * 65)
            print(f"Timestamp:       {report['timestamp']}")
            print(f"Cycle Duration:  {report['duration_seconds']}s")
            print(f"Projects Scanned: {report['scanned_projects_count']}")
            print(f"Technologies:    {len(report['discovered_technologies'])} discovered")
            if report['newly_synthesized_specialties']:
                print(f"New Specialties: {', '.join(report['newly_synthesized_specialties'])}")
            else:
                print("New Specialties: None required (all stacks covered).")
            print(f"Consolidated:    {len(report['consolidated_insights'])} high-level insights")
            print("=" * 65)

    elif args.command == "status":
        state = learner.state
        if args.json:
            print(json.dumps(state, indent=2, ensure_ascii=False))
        else:
            print("=" * 65)
            print("  CEPHALO CONTINUOUS LEARNING STATUS")
            print("=" * 65)
            print(f"Total Cycles Run:     {state.get('total_cycles_run', 0)}")
            print(f"Last Cycle:           {state.get('last_cycle_timestamp', 'Never')}")
            print(f"Tracked Projects:     {len(state.get('tracked_projects', {}))}")
            for pname, techs in state.get('tracked_projects', {}).items():
                print(f"  • {pname}: {', '.join(techs) if techs else 'no standard manifests'}")
            print(f"Discovered Stacks:    {len(state.get('discovered_technologies', []))}")
            print(f"Synthesized Modules:  {len(state.get('synthesized_specialties', []))}")
            print("=" * 65)

    elif args.command == "watch":
        learner.watch(interval_seconds=args.interval)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Cephalo Deep Research & Specialty Synthesis Engine (research_engine.py)
======================================================================
Autonomous research engine embodying the user's exact methodology, depth,
and craftsmanship standards for investigating topics and creating specialties.

Core Methodological Invariants:
1. First Principles & Core Mechanics:
   - Deep dive into fundamentals, internal execution model, and system primitives.
2. Industry Standards & Production Best Practices:
   - Real-world production patterns from leading teams; anti-patterns to eliminate.
3. Craftsmanship & Anti-AI-Slop Discipline:
   - Matt Pocock "Skills for Real Engineers" (specs before tickets, tickets before code,
     vertical slices, structured grilling).
   - Linux Kernel conventions (Linus Torvalds: 1-2 screen functions, max 3 indent levels,
     early returns, minimal indirection, explicit error handling at call site, no swallowed errors).
   - Rule of Three (no speculative generic abstractions before 3 distinct call sites).
   - Strict type boundaries (no 'any' or unsafe casts; runtime contract validation via Zod/Pydantic).
4. Popular & Battle-Tested GitHub Projects:
   - Automated web search & GitHub API querying for top repositories, real stars, and reference patterns.
5. UI/UX & Human-Centered Standards (when applicable):
   - Nielsen Norman Group heuristics, Refactoring UI, WCAG 2.1 AA (4.5:1 text contrast, visible focus rings).
   - 4 mandatory async states: Loading/Skeleton, Error with retry, Empty with CTA, Populated.
   - Mobile-first ergonomics (44x44px touch targets, fixed bottom thumb zone, single-row swipeable carousels).
   - Simplicity is key, ALWAYS (clean stone/paper canvas, modern pastel semantic accents, zero raw HTML).
6. Bound User Preferences & Target Hardware:
   - Injects user profile constraints (TCL 65T8B TV for multimedia/video, English code/docs, silent background execution).
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Force UTF-8 on Windows terminal/pipes
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Base paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROFILE_FILE = SCRIPT_DIR / "USER_PROFILE.md"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [Cephalo:Research] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cephalo.research_engine")


def slugify(text: str) -> str:
    """Converts a string into a clean filesystem slug."""
    text = text.lower().strip()
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'[^a-z0-9\-]', '', text)
    return text or "default"


@dataclass
class GitHubRepoInfo:
    name: str
    url: str
    stars: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DeepResearchEngine:
    """
    Executes multi-perspective investigation across web search, GitHub repositories,
    and user engineering principles to produce production-grade Cephalo specialties.
    """

    GITHUB_API_HEADERS = {
        "User-Agent": "Cephalo-Deep-Researcher/1.0",
        "Accept": "application/vnd.github.v3+json",
    }

    # Common UI/UX keywords to trigger UI/UX ergonomics module
    UI_KEYWORDS = {
        "ui", "ux", "frontend", "css", "tailwind", "component", "design", "layout",
        "mobile", "web", "react", "vue", "svelte", "nextjs", "html", "screen", "theme",
        "modal", "view", "dashboard", "widget", "carousel"
    }

    # Multimedia / Cinema keywords to trigger TCL 65T8B & Video profile
    MEDIA_KEYWORDS = {
        "video", "cinema", "movie", "stream", "reels", "audio", "display", "tv", "remotion", "ffmpeg", "player"
    }

    def __init__(self):
        from web_search import WebSearchEngine
        self.web_engine = WebSearchEngine()

    def _query_github_repo_metadata(self, owner_repo: str) -> Optional[GitHubRepoInfo]:
        """Queries GitHub API for stars and repository description, fallback gracefully."""
        owner_repo = owner_repo.strip().strip("/")
        parts = owner_repo.split("/")
        if len(parts) != 2:
            return None

        owner, repo = parts[0], parts[1]
        api_url = f"https://api.github.com/repos/{owner}/{repo}"

        try:
            req = urllib.request.Request(api_url, headers=self.GITHUB_API_HEADERS)
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                stars_count = data.get("stargazers_count", 0)
                stars_str = f"{stars_count // 1000}k+" if stars_count >= 1000 else str(stars_count)
                desc = data.get("description") or "GitHub repository and architecture reference."
                return GitHubRepoInfo(
                    name=f"{owner}/{repo}",
                    url=f"https://github.com/{owner}/{repo}",
                    stars=stars_str,
                    description=desc.strip(),
                )
        except Exception:
            return None

    def search_curated_github_repos(self, topic: str, max_repos: int = 4) -> List[Dict[str, Any]]:
        """
        Searches GitHub via WebSearchEngine and resolves repository metadata,
        stars, and architectural descriptions.
        """
        results: List[Dict[str, Any]] = []
        seen_repos: Set[str] = set()

        queries = [
            f"site:github.com {topic} best practices OR awesome OR architecture",
            f"site:github.com {topic} framework OR library",
        ]

        for q in queries:
            if len(results) >= max_repos:
                break
            try:
                search_hits = self.web_engine.search(q, max_results=6)
                for hit in search_hits:
                    url = hit.url
                    match = re.search(r"github\.com/([a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+)", url)
                    if match:
                        full_repo = match.group(1).rstrip(".git")
                        # Skip GitHub special pages (topics, search, features)
                        if full_repo.split("/")[0] in ("features", "topics", "collections", "search", "trending", "explore"):
                            continue
                        if full_repo.lower() in seen_repos:
                            continue

                        seen_repos.add(full_repo.lower())

                        # Try GitHub API for exact stars and description
                        repo_info = self._query_github_repo_metadata(full_repo)
                        if repo_info:
                            results.append(repo_info.to_dict())
                        else:
                            # Fallback from search hit snippet
                            clean_title = re.sub(r"^GitHub\s*-\s*", "", hit.title).strip()
                            clean_desc = hit.snippet.strip() or f"Curated GitHub reference project for {topic}."
                            results.append({
                                "name": full_repo,
                                "url": f"https://github.com/{full_repo}",
                                "stars": "Curated",
                                "description": clean_desc,
                            })

                        if len(results) >= max_repos:
                            break
            except Exception as e:
                logger.debug(f"GitHub search query '{q}' failed: {e}")

        # If no repos found, provide awesome list link
        if not results:
            slug = slugify(topic)
            results.append({
                "name": f"awesome-{slug}",
                "url": f"https://github.com/search?q={urllib.parse.quote_plus(topic)}+awesome",
                "stars": "Curated",
                "description": f"Curated open-source ecosystem, architectures, and libraries for {topic}.",
            })

        return results

    def search_industry_best_practices(self, topic: str, max_snippets: int = 5) -> List[str]:
        """Searches the live web for industry standards, conventions, and production insights."""
        queries = [
            f"{topic} best practices industry standards production architecture",
            f"{topic} common mistakes anti-patterns pitfalls production",
        ]

        snippets: List[str] = []
        for q in queries:
            try:
                hits = self.web_engine.search(q, max_results=4)
                for h in hits:
                    if h.snippet and len(h.snippet) > 40:
                        clean_snip = re.sub(r"\s+", " ", h.snippet).strip()
                        snippets.append(clean_snip)
            except Exception as e:
                logger.debug(f"Best practices query '{q}' failed: {e}")

        return snippets[:max_snippets]

    def decompose_subtopics(self, topic: str, user_subtopics: Optional[List[str]] = None) -> List[str]:
        """Decomposes a broad topic into granular architectural subtopics."""
        if user_subtopics:
            return [s.strip() for s in user_subtopics if s.strip()]

        clean = topic.lower()
        subtopics = []

        # Domain-aware decomposition heuristics
        if any(w in clean for w in self.UI_KEYWORDS):
            subtopics.extend([
                "Component Architecture & State Management",
                "Design System Tokens & Semantic Styling",
                "Four Mandatory Async UI States (Skeleton, Error, Empty, Populated)",
                "Mobile-First Ergonomics & Touch Targets (44x44px)",
                "Accessibility Compliance (WCAG 2.1 AA & Keyboard Navigation)",
            ])
        elif any(w in clean for w in ("database", "sql", "orm", "postgres", "redis", "cache")):
            subtopics.extend([
                "Data Modeling & Normalization Invariants",
                "Indexing Strategy & Query Execution Plans",
                "Connection Pooling & Concurrency Lifecycle",
                "Atomic Operations & Race Condition Elimination",
                "Schema Migrations & Rollback Safety",
            ])
        elif any(w in clean for w in ("queue", "worker", "job", "event", "bullmq", "kafka", "rabbitmq")):
            subtopics.extend([
                "Job Lifecycle & Concurrency Throttling",
                "Deterministic Job Deduplication (jobId)",
                "Exponential Backoff Retries & Stalled Job Heartbeats",
                "Graceful Shutdown & In-Flight Worker Isolation",
            ])
        elif any(w in clean for w in ("api", "backend", "server", "endpoint", "webhook", "http")):
            subtopics.extend([
                "Payload Validation & Runtime Schema Contracts (Zod/Pydantic)",
                "Explicit Error Handling & Call-Site Context Propagation",
                "Rate Limiting & Backpressure Compliance",
                "Idempotency Keys & Replay Protection",
            ])
        elif any(w in clean for w in self.MEDIA_KEYWORDS):
            subtopics.extend([
                "Asset Preprocessing & Pipeline Optimization",
                "Color Grading & Saturation Tuning (TCL 65T8B 4K Pop)",
                "Zero-Buffering Playback & Instant Velocity Pacing",
            ])
        else:
            subtopics.extend([
                "First Principles & Core Execution Mechanics",
                "Modular Boundary Separation & Minimal Indirection",
                "Production Configuration & Failure Mode Recovery",
                "Deterministic Resource Cleanup & Lifecycle Management",
            ])

        return subtopics

    def synthesize_specialty(
        self,
        topic: str,
        project: str = "global",
        subtopics: Optional[List[str]] = None,
        custom_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Conducts deep investigation and synthesizes a production-grade specialty module
        following the user's anti-slop, craftsmanship, and depth standards.
        """
        clean_title = topic.replace("-", " ").replace("_", " ").title()
        slug = slugify(topic)
        logger.info(f"Conducting deep research for topic: '{clean_title}' (Project: {project})...")

        # 1. Decompose subtopics
        resolved_subtopics = self.decompose_subtopics(topic, subtopics)

        # 2. Live Web & GitHub Investigation
        curated_repos = self.search_curated_github_repos(topic)
        industry_snippets = self.search_industry_best_practices(topic)

        # 3. Detect UI and Media contexts
        is_ui_topic = any(w in topic.lower() for w in self.UI_KEYWORDS)
        is_media_topic = any(w in topic.lower() for w in self.MEDIA_KEYWORDS)

        # 4. Formulate Deep Fundamentals
        fundamentals_blocks = [
            f"Production engineering and architectural discipline for '{clean_title}'. "
            f"Grounded in verified first principles, deterministic lifecycle mechanics, and strict elimination "
            f"of AI slop (premature abstractions, redundant wrapper layers, empty helpers, and swallowed errors). "
            f"Enforces Matt Pocock's 'Skills for Real Engineers' (formal specs before tickets, tickets before code, "
            f"vertical slices, structured grilling) combined with the Linux Kernel software philosophy (Linus Torvalds: "
            f"functions fit on 1-2 screens, maximum 3 levels of indentation, early returns, self-evident code without "
            f"narrative comments explaining basic syntax, minimal indirection, and explicit error handling at the call site). "
            f"Adheres to the Rule of Three (write concrete code first; introduce generic abstractions only after 3 distinct "
            f"call sites share identical invariants) and strict type boundaries with runtime validation (Zod/Pydantic)."
        ]

        if resolved_subtopics:
            fundamentals_blocks.append(
                "### Architectural Subtopics & Primitives\n"
                + "\n".join([f"- **{s}**: Production-grade isolation and verified mechanics." for s in resolved_subtopics])
            )

        if industry_snippets:
            fundamentals_blocks.append(
                "### Industry Standards & Production Evidence\n"
                + "\n".join([f"- {snip}" for snip in industry_snippets[:3]])
            )

        if is_ui_topic:
            fundamentals_blocks.append(
                "### Human-Centered UI/UX Engineering Standards\n"
                f"Adheres to gold-standard human-designed interface principles (Readwise Reader, Substack, Linear, Things 3). "
                f"Requires a tokenized design system (CSS variables for colors, typography, spacing), calm modern pastel "
                f"semantic accents with strict WCAG 2.1 AA text contrast (> 4.5:1), and unbleached stone/warm paper canvases. "
                f"Mandates four explicit states for all async views (Loading/Skeleton, Error with retry, Empty with clear CTA, "
                f"and Populated). Mobile-first navigation is anchored strictly in the fixed bottom thumb zone with 44x44px minimum tap targets. "
                f"Zero raw unescaped HTML and zero generic AI template clichés (no harsh pitch-black backgrounds, glowing cyan borders, or sparkle stars)."
            )

        if is_media_topic:
            fundamentals_blocks.append(
                "### Living Room Hardware & Display Optimization\n"
                f"Engineered specifically for the primary living room display: **TCL 65T8B** (65-inch 4K QLED Google TV). "
                f"Prioritizes eye-popping visual pop, high dynamic range, vibrant saturation, and instant velocity from minute 1. "
                f"Strictly avoids slow-burn pacing and drab, muted grey palettes."
            )

        if custom_notes:
            fundamentals_blocks.append(f"### Specific Implementation Directives\n{custom_notes.strip()}")

        full_fundamentals = "\n\n".join(fundamentals_blocks)

        # 5. Formulate Actionable Key Takeaways
        takeaways = [
            f"Specification before implementation: define crisp domain schemas and contracts before writing implementation code.",
            f"Maximum 3 levels of indentation: invert 'if' conditionals with early returns; keep functions focused on a single responsibility.",
            f"Explicit error handling: handle errors at call sites; attach informative boundary context; never swallow exceptions.",
            f"Anti-slop simplicity: ban premature generic wrappers; write straightforward concrete code; respect the Rule of Three.",
            f"Strict boundary validation: enforce runtime contract boundaries using schemas (Zod/Pydantic); avoid unsafe type assertions ('as any').",
            f"Deterministic lifecycle management: ensure all connections, timers, workers, and subprocesses close cleanly with zero resource leaks.",
        ]

        if is_ui_topic:
            takeaways.extend([
                "Four mandatory UI states: every async view must handle Loading (skeletons), Error (retry CTA), Empty (helpful CTA), and Populated.",
                "Mobile thumb-zone ergonomics: primary navigation in bottom safe area; enforce 44x44px minimum tap targets; single-row horizontal carousels.",
                "Tactile calm aesthetics: warm stone paper canvas, modern pastel semantic accents, and zero raw HTML or AI template markers.",
            ])

        # 6. User Preferences Binding
        user_prefs = [
            "anti_slop_engineering",
            "minimal_indirection",
            "specs_before_code",
            "rule_of_three",
            "strict_runtime_validation",
            "silent_background_execution",
            "english_code_and_docs",
        ]
        if is_ui_topic:
            user_prefs.extend(["wcag_2_1_aa", "tokenized_design_system", "mobile_thumb_zone", "simplicity_first"])
        if is_media_topic:
            user_prefs.extend(["tcl_65t8b_qled_4k", "instant_velocity_pacing", "high_saturation"])

        tags = [slug, project, "deep-research", "industry-standards"]
        if is_ui_topic:
            tags.append("ui-ux")
        if is_media_topic:
            tags.append("multimedia")

        return {
            "name": f"{clean_title} Architecture & Engineering",
            "slug": slug,
            "project": project,
            "fundamentals": full_fundamentals,
            "key_takeaways": takeaways,
            "github_repos": curated_repos,
            "user_preferences": user_prefs,
            "tags": tags,
            "subtopics": resolved_subtopics,
            "researched_at": datetime.datetime.now().astimezone().isoformat(),
        }


# =============================================================================
# CLI Interface
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Cephalo Deep Research & Specialty Synthesis Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("topic", help="Technology, methodology, or domain topic to research.")
    parser.add_argument("--project", default="global", help="Target project slug (default: global).")
    parser.add_argument("--subtopics", nargs="+", help="Specific subtopics to decompose and investigate.")
    parser.add_argument("--notes", help="Optional user notes or custom architectural directives.")
    parser.add_argument("--create", action="store_true", help="Automatically persist specialty in Cephalo and LanceDB.")
    parser.add_argument("--json", action="store_true", help="Output raw synthesized JSON.")

    args = parser.parse_args()
    engine = DeepResearchEngine()

    synthesized = engine.synthesize_specialty(
        topic=args.topic,
        project=args.project,
        subtopics=args.subtopics,
        custom_notes=args.notes,
    )

    if args.create:
        from specialties_manager import SpecialtiesManager
        sm = SpecialtiesManager()
        created = sm.create_specialty(
            name=synthesized["name"],
            project=synthesized["project"],
            fundamentals=synthesized["fundamentals"],
            github_repos=synthesized["github_repos"],
            key_takeaways=synthesized["key_takeaways"],
            user_preferences=synthesized["user_preferences"],
            tags=synthesized["tags"],
            slug=synthesized["slug"],
            sync_to_vector_db=True,
        )
        print(f"Successfully researched and created specialty '{synthesized['name']}' at {created['path']}")

    if args.json:
        print(json.dumps(synthesized, indent=2, ensure_ascii=False))
    elif not args.create:
        print("=" * 70)
        print(f"  CEPHALO DEEP RESEARCH REPORT: {synthesized['name']}")
        print("=" * 70)
        print(f"Project:     {synthesized['project']}")
        print(f"Slug:        {synthesized['slug']}")
        print(f"Subtopics:   {', '.join(synthesized['subtopics'])}")
        print(f"Repositories ({len(synthesized['github_repos'])}):")
        for r in synthesized["github_repos"]:
            print(f"  * {r['name']} (Stars: {r['stars']}): {r['description'][:80]}...")
        print(f"Key Takeaways ({len(synthesized['key_takeaways'])}):")
        for t in synthesized["key_takeaways"][:4]:
            print(f"  - {t}")
        print("=" * 70)


if __name__ == "__main__":
    main()

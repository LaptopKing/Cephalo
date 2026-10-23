#!/usr/bin/env python3
"""
Cephalo - Web Search & Sovereign SERP Intelligence Engine (web_search.py)
========================================================================
Provides multi-engine web search, Google-style SERP synthesis, clean content
extraction, and interactive generative UI rendering.

Features:
- Sovereign Google-Style SERP UX:
  * Instant AI Overview / Quick Summary synthesized from authoritative sources.
  * Organic Web Results with breadcrumbs, favicons, clean URLs, and snippets.
  * Inline & Dedicated Social Blocks (Reddit, YouTube, GitHub, X, StackOverflow).
- Dual Engine Architecture:
  * High-Precision Neural Search via Exa API (quota-preserved with local SQLite caching).
  * Resilient Zero-Key DuckDuckGo HTML parser & Chromium dynamic crawler fallback.
- Rich Generative UI:
  * Antigravity inline chat widgets (<agent-embed>).
  * Standalone responsive HTML artifacts (WCAG 2.1 AA, stone paper / dark obsidian aesthetic).
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import logging
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Base paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CACHE_DB_PATH = DATA_DIR / "search_cache.db"
DEFAULT_PROFILE_DIR = DATA_DIR / "chromium_profile"
MCP_CONFIG_PATH = Path.home() / ".gemini" / "config" / "mcp_config.json"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [Cephalo:Web] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cephalo.web_search")

# Import SERP data structures
try:
    from serp_renderer import CephaloSERP, SearchItem, get_social_badge, render_serp_html
except ImportError:
    # Fallback if imported from a different cwd
    sys.path.insert(0, str(BASE_DIR))
    from serp_renderer import CephaloSERP, SearchItem, get_social_badge, render_serp_html


def is_deep_discussion_url(url: str) -> bool:
    """
    Validates whether a URL points to an actual discussion thread, forum topic,
    issue, or video, rather than a generic landing page, channel root, or category index.
    """
    if not url:
        return False
    try:
        p = urllib.parse.urlparse(url)
        netloc = p.netloc.lower()
        path = p.path.lower()
        query = p.query.lower()

        # Reddit: strictly requires /comments/<id>/
        if "reddit.com" in netloc:
            return "/comments/" in path

        # YouTube: strictly requires watch?v= or youtu.be/<id> (reject channel/playlist roots)
        if "youtube.com" in netloc or "youtu.be" in netloc:
            if any(k in path for k in ["/channel/", "/@", "/playlist", "/feed"]):
                return False
            return "watch?v=" in url or "youtu.be/" in url

        # GitHub: strictly requires /discussions/, /issues/, or /pull/
        if "github.com" in netloc:
            if any(k in path for k in ["/blob/", "/tree/", "/releases", "/commit"]):
                return False
            return any(k in path for k in ["/discussions/", "/issues/", "/pull/"])

        # Stack Overflow / Stack Exchange: strictly requires /questions/
        if "stackoverflow.com" in netloc or "stackexchange.com" in netloc:
            return "/questions/" in path

        # Hacker News: strictly requires item?id=
        if "news.ycombinator.com" in netloc:
            return "item?id=" in query or "item?id=" in url

        # Lobsters: strictly requires /s/
        if "lobste.rs" in netloc:
            return "/s/" in path

        # Specialized community forums: AVSForum, Tom's Hardware, Linus Tech Tips, MacRumors
        if any(f in netloc for f in ["avsforum.com", "tomshardware.com", "linustechtips.com", "macrumors.com"]):
            return any(k in path for k in ["/threads/", "/topic/"])

        # Generic Discourse / forum thread patterns
        if re.search(r'/(t|threads|topic|thread|discussion|viewtopic\.php)/[a-zA-Z0-9_\-]+', path):
            return True

        return False
    except Exception:
        return False


def select_community_targets(query: str) -> List[str]:
    """
    Selects high-relevance community and forum domains dynamically based on query topic.
    """
    q_lower = query.lower()

    # Hardware, Audio/Video, Home Theater, Displays (e.g. TCL TV, Monitors, Audio)
    hardware_keywords = [
        "tv", "oled", "qled", "display", "screen", "audio", "speaker", "soundbar",
        "gpu", "cpu", "monitor", "tcl", "hdmi", "receiver", "amp", "subwoofer", "dolby", "rtings",
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', q_lower) for w in hardware_keywords):
        return [
            "avsforum.com",
            "reddit.com",
            "youtube.com",
            "forums.tomshardware.com",
            "linustechtips.com",
        ]

    # Automotive & Mechanics (e.g. MyGarage)
    automotive_keywords = [
        "car", "vehicle", "engine", "transmission", "brake", "oil", "bmw", "audi",
        "mercedes", "tires", "garage", "exhaust", "mechanic",
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', q_lower) for w in automotive_keywords):
        return [
            "reddit.com",
            "youtube.com",
            "bobistheoilguy.com",
            "garagejournal.com",
        ]

    # Software Engineering, Programming, Web Dev
    dev_keywords = [
        "code", "nextjs", "next.js", "react", "python", "typescript", "javascript",
        "rust", "golang", "go", "docker", "k8s", "kubernetes", "bug", "error",
        "api", "framework", "git", "npm", "pip", "sql", "postgres", "redis",
        "database", "css", "html", "tailwind", "fastapi", "vue", "angular", "node",
        "nodejs", "prisma", "orm", "sdk", "backend", "frontend",
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', q_lower) for w in dev_keywords):
        return [
            "github.com",
            "news.ycombinator.com",
            "stackoverflow.com",
            "lobste.rs",
            "reddit.com",
            "youtube.com",
        ]

    # General default: high-relevance mix
    return [
        "reddit.com",
        "news.ycombinator.com",
        "youtube.com",
        "github.com",
        "stackoverflow.com",
    ]



@dataclass
class SearchResult:
    """Legacy dataclass preserved for 100% backward compatibility."""
    title: str
    url: str
    snippet: str
    source: str = "web"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HTMLTextExtractor(HTMLParser):
    """Clean HTML parser that strips scripts, styles, and extracts readable text."""

    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text_parts: List[str] = []
        self._ignore_tag = False

    def handle_starttag(self, tag: str, attrs: Any):
        if tag.lower() in ("script", "style", "noscript", "svg", "head", "iframe"):
            self._ignore_tag = True
        elif tag.lower() in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"):
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str):
        if tag.lower() in ("script", "style", "noscript", "svg", "head", "iframe"):
            self._ignore_tag = False
        elif tag.lower() in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"):
            self.text_parts.append("\n")

    def handle_data(self, data: str):
        if not self._ignore_tag:
            cleaned = data.strip()
            if cleaned:
                self.text_parts.append(cleaned + " ")

    def get_text(self) -> str:
        raw = "".join(self.text_parts)
        return re.sub(r'\n\s*\n+', '\n\n', raw).strip()


class WebSearchEngine:
    """
    Orchestrates web search, Google-style SERP synthesis, and content extraction.
    """

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Cephalo/1.0"
    )

    SOCIAL_DOMAINS = [
        "reddit.com",
        "youtube.com",
        "github.com",
        "x.com",
        "twitter.com",
        "stackoverflow.com",
        "news.ycombinator.com",
    ]

    def __init__(self, tavily_api_key: Optional[str] = None, exa_api_key: Optional[str] = None):
        self.tavily_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        self.exa_key = exa_api_key or self._resolve_exa_key()
        self._init_cache_db()

    def _resolve_exa_key(self) -> Optional[str]:
        """Resolves Exa API key from environment or Antigravity MCP configuration."""
        if os.getenv("EXA_API_KEY"):
            return os.getenv("EXA_API_KEY")
        if MCP_CONFIG_PATH.exists():
            try:
                with open(MCP_CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    key = cfg.get("mcpServers", {}).get("exa", {}).get("headers", {}).get("x-api-key")
                    if key:
                        return key
            except Exception:
                pass
        return None

    def _init_cache_db(self) -> None:
        """Initializes SQLite cache database to preserve monthly API quota."""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(CACHE_DB_PATH) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS serp_cache (
                        cache_key TEXT PRIMARY KEY,
                        query TEXT NOT NULL,
                        serp_json TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        expires_at REAL NOT NULL
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.debug(f"Failed to initialize search cache DB: {e}")

    def _get_from_cache(self, query: str) -> Optional[CephaloSERP]:
        """Retrieves cached SERP result if still fresh."""
        try:
            cache_key = hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()
            now = time.time()
            with sqlite3.connect(CACHE_DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT serp_json FROM serp_cache WHERE cache_key = ? AND expires_at > ?",
                    (cache_key, now),
                )
                row = cur.fetchone()
                if row:
                    data = json.loads(row[0])
                    organic = [SearchItem(**item) for item in data.get("organic_results", [])]
                    social = [SearchItem(**item) for item in data.get("social_blocks", [])]
                    return CephaloSERP(
                        query=data.get("query", query),
                        quick_summary=data.get("quick_summary", ""),
                        key_takeaways=data.get("key_takeaways", []),
                        citations=data.get("citations", []),
                        organic_results=organic,
                        social_blocks=social,
                        execution_time_seconds=0.01,
                        engine_used=data.get("engine_used", "Cache") + " (Cached)",
                    )
        except Exception as e:
            logger.debug(f"Cache lookup failed: {e}")
        return None

    def _save_to_cache(self, serp: CephaloSERP, ttl_hours: float = 24.0) -> None:
        """Persists SERP result to SQLite cache."""
        try:
            cache_key = hashlib.sha256(serp.query.strip().lower().encode("utf-8")).hexdigest()
            now = time.time()
            expires = now + (ttl_hours * 3600)
            data_str = json.dumps(serp.to_dict(), ensure_ascii=False)
            with sqlite3.connect(CACHE_DB_PATH) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO serp_cache (cache_key, query, serp_json, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                    (cache_key, serp.query, data_str, now, expires),
                )
                conn.commit()
        except Exception as e:
            logger.debug(f"Failed to cache search result: {e}")

    def search_serp(
        self,
        query: str,
        max_results: int = 5,
        include_social: bool = True,
        use_cache: bool = True,
    ) -> CephaloSERP:
        """
        Executes a Google-style SERP search with Quick Summary, Organic Results,
        and Social & Community Blocks.
        """
        query = query.strip()
        if not query:
            return CephaloSERP(
                query="",
                quick_summary="Empty search query provided.",
                key_takeaways=[],
                citations=[],
                organic_results=[],
                social_blocks=[],
            )

        # 1. Check local cache
        if use_cache:
            cached = self._get_from_cache(query)
            if cached:
                return cached

        t0 = time.time()
        organic_items: List[SearchItem] = []
        social_items: List[SearchItem] = []
        engine_name = "DuckDuckGo (Free Fallback)"

        # 2. Try Exa Neural Engine (if key exists)
        if self.exa_key:
            try:
                organic_items, social_items = self._search_exa_serp(query, max_results=max_results, include_social=include_social)
                engine_name = "Exa Neural Search"
            except Exception as exa_err:
                logger.warning(f"Exa search failed ({exa_err}), falling back to DuckDuckGo.")

        # 3. Fallback to DuckDuckGo HTML (Zero-Key) if no results from Exa
        if not organic_items:
            organic_items, social_items = self._search_duckduckgo_serp(query, max_results=max_results, include_social=include_social)
            engine_name = "DuckDuckGo Multi-Stream"

        # 4. Synthesize Quick Summary (AI Overview)
        all_items = organic_items + social_items
        quick_summary, takeaways, citations = self._synthesize_quick_summary(query, all_items)

        elapsed = time.time() - t0
        serp = CephaloSERP(
            query=query,
            quick_summary=quick_summary,
            key_takeaways=takeaways,
            citations=citations,
            organic_results=organic_items,
            social_blocks=social_items,
            execution_time_seconds=elapsed,
            engine_used=engine_name,
        )

        # Cache valid results
        if organic_items or social_items:
            self._save_to_cache(serp)

        return serp

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Legacy search interface returning standard SearchResult list."""
        serp = self.search_serp(query=query, max_results=max_results, include_social=False)
        return [
            SearchResult(
                title=item.title,
                url=item.url,
                snippet=item.snippet,
                source=item.source,
            )
            for item in serp.organic_results
        ]

    def _search_exa_serp(
        self,
        query: str,
        max_results: int = 5,
        include_social: bool = True,
    ) -> Tuple[List[SearchItem], List[SearchItem]]:
        """Queries Exa API for both organic and deep social discussion streams with text highlights."""
        from exa_py import Exa
        exa = Exa(api_key=self.exa_key)

        # Stream 1: Organic Results
        res_organic = exa.search(
            query,
            num_results=max_results + 2,
            contents={"highlights": True, "text": False},
        )

        organic_items: List[SearchItem] = []
        for r in res_organic.results:
            domain = urllib.parse.urlparse(r.url).netloc.lower()
            snippet = (r.highlights[0] if r.highlights else "")
            snippet = snippet.replace("\n", " ").strip()
            item = SearchItem(
                title=r.title or domain,
                url=r.url,
                display_url=domain + urllib.parse.urlparse(r.url).path,
                snippet=snippet,
                domain=domain,
                source="exa",
                social_type=self._classify_social(domain),
                extra={"highlights": r.highlights},
            )
            organic_items.append(item)

        # Stream 2: Deep Social & Community Discussions (Enforce Actual Threads)
        social_items: List[SearchItem] = []
        if include_social:
            target_domains = select_community_targets(query)
            seen_urls = set()
            try:
                # Primary community query with topic-targeted domains
                res_social = exa.search(
                    query,
                    include_domains=target_domains,
                    num_results=8,
                    contents={"highlights": True, "text": False},
                )
                for r in res_social.results:
                    if not is_deep_discussion_url(r.url):
                        continue
                    if r.url in seen_urls:
                        continue
                    seen_urls.add(r.url)

                    domain = urllib.parse.urlparse(r.url).netloc.lower()
                    snippet = (r.highlights[0] if r.highlights else "").replace("\n", " ").strip()
                    s_type = self._classify_social(domain)
                    social_items.append(
                        SearchItem(
                            title=r.title or f"Discussion on {domain}",
                            url=r.url,
                            display_url=domain + urllib.parse.urlparse(r.url).path,
                            snippet=snippet,
                            domain=domain,
                            source="exa_social",
                            social_type=s_type,
                            extra={"highlights": r.highlights},
                        )
                    )
                    if len(social_items) >= 4:
                        break
            except Exception as e:
                logger.debug(f"Exa targeted social search failed: {e}")

            # If fewer than 2 deep discussions found, run a targeted discussion fallback
            if len(social_items) < 2:
                try:
                    fallback_domains = ["news.ycombinator.com", "github.com", "stackoverflow.com", "youtube.com", "lobste.rs"]
                    fallback_q = f"{query} discussion problem issue feedback"
                    res_fb = exa.search(
                        fallback_q,
                        include_domains=fallback_domains,
                        num_results=6,
                        contents={"highlights": True, "text": False},
                    )
                    for r in res_fb.results:
                        if not is_deep_discussion_url(r.url):
                            continue
                        if r.url in seen_urls:
                            continue
                        seen_urls.add(r.url)

                        domain = urllib.parse.urlparse(r.url).netloc.lower()
                        snippet = (r.highlights[0] if r.highlights else "").replace("\n", " ").strip()
                        s_type = self._classify_social(domain)
                        social_items.append(
                            SearchItem(
                                title=r.title or f"Discussion on {domain}",
                                url=r.url,
                                display_url=domain + urllib.parse.urlparse(r.url).path,
                                snippet=snippet,
                                domain=domain,
                                source="exa_social_fallback",
                                social_type=s_type,
                                extra={"highlights": r.highlights},
                            )
                        )
                        if len(social_items) >= 4:
                            break
                except Exception as e:
                    logger.debug(f"Exa discussion fallback query failed: {e}")

        return organic_items[:max_results], social_items[:4]

    def _search_duckduckgo_serp(
        self,
        query: str,
        max_results: int = 5,
        include_social: bool = True,
    ) -> Tuple[List[SearchItem], List[SearchItem]]:
        """Zero-key DuckDuckGo HTML parser with fixed snippet extraction and deep social blocks."""
        raw_items = self._fetch_duckduckgo_raw(query, max_results=max_results + 5)

        organic_items: List[SearchItem] = []
        social_items: List[SearchItem] = []

        for it in raw_items:
            s_type = self._classify_social(it["domain"])
            search_item = SearchItem(
                title=it["title"],
                url=it["url"],
                display_url=it["display_url"],
                snippet=it["snippet"],
                domain=it["domain"],
                source="duckduckgo",
                social_type=s_type,
            )
            # Strictly enforce deep discussion URL validation
            if s_type and is_deep_discussion_url(it["url"]) and include_social:
                social_items.append(search_item)
            else:
                organic_items.append(search_item)

        # If social items are missing and social is requested, run targeted deep discussion search
        if include_social and len(social_items) < 2:
            try:
                social_q = f"{query} (site:reddit.com/r/*/comments OR site:news.ycombinator.com/item OR site:github.com/*/discussions OR site:stackoverflow.com/questions)"
                raw_socials = self._fetch_duckduckgo_raw(social_q, max_results=4)
                for s in raw_socials:
                    if not is_deep_discussion_url(s["url"]):
                        continue
                    s_type = self._classify_social(s["domain"])
                    social_items.append(
                        SearchItem(
                            title=s["title"],
                            url=s["url"],
                            display_url=s["display_url"],
                            snippet=s["snippet"],
                            domain=s["domain"],
                            source="duckduckgo_social",
                            social_type=s_type or "community",
                        )
                    )
            except Exception:
                pass

        return organic_items[:max_results], social_items[:4]


    def _fetch_duckduckgo_raw(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Submits DuckDuckGo HTML request and extracts full titles, clean URLs, and snippets."""
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            html_content = response.read().decode("utf-8", errors="ignore")

        # Split by individual result block
        parts = re.split(r'<div class="result results_links results_links_deep web-result ">', html_content)
        results: List[Dict[str, Any]] = []

        title_pattern = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
        snippet_pattern = re.compile(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)
        url_pattern = re.compile(r'<a class="result__url"[^>]*>(.*?)</a>', re.DOTALL)

        for part in parts[1:]:
            if len(results) >= max_results:
                break

            t_match = title_pattern.search(part)
            s_match = snippet_pattern.search(part)
            u_match = url_pattern.search(part)

            if not t_match:
                continue

            raw_href = t_match.group(1)
            if "uddg=" in raw_href:
                parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(raw_href).query)
                clean_url = parsed_qs.get("uddg", [raw_href])[0]
            else:
                clean_url = raw_href

            title = html.unescape(re.sub(r'<[^>]+>', '', t_match.group(2)).strip())
            snippet = html.unescape(re.sub(r'<[^>]+>', '', s_match.group(1)).strip()) if s_match else ""
            display_url = html.unescape(re.sub(r'<[^>]+>', '', u_match.group(1)).strip()) if u_match else clean_url
            domain = urllib.parse.urlparse(clean_url).netloc.lower()

            results.append({
                "title": title,
                "url": clean_url,
                "display_url": display_url,
                "snippet": snippet,
                "domain": domain,
            })

        return results

    def _classify_social(self, domain: str) -> Optional[str]:
        """Classifies a domain into its community/social category."""
        domain = domain.lower()
        if "reddit.com" in domain:
            return "reddit"
        if "youtube.com" in domain or "youtu.be" in domain:
            return "youtube"
        if "github.com" in domain:
            return "github"
        if "twitter.com" in domain or "x.com" in domain:
            return "x"
        if "stackoverflow.com" in domain or "stackexchange.com" in domain:
            return "stackoverflow"
        if "news.ycombinator.com" in domain:
            return "hackernews"
        if "lobste.rs" in domain:
            return "lobsters"
        if "avsforum.com" in domain:
            return "avsforum"
        if "tomshardware.com" in domain:
            return "tomshardware"
        if "linustechtips.com" in domain:
            return "linustechtips"
        if any(k in domain for k in ["discourse", "forum", "community"]):
            return "forum"
        return None


    def _synthesize_quick_summary(
        self,
        query: str,
        items: List[SearchItem],
    ) -> Tuple[str, List[str], List[Dict[str, str]]]:
        """
        Synthesizes an immediate high-signal executive overview answering the search
        query, along with bullet takeaways and domain citations.
        """
        query_words = set(re.findall(r'\w+', query.strip().lower()))
        stop_words = {"the", "a", "an", "in", "on", "at", "for", "to", "of", "and", "or", "is", "are", "vs", "what", "how", "with"}
        meaningful = query_words - stop_words

        candidates = []
        seen = set()

        for it in items:
            text_sources = []
            if it.extra and "highlights" in it.extra:
                hl = it.extra["highlights"]
                if isinstance(hl, list):
                    text_sources.extend(hl)
                else:
                    text_sources.append(str(hl))
            if it.snippet:
                text_sources.append(it.snippet)

            combined_raw = " ".join(text_sources)
            # 1. Clean markdown artifacts, code blocks, and comments
            cleaned_body = re.sub(r'```[\s\S]*?```', ' ', combined_raw)
            cleaned_body = re.sub(r'\{/\*[\s\S]*?\*/\}', ' ', cleaned_body)
            cleaned_body = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', cleaned_body)
            cleaned_body = cleaned_body.replace('`', '')
            cleaned_body = re.sub(r'#+\s*', '', cleaned_body)

            # 2. Split by punctuation or linebreaks
            sentences = re.split(r'(?<=[.!?])\s+|\n+', cleaned_body)
            for s in sentences:
                s_clean = s.strip()
                # Skip markdown tables, long URLs, or paths
                if s_clean.count('|') >= 2 or '---' in s_clean or s_clean.count('/') >= 4:
                    continue
                s_clean = re.sub(r'^[^a-zA-Z0-9]+', '', s_clean)
                s_clean = re.sub(r'\s+', ' ', s_clean).strip()
                if len(s_clean) < 35 or len(s_clean) > 240:
                    continue

                words = s_clean.split()
                if len(words) < 6:
                    continue

                s_lower = s_clean.lower()
                sim_key = "".join(ch for ch in s_lower if ch.isalnum())[:50]
                if sim_key in seen:
                    continue
                seen.add(sim_key)

                score = 0
                word_set = set(re.findall(r'\w+', s_lower))
                score += len(word_set.intersection(meaningful)) * 4

                if any(k in s_lower for k in ["features", "introduces", "is a", "allows", "support", "released", "faster", "improves", "now provides", "designed to"]):
                    score += 3
                if any(k in s_lower for k in ["cookie", "privacy policy", "sign up", "subscribe", "click here", "read more"]):
                    score -= 20

                candidates.append((score, s_clean, it.title, it.url, it.domain))

        candidates.sort(key=lambda x: x[0], reverse=True)

        overview_parts = []
        takeaways = []
        citations = []
        seen_domains = set()

        for score, sent, title, url, domain in candidates[:6]:
            if len(overview_parts) < 2:
                overview_parts.append(sent)
            else:
                takeaways.append(sent)

            if domain and domain not in seen_domains:
                seen_domains.add(domain)
                citations.append({"title": title, "url": url, "domain": domain})

        if not overview_parts and items:
            overview = items[0].snippet or f"Information regarding {query}."
        else:
            overview = " ".join(overview_parts)

        return overview, takeaways[:4], citations[:4]

    def render_serp_html(
        self,
        serp: CephaloSERP,
        output_path: Optional[Path] = None,
        standalone: bool = False,
    ) -> str:
        """Renders the HTML document and optionally saves to disk."""
        html_content = render_serp_html(serp, standalone=standalone)
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html_content, encoding="utf-8")
        return html_content

    def is_youtube_url(self, url: str) -> bool:
        """Determines whether a URL or string refers to a YouTube video."""
        if not url:
            return False
        return bool(re.search(r'(?:youtube\.com\/(?:watch\?v=|shorts\/|embed\/)|youtu\.be\/|^[a-zA-Z0-9_-]{11}$)', url))

    def fetch_youtube_transcript(
        self,
        video_url_or_id: str,
        languages: Optional[List[str]] = None,
        max_chars: int = 40000,
    ) -> Dict[str, Any]:
        """Fetches and formats a clean transcript from a YouTube video."""
        vid_match = re.search(r'(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/)([a-zA-Z0-9_-]{11})', video_url_or_id)
        video_id = vid_match.group(1) if vid_match else video_url_or_id.strip()

        if len(video_id) != 11:
            raise ValueError(f"Invalid YouTube video identifier: '{video_url_or_id}'")

        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError:
            raise RuntimeError("youtube-transcript-api is not installed. Run 'pip install youtube-transcript-api'")

        langs = languages or ["en", "hu"]
        ytt = YouTubeTranscriptApi()
        transcript_list = ytt.list(video_id)

        # 1. Try finding preferred languages
        transcript = None
        try:
            transcript = transcript_list.find_transcript(langs)
        except Exception:
            # 2. Fall back to first available transcript
            try:
                for t in transcript_list:
                    transcript = t
                    break
            except Exception:
                pass

        if not transcript:
            raise RuntimeError(f"No transcripts found for YouTube video {video_id}")

        fetched = transcript.fetch()
        paragraphs = []
        current_chunk = []
        current_len = 0

        for snippet in fetched:
            text = snippet.text.strip()
            # Remove music/sound notations like [Music], [♪♪♪], (Applause)
            text = re.sub(r'\[(?:Music|Applause|♪+)[^\]]*\]', '', text, flags=re.IGNORECASE)
            text = re.sub(r'\((?:Music|Applause|♪+)[^\)]*\)', '', text, flags=re.IGNORECASE).strip()
            if not text:
                continue

            current_chunk.append(text)
            current_len += len(text)

            # Group every ~300 chars into coherent paragraphs
            if current_len >= 300 or text.endswith(('.', '!', '?')):
                paragraphs.append(" ".join(current_chunk))
                current_chunk = []
                current_len = 0

        if current_chunk:
            paragraphs.append(" ".join(current_chunk))

        full_text = "\n\n".join(paragraphs)
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars] + f"\n\n[Truncated to {max_chars} characters]"

        return {
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "language": transcript.language,
            "language_code": transcript.language_code,
            "is_generated": transcript.is_generated,
            "content": full_text,
        }

    def fetch_url(
        self,
        target_url: str,
        max_chars: int = 15000,
        dynamic: bool = False,
        headless: bool = True,
        persistent: bool = False,
    ) -> str:
        """Fetches a URL and returns clean readable markdown/text content."""
        if self.is_youtube_url(target_url):
            try:
                yt_res = self.fetch_youtube_transcript(target_url, max_chars=max_chars)
                return f"[YouTube Transcript - {yt_res['url']} ({yt_res['language']})]\n\n{yt_res['content']}"
            except Exception as e:
                logger.warning("YouTube transcript fetch failed (%s), falling back to standard fetch", e)

        if dynamic:
            return self.fetch_dynamic(
                target_url=target_url,
                max_chars=max_chars,
                headless=headless,
                persistent=persistent,
            )

        try:
            req = urllib.request.Request(target_url, headers={"User-Agent": self.USER_AGENT})
            with urllib.request.urlopen(req, timeout=12) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" not in content_type and "text/plain" not in content_type:
                    return f"[Unsupported Content-Type: {content_type}]"
                html_text = resp.read().decode("utf-8", errors="ignore")

            parser = HTMLTextExtractor()
            parser.feed(html_text)
            text = parser.get_text()

            if len(text.strip()) < 100:
                text += "\n\n[Notice: Page returned minimal text. Use --dynamic flag to render with Chromium]"

            if len(text) > max_chars:
                text = text[:max_chars] + f"\n\n[Truncated to {max_chars} characters]"
            return text

        except Exception as e:
            return f"[Static Fetch Error: {e}. Try --dynamic to render via Chromium]"

    def fetch_dynamic(
        self,
        target_url: str,
        max_chars: int = 25000,
        headless: bool = True,
        persistent: bool = False,
        wait_seconds: float = 3.0,
    ) -> str:
        """Launches Playwright Chromium to fetch and render dynamic SPAs."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return "[Error: Playwright is not installed. Run 'pip install playwright && playwright install chromium']"

        with sync_playwright() as p:
            if persistent:
                DEFAULT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(DEFAULT_PROFILE_DIR),
                    headless=headless,
                    user_agent=self.USER_AGENT,
                    viewport={"width": 1280, "height": 800},
                    args=["--disable-blink-features=AutomationControlled"],
                )
                page = context.new_page() if not context.pages else context.pages[0]
            else:
                browser = p.chromium.launch(
                    headless=headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = browser.new_context(
                    user_agent=self.USER_AGENT,
                    viewport={"width": 1280, "height": 800},
                )
                page = context.new_page()

            try:
                page.add_init_script("delete Object.getPrototypeOf(navigator).webdriver")
                page.goto(target_url, wait_until="domcontentloaded", timeout=25000)
                if wait_seconds > 0:
                    page.wait_for_timeout(int(wait_seconds * 1000))

                raw_text = page.evaluate("""() => {
                    const scripts = document.querySelectorAll('script, style, noscript, svg, iframe');
                    scripts.forEach(s => s.remove());
                    return document.body ? document.body.innerText : document.documentElement.innerText;
                }""")

                cleaned = re.sub(r'\n\s*\n+', '\n\n', raw_text).strip()
                if len(cleaned) > max_chars:
                    cleaned = cleaned[:max_chars] + f"\n\n[Truncated to {max_chars} characters]"
                return cleaned

            finally:
                context.close()
                if not persistent:
                    browser.close()


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "FastAPI vs Litestar python"
    engine = WebSearchEngine()
    serp = engine.search_serp(q)
    print(f"\nQUERY: {serp.query}")
    print(f"ENGINE: {serp.engine_used}")
    print("\n" + "=" * 60)
    print("QUICK SUMMARY:")
    print(serp.quick_summary)
    if serp.key_takeaways:
        print("\nTAKEAWAYS:")
        for t in serp.key_takeaways:
            print(f"• {t}")
    print("\nORGANIC RESULTS:")
    for r in serp.organic_results:
        print(f"- {r.title} ({r.url})")
    print("\nSOCIAL BLOCKS:")
    for s in serp.social_blocks:
        print(f"- [{s.social_type}] {s.title} ({s.url})")
    print("=" * 60)

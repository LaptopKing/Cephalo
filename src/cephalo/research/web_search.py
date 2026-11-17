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
import ipaddress
import json
import logging
import os
import re
import socket
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
BASE_DIR = Path(__file__).resolve().parents[3]
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
    from cephalo.research.serp_renderer import CephaloSERP, SearchItem, get_social_badge, render_serp_html
except ImportError:
    # Fallback if imported from a different cwd
    sys.path.insert(0, str(BASE_DIR))
    from cephalo.research.serp_renderer import CephaloSERP, SearchItem, get_social_badge, render_serp_html

# Scrapling Adaptive Stealth Scraping Integration (curl_cffi TLS impersonation + Patchright)
try:
    from scrapling.fetchers import Fetcher as ScraplingFetcher
    from scrapling.fetchers import StealthyFetcher as ScraplingStealthyFetcher
    HAS_SCRAPLING = True
    logging.getLogger("scrapling").setLevel(logging.WARNING)
except ImportError:
    HAS_SCRAPLING = False




from cephalo.research.web_community import (
    is_deep_discussion_url,
    select_community_targets,
)
from cephalo.research.web_fetcher import (
    HTMLTextExtractor,
    WebFetcher,
    validate_safe_url,
)
from cephalo.research.web_search_cache import DEFAULT_SERP_CACHE_DB, WebSearchCache
from cephalo.research.serp_summary import classify_social, synthesize_quick_summary

class SearchResult:
    """Legacy dataclass preserved for 100% backward compatibility."""
    title: str
    url: str
    snippet: str
    source: str = "web"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)



class WebSearchEngine(WebFetcher):
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
        self.serp_cache_db = DEFAULT_SERP_CACHE_DB
        self.cache = WebSearchCache(self.serp_cache_db)

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
        pass

    def _get_page_from_cache(self, url: str) -> Optional[str]:
        return self.cache._get_page_from_cache(url)

    def _save_page_to_cache(self, url: str, content: str, engine: str = "scrapling", ttl_hours: float = 24.0) -> None:
        self.cache._save_page_to_cache(url, content, engine, ttl_hours)

    def _get_from_cache(self, query: str) -> Optional[CephaloSERP]:
        return self.cache._get_from_cache(query)

    def _save_to_cache(self, serp: CephaloSERP, ttl_hours: float = 24.0) -> None:
        self.cache._save_to_cache(serp, ttl_hours)

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

        html_content = ""
        # 1. Prefer Scrapling Fetcher with TLS browser impersonation
        if HAS_SCRAPLING:
            try:
                res = ScraplingFetcher.get(url, timeout=10)
                if res.status in (200, 202) and res.html_content:
                    html_content = res.html_content
            except Exception as e:
                logger.debug(f"Scrapling DuckDuckGo fetch error: {e}")

        # 2. Fallback to standard urllib request
        if not html_content:
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
        return classify_social(domain)

    def _synthesize_quick_summary(
        self,
        query: str,
        items: List[SearchItem],
    ) -> Tuple[str, List[str], List[Dict[str, str]]]:
        return synthesize_quick_summary(query, items)

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


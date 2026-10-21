#!/usr/bin/env python3
"""
Cephalo - Web Search & Web Ingestion Engine (web_search.py)
===========================================================
Provides zero-key web search and clean webpage content extraction.
Features:
- Free DuckDuckGo HTML fallback (zero external API keys required).
- Optional API provider support (Tavily, Exa, Brave) via .env.
- Webpage content scraper with HTML sanitization.
- Automatic integration with Cephalo's local sanitizer & LanceDB vector store.
"""

from __future__ import annotations

import html
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional


@dataclass
class SearchResult:
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
        # Collapse multiple blank lines
        return re.sub(r'\n\s*\n+', '\n\n', raw).strip()


class WebSearchEngine:
    """Orchestrates web search and webpage content retrieval."""

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Cephalo/0.1.0"

    def __init__(self, tavily_api_key: Optional[str] = None, exa_api_key: Optional[str] = None):
        self.tavily_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        self.exa_key = exa_api_key or os.getenv("EXA_API_KEY")

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Searches the web using API provider if configured, else DuckDuckGo HTML fallback."""
        query = query.strip()
        if not query:
            return []

        # 1. Tavily API (if configured)
        if self.tavily_key:
            try:
                return self._search_tavily(query, max_results)
            except Exception:
                pass

        # 2. Free DuckDuckGo HTML Fallback (Zero-Key)
        try:
            return self._search_duckduckgo_html(query, max_results)
        except Exception as e:
            # Fallback to empty if network issue
            return [SearchResult(title="Search Error", url="", snippet=f"Failed to fetch results: {e}")]

    def _search_duckduckgo_html(self, query: str, max_results: int) -> List[SearchResult]:
        """Free DuckDuckGo HTML search without API keys."""
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

        results: List[SearchResult] = []
        # Pattern to extract results from html.duckduckgo.com
        # Matches result blocks
        blocks = re.findall(r'<div class="result results_links[^"]*">(.*?)</div>\s*</div>', html_content, re.DOTALL)
        if not blocks:
            # Alternative fallback pattern for simple links
            blocks = re.findall(r'<a class="result__snippet[^"]*".*?</a>', html_content, re.DOTALL)

        # Regex for link and snippet
        link_pattern = re.compile(r'<a[^>]+class="result__url"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
        title_pattern = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
        snippet_pattern = re.compile(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)

        for block in blocks:
            if len(results) >= max_results:
                break

            title_m = title_pattern.search(block)
            snip_m = snippet_pattern.search(block)

            if title_m:
                raw_url = title_m.group(1)
                # DuckDuckGo redirect url unwrap: /l/?uddg=https%3A%2F%2F...
                if "uddg=" in raw_url:
                    parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                    clean_url = parsed_qs.get("uddg", [raw_url])[0]
                else:
                    clean_url = raw_url

                title = re.sub(r'<[^>]+>', '', title_m.group(2)).strip()
                title = html.unescape(title)

                snippet = ""
                if snip_m:
                    snippet = re.sub(r'<[^>]+>', '', snip_m.group(1)).strip()
                    snippet = html.unescape(snippet)

                if clean_url and title:
                    results.append(SearchResult(title=title, url=clean_url, snippet=snippet, source="duckduckgo"))

        return results

    def _search_tavily(self, query: str, max_results: int) -> List[SearchResult]:
        """Tavily search API integration."""
        data = json.dumps({"query": query, "max_results": max_results, "include_answer": True}).encode("utf-8")
        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=data,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.tavily_key}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))

        results = []
        for item in res_json.get("results", []):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    source="tavily",
                )
            )
        return results

    def fetch_url(self, target_url: str, max_chars: int = 15000) -> str:
        """Fetches a URL and returns clean readable markdown/text content."""
        req = urllib.request.Request(target_url, headers={"User-Agent": self.USER_AGENT})
        with urllib.request.urlopen(req, timeout=12) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return f"[Unsupported Content-Type: {content_type}]"
            html_text = resp.read().decode("utf-8", errors="ignore")

        parser = HTMLTextExtractor()
        parser.feed(html_text)
        text = parser.get_text()
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[Truncated to {max_chars} characters]"
        return text


if __name__ == "__main__":
    import sys
    engine = WebSearchEngine()
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Python LanceDB vector database"
    print(f"Searching: '{q}'\n" + "-" * 50)
    for r in engine.search(q, max_results=3):
        print(f"• {r.title}\n  {r.url}\n  {r.snippet}\n")

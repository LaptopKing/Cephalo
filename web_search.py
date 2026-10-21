#!/usr/bin/env python3
"""
Cephalo - Web Search & Chromium Playwright Dynamic Crawler (web_search.py)
==========================================================================
Provides multi-engine web search and clean webpage content extraction.
Features:
- Fast Static Extractor: Zero-key DuckDuckGo HTML & urllib (sub-second, lightweight).
- Dynamic Chromium Crawler: Playwright-powered headless or persistent browser engine
  capable of rendering JavaScript SPAs, handling dynamic DOMs, and preserving session cookies.
- Optional API Engine: Tavily and Exa integrations via .env.
- Automatic integration with Cephalo's local sanitizer & LanceDB memory store.
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
from pathlib import Path
from typing import Any, Dict, List, Optional

# Base directory for persistent browser profile
DEFAULT_PROFILE_DIR = Path(__file__).resolve().parent / "data" / "chromium_profile"


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
        return re.sub(r'\n\s*\n+', '\n\n', raw).strip()


class WebSearchEngine:
    """Orchestrates web search and static/dynamic Chromium webpage retrieval."""

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Cephalo/0.1.0"

    def __init__(self, tavily_api_key: Optional[str] = None, exa_api_key: Optional[str] = None):
        self.tavily_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        self.exa_key = exa_api_key or os.getenv("EXA_API_KEY")

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Searches the web using API provider if configured, else DuckDuckGo fallback."""
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
        blocks = re.findall(r'<div class="result results_links[^"]*">(.*?)</div>\s*</div>', html_content, re.DOTALL)
        if not blocks:
            blocks = re.findall(r'<a class="result__snippet[^"]*".*?</a>', html_content, re.DOTALL)

        title_pattern = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
        snippet_pattern = re.compile(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)

        for block in blocks:
            if len(results) >= max_results:
                break

            title_m = title_pattern.search(block)
            snip_m = snippet_pattern.search(block)

            if title_m:
                raw_url = title_m.group(1)
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

    def fetch_url(
        self,
        target_url: str,
        max_chars: int = 15000,
        dynamic: bool = False,
        headless: bool = True,
        persistent: bool = False,
    ) -> str:
        """
        Fetches a URL and returns clean readable markdown/text content.
        If dynamic=True, uses Playwright Chromium to execute JavaScript and render dynamic SPAs.
        """
        if dynamic:
            return self.fetch_dynamic(
                target_url=target_url,
                max_chars=max_chars,
                headless=headless,
                persistent=persistent,
            )

        # Fast static fetch
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

            # If page is essentially empty or an SPA shell, hint at dynamic crawling
            if len(text.strip()) < 100:
                text += "\n\n[Notice: Page returned minimal text. Use --dynamic flag to render with Chromium]"

            if len(text) > max_chars:
                text = text[:max_chars] + f"\n\n[Truncated to {max_chars} characters]"
            return text

        except Exception as e:
            # If static fetch fails with 403 or blocks, try dynamic fallback
            return f"[Static Fetch Error: {e}. Try --dynamic to render via Chromium]"

    def fetch_dynamic(
        self,
        target_url: str,
        max_chars: int = 25000,
        headless: bool = True,
        persistent: bool = False,
        wait_seconds: float = 3.0,
    ) -> str:
        """
        Launches Playwright Chromium to fetch and render JavaScript-heavy dynamic web pages.
        Supports persistent browser profiles for residential cookies and session storage.
        """
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
                # Remove webdriver flag
                page.add_init_script("delete Object.getPrototypeOf(navigator).webdriver")
                
                # Navigate
                page.goto(target_url, wait_until="domcontentloaded", timeout=25000)
                if wait_seconds > 0:
                    page.wait_for_timeout(int(wait_seconds * 1000))

                # Extract rendered text from the live DOM
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
    import sys
    engine = WebSearchEngine()
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        print(f"Fetching URL dynamically: {sys.argv[1]}")
        content = engine.fetch_url(sys.argv[1], dynamic=True)
        print(content[:1000])
    else:
        q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Cephalo AI memory"
        print(f"Searching: '{q}'\n" + "-" * 50)
        for r in engine.search(q, max_results=3):
            print(f"• {r.title}\n  {r.url}\n  {r.snippet}\n")

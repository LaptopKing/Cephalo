"""
Web Fetcher, Dynamic Scrapling Runner, and YouTube Transcript Pipeline.
"""

from __future__ import annotations

import json
import logging
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import ipaddress
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional

from cephalo.config import DATA_DIR

logger = logging.getLogger("cephalo.research.web_fetcher")
DEFAULT_PROFILE_DIR = DATA_DIR / "browser_profile"
try:
    import scrapling  # noqa: F401
    HAS_SCRAPLING = True
except ImportError:
    HAS_SCRAPLING = False

def validate_safe_url(url: str, allow_internal: bool = False) -> None:
    """
    Validates that a URL uses http/https and does not resolve to loopback,
    private RFC-1918, link-local, cloud metadata, or internal intranet IPs (SSRF prevention).
    """
    if allow_internal:
        return

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(f"Unsafe URL scheme '{parsed.scheme}': only http and https are allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"Invalid URL: missing hostname in '{url}'.")

    host_lower = hostname.lower()
    if (
        host_lower in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "metadata.google.internal")
        or host_lower.endswith(".local")
        or host_lower.endswith(".internal")
    ):
        raise ValueError(f"SSRF Protection: Access to private/local host '{hostname}' is blocked.")

    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except Exception:
        return

    for addr in addr_infos:
        ip_str = addr[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
            if (
                ip.is_loopback
                or ip.is_private
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                raise ValueError(
                    f"SSRF Protection: Destination '{hostname}' resolves to restricted/internal IP {ip_str}."
                )
        except ValueError:
            raise
        except Exception:
            pass


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




class WebFetcher:
    """Sovereign fetcher with SSRF guards, Scrapling dynamic fallback, and YouTube transcript extraction."""

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

    CHALLENGE_KEYWORDS = [
        "just a moment...",
        "checking your browser",
        "cf-turnstile",
        "cloudflare turnstile",
        "attention required! | cloudflare",
        "access denied | www.",
        "please enable cookies",
        "security check to continue",
        "enable javascript and cookies",
        "human verification",
        "ray id:",
    ]

    def _is_challenge_page(self, text: str) -> bool:
        """Detects if scraped text is an anti-bot or Cloudflare challenge interstitial."""
        if not text:
            return True
        t_low = text.lower()
        if len(text.strip()) < 600 and any(kw in t_low for kw in self.CHALLENGE_KEYWORDS):
            return True
        return False

    def fetch_url(
        self,
        target_url: str,
        max_chars: int = 25000,
        dynamic: bool = False,
        headless: bool = True,
        persistent: bool = False,
        use_cache: bool = True,
    ) -> str:
        """
        Fetches a URL and returns clean readable markdown/text content using a tiered
        high-performance architecture:
        - Tier 0: SQLite URL content cache (instant sub-millisecond retrieval).
        - Tier 1: Scrapling Fetcher (curl_cffi TLS impersonation, HTTP/2 & HTTP/3, ~200ms).
        - Tier 2: Scrapling StealthyFetcher / Patchright (stealth Chromium, Turnstile solver).
        - Tier 3: Fallback to urllib.request + Playwright sync_api.
        """
        # 0. SSRF Security Validation
        try:
            validate_safe_url(target_url)
        except ValueError as ssrf_err:
            logger.warning(f"SSRF blocked attempt to fetch: {target_url} - {ssrf_err}")
            return f"[SSRF Blocked: {ssrf_err}]"

        if self.is_youtube_url(target_url):
            try:
                yt_res = self.fetch_youtube_transcript(target_url, max_chars=max_chars)
                return f"[YouTube Transcript - {yt_res['url']} ({yt_res['language']})]\n\n{yt_res['content']}"
            except Exception as e:
                logger.warning("YouTube transcript fetch failed (%s), falling back to standard fetch", e)

        # 0. Check SQLite page cache
        if use_cache:
            cached = self._get_page_from_cache(target_url)
            if cached:
                logger.info(f"Page cache hit for {target_url}")
                if len(cached) > max_chars:
                    return cached[:max_chars] + f"\n\n[Truncated to {max_chars} characters]"
                return cached

        # Explicit dynamic rendering requested
        if dynamic:
            return self.fetch_dynamic(
                target_url=target_url,
                max_chars=max_chars,
                headless=headless,
                persistent=persistent,
                use_cache=use_cache,
            )

        # 1. Tier 1: Scrapling Stealth HTTP Fetcher
        if HAS_SCRAPLING:
            try:
                res = ScraplingFetcher.get(
                    target_url,
                    timeout=12,
                    follow_redirects=True,
                )
                if res.status == 200:
                    try:
                        md_text = res.markdown().strip()
                    except Exception:
                        md_text = res.get_all_text().strip()

                    # Verify not blocked by Cloudflare interstitial and content is substantive
                    if md_text and not self._is_challenge_page(md_text) and len(md_text) >= 150:
                        if use_cache:
                            self._save_page_to_cache(target_url, md_text, engine="scrapling_fetcher")
                        if len(md_text) > max_chars:
                            return md_text[:max_chars] + f"\n\n[Truncated to {max_chars} characters]"
                        return md_text
                    else:
                        logger.info(f"Scrapling static fetch returned minimal or challenge content for {target_url}, escalating to dynamic stealth fetcher...")
                elif res.status in (403, 503):
                    logger.info(f"Scrapling static fetch returned HTTP {res.status} for {target_url}, escalating to dynamic stealth fetcher...")
            except Exception as e:
                logger.debug(f"Scrapling Fetcher error on {target_url}: {e}, escalating...")

            # Escalate automatically to Tier 2 (StealthyFetcher)
            return self.fetch_dynamic(
                target_url=target_url,
                max_chars=max_chars,
                headless=headless,
                persistent=persistent,
                use_cache=use_cache,
            )

        # 2. Tier 3: Legacy urllib.request fallback
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

            if use_cache and len(text.strip()) >= 100:
                self._save_page_to_cache(target_url, text, engine="urllib_legacy")

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
        wait_seconds: float = 2.0,
        use_cache: bool = True,
    ) -> str:
        """
        Executes dynamic JS rendering and anti-bot challenge solving.
        Prefers Scrapling StealthyFetcher (Patchright with Turnstile solver),
        falling back to Playwright sync_api.
        """
        # 0. SSRF Security Validation
        try:
            validate_safe_url(target_url)
        except ValueError as ssrf_err:
            logger.warning(f"SSRF blocked attempt to dynamically fetch: {target_url} - {ssrf_err}")
            return f"[SSRF Blocked: {ssrf_err}]"

        # 1. Tier 2: Scrapling StealthyFetcher (Patchright)
        if HAS_SCRAPLING:
            try:
                res = ScraplingStealthyFetcher.fetch(
                    target_url,
                    headless=headless,
                    solve_cloudflare=True,
                    timeout=25,
                )
                if res.status == 200:
                    try:
                        md_text = res.markdown().strip()
                    except Exception:
                        md_text = res.get_all_text().strip()

                    if md_text and not self._is_challenge_page(md_text):
                        if use_cache:
                            self._save_page_to_cache(target_url, md_text, engine="scrapling_stealthy")
                        if len(md_text) > max_chars:
                            return md_text[:max_chars] + f"\n\n[Truncated to {max_chars} characters]"
                        return md_text
            except Exception as stealth_err:
                logger.warning(f"Scrapling StealthyFetcher failed on {target_url} ({stealth_err}), falling back to Playwright Chromium...")

        # 2. Tier 3: Legacy Playwright Chromium fallback
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return "[Error: Neither Scrapling nor Playwright are available for dynamic fetching. Run 'pip install scrapling[all]']"

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
                if use_cache and len(cleaned) >= 100:
                    self._save_page_to_cache(target_url, cleaned, engine="playwright_legacy")
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

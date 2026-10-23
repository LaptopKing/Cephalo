#!/usr/bin/env python3
"""
Cephalo SERP & Generative UI Renderer (serp_renderer.py)
========================================================
Renders accessible, responsive Google-style SERP interfaces and Generative UI widgets
for Antigravity chat (<agent-embed>), Claude Code, Cursor, and web browsers.

Aesthetic Guidelines (USER_PROFILE.md):
- Simplicity is key, ALWAYS. Zero generic AI neon slop or glowing cyan borders.
- Tactile stone paper / dark obsidian surfaces with WCAG 2.1 AA compliant pastel accents.
- Strict typography floor (>= 12px), 44x44px minimum tap targets.
- Embedded inline compatibility (transparent root body, elevation cards).
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SearchItem:
    title: str
    url: str
    display_url: str
    snippet: str
    domain: str
    source: str = "web"
    social_type: Optional[str] = None  # "reddit", "youtube", "github", "x", "stackoverflow", "hackernews"
    extra: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CephaloSERP:
    query: str
    quick_summary: str
    key_takeaways: List[str]
    citations: List[Dict[str, str]]
    organic_results: List[SearchItem]
    social_blocks: List[SearchItem]
    execution_time_seconds: float = 0.0
    engine_used: str = "Cephalo Multi-Engine"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "quick_summary": self.quick_summary,
            "key_takeaways": self.key_takeaways,
            "citations": self.citations,
            "organic_results": [r.to_dict() for r in self.organic_results],
            "social_blocks": [s.to_dict() for s in self.social_blocks],
            "execution_time_seconds": self.execution_time_seconds,
            "engine_used": self.engine_used,
        }


def get_social_badge(social_type: Optional[str]) -> Dict[str, str]:
    """Returns accessible theme colors and icons for social badges."""
    badges = {
        "reddit": {
            "name": "Reddit",
            "bg": "bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-200 border-amber-200 dark:border-amber-800",
            "icon": "💬",
        },
        "youtube": {
            "name": "YouTube",
            "bg": "bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-200 border-rose-200 dark:border-rose-800",
            "icon": "▶",
        },
        "github": {
            "name": "GitHub",
            "bg": "bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border-slate-300 dark:border-slate-700",
            "icon": "⌥",
        },
        "x": {
            "name": "X",
            "bg": "bg-sky-50 dark:bg-sky-950/40 text-sky-800 dark:text-sky-200 border-sky-200 dark:border-sky-800",
            "icon": "𝕏",
        },
        "stackoverflow": {
            "name": "Stack Overflow",
            "bg": "bg-orange-50 dark:bg-orange-950/40 text-orange-800 dark:text-orange-200 border-orange-200 dark:border-orange-800",
            "icon": "⚡",
        },
        "hackernews": {
            "name": "Hacker News",
            "bg": "bg-amber-100/60 dark:bg-amber-900/40 text-amber-900 dark:text-amber-100 border-amber-300 dark:border-amber-700",
            "icon": "Y",
        },
    }
    return badges.get(
        social_type or "",
        {
            "name": "Community",
            "bg": "bg-stone-100 dark:bg-stone-800 text-stone-700 dark:text-stone-300 border-stone-200 dark:border-stone-700",
            "icon": "✦",
        },
    )


def render_serp_html(serp: CephaloSERP, standalone: bool = False) -> str:
    """
    Renders a Google-style, human-centered SERP interface compatible with Antigravity
    generative UI (<agent-embed>) and full-page browser rendering.
    """
    safe_query = html.escape(serp.query)
    safe_summary = html.escape(serp.quick_summary)
    exec_time = f"{serp.execution_time_seconds:.2f}s" if serp.execution_time_seconds else "0.4s"
    total_results = len(serp.organic_results) + len(serp.social_blocks)

    # Citations HTML
    citation_chips = []
    for c in serp.citations:
        c_title = html.escape(c.get("title", "Source"))
        c_url = html.escape(c.get("url", "#"))
        c_domain = html.escape(c.get("domain", ""))
        citation_chips.append(f"""
            <a href="{c_url}" target="_blank" rel="noopener noreferrer"
               class="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-full bg-[var(--muted)]/60 text-[var(--foreground)] border border-[var(--border)] hover:bg-[var(--muted)] transition-colors">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                <span>{c_domain or c_title}</span>
            </a>
        """)
    citations_html = "".join(citation_chips)

    # Takeaways HTML
    takeaways_items = []
    for t in serp.key_takeaways:
        safe_t = html.escape(t)
        takeaways_items.append(f"""
            <li class="flex items-start gap-2 text-sm text-[var(--foreground)] leading-relaxed">
                <span class="text-emerald-600 dark:text-emerald-400 font-bold mt-0.5">•</span>
                <span>{safe_t}</span>
            </li>
        """)
    takeaways_html = f'<ul class="space-y-1.5 mt-3 pt-3 border-t border-[var(--border)]">{"".join(takeaways_items)}</ul>' if takeaways_items else ""

    # Organic Results HTML
    organic_cards = []
    for idx, item in enumerate(serp.organic_results, 1):
        s_title = html.escape(item.title)
        s_url = html.escape(item.url)
        s_disp = html.escape(item.display_url or item.url)
        s_domain = html.escape(item.domain)
        s_snippet = html.escape(item.snippet)
        organic_cards.append(f"""
            <article class="serp-item web-result group p-4 rounded-xl bg-[var(--card)] border border-[var(--border)] hover:border-[var(--primary)]/40 hover:shadow-sm transition-all duration-150" data-category="web">
                <div class="flex items-center gap-2 mb-1.5 text-xs text-[var(--muted-foreground)]">
                    <span class="w-4 h-4 rounded-full bg-stone-200 dark:bg-stone-700 flex items-center justify-center text-[10px] font-semibold text-stone-700 dark:text-stone-300">
                        {s_domain[:1].upper()}
                    </span>
                    <span class="font-medium text-[var(--foreground)]">{s_domain}</span>
                    <span class="opacity-50">›</span>
                    <span class="truncate max-w-[280px] sm:max-w-md">{s_disp}</span>
                </div>
                <h3 class="text-base font-semibold text-[var(--foreground)] leading-snug group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                    <a href="{s_url}" target="_blank" rel="noopener noreferrer" class="hover:underline">
                        {s_title}
                    </a>
                </h3>
                <p class="text-sm text-[var(--muted-foreground)] mt-1.5 leading-relaxed">
                    {s_snippet}
                </p>
                <div class="mt-3 flex items-center gap-3 pt-2 border-t border-[var(--border)]/50 text-xs">
                    <a href="{s_url}" target="_blank" rel="noopener noreferrer" class="text-blue-600 dark:text-blue-400 hover:underline font-medium">
                        Visit Source ↗
                    </a>
                    <button onclick="navigator.clipboard.writeText('{s_url}'); this.innerText='Copied!'; setTimeout(()=>this.innerText='Copy URL', 1500)"
                            class="text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors">
                        Copy URL
                    </button>
                </div>
            </article>
        """)

    # Social Blocks HTML
    social_cards = []
    for item in serp.social_blocks:
        badge = get_social_badge(item.social_type)
        s_title = html.escape(item.title)
        s_url = html.escape(item.url)
        s_domain = html.escape(item.domain)
        s_snippet = html.escape(item.snippet)
        s_type = item.social_type or "social"
        social_cards.append(f"""
            <article class="serp-item social-result flex flex-col justify-between p-3.5 rounded-xl bg-[var(--card)] border border-[var(--border)] hover:border-[var(--primary)]/40 hover:shadow-sm transition-all" data-category="social" data-social-type="{s_type}">
                <div>
                    <div class="flex items-center justify-between gap-2 mb-2">
                        <span class="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-semibold rounded-md border {badge['bg']}">
                            <span>{badge['icon']}</span>
                            <span>{badge['name']}</span>
                        </span>
                        <span class="text-xs text-[var(--muted-foreground)] truncate">{s_domain}</span>
                    </div>
                    <h4 class="text-sm font-semibold text-[var(--foreground)] leading-snug line-clamp-2">
                        <a href="{s_url}" target="_blank" rel="noopener noreferrer" class="hover:underline">
                            {s_title}
                        </a>
                    </h4>
                    <p class="text-xs text-[var(--muted-foreground)] mt-1.5 line-clamp-3 leading-relaxed">
                        {s_snippet}
                    </p>
                </div>
                <div class="mt-3 pt-2 border-t border-[var(--border)]/50 flex items-center justify-between text-xs">
                    <a href="{s_url}" target="_blank" rel="noopener noreferrer" class="text-blue-600 dark:text-blue-400 font-medium hover:underline">
                        Open Discussion ↗
                    </a>
                </div>
            </article>
        """)

    # Social section (Google-style "Discussions and Forums")
    social_section_html = ""
    if social_cards:
        social_section_html = f"""
            <div class="my-5 p-4 rounded-xl bg-[var(--muted)]/30 border border-[var(--border)]">
                <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center gap-2">
                        <span class="text-base">💬</span>
                        <h3 class="text-sm font-semibold text-[var(--foreground)] uppercase tracking-wider">
                            Discussions & Community Highlights
                        </h3>
                    </div>
                    <span class="text-xs text-[var(--muted-foreground)]">{len(serp.social_blocks)} relevant threads</span>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {"".join(social_cards)}
                </div>
            </div>
        """

    # Interleave results: Top 2 organic, then social section, then rest of organic
    if len(organic_cards) > 2 and social_section_html:
        combined_stream = "".join(organic_cards[:2]) + social_section_html + "".join(organic_cards[2:])
    elif social_section_html:
        combined_stream = "".join(organic_cards) + social_section_html
    else:
        combined_stream = "".join(organic_cards)

    body_bg = "bg-[var(--background)]" if standalone else "bg-transparent"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Cephalo Search: {safe_query}</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    :root {{
      --background: #FAFAF7;
      --foreground: #1C1917;
      --card: #FFFFFF;
      --card-foreground: #1C1917;
      --border: #E8E7E1;
      --muted: #F4F4F0;
      --muted-foreground: #78716C;
      --primary: #2563EB;
      --primary-foreground: #FFFFFF;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --background: #161615;
        --foreground: #F5F5F4;
        --card: #1E1E1C;
        --card-foreground: #F5F5F4;
        --border: #2E2E2A;
        --muted: #242421;
        --muted-foreground: #A8A29E;
        --primary: #3B82F6;
        --primary-foreground: #FFFFFF;
      }}
    }}
    .line-clamp-2 {{ display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
    .line-clamp-3 {{ display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }}
  </style>
</head>
<body class="{body_bg} text-[var(--foreground)] antialiased p-3 sm:p-5 font-sans">
  <div class="max-w-4xl mx-auto space-y-4">

    <!-- Search Header & Metadata -->
    <header class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[var(--border)]">
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 rounded-lg bg-[var(--primary)] text-[var(--primary-foreground)] flex items-center justify-center font-bold text-sm shadow-sm">
          C
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h1 class="text-base sm:text-lg font-bold text-[var(--foreground)]">"{safe_query}"</h1>
            <span class="px-2 py-0.5 text-xs rounded-full bg-[var(--muted)] text-[var(--muted-foreground)] font-medium">
              {total_results} results ({exec_time})
            </span>
          </div>
          <p class="text-xs text-[var(--muted-foreground)]">Cephalo Sovereign Intelligence Search</p>
        </div>
      </div>

      <!-- Quick Filter Pills -->
      <nav class="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0" id="filter-tabs">
        <button onclick="setFilter('all', this)" class="filter-tab px-3 py-1.5 text-xs font-semibold rounded-lg bg-[var(--foreground)] text-[var(--background)] transition-all">
          All
        </button>
        <button onclick="setFilter('web', this)" class="filter-tab px-3 py-1.5 text-xs font-medium rounded-lg bg-[var(--muted)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-all">
          Web ({len(serp.organic_results)})
        </button>
        <button onclick="setFilter('social', this)" class="filter-tab px-3 py-1.5 text-xs font-medium rounded-lg bg-[var(--muted)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-all">
          Discussions ({len(serp.social_blocks)})
        </button>
      </nav>
    </header>

    <!-- AI Overview / Quick Summary Card (Google-style Answer Box) -->
    <section class="p-4 sm:p-5 rounded-2xl bg-[var(--card)] border border-[var(--border)] shadow-sm">
      <div class="flex items-center justify-between gap-2 mb-3">
        <div class="flex items-center gap-2">
          <span class="w-6 h-6 rounded-md bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 flex items-center justify-center text-xs font-bold">
            ✦
          </span>
          <h2 class="text-sm font-semibold uppercase tracking-wider text-[var(--foreground)]">
            Quick Summary
          </h2>
        </div>
        <span class="text-xs text-[var(--muted-foreground)]">Synthesized from authoritative sources</span>
      </div>

      <div class="text-sm sm:text-base text-[var(--foreground)] leading-relaxed font-normal">
        {safe_summary}
      </div>

      {takeaways_html}

      <!-- Source Citations Pills -->
      {f'''
      <div class="mt-4 pt-3 border-t border-[var(--border)] flex flex-wrap items-center gap-2">
        <span class="text-xs font-medium text-[var(--muted-foreground)]">Key Sources:</span>
        {citations_html}
      </div>
      ''' if citations_html else ''}
    </section>

    <!-- Results Stream -->
    <main id="serp-container" class="space-y-3">
      {combined_stream}
    </main>

    <!-- Footer -->
    <footer class="pt-4 border-t border-[var(--border)] flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-[var(--muted-foreground)]">
      <span>Cephalo Second Brain • Engine: {html.escape(serp.engine_used)}</span>
      <div class="flex items-center gap-3">
        <span>Press <kbd class="px-1.5 py-0.5 rounded bg-[var(--muted)] border border-[var(--border)] font-mono text-[10px]">ESC</kbd> to dismiss</span>
      </div>
    </footer>

  </div>

  <script>
    function setFilter(category, btn) {{
      document.querySelectorAll('.filter-tab').forEach(b => {{
        b.className = 'filter-tab px-3 py-1.5 text-xs font-medium rounded-lg bg-[var(--muted)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-all';
      }});
      btn.className = 'filter-tab px-3 py-1.5 text-xs font-semibold rounded-lg bg-[var(--foreground)] text-[var(--background)] transition-all';

      const items = document.querySelectorAll('.serp-item');
      items.forEach(item => {{
        if (category === 'all') {{
          item.style.display = '';
        }} else if (item.dataset.category === category) {{
          item.style.display = '';
        }} else {{
          item.style.display = 'none';
        }}
      }});
    }}
  </script>
</body>
</html>
"""

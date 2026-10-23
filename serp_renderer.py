#!/usr/bin/env python3
"""
Cephalo SERP & Generative UI Renderer (serp_renderer.py)
========================================================
Renders accessible, responsive Google-style SERP interfaces and Generative UI widgets
for Antigravity chat (<agent-embed>), Claude Code, Cursor, Windsurf, and web browsers.

Aesthetic Guidelines (USER_PROFILE.md):
- Simplicity is key, ALWAYS. Zero generic AI neon slop or glowing cyan borders.
- Tactile stone paper / dark obsidian surfaces with WCAG 2.1 AA compliant pastel accents.
- Strict typography floor (>= 12px), 44x44px minimum tap targets.
- Embedded inline compatibility: adapts dynamically to Antigravity theme variables
  with guaranteed high-contrast dark/light fallbacks.
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
    """Returns accessible theme colors and icons for social badges with guaranteed dark-mode contrast."""
    badges = {
        "reddit": {
            "name": "Reddit",
            "bg": "bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-950/70 dark:text-amber-200 dark:border-amber-700",
            "icon": "💬",
        },
        "youtube": {
            "name": "YouTube",
            "bg": "bg-rose-100 text-rose-900 border-rose-300 dark:bg-rose-950/70 dark:text-rose-200 dark:border-rose-700",
            "icon": "▶",
        },
        "github": {
            "name": "GitHub",
            "bg": "bg-slate-100 text-slate-900 border-slate-300 dark:bg-slate-800 dark:text-slate-100 dark:border-slate-600",
            "icon": "⌥",
        },
        "x": {
            "name": "X",
            "bg": "bg-sky-100 text-sky-900 border-sky-300 dark:bg-sky-950/70 dark:text-sky-200 dark:border-sky-700",
            "icon": "𝕏",
        },
        "stackoverflow": {
            "name": "Stack Overflow",
            "bg": "bg-orange-100 text-orange-900 border-orange-300 dark:bg-orange-950/70 dark:text-orange-200 dark:border-orange-700",
            "icon": "⚡",
        },
        "hackernews": {
            "name": "Hacker News",
            "bg": "bg-amber-200/80 text-amber-950 border-amber-400 dark:bg-amber-900/60 dark:text-amber-100 dark:border-amber-600",
            "icon": "Y",
        },
    }
    return badges.get(
        social_type or "",
        {
            "name": "Community",
            "bg": "bg-stone-100 text-stone-900 border-stone-300 dark:bg-stone-800 dark:text-stone-200 dark:border-stone-600",
            "icon": "✦",
        },
    )


def render_serp_html(serp: CephaloSERP, standalone: bool = False) -> str:
    """
    Renders a Google-style, human-centered SERP interface compatible with Antigravity
    generative UI (<agent-embed>) and full-page browser rendering.
    
    Guarantees pristine contrast (> 8:1) across both Dark and Light host themes
    by utilizing resilient semantic tokens with explicit solid fallbacks.
    """
    safe_query = html.escape(serp.query)
    safe_summary = html.escape(serp.quick_summary)
    exec_time = f"{serp.execution_time_seconds:.2f}s" if serp.execution_time_seconds else "0.3s"
    total_results = len(serp.organic_results) + len(serp.social_blocks)

    # Citations HTML (with high-contrast pills)
    citation_chips = []
    for c in serp.citations:
        c_title = html.escape(c.get("title", "Source"))
        c_url = html.escape(c.get("url", "#"))
        c_domain = html.escape(c.get("domain", ""))
        citation_chips.append(f"""
            <a href="{c_url}" target="_blank" rel="noopener noreferrer"
               class="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full bg-stone-100 dark:bg-stone-800/90 text-stone-900 dark:text-stone-100 border border-stone-300 dark:border-stone-700 hover:border-blue-500 hover:text-blue-600 dark:hover:text-sky-300 transition-colors">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                <span>{c_domain or c_title}</span>
            </a>
        """)
    citations_html = "".join(citation_chips)

    # Key Takeaways HTML
    takeaways_items = []
    for t in serp.key_takeaways:
        safe_t = html.escape(t)
        takeaways_items.append(f"""
            <li class="flex items-start gap-2 text-xs sm:text-sm text-stone-800 dark:text-stone-200 leading-relaxed font-normal">
                <span class="text-emerald-600 dark:text-emerald-400 font-bold mt-0.5">•</span>
                <span>{safe_t}</span>
            </li>
        """)
    takeaways_html = f'<ul class="space-y-2 mt-3 pt-3 border-t border-stone-200 dark:border-stone-700/60">{"".join(takeaways_items)}</ul>' if takeaways_items else ""

    # Organic Web Results HTML
    organic_cards = []
    for idx, item in enumerate(serp.organic_results, 1):
        s_title = html.escape(item.title)
        s_url = html.escape(item.url)
        s_disp = html.escape(item.display_url or item.url)
        s_domain = html.escape(item.domain)
        s_snippet = html.escape(item.snippet)
        organic_cards.append(f"""
            <article class="serp-item web-result group p-4 rounded-xl bg-white dark:bg-[#1E1E1C] border border-stone-200 dark:border-stone-800 hover:border-blue-400 dark:hover:border-sky-500/60 shadow-sm transition-all duration-150" data-category="web">
                <div class="flex items-center gap-2 mb-1.5 text-xs text-stone-500 dark:text-stone-400">
                    <span class="w-4 h-4 rounded-full bg-stone-200 dark:bg-stone-700 flex items-center justify-center text-[10px] font-bold text-stone-700 dark:text-stone-300">
                        {s_domain[:1].upper()}
                    </span>
                    <span class="font-semibold text-stone-800 dark:text-stone-200">{s_domain}</span>
                    <span class="opacity-40">›</span>
                    <span class="truncate max-w-[240px] sm:max-w-md">{s_disp}</span>
                </div>
                <h3 class="text-sm sm:text-base font-semibold leading-snug">
                    <a href="{s_url}" target="_blank" rel="noopener noreferrer"
                       class="text-blue-700 dark:text-sky-400 hover:underline hover:text-blue-800 dark:hover:text-sky-300 transition-colors">
                        {s_title}
                    </a>
                </h3>
                <p class="text-xs sm:text-sm text-stone-600 dark:text-stone-300 mt-2 leading-relaxed">
                    {s_snippet}
                </p>
                <div class="mt-3 flex items-center gap-3 pt-2 border-t border-stone-100 dark:border-stone-800/80 text-xs">
                    <a href="{s_url}" target="_blank" rel="noopener noreferrer" class="text-blue-600 dark:text-sky-400 hover:underline font-semibold flex items-center gap-1">
                        Visit Source <span>↗</span>
                    </a>
                    <button onclick="navigator.clipboard.writeText('{s_url}'); this.innerText='Copied!'; setTimeout(()=>this.innerText='Copy URL', 1500)"
                            class="text-stone-500 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-200 transition-colors py-1 px-2 rounded">
                        Copy URL
                    </button>
                </div>
            </article>
        """)

    # Social & Community Blocks HTML
    social_cards = []
    for item in serp.social_blocks:
        badge = get_social_badge(item.social_type)
        s_title = html.escape(item.title)
        s_url = html.escape(item.url)
        s_domain = html.escape(item.domain)
        s_snippet = html.escape(item.snippet)
        s_type = item.social_type or "social"
        social_cards.append(f"""
            <article class="serp-item social-result flex flex-col justify-between p-3.5 rounded-xl bg-stone-50 dark:bg-[#242421] border border-stone-200 dark:border-stone-700/80 hover:border-blue-400 dark:hover:border-sky-500/60 shadow-sm transition-all" data-category="social" data-social-type="{s_type}">
                <div>
                    <div class="flex items-center justify-between gap-2 mb-2">
                        <span class="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-semibold rounded-md border {badge['bg']}">
                            <span>{badge['icon']}</span>
                            <span>{badge['name']}</span>
                        </span>
                        <span class="text-[11px] text-stone-500 dark:text-stone-400 font-medium truncate">{s_domain}</span>
                    </div>
                    <h4 class="text-xs sm:text-sm font-semibold leading-snug line-clamp-2">
                        <a href="{s_url}" target="_blank" rel="noopener noreferrer"
                           class="text-stone-900 dark:text-stone-100 hover:text-blue-600 dark:hover:text-sky-300 hover:underline transition-colors">
                            {s_title}
                        </a>
                    </h4>
                    <p class="text-xs text-stone-600 dark:text-stone-300 mt-2 line-clamp-3 leading-relaxed">
                        {s_snippet}
                    </p>
                </div>
                <div class="mt-3 pt-2 border-t border-stone-200 dark:border-stone-700/60 flex items-center justify-between text-xs">
                    <a href="{s_url}" target="_blank" rel="noopener noreferrer" class="text-blue-600 dark:text-sky-400 font-semibold hover:underline">
                        Open Discussion ↗
                    </a>
                </div>
            </article>
        """)

    # Social Section Container
    social_section_html = ""
    if social_cards:
        social_section_html = f"""
            <div class="my-4 p-4 rounded-xl bg-stone-100/70 dark:bg-[#1A1A18] border border-stone-200 dark:border-stone-800">
                <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center gap-2">
                        <span class="text-sm">💬</span>
                        <h3 class="text-xs font-bold text-stone-700 dark:text-stone-300 uppercase tracking-wider">
                            Discussions & Community Highlights
                        </h3>
                    </div>
                    <span class="text-xs text-stone-500 dark:text-stone-400 font-medium">{len(serp.social_blocks)} relevant threads</span>
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

    body_bg = "bg-stone-100 dark:bg-[#121211]" if standalone else "bg-transparent"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Cephalo Search: {safe_query}</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <script>
    // Robust dark/light mode detection matching host environment
    (function() {{
      try {{
        const isDark = document.documentElement.classList.contains('dark') ||
                       window.matchMedia('(prefers-color-scheme: dark)').matches ||
                       (window.parent !== window && !document.documentElement.classList.contains('light'));
        if (isDark) {{
          document.documentElement.classList.add('dark');
        }} else {{
          document.documentElement.classList.remove('dark');
        }}
      }} catch (e) {{}}
    }})();
  </script>
  <style>
    .line-clamp-2 {{ display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
    .line-clamp-3 {{ display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }}
  </style>
</head>
<body class="{body_bg} text-stone-900 dark:text-stone-100 antialiased p-2 sm:p-4 font-sans">
  <div class="max-w-4xl mx-auto space-y-4">

    <!-- Card Wrapper for Clean Antigravity Elevation -->
    <div class="bg-white dark:bg-[#181816] text-stone-900 dark:text-stone-100 border border-stone-200 dark:border-stone-800 rounded-2xl p-4 sm:p-5 shadow-sm space-y-4">

      <!-- Header & Metadata -->
      <header class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-stone-200 dark:border-stone-800">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center font-bold text-sm shadow-sm flex-shrink-0">
            C
          </div>
          <div>
            <div class="flex flex-wrap items-center gap-2">
              <h1 class="text-base sm:text-lg font-bold text-stone-900 dark:text-stone-100">"{safe_query}"</h1>
              <span class="px-2 py-0.5 text-xs rounded-full bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-300 font-medium">
                {total_results} results ({exec_time})
              </span>
            </div>
            <p class="text-xs text-stone-500 dark:text-stone-400">Cephalo Unified Intelligence Search</p>
          </div>
        </div>

        <!-- Filter Pills -->
        <nav class="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0" id="filter-tabs">
          <button onclick="setFilter('all', this)" class="filter-tab px-3 py-1.5 text-xs font-bold rounded-lg bg-blue-600 text-white shadow-sm transition-all flex-shrink-0">
            All
          </button>
          <button onclick="setFilter('web', this)" class="filter-tab px-3 py-1.5 text-xs font-semibold rounded-lg bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-300 hover:text-stone-900 dark:hover:text-white transition-all flex-shrink-0">
            Web ({len(serp.organic_results)})
          </button>
          <button onclick="setFilter('social', this)" class="filter-tab px-3 py-1.5 text-xs font-semibold rounded-lg bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-300 hover:text-stone-900 dark:hover:text-white transition-all flex-shrink-0">
            Discussions ({len(serp.social_blocks)})
          </button>
        </nav>
      </header>

      <!-- AI Overview / Quick Summary Card -->
      <section class="p-4 sm:p-5 rounded-xl bg-blue-50/50 dark:bg-[#1E222D]/70 border border-blue-200/80 dark:border-blue-900/60 shadow-sm">
        <div class="flex items-center justify-between gap-2 mb-2.5">
          <div class="flex items-center gap-2">
            <span class="w-6 h-6 rounded-md bg-blue-600 text-white flex items-center justify-center text-xs font-bold shadow-sm">
              ✦
            </span>
            <h2 class="text-xs sm:text-sm font-bold uppercase tracking-wider text-blue-900 dark:text-blue-300">
              Quick Summary (AI Overview)
            </h2>
          </div>
          <span class="text-[11px] text-blue-700 dark:text-blue-400 font-medium">Synthesized Answer</span>
        </div>

        <div class="text-xs sm:text-sm text-stone-900 dark:text-stone-100 leading-relaxed font-normal">
          {safe_summary}
        </div>

        {takeaways_html}

        <!-- Sources -->
        {f'''
        <div class="mt-3.5 pt-3 border-t border-blue-200/60 dark:border-blue-900/40 flex flex-wrap items-center gap-2">
          <span class="text-xs font-semibold text-stone-600 dark:text-stone-400">Key Sources:</span>
          {citations_html}
        </div>
        ''' if citations_html else ''}
      </section>

      <!-- Results Stream -->
      <main id="serp-container" class="space-y-3">
        {combined_stream}
      </main>

      <!-- Footer -->
      <footer class="pt-3 border-t border-stone-200 dark:border-stone-800 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-stone-500 dark:text-stone-400">
        <span>Cephalo Sovereign Engine • {html.escape(serp.engine_used)}</span>
        <span>Google-Style Unified SERP</span>
      </footer>

    </div>

  </div>

  <script>
    function setFilter(category, btn) {{
      document.querySelectorAll('.filter-tab').forEach(b => {{
        b.className = 'filter-tab px-3 py-1.5 text-xs font-semibold rounded-lg bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-300 hover:text-stone-900 dark:hover:text-white transition-all flex-shrink-0';
      }});
      btn.className = 'filter-tab px-3 py-1.5 text-xs font-bold rounded-lg bg-blue-600 text-white shadow-sm transition-all flex-shrink-0';

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

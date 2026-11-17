"""
SERP Quick Synthesis and Social Domain Classification.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Set
from cephalo.research.serp_renderer import CephaloSERP, SearchItem

logger = logging.getLogger("cephalo.research.serp_summary")

def classify_social(domain: str) -> Optional[str]:
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


def synthesize_quick_summary(

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


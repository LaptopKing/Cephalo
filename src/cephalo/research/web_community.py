"""
Community Discussion Targets and Deep-Web Forum Heuristics.
"""

import re
from typing import List

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

"""
Cephalo Safeguards & Blacklist Manager (safeguards.py)
======================================================
Cross-platform configurable privacy filter and security gatekeeper.
Prevents accidental ingestion or indexing of password managers, private
browsing sessions, financial windows, and sensitive desktop processes.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cephalo.config import DATA_DIR

logger = logging.getLogger("cephalo.safeguards")

SAFEGUARDS_FILE = DATA_DIR / "safeguards.json"

DEFAULT_SAFEGUARDS: Dict[str, Any] = {
    "enabled": True,
    "blacklisted_processes": [
        "1password",
        "bitwarden",
        "keepass",
        "keepassxc",
        "vaultwarden",
        "lastpass",
        "authenticator",
        "authy",
    ],
    "blacklisted_window_titles": [
        r"(?i)incognito",
        r"(?i)private browsing",
        r"(?i)inprivate",
        r"(?i)password",
        r"(?i)credential",
        r"(?i)payment|checkout|credit card|cvv|security code",
    ],
    "blacklisted_domains": [
        "*.bank*",
        "paypal.com",
        "stripe.com/dashboard",
        "revolut.com",
        "wise.com",
    ],
    "pause_on_fullscreen_video": True,
}


def load_safeguards_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Loads safeguards configuration from disk, writing defaults if not present."""
    target_path = path or SAFEGUARDS_FILE
    if not target_path.exists():
        save_safeguards_config(DEFAULT_SAFEGUARDS, target_path)
        return dict(DEFAULT_SAFEGUARDS)

    try:
        data = json.loads(target_path.read_text(encoding="utf-8"))
        # Merge with defaults in case new keys were added
        merged = dict(DEFAULT_SAFEGUARDS)
        merged.update(data)
        return merged
    except Exception as e:
        logger.warning("Failed to parse %s, falling back to defaults: %s", target_path, e)
        return dict(DEFAULT_SAFEGUARDS)


def save_safeguards_config(config: Dict[str, Any], path: Optional[Path] = None) -> None:
    """Atomically saves safeguards configuration to disk."""
    target_path = path or SAFEGUARDS_FILE
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = target_path.with_suffix(".tmp")
    temp_file.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_file.replace(target_path)


def is_shielded(
    window_title: str = "",
    process_name: str = "",
    domain: str = "",
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """
    Evaluates whether an active window, process, or URL domain is blacklisted.
    Returns (True, reason) if shielded, or (False, "") if allowed.
    """
    cfg = config or load_safeguards_config()
    if not cfg.get("enabled", True):
        return False, ""

    # 1. Process Name Check
    proc_clean = process_name.strip().lower()
    if proc_clean:
        # Strip path or .exe if present
        proc_base = Path(proc_clean).stem.lower()
        for bl_proc in cfg.get("blacklisted_processes", []):
            bl_stem = Path(bl_proc).stem.lower()
            if bl_stem in proc_base or bl_stem == proc_clean:
                return True, f"Blacklisted process: {process_name}"

    # 2. Window Title Regex Check
    title_clean = window_title.strip()
    if title_clean:
        for pattern in cfg.get("blacklisted_window_titles", []):
            try:
                if re.search(pattern, title_clean):
                    return True, f"Blacklisted window title pattern: {pattern}"
            except re.error as e:
                logger.debug("Invalid regex pattern '%s': %s", pattern, e)

    # 3. Domain Check
    dom_clean = domain.strip().lower()
    if dom_clean:
        for bl_dom in cfg.get("blacklisted_domains", []):
            bl_regex = "^" + re.escape(bl_dom.lower()).replace(r"\*", ".*") + "$"
            if re.match(bl_regex, dom_clean):
                return True, f"Blacklisted domain: {domain}"

    return False, ""


def add_blacklisted_process(name: str, path: Optional[Path] = None) -> Dict[str, Any]:
    """Adds a process name to the blacklist."""
    cfg = load_safeguards_config(path)
    stem = Path(name.strip().lower()).stem
    if stem and stem not in cfg["blacklisted_processes"]:
        cfg["blacklisted_processes"].append(stem)
        save_safeguards_config(cfg, path)
    return cfg


def add_blacklisted_title(pattern: str, path: Optional[Path] = None) -> Dict[str, Any]:
    """Adds a regex pattern to window title blacklist."""
    cfg = load_safeguards_config(path)
    pattern_clean = pattern.strip()
    if pattern_clean and pattern_clean not in cfg["blacklisted_window_titles"]:
        cfg["blacklisted_window_titles"].append(pattern_clean)
        save_safeguards_config(cfg, path)
    return cfg


def remove_blacklisted_process(name: str, path: Optional[Path] = None) -> bool:
    """Removes a process name from the blacklist."""
    cfg = load_safeguards_config(path)
    stem = Path(name.strip().lower()).stem
    if stem in cfg["blacklisted_processes"]:
        cfg["blacklisted_processes"].remove(stem)
        save_safeguards_config(cfg, path)
        return True
    return False


def remove_blacklisted_title(pattern: str, path: Optional[Path] = None) -> bool:
    """Removes a window title pattern from the blacklist."""
    cfg = load_safeguards_config(path)
    pattern_clean = pattern.strip()
    if pattern_clean in cfg["blacklisted_window_titles"]:
        cfg["blacklisted_window_titles"].remove(pattern_clean)
        save_safeguards_config(cfg, path)
        return True
    return False

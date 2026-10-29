#!/usr/bin/env python3
"""
Cephalo - Cross-Platform Silent Clipboard Utilities (clipboard_utils.py)
========================================================================
Provides zero-dependency, silent clipboard reading and writing across Windows,
macOS, and Linux.

Non-Negotiable Invariants:
- Strictly enforces CREATE_NO_WINDOW (0x08000000) on Windows to prevent flashing console popups.
- Safe fallbacks: handles empty clipboards, encoding issues, and headless environments.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Optional

logger = logging.getLogger("cephalo.clipboard")

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def get_clipboard_text() -> str:
    """Reads and returns the current system clipboard text."""
    try:
        if sys.platform == "win32":
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=CREATE_NO_WINDOW,
                timeout=5,
            )
            if proc.returncode == 0:
                return proc.stdout.strip()
        elif sys.platform == "darwin":
            proc = subprocess.run(
                ["pbpaste"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=5,
            )
            if proc.returncode == 0:
                return proc.stdout.strip()
        else:
            # Linux: try wl-paste (Wayland), then xclip, then xsel
            for cmd in [["wl-paste"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]]:
                try:
                    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=5)
                    if proc.returncode == 0:
                        return proc.stdout.strip()
                except FileNotFoundError:
                    continue
    except Exception as e:
        logger.warning("Failed to read clipboard: %s", e)

    # Optional fallback to pyperclip
    try:
        import pyperclip
        return pyperclip.paste() or ""
    except Exception:
        pass

    return ""


def set_clipboard_text(text: str) -> bool:
    """Copies text to the system clipboard silently."""
    if not text:
        return False

    try:
        if sys.platform == "win32":
            # Built-in clip.exe accepts text via stdin
            proc = subprocess.run(
                ["clip.exe"],
                input=text,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=CREATE_NO_WINDOW,
                timeout=5,
            )
            return proc.returncode == 0
        elif sys.platform == "darwin":
            proc = subprocess.run(
                ["pbcopy"],
                input=text,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=5,
            )
            return proc.returncode == 0
        else:
            # Linux: try wl-copy, then xclip, then xsel
            for cmd in [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
                try:
                    proc = subprocess.run(cmd, input=text, text=True, encoding="utf-8", errors="ignore", timeout=5)
                    if proc.returncode == 0:
                        return True
                except FileNotFoundError:
                    continue
    except Exception as e:
        logger.warning("Failed to write to clipboard: %s", e)

    # Optional fallback to pyperclip
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        pass

    return False

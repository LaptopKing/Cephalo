"""
Cephalo Central Configuration & Root Paths
==========================================
Provides authoritative directory and file anchors regardless of execution working directory.
"""

from __future__ import annotations

from pathlib import Path

# Package and Root Anchors
PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
ROOT_DIR = SRC_DIR.parent

DATA_DIR = ROOT_DIR / "data"
PROMPTS_FILE = DATA_DIR / "prompts.jsonl"
DEFAULT_LANCEDB_DIR = DATA_DIR / "lancedb"
PROFILE_FILE = ROOT_DIR / "USER_PROFILE.md"
SPECIALTIES_DIR = ROOT_DIR / "specialties"
DOCS_DIR = ROOT_DIR / "docs"
PATTERNS_DIR = ROOT_DIR / "patterns"

# Ensure essential directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_LANCEDB_DIR.mkdir(parents=True, exist_ok=True)
SPECIALTIES_DIR.mkdir(parents=True, exist_ok=True)

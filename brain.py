#!/usr/bin/env python3
"""
Cephalo - Root Entrypoint & Backward-Compatible Shim (brain.py)
===============================================================
Universal CLI entrypoint and package bridge. Dispatches commands
to `src/cephalo/cli.py` while preserving backward compatibility.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"

for p in (str(BASE_DIR), str(SRC_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Re-export all CLI handlers and main from cephalo.cli
from cephalo.cli import *
from cephalo.cli import main

if __name__ == "__main__":
    main()

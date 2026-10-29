"""
Cephalo - Sovereign Local Memory & Cognitive Coprocessor
========================================================
Clean, modular package architecture.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure ROOT_DIR and src/ are in sys.path
PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
ROOT_DIR = SRC_DIR.parent

for p in (str(ROOT_DIR), str(SRC_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

__version__ = "2.1.0"

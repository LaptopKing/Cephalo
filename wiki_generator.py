#!/usr/bin/env python3
"""Backward-compatibility shim for cephalo.research.wiki_generator."""
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import cephalo.research.wiki_generator as wiki_generator
from cephalo.research.wiki_generator import *

if __name__ == "__main__":
    if hasattr(wiki_generator, "main"):
        wiki_generator.main()

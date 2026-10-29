#!/usr/bin/env python3
"""Backward-compatibility shim for cephalo.learning.auto_harvest."""
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import cephalo.learning.auto_harvest as auto_harvest
from cephalo.learning.auto_harvest import *

if __name__ == "__main__":
    if hasattr(auto_harvest, "main"):
        auto_harvest.main()

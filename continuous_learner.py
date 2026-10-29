#!/usr/bin/env python3
"""Backward-compatibility shim for cephalo.learning.continuous_learner."""
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import cephalo.learning.continuous_learner as continuous_learner
from cephalo.learning.continuous_learner import *

if __name__ == "__main__":
    if hasattr(continuous_learner, "main"):
        continuous_learner.main()

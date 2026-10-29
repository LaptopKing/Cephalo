#!/usr/bin/env python3
"""Backward-compatibility shim for cephalo.core.patterns_manager."""
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import cephalo.core.patterns_manager as patterns_manager
from cephalo.core.patterns_manager import *

#!/usr/bin/env python3
"""Backward-compatibility shim for cephalo.learning.specialties_manager."""
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import cephalo.learning.specialties_manager as specialties_manager
from cephalo.learning.specialties_manager import *

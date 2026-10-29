#!/usr/bin/env python3
"""Backward-compatibility shim for cephalo.utils.clipboard_utils."""
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import cephalo.utils.clipboard_utils as clipboard_utils
from cephalo.utils.clipboard_utils import *

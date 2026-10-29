#!/usr/bin/env python3
"""Backward-compatibility shim for cephalo.services.cephalo_daemon."""
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import cephalo.services.cephalo_daemon as cephalo_daemon
from cephalo.services.cephalo_daemon import *

if __name__ == "__main__":
    if hasattr(cephalo_daemon, "main"):
        cephalo_daemon.main()

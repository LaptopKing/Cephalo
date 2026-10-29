#!/usr/bin/env python3
"""Backward-compatibility shim for cephalo.services.webhook_server."""
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import cephalo.services.webhook_server as webhook_server
from cephalo.services.webhook_server import *

if __name__ == "__main__":
    if hasattr(webhook_server, "main"):
        webhook_server.main()

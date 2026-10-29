#!/usr/bin/env python3
"""Backward-compatibility shim for cephalo.services.mcp_server."""
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import cephalo.services.mcp_server as mcp_server
from cephalo.services.mcp_server import *

if __name__ == "__main__":
    if hasattr(mcp_server, "main"):
        mcp_server.main()

#!/usr/bin/env python3
"""Backward-compatibility shim for cephalo.core.embedding_pipeline."""
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import cephalo.core.embedding_pipeline as embedding_pipeline
from cephalo.core.embedding_pipeline import *

if __name__ == "__main__":
    if hasattr(embedding_pipeline, "main"):
        embedding_pipeline.main()

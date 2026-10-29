import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

for p in (str(ROOT_DIR), str(SRC_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

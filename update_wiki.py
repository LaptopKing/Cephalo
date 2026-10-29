import re
from pathlib import Path

path = Path(r"C:\Users\strider-desktop\.gemini\antigravity\scratch\second-brain\wiki_generator.py")
content = path.read_text(encoding="utf-8")

# 1. Update imports
old_imports = """from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
DOCS_WIKI_DIR = BASE_DIR / "docs" / "wiki"

logger = logging.getLogger("cephalo.wiki")"""

new_imports = """import datetime
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
DOCS_WIKI_DIR = BASE_DIR / "docs" / "wiki"
DATA_DIR = BASE_DIR / "data"
PROMPTS_FILE = DATA_DIR / "prompts.jsonl"
DEFAULT_LANCEDB_DIR = DATA_DIR / "lancedb"

logger = logging.getLogger("cephalo.wiki")"""

content = content.replace(old_imports.replace("\n", "\r\n"), new_imports.replace("\n", "\r\n"))
if new_imports not in content and new_imports.replace("\n", "\r\n") not in content:
    # Try normalizing \r\n
    content = content.replace("\r\n", "\n").replace(old_imports, new_imports)

# 2. Add _write_timeline_dashboard call in generate_all
if "self._write_timeline_dashboard()" not in content:
    content = content.replace(
        "gen_files.append(self._write_index(modules))",
        "gen_files.append(self._write_index(modules))\n        gen_files.append(self._write_timeline_dashboard())"
    )

print("Imports & generate_all updated:", "DEFAULT_LANCEDB_DIR" in content, "_write_timeline_dashboard" in content)
path.write_text(content, encoding="utf-8")

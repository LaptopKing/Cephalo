"""
DeepWiki Embedded HTTP Dashboard Server and Timeline Record Handlers.
"""

import datetime
import json
import logging
import mimetypes
import os
import sys
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[3]
DOCS_WIKI_DIR = ROOT_DIR / "docs" / "wiki"
DATA_DIR = ROOT_DIR / "data"
PROMPTS_FILE = DATA_DIR / "prompts.jsonl"

logger = logging.getLogger("cephalo.research.wiki_server")

def get_timeline_records(limit: int = 500) -> List[Dict[str, Any]]:
    """Reads memories from prompts.jsonl and frame_index.jsonl in reverse-chronological order."""
    from cephalo.core.embedding_pipeline import extract_tags

    records = []
    if PROMPTS_FILE.exists():
        with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if "tags" not in rec or not rec["tags"]:
                        rec["tags"] = extract_tags(rec.get("content", ""))
                    rec.setdefault("is_deprecated", False)
                    rec.setdefault("supersedes", "")
                    rec.setdefault("relates_to", [])
                    records.append(rec)
                except Exception:
                    pass

    # Blend recent screen events if present
    frames_file = DATA_DIR / "frames" / "frame_index.jsonl"
    if frames_file.exists():
        with open(frames_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    frec = json.loads(line)
                    ts = frec.get("timestamp", "")
                    title = frec.get("window_title", "Screen Snapshot")
                    proc = frec.get("process_name", "")
                    content = f"📸 Screen Activity: {title}" + (f" ({proc})" if proc else "")
                    if frec.get("ocr_text"):
                        content += f"\n\nOCR Text: {frec['ocr_text'][:200]}"
                    records.append({
                        "id": frec.get("id"),
                        "timestamp": ts,
                        "category": "screen_capture",
                        "content": content,
                        "tags": ["#screen", f"#{proc.replace('.exe','').lower()}"] if proc else ["#screen"],
                        "image_path": frec.get("path"),
                        "is_deprecated": False,
                        "supersedes": "",
                        "relates_to": [],
                    })
                except Exception:
                    pass

    records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return records[:limit]


def get_heatmap_data() -> Dict[str, Any]:
    """Computes daily ingestion counts over the past 365 days."""
    if not PROMPTS_FILE.exists():
        return {"days": {}, "total": 0, "active_days": 0, "current_streak": 0}

    days_count: Dict[str, int] = {}
    total = 0

    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                ts = data.get("timestamp", "")
                if ts:
                    day_key = ts[:10]
                    days_count[day_key] = days_count.get(day_key, 0) + 1
                    total += 1
            except Exception:
                pass

    today = datetime.date.today()
    streak = 0
    cur_day = today
    while True:
        k = cur_day.isoformat()
        if days_count.get(k, 0) > 0:
            streak += 1
            cur_day -= datetime.timedelta(days=1)
        else:
            break

    return {
        "days": days_count,
        "total": total,
        "active_days": len(days_count),
        "current_streak": streak,
    }


class DeepWikiServerHandler(SimpleHTTPRequestHandler):
    """Dynamic HTTP handler for DeepWiki documentation, timeline feed, and quick capture."""

    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=str(DOCS_WIKI_DIR), **kwargs)

    def _is_allowed_origin(self, origin: str) -> bool:
        """Validates that origin is strictly local or an authorized browser extension."""
        if not origin:
            return True
        pattern = r'^https?://(?:localhost|127\.0\.0\.1)(?::\d+)?$'
        if re.match(pattern, origin):
            return True
        if origin.startswith("moz-extension://") or origin.startswith("chrome-extension://"):
            return True
        return False

    def _send_cors(self):
        origin = self.headers.get("Origin", "")
        # Strictly restrict CORS to localhost and local extensions to prevent unauthorized memory exfiltration
        if self._is_allowed_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin or "http://127.0.0.1")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            index_file = DOCS_WIKI_DIR / "index.html"
            if not index_file.exists():
                wg = WikiGenerator()
                wg._write_timeline_dashboard()
            return super().do_GET()

        if path == "/api/timeline":
            records = get_timeline_records()
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(records, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/heatmap":
            hdata = get_heatmap_data()
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(hdata, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/digest":
            qs = urllib.parse.parse_qs(parsed.query)
            date_param = qs.get("date", [None])[0]
            from cephalo.core.daily_digest import DailyDigestGenerator
            gen = DailyDigestGenerator()
            digest_data = gen.generate_digest(date_param)
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(digest_data, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/frames":
            qs = urllib.parse.parse_qs(parsed.query)
            date_param = qs.get("date", [None])[0] or datetime.date.today().isoformat()
            frames = []
            index_file = DATA_DIR / "frames" / "frame_index.jsonl"
            if index_file.exists():
                try:
                    with open(index_file, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    rec = json.loads(line)
                                    if rec.get("date") == date_param:
                                        frames.append(rec)
                                except Exception:
                                    pass
                except Exception:
                    pass
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(frames, ensure_ascii=False).encode("utf-8"))
            return

        if path.startswith("/data/frames/") or path.startswith("/frames/"):
            rel_path = path.lstrip("/")
            if rel_path.startswith("data/"):
                img_path = (ROOT_DIR / rel_path).resolve()
            else:
                img_path = (DATA_DIR / rel_path).resolve()

            allowed_dirs = [
                (DATA_DIR / "frames").resolve(),
                (ROOT_DIR / "data" / "frames").resolve(),
            ]
            if not any(img_path.is_relative_to(d) for d in allowed_dirs):
                self.send_response(403)
                self._send_cors()
                self.end_headers()
                self.wfile.write(b"Forbidden: path traversal blocked.")
                return

            if img_path.exists() and img_path.is_file():
                self.send_response(200)
                self._send_cors()
                content_type = "image/webp" if img_path.suffix == ".webp" else "image/png"
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(img_path.stat().st_size))
                self.end_headers()
                self.wfile.write(img_path.read_bytes())
                return
            else:
                self.send_response(404)
                self._send_cors()
                self.end_headers()
                self.wfile.write(b"Frame not found")
                return

        if path == "/api/stats":
            hdata = get_heatmap_data()
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            stats = {
                "total_memories": hdata["total"],
                "active_days": hdata["active_days"],
                "current_streak": hdata["current_streak"],
                "lancedb_dir": str(DEFAULT_LANCEDB_DIR),
            }
            self.wfile.write(json.dumps(stats, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/doc":
            qs = urllib.parse.parse_qs(parsed.query)
            filename = qs.get("file", ["README.md"])[0]
            safe_filename = Path(filename).name
            doc_file = DOCS_WIKI_DIR / safe_filename
            if doc_file.exists():
                self.send_response(200)
                self._send_cors()
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(doc_file.read_text(encoding="utf-8").encode("utf-8"))
            else:
                self.send_response(404)
                self._send_cors()
                self.end_headers()
                self.wfile.write(b"Document not found")
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        origin = self.headers.get("Origin", "")
        if origin and not self._is_allowed_origin(origin):
            self.send_response(403)
            self._send_cors()
            self.end_headers()
            self.wfile.write(b"Forbidden: Invalid Origin")
            return

        fetch_site = self.headers.get("Sec-Fetch-Site", "")
        if fetch_site in ("cross-site",):
            self.send_response(403)
            self._send_cors()
            self.end_headers()
            self.wfile.write(b"Forbidden: Cross-site request rejected")
            return

        if parsed.path in ("/api/record", "/ingest"):
            length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(length)
            try:
                data = json.loads(body_bytes.decode("utf-8"))
                text = data.get("text", "")
                cat = data.get("category", "quick_note")
                tags = data.get("tags", [])
                supersedes = data.get("supersedes")
                source = data.get("source", "web_ui")

                from cephalo.core.embedding_pipeline import EmbeddingPipeline, create_embedder
                embedder = create_embedder(mode="local")
                pipeline = EmbeddingPipeline(embedder=embedder)

                rec = pipeline.ingest_prompt(
                    raw_text=text,
                    category=cat,
                    tags=tags,
                    supersedes=supersedes,
                    source=source,
                    sync_to_jsonl=True,
                )

                self.send_response(200)
                self._send_cors()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "success",
                    "id": rec["id"],
                    "tags": rec.get("tags", []),
                    "category": rec["category"],
                    "sanitized": rec["content"],
                }, ensure_ascii=False).encode("utf-8"))
                return
            except Exception as e:
                self.send_response(500)
                self._send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                return

        self.send_response(404)
        self.end_headers()


def run_deepwiki_server(port: int = 7433, open_browser: bool = True) -> None:
    """Runs the integrated Sovereign DeepWiki & Timeline dashboard server."""
    import webbrowser
    wg = WikiGenerator()
    wg._write_timeline_dashboard()
    print(f"[+] Serving Cephalo DeepWiki & Memory Timeline at http://127.0.0.1:{port}/")
    if open_browser:
        webbrowser.open(f"http://127.0.0.1:{port}/")
    with ThreadingHTTPServer(("127.0.0.1", port), DeepWikiServerHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[+] DeepWiki server stopped.")

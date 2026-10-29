#!/usr/bin/env python3
"""
Cephalo Multi-Channel Quick Capture & Webhook Ingress Gateway (webhook_server.py)
================================================================================
Lightweight, local-first HTTP webhook server and ingestion bridge.
Allows instant quick-capture from:
- iOS Shortcuts / Android Tasker / curl
- Browser extensions / Raycast scripts
- Telegram Bot (polling or webhook)
- Local scripts and external services

All ingested content passes through Cephalo's Zero-Leak Privacy Shield
and is embedded into LanceDB and prompts.jsonl automatically.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

# Base paths
ROOT_DIR = Path(__file__).resolve().parents[2]
BASE_DIR = ROOT_DIR
DATA_DIR = ROOT_DIR / "data"
PROMPTS_FILE = DATA_DIR / "prompts.jsonl"
DEFAULT_PORT = 7434
DEFAULT_HOST = "127.0.0.1"

logger = logging.getLogger("cephalo.webhook")

# Lazy pipeline holder
_pipeline_cache = None


def get_pipeline():
    global _pipeline_cache
    if _pipeline_cache is None:
        from embedding_pipeline import EmbeddingPipeline, create_embedder
        embedder = create_embedder(mode="local")
        _pipeline_cache = EmbeddingPipeline(embedder=embedder)
    return _pipeline_cache


class WebhookRequestHandler(BaseHTTPRequestHandler):
    """Handles incoming HTTP webhooks, REST ingest calls, and health checks."""

    auth_token: Optional[str] = None

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def _authenticate(self) -> bool:
        if not self.auth_token:
            return True
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            return token == self.auth_token
        return False

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path in ("/health", "/status"):
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

            prompt_count = 0
            if PROMPTS_FILE.exists():
                with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
                    prompt_count = sum(1 for line in f if line.strip())

            status = {
                "status": "healthy",
                "service": "cephalo_webhook",
                "prompts_logged": prompt_count,
                "timestamp": time.time(),
            }
            self.wfile.write(json.dumps(status).encode("utf-8"))
            return

        self.send_response(404)
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(b"Not Found")

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if not self._authenticate():
            self.send_response(401)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Unauthorized"}).encode("utf-8"))
            return

        if path in ("/ingest", "/webhook", "/api/record"):
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self.send_response(400)
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Empty payload"}).encode("utf-8"))
                return

            body_bytes = self.rfile.read(content_length)
            content_type = self.headers.get("Content-Type", "")

            text = ""
            category = "quick_note"
            tags: List[str] = []
            source = "webhook"
            supersedes: Optional[str] = None
            relates_to: Optional[List[str]] = None

            if "application/json" in content_type:
                try:
                    data = json.loads(body_bytes.decode("utf-8"))
                    text = data.get("text", "") or data.get("content", "") or data.get("message", "")
                    category = data.get("category", "quick_note")
                    source = data.get("source", "webhook")
                    supersedes = data.get("supersedes")
                    relates_to = data.get("relates_to")
                    raw_tags = data.get("tags", [])
                    if isinstance(raw_tags, list):
                        tags = [str(t) for t in raw_tags]
                    elif isinstance(raw_tags, str):
                        tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
                except Exception as err:
                    self.send_response(400)
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": f"Invalid JSON: {err}"}).encode("utf-8"))
                    return
            elif "application/x-www-form-urlencoded" in content_type:
                params = urllib.parse.parse_qs(body_bytes.decode("utf-8"))
                text = params.get("text", [""])[0] or params.get("content", [""])[0]
                category = params.get("category", ["quick_note"])[0]
                source = params.get("source", ["webhook"])[0]
                supersedes = params.get("supersedes", [None])[0]
            else:
                # Raw text payload
                text = body_bytes.decode("utf-8", errors="replace").strip()

            if not text.strip():
                self.send_response(400)
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing 'text' field"}).encode("utf-8"))
                return

            try:
                pipeline = get_pipeline()
                record = pipeline.ingest_prompt(
                    raw_text=text,
                    category=category,
                    source=source,
                    tags=tags,
                    supersedes=supersedes,
                    relates_to=relates_to,
                    sync_to_jsonl=True,
                )

                response_payload = {
                    "status": "success",
                    "id": record["id"],
                    "category": record["category"],
                    "tags": record.get("tags", []),
                    "sanitized": record["content"],
                    "supersedes": record.get("supersedes", ""),
                }

                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(response_payload, ensure_ascii=False).encode("utf-8"))
                logger.info("Ingested memory via webhook: [%s] (%s)", record["id"], record["category"])

            except Exception as e:
                logger.error("Error processing webhook ingestion: %s", e, exc_info=True)
                self.send_response(500)
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        self.send_response(404)
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(b"Not Found")

    def log_message(self, fmt, *args):
        # Override to log via standard logger instead of stderr spam
        logger.debug(fmt, *args)


class WebhookServer:
    """Manages the lifecycle of the quick-capture HTTP ingress server."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, auth_token: Optional[str] = None):
        self.host = host
        self.port = port
        self.auth_token = auth_token or os.environ.get("CEPHALO_WEBHOOK_TOKEN")
        self.server: Optional[ThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self, background: bool = False) -> None:
        """Starts the webhook server either in the foreground or in a background daemon thread."""
        handler_class = WebhookRequestHandler
        handler_class.auth_token = self.auth_token

        self.server = ThreadingHTTPServer((self.host, self.port), handler_class)
        logger.info("Cephalo Webhook Ingress Gateway listening at http://%s:%d/", self.host, self.port)

        if background:
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            logger.info("Webhook server running in background thread.")
        else:
            try:
                print(f"[+] Cephalo Webhook Gateway active at http://{self.host}:{self.port}/ (Ctrl+C to stop)")
                self.server.serve_forever()
            except KeyboardInterrupt:
                print("\n[+] Stopping Webhook Gateway...")
                self.stop()

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            logger.info("Webhook server stopped.")


# ==============================================================================
# Telegram Ingestion Bridge (Optional Poller)
# ==============================================================================
class TelegramIngestBot:
    """Lightweight zero-dependency Telegram bot polling worker for remote thought capture."""

    def __init__(self, bot_token: str, allowed_chat_ids: Optional[List[str]] = None):
        self.bot_token = bot_token
        self.allowed_chat_ids = set(allowed_chat_ids or [])
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.offset = 0

    def _api_call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        try:
            if params:
                data = json.dumps(params).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            else:
                req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.debug("Telegram API error (%s): %s", method, e)
            return None

    def _poll_loop(self) -> None:
        logger.info("Telegram quick-capture poller started.")
        pipeline = get_pipeline()

        while self.running:
            updates = self._api_call("getUpdates", {"offset": self.offset, "timeout": 20})
            if not updates or not updates.get("ok"):
                time.sleep(2)
                continue

            for item in updates.get("result", []):
                self.offset = max(self.offset, item.get("update_id", 0) + 1)
                message = item.get("message") or item.get("channel_post")
                if not message:
                    continue

                chat = message.get("chat", {})
                chat_id = str(chat.get("id", ""))
                text = message.get("text", "") or message.get("caption", "")

                if self.allowed_chat_ids and chat_id not in self.allowed_chat_ids:
                    logger.warning("Ignored Telegram message from unauthorized chat ID: %s", chat_id)
                    continue

                if not text.strip():
                    continue

                # Ingest into Cephalo
                try:
                    rec = pipeline.ingest_prompt(
                        raw_text=text,
                        category="telegram_quick_capture",
                        source="telegram",
                        sync_to_jsonl=True,
                    )
                    tags_str = (" " + " ".join([f"#{t}" for t in rec.get("tags", [])])) if rec.get("tags") else ""
                    reply_text = f"🧠 Ingested into Cephalo [{rec['id']}]{tags_str}:\n{rec['content'][:120]}"
                    self._api_call("sendMessage", {"chat_id": chat_id, "text": reply_text})
                    logger.info("Telegram note captured: [%s]", rec["id"])
                except Exception as err:
                    logger.error("Failed to ingest Telegram note: %s", err)

    def start(self) -> None:
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False


def send_quick_memory(text: str, category: str = "quick_note", host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Dict[str, Any]:
    """Helper for CLI to post a note to the local webhook gateway."""
    url = f"http://{host}:{port}/ingest"
    payload = json.dumps({"text": text, "category": category, "source": "cli_webhook"}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))

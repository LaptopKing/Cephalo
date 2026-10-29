#!/usr/bin/env python3
"""
Test Suite: Memos-Inspired Improvements to Cephalo
===================================================
Tests all 4 newly implemented features:
1. Activity Heatmap & Memory Timeline Feed (DeepWiki Dashboard)
2. Multi-Channel Quick Capture HTTP Webhook Gateway
3. Inline #tag Extraction & Tag-Filtered Search
4. Memory Relations & Supersession Deprecation Tracking
"""

import datetime
import json
import shutil
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

from embedding_pipeline import (
    EmbeddingPipeline,
    FastEmbedEmbedder,
    LanceDBStore,
    extract_tags,
)
from webhook_server import WebhookServer, send_quick_memory
from wiki_generator import (
    WikiGenerator,
    get_heatmap_data,
    get_timeline_records,
)


class TestTagTaxonomy(unittest.TestCase):
    """Tests Feature 3: Inline #tag and Hierarchical Tagging Taxonomy."""

    def test_extract_tags(self):
        # Basic tags
        self.assertEqual(extract_tags("Notes on #database and #storage"), ["database", "storage"])

        # Hierarchical nested tags
        self.assertEqual(
            extract_tags("Display calibrated on #hardware/display and #cinema/hdr"),
            ["hardware/display", "cinema/hdr"],
        )

        # Ignores pure numbers, markdown headers, and empty
        self.assertEqual(extract_tags("# NotATag #123 #"), [])

        # Mixed alphanumeric tags with hyphens and underscores
        self.assertEqual(
            extract_tags("Testing on #tcl-65t8b with #vivid_mode"),
            ["tcl-65t8b", "vivid_mode"],
        )

    def test_ingest_with_tags(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            embedder = FastEmbedEmbedder(model_name="Qwen/Qwen3-Embedding-0.6B-Q")
            pipeline = EmbeddingPipeline(embedder=embedder, db_path=tmp_dir)

            record = pipeline.ingest_prompt(
                raw_text="Prefer LanceDB over Pinecone for #storage/vectors and #ai #local-first",
                category="architecture",
                sync_to_jsonl=False,
            )

            self.assertIn("storage/vectors", record["tags"])
            self.assertIn("ai", record["tags"])
            self.assertIn("local-first", record["tags"])

            # Search with tag filter
            results = pipeline.search(
                raw_query="vectors",
                tag="storage/vectors",
                limit=5,
            )
            self.assertTrue(len(results) > 0)
            self.assertEqual(results[0]["id"], record["id"])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestMemoryRelationsAndSupersession(unittest.TestCase):
    """Tests Feature 4: Memory Relations & Supersession Links."""

    def test_supersession_deprecation(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            embedder = FastEmbedEmbedder(model_name="Qwen/Qwen3-Embedding-0.6B-Q")
            pipeline = EmbeddingPipeline(embedder=embedder, db_path=tmp_dir)

            # 1. Record original decision
            mem1 = pipeline.ingest_prompt(
                raw_text="Initial decision: Use REST API for internal communication #backend",
                prompt_id="prompt-old-001",
                category="architecture",
                sync_to_jsonl=False,
            )
            self.assertFalse(mem1["is_deprecated"])

            # 2. Record new decision that supersedes mem1
            mem2 = pipeline.ingest_prompt(
                raw_text="Updated decision: Migrated to gRPC for microsecond latency #backend/grpc",
                prompt_id="prompt-new-002",
                category="architecture",
                supersedes="prompt-old-001",
                sync_to_jsonl=False,
            )

            self.assertEqual(mem2["supersedes"], "prompt-old-001")
            self.assertFalse(mem2["is_deprecated"])

            # Verify that prompt-old-001 is now deprecated in LanceDB
            active_results = pipeline.search(
                raw_query="internal communication",
                include_deprecated=False,
            )
            found_ids = [r["id"] for r in active_results]
            self.assertNotIn("prompt-old-001", found_ids)

            # When include_deprecated is True, it should be visible
            all_results = pipeline.search(
                raw_query="internal communication",
                include_deprecated=True,
            )
            all_ids = [r["id"] for r in all_results]
            self.assertIn("prompt-old-001", all_ids)

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestWebhookQuickCapture(unittest.TestCase):
    """Tests Feature 2: Multi-Channel Quick Capture HTTP Webhook Gateway."""

    def test_webhook_ingest_and_health(self):
        server = WebhookServer(host="127.0.0.1", port=7439)
        server.start(background=True)
        time.sleep(0.5)

        try:
            # Check health
            with urllib.request.urlopen("http://127.0.0.1:7439/health", timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(data["status"], "healthy")
                self.assertEqual(data["service"], "cephalo_webhook")

            # Post memory via helper
            res = send_quick_memory(
                text="Remote note: TCL 65T8B requires Warm color temperature on SDR #hardware/display",
                category="hardware",
                port=7439,
            )
            self.assertEqual(res["status"], "success")
            self.assertIn("id", res)
            self.assertIn("hardware/display", res.get("tags", []))
            self.assertIn("TCL 65T8B", res.get("sanitized", ""))

        finally:
            server.stop()


class TestDashboardAndHeatmap(unittest.TestCase):
    """Tests Feature 1: Memory Timeline & Activity Heatmap."""

    def test_generate_dashboard_html(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            wg = WikiGenerator(output_dir=tmp_dir)
            index_path = wg._write_timeline_dashboard()
            self.assertTrue(index_path.exists())
            content = index_path.read_text(encoding="utf-8")
            self.assertIn("Cephalo — Memory Timeline & Activity Heatmap", content)
            self.assertIn("heatmap-grid", content)
            self.assertIn("timeline-stream", content)
            self.assertIn("Quick Capture", content)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_heatmap_data_aggregation(self):
        hdata = get_heatmap_data()
        self.assertIn("days", hdata)
        self.assertIn("total", hdata)
        self.assertIn("active_days", hdata)
        self.assertIn("current_streak", hdata)
        self.assertIsInstance(hdata["days"], dict)


if __name__ == "__main__":
    unittest.main()

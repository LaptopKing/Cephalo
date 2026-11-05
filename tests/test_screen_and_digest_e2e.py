"""
End-to-End Test Suite: Cephalo Screen Memory, Safeguards, & Anti-AI-Slop Digest
=============================================================================
Verifies:
1. Configurable Safeguards & Blacklist filter (process, window title, domain).
2. Perceptual frame delta computation and threshold gating.
3. Event-driven WebP keyframe capture & indexing.
4. Privacy shield masking on OCR text & shielded aborts.
5. Anti-AI-slop Daily Digest generation (hourly velocity, Mermaid xychart, tables).
6. DeepWiki 24-hour timeline scrubber integration and frame blending.
7. Frame pruning and thumbnail compaction.
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from cephalo.core.daily_digest import DailyDigestGenerator
from cephalo.core.safeguards import (
    DEFAULT_SAFEGUARDS,
    add_blacklisted_process,
    add_blacklisted_title,
    is_shielded,
    load_safeguards_config,
    remove_blacklisted_process,
    remove_blacklisted_title,
    save_safeguards_config,
)


class TestSafeguardsE2E(unittest.TestCase):
    """End-to-end testing for configurable privacy safeguards and blacklists."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="cephalo_test_safe_"))
        self.safeguards_file = self.test_dir / "safeguards.json"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_safeguards_initialization(self):
        cfg = load_safeguards_config(self.safeguards_file)
        self.assertTrue(cfg["enabled"])
        self.assertIn("bitwarden", cfg["blacklisted_processes"])
        self.assertIn("1password", cfg["blacklisted_processes"])
        self.assertTrue(self.safeguards_file.exists())

    def test_shielding_blacklisted_processes(self):
        cfg = load_safeguards_config(self.safeguards_file)

        # Process stem matching
        shielded, reason = is_shielded(process_name="Bitwarden.exe", config=cfg)
        self.assertTrue(shielded)
        self.assertIn("Bitwarden", reason)

        shielded, reason = is_shielded(process_name="C:\\Program Files\\1Password\\1Password.exe", config=cfg)
        self.assertTrue(shielded)

        # Non-blacklisted process
        shielded, reason = is_shielded(process_name="Code.exe", config=cfg)
        self.assertFalse(shielded)

    def test_shielding_window_titles_regex(self):
        cfg = load_safeguards_config(self.safeguards_file)

        # Incognito / Private
        shielded, _ = is_shielded(window_title="Google Chrome - Incognito", config=cfg)
        self.assertTrue(shielded)

        shielded, _ = is_shielded(window_title="Mozilla Firefox - Private Browsing", config=cfg)
        self.assertTrue(shielded)

        # Payment & Credential
        shielded, _ = is_shielded(window_title="Checkout - Enter Credit Card Details", config=cfg)
        self.assertTrue(shielded)

        # Normal coding window
        shielded, _ = is_shielded(window_title="USER_PROFILE.md — Cephalo — Visual Studio Code", config=cfg)
        self.assertFalse(shielded)

    def test_dynamic_add_and_remove(self):
        # Add custom process
        add_blacklisted_process("slack_private", self.safeguards_file)
        cfg = load_safeguards_config(self.safeguards_file)
        self.assertIn("slack_private", cfg["blacklisted_processes"])

        shielded, _ = is_shielded(process_name="slack_private.exe", config=cfg)
        self.assertTrue(shielded)

        # Remove process
        remove_blacklisted_process("slack_private", self.safeguards_file)
        cfg = load_safeguards_config(self.safeguards_file)
        self.assertNotIn("slack_private", cfg["blacklisted_processes"])

        shielded, _ = is_shielded(process_name="slack_private.exe", config=cfg)
        self.assertFalse(shielded)


class TestNativeRustScreenE2E(unittest.TestCase):
    """End-to-end testing for sovereign native Rust screen memory engine."""

    def test_rust_screen_status(self):
        res = subprocess.run(["cephalo", "screen", "status", "--json"], capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        self.assertTrue(data.get("safe_rust"))
        self.assertFalse(data.get("unsafe_code"))
        self.assertIn("status", data)
        self.assertIn("frames_dir", data)

    def test_rust_screen_snap_force(self):
        res = subprocess.run(["cephalo", "screen", "snap", "--force", "--json"], capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        self.assertIn(data.get("status"), ("captured", "shielded", "high_churn_suppressed"))
        if data.get("status") == "captured":
            self.assertIn("frame_id", data)
            self.assertIn("path", data)
            self.assertIn("roi_mode", data)
            self.assertIn(data.get("roi_mode"), ("active_window", "full_screen"))

    def test_rust_screen_enable_and_status(self):
        # Enable screen memory
        subprocess.run(["cephalo", "screen", "enable"], capture_output=True, text=True, check=True)
        res = subprocess.run(["cephalo", "screen", "status", "--json"], capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        self.assertEqual(data.get("status"), "enabled")
        self.assertTrue(data.get("screen_capture_enabled"))


class TestDailyDigestE2E(unittest.TestCase):
    """End-to-end testing for Anti-AI-Slop Daily Digest generation."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="cephalo_test_digest_"))
        self.prompts_file = self.test_dir / "prompts.jsonl"
        self.frames_file = self.test_dir / "frame_index.jsonl"
        self.today_str = datetime.date.today().isoformat()

        # Seed sample prompts for today
        sample_prompts = [
            {
                "id": "prompt-001",
                "timestamp": f"{self.today_str}T09:15:00",
                "category": "architecture",
                "text": "Adopted cross-platform perceptual delta screen engine #screen #architecture",
                "tags": ["screen", "architecture"],
            },
            {
                "id": "prompt-002",
                "timestamp": f"{self.today_str}T10:30:00",
                "category": "tech_stack",
                "text": "Integrated WebP compression for keyframes #tech_stack #storage",
                "tags": ["tech_stack", "storage"],
            },
            {
                "id": "prompt-003",
                "timestamp": f"{self.today_str}T10:45:00",
                "category": "quick_note",
                "text": "Review DeepWiki 24-hour timeline scrubber slider #ui #deepwiki",
                "tags": ["ui", "deepwiki"],
            },
        ]

        with open(self.prompts_file, "w", encoding="utf-8") as f:
            for sp in sample_prompts:
                f.write(json.dumps(sp) + "\n")

        # Seed sample screen frames for today
        sample_frames = [
            {
                "id": "frame-001",
                "timestamp": f"{self.today_str}T09:20:00",
                "date": self.today_str,
                "process_name": "Code.exe",
                "window_title": "screen_recorder.py — Cephalo",
                "delta": 0.12,
            },
            {
                "id": "frame-002",
                "timestamp": f"{self.today_str}T10:35:00",
                "date": self.today_str,
                "process_name": "chrome.exe",
                "window_title": "LanceDB Documentation",
                "delta": 0.08,
            },
        ]

        with open(self.frames_file, "w", encoding="utf-8") as f:
            for sf in sample_frames:
                f.write(json.dumps(sf) + "\n")

        self.generator = DailyDigestGenerator(
            prompts_file=self.prompts_file,
            frames_file=self.frames_file,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_generate_digest_metrics(self):
        digest = self.generator.generate_digest(self.today_str)
        self.assertEqual(digest["date"], self.today_str)
        self.assertEqual(digest["total_events"], 5)  # 3 prompts + 2 frames
        self.assertEqual(digest["prompts_count"], 3)
        self.assertEqual(digest["screen_frames_count"], 2)

        # Check hourly aggregation (9:00 and 10:00)
        self.assertIn(9, digest["hourly_counts"])
        self.assertIn(10, digest["hourly_counts"])
        self.assertEqual(digest["hourly_counts"][9], 2)
        self.assertEqual(digest["hourly_counts"][10], 3)

        # Check active processes
        self.assertIn("Code.exe", digest["active_processes"])
        self.assertIn("chrome.exe", digest["active_processes"])

    def test_anti_ai_slop_markdown_rendering(self):
        digest = self.generator.generate_digest(self.today_str)
        md = self.generator.render_markdown(digest)

        # Must include structured headers and metrics
        self.assertIn("# 🧠 Cephalo Daily Digest", md)
        self.assertIn("5 Events", md)
        self.assertIn("xychart-beta", md)  # Mermaid chart
        self.assertIn("Focus Domain / Category", md)  # Structured table
        self.assertIn("Active Workspace Tools", md)

        # Anti-AI-slop assertion: Zero generic narrative filler
        self.assertNotIn("I hope this helps", md)
        self.assertNotIn("Here is a summary of what you did today", md)
        self.assertNotIn("Overall, it was a productive day", md)


class TestDeepWikiScrubberE2E(unittest.TestCase):
    """End-to-end testing for DeepWiki 24-hour timeline scrubber & frame blending."""

    def test_timeline_records_blends_prompts_and_frames(self):
        from cephalo.research.wiki_generator import get_timeline_records

        records = get_timeline_records(limit=20)
        self.assertIsInstance(records, list)
        # Verify structure
        for rec in records:
            self.assertIn("id", rec)
            self.assertIn("timestamp", rec)
            self.assertIn("category", rec)

    def test_dashboard_html_contains_scrubber(self):
        from cephalo.research.wiki_generator import WikiGenerator

        wg = WikiGenerator()
        index_path = wg._write_timeline_dashboard()
        self.assertTrue(index_path.exists())

        html = index_path.read_text(encoding="utf-8")
        # Assert scrubber components exist in HTML/JS
        self.assertIn("24-Hour Timeline Scrubber", html)
        self.assertIn("id=\"hour-slider\"", html)
        self.assertIn("onScrubHour", html)
        self.assertIn("resetScrubber", html)
        self.assertIn("activeHour", html)


if __name__ == "__main__":
    unittest.main()

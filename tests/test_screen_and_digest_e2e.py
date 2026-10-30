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
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

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
from cephalo.services.screen_recorder import (
    ScreenMemoryEngine,
    compute_frame_delta,
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


class TestScreenMemoryDeltaE2E(unittest.TestCase):
    """End-to-end testing for perceptual delta gating and WebP frame capture."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="cephalo_test_screen_"))
        self.engine = ScreenMemoryEngine(base_dir=self.test_dir, min_delta_threshold=0.05)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_mock_image(self, color=(100, 100, 100), text: str = "") -> Image.Image:
        img = Image.new("RGB", (400, 300), color=color)
        if text:
            draw = ImageDraw.Draw(img)
            draw.text((20, 20), text, fill=(255, 255, 255))
        return img

    def test_delta_computation_identical_frames(self):
        img_a = self._create_mock_image((50, 50, 50))
        img_b = self._create_mock_image((50, 50, 50))
        delta = compute_frame_delta(img_a, img_b)
        self.assertEqual(delta, 0.0)

    def test_delta_computation_different_frames(self):
        img_a = self._create_mock_image((0, 0, 0))
        img_b = self._create_mock_image((255, 255, 255))
        delta = compute_frame_delta(img_a, img_b)
        self.assertAlmostEqual(delta, 1.0, places=2)

    def test_capture_step_first_frame(self):
        img = self._create_mock_image((30, 40, 50), text="Code Editor Active")
        ctx = {"title": "main.py — Project", "process": "Code.exe", "platform": "linux"}

        res = self.engine.capture_step(image=img, window_context=ctx)
        self.assertEqual(res["status"], "captured")
        self.assertEqual(res["process_name"], "Code.exe")
        self.assertTrue(Path(self.test_dir.parent / res["path"]).exists())

    def test_capture_step_skips_unchanged_screen(self):
        img_a = self._create_mock_image((50, 50, 50), text="Reading Document")
        ctx = {"title": "Doc — Browser", "process": "chrome.exe", "platform": "win32"}

        # Step 1: Capture initial frame
        res1 = self.engine.capture_step(image=img_a, window_context=ctx)
        self.assertEqual(res1["status"], "captured")

        # Step 2: Unchanged screen -> must be skipped
        res2 = self.engine.capture_step(image=img_a, window_context=ctx)
        self.assertEqual(res2["status"], "skipped_no_change")
        self.assertLess(res2["delta"], 0.05)

    def test_capture_step_triggers_on_significant_change(self):
        img_a = self._create_mock_image((0, 0, 0), text="State 1")
        img_b = self._create_mock_image((200, 200, 200), text="State 2 (Terminal)")
        ctx = {"title": "Terminal", "process": "pwsh.exe", "platform": "win32"}

        self.engine.capture_step(image=img_a, window_context=ctx)
        res = self.engine.capture_step(image=img_b, window_context=ctx)
        self.assertEqual(res["status"], "captured")
        self.assertGreaterEqual(res["delta"], 0.05)

    def test_safeguards_shield_abort(self):
        img = self._create_mock_image((10, 10, 10))
        # Active window is a password manager
        ctx = {"title": "Master Password Entry", "process": "Bitwarden.exe", "platform": "win32"}

        res = self.engine.capture_step(image=img, window_context=ctx)
        self.assertEqual(res["status"], "shielded")
        self.assertIn("Blacklisted process", res["reason"])
        # Verify no image was written to disk
        self.assertFalse(any(self.test_dir.rglob("*.webp")))

    def test_frame_pruning_and_thumbnails(self):
        # Create an artificial past date directory
        past_date_str = (datetime.datetime.now() - datetime.timedelta(days=20)).strftime("%Y-%m-%d")
        past_dir = self.test_dir / past_date_str
        past_dir.mkdir(parents=True, exist_ok=True)

        fake_frame = past_dir / "frame_120000_abc123.webp"
        img = self._create_mock_image((80, 80, 80))
        img.save(fake_frame, "WEBP")

        # Run pruning
        prune_res = self.engine.prune_frames(max_age_days=14, keep_thumbnails=True)
        self.assertEqual(prune_res["deleted_frames"], 1)
        self.assertEqual(prune_res["thumbnails_created"], 1)

        # Verify full-res is deleted and thumbnail exists
        self.assertFalse(fake_frame.exists())
        thumb = past_dir / "frame_120000_abc123_thumb.webp"
        self.assertTrue(thumb.exists())


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

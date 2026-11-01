#!/usr/bin/env python3
"""
Unit tests for Cephalo Autonomous Contextual Preference Reconciler (Multilingual & Global).
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure src is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cephalo.core.preference_reconciler import PreferenceReconciler


class TestPreferenceReconciler(unittest.TestCase):
    def setUp(self):
        self.reconciler = PreferenceReconciler()

    def test_ui_theme_mutually_exclusive_supersession(self):
        old_text = "I prefer dark mode obsidian theme for all dashboard UIs."
        new_text = "From now on, switch to warm light stone paper theme for all dashboard UIs, dark mode strains my eyes."

        is_sup, reason, conf = self.reconciler.detect_supersession(
            new_text=new_text,
            cand_text=old_text,
            category="user_preference",
            cand_category="user_preference",
        )
        self.assertTrue(is_sup)
        self.assertGreaterEqual(conf, 0.85)

    def test_living_room_hardware_supersession(self):
        old_text = "User display devices: Living room TV is TCL 65T8B (65-inch 4K QLED Google TV)."
        new_text = "My living room TV is an LG OLED C3 65-inch, replaced the older unit."

        is_sup, reason, conf = self.reconciler.detect_supersession(
            new_text=new_text,
            cand_text=old_text,
            category="hardware_spec",
            cand_category="hardware_devices",
        )
        self.assertTrue(is_sup)
        self.assertGreaterEqual(conf, 0.85)

    def test_hungarian_tv_replacement_supersession(self):
        old_text = "User display devices: Living room TV is TCL 65T8B (65-inch 4K QLED Google TV)."
        new_text = "Mostantól a nappaliban egy LG OLED C3 tévét használunk, a korábbi TCL-t lecseréltük."

        is_sup, reason, conf = self.reconciler.detect_supersession(
            new_text=new_text,
            cand_text=old_text,
            category="hardware_spec",
            cand_category="hardware_devices",
        )
        self.assertTrue(is_sup)
        self.assertGreaterEqual(conf, 0.85)

    def test_hungarian_ui_theme_supersession(self):
        old_text = "I prefer dark mode obsidian theme for all dashboard UIs."
        new_text = "Átállunk világos kőpapír témára minden felületen, a sötét mód már nem kell."

        is_sup, reason, conf = self.reconciler.detect_supersession(
            new_text=new_text,
            cand_text=old_text,
            category="user_preference",
            cand_category="user_preference",
        )
        self.assertTrue(is_sup)
        self.assertGreaterEqual(conf, 0.85)

    def test_hungarian_package_manager_supersession(self):
        old_text = "Use Yarn for package management across all web applications."
        new_text = "A jövőben Yarn helyett csak Bunt használunk csomagkezelésre."

        is_sup, reason, conf = self.reconciler.detect_supersession(
            new_text=new_text,
            cand_text=old_text,
            category="workflow_rule",
            cand_category="workflow_rule",
        )
        self.assertTrue(is_sup)
        self.assertGreaterEqual(conf, 0.90)

    def test_german_package_manager_supersession(self):
        old_text = "Use Yarn for package management across all web applications."
        new_text = "Ab jetzt verwenden wir Bun statt Yarn für alle Node.js Webprojekte."

        is_sup, reason, conf = self.reconciler.detect_supersession(
            new_text=new_text,
            cand_text=old_text,
            category="workflow_rule",
            cand_category="workflow_rule",
        )
        self.assertTrue(is_sup)
        self.assertGreaterEqual(conf, 0.90)

    def test_french_tv_replacement_supersession(self):
        old_text = "User display devices: Living room TV is TCL 65T8B (65-inch 4K QLED Google TV)."
        new_text = "À partir de maintenant notre téléviseur dans le salon est un LG OLED C3, nous avons remplacé le TCL."

        is_sup, reason, conf = self.reconciler.detect_supersession(
            new_text=new_text,
            cand_text=old_text,
            category="hardware_spec",
            cand_category="hardware_devices",
        )
        self.assertTrue(is_sup)
        self.assertGreaterEqual(conf, 0.85)

    def test_api_protocol_transition_supersession(self):
        old_text = "Initial decision: Use REST API for internal communication #backend"
        new_text = "Migrated to gRPC for microsecond latency #backend/grpc"

        is_sup, reason, conf = self.reconciler.detect_supersession(
            new_text=new_text,
            cand_text=old_text,
            category="architecture",
            cand_category="architecture",
        )
        self.assertTrue(is_sup)
        self.assertGreaterEqual(conf, 0.90)

    def test_unrelated_statements_not_superseded(self):
        old_text = "Strict anti-slop software engineering: Matt Pocock real-engineer rules."
        new_text = "Integrated Lemon Squeezy as primary Merchant of Record."

        is_sup, reason, conf = self.reconciler.detect_supersession(
            new_text=new_text,
            cand_text=old_text,
            category="architecture",
            cand_category="coding_philosophy",
        )
        self.assertFalse(is_sup)

    def test_markdown_section_reconciliation_replaces_key(self):
        section_text = (
            "## 2. User Identity & Verified Hardware\n"
            "- **User:** Peter\n"
            "- **Living Room Display:** TCL 65T8B (65\" 4K QLED Google TV)\n"
            "- **Workstation Monitor:** Acer B243HL"
        )
        new_bullet = "- **Living Room Display:** LG OLED C3 (65\" 4K OLED TV)"

        updated, replaced, old_bullet = self.reconciler.reconcile_markdown_section(section_text, new_bullet)
        self.assertTrue(replaced)
        self.assertIn("LG OLED C3", updated)
        self.assertNotIn("TCL 65T8B", updated)
        self.assertEqual(old_bullet, "- **Living Room Display:** TCL 65T8B (65\" 4K QLED Google TV)")

    def test_markdown_section_reconciliation_appends_novel_key(self):
        section_text = (
            "## 2. User Identity & Verified Hardware\n"
            "- **User:** Peter\n"
            "- **Workstation Monitor:** Acer B243HL"
        )
        new_bullet = "- **Tablet Device:** iPad Pro 11-inch M2"

        updated, replaced, old_bullet = self.reconciler.reconcile_markdown_section(section_text, new_bullet)
        self.assertFalse(replaced)
        self.assertIsNone(old_bullet)
        self.assertIn("iPad Pro", updated)
        self.assertIn("Acer B243HL", updated)

    def test_sync_deprecation_to_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            jsonl_path = Path(tmp_dir) / "test_prompts.jsonl"
            entries = [
                {"id": "prompt-001", "content": "Prefer dark mode", "is_deprecated": False},
                {"id": "prompt-002", "content": "Living room TV", "is_deprecated": False},
            ]
            with open(jsonl_path, "w", encoding="utf-8") as f:
                for e in entries:
                    f.write(json.dumps(e) + "\n")

            success = self.reconciler.sync_deprecation_to_jsonl(
                record_id="prompt-001",
                superseded_by="prompt-003",
                jsonl_path=jsonl_path,
            )
            self.assertTrue(success)

            with open(jsonl_path, "r", encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]

            self.assertTrue(lines[0]["is_deprecated"])
            self.assertEqual(lines[0]["superseded_by"], "prompt-003")
            self.assertFalse(lines[1]["is_deprecated"])


if __name__ == "__main__":
    unittest.main()

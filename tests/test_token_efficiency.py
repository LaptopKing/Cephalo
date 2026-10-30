import os
import sys
import unittest
from pathlib import Path

# Add src to sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cephalo.cli import parse_profile_sections
from cephalo.core.embedding_pipeline import get_safe_onnx_providers


class TestTokenEfficiency(unittest.TestCase):
    def setUp(self):
        self.sample_markdown = """# Title

Preamble information here.

---

## 1. Principles & Rules
- Principle A
- Principle B

---

## 2. Hardware Profile
- Display: TCL 65T8B
- Workstation: PC

---

## 5. Entertainment & Cinema
- Instant action
- Guy Ritchie
"""

    def test_parse_profile_sections(self):
        sections = parse_profile_sections(self.sample_markdown)
        self.assertEqual(len(sections), 4)
        self.assertEqual(sections[0]["title"], "Preamble")
        self.assertTrue("1. Principles & Rules" in sections[1]["title"])
        self.assertTrue("2. Hardware Profile" in sections[2]["title"])
        self.assertTrue("5. Entertainment & Cinema" in sections[3]["title"])

    def test_tokens_est_calculation(self):
        sections = parse_profile_sections(self.sample_markdown)
        for s in sections:
            self.assertIn("tokens_est", s)
            self.assertGreater(s["tokens_est"], 0)

    def test_section_filtering_keyword(self):
        sections = parse_profile_sections(self.sample_markdown)
        cinema = next((s for s in sections if "cinema" in s["title"].lower()), None)
        self.assertIsNotNone(cinema)
        self.assertIn("Instant action", cinema["content"])

    def test_safe_onnx_providers(self):
        providers = get_safe_onnx_providers()
        self.assertIsInstance(providers, list)
        self.assertIn("CPUExecutionProvider", providers)

    def test_sectional_profile_reconstruction(self):
        sections = parse_profile_sections(self.sample_markdown)
        # Verify divider stripping
        for s in sections:
            self.assertFalse(s["content"].strip().endswith("---"))

        # Mutate cinema section
        cinema_idx = 3
        sections[cinema_idx]["content"] = sections[cinema_idx]["content"] + "\n- New constraint: No shaky cam"
        reconstructed = "\n\n---\n\n".join(s["content"].strip() for s in sections) + "\n"
        self.assertIn("No shaky cam", reconstructed)
        self.assertIn("## 1. Principles & Rules", reconstructed)

    def test_actual_profile_modularization(self):
        profile_file = ROOT_DIR / "USER_PROFILE.md"
        if profile_file.exists():
            text = profile_file.read_text(encoding="utf-8")
            sections = parse_profile_sections(text)
            self.assertEqual(len(sections), 11)
            titles = [s["title"] for s in sections]
            self.assertIn("Preamble", titles[0])
            self.assertIn("1. Core Principles & Non-Negotiables", titles[1])
            self.assertIn("10. Cephalo Continuous Learning & Autonomous Research Engine", titles[10])


if __name__ == "__main__":
    unittest.main()

import unittest
from cephalo.cli import parse_profile_sections

class TestTokenEfficiency(unittest.TestCase):
    def setUp(self):
        self.sample_markdown = """# Title

Preamble information here.

## 1. Principles & Rules
- Principle A
- Principle B

## 2. Hardware Profile
- Display: TCL 65T8B
- Workstation: PC

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

if __name__ == "__main__":
    unittest.main()

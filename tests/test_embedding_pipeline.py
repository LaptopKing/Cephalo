#!/usr/bin/env python3
"""
Unit and Integration Tests for embedding_pipeline.py
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
import sys
from pathlib import Path
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from cephalo.core.embedding_pipeline import (
    Sanitizer,
    FastEmbedEmbedder,
    GoogleEmbedder,
    LanceDBStore,
    EmbeddingPipeline,
)


class TestSanitizer(unittest.TestCase):
    def setUp(self):
        self.sanitizer = Sanitizer()

    def test_regex_secrets_redaction(self):
        text = "My secret token: api_key=supersecretpassword123456 and sk-abcdef1234567890abcdef1234567890"
        clean = self.sanitizer.sanitize(text)
        self.assertNotIn("supersecretpassword123456", clean)
        self.assertNotIn("sk-abcdef1234567890abcdef1234567890", clean)
        # Should be redacted by either Presidio or Regex
        self.assertTrue("<REDACTED_" in clean or "<PERSON>" in clean)

    def test_regex_ip_and_card_redaction(self):
        text = "Server is at 192.168.1.100 and card is 4111 2222 3333 4444"
        clean = self.sanitizer.sanitize(text)
        self.assertNotIn("192.168.1.100", clean)
        self.assertNotIn("4111 2222 3333 4444", clean)
        # Redacted by Presidio (<IP_ADDRESS>) or Regex (<REDACTED_IP>)
        self.assertTrue("<IP_ADDRESS>" in clean or "<REDACTED_IP>" in clean)
        self.assertTrue("<REDACTED_CARD>" in clean or "<CREDIT_CARD>" in clean)

    def test_code_identifier_shield(self):
        code = "def calculate_total(person, order_id): return person.balance - order_id"
        clean = self.sanitizer.sanitize(code)
        # Ensure code variable 'person' was preserved and NOT turned into PII
        self.assertIn("person", clean)
        self.assertNotIn("<REDACTED_PERSON", clean)
        self.assertNotIn("<PERSON>", clean)

    def test_shannon_entropy_secret_assignment(self):
        line = 'client_secret = "9xLpQ01mNmNaK29188xZ" # internal key'
        clean = self.sanitizer.sanitize(line)
        self.assertNotIn("9xLpQ01mNmNaK29188xZ", clean)
        self.assertIn("<REDACTED_SECRET>", clean)

    def test_hungarian_iban_and_pii(self):
        line = "Kovács János Budapesten él, számlája HU42 1177 3016 1111 2222 0000 0000"
        clean = self.sanitizer.sanitize(line)
        self.assertNotIn("1177 3016 1111 2222 0000 0000", clean)
        self.assertIn("<REDACTED_HU_IBAN>", clean)


class TestFastEmbed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.embedder = FastEmbedEmbedder(model_name="BAAI/bge-small-en-v1.5")

    def test_dimensions_and_embedding(self):
        self.assertEqual(self.embedder.dimension, 384)
        vectors = self.embedder.embed_texts(["hello world", "artificial intelligence"])
        self.assertEqual(len(vectors), 2)
        self.assertEqual(len(vectors[0]), 384)
        self.assertEqual(len(vectors[1]), 384)


class TestGoogleEmbedder(unittest.TestCase):
    def test_missing_api_key_raises(self):
        # Clear env variables temporarily
        orig_gemini = os.environ.pop("GEMINI_API_KEY", None)
        orig_google = os.environ.pop("GOOGLE_API_KEY", None)
        try:
            with self.assertRaises(ValueError):
                GoogleEmbedder(api_key=None)
        finally:
            if orig_gemini:
                os.environ["GEMINI_API_KEY"] = orig_gemini
            if orig_google:
                os.environ["GOOGLE_API_KEY"] = orig_google

    def test_matryoshka_dimension_config(self):
        embedder = GoogleEmbedder(api_key="dummy_key", dimension=256)
        self.assertEqual(embedder.dimension, 256)
        self.assertEqual(embedder.model_name, "text-embedding-004")
        self.assertEqual(embedder.mode, "google")


class TestLanceDBStore(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test_db"
        self.store = LanceDBStore(db_path=self.db_path, table_name="test_table", dimension=4)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_add_and_deduplicate(self):
        records = [
            {
                "id": "p-01",
                "vector": [1.0, 0.0, 0.0, 0.0],
                "content": "first document",
                "category": "cat1",
                "source": "src1",
                "timestamp": "2026-10-20T00:00:00Z",
                "embedding_model": "test",
                "dimension": 4,
                "extracted_intent": "",
                "learned_traits": ["trait1"],
                "sanitized": True,
            },
            {
                "id": "p-02",
                "vector": [0.0, 1.0, 0.0, 0.0],
                "content": "second document",
                "category": "cat2",
                "source": "src2",
                "timestamp": "2026-10-20T00:00:00Z",
                "embedding_model": "test",
                "dimension": 4,
                "extracted_intent": "",
                "learned_traits": [],
                "sanitized": True,
            },
        ]
        inserted = self.store.add_records(records)
        self.assertEqual(inserted, 2)
        self.assertEqual(self.store.count(), 2)

        # Attempt to re-insert existing IDs (idempotency check)
        inserted_again = self.store.add_records(records)
        self.assertEqual(inserted_again, 0)
        self.assertEqual(self.store.count(), 2)

    def test_vector_search(self):
        self.store.add_records([
            {
                "id": "doc-a",
                "vector": [1.0, 0.0, 0.0, 0.0],
                "content": "Topic Alpha",
                "category": "general",
                "source": "test",
                "timestamp": "2026-10-20T00:00:00Z",
                "embedding_model": "test",
                "dimension": 4,
                "extracted_intent": "",
                "learned_traits": [],
                "sanitized": True,
            },
            {
                "id": "doc-b",
                "vector": [0.0, 1.0, 0.0, 0.0],
                "content": "Topic Beta",
                "category": "general",
                "source": "test",
                "timestamp": "2026-10-20T00:00:00Z",
                "embedding_model": "test",
                "dimension": 4,
                "extracted_intent": "",
                "learned_traits": [],
                "sanitized": True,
            },
        ])
        results = self.store.search(query_vector=[0.9, 0.1, 0.0, 0.0], limit=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "doc-a")

    def test_hybrid_search(self):
        self.store.add_records([
            {
                "id": "doc-python",
                "vector": [1.0, 0.0, 0.0, 0.0],
                "content": "Building async web servers with Python FastAPI",
                "category": "backend",
                "source": "test",
                "timestamp": "2026-10-20T10:00:00Z",
                "embedding_model": "test",
                "dimension": 4,
                "extracted_intent": "",
                "learned_traits": [],
                "sanitized": True,
            },
            {
                "id": "doc-rust",
                "vector": [0.0, 1.0, 0.0, 0.0],
                "content": "High-performance systems programming in Rust",
                "category": "systems",
                "source": "test",
                "timestamp": "2026-10-20T11:00:00Z",
                "embedding_model": "test",
                "dimension": 4,
                "extracted_intent": "",
                "learned_traits": [],
                "sanitized": True,
            },
        ])
        # Hybrid search combining text keyword match and vector
        results = self.store.search(
            query_vector=[0.8, 0.2, 0.0, 0.0],
            query_text="FastAPI Python",
            query_type="hybrid",
            limit=1,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "doc-python")
        self.assertIn("_relevance_score", results[0])

    def test_where_filter_hybrid(self):
        self.store.add_records([
            {
                "id": "doc-early",
                "vector": [1.0, 0.0, 0.0, 0.0],
                "content": "Morning development session in terminal",
                "category": "dev",
                "source": "terminal",
                "timestamp": "2026-10-20T08:00:00Z",
                "embedding_model": "test",
                "dimension": 4,
                "extracted_intent": "",
                "learned_traits": [],
                "sanitized": True,
            },
            {
                "id": "doc-late",
                "vector": [0.95, 0.05, 0.0, 0.0],
                "content": "Afternoon development session in terminal",
                "category": "dev",
                "source": "terminal",
                "timestamp": "2026-10-20T15:00:00Z",
                "embedding_model": "test",
                "dimension": 4,
                "extracted_intent": "",
                "learned_traits": [],
                "sanitized": True,
            },
        ])
        # Filter for sessions after 12:00:00
        results = self.store.search(
            query_vector=[1.0, 0.0, 0.0, 0.0],
            query_text="terminal",
            query_type="hybrid",
            where="timestamp >= '2026-10-20T12:00:00Z'",
            limit=5,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "doc-late")

    def test_fts_only_search(self):
        self.store.add_records([
            {
                "id": "doc-needle",
                "vector": [0.0, 0.0, 1.0, 0.0],
                "content": "A very specific keyword XYZ999UniqueToken",
                "category": "secrets",
                "source": "test",
                "timestamp": "2026-10-20T12:00:00Z",
                "embedding_model": "test",
                "dimension": 4,
                "extracted_intent": "",
                "learned_traits": [],
                "sanitized": True,
            }
        ])
        results = self.store.search(
            query_text="XYZ999UniqueToken",
            query_type="fts",
            limit=1,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "doc-needle")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""
End-to-End Integration Tests for Cephalo Contextual Preference Invalidation and Supersession.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from cephalo.core.embedding_pipeline import BaseEmbedder, EmbeddingPipeline


class MockDeterministicEmbedder(BaseEmbedder):
    """
    Ultra-fast deterministic embedder for unit/integration testing without FastEmbed / ONNX overhead.
    Produces repeatable vectors with high cosine similarity for related keywords.
    """

    def __init__(self, dim: int = 64):
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def mode(self) -> str:
        return "local"

    @property
    def model_name(self) -> str:
        return "mock-embedder"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        words = text.lower().split()
        for idx, w in enumerate(words):
            bucket = abs(hash(w)) % self._dim
            vec[bucket] += 1.0 / (idx + 1)
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [float(x / norm) for x in vec]


class TestContextualSupersessionE2E(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.jsonl_path = self.tmp_dir / "prompts.jsonl"
        self.embedder = MockDeterministicEmbedder(dim=64)
        self.pipeline = EmbeddingPipeline(
            embedder=self.embedder,
            db_path=self.tmp_dir / "lancedb",
            table_name="test_prompts",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_autonomous_supersession_flow(self):
        # 1. Ingest initial preference
        mem1 = self.pipeline.ingest_prompt(
            raw_text="I prefer dark mode obsidian theme for all dashboard UIs.",
            prompt_id="prompt-test-001",
            category="user_preference",
            sync_to_jsonl=False,
            auto_reconcile=False,
        )
        self.assertFalse(mem1["is_deprecated"])

        # 2. Ingest updated preference without manual supersedes ID
        mem2 = self.pipeline.ingest_prompt(
            raw_text="From now on, switch to warm light stone paper theme for all dashboard UIs, dark mode strains my eyes.",
            prompt_id="prompt-test-002",
            category="user_preference",
            sync_to_jsonl=False,
            auto_reconcile=True,
        )

        # 3. Verify mem2 recorded supersedes link to prompt-test-001
        self.assertIn("prompt-test-001", mem2.get("superseded_records", []))
        self.assertEqual(mem2["supersedes"], "prompt-test-001")
        self.assertFalse(mem2["is_deprecated"])

        # 4. Verify mem1 is now marked deprecated in LanceDB
        table = self.pipeline.store.table
        records = table.to_arrow().to_pylist()
        rec_map = {r["id"]: r for r in records}

        self.assertTrue(rec_map["prompt-test-001"]["is_deprecated"])
        self.assertEqual(rec_map["prompt-test-001"]["superseded_by"], "prompt-test-002")

        # 5. Search active memories - only prompt-test-002 should appear
        active_results = self.pipeline.search(
            raw_query="dashboard UI theme preference",
            include_deprecated=False,
        )
        active_ids = [r["id"] for r in active_results]
        self.assertIn("prompt-test-002", active_ids)
        self.assertNotIn("prompt-test-001", active_ids)

        # 6. With include_deprecated=True, both should appear
        all_results = self.pipeline.search(
            raw_query="dashboard UI theme preference",
            include_deprecated=True,
        )
        all_ids = [r["id"] for r in all_results]
        self.assertIn("prompt-test-001", all_ids)
        self.assertIn("prompt-test-002", all_ids)

    def test_hardware_specification_auto_supersession(self):
        mem1 = self.pipeline.ingest_prompt(
            raw_text="User display devices: Living room TV is TCL 65T8B (65-inch 4K QLED Google TV).",
            prompt_id="prompt-hw-001",
            category="hardware_devices",
            sync_to_jsonl=False,
            auto_reconcile=False,
        )
        self.assertFalse(mem1["is_deprecated"])

        mem2 = self.pipeline.ingest_prompt(
            raw_text="My living room TV is an LG OLED C3 65-inch.",
            prompt_id="prompt-hw-002",
            category="hardware_spec",
            sync_to_jsonl=False,
            auto_reconcile=True,
        )

        self.assertIn("prompt-hw-001", mem2.get("superseded_records", []))
        table = self.pipeline.store.table
        records = {r["id"]: r for r in table.to_arrow().to_pylist()}
        self.assertTrue(records["prompt-hw-001"]["is_deprecated"])
        self.assertEqual(records["prompt-hw-001"]["superseded_by"], "prompt-hw-002")


if __name__ == "__main__":
    unittest.main()

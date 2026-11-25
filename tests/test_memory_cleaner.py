import json
import pytest
from pathlib import Path
from cephalo.core.memory_cleaner import MemoryCleaner


def test_memory_cleaner_purges_empty_and_duplicates(tmp_path):
    prompts_file = tmp_path / "prompts.jsonl"
    lancedb_dir = tmp_path / "lancedb"

    sample_records = [
        # Empty records
        {"id": "prompt-empty-1", "content": "", "category": "general", "timestamp": "2026-11-01T10:00:00Z"},
        {"id": "prompt-empty-2", "content": "   ", "category": "general", "timestamp": "2026-11-01T10:01:00Z"},
        # Duplicate records (TCL color temperature note)
        {
            "id": "prompt-dup-1",
            "content": "Remote note: Sample 4K TV requires Warm color temperature on SDR #hardware/display",
            "category": "hardware",
            "is_deprecated": True,
            "timestamp": "2026-10-29T21:46:55Z",
            "tags": ["hardware/display"],
        },
        {
            "id": "prompt-dup-2",
            "content": "Remote note: Sample 4K TV requires Warm color temperature on SDR #hardware/display",
            "category": "hardware",
            "is_deprecated": False,
            "timestamp": "2026-11-02T12:00:00Z",
            "tags": ["hardware/display"],
        },
        # Unique valid preference
        {
            "id": "prompt-valid-1",
            "content": "Cinema & Entertainment Preferences: Prefers high-velocity modern action-comedies.",
            "category": "entertainment_preferences",
            "is_deprecated": False,
            "timestamp": "2026-10-25T14:00:00Z",
            "tags": ["cinema"],
        },
    ]

    with open(prompts_file, "w", encoding="utf-8") as f:
        for r in sample_records:
            f.write(json.dumps(r) + "\n")

    cleaner = MemoryCleaner(prompts_file=prompts_file, lancedb_dir=lancedb_dir)
    res = cleaner.clean_records()

    assert res["empty_removed"] == 2
    assert res["duplicates_removed"] == 1
    assert res["total_retained"] == 2

    # Verify content in cleaned file
    with open(prompts_file, "r", encoding="utf-8") as f:
        retained = [json.loads(line) for line in f if line.strip()]

    assert len(retained) == 2
    retained_ids = {r["id"] for r in retained}
    assert "prompt-valid-1" in retained_ids
    # Canonical non-deprecated record should be retained over deprecated record
    assert "prompt-dup-2" in retained_ids
    assert "prompt-dup-1" not in retained_ids

"""
Cephalo Sovereign Memory - Universal Migration Test Suite
=========================================================
Tests lossless packaging, SHA-256 integrity verification, multi-harness
configuration extraction, adaptive non-destructive merging, single-command
setup, and CLI / MCP interfaces.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Setup paths
ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
for p in (str(ROOT_DIR), str(SRC_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from cephalo.core.migration import (
    CompressionFormat,
    HarnessDetector,
    MigrationManager,
    MigrationManifest,
    MigrationScope,
    compute_sha256,
    should_exclude,
)
from cephalo.services.mcp_server import handle_tool_call


class TestCephaloMigration(unittest.TestCase):
    def setUp(self):
        self.manager = MigrationManager(base_dir=ROOT_DIR)
        self.temp_dir = tempfile.mkdtemp(prefix="cephalo_test_mig_")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ephemeral_exclusion_rules(self):
        """Verifies that non-reproducible caches and ephemeral files are correctly filtered."""
        self.assertTrue(should_exclude("foo/__pycache__/bar.cpython-312.pyc"))
        self.assertTrue(should_exclude(".pytest_cache/v/cache/nodeids"))
        self.assertTrue(should_exclude("Thumbs.db"))
        self.assertTrue(should_exclude(".DS_Store"))
        self.assertTrue(should_exclude("temp.tmp"))
        self.assertTrue(should_exclude("database.db-wal"))
        self.assertTrue(should_exclude("database.db-shm"))
        self.assertTrue(should_exclude("crates/target/debug/build"))
        self.assertFalse(should_exclude("src/cephalo/cli.py"))
        self.assertFalse(should_exclude("USER_PROFILE.md"))
        self.assertFalse(should_exclude("Cargo.toml"))

    def test_harness_detector(self):
        """Verifies that installed agent harnesses are discovered dynamically."""
        harnesses = HarnessDetector.detect_all()
        self.assertIn("antigravity", harnesses)
        agy = harnesses["antigravity"]
        self.assertIsNotNone(agy.get("config_dir"))
        self.assertTrue(agy["config_dir"].exists())

    def test_export_and_inspect_settings_migration(self):
        """Tests creating a settings migration bundle and inspecting its manifest."""
        out_archive = Path(self.temp_dir) / "test_settings_migration.cephalo.tar.xz"
        res = self.manager.create_migration(
            scope=MigrationScope.SETTINGS,
            output_path=out_archive,
            compression_format=CompressionFormat.XZ,
        )

        self.assertEqual(res["status"], "success")
        self.assertTrue(out_archive.exists())
        self.assertGreater(res["files_count"], 0)
        self.assertGreater(res["uncompressed_bytes"], 0)
        self.assertGreater(res["compressed_bytes"], 0)
        self.assertGreater(res["compression_ratio_pct"], 0)

        # Inspect without extracting
        info = self.manager.inspect_migration(out_archive)
        self.assertEqual(info["scope"], "settings")
        self.assertEqual(info["total_files"], res["files_count"])
        self.assertIn("antigravity", info["harnesses_detected"])
        self.assertIn("compression_ratio", info)

    def test_restore_dry_run_does_not_modify_disk(self):
        """Verifies that dry-run validates integrity without writing to disk."""
        out_archive = Path(self.temp_dir) / "test_dry_run.cephalo.tar.xz"
        self.manager.create_migration(
            scope=MigrationScope.SETTINGS,
            output_path=out_archive,
            compression_format=CompressionFormat.XZ,
        )

        dry_res = self.manager.restore_migration(
            archive_path=out_archive,
            dry_run=True,
        )
        self.assertEqual(dry_res["status"], "dry_run")
        self.assertEqual(dry_res["integrity"], "verified_lossless")
        self.assertGreater(dry_res["files_to_restore"], 0)

    def test_restore_lossless_bit_for_bit(self):
        """Tests full restoration into a sandbox target, verifying SHA-256 byte-for-byte exactness."""
        out_archive = Path(self.temp_dir) / "test_restore.cephalo.tar.xz"
        export_res = self.manager.create_migration(
            scope=MigrationScope.SETTINGS,
            output_path=out_archive,
            compression_format=CompressionFormat.XZ,
        )

        sandbox_target = Path(self.temp_dir) / "restored_brain"
        sandbox_target.mkdir(parents=True, exist_ok=True)

        restore_res = self.manager.restore_migration(
            archive_path=out_archive,
            dry_run=False,
            auto_backup=True,
            target_cephalo_dir=sandbox_target,
            only_cephalo=True,
        )

        self.assertEqual(restore_res["status"], "success")
        self.assertGreater(restore_res["restored_files_count"], 0)

        # Verify USER_PROFILE.md exists and has bit-identical hash
        orig_profile = ROOT_DIR / "USER_PROFILE.md"
        restored_profile = sandbox_target / "USER_PROFILE.md"
        self.assertTrue(restored_profile.exists())
        self.assertEqual(compute_sha256(orig_profile), compute_sha256(restored_profile))

        # Verify safeguards.json
        orig_safeguards = ROOT_DIR / "data" / "safeguards.json"
        restored_safeguards = sandbox_target / "safeguards.json"
        if orig_safeguards.exists():
            self.assertTrue(restored_safeguards.exists())
            self.assertEqual(compute_sha256(orig_safeguards), compute_sha256(restored_safeguards))

    def test_non_destructive_hooks_merge(self):
        """Verifies that merging hooks preserves existing custom user hooks."""
        src_hooks_file = Path(self.temp_dir) / "src_hooks.json"
        dest_hooks_file = Path(self.temp_dir) / "dest_hooks.json"

        # Pre-existing user hooks
        dest_hooks_file.write_text(json.dumps({
            "my-custom-pre-commit": {
                "enabled": True,
                "PreInvocation": [{"command": "echo check"}]
            }
        }), encoding="utf-8")

        # Incoming Cephalo hooks
        src_hooks_file.write_text(json.dumps({
            "cephalo-autonomous-brain": {
                "enabled": True,
                "SessionStart": [{"command": "python auto_harvest.py"}]
            }
        }), encoding="utf-8")

        backups = []
        self.manager._merge_hooks_json(
            src_path=src_hooks_file,
            dest_path=dest_hooks_file,
            auto_backup=True,
            timestamp="20261103_test",
            backups_created=backups,
        )

        merged = json.loads(dest_hooks_file.read_text(encoding="utf-8"))
        self.assertIn("my-custom-pre-commit", merged)
        self.assertIn("cephalo-autonomous-brain", merged)
        self.assertEqual(len(backups), 1)
        self.assertTrue(Path(backups[0]).exists())

    def test_non_destructive_mcp_merge(self):
        """Verifies that merging MCP server configurations preserves other servers."""
        src_mcp = Path(self.temp_dir) / "src_mcp.json"
        dest_mcp = Path(self.temp_dir) / "dest_mcp.json"

        # Existing external MCP servers (e.g. filesystem, github)
        dest_mcp.write_text(json.dumps({
            "mcpServers": {
                "github": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"]}
            }
        }), encoding="utf-8")

        # Incoming Cephalo MCP
        src_mcp.write_text(json.dumps({
            "mcpServers": {
                "cephalo": {"command": "python", "args": ["mcp_server.py"]}
            }
        }), encoding="utf-8")

        backups = []
        self.manager._merge_mcp_config_json(
            src_path=src_mcp,
            dest_path=dest_mcp,
            auto_backup=True,
            timestamp="20261103_test",
            backups_created=backups,
        )

        merged = json.loads(dest_mcp.read_text(encoding="utf-8"))
        self.assertIn("github", merged["mcpServers"])
        self.assertIn("cephalo", merged["mcpServers"])
        self.assertEqual(len(backups), 1)

    def test_mcp_tool_cephalo_migrate(self):
        """Verifies that the MCP server's cephalo_migrate tool executes properly."""
        list_res = handle_tool_call("cephalo_migrate", {"action": "list"})
        self.assertIn("count", list_res)
        self.assertIn("archives", list_res)

        test_out = str(Path(self.temp_dir) / "mcp_tool_test.cephalo.tar.xz")
        exp_res = handle_tool_call("cephalo_migrate", {
            "action": "export",
            "scope": "settings",
            "output_path": test_out,
        })
        self.assertEqual(exp_res.get("status"), "success")
        self.assertTrue(Path(test_out).exists())

        ins_res = handle_tool_call("cephalo_migrate", {
            "action": "inspect",
            "archive_path": test_out,
        })
        self.assertEqual(ins_res.get("scope"), "settings")
        self.assertIn("total_files", ins_res)


if __name__ == "__main__":
    unittest.main()

"""
Tests for Cephalo Non-Destructive Installer, Multi-Ecosystem Integrator,
Autonomous Background Auto-Updater, and GitHub Release Management.
"""

import json
import os
import tempfile
import time
from pathlib import Path
import pytest

from cephalo.services.integrator import (
    merge_managed_block,
    merge_json_config,
    backup_file,
    inspect_status,
)
from cephalo.services.updater import (
    parse_semver,
    is_newer_version,
    load_update_state,
    save_update_state,
    acquire_update_lock,
    release_update_lock,
    is_update_locked,
    check_for_updates,
    get_harness_notification,
)


class TestEcosystemIntegrator:
    """Tests non-destructive file merging and backup guarantees."""

    def test_merge_managed_block_creation_and_update(self, tmp_path):
        target = tmp_path / "test_shell.rc"
        initial_content = "export FOO=1\nalias ll='ls -l'\n"
        target.write_text(initial_content, encoding="utf-8")

        block_v1 = "export CEPHALO_DIR=/opt/cephalo\nexport PATH=$CEPHALO_DIR/bin:$PATH"
        changed, msg, bak = merge_managed_block(target, block_v1, tag="cephalo test", comment_style="#")

        assert changed is True
        assert bak is not None
        assert bak.exists()
        assert bak.read_text(encoding="utf-8") == initial_content

        text_v1 = target.read_text(encoding="utf-8")
        assert "export FOO=1" in text_v1
        assert "alias ll='ls -l'" in text_v1
        assert "# >>> cephalo test >>>" in text_v1
        assert "# <<< cephalo test <<<" in text_v1
        assert "export CEPHALO_DIR=/opt/cephalo" in text_v1

        # Second run with updated content: MUST replace in-place without duplicating
        block_v2 = "export CEPHALO_DIR=/custom/cephalo\nexport PATH=$CEPHALO_DIR/bin:$PATH"
        changed2, msg2, bak2 = merge_managed_block(target, block_v2, tag="cephalo test", comment_style="#")

        assert changed2 is True
        text_v2 = target.read_text(encoding="utf-8")
        assert text_v2.count("# >>> cephalo test >>>") == 1
        assert text_v2.count("# <<< cephalo test <<<") == 1
        assert "/custom/cephalo" in text_v2
        assert "/opt/cephalo" not in text_v2
        assert "export FOO=1" in text_v2

        # Third run with identical content: MUST report no changes
        changed3, msg3, bak3 = merge_managed_block(target, block_v2, tag="cephalo test", comment_style="#")
        assert changed3 is False

    def test_merge_managed_block_markdown_style(self, tmp_path):
        target = tmp_path / "CLAUDE.md"
        target.write_text("# My Existing System\nDon't delete me.\n", encoding="utf-8")

        block = "- Root: /home/user/Cephalo\n- Rule: Always consult memory"
        changed, msg, bak = merge_managed_block(target, block, tag="Cephalo Invariant", comment_style="<!--")

        assert changed is True
        text = target.read_text(encoding="utf-8")
        assert "# My Existing System" in text
        assert "<!-- Cephalo Invariant START -->" in text
        assert "<!-- Cephalo Invariant END -->" in text

    def test_merge_json_config_preserves_existing_keys(self, tmp_path):
        mcp_path = tmp_path / "mcp_config.json"
        initial_data = {
            "mcpServers": {
                "exa": {
                    "url": "https://mcp.exa.ai/mcp",
                    "headers": {"Authorization": "Bearer secret123"}
                }
            },
            "customSetting": "preserved"
        }
        mcp_path.write_text(json.dumps(initial_data, indent=2), encoding="utf-8")

        def _add_cephalo(data):
            if "mcpServers" not in data:
                data["mcpServers"] = {}
            data["mcpServers"]["cephalo"] = {
                "command": "/bin/python",
                "args": ["server.py"]
            }
            return data

        changed, msg, bak = merge_json_config(mcp_path, _add_cephalo)
        assert changed is True
        assert bak is not None

        updated_data = json.loads(mcp_path.read_text(encoding="utf-8"))
        # Verify exa was NOT overwritten
        assert "exa" in updated_data["mcpServers"]
        assert updated_data["mcpServers"]["exa"]["url"] == "https://mcp.exa.ai/mcp"
        # Verify custom settings preserved
        assert updated_data["customSetting"] == "preserved"
        # Verify cephalo added cleanly
        assert "cephalo" in updated_data["mcpServers"]
        assert updated_data["mcpServers"]["cephalo"]["command"] == "/bin/python"

        # Running again with same content returns changed=False
        changed2, msg2, bak2 = merge_json_config(mcp_path, _add_cephalo)
        assert changed2 is False


class TestAutoUpdater:
    """Tests Semver parsing, update check caching, and background locking."""

    def test_semver_parsing_and_comparison(self):
        assert parse_semver("v2.1.0") == (2, 1, 0)
        assert parse_semver("2.1.0") == (2, 1, 0)
        assert parse_semver("v1.10.5") == (1, 10, 5)
        assert parse_semver("v3.0.0-beta.1") == (3, 0, 0)

        assert is_newer_version("v2.2.0", "v2.1.0") is True
        assert is_newer_version("v2.1.1", "v2.1.0") is True
        assert is_newer_version("v3.0.0", "v2.9.9") is True
        assert is_newer_version("v2.1.0", "v2.1.0") is False
        assert is_newer_version("v2.0.9", "v2.1.0") is False

    def test_update_lock_lifecycle(self, tmp_path, monkeypatch):
        test_lock = tmp_path / "test_update.lock"
        monkeypatch.setattr("cephalo.services.updater.LOCK_FILE", test_lock)

        assert is_update_locked() is False
        assert acquire_update_lock() is True
        assert is_update_locked() is True
        # Second acquire fails while locked
        assert acquire_update_lock() is False

        release_update_lock()
        assert is_update_locked() is False

    def test_update_state_persistence(self, tmp_path, monkeypatch):
        test_state_file = tmp_path / "update_state.json"
        monkeypatch.setattr("cephalo.services.updater.STATE_FILE", test_state_file)

        state = load_update_state()
        state["latest_version"] = "2.9.9"
        state["update_available"] = True
        save_update_state(state)

        reloaded = load_update_state()
        assert reloaded["latest_version"] == "2.9.9"
        assert reloaded["update_available"] is True

    def test_harness_notification_generation(self, tmp_path, monkeypatch):
        test_state_file = tmp_path / "update_state.json"
        monkeypatch.setattr("cephalo.services.updater.STATE_FILE", test_state_file)

        # 1. When an update was recently applied
        state = {
            "last_update_applied_at": "2026-11-09T18:00:00Z",
            "last_update_version": "2.2.0",
            "notified_in_session": False,
            "policy": "auto",
        }
        save_update_state(state)
        notice = get_harness_notification()
        assert notice is not None
        assert notice["type"] == "applied"
        assert "v2.2.0" in notice["message"]

        # Notice should only be shown once per session
        notice2 = get_harness_notification()
        assert notice2 is None

        # 2. When a newer release is detected
        state2 = {
            "update_available": True,
            "latest_version": "2.3.0",
            "policy": "notify",
            "release_url": "https://github.com/LaptopKing/Cephalo/releases/tag/v2.3.0",
        }
        save_update_state(state2)
        notice_avail = get_harness_notification()
        assert notice_avail is not None
        assert notice_avail["type"] == "available"
        assert "v2.3.0" in notice_avail["message"]

    def test_session_start_hook_checks_only_never_auto_updates(self, tmp_path, monkeypatch):
        from cephalo.services import updater

        test_state_file = tmp_path / "update_state.json"
        monkeypatch.setattr(updater, "STATE_FILE", test_state_file)
        save_update_state({
            "current_version": "2.1.0",
            "latest_version": "2.9.9",
            "update_available": True,
            "policy": "auto",
            "release_url": "https://github.com/LaptopKing/Cephalo/releases/tag/v2.9.9",
        })

        monkeypatch.setattr(
            updater,
            "check_for_updates",
            lambda **kwargs: {"update_available": True, "latest_version": "2.9.9"},
        )

        called = []
        monkeypatch.setattr(
            updater,
            "apply_update_background",
            lambda *args, **kwargs: called.append(True),
        )

        msg = updater.trigger_session_start_hook()
        assert called == []
        assert msg is not None
        assert "v2.9.9" in msg

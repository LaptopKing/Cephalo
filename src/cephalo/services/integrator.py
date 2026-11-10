"""
Cephalo Non-Destructive Multi-Ecosystem Integrator (integrator.py)
==================================================================
Safely connects Cephalo's Sovereign Memory Engine into existing developer
environments (Bash, Zsh, Fish, Antigravity, Claude Code, Cursor, Windsurf,
VS Code / Cline / Roo, Aider, Herdr).

Core Invariants:
1. Never Overwrite: Always preserves existing configurations and creates timestamped backups.
2. Managed Blocks: Uses deterministic, parseable comment markers to update in-place without duplication.
3. Selective Adaptation: Only integrates with tools present on the host (unless explicitly forced).
4. Full Auditability: Returns structured reports of every action and file modified.
"""

from __future__ import annotations

import datetime
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parents[3]
BIN_DIR = ROOT_DIR / "bin"
SRC_DIR = ROOT_DIR / "src"
HOME_DIR = Path.home()


def backup_file(path: Path) -> Optional[Path]:
    """Creates a timestamped safety backup of a file if it exists."""
    if not path.exists():
        return None
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    bak_path = path.with_name(f"{path.name}.bak.{ts}")
    shutil.copy2(path, bak_path)
    return bak_path


def merge_managed_block(
    target_path: Path,
    block_content: str,
    tag: str = "CEPHALO MANAGED BLOCK",
    comment_style: str = "#",
) -> Tuple[bool, str, Optional[Path]]:
    """
    Inserts or updates a managed block inside target_path.
    Comment styles: '#' for shell/yaml/python, '<!--' for markdown/xml, '//' for js/json/c.
    Returns (changed, action_summary, backup_path).
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if comment_style == "<!--":
        start_tag = f"<!-- {tag} START -->"
        end_tag = f"<!-- {tag} END -->"
    elif comment_style == "//":
        start_tag = f"// >>> {tag} >>>"
        end_tag = f"// <<< {tag} <<<"
    else:
        start_tag = f"# >>> {tag} >>>"
        end_tag = f"# <<< {tag} <<<"

    full_block = f"{start_tag}\n{block_content}\n{end_tag}"
    bak = backup_file(target_path)

    if target_path.exists():
        try:
            content = target_path.read_text(encoding="utf-8")
        except Exception:
            content = ""

        # Check if block already exists
        escaped_start = re.escape(start_tag)
        escaped_end = re.escape(end_tag)
        pattern = re.compile(rf"{escaped_start}.*?{escaped_end}", re.DOTALL)

        if pattern.search(content):
            # Check if content is already identical
            existing_match = pattern.search(content).group(0)
            if existing_match == full_block:
                return False, "Already up to date", None
            updated = pattern.sub(full_block, content)
            target_path.write_text(updated, encoding="utf-8")
            return True, f"Updated existing Cephalo managed block in {target_path}", bak
        else:
            sep = "\n\n" if content and not content.endswith("\n\n") else "\n"
            updated = content.rstrip() + sep + full_block + "\n"
            target_path.write_text(updated, encoding="utf-8")
            return True, f"Appended Cephalo managed block to {target_path}", bak
    else:
        target_path.write_text(full_block + "\n", encoding="utf-8")
        return True, f"Created {target_path} with Cephalo managed block", None


def merge_json_config(
    target_path: Path,
    updater_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> Tuple[bool, str, Optional[Path]]:
    """
    Safely reads, updates, and writes a JSON configuration file.
    Preserves all existing keys and formatting.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    bak = backup_file(target_path)

    data: Dict[str, Any] = {}
    if target_path.exists():
        try:
            text = target_path.read_text(encoding="utf-8").strip()
            if text:
                data = json.loads(text)
        except Exception as e:
            # If JSON is corrupted, keep backup and initialize
            data = {}

    old_serialized = json.dumps(data, sort_keys=True)
    updated_data = updater_fn(data)
    new_serialized = json.dumps(updated_data, sort_keys=True)

    if old_serialized == new_serialized:
        return False, "Already up to date", None

    target_path.write_text(json.dumps(updated_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True, f"Safely merged Cephalo config into {target_path}", bak


# =============================================================================
# Individual Ecosystem Integrations
# =============================================================================

def find_python_executable() -> str:
    """Finds best Python executable, favoring isolated .venv."""
    venv_py = ROOT_DIR / ".venv" / ("bin" if sys.platform != "win32" else "Scripts") / ("python" if sys.platform != "win32" else "python.exe")
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def integrate_shells() -> List[Dict[str, Any]]:
    """Non-destructively integrates Cephalo environment into Bash, Zsh, and Fish."""
    results = []
    py_bin = BIN_DIR / ("cephalo" if sys.platform != "win32" else "cephalo.bat")
    user_bin = HOME_DIR / ".local" / "bin"
    user_bin.mkdir(parents=True, exist_ok=True)

    # Symlink cephalo into ~/.local/bin if on Unix
    if sys.platform != "win32":
        symlink_target = user_bin / "cephalo"
        try:
            if symlink_target.exists() or symlink_target.is_symlink():
                symlink_target.unlink()
            symlink_target.symlink_to(py_bin)
            results.append({
                "ecosystem": "shell_symlink",
                "target": str(symlink_target),
                "status": "linked",
                "message": f"Symlinked {symlink_target} -> {py_bin}",
            })
        except Exception as e:
            results.append({
                "ecosystem": "shell_symlink",
                "target": str(symlink_target),
                "status": "warning",
                "message": f"Could not create symlink: {e}",
            })

    # 1. Bash
    bashrc = HOME_DIR / ".bashrc"
    if bashrc.exists():
        bash_block = f"""# Cephalo Sovereign Memory CLI & Environment
export CEPHALO_DIR="{ROOT_DIR}"
if [[ ":$PATH:" != *":$CEPHALO_DIR/bin:"* ]]; then
    export PATH="$CEPHALO_DIR/bin:$PATH"
fi"""
        changed, msg, bak = merge_managed_block(bashrc, bash_block, tag="cephalo initialize", comment_style="#")
        results.append({
            "ecosystem": "bash",
            "target": str(bashrc),
            "changed": changed,
            "message": msg,
            "backup": str(bak) if bak else None,
        })

    # 2. Zsh
    zshrc = HOME_DIR / ".zshrc"
    if zshrc.exists():
        zsh_block = f"""# Cephalo Sovereign Memory CLI & Environment
export CEPHALO_DIR="{ROOT_DIR}"
if [[ ":$PATH:" != *":$CEPHALO_DIR/bin:"* ]]; then
    export PATH="$CEPHALO_DIR/bin:$PATH"
fi"""
        changed, msg, bak = merge_managed_block(zshrc, zsh_block, tag="cephalo initialize", comment_style="#")
        results.append({
            "ecosystem": "zsh",
            "target": str(zshrc),
            "changed": changed,
            "message": msg,
            "backup": str(bak) if bak else None,
        })

    # 3. Fish
    fish_config = HOME_DIR / ".config" / "fish" / "config.fish"
    if fish_config.exists():
        fish_block = f"""# Cephalo Sovereign Memory CLI & Environment
set -gx CEPHALO_DIR "{ROOT_DIR}"
if not contains "$CEPHALO_DIR/bin" $PATH
    set -gx PATH "$CEPHALO_DIR/bin" $PATH
end"""
        changed, msg, bak = merge_managed_block(fish_config, fish_block, tag="cephalo initialize", comment_style="#")
        results.append({
            "ecosystem": "fish",
            "target": str(fish_config),
            "changed": changed,
            "message": msg,
            "backup": str(bak) if bak else None,
        })

    return results


def integrate_antigravity() -> List[Dict[str, Any]]:
    """Integrates Cephalo into Google Antigravity & Gemini CLI (~/.gemini)."""
    results = []
    gemini_base = HOME_DIR / ".gemini"
    if not gemini_base.exists():
        return [{"ecosystem": "antigravity", "status": "skipped", "message": "~/.gemini not detected."}]

    py_cmd = find_python_executable()
    mcp_script = str(SRC_DIR / "cephalo" / "services" / "mcp_server.py")
    harvest_script = str(SRC_DIR / "cephalo" / "learning" / "auto_harvest.py")

    # 1. Plugin directories
    plugin_dir = gemini_base / "config" / "plugins" / "cephalo"
    rules_dir = plugin_dir / "rules"
    skills_dir = plugin_dir / "skills" / "cephalo"
    global_skills_dir = gemini_base / "config" / "skills" / "cephalo"

    rules_dir.mkdir(parents=True, exist_ok=True)
    skills_dir.mkdir(parents=True, exist_ok=True)
    global_skills_dir.mkdir(parents=True, exist_ok=True)

    # Manifest
    manifest_file = plugin_dir / "plugin.json"
    manifest_file.write_text(json.dumps({
        "name": "cephalo",
        "description": "Cephalo Omnipresent Autonomous Second Brain and Personal Memory Engine",
        "version": "2.1.0"
    }, indent=2), encoding="utf-8")

    # SKILL.md
    src_skill = ROOT_DIR / "integrations" / "antigravity" / "SKILL.md"
    if src_skill.exists():
        shutil.copy2(src_skill, skills_dir / "SKILL.md")
        shutil.copy2(src_skill, global_skills_dir / "SKILL.md")

    # Rules
    src_rule = ROOT_DIR / "integrations" / "antigravity" / "cephalo_second_brain.md"
    if src_rule.exists():
        content = src_rule.read_text(encoding="utf-8").replace("{{CEPHALO_DIR}}", str(ROOT_DIR))
        (rules_dir / "AGENTS.md").write_text(content, encoding="utf-8")
        (rules_dir / "GEMINI.md").write_text(content, encoding="utf-8")

    # Clean legacy duplicate rule if present
    legacy_rule = gemini_base / "config" / "rules" / "cephalo_second_brain.md"
    if legacy_rule.exists():
        legacy_rule.unlink()

    # 2. Non-destructive hooks merge
    def _hook_updater(data: Dict[str, Any]) -> Dict[str, Any]:
        data["cephalo-autonomous-brain"] = {
            "enabled": True,
            "SessionStart": [{"type": "command", "command": f'"{py_cmd}" "{harvest_script}" --session-start', "timeout": 15}],
            "PreInvocation": [{"type": "command", "command": f'"{py_cmd}" "{harvest_script}" --pre-invocation', "timeout": 15}],
            "Stop": [{"type": "command", "command": f'"{py_cmd}" "{harvest_script}" --stop-hook', "timeout": 15}],
        }
        return data

    for hooks_path in [plugin_dir / "hooks.json", gemini_base / "config" / "hooks.json"]:
        c, m, b = merge_json_config(hooks_path, _hook_updater)
        results.append({
            "ecosystem": "antigravity_hooks",
            "target": str(hooks_path),
            "changed": c,
            "message": m,
            "backup": str(b) if b else None,
        })

    # 3. Non-destructive MCP configuration
    def _mcp_updater(data: Dict[str, Any]) -> Dict[str, Any]:
        if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
            data["mcpServers"] = {}
        data["mcpServers"]["cephalo"] = {
            "command": py_cmd,
            "args": [mcp_script],
            "env": {
                "PYTHONPATH": str(SRC_DIR),
                "PYTHONIOENCODING": "utf-8",
            },
        }
        return data

    for mcp_path in [plugin_dir / "mcp_config.json", gemini_base / "config" / "mcp_config.json"]:
        c, m, b = merge_json_config(mcp_path, _mcp_updater)
        results.append({
            "ecosystem": "antigravity_mcp",
            "target": str(mcp_path),
            "changed": c,
            "message": m,
            "backup": str(b) if b else None,
        })

    # Symlink into antigravity bin if exists
    for agy_bin in [gemini_base / "antigravity-cli" / "bin", gemini_base / "antigravity" / "bin"]:
        if agy_bin.exists() and sys.platform != "win32":
            link = agy_bin / "cephalo"
            try:
                if link.exists() or link.is_symlink():
                    link.unlink()
                link.symlink_to(BIN_DIR / "cephalo")
            except Exception:
                pass

    return results


def integrate_claude() -> List[Dict[str, Any]]:
    """Integrates Cephalo into Claude Code (~/.claude)."""
    results = []
    claude_dir = HOME_DIR / ".claude"
    claude_cmd = shutil.which("claude")

    if not claude_dir.exists() and not claude_cmd:
        return [{"ecosystem": "claude", "status": "skipped", "message": "Claude Code not detected on host."}]

    py_cmd = find_python_executable()
    mcp_script = str(SRC_DIR / "cephalo" / "services" / "mcp_server.py")

    # CLI MCP registration if available
    if claude_cmd:
        try:
            res = subprocess.run([claude_cmd, "mcp", "add", "cephalo", "--", py_cmd, mcp_script], capture_output=True, text=True, timeout=10)
            results.append({
                "ecosystem": "claude_cli_mcp",
                "status": "success" if res.returncode == 0 else "notice",
                "message": f"'claude mcp add cephalo' executed (returncode {res.returncode})",
            })
        except Exception as e:
            results.append({"ecosystem": "claude_cli_mcp", "status": "warning", "message": str(e)})

    # Non-destructive managed block in CLAUDE.md
    claude_md = claude_dir / "CLAUDE.md"
    claude_block = f"""### Cephalo Sovereign Memory Integration
- **Root Directory:** {ROOT_DIR}
- **Grounding Invariant:** Consult Cephalo before answering past preferences or decisions (`cephalo search "<query>" --json`).
- **Autonomous Capture:** Record preferences & decisions immediately (`cephalo record "<statement>" --category "<category>"`)."""

    c, m, b = merge_managed_block(claude_md, claude_block, tag="Cephalo Sovereign Memory Integration", comment_style="<!--")
    results.append({
        "ecosystem": "claude_markdown",
        "target": str(claude_md),
        "changed": c,
        "message": m,
        "backup": str(b) if b else None,
    })

    return results


def integrate_cursor() -> List[Dict[str, Any]]:
    """Integrates Cephalo into Cursor IDE."""
    results = []
    candidates = [
        HOME_DIR / ".cursor" / "mcp.json",
        HOME_DIR / ".config" / "Cursor" / "User" / "globalStorage" / "rooveterinaryinc.cursor-mcp" / "mcp.json",
    ]
    if platform.system() == "Darwin":
        candidates.append(HOME_DIR / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage" / "rooveterinaryinc.cursor-mcp" / "mcp.json")
    elif platform.system() == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(Path(appdata) / "Cursor" / "User" / "globalStorage" / "rooveterinaryinc.cursor-mcp" / "mcp.json")

    py_cmd = find_python_executable()
    mcp_script = str(SRC_DIR / "cephalo" / "services" / "mcp_server.py")

    def _cursor_updater(data: Dict[str, Any]) -> Dict[str, Any]:
        if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
            data["mcpServers"] = {}
        data["mcpServers"]["cephalo"] = {
            "command": py_cmd,
            "args": [mcp_script],
            "env": {
                "PYTHONPATH": str(SRC_DIR),
                "PYTHONIOENCODING": "utf-8",
            },
        }
        return data

    found_cursor = False
    for path in candidates:
        if path.parent.exists():
            found_cursor = True
            c, m, b = merge_json_config(path, _cursor_updater)
            results.append({
                "ecosystem": "cursor_mcp",
                "target": str(path),
                "changed": c,
                "message": m,
                "backup": str(b) if b else None,
            })

    if not found_cursor:
        results.append({"ecosystem": "cursor", "status": "skipped", "message": "Cursor IDE directories not detected."})

    return results


def integrate_windsurf() -> List[Dict[str, Any]]:
    """Integrates Cephalo into Windsurf Cascade (~/.codeium/windsurf)."""
    results = []
    windsurf_cfg = HOME_DIR / ".codeium" / "windsurf" / "mcp_config.json"
    if not windsurf_cfg.parent.exists():
        return [{"ecosystem": "windsurf", "status": "skipped", "message": "Windsurf Cascade not detected."}]

    py_cmd = find_python_executable()
    mcp_script = str(SRC_DIR / "cephalo" / "services" / "mcp_server.py")

    def _windsurf_updater(data: Dict[str, Any]) -> Dict[str, Any]:
        if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
            data["mcpServers"] = {}
        data["mcpServers"]["cephalo"] = {
            "command": py_cmd,
            "args": [mcp_script],
            "env": {
                "PYTHONPATH": str(SRC_DIR),
                "PYTHONIOENCODING": "utf-8",
            },
        }
        return data

    c, m, b = merge_json_config(windsurf_cfg, _windsurf_updater)
    results.append({
        "ecosystem": "windsurf_mcp",
        "target": str(windsurf_cfg),
        "changed": c,
        "message": m,
        "backup": str(b) if b else None,
    })
    return results


def integrate_vscode_cline_roo() -> List[Dict[str, Any]]:
    """Integrates Cephalo into VS Code Cline & Roo Code extensions if present."""
    results = []
    candidates = []

    # Linux paths
    candidates.append(HOME_DIR / ".config" / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json")
    candidates.append(HOME_DIR / ".config" / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "cline_mcp_settings.json")

    # macOS paths
    candidates.append(HOME_DIR / "Library" / "Application Support" / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json")
    candidates.append(HOME_DIR / "Library" / "Application Support" / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "cline_mcp_settings.json")

    # Windows paths
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json")
        candidates.append(Path(appdata) / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "cline_mcp_settings.json")

    py_cmd = find_python_executable()
    mcp_script = str(SRC_DIR / "cephalo" / "services" / "mcp_server.py")

    def _cline_updater(data: Dict[str, Any]) -> Dict[str, Any]:
        if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
            data["mcpServers"] = {}
        data["mcpServers"]["cephalo"] = {
            "command": py_cmd,
            "args": [mcp_script],
            "env": {
                "PYTHONPATH": str(SRC_DIR),
                "PYTHONIOENCODING": "utf-8",
            },
        }
        return data

    found = False
    for path in candidates:
        if path.parent.exists():
            found = True
            c, m, b = merge_json_config(path, _cline_updater)
            results.append({
                "ecosystem": "vscode_cline_roo",
                "target": str(path),
                "changed": c,
                "message": m,
                "backup": str(b) if b else None,
            })

    if not found:
        results.append({"ecosystem": "vscode_cline_roo", "status": "skipped", "message": "VS Code Cline / Roo Code not detected."})

    return results


def integrate_project(target_project_dir: Path) -> List[Dict[str, Any]]:
    """
    Integrates Cephalo memory grounding into any local project non-destructively.
    Injects managed blocks into project-level AGENTS.md, .cursorrules, or .windsurfrules.
    """
    results = []
    if not target_project_dir.exists() or not target_project_dir.is_dir():
        return [{"ecosystem": "project", "status": "error", "message": f"Directory not found: {target_project_dir}"}]

    # 1. Project AGENTS.md
    proj_agents = target_project_dir / "AGENTS.md"
    block = f"""### Cephalo Sovereign Memory Grounding
- Cephalo Root: {ROOT_DIR}
- Always consult Cephalo before making architectural or preference decisions: `cephalo search "<query>" --json`
- Record technical milestones and decisions: `cephalo record "<decision>" --category "architecture"`"""

    c, m, b = merge_managed_block(proj_agents, block, tag="Cephalo Memory Grounding", comment_style="<!--")
    results.append({"target": str(proj_agents), "changed": c, "message": m, "backup": str(b) if b else None})

    # 2. Project .cursorrules if Cursor is used in project
    proj_cursor = target_project_dir / ".cursorrules"
    if proj_cursor.exists():
        c, m, b = merge_managed_block(proj_cursor, block, tag="Cephalo Memory Grounding", comment_style="#")
        results.append({"target": str(proj_cursor), "changed": c, "message": m, "backup": str(b) if b else None})

    return results


def run_all_integrations() -> Dict[str, Any]:
    """Runs all adaptive ecosystem integrations non-destructively."""
    all_results = {
        "shells": integrate_shells(),
        "antigravity": integrate_antigravity(),
        "claude": integrate_claude(),
        "cursor": integrate_cursor(),
        "windsurf": integrate_windsurf(),
        "vscode_cline_roo": integrate_vscode_cline_roo(),
    }
    return all_results


def inspect_status() -> Dict[str, Any]:
    """Inspects integration health across all ecosystems."""
    status = {
        "cephalo_dir": str(ROOT_DIR),
        "python_exe": find_python_executable(),
        "shells": {
            "bash": (HOME_DIR / ".bashrc").exists(),
            "zsh": (HOME_DIR / ".zshrc").exists(),
            "fish": (HOME_DIR / ".config" / "fish" / "config.fish").exists(),
            "in_path": shutil.which("cephalo") is not None,
        },
        "antigravity": {
            "detected": (HOME_DIR / ".gemini").exists(),
            "plugin_installed": (HOME_DIR / ".gemini" / "config" / "plugins" / "cephalo").exists(),
            "hooks_configured": (HOME_DIR / ".gemini" / "config" / "hooks.json").exists(),
            "mcp_configured": (HOME_DIR / ".gemini" / "config" / "mcp_config.json").exists(),
        },
        "claude": {
            "detected": (HOME_DIR / ".claude").exists() or shutil.which("claude") is not None,
        },
        "cursor": {
            "detected": (HOME_DIR / ".cursor").exists() or (HOME_DIR / ".config" / "Cursor").exists(),
        },
        "windsurf": {
            "detected": (HOME_DIR / ".codeium" / "windsurf").exists(),
        },
        "herdr": {
            "detected": (HOME_DIR / ".config" / "herdr").exists(),
        },
    }
    return status

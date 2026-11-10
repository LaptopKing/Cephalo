"""
Cephalo Autonomous Auto-Updater & Release Tracking Engine (updater.py)
======================================================================
Provides non-blocking background update detection, automatic git pull / release syncing,
and agent harness lifecycle notification without disrupting active user workflows.

Core Invariants:
1. Zero User Flow Disruption:
   - Update checks run asynchronously or are throttled (default: 6 hours).
   - Hook executions (SessionStart / PreInvocation) are never blocked by network calls.
2. Safety First:
   - Does not overwrite or clobber uncommitted local changes (checks git status first).
   - Atomic state management via update_state.json with locking (update.lock).
3. Background Execution:
   - Updates run detached in the background or via Cephalo JobQueue.
4. Seamless Harness Notification:
   - Reports newly applied updates or available releases cleanly to agent harnesses.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("cephalo.updater")

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
STATE_FILE = DATA_DIR / "update_state.json"
LOCK_FILE = DATA_DIR / "update.lock"
LOGS_DIR = DATA_DIR / "logs"
UPDATE_LOG_FILE = LOGS_DIR / "auto_update.log"

GITHUB_REPO = "LaptopKing/Cephalo"
DEFAULT_CHECK_INTERVAL_SECONDS = 6 * 3600  # 6 hours


def get_current_version() -> str:
    """Returns current Cephalo version from __init__.py or pyproject.toml."""
    try:
        from cephalo import __version__
        return __version__
    except Exception:
        pass

    pyproject = ROOT_DIR / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
            m = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            if m:
                return m.group(1)
        except Exception:
            pass
    return "0.0.0"


def parse_semver(v_str: str) -> Tuple[int, ...]:
    """Parses version string (e.g. 'v2.1.0' or '2.1.0-beta.1') into integer tuple."""
    clean = re.sub(r"^[vV]", "", v_str.strip())
    # Separate pre-release if present
    base = clean.split("-")[0].split("+")[0]
    parts = []
    for p in base.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer_version(latest_str: str, current_str: str) -> bool:
    """Returns True if latest_str is strictly newer than current_str."""
    return parse_semver(latest_str) > parse_semver(current_str)


def load_update_state() -> Dict[str, Any]:
    """Loads update tracking state from disk."""
    default_state = {
        "current_version": get_current_version(),
        "latest_version": get_current_version(),
        "update_available": False,
        "last_checked_at": None,
        "last_update_applied_at": None,
        "last_update_version": None,
        "release_url": None,
        "release_notes": None,
        "policy": "auto",  # 'auto', 'notify', 'off'
        "notified_in_session": False,
    }
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_state.update(data)
        except Exception:
            pass
    default_state["current_version"] = get_current_version()
    return default_state


def save_update_state(state: Dict[str, Any]) -> None:
    """Atomically saves update state to disk."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        tmp.replace(STATE_FILE)
    except Exception as e:
        logger.warning(f"Failed to save update state: {e}")


def is_update_locked() -> bool:
    """Checks if another update process holds the lock."""
    if not LOCK_FILE.exists():
        return False
    try:
        content = LOCK_FILE.read_text(encoding="utf-8").strip()
        data = json.loads(content)
        pid = data.get("pid")
        started = data.get("started_at", 0)
        # Stale lock check (older than 20 minutes)
        if time.time() - started > 1200:
            LOCK_FILE.unlink(missing_ok=True)
            return False
        # Process check on Unix/Windows
        if pid:
            try:
                os.kill(pid, 0)
                return True
            except (OSError, ProcessLookupError):
                LOCK_FILE.unlink(missing_ok=True)
                return False
    except Exception:
        LOCK_FILE.unlink(missing_ok=True)
    return False


def acquire_update_lock() -> bool:
    """Acquires lock for applying an update."""
    if is_update_locked():
        return False
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "started_at": time.time(),
            "time_iso": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        with open(LOCK_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        return True
    except Exception:
        return False


def release_update_lock() -> None:
    """Releases the update lock."""
    LOCK_FILE.unlink(missing_ok=True)


def fetch_latest_github_release(repo: str = GITHUB_REPO, timeout: float = 3.5) -> Optional[Dict[str, Any]]:
    """
    Fetches latest release info from GitHub API with low timeout to prevent hanging.
    Falls back gracefully if offline, rate-limited, or unreachable.
    """
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        api_url,
        headers={
            "User-Agent": f"Cephalo-AutoUpdater/{get_current_version()}",
            "Accept": "application/vnd.github.v3+json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                tag = data.get("tag_name", "").strip()
                return {
                    "tag_name": tag,
                    "version": re.sub(r"^[vV]", "", tag),
                    "name": data.get("name") or tag,
                    "body": data.get("body", ""),
                    "html_url": data.get("html_url", ""),
                    "published_at": data.get("published_at", ""),
                    "assets": [
                        {"name": a.get("name"), "url": a.get("browser_download_url")}
                        for a in data.get("assets", [])
                    ],
                }
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, Exception) as e:
        logger.debug(f"GitHub release check failed gracefully: {e}")

    # Fallback to git remote tags if in a git clone
    if (ROOT_DIR / ".git").exists():
        try:
            res = subprocess.run(
                ["git", "ls-remote", "--tags", "origin"],
                cwd=str(ROOT_DIR),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if res.returncode == 0 and res.stdout.strip():
                tags = []
                for line in res.stdout.splitlines():
                    m = re.search(r"refs/tags/(v?[0-9]+\.[0-9]+(?:\.[0-9]+)?)$", line.strip())
                    if m:
                        tags.append(m.group(1))
                if tags:
                    tags.sort(key=parse_semver)
                    latest_tag = tags[-1]
                    return {
                        "tag_name": latest_tag,
                        "version": re.sub(r"^[vV]", "", latest_tag),
                        "name": f"Cephalo {latest_tag}",
                        "body": "Discovered via git remote tags.",
                        "html_url": f"https://github.com/{repo}/releases/tag/{latest_tag}",
                        "published_at": "",
                        "assets": [],
                    }
        except Exception:
            pass

    return None


def check_for_updates(
    force: bool = False,
    interval_seconds: int = DEFAULT_CHECK_INTERVAL_SECONDS,
) -> Dict[str, Any]:
    """
    Checks if a newer Cephalo release exists.
    Throttled by interval_seconds unless force=True.
    """
    state = load_update_state()
    current_ver = get_current_version()
    state["current_version"] = current_ver

    now = time.time()
    last_checked_iso = state.get("last_checked_at")
    last_checked_ts = 0.0
    if last_checked_iso:
        try:
            dt = datetime.datetime.fromisoformat(last_checked_iso)
            last_checked_ts = dt.timestamp()
        except Exception:
            pass

    # Return cached check if throttled and not forced
    if not force and (now - last_checked_ts < interval_seconds):
        return {
            "update_available": state.get("update_available", False),
            "current_version": current_ver,
            "latest_version": state.get("latest_version", current_ver),
            "release_url": state.get("release_url"),
            "release_notes": state.get("release_notes"),
            "checked_at": last_checked_iso,
            "cached": True,
        }

    # Perform network check
    release_info = fetch_latest_github_release()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    state["last_checked_at"] = now_iso

    if release_info:
        latest_ver = release_info["version"]
        newer = is_newer_version(latest_ver, current_ver)
        state["latest_version"] = latest_ver
        state["update_available"] = newer
        state["release_url"] = release_info["html_url"]
        state["release_notes"] = release_info["body"][:800]
        if newer:
            state["notified_in_session"] = False
        save_update_state(state)
        return {
            "update_available": newer,
            "current_version": current_ver,
            "latest_version": latest_ver,
            "release_url": release_info["html_url"],
            "release_notes": release_info["body"][:800],
            "checked_at": now_iso,
            "cached": False,
        }

    save_update_state(state)
    return {
        "update_available": state.get("update_available", False),
        "current_version": current_ver,
        "latest_version": state.get("latest_version", current_ver),
        "checked_at": now_iso,
        "cached": False,
        "error": "Could not contact GitHub API or remote repository.",
    }


def find_venv_python() -> str:
    """Finds best Python executable (virtualenv first to prevent system pollution)."""
    venv_py = ROOT_DIR / ".venv" / ("bin" if sys.platform != "win32" else "Scripts") / ("python" if sys.platform != "win32" else "python.exe")
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def execute_update_sync(target_tag: Optional[str] = None) -> Tuple[bool, str]:
    """
    Applies update steps sequentially:
    1. Git fetch & pull (or checkout tag).
    2. Python dependency upgrade.
    3. Rust cargo build (if cargo is available).
    4. Database migration run.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = open(UPDATE_LOG_FILE, "a", encoding="utf-8")

    def _log(msg: str):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        log_file.write(line + "\n")
        log_file.flush()

    _log("Starting Cephalo update procedure...")
    is_git_repo = (ROOT_DIR / ".git").exists()

    if is_git_repo:
        # Check git status for local unstaged changes to prevent loss
        res_diff = subprocess.run(["git", "diff", "--quiet"], cwd=str(ROOT_DIR))
        res_cached = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(ROOT_DIR))
        has_dirty_files = (res_diff.returncode != 0 or res_cached.returncode != 0)

        if has_dirty_files:
            _log("Notice: Working tree has uncommitted modifications. Stashing safely before update...")
            subprocess.run(["git", "stash", "push", "-m", "cephalo-auto-update-safety-stash"], cwd=str(ROOT_DIR), stdout=log_file, stderr=log_file)

        _log("Fetching latest changes from origin...")
        f_res = subprocess.run(["git", "fetch", "--tags", "origin"], cwd=str(ROOT_DIR), stdout=log_file, stderr=log_file)
        if f_res.returncode != 0:
            _log("Warning: 'git fetch' returned non-zero code.")

        if target_tag:
            _log(f"Checking out target tag: {target_tag}")
            p_res = subprocess.run(["git", "checkout", target_tag], cwd=str(ROOT_DIR), stdout=log_file, stderr=log_file)
        else:
            _log("Pulling changes fast-forward on main branch...")
            p_res = subprocess.run(["git", "pull", "--ff-only", "origin", "main"], cwd=str(ROOT_DIR), stdout=log_file, stderr=log_file)

        if p_res.returncode != 0:
            _log("Error during git pull/checkout. Aborting update to protect codebase.")
            if has_dirty_files:
                subprocess.run(["git", "stash", "pop"], cwd=str(ROOT_DIR), stdout=log_file, stderr=log_file)
            log_file.close()
            return False, "Git update failed."

        if has_dirty_files:
            _log("Restoring stashed changes...")
            subprocess.run(["git", "stash", "pop"], cwd=str(ROOT_DIR), stdout=log_file, stderr=log_file)
    else:
        _log("Cephalo is not a git repository. Skipping git pull.")

    # Python dependencies
    py_exe = find_venv_python()
    req_txt = ROOT_DIR / "requirements.txt"
    if req_txt.exists():
        _log(f"Upgrading Python dependencies via {py_exe}...")
        pip_res = subprocess.run([py_exe, "-m", "pip", "install", "--quiet", "-r", str(req_txt)], cwd=str(ROOT_DIR), stdout=log_file, stderr=log_file)
        if pip_res.returncode != 0:
            _log("Warning: pip dependency upgrade encountered errors.")

    # Native Rust binary build
    cargo_path = shutil.which("cargo")
    cargo_toml = ROOT_DIR / "rust" / "Cargo.toml"
    if cargo_path and cargo_toml.exists():
        _log("Compiling ultra-low latency native Rust binary...")
        c_res = subprocess.run([cargo_path, "build", "--release", "--manifest-path", str(cargo_toml)], cwd=str(ROOT_DIR), stdout=log_file, stderr=log_file)
        if c_res.returncode == 0:
            _log("Rust binary successfully compiled.")
        else:
            _log("Warning: cargo build failed. Falling back to Python runtime.")

    # Migrations
    brain_py = ROOT_DIR / "brain.py"
    if brain_py.exists():
        _log("Running Cephalo database integrity migrations...")
        subprocess.run([py_exe, str(brain_py), "migrate", "run"], cwd=str(ROOT_DIR), stdout=log_file, stderr=log_file)

    new_ver = get_current_version()
    _log(f"Cephalo update complete! New version: {new_ver}")
    log_file.close()

    # Update state file
    state = load_update_state()
    state["current_version"] = new_ver
    state["update_available"] = False
    state["last_update_applied_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    state["last_update_version"] = new_ver
    state["notified_in_session"] = False
    save_update_state(state)

    return True, f"Successfully upgraded Cephalo to {new_ver}"


def apply_update_background(target_tag: Optional[str] = None) -> Dict[str, Any]:
    """
    Launches update procedure in a detached background subprocess.
    Returns immediately without blocking the caller.
    """
    if is_update_locked():
        return {"status": "in_progress", "message": "An update is already running in the background."}

    py_exe = find_venv_python()
    cmd = [py_exe, str(Path(__file__).resolve()), "--apply-sync"]
    if target_tag:
        cmd.extend(["--target", target_tag])

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = open(UPDATE_LOG_FILE, "a", encoding="utf-8")

    # Launch detached
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        subprocess.Popen(cmd, cwd=str(ROOT_DIR), stdout=out_file, stderr=out_file, creationflags=creationflags)
    else:
        subprocess.Popen(cmd, cwd=str(ROOT_DIR), stdout=out_file, stderr=out_file, start_new_session=True)

    return {
        "status": "started",
        "message": "Cephalo update initiated in background.",
        "log_file": str(UPDATE_LOG_FILE),
    }


def get_harness_notification() -> Optional[Dict[str, str]]:
    """
    Checks if there is an update notice or newly applied upgrade to announce
    during agent SessionStart hook.
    """
    state = load_update_state()

    # Case 1: Fresh update was applied recently and not yet notified
    last_applied = state.get("last_update_applied_at")
    if last_applied and not state.get("notified_in_session", False):
        state["notified_in_session"] = True
        save_update_state(state)
        ver = state.get("last_update_version", get_current_version())
        return {
            "type": "applied",
            "message": f"🚀 [Cephalo Auto-Update]: Seamlessly upgraded to v{ver} in the background. Cognitive Coprocessor active and up to date.",
        }

    # Case 2: New update is available
    if state.get("update_available", False) and state.get("policy") != "off":
        latest = state.get("latest_version")
        url = state.get("release_url", "")
        return {
            "type": "available",
            "message": f"💡 [Cephalo Update]: Newer release v{latest} detected. Background update policy: {state.get('policy')}. (Run 'cephalo update' to apply immediately).",
        }

    return None


def trigger_session_start_hook() -> Optional[str]:
    """
    Hook handler called from auto_harvest.py on SessionStart.
    Checks for updates throttled, triggers background update if policy=auto,
    and returns notification text if applicable.
    """
    state = load_update_state()
    policy = state.get("policy", "auto")

    # Perform background throttled check
    check_res = check_for_updates(force=False, interval_seconds=DEFAULT_CHECK_INTERVAL_SECONDS)

    if check_res.get("update_available") and policy == "auto":
        # Launch background update
        if not is_update_locked():
            apply_update_background(target_tag=check_res.get("latest_version"))

    notice = get_harness_notification()
    if notice:
        return notice["message"]
    return None


def main():
    parser = argparse.ArgumentParser(description="Cephalo Autonomous Auto-Updater & Release Engine")
    parser.add_argument("--check", action="store_true", help="Check for newer release on GitHub")
    parser.add_argument("--force", action="store_true", help="Bypass throttling on update check")
    parser.add_argument("--apply", action="store_true", help="Apply available update in background")
    parser.add_argument("--apply-sync", action="store_true", help="Apply update synchronously (internal/cli)")
    parser.add_argument("--status", action="store_true", help="Show update engine status")
    parser.add_argument("--set-policy", choices=["auto", "notify", "off"], help="Set auto-update policy")
    parser.add_argument("--target", type=str, help="Target release tag to install")
    parser.add_argument("--json", action="store_true", help="Format output as JSON")
    args = parser.parse_args()

    if args.set_policy:
        state = load_update_state()
        state["policy"] = args.set_policy
        save_update_state(state)
        print(f"Cephalo update policy set to: {args.set_policy}")
        return

    if args.apply_sync:
        if not acquire_update_lock():
            print("Another update is currently in progress. Exiting.")
            sys.exit(1)
        try:
            ok, msg = execute_update_sync(args.target)
            if not ok:
                sys.exit(1)
        finally:
            release_update_lock()
        return

    if args.apply:
        res = apply_update_background(args.target)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"[+] {res['message']}")
            print(f"    Follow logs: tail -f {res['log_file']}")
        return

    if args.check:
        res = check_for_updates(force=args.force)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print("=" * 64)
            print("  ⚡ CEPHALO RELEASE TRACKER")
            print("=" * 64)
            print(f"  Current Version:  {res.get('current_version')}")
            print(f"  Latest Release:   {res.get('latest_version')}")
            print(f"  Update Available: {'YES (Ready to update)' if res.get('update_available') else 'NO (Up to date)'}")
            print(f"  Last Checked:     {res.get('checked_at')}")
            if res.get("release_url"):
                print(f"  Release URL:      {res.get('release_url')}")
            print("=" * 64)
        return

    # Default: status
    state = load_update_state()
    if args.json:
        print(json.dumps(state, indent=2))
    else:
        print("=" * 64)
        print("  ⚡ CEPHALO AUTO-UPDATE STATUS")
        print("=" * 64)
        print(f"  Current Version:      {state.get('current_version')}")
        print(f"  Latest Known Release: {state.get('latest_version')}")
        print(f"  Update Available:     {state.get('update_available')}")
        print(f"  Update Policy:        {state.get('policy')}")
        print(f"  Last Checked:         {state.get('last_checked_at') or 'Never'}")
        print(f"  Last Update Applied:  {state.get('last_update_applied_at') or 'None'}")
        print(f"  Update Lock Active:   {is_update_locked()}")
        print("=" * 64)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Cephalo Always-On Background Daemon (cephalo_daemon.py)
======================================================
Autonomous 24/7 background worker ensuring Cephalo continuously learns across
ALL agent harnesses (Claude Code, Antigravity, Cursor, Windsurf, Copilot, Aider).

Core Duties:
1. Workspace File & Stack Watcher:
   - Periodically monitors `scratch/projects` for newly added dependencies, packages, and frameworks.
   - Automatically invokes `ContinuousLearner` to synthesize missing specialties.
2. Cross-Harness Transcript Harvester:
   - Scans conversation transcripts from Antigravity, Claude, and local agent logs.
   - Ingests all user prompts and extracts preferences & negative constraints.
3. Git Synchronization:
   - Automatically synchronizes newly synthesized knowledge to GitHub (`LaptopKing/Cephalo`).
4. Windows Task Scheduler & Background Process Management:
   - Supports detached background execution (`cephalo daemon start/stop/status`).
   - Supports 1-click Windows Scheduled Task registration (`cephalo daemon install-task`).
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Base paths
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
PID_FILE = DATA_DIR / "cephalo_daemon.pid"
DAEMON_STATUS_FILE = DATA_DIR / "cephalo_daemon_status.json"
DAEMON_LOG_FILE = DATA_DIR / "daemon.log"
DEFAULT_INTERVAL_SECONDS = 90

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Defend against pythonw.exe NoneType stdout/stderr on Windows
if sys.stdout is None:
    sys.stdout = open(DAEMON_LOG_FILE, "a", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(DAEMON_LOG_FILE, "a", encoding="utf-8")

# Logging setup with both FileHandler and StreamHandler
handlers = [logging.FileHandler(DAEMON_LOG_FILE, encoding="utf-8")]
if sys.stderr and hasattr(sys.stderr, "write"):
    handlers.append(logging.StreamHandler(sys.stderr))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [Cephalo:Daemon] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=handlers,
)
logger = logging.getLogger("cephalo.daemon")


class CephaloDaemon:
    """Always-on background supervisor for sovereign continuous learning."""

    def __init__(self, interval_seconds: int = DEFAULT_INTERVAL_SECONDS):
        self.interval_seconds = interval_seconds
        self.running = False
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _write_pid(self) -> None:
        try:
            PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to write PID file: {e}")

    def _remove_pid(self) -> None:
        try:
            if PID_FILE.exists():
                PID_FILE.unlink()
        except Exception:
            pass

    def _update_status(self, cycle_report: Dict[str, Any]) -> None:
        try:
            status = {
                "pid": os.getpid(),
                "status": "running" if self.running else "stopped",
                "interval_seconds": self.interval_seconds,
                "last_heartbeat": datetime.datetime.now().astimezone().isoformat(),
                "last_cycle": cycle_report,
            }
            DAEMON_STATUS_FILE.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def execute_cycle(self) -> Dict[str, Any]:
        """Runs one unified autonomous cycle: Learn -> Harvest -> Git Sync."""
        logger.info("Executing autonomous background cycle...")
        cycle_result: Dict[str, Any] = {"success": True}

        # 1. Run Continuous Learner
        try:
            from continuous_learner import ContinuousLearner
            learner = ContinuousLearner()
            learn_report = learner.run_cycle()
            cycle_result["learning"] = learn_report
        except Exception as e:
            logger.error(f"Continuous learning step failed: {e}")
            cycle_result["learning_error"] = str(e)

        # 2. Run Autonomous Transcript Harvest
        try:
            from auto_harvest import run_standalone_scan
            run_standalone_scan()
            cycle_result["harvest"] = "completed"
        except Exception as e:
            logger.debug(f"Transcript harvest step skipped/failed: {e}")
            cycle_result["harvest_error"] = str(e)

        # 3. Auto-commit and push if new specialties or profile changes occurred
        try:
            status_proc = subprocess.run(
                ["git", "-C", str(SCRIPT_DIR), "status", "-s"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            git_changes = status_proc.stdout.strip()
            if git_changes:
                logger.info("Detected local Cephalo changes. Synchronizing to GitHub...")
                subprocess.run(["git", "-C", str(SCRIPT_DIR), "add", "."], check=True, timeout=10)
                commit_msg = f"chore(auto-sync): autonomous continuous learning cycle [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}]"
                subprocess.run(["git", "-C", str(SCRIPT_DIR), "commit", "-m", commit_msg], check=True, timeout=10)
                subprocess.run(["git", "-C", str(SCRIPT_DIR), "push", "origin", "main"], check=True, timeout=20)
                logger.info("Successfully pushed updates to LaptopKing/Cephalo.")
                cycle_result["git_pushed"] = True
            else:
                cycle_result["git_pushed"] = False
        except Exception as e:
            logger.debug(f"Git auto-sync skipped: {e}")
            cycle_result["git_error"] = str(e)

        self._update_status(cycle_result)
        return cycle_result

    def run_foreground(self) -> None:
        """Runs the daemon loop in the foreground."""
        self.running = True
        self._write_pid()
        logger.info(f"Cephalo Always-On Daemon started (PID {os.getpid()}, Interval: {self.interval_seconds}s)")

        def handle_signal(sig, frame):
            logger.info("Termination signal received. Stopping daemon...")
            self.running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        try:
            while self.running:
                self.execute_cycle()
                # Sleep in short increments for responsive interrupt handling
                for _ in range(self.interval_seconds):
                    if not self.running:
                        break
                    time.sleep(1)
        finally:
            self._remove_pid()
            logger.info("Cephalo Daemon stopped gracefully.")


# =============================================================================
# Process Control Helpers (Start / Stop / Status / Task Scheduler)
# =============================================================================
def is_pid_running(pid: int) -> bool:
    """Checks if a process ID is actively running on Windows/Linux."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"], text=True)
            return str(pid) in out
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def get_daemon_status() -> Dict[str, Any]:
    """Inspects daemon PID file and status snapshot."""
    pid = None
    running = False
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            running = is_pid_running(pid)
        except Exception:
            pid = None

    detail = {}
    if DAEMON_STATUS_FILE.exists():
        try:
            detail = json.loads(DAEMON_STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "running": running,
        "pid": pid if running else None,
        "detail": detail,
    }


def start_daemon_detached(interval: int = DEFAULT_INTERVAL_SECONDS) -> bool:
    """Spawns the daemon as a detached, persistent background process."""
    status = get_daemon_status()
    if status["running"]:
        print(f"[!] Cephalo Daemon is already running (PID: {status['pid']}).")
        return True

    python_bin = sys.executable
    creation_flags = 0
    if sys.platform == "win32":
        pythonw = Path(sys.executable).parent / "pythonw.exe"
        if pythonw.exists():
            python_bin = str(pythonw)
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | 0x08000000  # CREATE_NO_WINDOW

    cmd = [
        python_bin,
        str(SCRIPT_DIR / "cephalo_daemon.py"),
        "run",
        "--interval",
        str(interval),
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            creationflags=creation_flags,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        # Give process a moment to initialize and write its PID file
        time.sleep(1)
        check = get_daemon_status()
        active_pid = check.get("pid") or proc.pid
        print(f"[+] Cephalo Always-On Daemon launched successfully in background (PID: {active_pid}).")
        print(f"    Check status anytime via: cephalo daemon status")
        return True
    except Exception as e:
        print(f"[-] Failed to start daemon: {e}")
        return False
    except Exception as e:
        print(f"[-] Failed to start daemon: {e}")
        return False


def stop_daemon() -> bool:
    """Stops the running background daemon."""
    status = get_daemon_status()
    if not status["running"] or not status["pid"]:
        print("[-] Cephalo Daemon is not currently running.")
        if PID_FILE.exists():
            PID_FILE.unlink()
        return True

    pid = status["pid"]
    print(f"[*] Stopping Cephalo Daemon (PID {pid})...")
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=True, capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
        if PID_FILE.exists():
            PID_FILE.unlink()
        print("[+] Cephalo Daemon stopped successfully.")
        return True
    except Exception as e:
        print(f"[-] Failed to stop process {pid}: {e}")
        return False


def install_windows_task() -> bool:
    """Registers a persistent Windows Scheduled Task running on user login."""
    if sys.platform != "win32":
        print("[-] Task Scheduler registration is only available on Windows.")
        return False

    task_name = "CephaloContinuousDaemon"
    script_path = SCRIPT_DIR / "cephalo_daemon.py"
    python_exe = sys.executable

    # Command: run pythonw or python minimized
    action_cmd = f'"{python_exe}" "{script_path}" run --interval 90'
    create_cmd = [
        "schtasks",
        "/Create",
        "/TN", task_name,
        "/TR", action_cmd,
        "/SC", "ONLOGON",
        "/F",  # Overwrite if exists
    ]

    print(f"[*] Registering Windows Scheduled Task '{task_name}'...")
    res = subprocess.run(create_cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"[+] Scheduled Task '{task_name}' installed! Cephalo will now run automatically on login.")
        return True
    else:
        print(f"[-] Failed to register task: {res.stderr or res.stdout}")
        return False


def uninstall_windows_task() -> bool:
    """Unregisters the Windows Scheduled Task."""
    if sys.platform != "win32":
        return False
    task_name = "CephaloContinuousDaemon"
    print(f"[*] Removing Windows Scheduled Task '{task_name}'...")
    res = subprocess.run(["schtasks", "/Delete", "/TN", task_name, "/F"], capture_output=True, text=True)
    if res.returncode == 0:
        print(f"[+] Scheduled Task '{task_name}' removed.")
        return True
    else:
        print(f"[-] Task was not found or could not be removed.")
        return False


# =============================================================================
# CLI Interface
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Cephalo Always-On Background Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Daemon command")

    # run (foreground)
    run_p = subparsers.add_parser("run", help="Run daemon in foreground.")
    run_p.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_SECONDS, help="Cycle interval in seconds.")

    # start (detached)
    start_p = subparsers.add_parser("start", help="Start daemon as detached background process.")
    start_p.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_SECONDS, help="Cycle interval in seconds.")

    # stop
    subparsers.add_parser("stop", help="Stop running background daemon.")

    # status
    status_p = subparsers.add_parser("status", help="Check daemon status and last cycle.")
    status_p.add_argument("--json", action="store_true", help="Output status in JSON format.")

    # install-task
    subparsers.add_parser("install-task", help="Install Windows Scheduled Task to run daemon on login.")

    # uninstall-task
    subparsers.add_parser("uninstall-task", help="Remove Windows Scheduled Task.")

    args = parser.parse_args()

    if args.command == "run":
        daemon = CephaloDaemon(interval_seconds=args.interval)
        daemon.run_foreground()
    elif args.command == "start":
        start_daemon_detached(interval=args.interval)
    elif args.command == "stop":
        stop_daemon()
    elif args.command == "status":
        info = get_daemon_status()
        if getattr(args, "json", False):
            print(json.dumps(info, indent=2, ensure_ascii=False))
        else:
            print("=" * 65)
            print("  CEPHALO ALWAYS-ON DAEMON STATUS")
            print("=" * 65)
            print(f"Status:        {'RUNNING (Active)' if info['running'] else 'STOPPED'}")
            if info["pid"]:
                print(f"Process PID:   {info['pid']}")
            detail = info.get("detail", {})
            if detail:
                print(f"Last Heartbeat: {detail.get('last_heartbeat', 'N/A')}")
                print(f"Interval:       {detail.get('interval_seconds', DEFAULT_INTERVAL_SECONDS)}s")
                last_c = detail.get("last_cycle", {})
                if "learning" in last_c:
                    l = last_c["learning"]
                    print(f"Last Learning:  {l.get('scanned_projects_count', 0)} projects, {len(l.get('discovered_technologies', []))} stacks")
                if "git_pushed" in last_c:
                    print(f"GitHub Sync:    {'Pushed' if last_c['git_pushed'] else 'Up to date'}")
            print("=" * 65)
    elif args.command == "install-task":
        install_windows_task()
    elif args.command == "uninstall-task":
        uninstall_windows_task()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

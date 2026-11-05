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
3. Windows Task Scheduler & Background Process Management:
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
ROOT_DIR = Path(__file__).resolve().parents[3]
SCRIPT_DIR = ROOT_DIR
DATA_DIR = ROOT_DIR / "data"
PID_FILE = DATA_DIR / "cephalo_daemon.pid"
DAEMON_STATUS_FILE = DATA_DIR / "cephalo_daemon_status.json"
DAEMON_LOG_FILE = DATA_DIR / "daemon.log"
DEFAULT_INTERVAL_SECONDS = 90

NO_WINDOW_FLAG = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

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
        self.webhook_port = int(os.environ.get("CEPHALO_WEBHOOK_PORT", "7434"))
        self.webhook_server = None
        self.telegram_bot = None
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
        """Runs one unified autonomous cycle: Learn -> Harvest."""
        logger.info("Executing autonomous background cycle...")
        cycle_result: Dict[str, Any] = {"success": True}

        # 1. Run Continuous Learner
        try:
            from cephalo.learning.continuous_learner import ContinuousLearner
            learner = ContinuousLearner()
            learn_report = learner.run_cycle()
            cycle_result["learning"] = learn_report
        except Exception as e:
            logger.error(f"Continuous learning step failed: {e}")
            cycle_result["learning_error"] = str(e)

        # 2. Run Autonomous Transcript Harvest
        try:
            from cephalo.learning.auto_harvest import run_standalone_scan
            run_standalone_scan()
            cycle_result["harvest"] = "completed"
        except Exception as e:
            logger.debug(f"Transcript harvest step skipped/failed: {e}")
            cycle_result["harvest_error"] = str(e)

        # 3. Autonomous Screen Perceptual Delta Evaluation (Zero-bloat, delta-gated)
        try:
            from cephalo.services.screen_recorder import ScreenMemoryEngine
            screen_engine = ScreenMemoryEngine()
            screen_report = screen_engine.capture_step(force=False)
            cycle_result["screen"] = screen_report.get("status", "unknown")
            if screen_report.get("status") == "captured":
                logger.info(f"Captured screen keyframe {screen_report.get('frame_id')} (delta: {screen_report.get('delta')})")
        except Exception as e:
            logger.debug(f"Screen capture step skipped: {e}")

        self._update_status(cycle_result)
        return cycle_result

    def run_foreground(self) -> None:
        """Runs the daemon loop in the foreground with serialized background work queue."""
        self.running = True
        self._write_pid()
        logger.info(f"Cephalo Always-On Daemon started (PID {os.getpid()}, Interval: {self.interval_seconds}s)")

        from cephalo.services.job_queue import JobQueue, QueueWorker
        self.queue = JobQueue()
        self.worker = QueueWorker(self.queue)

        # Start background quick-capture webhook server
        try:
            from cephalo.services.webhook_server import WebhookServer, TelegramIngestBot
            self.webhook_server = WebhookServer(port=self.webhook_port)
            self.webhook_server.start(background=True)
            logger.info("Daemon quick-capture webhook server active on port %d", self.webhook_port)

            tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
            if tg_token:
                allowed_chats = [c.strip() for c in os.environ.get("TELEGRAM_ALLOWED_CHATS", "").split(",") if c.strip()]
                self.telegram_bot = TelegramIngestBot(bot_token=tg_token, allowed_chat_ids=allowed_chats)
                self.telegram_bot.start()
                logger.info("Daemon Telegram thought capture poller started.")
        except Exception as wh_err:
            logger.warning("Could not start daemon webhook listener: %s", wh_err)

        def handle_signal(sig, frame):
            logger.info("Termination signal received. Stopping daemon...")
            self.running = False

        try:
            signal.signal(signal.SIGINT, handle_signal)
            if sys.platform != "win32":
                signal.signal(signal.SIGTERM, handle_signal)
        except Exception:
            pass

        last_cycle_time = 0.0

        try:
            while self.running:
                now = time.time()

                # 1. First priority: Drain pending heavy jobs in queue sequentially
                had_work = False
                try:
                    had_work = self.worker.process_one()
                except Exception as w_err:
                    logger.error(f"Queue worker exception: {w_err}", exc_info=True)

                if had_work:
                    # Give CPU and thermals a brief pause between queue tasks
                    time.sleep(0.5)
                    continue

                # 2. If queue is clear and interval elapsed, enqueue periodic tasks
                if (now - last_cycle_time) >= self.interval_seconds:
                    last_cycle_time = now
                    try:
                        # Enqueue periodic maintenance tasks with priority order
                        self.queue.enqueue("screen_capture", priority=4)
                        self.queue.enqueue("transcript_harvest", priority=3)
                        self.queue.enqueue("continuous_learn", priority=2)
                        self._update_status({"queue": self.queue.get_status()})
                    except Exception as cycle_err:
                        logger.error(f"Error enqueueing periodic cycle: {cycle_err}")

                # Sleep briefly when idle
                time.sleep(1.5)
        except Exception as loop_err:
            logger.error(f"Daemon fatal loop crash: {loop_err}", exc_info=True)
        finally:
            if self.webhook_server:
                self.webhook_server.stop()
            if self.telegram_bot:
                self.telegram_bot.stop()
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
            out = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"],
                text=True,
                creationflags=NO_WINDOW_FLAG,
            )
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
    script_path = SCRIPT_DIR / "cephalo_daemon.py"

    if sys.platform == "win32":
        # Use PowerShell Start-Process to guarantee complete process independence
        ps_cmd = (
            f"Start-Process -FilePath '{python_bin}' "
            f"-ArgumentList '\"{script_path}\" run --interval {interval}' "
            f"-WindowStyle Hidden"
        )
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                check=True,
            )
            time.sleep(1.5)
            check = get_daemon_status()
            active_pid = check.get("pid")
            print(f"[+] Cephalo Always-On Daemon launched successfully in background (PID: {active_pid or 'Active'}).")
            print(f"    Check status anytime via: cephalo daemon status")
            return True
        except Exception as e:
            logger.warning(f"PowerShell Start-Process failed: {e}. Falling back to Popen...")

    # Fallback to Popen
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = 0x08000000 | 0x00000200 | 0x00000008  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS

    cmd = [
        python_bin,
        str(script_path),
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
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=True, capture_output=True, creationflags=NO_WINDOW_FLAG)
        else:
            os.kill(pid, signal.SIGTERM)
        if PID_FILE.exists():
            PID_FILE.unlink()
        print("[+] Cephalo Daemon stopped successfully.")
        return True
    except Exception as e:
        print(f"[-] Failed to stop process {pid}: {e}")
        return False


def install_autostart() -> bool:
    """Registers Cephalo daemon to start automatically on user login/boot across Linux, macOS, and Windows."""
    script_path = Path(__file__).resolve()
    python_exe = sys.executable

    # 1. Windows: Task Scheduler ONLOGON
    if sys.platform == "win32":
        task_name = "CephaloContinuousDaemon"
        action_cmd = f'"{python_exe}" "{script_path}" run --interval 90'
        create_cmd = [
            "schtasks",
            "/Create",
            "/TN", task_name,
            "/TR", action_cmd,
            "/SC", "ONLOGON",
            "/F",
        ]
        print(f"[*] Registering Windows Scheduled Task '{task_name}'...")
        res = subprocess.run(create_cmd, capture_output=True, text=True, creationflags=NO_WINDOW_FLAG)
        if res.returncode == 0:
            print(f"[+] Scheduled Task '{task_name}' installed! Cephalo daemon will start automatically on login.")
            return True
        else:
            print(f"[-] Failed to register Windows task: {res.stderr or res.stdout}")
            return False

    # 2. macOS: LaunchAgents plist
    elif sys.platform == "darwin":
        launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
        launch_agents_dir.mkdir(parents=True, exist_ok=True)
        plist_path = launch_agents_dir / "ai.cephalo.daemon.plist"
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>ai.cephalo.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_exe}</string>
        <string>{script_path}</string>
        <string>run</string>
        <string>--interval</string>
        <string>90</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>{DATA_DIR}/daemon.err</string>
    <key>StandardOutPath</key>
    <string>{DATA_DIR}/daemon.log</string>
</dict>
</plist>
"""
        try:
            plist_path.write_text(plist_content, encoding="utf-8")
            subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
            subprocess.run(["launchctl", "load", str(plist_path)], check=True)
            print(f"[+] macOS LaunchAgent registered at {plist_path}. Daemon will start automatically on boot.")
            return True
        except Exception as e:
            print(f"[-] Failed to configure macOS LaunchAgent: {e}")
            return False

    # 3. Linux: XDG Desktop Autostart & systemd user service
    else:
        success = False
        # A) XDG Desktop Autostart (guarantees DISPLAY/Wayland access for screen capture)
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)
        desktop_file = autostart_dir / "cephalo-daemon.desktop"
        desktop_content = f"""[Desktop Entry]
Type=Application
Name=Cephalo Background Daemon
Comment=Always-on screen memory, perceptual delta capture, and continuous learning
Exec={python_exe} {script_path} run --interval 90
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
StartupNotify=false
Terminal=false
"""
        try:
            desktop_file.write_text(desktop_content, encoding="utf-8")
            desktop_file.chmod(0o755)
            print(f"[+] Linux XDG Autostart installed at {desktop_file}")
            success = True
        except Exception as e:
            print(f"[-] Failed to write XDG autostart file: {e}")

        # B) systemd user service (for background persistence across logins)
        systemd_user_dir = Path.home() / ".config" / "systemd" / "user"
        systemd_user_dir.mkdir(parents=True, exist_ok=True)
        service_file = systemd_user_dir / "cephalo-daemon.service"
        service_content = f"""[Unit]
Description=Cephalo Always-On Cognitive & Screen Memory Daemon
After=graphical-session.target network.target

[Service]
Type=simple
Environment="PYTHONPATH={ROOT_DIR / 'src'}"
Environment="DISPLAY=:0"
ExecStart={python_exe} {script_path} run --interval 90
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
"""
        try:
            service_file.write_text(service_content, encoding="utf-8")
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
            subprocess.run(["systemctl", "--user", "enable", "cephalo-daemon.service"], capture_output=True)
            print(f"[+] Linux systemd user service installed and enabled ({service_file})")
            success = True
        except Exception as e:
            print(f"[*] systemd registration skipped/failed: {e}")

        return success


def uninstall_autostart() -> bool:
    """Removes Cephalo autostart registration across Linux, macOS, and Windows."""
    if sys.platform == "win32":
        task_name = "CephaloContinuousDaemon"
        print(f"[*] Removing Windows Scheduled Task '{task_name}'...")
        res = subprocess.run(["schtasks", "/Delete", "/TN", task_name, "/F"], capture_output=True, text=True, creationflags=NO_WINDOW_FLAG)
        return res.returncode == 0
    elif sys.platform == "darwin":
        plist_path = Path.home() / "Library" / "LaunchAgents" / "ai.cephalo.daemon.plist"
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
            plist_path.unlink()
            print("[+] macOS LaunchAgent removed.")
            return True
        return False
    else:
        # Linux
        desktop_file = Path.home() / ".config" / "autostart" / "cephalo-daemon.desktop"
        if desktop_file.exists():
            desktop_file.unlink()
            print("[+] Linux XDG autostart desktop entry removed.")
        try:
            subprocess.run(["systemctl", "--user", "disable", "--now", "cephalo-daemon.service"], capture_output=True)
            service_file = Path.home() / ".config" / "systemd" / "user" / "cephalo-daemon.service"
            if service_file.exists():
                service_file.unlink()
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
            print("[+] Linux systemd user service removed.")
        except Exception:
            pass
        return True


install_windows_task = install_autostart
uninstall_windows_task = uninstall_autostart


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
                if "harvest" in last_c:
                    print(f"Last Harvest:   {last_c.get('harvest', 'N/A')}")
            print("=" * 65)
    elif args.command == "install-task":
        install_windows_task()
    elif args.command == "uninstall-task":
        uninstall_windows_task()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

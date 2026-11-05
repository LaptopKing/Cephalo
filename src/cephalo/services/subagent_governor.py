"""
Cephalo Subagent Resource Governor & State Recovery Engine (subagent_governor.py)
================================================================================
Monitors system hardware resources (battery status, power source, CPU load, thermals)
to dynamically govern subagent concurrency and prevent laptop power exhaustion.
Integrates with TaskLedger (agent_tasks.db) to ensure interrupted subagent tasks
checkpoint their progress and resume without starting over.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"

logger = logging.getLogger("cephalo.subagent_governor")


class SubagentGovernor:
    """
    Monitors hardware power constraints and manages subagent task lifecycle.
    """

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._init_task_ledger()

    def _init_task_ledger(self):
        from cephalo.core.task_ledger import TaskLedger
        self.ledger = TaskLedger(db_path=self.data_dir / "agent_tasks.db")

    def inspect_resources(self) -> Dict[str, Any]:
        """
        Samples real-time power, battery, and CPU load metrics.
        """
        cpu_count = os.cpu_count() or 4
        load_1m, load_5m, load_15m = (0.0, 0.0, 0.0)
        if hasattr(os, "getloadavg"):
            try:
                load_1m, load_5m, load_15m = os.getloadavg()
            except Exception:
                pass

        power_plugged: Optional[bool] = None
        battery_percent: Optional[float] = None
        battery_secsleft: Optional[int] = None

        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery:
                power_plugged = battery.power_plugged
                battery_percent = round(battery.percent, 1)
                battery_secsleft = battery.secsleft if battery.secsleft > 0 else None
            cpu_percent = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            mem_available_mb = round(mem.available / (1024 * 1024))
        except Exception:
            cpu_percent = round((load_1m / max(cpu_count, 1)) * 100, 1)
            mem_available_mb = 1024

        # Dynamic Concurrency and Thermal Safeguard Calculation
        # On laptop battery, excessive parallel subagents pull peak amps causing emergency power cutoffs
        on_battery = (power_plugged is False)
        
        if on_battery:
            if battery_percent is not None and battery_percent < 20.0:
                safe_concurrency = 0
                throttle_reason = f"Battery critically low ({battery_percent:.1f}%). Subagents paused to avoid abrupt hardware power cutoff. Please connect charger."
                mode = "EMERGENCY_CONSERVATION"
            else:
                safe_concurrency = 1
                throttle_reason = f"Running on Battery ({battery_percent:.1f}%). Strict sequential execution (max 1 subagent)."
                mode = "BATTERY_SAVER_SEQUENTIAL"
        else:
            if cpu_percent > 80.0 or (load_1m > cpu_count * 0.85):
                safe_concurrency = 1
                throttle_reason = f"High CPU load ({cpu_percent}%). Throttling subagents to 1 to manage thermals."
                mode = "THERMAL_THROTTLED"
            else:
                safe_concurrency = 2  # Hard cap at 2 for laptop safety
                throttle_reason = "AC Power connected and thermals nominal. Up to 2 subagents allowed."
                mode = "AC_POWER_BALANCED"

        return {
            "on_battery": on_battery,
            "power_plugged": power_plugged,
            "battery_percent": battery_percent,
            "battery_secsleft": battery_secsleft,
            "cpu_count": cpu_count,
            "cpu_percent": cpu_percent,
            "load_1m": load_1m,
            "mem_available_mb": mem_available_mb,
            "safe_concurrency": safe_concurrency,
            "mode": mode,
            "throttle_reason": throttle_reason,
            "timestamp": datetime.datetime.now().astimezone().isoformat(),
        }

    # =========================================================================
    # Task Lifecycle & Interruption Recovery
    # =========================================================================

    def register_subagent(
        self,
        task_id: str,
        user_goal: str,
        total_steps: int = 1,
        assignee_agent: str = "subagent",
        conversation_id: str = "default",
        parent_task_id: Optional[str] = None,
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Registers a new subagent task with Cephalo's ledger."""
        return self.ledger.register_task(
            task_id=task_id,
            conversation_id=conversation_id,
            assignee_agent=assignee_agent,
            user_goal=user_goal,
            total_steps=total_steps,
            parent_task_id=parent_task_id,
            initial_state=initial_state or {},
        )

    def checkpoint_subagent(
        self,
        task_id: str,
        step_index: int,
        checkpoint_state: Dict[str, Any],
        token_usage: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Checkpoints step progress so crashes or restarts do not lose work."""
        return self.ledger.checkpoint(
            task_id=task_id,
            step_index=step_index,
            checkpoint_state=checkpoint_state,
            token_usage=token_usage,
        )

    def complete_subagent(self, task_id: str, summary: str) -> Dict[str, Any]:
        """Marks subagent task as complete."""
        return self.ledger.complete_task(task_id=task_id, result_summary=summary)

    def fail_subagent(self, task_id: str, error: str) -> Dict[str, Any]:
        """Marks subagent task as failed."""
        return self.ledger.fail_task(task_id=task_id, error_message=error)

    def get_interrupted_tasks(self, conversation_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Scans ledger for tasks that were in progress ('running') but interrupted
        by a server restart or laptop shutdown.
        """
        tasks = self.ledger.list_tasks(conversation_id=conversation_id, status="running")
        interrupted = []
        for t in tasks:
            interrupted.append({
                "task_id": t["task_id"],
                "user_goal": t["user_goal"],
                "step_index": t["step_index"],
                "total_steps": t["total_steps"],
                "checkpoint_state": t["checkpoint_state"],
                "updated_at": t["updated_at"],
            })
        return interrupted

    def build_resume_brief(self, task_id: str) -> Optional[str]:
        """
        Builds a resume instruction payload for a revived subagent so it starts
        at step N+1 with its previous state intact.
        """
        task = self.ledger.get_task(task_id)
        if not task:
            return None

        step = task["step_index"]
        total = task["total_steps"]
        state_str = json.dumps(task["checkpoint_state"], indent=2)

        return (
            f"🔄 [Cephalo Subagent State Restoration | Task: {task_id}]\n"
            f"- Goal: {task['user_goal']}\n"
            f"- Last Successfully Completed Step: {step} of {total}\n"
            f"- Restored Checkpoint State:\n```json\n{state_str}\n```\n"
            f"- INSTRUCTION: Resume directly from step {step + 1}. DO NOT repeat steps 1 through {step}."
        )

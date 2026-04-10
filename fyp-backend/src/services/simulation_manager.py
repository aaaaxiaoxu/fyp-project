from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..db import SessionLocal, init_db
from ..models import Simulation, SimulationStatus
from ..repositories import simulation_repo
from ..utils import get_logger
from ..utils.path_resolver import (
    ensure_parent_directory,
    resolve_upload_path,
    simulation_config_path,
    simulation_env_status_path,
    simulation_log_path,
    simulation_profiles_path,
    simulation_reddit_actions_path,
    simulation_reddit_database_path,
    simulation_reddit_profiles_path,
    simulation_run_state_path,
    simulation_twitter_actions_path,
    simulation_twitter_database_path,
)
from .action_logger import ActionLogger
from .simulation_ipc import SimulationIPC
from .simulation_runner import SimulationRunner
from .zep_graph_memory_updater import ZepGraphMemoryUpdater

logger = get_logger("fyp.simulation_manager")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_parallel_simulation.py"
ROUND_DELAY_SECONDS = 0.02
_RUNNING_PROCESSES: dict[str, subprocess.Popen[str]] = {}
_PROCESS_LOCK = threading.Lock()


class SimulationStartError(RuntimeError):
    def __init__(self, detail: str, *, status_code: int) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class SimulationStopError(RuntimeError):
    def __init__(self, detail: str, *, status_code: int) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True, slots=True)
class SimulationStartResult:
    simulation_id: str
    status: str
    pid: int


@dataclass(frozen=True, slots=True)
class SimulationStopResult:
    simulation_id: str
    status: str
    command_id: str


class SimulationManager:
    async def start_simulation(self, simulation_id: str) -> SimulationStartResult:
        async with SessionLocal() as session:
            simulation = await simulation_repo.get_simulation_by_id(session, simulation_id)

        if simulation is None:
            raise SimulationStartError("Simulation not found", status_code=404)
        if simulation.status == SimulationStatus.RUNNING.value:
            raise SimulationStartError("Simulation is already running.", status_code=409)
        if simulation.status not in {
            SimulationStatus.READY.value,
            SimulationStatus.STOPPED.value,
            SimulationStatus.COMPLETED.value,
            SimulationStatus.FAILED.value,
        }:
            raise SimulationStartError("Simulation is not ready to start.", status_code=400)

        config = self._load_config(simulation)
        self._load_profiles(simulation_id)

        ipc = SimulationIPC(simulation_id)
        ipc.initialize_runtime()
        ipc.write_run_state(
            {
                "simulation_id": simulation_id,
                "status": SimulationStatus.RUNNING.value,
                "current_round": 0,
                "total_rounds": int(simulation.total_rounds or self._resolve_total_rounds(config)),
                "twitter_actions_count": 0,
                "reddit_actions_count": 0,
                "interactive_ready": False,
            }
        )
        ipc.write_env_status(
            status="launching",
            current_round=0,
            twitter_actions_count=0,
            reddit_actions_count=0,
            interactive_ready=False,
        )

        async with SessionLocal() as session:
            await simulation_repo.update_simulation(
                session,
                simulation_id,
                status=SimulationStatus.RUNNING.value,
                current_round=0,
                twitter_actions_count=0,
                reddit_actions_count=0,
                interactive_ready=False,
                error=None,
                started_at=datetime.now(timezone.utc),
                completed_at=None,
            )

        try:
            pid = self._spawn_subprocess(simulation_id)
        except Exception as exc:
            logger.exception("failed to start simulation subprocess for %s", simulation_id)
            await self._mark_failed(simulation_id, f"{exc}\n{traceback.format_exc()}")
            ipc.write_env_status(
                status="failed",
                current_round=0,
                twitter_actions_count=0,
                reddit_actions_count=0,
                interactive_ready=False,
                error=str(exc),
            )
            raise SimulationStartError("Failed to start simulation process.", status_code=500) from exc

        ipc.write_env_status(
            status=SimulationStatus.RUNNING.value,
            pid=pid,
            current_round=0,
            twitter_actions_count=0,
            reddit_actions_count=0,
            interactive_ready=False,
        )
        return SimulationStartResult(
            simulation_id=simulation_id,
            status=SimulationStatus.RUNNING.value,
            pid=pid,
        )

    async def stop_simulation(self, simulation_id: str) -> SimulationStopResult:
        async with SessionLocal() as session:
            simulation = await simulation_repo.get_simulation_by_id(session, simulation_id)

        if simulation is None:
            raise SimulationStopError("Simulation not found", status_code=404)
        if simulation.status != SimulationStatus.RUNNING.value:
            raise SimulationStopError("Simulation is not running.", status_code=409)

        command = SimulationIPC(simulation_id).write_command(
            command="stop",
            payload={"requested_at": datetime.now(timezone.utc).isoformat()},
        )
        return SimulationStopResult(
            simulation_id=simulation_id,
            status="stop_requested",
            command_id=command.command_id,
        )

    def run_parallel_simulation(self, simulation_id: str) -> None:
        asyncio.run(self._run_parallel_simulation_async(simulation_id))

    async def _run_parallel_simulation_async(self, simulation_id: str) -> None:
        await init_db()
        ipc = SimulationIPC(simulation_id)
        ipc.initialize_runtime(purge_commands=False)

        try:
            async with SessionLocal() as session:
                simulation = await simulation_repo.get_simulation_by_id(session, simulation_id)
            if simulation is None:
                raise RuntimeError("Simulation not found")

            config = self._load_config(simulation)
            profiles = self._load_profiles(simulation_id)
            total_rounds = int(simulation.total_rounds or self._resolve_total_rounds(config))

            action_logger = ActionLogger(simulation_id)
            runner = SimulationRunner(
                simulation_id=simulation_id,
                config=config,
                profiles=profiles,
                total_rounds=total_rounds,
                twitter_enabled=simulation.twitter_enabled,
                reddit_enabled=simulation.reddit_enabled,
            )
            runner.prepare_environment(action_logger)
            memory_updater = ZepGraphMemoryUpdater(graph_id=str(config.get("graph_id") or ""))

            twitter_count = 0
            reddit_count = 0
            ipc.write_env_status(
                status=SimulationStatus.RUNNING.value,
                pid=os.getpid(),
                current_round=0,
                total_rounds=total_rounds,
                twitter_actions_count=0,
                reddit_actions_count=0,
                interactive_ready=False,
            )

            for round_number in range(1, total_rounds + 1):
                stop_requested = False
                for command in ipc.consume_commands():
                    if command.command == "stop":
                        stop_requested = True
                        ipc.write_response(
                            command_id=command.command_id,
                            payload={
                                "simulation_id": simulation_id,
                                "status": "accepted",
                                "command": "stop",
                            },
                        )

                if stop_requested:
                    interactive_ready = self._artifacts_complete(
                        simulation_id,
                        twitter_enabled=simulation.twitter_enabled,
                        reddit_enabled=simulation.reddit_enabled,
                    )
                    await self._set_terminal_state(
                        simulation_id,
                        status=SimulationStatus.STOPPED.value,
                        current_round=round_number - 1,
                        twitter_actions_count=twitter_count,
                        reddit_actions_count=reddit_count,
                        interactive_ready=interactive_ready,
                    )
                    ipc.write_run_state(
                        {
                            "simulation_id": simulation_id,
                            "status": SimulationStatus.STOPPED.value,
                            "current_round": round_number - 1,
                            "total_rounds": total_rounds,
                            "twitter_actions_count": twitter_count,
                            "reddit_actions_count": reddit_count,
                            "interactive_ready": interactive_ready,
                        }
                    )
                    ipc.write_env_status(
                        status=SimulationStatus.STOPPED.value,
                        pid=os.getpid(),
                        current_round=round_number - 1,
                        total_rounds=total_rounds,
                        twitter_actions_count=twitter_count,
                        reddit_actions_count=reddit_count,
                        interactive_ready=interactive_ready,
                    )
                    return

                round_result = runner.execute_round(round_number)
                if round_result.twitter_actions:
                    action_logger.append_actions("twitter", round_result.twitter_actions)
                    twitter_count += len(round_result.twitter_actions)
                if round_result.reddit_actions:
                    action_logger.append_actions("reddit", round_result.reddit_actions)
                    reddit_count += len(round_result.reddit_actions)

                memory_summary = memory_updater.record_round(round_number, round_result.all_actions)
                ipc.write_run_state(
                    {
                        "simulation_id": simulation_id,
                        "status": SimulationStatus.RUNNING.value,
                        "current_round": round_number,
                        "total_rounds": total_rounds,
                        "twitter_actions_count": twitter_count,
                        "reddit_actions_count": reddit_count,
                        "interactive_ready": False,
                        "recent_actions": round_result.all_actions[-6:],
                        "memory_update": memory_summary,
                    }
                )
                ipc.write_env_status(
                    status=SimulationStatus.RUNNING.value,
                    pid=os.getpid(),
                    current_round=round_number,
                    total_rounds=total_rounds,
                    twitter_actions_count=twitter_count,
                    reddit_actions_count=reddit_count,
                    interactive_ready=False,
                )

                async with SessionLocal() as session:
                    await simulation_repo.update_simulation(
                        session,
                        simulation_id,
                        status=SimulationStatus.RUNNING.value,
                        current_round=round_number,
                        twitter_actions_count=twitter_count,
                        reddit_actions_count=reddit_count,
                        interactive_ready=False,
                        error=None,
                    )
                time.sleep(ROUND_DELAY_SECONDS)

            interactive_ready = self._artifacts_complete(
                simulation_id,
                twitter_enabled=simulation.twitter_enabled,
                reddit_enabled=simulation.reddit_enabled,
            )
            await self._set_terminal_state(
                simulation_id,
                status=SimulationStatus.COMPLETED.value,
                current_round=total_rounds,
                twitter_actions_count=twitter_count,
                reddit_actions_count=reddit_count,
                interactive_ready=interactive_ready,
            )
            ipc.write_run_state(
                {
                    "simulation_id": simulation_id,
                    "status": SimulationStatus.COMPLETED.value,
                    "current_round": total_rounds,
                    "total_rounds": total_rounds,
                    "twitter_actions_count": twitter_count,
                    "reddit_actions_count": reddit_count,
                    "interactive_ready": interactive_ready,
                }
            )
            ipc.write_env_status(
                status=SimulationStatus.COMPLETED.value,
                pid=os.getpid(),
                current_round=total_rounds,
                total_rounds=total_rounds,
                twitter_actions_count=twitter_count,
                reddit_actions_count=reddit_count,
                interactive_ready=interactive_ready,
            )
        except Exception as exc:
            logger.exception("simulation process failed for %s", simulation_id)
            await self._mark_failed(simulation_id, f"{exc}\n{traceback.format_exc()}")
            ipc.write_run_state(
                {
                    "simulation_id": simulation_id,
                    "status": SimulationStatus.FAILED.value,
                    "interactive_ready": False,
                    "error": str(exc),
                }
            )
            ipc.write_env_status(
                status=SimulationStatus.FAILED.value,
                pid=os.getpid(),
                interactive_ready=False,
                error=str(exc),
            )

    async def _set_terminal_state(
        self,
        simulation_id: str,
        *,
        status: str,
        current_round: int,
        twitter_actions_count: int,
        reddit_actions_count: int,
        interactive_ready: bool,
    ) -> None:
        async with SessionLocal() as session:
            await simulation_repo.update_simulation(
                session,
                simulation_id,
                status=status,
                current_round=current_round,
                twitter_actions_count=twitter_actions_count,
                reddit_actions_count=reddit_actions_count,
                interactive_ready=interactive_ready,
                error=None,
                completed_at=datetime.now(timezone.utc),
            )

    async def _mark_failed(self, simulation_id: str, error: str) -> None:
        async with SessionLocal() as session:
            await simulation_repo.update_simulation(
                session,
                simulation_id,
                status=SimulationStatus.FAILED.value,
                interactive_ready=False,
                error=error,
                completed_at=datetime.now(timezone.utc),
            )

    def _spawn_subprocess(self, simulation_id: str) -> int:
        ensure_parent_directory(simulation_log_path(simulation_id))
        log_handle = simulation_log_path(simulation_id).open("a", encoding="utf-8")
        env = os.environ.copy()
        current_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{PROJECT_ROOT}{os.pathsep}{current_pythonpath}" if current_pythonpath else str(PROJECT_ROOT)
        )

        process = subprocess.Popen(
            [sys.executable, str(RUN_SCRIPT_PATH), simulation_id],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
        with _PROCESS_LOCK:
            _RUNNING_PROCESSES[simulation_id] = process
        threading.Thread(
            target=self._monitor_process,
            args=(simulation_id, process, log_handle),
            daemon=True,
        ).start()
        return int(process.pid)

    def _monitor_process(
        self,
        simulation_id: str,
        process: subprocess.Popen[str],
        log_handle,
    ) -> None:
        try:
            process.wait()
        finally:
            with _PROCESS_LOCK:
                current = _RUNNING_PROCESSES.get(simulation_id)
                if current is process:
                    _RUNNING_PROCESSES.pop(simulation_id, None)
            log_handle.close()

    def _load_config(self, simulation: Simulation) -> dict[str, Any]:
        if not simulation.config_path:
            raise SimulationStartError("Simulation config is missing.", status_code=400)
        config_path = resolve_upload_path(simulation.config_path)
        if not config_path.exists():
            raise SimulationStartError("Simulation config is missing.", status_code=400)
        data = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SimulationStartError("Simulation config file is invalid.", status_code=400)
        return data

    def _load_profiles(self, simulation_id: str) -> list[dict[str, Any]]:
        primary_path = simulation_profiles_path(simulation_id)
        fallback_path = simulation_reddit_profiles_path(simulation_id)

        if primary_path.exists():
            try:
                return self._read_json_list(primary_path)
            except Exception:
                logger.warning(
                    "failed to read full profiles %s for simulation %s; using fallback if available",
                    primary_path,
                    simulation_id,
                    exc_info=True,
                )

        if fallback_path.exists():
            return self._read_json_list(fallback_path)

        raise SimulationStartError("Simulation profiles are missing.", status_code=400)

    def _resolve_total_rounds(self, config: dict[str, Any]) -> int:
        time_config = config.get("time_config") or {}
        total_hours = int(time_config.get("total_simulation_hours") or 0)
        minutes_per_round = int(time_config.get("minutes_per_round") or 60)
        if total_hours <= 0:
            return 1
        return max(1, int(total_hours * 60 / max(minutes_per_round, 1)))

    def _artifacts_complete(
        self,
        simulation_id: str,
        *,
        twitter_enabled: bool,
        reddit_enabled: bool,
    ) -> bool:
        required_paths = [
            simulation_config_path(simulation_id),
            simulation_run_state_path(simulation_id),
            simulation_env_status_path(simulation_id),
        ]
        if not any(path.exists() and path.stat().st_size > 0 for path in (simulation_profiles_path(simulation_id), simulation_reddit_profiles_path(simulation_id))):
            return False
        if any(not path.exists() or path.stat().st_size == 0 for path in required_paths):
            return False
        if twitter_enabled:
            if not simulation_twitter_actions_path(simulation_id).exists() or simulation_twitter_actions_path(simulation_id).stat().st_size == 0:
                return False
            if not simulation_twitter_database_path(simulation_id).exists() or simulation_twitter_database_path(simulation_id).stat().st_size == 0:
                return False
        if reddit_enabled:
            if not simulation_reddit_actions_path(simulation_id).exists() or simulation_reddit_actions_path(simulation_id).stat().st_size == 0:
                return False
            if not simulation_reddit_database_path(simulation_id).exists() or simulation_reddit_database_path(simulation_id).stat().st_size == 0:
                return False
        return True

    def _read_json_list(self, path: Path) -> list[dict[str, Any]]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise ValueError("profile file must contain a JSON array of objects")
        return data

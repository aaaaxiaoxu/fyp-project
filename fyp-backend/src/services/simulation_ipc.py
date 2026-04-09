from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..utils import get_logger
from ..utils.path_resolver import (
    ensure_directory,
    ensure_parent_directory,
    simulation_env_status_path,
    simulation_ipc_commands_dir,
    simulation_ipc_responses_dir,
    simulation_run_state_path,
)

logger = get_logger("fyp.simulation_ipc")


@dataclass(frozen=True, slots=True)
class IPCCommand:
    command_id: str
    command: str
    payload: dict[str, Any]


class SimulationIPC:
    def __init__(self, simulation_id: str) -> None:
        self.simulation_id = simulation_id
        self.commands_dir = simulation_ipc_commands_dir(simulation_id)
        self.responses_dir = simulation_ipc_responses_dir(simulation_id)
        self.run_state_path = simulation_run_state_path(simulation_id)
        self.env_status_path = simulation_env_status_path(simulation_id)

    def initialize_runtime(self) -> None:
        ensure_directory(self.commands_dir)
        ensure_directory(self.responses_dir)
        # Purge any stale commands from a previous run so they don't affect restarts.
        for stale in self.commands_dir.glob("*.json"):
            stale.unlink(missing_ok=True)
        if not self.run_state_path.exists():
            self.write_run_state(
                {
                    "simulation_id": self.simulation_id,
                    "status": "created",
                    "current_round": 0,
                    "twitter_actions_count": 0,
                    "reddit_actions_count": 0,
                    "interactive_ready": False,
                }
            )
        if not self.env_status_path.exists():
            self.write_env_status(status="created", current_round=0)

    def write_run_state(self, payload: dict[str, Any]) -> None:
        payload = dict(payload)
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        ensure_parent_directory(self.run_state_path)
        self.run_state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def write_env_status(self, *, status: str, **fields: Any) -> None:
        payload = {
            "simulation_id": self.simulation_id,
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **fields,
        }
        ensure_parent_directory(self.env_status_path)
        self.env_status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def consume_commands(self) -> list[IPCCommand]:
        ensure_directory(self.commands_dir)
        commands: list[IPCCommand] = []
        for path in sorted(self.commands_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("command file must contain a JSON object")
                command = str(data.get("command") or "").strip()
                if not command:
                    raise ValueError("command field is required")
                commands.append(
                    IPCCommand(
                        command_id=path.stem,
                        command=command,
                        payload={key: value for key, value in data.items() if key != "command"},
                    )
                )
            except Exception as exc:
                logger.warning("failed to parse simulation command %s: %s", path, exc)
            finally:
                path.unlink(missing_ok=True)
        return commands

    def write_response(self, *, command_id: str, payload: dict[str, Any]) -> Path:
        ensure_directory(self.responses_dir)
        filename = f"{command_id}_{uuid4().hex[:8]}.json"
        target = self.responses_dir / filename
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..utils import get_logger
from ..utils.path_resolver import (
    ensure_parent_directory,
    simulation_reddit_actions_path,
    simulation_reddit_database_path,
    simulation_twitter_actions_path,
    simulation_twitter_database_path,
)

logger = get_logger("fyp.action_logger")


class ActionLogger:
    def __init__(self, simulation_id: str) -> None:
        self.simulation_id = simulation_id

    def reset_platform_storage(self, platform: str) -> None:
        action_path = self._action_path(platform)
        database_path = self._database_path(platform)

        ensure_parent_directory(action_path)
        action_path.write_text("", encoding="utf-8")

        ensure_parent_directory(database_path)
        if database_path.exists():
            database_path.unlink()

        with sqlite3.connect(database_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    simulation_id TEXT NOT NULL,
                    round_number INTEGER NOT NULL,
                    platform TEXT NOT NULL,
                    agent_id INTEGER NOT NULL,
                    agent_name TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    topic TEXT,
                    content TEXT,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def append_actions(self, platform: str, actions: list[dict[str, Any]]) -> None:
        if not actions:
            return

        action_path = self._action_path(platform)
        database_path = self._database_path(platform)
        ensure_parent_directory(action_path)
        ensure_parent_directory(database_path)

        with action_path.open("a", encoding="utf-8") as handle:
            for action in actions:
                payload = dict(action)
                payload.setdefault("created_at", datetime.now(timezone.utc).isoformat())
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

        with sqlite3.connect(database_path) as conn:
            conn.executemany(
                """
                INSERT INTO actions (
                    created_at,
                    simulation_id,
                    round_number,
                    platform,
                    agent_id,
                    agent_name,
                    action_type,
                    topic,
                    content,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(action.get("created_at") or datetime.now(timezone.utc).isoformat()),
                        self.simulation_id,
                        int(action.get("round_number") or 0),
                        platform,
                        int(action.get("agent_id") or 0),
                        str(action.get("agent_name") or ""),
                        str(action.get("action_type") or ""),
                        str(action.get("topic") or ""),
                        str(action.get("content") or ""),
                        json.dumps(action.get("metadata") or {}, ensure_ascii=False),
                    )
                    for action in actions
                ],
            )
            conn.commit()

        logger.info(
            "logged %s %s actions for simulation %s",
            len(actions),
            platform,
            self.simulation_id,
        )

    def _action_path(self, platform: str) -> Path:
        if platform == "twitter":
            return simulation_twitter_actions_path(self.simulation_id)
        if platform == "reddit":
            return simulation_reddit_actions_path(self.simulation_id)
        raise ValueError(f"unsupported platform: {platform}")

    def _database_path(self, platform: str) -> Path:
        if platform == "twitter":
            return simulation_twitter_database_path(self.simulation_id)
        if platform == "reddit":
            return simulation_reddit_database_path(self.simulation_id)
        raise ValueError(f"unsupported platform: {platform}")

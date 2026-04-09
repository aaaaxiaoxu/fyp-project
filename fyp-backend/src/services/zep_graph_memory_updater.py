from __future__ import annotations

from typing import Any

from ..utils import get_logger

logger = get_logger("fyp.zep_graph_memory_updater")


class ZepGraphMemoryUpdater:
    def __init__(self, *, graph_id: str | None) -> None:
        self.graph_id = graph_id

    def record_round(self, round_number: int, actions: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.graph_id or not actions:
            return {
                "graph_id": self.graph_id,
                "round_number": round_number,
                "action_count": len(actions),
                "updated": False,
            }

        logger.info(
            "skipping live graph memory write for graph %s on round %s with %s actions",
            self.graph_id,
            round_number,
            len(actions),
        )
        return {
            "graph_id": self.graph_id,
            "round_number": round_number,
            "action_count": len(actions),
            "updated": False,
        }

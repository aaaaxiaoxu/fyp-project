from __future__ import annotations

import asyncio
from typing import Any

from zep_cloud.client import Zep

from ..settings import settings
from ..utils import get_logger

logger = get_logger("fyp.zep_graph_memory_updater")

# Action types whose content is worth writing to the knowledge graph
_NARRATIVE_ACTIONS = frozenset({
    "CREATE_POST",
    "CREATE_COMMENT",
    "QUOTE_POST",
})

# Maximum actions to surface per round in the Zep text snippet
_MAX_ACTIONS_IN_SUMMARY = 10


class ZepGraphMemoryUpdater:
    """Write per-round simulation summaries to a Zep knowledge graph.

    Each round's significant actions (posts, comments, quote-posts) are
    serialised as a short text episode and added to the graph so that the
    Explorer's search tools can reason about *what happened* during the
    simulation.
    """

    def __init__(self, *, graph_id: str | None) -> None:
        self.graph_id = graph_id
        self._client: Zep | None = None

    async def record_round(self, round_number: int, actions: list[dict[str, Any]]) -> dict[str, Any]:
        """Write a round summary to Zep.  Always returns a status dict."""
        base = {
            "graph_id": self.graph_id,
            "round_number": round_number,
            "action_count": len(actions),
            "updated": False,
        }

        if not self.graph_id or not actions:
            return base

        try:
            client = self._get_client()
        except ValueError:
            # ZEP_API_KEY not configured — skip silently (not a hard error)
            logger.debug("ZEP_API_KEY not configured; skipping memory update for round %s", round_number)
            return base

        summary = _build_round_summary(round_number, actions)
        try:
            await asyncio.to_thread(
                client.graph.add,
                data=summary,
                type="text",
                graph_id=self.graph_id,
                source_description=f"simulation_round_{round_number}",
            )
            logger.info(
                "wrote round %s summary to Zep graph %s (%s actions)",
                round_number,
                self.graph_id,
                len(actions),
            )
            return {**base, "updated": True}
        except Exception:
            logger.exception(
                "failed to update Zep graph %s for round %s",
                self.graph_id,
                round_number,
            )
            return base

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_client(self) -> Zep:
        if self._client is None:
            api_key = settings.ZEP_API_KEY.strip()
            if not api_key:
                raise ValueError("ZEP_API_KEY 未配置")
            base_url = settings.ZEP_BASE_URL.strip() or None
            self._client = Zep(api_key=api_key, base_url=base_url)
        return self._client


def _build_round_summary(round_number: int, actions: list[dict[str, Any]]) -> str:
    """Produce a concise text episode for the given round's actions.

    Prioritises posts/comments with content, falls back to all actions.
    """
    # Prefer narrative actions with actual content
    narrative = [
        a for a in actions
        if a.get("action_type") in _NARRATIVE_ACTIONS and a.get("content")
    ]
    sampled = (narrative or actions)[:_MAX_ACTIONS_IN_SUMMARY]

    header = f"Simulation round {round_number} — {len(actions)} action(s) total."
    lines = [header]
    for a in sampled:
        platform = str(a.get("platform") or "")
        agent = str(a.get("agent_name") or f"Agent {a.get('agent_id', '?')}")
        action_type = str(a.get("action_type") or "action").replace("_", " ").lower()
        content = str(a.get("content") or "").strip()[:160]

        entry = f"  [{platform}] {agent} {action_type}"
        if content:
            entry += f': "{content}"'
        lines.append(entry)

    return "\n".join(lines)

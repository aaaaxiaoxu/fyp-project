from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..utils import get_logger
from .action_logger import ActionLogger

logger = get_logger("fyp.simulation_runner")


@dataclass(frozen=True, slots=True)
class RoundExecutionResult:
    round_number: int
    twitter_actions: list[dict[str, Any]]
    reddit_actions: list[dict[str, Any]]

    @property
    def all_actions(self) -> list[dict[str, Any]]:
        return [*self.twitter_actions, *self.reddit_actions]


class SimulationRunner:
    def __init__(
        self,
        *,
        simulation_id: str,
        config: dict[str, Any],
        profiles: list[dict[str, Any]],
        total_rounds: int,
        twitter_enabled: bool,
        reddit_enabled: bool,
    ) -> None:
        self.simulation_id = simulation_id
        self.config = config
        self.profiles = profiles
        self.total_rounds = max(1, total_rounds)
        self.twitter_enabled = twitter_enabled
        self.reddit_enabled = reddit_enabled
        self.agent_configs = list(config.get("agent_configs") or [])
        self.hot_topics = list(((config.get("event_config") or {}).get("hot_topics")) or [])
        self.twitter_actions = list(((config.get("twitter_config") or {}).get("available_actions")) or [])
        self.reddit_actions = list(((config.get("reddit_config") or {}).get("available_actions")) or [])
        self.profiles_by_id = {
            int(profile.get("user_id") or 0): profile
            for profile in self.profiles
            if isinstance(profile, dict) and profile.get("user_id") is not None
        }

    def prepare_environment(self, action_logger: ActionLogger) -> None:
        if self.twitter_enabled:
            action_logger.reset_platform_storage("twitter")
        if self.reddit_enabled:
            action_logger.reset_platform_storage("reddit")

    def execute_round(self, round_number: int) -> RoundExecutionResult:
        twitter_actions = self._build_actions_for_platform("twitter", round_number) if self.twitter_enabled else []
        reddit_actions = self._build_actions_for_platform("reddit", round_number) if self.reddit_enabled else []
        logger.info(
            "generated round %s for simulation %s: twitter=%s reddit=%s",
            round_number,
            self.simulation_id,
            len(twitter_actions),
            len(reddit_actions),
        )
        return RoundExecutionResult(
            round_number=round_number,
            twitter_actions=twitter_actions,
            reddit_actions=reddit_actions,
        )

    def _build_actions_for_platform(self, platform: str, round_number: int) -> list[dict[str, Any]]:
        available_actions = self.twitter_actions if platform == "twitter" else self.reddit_actions
        available_actions = [action for action in available_actions if action != "DO_NOTHING"] or ["CREATE_POST"]
        if not self.agent_configs:
            return []

        min_agents = int(((self.config.get("time_config") or {}).get("agents_per_hour_min")) or 1)
        max_agents = int(((self.config.get("time_config") or {}).get("agents_per_hour_max")) or len(self.agent_configs))
        max_agents = max(1, min(max_agents, len(self.agent_configs)))
        min_agents = max(1, min(min_agents, max_agents))
        active_count = min_agents + ((round_number - 1) % max(1, max_agents - min_agents + 1))

        start_index = (round_number - 1) % len(self.agent_configs)
        active_agents = [
            self.agent_configs[(start_index + offset) % len(self.agent_configs)]
            for offset in range(active_count)
        ]

        actions: list[dict[str, Any]] = []
        for index, agent in enumerate(active_agents):
            agent_id = int(agent.get("agent_id") or 0)
            profile = self.profiles_by_id.get(agent_id, {})
            agent_name = str(agent.get("entity_name") or profile.get("name") or f"Agent {agent_id}")
            topic = self._select_topic(agent, profile, round_number, platform)
            rng = random.Random(f"{self.simulation_id}:{platform}:{round_number}:{agent_id}:{index}")
            action_type = available_actions[rng.randrange(len(available_actions))]
            actions.append(
                {
                    "simulation_id": self.simulation_id,
                    "platform": platform,
                    "round_number": round_number,
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "action_type": action_type,
                    "topic": topic,
                    "content": self._build_content(
                        platform=platform,
                        action_type=action_type,
                        topic=topic,
                        agent_name=agent_name,
                        round_number=round_number,
                    ),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "entity_type": str(agent.get("entity_type") or profile.get("source_entity_type") or "Entity"),
                        "influence_weight": agent.get("influence_weight"),
                    },
                }
            )
        return actions

    def _select_topic(
        self,
        agent_config: dict[str, Any],
        profile: dict[str, Any],
        round_number: int,
        platform: str,
    ) -> str:
        profile_topics = [str(item) for item in profile.get("interested_topics") or [] if str(item).strip()]
        topics = profile_topics or self.hot_topics or [str(agent_config.get("entity_type") or platform)]
        index = (round_number - 1) % len(topics)
        return topics[index]

    def _build_content(
        self,
        *,
        platform: str,
        action_type: str,
        topic: str,
        agent_name: str,
        round_number: int,
    ) -> str:
        if platform == "twitter":
            return f"{agent_name} uses {action_type} on {topic} during round {round_number}."
        return f"{agent_name} contributes via {action_type} around {topic} in round {round_number}."

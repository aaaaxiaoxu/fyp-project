from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable

from ..settings import settings
from ..utils.llm_client import LLMClient
from .oasis_profile_generator import OasisAgentProfile
from .zep_entity_reader import EntityNode

CONFIG_SYSTEM_PROMPT = """你是一个社交模拟配置生成器。

请根据给定的模拟需求、实体信息和默认参数，输出一个 JSON 对象，可包含以下字段：
- time_config
- event_config
- twitter_config
- reddit_config

要求：
1. 只输出有效 JSON
2. 不要删除默认结构中未出现的必需字段
3. 取值必须适合多 Agent 社交舆论模拟
"""

_HIGH_INFLUENCE_TYPES = {"MediaOutlet", "GovernmentAgency", "Government", "Organization", "Company"}


@dataclass(frozen=True, slots=True)
class AgentActivityConfig:
    agent_id: int
    entity_uuid: str
    entity_name: str
    entity_type: str
    activity_level: float
    posts_per_hour: float
    comments_per_hour: float
    active_hours: list[int]
    response_delay_min: int
    response_delay_max: int
    sentiment_bias: float
    stance: str
    influence_weight: float


@dataclass(frozen=True, slots=True)
class TimeSimulationConfig:
    total_simulation_hours: int
    minutes_per_round: int
    agents_per_hour_min: int
    agents_per_hour_max: int
    peak_hours: list[int] = field(default_factory=lambda: [19, 20, 21, 22])
    peak_activity_multiplier: float = 1.5
    off_peak_hours: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5])
    off_peak_activity_multiplier: float = 0.08
    morning_hours: list[int] = field(default_factory=lambda: [6, 7, 8])
    morning_activity_multiplier: float = 0.45
    work_hours: list[int] = field(default_factory=lambda: [9, 10, 11, 12, 13, 14, 15, 16, 17, 18])
    work_activity_multiplier: float = 0.8


@dataclass(frozen=True, slots=True)
class EventConfig:
    initial_posts: list[dict[str, Any]] = field(default_factory=list)
    scheduled_events: list[dict[str, Any]] = field(default_factory=list)
    hot_topics: list[str] = field(default_factory=list)
    narrative_direction: str = ""


@dataclass(frozen=True, slots=True)
class PlatformConfig:
    platform: str
    recency_weight: float
    popularity_weight: float
    relevance_weight: float
    viral_threshold: int
    echo_chamber_strength: float
    available_actions: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SimulationParameters:
    simulation_id: str
    project_id: str
    graph_id: str
    simulation_requirement: str
    time_config: TimeSimulationConfig
    agent_configs: list[AgentActivityConfig]
    event_config: EventConfig
    twitter_config: PlatformConfig | None
    reddit_config: PlatformConfig | None
    llm_model: str
    llm_base_url: str
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    generation_reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "time_config": asdict(self.time_config),
            "agent_configs": [asdict(item) for item in self.agent_configs],
            "event_config": asdict(self.event_config),
            "twitter_config": asdict(self.twitter_config) if self.twitter_config is not None else None,
            "reddit_config": asdict(self.reddit_config) if self.reddit_config is not None else None,
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "generated_at": self.generated_at,
            "generation_reasoning": self.generation_reasoning,
        }


class SimulationConfigGenerator:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    @property
    def _client(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def generate_config(
        self,
        *,
        simulation_id: str,
        project_id: str,
        graph_id: str,
        simulation_requirement: str,
        document_text: str,
        entities: list[EntityNode],
        profiles: list[OasisAgentProfile],
        enable_twitter: bool = True,
        enable_reddit: bool = True,
        use_llm: bool = True,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> SimulationParameters:
        if progress_callback is not None:
            progress_callback(1, 3, "building default simulation config")

        defaults = self._build_defaults(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            simulation_requirement=simulation_requirement,
            entities=entities,
            profiles=profiles,
            enable_twitter=enable_twitter,
            enable_reddit=enable_reddit,
        )

        reasoning = "heuristic defaults"
        if use_llm:
            if progress_callback is not None:
                progress_callback(2, 3, "refining config with llm")
            try:
                overrides = self._client.chat_json(
                    messages=[
                        {"role": "system", "content": CONFIG_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": self._build_llm_prompt(
                                simulation_requirement=simulation_requirement,
                                document_text=document_text,
                                entities=entities,
                                defaults=defaults,
                            ),
                        },
                    ],
                    temperature=0.3,
                    max_tokens=1600,
                )
                defaults = self._apply_overrides(defaults, overrides)
                reasoning = "llm refined"
            except Exception:
                reasoning = "heuristic defaults (llm fallback)"

        if progress_callback is not None:
            progress_callback(3, 3, "finalizing simulation config")

        return SimulationParameters(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            simulation_requirement=simulation_requirement,
            time_config=defaults["time_config"],
            agent_configs=defaults["agent_configs"],
            event_config=defaults["event_config"],
            twitter_config=defaults["twitter_config"],
            reddit_config=defaults["reddit_config"],
            llm_model=settings.LLM_MODEL,
            llm_base_url=settings.LLM_BASE_URL,
            generation_reasoning=reasoning,
        )

    def _build_defaults(
        self,
        *,
        simulation_id: str,
        project_id: str,
        graph_id: str,
        simulation_requirement: str,
        entities: list[EntityNode],
        profiles: list[OasisAgentProfile],
        enable_twitter: bool,
        enable_reddit: bool,
    ) -> dict[str, Any]:
        entity_count = max(1, len(entities))
        total_hours = min(72, max(24, 12 + entity_count * 2))
        minutes_per_round = 60
        total_rounds = max(1, math.ceil(total_hours * 60 / minutes_per_round))
        per_hour_max = min(entity_count, max(3, math.ceil(entity_count * 0.35)))
        per_hour_min = min(per_hour_max, max(1, math.floor(per_hour_max * 0.5)))

        time_config = TimeSimulationConfig(
            total_simulation_hours=total_hours,
            minutes_per_round=minutes_per_round,
            agents_per_hour_min=per_hour_min,
            agents_per_hour_max=per_hour_max,
        )
        agent_configs = [self._build_agent_config(profile) for profile in profiles]
        event_config = self._build_event_config(simulation_requirement, profiles, total_rounds)
        twitter_config = (
            PlatformConfig(
                platform="twitter",
                recency_weight=0.45,
                popularity_weight=0.3,
                relevance_weight=0.25,
                viral_threshold=12,
                echo_chamber_strength=0.55,
                available_actions=list(settings.OASIS_TWITTER_ACTIONS),
            )
            if enable_twitter
            else None
        )
        reddit_config = (
            PlatformConfig(
                platform="reddit",
                recency_weight=0.35,
                popularity_weight=0.4,
                relevance_weight=0.25,
                viral_threshold=8,
                echo_chamber_strength=0.62,
                available_actions=list(settings.OASIS_REDDIT_ACTIONS),
            )
            if enable_reddit
            else None
        )
        return {
            "simulation_id": simulation_id,
            "project_id": project_id,
            "graph_id": graph_id,
            "simulation_requirement": simulation_requirement,
            "time_config": time_config,
            "agent_configs": agent_configs,
            "event_config": event_config,
            "twitter_config": twitter_config,
            "reddit_config": reddit_config,
        }

    def _build_agent_config(self, profile: OasisAgentProfile) -> AgentActivityConfig:
        entity_type = profile.source_entity_type or "Entity"
        high_influence = entity_type in _HIGH_INFLUENCE_TYPES
        activity_level = 0.78 if high_influence else 0.58
        active_hours = list(range(8, 23)) if not high_influence else list(range(7, 24))
        posts_per_hour = 1.6 if high_influence else 0.9
        comments_per_hour = 2.3 if high_influence else 1.5
        influence_weight = max(0.8, min(2.8, profile.follower_count / 700))

        return AgentActivityConfig(
            agent_id=profile.user_id,
            entity_uuid=profile.source_entity_uuid or "",
            entity_name=profile.name,
            entity_type=entity_type,
            activity_level=round(activity_level, 2),
            posts_per_hour=round(posts_per_hour, 2),
            comments_per_hour=round(comments_per_hour, 2),
            active_hours=active_hours,
            response_delay_min=5 if high_influence else 10,
            response_delay_max=45 if high_influence else 90,
            sentiment_bias=0.0,
            stance="neutral",
            influence_weight=round(influence_weight, 2),
        )

    def _build_event_config(
        self,
        simulation_requirement: str,
        profiles: list[OasisAgentProfile],
        total_rounds: int,
    ) -> EventConfig:
        hot_topics: list[str] = []
        for profile in profiles:
            for topic in profile.interested_topics:
                if topic not in hot_topics:
                    hot_topics.append(topic)
                if len(hot_topics) >= 6:
                    break
            if len(hot_topics) >= 6:
                break

        initial_posts: list[dict[str, Any]] = []
        for profile in sorted(profiles, key=lambda item: item.follower_count, reverse=True)[: min(3, len(profiles))]:
            topic = hot_topics[0] if hot_topics else "public discussion"
            initial_posts.append(
                {
                    "poster_agent_id": profile.user_id,
                    "platform": "twitter",
                    "topic": topic,
                    "content": f"{profile.name} kicks off a discussion about {topic} around the requirement: {simulation_requirement[:120]}",
                }
            )

        scheduled_events = []
        if total_rounds >= 12:
            scheduled_events.append(
                {
                    "round": min(6, total_rounds // 2),
                    "topic": hot_topics[1] if len(hot_topics) > 1 else "follow-up discussion",
                    "description": "Mid-cycle discussion spike",
                }
            )

        return EventConfig(
            initial_posts=initial_posts,
            scheduled_events=scheduled_events,
            hot_topics=hot_topics,
            narrative_direction=simulation_requirement[:240],
        )

    def _build_llm_prompt(
        self,
        *,
        simulation_requirement: str,
        document_text: str,
        entities: list[EntityNode],
        defaults: dict[str, Any],
    ) -> str:
        entity_preview = [
            {
                "name": entity.name,
                "type": entity.get_entity_type() or "Entity",
                "summary": entity.summary[:120],
            }
            for entity in entities[:12]
        ]
        doc_excerpt = document_text[:5000]
        return (
            f"模拟需求:\n{simulation_requirement}\n\n"
            f"文档摘录:\n{doc_excerpt}\n\n"
            f"实体预览:\n{entity_preview}\n\n"
            f"默认配置:\n{SimulationParameters(**defaults, llm_model=settings.LLM_MODEL, llm_base_url=settings.LLM_BASE_URL).to_dict()}\n\n"
            "请仅返回需要覆盖的字段，不要重复全部配置。"
        )

    def _apply_overrides(self, defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
        merged = dict(defaults)

        time_overrides = overrides.get("time_config")
        if isinstance(time_overrides, dict):
            current = asdict(merged["time_config"])
            current.update({key: value for key, value in time_overrides.items() if key in current})
            merged["time_config"] = TimeSimulationConfig(**current)

        event_overrides = overrides.get("event_config")
        if isinstance(event_overrides, dict):
            current = asdict(merged["event_config"])
            current.update({key: value for key, value in event_overrides.items() if key in current})
            merged["event_config"] = EventConfig(**current)

        for key in ("twitter_config", "reddit_config"):
            config_overrides = overrides.get(key)
            if merged.get(key) is None or not isinstance(config_overrides, dict):
                continue
            current = asdict(merged[key])
            current.update({field: value for field, value in config_overrides.items() if field in current})
            merged[key] = PlatformConfig(**current)

        return merged

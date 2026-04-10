from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from camel.models import ModelFactory
from camel.types import ModelPlatformType
import oasis
from oasis.environment.env_action import LLMAction, ManualAction
from oasis.social_agent.agent import SocialAgent
from oasis.social_agent.agent_graph import AgentGraph
from oasis.social_platform.config import UserInfo
from oasis.social_platform.typing import ActionType, DefaultPlatformType

from ..settings import settings
from ..utils import get_logger
from ..utils.path_resolver import (
    ensure_parent_directory,
    simulation_oasis_reddit_db_path,
    simulation_oasis_twitter_db_path,
)
from .action_logger import ActionLogger

logger = get_logger("fyp.simulation_runner")

# Actions that add no analytical value — skip from JSONL log
_SKIP_ACTIONS: frozenset[str] = frozenset({
    "do_nothing",
    "sign_up",
    "update_rec_table",
    "exit",
})


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

        self.agent_configs: list[dict[str, Any]] = list(config.get("agent_configs") or [])
        self.hot_topics: list[str] = list(((config.get("event_config") or {}).get("hot_topics")) or [])
        self.twitter_actions: list[str] = list(((config.get("twitter_config") or {}).get("available_actions")) or [])
        self.reddit_actions: list[str] = list(((config.get("reddit_config") or {}).get("available_actions")) or [])
        self.initial_posts: list[dict[str, Any]] = list(((config.get("event_config") or {}).get("initial_posts")) or [])
        self.profiles_by_id: dict[int, dict[str, Any]] = {
            int(profile.get("user_id") or 0): profile
            for profile in self.profiles
            if isinstance(profile, dict) and profile.get("user_id") is not None
        }

        # OASIS runtime state — populated by setup()
        self._twitter_env: oasis.environment.env.OasisEnv | None = None
        self._reddit_env: oasis.environment.env.OasisEnv | None = None
        self._twitter_agents: list[SocialAgent] = []
        self._reddit_agents: list[SocialAgent] = []
        self._twitter_trace_rowid: int = 0
        self._reddit_trace_rowid: int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def prepare_environment(self, action_logger: ActionLogger) -> None:
        """Reset per-platform action storage and remove stale OASIS DB files."""
        if self.twitter_enabled:
            action_logger.reset_platform_storage("twitter")
            _try_delete(simulation_oasis_twitter_db_path(self.simulation_id))
        if self.reddit_enabled:
            action_logger.reset_platform_storage("reddit")
            _try_delete(simulation_oasis_reddit_db_path(self.simulation_id))

    async def setup(self) -> None:
        """Build OASIS environments and sign up all agents."""
        if not self.agent_configs:
            logger.warning("no agent_configs in simulation %s — OASIS envs skipped", self.simulation_id)
            return

        model = _build_camel_model()

        if self.twitter_enabled:
            logger.info("setting up twitter OASIS env for simulation %s", self.simulation_id)
            db_path = simulation_oasis_twitter_db_path(self.simulation_id)
            ensure_parent_directory(db_path)
            env, agents = await _setup_platform(
                simulation_id=self.simulation_id,
                platform=DefaultPlatformType.TWITTER,
                db_path=str(db_path),
                agent_configs=self.agent_configs,
                profiles_by_id=self.profiles_by_id,
                available_actions=_parse_action_types(self.twitter_actions),
                model=model,
            )
            self._twitter_env = env
            self._twitter_agents = agents
            self._twitter_trace_rowid = _get_max_trace_rowid(db_path)
            logger.info("twitter env ready with %s agents", len(agents))

        if self.reddit_enabled:
            logger.info("setting up reddit OASIS env for simulation %s", self.simulation_id)
            db_path = simulation_oasis_reddit_db_path(self.simulation_id)
            ensure_parent_directory(db_path)
            env, agents = await _setup_platform(
                simulation_id=self.simulation_id,
                platform=DefaultPlatformType.REDDIT,
                db_path=str(db_path),
                agent_configs=self.agent_configs,
                profiles_by_id=self.profiles_by_id,
                available_actions=_parse_action_types(self.reddit_actions),
                model=model,
            )
            self._reddit_env = env
            self._reddit_agents = agents
            self._reddit_trace_rowid = _get_max_trace_rowid(db_path)
            logger.info("reddit env ready with %s agents", len(agents))

    async def teardown(self) -> None:
        """Gracefully close all OASIS platform environments."""
        for env_name, env in (("twitter", self._twitter_env), ("reddit", self._reddit_env)):
            if env is not None:
                try:
                    await env.close()
                    logger.info("%s OASIS env closed", env_name)
                except Exception:
                    logger.exception("error closing %s OASIS env", env_name)
        self._twitter_env = None
        self._reddit_env = None
        self._twitter_agents = []
        self._reddit_agents = []

    # ------------------------------------------------------------------
    # Round execution
    # ------------------------------------------------------------------

    async def execute_round(self, round_number: int) -> RoundExecutionResult:
        twitter_actions: list[dict[str, Any]] = []
        reddit_actions: list[dict[str, Any]] = []

        if self._twitter_env is not None and self._twitter_agents:
            actions_dict = _build_actions_dict(
                agents=self._twitter_agents,
                platform="twitter",
                round_number=round_number,
                initial_posts=self.initial_posts,
            )
            try:
                await self._twitter_env.step(actions_dict)
            except Exception as exc:
                logger.exception("twitter env.step failed at round %s (sim %s)", round_number, self.simulation_id)
                raise RuntimeError(f"twitter OASIS step failed at round {round_number}") from exc
            else:
                db_path = simulation_oasis_twitter_db_path(self.simulation_id)
                new_rows = _extract_new_traces(db_path, self._twitter_trace_rowid)
                if new_rows:
                    self._twitter_trace_rowid = new_rows[-1]["rowid"]
                twitter_actions = [
                    self._trace_to_action(row, "twitter", round_number)
                    for row in new_rows
                    if str(row.get("action") or "").lower() not in _SKIP_ACTIONS
                ]

        if self._reddit_env is not None and self._reddit_agents:
            actions_dict = _build_actions_dict(
                agents=self._reddit_agents,
                platform="reddit",
                round_number=round_number,
                initial_posts=self.initial_posts,
            )
            try:
                await self._reddit_env.step(actions_dict)
            except Exception as exc:
                logger.exception("reddit env.step failed at round %s (sim %s)", round_number, self.simulation_id)
                raise RuntimeError(f"reddit OASIS step failed at round {round_number}") from exc
            else:
                db_path = simulation_oasis_reddit_db_path(self.simulation_id)
                new_rows = _extract_new_traces(db_path, self._reddit_trace_rowid)
                if new_rows:
                    self._reddit_trace_rowid = new_rows[-1]["rowid"]
                reddit_actions = [
                    self._trace_to_action(row, "reddit", round_number)
                    for row in new_rows
                    if str(row.get("action") or "").lower() not in _SKIP_ACTIONS
                ]

        logger.info(
            "round %s sim %s: twitter=%s reddit=%s",
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _trace_to_action(self, row: dict[str, Any], platform: str, round_number: int) -> dict[str, Any]:
        agent_id = int(row.get("user_id") or 0)
        profile = self.profiles_by_id.get(agent_id, {})
        agent_name = str(profile.get("name") or f"Agent {agent_id}")
        action_type = str(row.get("action") or "").upper()

        info: dict[str, Any] = {}
        try:
            raw_info = row.get("info") or "{}"
            info = json.loads(raw_info) if isinstance(raw_info, str) else {}
        except (json.JSONDecodeError, TypeError):
            pass

        content = str(info.get("content") or info.get("comment") or info.get("quote_content") or "")

        return {
            "simulation_id": self.simulation_id,
            "platform": platform,
            "round_number": round_number,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "action_type": action_type,
            "topic": "",
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "entity_type": str(profile.get("source_entity_type") or "Entity"),
                "influence_weight": profile.get("influence_weight"),
                "oasis_info": info,
            },
        }


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


async def _setup_platform(
    *,
    simulation_id: str,
    platform: DefaultPlatformType,
    db_path: str,
    agent_configs: list[dict[str, Any]],
    profiles_by_id: dict[int, dict[str, Any]],
    available_actions: list[ActionType] | None,
    model: Any,
) -> tuple[Any, list[SocialAgent]]:
    agent_graph = AgentGraph()

    for agent_cfg in agent_configs:
        agent_id = int(agent_cfg.get("agent_id") or 0)
        profile = profiles_by_id.get(agent_id, {})

        persona = str(profile.get("persona") or profile.get("bio") or f"Agent {agent_id} in a social simulation.")
        username = str(profile.get("username") or f"agent_{agent_id}")
        name = str(profile.get("name") or username)
        bio = str(profile.get("bio") or "Participating in a social simulation.")

        user_info = UserInfo(
            user_name=username,
            name=name,
            description=bio,
            profile={"other_info": {"user_profile": persona}},
            recsys_type=platform.value,
        )
        agent = SocialAgent(
            agent_id=agent_id,
            user_info=user_info,
            model=model,
            agent_graph=agent_graph,
            available_actions=available_actions or None,
        )
        agent_graph.add_agent(agent)

    env = oasis.make(
        agent_graph=agent_graph,
        platform=platform,
        database_path=db_path,
    )
    await env.reset()

    agents = [agent for _, agent in agent_graph.get_agents()]
    return env, agents


def _build_actions_dict(
    *,
    agents: list[SocialAgent],
    platform: str,
    round_number: int,
    initial_posts: list[dict[str, Any]],
) -> dict[SocialAgent, LLMAction | ManualAction]:
    # Build a map of agent_id → initial post content for round 1
    initial_by_agent: dict[int, str] = {}
    if round_number == 1:
        for post in initial_posts:
            if str(post.get("platform") or "") == platform:
                agent_id = int(post.get("poster_agent_id") or 0)
                content = str(post.get("content") or "").strip()
                if agent_id and content:
                    initial_by_agent[agent_id] = content

    actions: dict[SocialAgent, LLMAction | ManualAction] = {}
    for agent in agents:
        agent_id = agent.social_agent_id
        if agent_id in initial_by_agent:
            actions[agent] = ManualAction(
                action_type=ActionType.CREATE_POST,
                action_args={"content": initial_by_agent[agent_id]},
            )
        else:
            actions[agent] = LLMAction()
    return actions


def _extract_new_traces(db_path: Path, last_rowid: int) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    try:
        with sqlite3.connect(str(db_path), timeout=10) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT rowid, user_id, created_at, action, info FROM trace WHERE rowid > ? ORDER BY rowid",
                (last_rowid,),
            )
            return [dict(row) for row in cursor.fetchall()]
    except Exception:
        logger.exception("failed to extract trace rows from %s", db_path)
        return []


def _get_max_trace_rowid(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    try:
        with sqlite3.connect(str(db_path), timeout=10) as conn:
            row = conn.execute("SELECT MAX(rowid) FROM trace").fetchone()
            return int(row[0] or 0)
    except Exception:
        return 0


def _build_camel_model() -> Any:
    return ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
        model_type=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY or "placeholder",
        url=settings.LLM_BASE_URL,
        model_config_dict={"temperature": 0.3, "max_tokens": 800},
        max_retries=3,
    )


def _parse_action_types(action_names: list[str]) -> list[ActionType] | None:
    result: list[ActionType] = []
    for name in action_names:
        # Try enum key first (e.g., "CREATE_POST"), then lowercase value
        try:
            result.append(ActionType[name])
        except KeyError:
            try:
                result.append(ActionType(name.lower()))
            except ValueError:
                logger.warning("unknown OASIS action type: %s", name)
    return result if result else None


def _try_delete(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass

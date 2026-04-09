from __future__ import annotations

import asyncio
import csv
import json
import shutil
import sys
import time
import uuid
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db import SYSTEM_OWNER_ID, SessionLocal, init_db
from src.main import app
from src.models import Project, Simulation
from src.services import EventConfig, SimulationParameters, TimeSimulationConfig
from src.services.simulation_config_generator import AgentActivityConfig, PlatformConfig
from src.settings import settings
from src.utils.path_resolver import (
    as_upload_relative_path,
    project_dir,
    simulation_config_path,
    simulation_dir,
    simulation_env_status_path,
    simulation_profiles_dir,
    simulation_profiles_path,
    simulation_reddit_actions_path,
    simulation_reddit_database_path,
    simulation_reddit_profiles_path,
    simulation_run_state_path,
    simulation_twitter_actions_path,
    simulation_twitter_database_path,
    simulation_twitter_profiles_path,
)


def _set_runtime_defaults() -> None:
    if not settings.LLM_API_KEY.strip():
        settings.LLM_API_KEY = "task10-test-llm-key"
    if not settings.ZEP_API_KEY.strip():
        settings.ZEP_API_KEY = "task10-test-zep-key"


def _build_config(simulation_id: str, project_id: str) -> SimulationParameters:
    return SimulationParameters(
        simulation_id=simulation_id,
        project_id=project_id,
        graph_id="graph_task10_fake",
        simulation_requirement="simulate task10 validation",
        time_config=TimeSimulationConfig(
            total_simulation_hours=4,
            minutes_per_round=60,
            agents_per_hour_min=1,
            agents_per_hour_max=2,
        ),
        agent_configs=[
            AgentActivityConfig(
                agent_id=1,
                entity_uuid="node_alice",
                entity_name="Alice",
                entity_type="Student",
                activity_level=0.7,
                posts_per_hour=1.2,
                comments_per_hour=1.8,
                active_hours=list(range(8, 23)),
                response_delay_min=5,
                response_delay_max=30,
                sentiment_bias=0.0,
                stance="neutral",
                influence_weight=1.2,
            ),
            AgentActivityConfig(
                agent_id=2,
                entity_uuid="node_bob",
                entity_name="Bob",
                entity_type="Cadre",
                activity_level=0.8,
                posts_per_hour=1.4,
                comments_per_hour=2.0,
                active_hours=list(range(7, 24)),
                response_delay_min=5,
                response_delay_max=30,
                sentiment_bias=0.0,
                stance="neutral",
                influence_weight=1.5,
            ),
        ],
        event_config=EventConfig(
            initial_posts=[
                {
                    "poster_agent_id": 1,
                    "platform": "twitter",
                    "topic": "community policy",
                    "content": "Alice opens the discussion.",
                }
            ],
            scheduled_events=[{"round": 2, "topic": "follow-up", "description": "mid-run spike"}],
            hot_topics=["community policy", "production team"],
            narrative_direction="task10 validation flow",
        ),
        twitter_config=PlatformConfig(
            platform="twitter",
            recency_weight=0.45,
            popularity_weight=0.3,
            relevance_weight=0.25,
            viral_threshold=12,
            echo_chamber_strength=0.55,
            available_actions=list(settings.OASIS_TWITTER_ACTIONS),
        ),
        reddit_config=PlatformConfig(
            platform="reddit",
            recency_weight=0.35,
            popularity_weight=0.4,
            relevance_weight=0.25,
            viral_threshold=8,
            echo_chamber_strength=0.62,
            available_actions=list(settings.OASIS_REDDIT_ACTIONS),
        ),
        llm_model=settings.LLM_MODEL,
        llm_base_url=settings.LLM_BASE_URL,
        generation_reasoning="task10 validation config",
    )


def _write_runtime_inputs(simulation_id: str, project_id: str) -> None:
    simulation_root = simulation_dir(simulation_id)
    simulation_root.mkdir(parents=True, exist_ok=True)
    profiles_root = simulation_profiles_dir(simulation_id)
    profiles_root.mkdir(parents=True, exist_ok=True)

    config = _build_config(simulation_id, project_id)
    simulation_config_path(simulation_id).write_text(
        json.dumps(config.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    profiles_payload = [
        {
            "user_id": 1,
            "username": "agent_1",
            "name": "Alice",
            "bio": "Alice bio",
            "persona": "Alice persona",
            "profession": "student",
            "interested_topics": ["community policy", "education"],
            "source_entity_uuid": "node_alice",
            "source_entity_type": "Student",
            "follower_count": 210,
            "friend_count": 110,
            "statuses_count": 310,
        },
        {
            "user_id": 2,
            "username": "agent_2",
            "name": "Bob",
            "bio": "Bob bio",
            "persona": "Bob persona",
            "profession": "cadre",
            "interested_topics": ["production team", "leadership"],
            "source_entity_uuid": "node_bob",
            "source_entity_type": "Cadre",
            "follower_count": 320,
            "friend_count": 140,
            "statuses_count": 410,
        },
    ]
    simulation_profiles_path(simulation_id).write_text(
        json.dumps(profiles_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    simulation_reddit_profiles_path(simulation_id).write_text(
        json.dumps(
            [
                {
                    "user_id": profile["user_id"],
                    "username": profile["username"],
                    "name": profile["name"],
                    "bio": profile["bio"],
                    "persona": profile["persona"],
                    "karma": 1000 + index,
                }
                for index, profile in enumerate(profiles_payload, start=1)
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    with simulation_twitter_profiles_path(simulation_id).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "user_id",
                "username",
                "name",
                "bio",
                "persona",
                "friend_count",
                "follower_count",
                "statuses_count",
            ],
        )
        writer.writeheader()
        for profile in profiles_payload:
            writer.writerow(
                {
                    "user_id": profile["user_id"],
                    "username": profile["username"],
                    "name": profile["name"],
                    "bio": profile["bio"],
                    "persona": profile["persona"],
                    "friend_count": profile["friend_count"],
                    "follower_count": profile["follower_count"],
                    "statuses_count": profile["statuses_count"],
                }
            )


async def _create_project_and_simulation(suffix: str) -> tuple[str, str]:
    await init_db()
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    simulation_id = f"sim_{uuid.uuid4().hex[:12]}"

    project_dir(project_id).mkdir(parents=True, exist_ok=True)
    _write_runtime_inputs(simulation_id, project_id)

    async with SessionLocal() as session:
        session.add(
            Project(
                id=project_id,
                user_id=SYSTEM_OWNER_ID,
                name=f"Task 10 Project {suffix}",
                status="graph_completed",
                zep_graph_id="graph_task10_fake",
                simulation_requirement=f"simulate task10 {suffix}",
                ontology_path=f"projects/{project_id}/ontology.json",
                extracted_text_path=f"projects/{project_id}/extracted_text.txt",
            )
        )
        session.add(
            Simulation(
                id=simulation_id,
                project_id=project_id,
                user_id=SYSTEM_OWNER_ID,
                status="ready",
                twitter_enabled=True,
                reddit_enabled=True,
                interactive_ready=False,
                total_rounds=4,
                current_round=0,
                twitter_actions_count=0,
                reddit_actions_count=0,
                config_path=as_upload_relative_path(simulation_config_path(simulation_id)),
                profiles_dir=as_upload_relative_path(simulation_profiles_dir(simulation_id)),
                error=None,
            )
        )
        await session.commit()
    return project_id, simulation_id


async def _fetch_simulation(simulation_id: str) -> Simulation | None:
    async with SessionLocal() as session:
        return await session.scalar(select(Simulation).where(Simulation.id == simulation_id))


async def _cleanup(project_id: str, simulation_id: str) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(Simulation).where(Simulation.id == simulation_id))
        await session.execute(delete(Project).where(Project.id == project_id))
        await session.commit()

    shutil.rmtree(project_dir(project_id), ignore_errors=True)
    shutil.rmtree(simulation_dir(simulation_id), ignore_errors=True)


async def main() -> None:
    _set_runtime_defaults()
    suffix = uuid.uuid4().hex[:10]
    project_id, simulation_id = await _create_project_and_simulation(suffix)

    try:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(f"/api/simulation/start/{simulation_id}")
                assert response.status_code == 202, response.text
                payload = response.json()
                assert payload["simulation_id"] == simulation_id
                assert payload["status"] == "running"
                assert int(payload["pid"]) > 0

                simulation = await _fetch_simulation(simulation_id)
                assert simulation is not None
                assert simulation.status == "running"

                deadline = time.monotonic() + 10.0
                current_round_values: list[int] = []
                twitter_counts: list[int] = []
                reddit_counts: list[int] = []

                while time.monotonic() < deadline:
                    simulation = await _fetch_simulation(simulation_id)
                    assert simulation is not None
                    current_round_values.append(simulation.current_round)
                    twitter_counts.append(simulation.twitter_actions_count)
                    reddit_counts.append(simulation.reddit_actions_count)
                    if simulation.status in {"completed", "failed"}:
                        break
                    await asyncio.sleep(0.05)
                else:
                    raise TimeoutError("simulation start validation timed out")

                assert simulation.status == "completed", simulation.error
                assert simulation.current_round == 4
                assert simulation.twitter_actions_count > 0
                assert simulation.reddit_actions_count > 0
                assert simulation.interactive_ready is True
                assert max(current_round_values) >= 1
                assert max(twitter_counts) > 0
                assert max(reddit_counts) > 0

                assert simulation_run_state_path(simulation_id).exists()
                assert simulation_env_status_path(simulation_id).exists()
                assert simulation_twitter_actions_path(simulation_id).exists()
                assert simulation_reddit_actions_path(simulation_id).exists()
                assert simulation_twitter_actions_path(simulation_id).read_text(encoding="utf-8").strip()
                assert simulation_reddit_actions_path(simulation_id).read_text(encoding="utf-8").strip()
                assert simulation_twitter_database_path(simulation_id).exists()
                assert simulation_reddit_database_path(simulation_id).exists()
                assert simulation_twitter_database_path(simulation_id).stat().st_size > 0
                assert simulation_reddit_database_path(simulation_id).stat().st_size > 0

        print("task10_api_validation_ok")
    finally:
        await _cleanup(project_id, simulation_id)


if __name__ == "__main__":
    asyncio.run(main())

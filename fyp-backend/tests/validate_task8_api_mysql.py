from __future__ import annotations

import asyncio
import json
import shutil
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db import SYSTEM_OWNER_ID, SessionLocal, init_db
from src.main import app
from src.models import Project, Simulation, Task
from src.services import (
    EventConfig,
    OasisAgentProfile,
    SimulationParameters,
    TimeSimulationConfig,
)
from src.services.simulation_config_generator import AgentActivityConfig, PlatformConfig
from src.services.zep_entity_reader import EntityNode, FilteredEntities
from src.settings import settings
from src.utils.path_resolver import (
    as_upload_relative_path,
    project_dir,
    project_extracted_text_path,
    simulation_dir,
    simulation_reddit_profiles_path,
    simulation_twitter_profiles_path,
)


def _set_runtime_defaults() -> None:
    if not settings.LLM_API_KEY.strip():
        settings.LLM_API_KEY = "task8-test-llm-key"
    if not settings.ZEP_API_KEY.strip():
        settings.ZEP_API_KEY = "task8-test-zep-key"


def _fake_filter_entities_sync(graph_id: str, entity_types: list[str] | None):
    entities = [
        EntityNode(
            uuid="node_alice",
            name="Alice",
            labels=["Entity", "Student"],
            summary="Alice is a student organizer focused on campus policy.",
            attributes={"role": "student"},
            related_edges=[{"fact": "Alice debates policy reform"}],
            related_nodes=[{"uuid": "node_uni", "name": "FYP University", "labels": ["Entity", "University"], "summary": ""}],
        ),
        EntityNode(
            uuid="node_daily_news",
            name="Daily News",
            labels=["Entity", "MediaOutlet"],
            summary="Daily News covers higher education and public opinion.",
            attributes={"kind": "media"},
            related_edges=[{"fact": "Daily News reports on Alice"}],
            related_nodes=[{"uuid": "node_alice", "name": "Alice", "labels": ["Entity", "Student"], "summary": ""}],
        ),
    ]
    if entity_types:
        entities = [entity for entity in entities if entity.get_entity_type() in entity_types]
    return FilteredEntities(
        entities=entities,
        entity_types={entity.get_entity_type() or "Entity" for entity in entities},
        total_count=2,
        filtered_count=len(entities),
    )


def _fake_generate_profiles_sync(entities, use_llm_for_profiles, progress_callback):
    profiles = []
    total = len(entities)
    for index, entity in enumerate(entities, start=1):
        progress_callback(index, total, f"building profile for {entity.name}")
        profiles.append(
            OasisAgentProfile(
                user_id=index,
                username=f"agent_{index}",
                name=entity.name,
                bio=f"{entity.name} bio",
                persona=f"{entity.name} persona",
                profession=entity.get_entity_type(),
                interested_topics=[entity.get_entity_type() or "Entity", "public opinion"],
                source_entity_uuid=entity.uuid,
                source_entity_type=entity.get_entity_type(),
                karma=1000 + index,
                friend_count=100 + index,
                follower_count=200 + index,
                statuses_count=300 + index,
            )
        )
    return profiles


def _fake_generate_simulation_config_sync(
    simulation_id: str,
    project_id: str,
    graph_id: str,
    simulation_requirement: str,
    document_text: str,
    entities,
    profiles,
    twitter_enabled: bool,
    reddit_enabled: bool,
    use_llm_for_config: bool,
    progress_callback,
):
    progress_callback(1, 3, "building default simulation config")
    progress_callback(2, 3, "refining config with llm")
    progress_callback(3, 3, "finalizing simulation config")
    return SimulationParameters(
        simulation_id=simulation_id,
        project_id=project_id,
        graph_id=graph_id,
        simulation_requirement=simulation_requirement,
        time_config=TimeSimulationConfig(
            total_simulation_hours=24,
            minutes_per_round=60,
            agents_per_hour_min=1,
            agents_per_hour_max=2,
        ),
        agent_configs=[
            AgentActivityConfig(
                agent_id=profile.user_id,
                entity_uuid=profile.source_entity_uuid or "",
                entity_name=profile.name,
                entity_type=profile.source_entity_type or "Entity",
                activity_level=0.6,
                posts_per_hour=1.2,
                comments_per_hour=1.8,
                active_hours=list(range(8, 23)),
                response_delay_min=10,
                response_delay_max=60,
                sentiment_bias=0.0,
                stance="neutral",
                influence_weight=1.3,
            )
            for profile in profiles
        ],
        event_config=EventConfig(
            initial_posts=[
                {
                    "poster_agent_id": 1,
                    "platform": "twitter",
                    "topic": "Student",
                    "content": "Alice starts the discussion.",
                }
            ],
            scheduled_events=[],
            hot_topics=["Student", "MediaOutlet"],
            narrative_direction="simulate task8",
        ),
        twitter_config=PlatformConfig(
            platform="twitter",
            recency_weight=0.45,
            popularity_weight=0.3,
            relevance_weight=0.25,
            viral_threshold=12,
            echo_chamber_strength=0.55,
            available_actions=list(settings.OASIS_TWITTER_ACTIONS),
        )
        if twitter_enabled
        else None,
        reddit_config=PlatformConfig(
            platform="reddit",
            recency_weight=0.35,
            popularity_weight=0.4,
            relevance_weight=0.25,
            viral_threshold=8,
            echo_chamber_strength=0.62,
            available_actions=list(settings.OASIS_REDDIT_ACTIONS),
        )
        if reddit_enabled
        else None,
        llm_model=settings.LLM_MODEL,
        llm_base_url=settings.LLM_BASE_URL,
        generation_reasoning="task8 test config",
    )


async def _create_project_with_graph(suffix: str) -> str:
    await init_db()
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    project_root = project_dir(project_id)
    project_root.mkdir(parents=True, exist_ok=True)
    extracted_text_path = project_extracted_text_path(project_id)
    extracted_text_path.write_text(
        "Alice and Daily News are central actors in the document.",
        encoding="utf-8",
    )

    async with SessionLocal() as session:
        session.add(
            Project(
                id=project_id,
                user_id=SYSTEM_OWNER_ID,
                name=f"Task 8 Project {suffix}",
                status="graph_completed",
                zep_graph_id="graph_task8_fake",
                simulation_requirement=f"simulate task8 {suffix}",
                ontology_path=f"projects/{project_id}/ontology.json",
                extracted_text_path=as_upload_relative_path(extracted_text_path),
            )
        )
        await session.commit()
    return project_id


async def _poll_task(client: AsyncClient, task_id: str, timeout_s: float = 10.0) -> tuple[dict[str, object], list[int]]:
    deadline = time.monotonic() + timeout_s
    progress_values: list[int] = []
    while time.monotonic() < deadline:
        response = await client.get(f"/api/simulation/prepare/status/{task_id}")
        assert response.status_code == 200, response.text
        payload = response.json()
        progress_values.append(int(payload["progress"]))
        if payload["status"] in {"completed", "failed"}:
            return payload, progress_values
        await asyncio.sleep(0.05)
    raise TimeoutError(f"task polling timed out for {task_id}")


async def _fetch_simulation(simulation_id: str) -> Simulation | None:
    async with SessionLocal() as session:
        return await session.scalar(select(Simulation).where(Simulation.id == simulation_id))


async def _cleanup(project_id: str, simulation_id: str | None) -> None:
    async with SessionLocal() as session:
        if simulation_id:
            await session.execute(delete(Task).where(Task.simulation_id == simulation_id))
            await session.execute(delete(Simulation).where(Simulation.id == simulation_id))
        await session.execute(delete(Task).where(Task.project_id == project_id))
        await session.execute(delete(Project).where(Project.id == project_id))
        await session.commit()

    shutil.rmtree(project_dir(project_id), ignore_errors=True)
    if simulation_id:
        shutil.rmtree(simulation_dir(simulation_id), ignore_errors=True)


async def main() -> None:
    _set_runtime_defaults()
    suffix = uuid.uuid4().hex[:12]
    project_id = await _create_project_with_graph(suffix)
    simulation_id: str | None = None

    try:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                with patch("src.routers.simulation._filter_project_entities_sync", new=_fake_filter_entities_sync), patch(
                    "src.routers.simulation._generate_profiles_sync",
                    new=_fake_generate_profiles_sync,
                ), patch(
                    "src.routers.simulation._generate_simulation_config_sync",
                    new=_fake_generate_simulation_config_sync,
                ):
                    prepare_response = await client.post(
                        f"/api/simulation/prepare/{project_id}",
                        json={"use_llm_for_profiles": False, "use_llm_for_config": False},
                    )
                    assert prepare_response.status_code == 202, prepare_response.text
                    task_id = prepare_response.json()["task_id"]

                    task_payload, progress_values = await _poll_task(client, task_id)
                    assert task_payload["status"] == "completed"
                    assert task_payload["progress"] == 100
                    assert any(0 < value < 100 for value in progress_values)
                    simulation_id = task_payload["result_json"]["simulation_id"]

                    config_response = await client.get(f"/api/simulation/{simulation_id}/config")
                    assert config_response.status_code == 200, config_response.text
                    config_payload = config_response.json()
                    assert config_payload["simulation_id"] == simulation_id
                    assert len(config_payload["agent_configs"]) == 2

        assert simulation_id is not None
        stored_simulation = await _fetch_simulation(simulation_id)
        assert stored_simulation is not None
        assert stored_simulation.status == "ready"
        assert stored_simulation.config_path == f"simulations/{simulation_id}/simulation_config.json"
        assert stored_simulation.profiles_dir == f"simulations/{simulation_id}/profiles"

        reddit_profiles_path = simulation_reddit_profiles_path(simulation_id)
        twitter_profiles_path = simulation_twitter_profiles_path(simulation_id)
        assert reddit_profiles_path.exists()
        assert twitter_profiles_path.exists()
        reddit_profiles = json.loads(reddit_profiles_path.read_text(encoding="utf-8"))
        assert len(reddit_profiles) == 2
        assert "username" in reddit_profiles[0]

        print(
            "task8_api_validation_ok",
            {"project_id": project_id, "simulation_id": simulation_id},
        )
    finally:
        await _cleanup(project_id, simulation_id)


if __name__ == "__main__":
    asyncio.run(main())

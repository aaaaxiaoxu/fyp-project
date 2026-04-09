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

from src.db import SessionLocal, init_db
from src.jwt_utils import create_access_token
from src.main import app
from src.models import Project, Task, User
from src.routers.graph import GraphBuildResult
from src.settings import settings
from src.utils.path_resolver import as_upload_relative_path, project_dir, project_extracted_text_path, project_ontology_path


def _set_runtime_defaults() -> None:
    if not settings.LLM_API_KEY.strip():
        settings.LLM_API_KEY = "task6-test-llm-key"
    if not settings.ZEP_API_KEY.strip():
        settings.ZEP_API_KEY = "task6-test-zep-key"


def _fake_build_graph_sync(
    task_id: str,
    user_id: str,
    text: str,
    ontology: dict[str, object],
    graph_name: str,
    chunk_size: int,
    chunk_overlap: int,
    batch_size: int,
) -> GraphBuildResult:
    time.sleep(0.2)
    assert text
    assert ontology["entity_types"]
    assert graph_name
    assert chunk_size > chunk_overlap
    assert batch_size >= 1
    return GraphBuildResult(
        graph_id="graph_task6_fake",
        node_count=3,
        edge_count=2,
        entity_types=["Organization", "Person", "Student"],
        chunk_count=4,
    )


def _fake_graph_data_sync(graph_id: str) -> dict[str, object]:
    return {
        "graph_id": graph_id,
        "nodes": [
            {
                "uuid": "node_a",
                "name": "Alice",
                "labels": ["Entity", "Student"],
                "summary": "student node",
                "attributes": {"role": "student"},
                "created_at": None,
            },
            {
                "uuid": "node_b",
                "name": "Daily News",
                "labels": ["Entity", "Organization"],
                "summary": "media node",
                "attributes": {"kind": "media"},
                "created_at": None,
            },
        ],
        "edges": [
            {
                "uuid": "edge_a",
                "name": "REPORTS_ON",
                "fact": "Daily News reports on Alice",
                "fact_type": "REPORTS_ON",
                "source_node_uuid": "node_b",
                "target_node_uuid": "node_a",
                "source_node_name": "Daily News",
                "target_node_name": "Alice",
                "attributes": {},
                "created_at": None,
                "valid_at": None,
                "invalid_at": None,
                "expired_at": None,
                "episodes": [],
            }
        ],
        "node_count": 2,
        "edge_count": 1,
    }


def _fake_graph_entities_sync(graph_id: str) -> dict[str, object]:
    return {
        "entities": [
            {
                "uuid": "node_a",
                "name": "Alice",
                "labels": ["Entity", "Student"],
                "summary": "student node",
                "attributes": {"role": "student"},
                "related_edges": [],
                "related_nodes": [],
            }
        ],
        "entity_types": ["Student"],
        "total_count": 2,
        "filtered_count": 1,
    }


async def _create_users(owner_id: str, other_id: str, suffix: str) -> None:
    await init_db()
    async with SessionLocal() as session:
        session.add_all(
            [
                User(
                    id=owner_id,
                    email=f"task6-owner-{suffix}@example.com",
                    password_hash="hashed",
                    is_verified=True,
                    nickname="task6-owner",
                ),
                User(
                    id=other_id,
                    email=f"task6-other-{suffix}@example.com",
                    password_hash="hashed",
                    is_verified=True,
                    nickname="task6-other",
                ),
            ]
        )
        await session.commit()


async def _create_project_with_artifacts(user_id: str, suffix: str, ready: bool) -> str:
    await init_db()
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    ontology_path = project_ontology_path(project_id)
    extracted_text_path = project_extracted_text_path(project_id)
    if ready:
        project_dir(project_id).mkdir(parents=True, exist_ok=True)
        ontology_path.write_text(
            json.dumps(
                {
                    "entity_types": [
                        {"name": "Student", "description": "student", "attributes": []},
                        {"name": "Person", "description": "fallback person", "attributes": []},
                        {"name": "Organization", "description": "fallback org", "attributes": []},
                    ],
                    "edge_types": [
                        {
                            "name": "REPORTS_ON",
                            "description": "reports on",
                            "source_targets": [{"source": "Organization", "target": "Student"}],
                            "attributes": [],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        extracted_text_path.write_text(
            "Alice is a student leader. Daily News reports on Alice and the university.",
            encoding="utf-8",
        )

    async with SessionLocal() as session:
        session.add(
            Project(
                id=project_id,
                user_id=user_id,
                name=f"Task 6 Project {suffix}",
                simulation_requirement=f"simulate task6 {suffix}",
                status="ontology_generated" if ready else "created",
                ontology_path=as_upload_relative_path(ontology_path) if ready else None,
                extracted_text_path=as_upload_relative_path(extracted_text_path) if ready else None,
            )
        )
        await session.commit()
    return project_id


async def _poll_task(client: AsyncClient, *, task_id: str, headers: dict[str, str], timeout_s: float = 10.0) -> tuple[dict[str, object], list[int]]:
    deadline = time.monotonic() + timeout_s
    seen_progress: list[int] = []
    while time.monotonic() < deadline:
        response = await client.get(f"/api/graph/task/{task_id}", headers=headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        seen_progress.append(int(payload["progress"]))
        if payload["status"] in {"completed", "failed"}:
            return payload, seen_progress
        await asyncio.sleep(0.05)
    raise TimeoutError(f"task polling timed out for {task_id}")


async def _fetch_project(project_id: str) -> Project | None:
    async with SessionLocal() as session:
        return await session.scalar(select(Project).where(Project.id == project_id))


async def _cleanup(user_ids: tuple[str, str], project_ids: tuple[str, str]) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(Task).where(Task.project_id.in_(project_ids)))
        await session.execute(delete(Project).where(Project.id.in_(project_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()

    for project_id in project_ids:
        shutil.rmtree(project_dir(project_id), ignore_errors=True)


async def main() -> None:
    _set_runtime_defaults()

    suffix = uuid.uuid4().hex[:12]
    owner_id = uuid.uuid4().hex
    other_id = uuid.uuid4().hex
    owner_headers = {"Authorization": f"Bearer {create_access_token(owner_id)}"}
    other_headers = {"Authorization": f"Bearer {create_access_token(other_id)}"}

    await _create_users(owner_id, other_id, suffix)
    ready_project_id = await _create_project_with_artifacts(owner_id, suffix, ready=True)
    missing_project_id = await _create_project_with_artifacts(owner_id, suffix, ready=False)

    try:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                with patch(
                    "src.routers.graph._build_graph_sync",
                    new=_fake_build_graph_sync,
                ), patch(
                    "src.routers.graph._get_graph_data_sync",
                    new=_fake_graph_data_sync,
                ), patch(
                    "src.routers.graph._get_graph_entities_sync",
                    new=_fake_graph_entities_sync,
                ):
                    invalid_response = await client.post(
                        "/api/graph/build",
                        headers=owner_headers,
                        json={"project_id": missing_project_id},
                    )
                    assert invalid_response.status_code == 400, invalid_response.text

                    build_response = await client.post(
                        "/api/graph/build",
                        headers=owner_headers,
                        json={
                            "project_id": ready_project_id,
                            "graph_name": "Task 6 Validation Graph",
                            "chunk_size": 400,
                            "chunk_overlap": 40,
                            "batch_size": 2,
                        },
                    )
                    assert build_response.status_code == 202, build_response.text
                    task_id = build_response.json()["task_id"]

                    task_payload, seen_progress = await _poll_task(
                        client,
                        task_id=task_id,
                        headers=owner_headers,
                    )
                    assert task_payload["status"] == "completed"
                    assert task_payload["result_json"]["graph_id"] == "graph_task6_fake"
                    assert any(value > 0 for value in seen_progress)
                    assert any(0 < value < 100 for value in seen_progress)

                    project = await _fetch_project(ready_project_id)
                    assert project is not None
                    assert project.status == "graph_completed"
                    assert project.zep_graph_id == "graph_task6_fake"

                    data_response = await client.get("/api/graph/data/graph_task6_fake", headers=owner_headers)
                    assert data_response.status_code == 200, data_response.text
                    data_payload = data_response.json()
                    assert data_payload["node_count"] == 2
                    assert data_payload["edge_count"] == 1

                    entities_response = await client.get("/api/graph/entities/graph_task6_fake", headers=owner_headers)
                    assert entities_response.status_code == 200, entities_response.text
                    entities_payload = entities_response.json()
                    assert entities_payload["filtered_count"] == 1
                    assert entities_payload["entity_types"] == ["Student"]

                    other_data_response = await client.get("/api/graph/data/graph_task6_fake", headers=other_headers)
                    other_entities_response = await client.get("/api/graph/entities/graph_task6_fake", headers=other_headers)
                    assert other_data_response.status_code == 404, other_data_response.text
                    assert other_entities_response.status_code == 404, other_entities_response.text

        print("task6_api_validation_ok")
    finally:
        await _cleanup((owner_id, other_id), (ready_project_id, missing_project_id))


if __name__ == "__main__":
    asyncio.run(main())

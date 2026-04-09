from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db import SessionLocal, engine, init_db
from src.jwt_utils import create_access_token
from src.main import app
from src.models import Project, User
from src.settings import settings


def _set_runtime_defaults() -> None:
    if not settings.LLM_API_KEY.strip():
        settings.LLM_API_KEY = "task4-test-llm-key"
    if not settings.ZEP_API_KEY.strip():
        settings.ZEP_API_KEY = "task4-test-zep-key"


async def _create_users(user_one_id: str, user_two_id: str, suffix: str) -> None:
    await init_db()
    async with SessionLocal() as session:
        session.add_all(
            [
                User(
                    id=user_one_id,
                    email=f"task4-owner-{suffix}@example.com",
                    password_hash="hashed",
                    is_verified=True,
                    nickname="task4-owner",
                ),
                User(
                    id=user_two_id,
                    email=f"task4-other-{suffix}@example.com",
                    password_hash="hashed",
                    is_verified=True,
                    nickname="task4-other",
                ),
            ]
        )
        await session.commit()


async def _project_exists(project_id: str, user_id: str) -> bool:
    async with SessionLocal() as session:
        project = await session.scalar(
            select(Project).where(Project.id == project_id, Project.user_id == user_id)
        )
        return project is not None


async def _cleanup(user_ids: tuple[str, str]) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(Project).where(Project.user_id.in_(user_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


async def main() -> None:
    _set_runtime_defaults()

    suffix = uuid.uuid4().hex[:12]
    owner_id = uuid.uuid4().hex
    other_id = uuid.uuid4().hex
    owner_token = create_access_token(owner_id)
    other_token = create_access_token(other_id)
    project_id: str | None = None

    await _create_users(owner_id, other_id, suffix)

    try:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                owner_headers = {"Authorization": f"Bearer {owner_token}"}
                other_headers = {"Authorization": f"Bearer {other_token}"}

                create_response = await client.post(
                    "/api/graph/project",
                    headers=owner_headers,
                    json={
                        "name": "Task 4 Real Project",
                        "simulation_requirement": "validate project metadata endpoints",
                    },
                )
                assert create_response.status_code == 201, create_response.text
                created_project = create_response.json()
                project_id = created_project["id"]
                assert project_id.startswith("proj_")
                assert created_project["status"] == "created"
                assert created_project["simulation_requirement"] == "validate project metadata endpoints"

                owned_get_response = await client.get(
                    f"/api/graph/project/{project_id}",
                    headers=owner_headers,
                )
                assert owned_get_response.status_code == 200, owned_get_response.text
                assert owned_get_response.json()["id"] == project_id

                list_response = await client.get("/api/graph/projects", headers=owner_headers)
                assert list_response.status_code == 200, list_response.text
                listed_ids = [item["id"] for item in list_response.json()["projects"]]
                assert project_id in listed_ids

                other_get_response = await client.get(
                    f"/api/graph/project/{project_id}",
                    headers=other_headers,
                )
                assert other_get_response.status_code == 404, other_get_response.text

                other_delete_response = await client.delete(
                    f"/api/graph/project/{project_id}",
                    headers=other_headers,
                )
                assert other_delete_response.status_code == 404, other_delete_response.text

                delete_response = await client.delete(
                    f"/api/graph/project/{project_id}",
                    headers=owner_headers,
                )
                assert delete_response.status_code == 200, delete_response.text
                assert delete_response.json() == {"ok": True, "project_id": project_id}

                after_delete_response = await client.get(
                    f"/api/graph/project/{project_id}",
                    headers=owner_headers,
                )
                assert after_delete_response.status_code == 404, after_delete_response.text

        if project_id is not None:
            assert not await _project_exists(project_id, owner_id)
    finally:
        await _cleanup((owner_id, other_id))
        await engine.dispose()

    print("task4_api_validation_ok", {"project_id": project_id, "owner_id": owner_id})


if __name__ == "__main__":
    asyncio.run(main())

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import fitz
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db import SessionLocal, engine, init_db
from src.jwt_utils import create_access_token
from src.main import app
from src.models import Project, ProjectFile, Task, User
from src.settings import settings
from src.utils.path_resolver import project_dir, project_extracted_text_path, project_ontology_path


def _set_runtime_defaults() -> None:
    if not settings.LLM_API_KEY.strip():
        settings.LLM_API_KEY = "task5-test-llm-key"
    if not settings.ZEP_API_KEY.strip():
        settings.ZEP_API_KEY = "task5-test-zep-key"


def _build_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Task 5 PDF content for ontology generation.")
    data = doc.tobytes()
    doc.close()
    return data


def _fake_ontology_generate(
    self,
    document_texts: list[str],
    simulation_requirement: str,
    additional_context: str | None = None,
) -> dict[str, object]:
    time.sleep(0.25)
    return {
        "entity_types": [
            {"name": "Student", "description": "学生", "attributes": [], "examples": ["Alice"]},
            {"name": "Professor", "description": "教授", "attributes": [], "examples": ["Bob"]},
            {"name": "Journalist", "description": "记者", "attributes": [], "examples": ["Carol"]},
            {"name": "MediaOutlet", "description": "媒体", "attributes": [], "examples": ["Daily News"]},
            {"name": "University", "description": "高校", "attributes": [], "examples": ["FYP University"]},
            {"name": "GovernmentAgency", "description": "政府机构", "attributes": [], "examples": ["Education Bureau"]},
            {"name": "Company", "description": "公司", "attributes": [], "examples": ["Acme"]},
            {"name": "NGO", "description": "组织", "attributes": [], "examples": ["Open Data Org"]},
            {"name": "Person", "description": "个人兜底", "attributes": [], "examples": ["Fallback Person"]},
            {"name": "Organization", "description": "组织兜底", "attributes": [], "examples": ["Fallback Org"]},
        ],
        "edge_types": [
            {
                "name": "reports_on",
                "description": "报道",
                "source_targets": [{"source": "Journalist", "target": "University"}],
                "attributes": [],
            }
        ],
        "analysis_summary": f"{simulation_requirement} / docs={len(document_texts)} / ctx={additional_context or ''}",
    }


def _fake_ontology_generate_failure(
    self,
    document_texts: list[str],
    simulation_requirement: str,
    additional_context: str | None = None,
) -> dict[str, object]:
    time.sleep(0.15)
    raise RuntimeError("synthetic ontology generation failure")


async def _create_users(owner_id: str, other_id: str, suffix: str) -> None:
    await init_db()
    async with SessionLocal() as session:
        session.add_all(
            [
                User(
                    id=owner_id,
                    email=f"task5-owner-{suffix}@example.com",
                    password_hash="hashed",
                    is_verified=True,
                    nickname="task5-owner",
                ),
                User(
                    id=other_id,
                    email=f"task5-other-{suffix}@example.com",
                    password_hash="hashed",
                    is_verified=True,
                    nickname="task5-other",
                ),
            ]
        )
        await session.commit()


async def _create_project(user_id: str, suffix: str, name: str) -> str:
    await init_db()
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    async with SessionLocal() as session:
        session.add(
            Project(
                id=project_id,
                user_id=user_id,
                name=name,
                simulation_requirement=f"simulate task5 {suffix}",
                status="created",
            )
        )
        await session.commit()
    return project_id


async def _poll_task(
    client: AsyncClient,
    *,
    task_id: str,
    headers: dict[str, str],
    timeout_s: float = 10.0,
) -> tuple[dict[str, object], list[int]]:
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


async def _fetch_project_files(project_id: str) -> list[ProjectFile]:
    async with SessionLocal() as session:
        return list(await session.scalars(select(ProjectFile).where(ProjectFile.project_id == project_id)))


async def _cleanup(user_ids: tuple[str, str], project_ids: tuple[str | None, str | None]) -> None:
    valid_project_ids = [project_id for project_id in project_ids if project_id]
    async with SessionLocal() as session:
        if valid_project_ids:
            await session.execute(delete(Task).where(Task.project_id.in_(valid_project_ids)))
            await session.execute(delete(ProjectFile).where(ProjectFile.project_id.in_(valid_project_ids)))
            await session.execute(delete(Project).where(Project.id.in_(valid_project_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()

    for project_id in valid_project_ids:
        shutil.rmtree(project_dir(project_id), ignore_errors=True)


async def main() -> None:
    _set_runtime_defaults()

    suffix = uuid.uuid4().hex[:12]
    owner_id = uuid.uuid4().hex
    other_id = uuid.uuid4().hex
    owner_token = create_access_token(owner_id)
    other_token = create_access_token(other_id)
    success_project_id: str | None = None
    failure_project_id: str | None = None

    await _create_users(owner_id, other_id, suffix)
    success_project_id = await _create_project(owner_id, suffix, "Task 5 Success Project")
    failure_project_id = await _create_project(owner_id, suffix, "Task 5 Failure Project")

    txt_bytes = b"Task 5 text content for extraction."
    md_bytes = b"# Task 5 Markdown\n\nThis document contributes ontology context."
    pdf_bytes = _build_pdf_bytes()

    try:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                owner_headers = {"Authorization": f"Bearer {owner_token}"}
                other_headers = {"Authorization": f"Bearer {other_token}"}

                with patch("src.routers.graph.OntologyGenerator.generate", new=_fake_ontology_generate):
                    success_response = await client.post(
                        "/api/graph/ontology/generate",
                        headers=owner_headers,
                        data={"project_id": success_project_id, "additional_context": "task5 success context"},
                        files=[
                            ("files", ("brief.txt", txt_bytes, "text/plain")),
                            ("files", ("notes.md", md_bytes, "text/markdown")),
                            ("files", ("report.pdf", pdf_bytes, "application/pdf")),
                        ],
                    )
                    assert success_response.status_code == 202, success_response.text
                    success_task_id = success_response.json()["task_id"]

                    success_payload, success_progress = await _poll_task(
                        client,
                        task_id=success_task_id,
                        headers=owner_headers,
                    )
                assert success_payload["status"] == "completed"
                assert success_payload["progress"] == 100
                assert any(value > 0 for value in success_progress)
                assert any(0 < value < 100 for value in success_progress)
                assert success_payload["result_json"]["project_id"] == success_project_id

                other_task_response = await client.get(
                    f"/api/graph/task/{success_task_id}",
                    headers=other_headers,
                )
                assert other_task_response.status_code == 404, other_task_response.text

                with patch("src.routers.graph.OntologyGenerator.generate", new=_fake_ontology_generate_failure):
                    failure_response = await client.post(
                        "/api/graph/ontology/generate",
                        headers=owner_headers,
                        data={"project_id": failure_project_id},
                        files=[("files", ("bad.txt", b"failure case text", "text/plain"))],
                    )
                    assert failure_response.status_code == 202, failure_response.text
                    failure_task_id = failure_response.json()["task_id"]

                    failure_payload, _ = await _poll_task(
                        client,
                        task_id=failure_task_id,
                        headers=owner_headers,
                    )
                assert failure_payload["status"] == "failed"
                assert "synthetic ontology generation failure" in (failure_payload["error"] or "")

        success_project = await _fetch_project(success_project_id)
        assert success_project is not None
        assert success_project.status == "ontology_generated"
        assert success_project.ontology_path == f"projects/{success_project_id}/ontology.json"
        assert success_project.extracted_text_path == f"projects/{success_project_id}/extracted_text.txt"

        success_project_files = await _fetch_project_files(success_project_id)
        assert len(success_project_files) == 3

        extracted_text_path = project_extracted_text_path(success_project_id)
        ontology_path = project_ontology_path(success_project_id)
        assert extracted_text_path.exists()
        assert ontology_path.exists()
        extracted_text = extracted_text_path.read_text(encoding="utf-8")
        assert "brief.txt" in extracted_text
        assert "notes.md" in extracted_text
        ontology_payload = json.loads(ontology_path.read_text(encoding="utf-8"))
        assert len(ontology_payload["entity_types"]) == 10
        assert ontology_payload["entity_types"][-2]["name"] == "Person"
        assert ontology_payload["entity_types"][-1]["name"] == "Organization"

        failure_project = await _fetch_project(failure_project_id)
        assert failure_project is not None
        assert failure_project.status == "failed"

    finally:
        await _cleanup((owner_id, other_id), (success_project_id, failure_project_id))
        await engine.dispose()

    print(
        "task5_api_validation_ok",
        {
            "success_project_id": success_project_id,
            "failure_project_id": failure_project_id,
        },
    )


if __name__ == "__main__":
    asyncio.run(main())

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.auth_deps import get_current_user, get_db
from src.models import Project, Task
from src.routers.graph import router as graph_router


def make_project(project_id: str, user_id: str) -> Project:
    now = datetime.now(timezone.utc)
    return Project(
        id=project_id,
        user_id=user_id,
        name="Task 5 Project",
        status="created",
        zep_graph_id=None,
        simulation_requirement="generate ontology",
        ontology_path=None,
        extracted_text_path=None,
        created_at=now,
        updated_at=now,
    )


def make_task(task_id: str, user_id: str, project_id: str) -> Task:
    now = datetime.now(timezone.utc)
    return Task(
        id=task_id,
        project_id=project_id,
        simulation_id=None,
        user_id=user_id,
        task_type="ontology_generate",
        status="processing",
        progress=45,
        message="extracting document text",
        result_json=None,
        progress_detail_json={"step": "extract"},
        error=None,
        created_at=now,
        updated_at=now,
    )


class GraphOntologyApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.user = SimpleNamespace(id="u" * 32)
        self.app = FastAPI()
        self.app.include_router(graph_router, prefix="/api/graph")
        self.app.dependency_overrides[get_current_user] = lambda: self.user

        async def fake_db():
            yield object()

        self.app.dependency_overrides[get_db] = fake_db
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()

    def test_generate_ontology_returns_task_id_and_schedules_worker(self) -> None:
        project = make_project("proj_task5", self.user.id)
        task = make_task("task_task5", self.user.id, project.id)
        get_project_mock = AsyncMock(return_value=project)
        create_task_mock = AsyncMock(return_value=task)

        with patch("src.routers.graph.project_repo.get_project_by_id", new=get_project_mock), patch(
            "src.routers.graph.task_repo.create_task",
            new=create_task_mock,
        ), patch("src.routers.graph._schedule_ontology_generation") as schedule_mock:
            response = self.client.post(
                "/api/graph/ontology/generate",
                data={"project_id": project.id, "additional_context": "context"},
                files=[
                    ("files", ("note.txt", BytesIO(b"hello world"), "text/plain")),
                    ("files", ("outline.md", BytesIO(b"# Title"), "text/markdown")),
                ],
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"task_id": "task_task5"})
        self.assertEqual(get_project_mock.await_args.kwargs["user_id"], self.user.id)
        self.assertEqual(create_task_mock.await_args.kwargs["task_type"], "ontology_generate")
        self.assertEqual(create_task_mock.await_args.kwargs["project_id"], project.id)
        schedule_mock.assert_called_once()

    def test_generate_ontology_rejects_invalid_inputs(self) -> None:
        project = make_project("proj_task5", self.user.id)

        with patch("src.routers.graph.project_repo.get_project_by_id", new=AsyncMock(return_value=project)):
            missing_files_response = self.client.post(
                "/api/graph/ontology/generate",
                data={"project_id": project.id},
            )
            unsupported_file_response = self.client.post(
                "/api/graph/ontology/generate",
                data={"project_id": project.id},
                files=[("files", ("bad.png", BytesIO(b"png"), "image/png"))],
            )

        self.assertEqual(missing_files_response.status_code, 422)
        self.assertEqual(unsupported_file_response.status_code, 400)
        self.assertIn("Unsupported file type", unsupported_file_response.json()["detail"])

    def test_get_graph_task_is_user_scoped(self) -> None:
        task = make_task("task_task5", self.user.id, "proj_task5")

        with patch("src.routers.graph.task_repo.get_task_by_id", new=AsyncMock(return_value=task)) as get_task_mock:
            response = self.client.get("/api/graph/task/task_task5")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["task_id"], "task_task5")
        self.assertEqual(payload["progress"], 45)
        self.assertEqual(get_task_mock.await_args.kwargs["user_id"], self.user.id)

    def test_get_graph_task_returns_404_for_missing_task(self) -> None:
        with patch("src.routers.graph.task_repo.get_task_by_id", new=AsyncMock(return_value=None)):
            response = self.client.get("/api/graph/task/task_missing")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Task not found")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.auth_deps import get_current_user, get_db
from src.models import Project
from src.routers.graph import router as graph_router


def make_project(*, project_id: str, user_id: str, name: str, simulation_requirement: str) -> Project:
    now = datetime.now(timezone.utc)
    return Project(
        id=project_id,
        user_id=user_id,
        name=name,
        status="created",
        zep_graph_id=None,
        simulation_requirement=simulation_requirement,
        ontology_path=None,
        extracted_text_path=None,
        created_at=now,
        updated_at=now,
    )


class GraphRouterTestCase(unittest.TestCase):
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

    def test_create_project_returns_created_project(self) -> None:
        project = make_project(
            project_id="proj_task4",
            user_id=self.user.id,
            name="Task 4 Project",
            simulation_requirement="simulate a discussion",
        )
        create_mock = AsyncMock(return_value=project)

        with patch("src.routers.graph._new_project_id", return_value="proj_task4"), patch(
            "src.routers.graph.project_repo.create_project",
            new=create_mock,
        ):
            response = self.client.post(
                "/api/graph/project",
                json={
                    "name": "  Task 4 Project  ",
                    "simulation_requirement": "  simulate a discussion  ",
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["id"], "proj_task4")
        self.assertEqual(payload["simulation_requirement"], "simulate a discussion")
        self.assertEqual(create_mock.await_args.kwargs["name"], "Task 4 Project")
        self.assertEqual(
            create_mock.await_args.kwargs["simulation_requirement"],
            "simulate a discussion",
        )

    def test_create_project_rejects_blank_values(self) -> None:
        response = self.client.post(
            "/api/graph/project",
            json={"name": "   ", "simulation_requirement": "   "},
        )

        self.assertEqual(response.status_code, 422)

    def test_get_and_list_only_return_current_users_projects(self) -> None:
        project = make_project(
            project_id="proj_task4_owned",
            user_id=self.user.id,
            name="Owned Project",
            simulation_requirement="owned requirement",
        )
        get_mock = AsyncMock(return_value=project)
        list_mock = AsyncMock(return_value=[project])

        with patch("src.routers.graph.project_repo.get_project_by_id", new=get_mock), patch(
            "src.routers.graph.project_repo.list_projects_by_user",
            new=list_mock,
        ):
            get_response = self.client.get("/api/graph/project/proj_task4_owned")
            list_response = self.client.get("/api/graph/projects")

        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["id"], "proj_task4_owned")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["projects"]), 1)
        self.assertEqual(get_mock.await_args.kwargs["user_id"], self.user.id)
        self.assertEqual(list_mock.await_args.args[1], self.user.id)

    def test_missing_or_not_owned_project_returns_404(self) -> None:
        get_mock = AsyncMock(return_value=None)
        delete_mock = AsyncMock(return_value=False)

        with patch("src.routers.graph.project_repo.get_project_by_id", new=get_mock), patch(
            "src.routers.graph.project_repo.delete_project",
            new=delete_mock,
        ):
            get_response = self.client.get("/api/graph/project/proj_missing")
            delete_response = self.client.delete("/api/graph/project/proj_missing")

        self.assertEqual(get_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        self.assertEqual(get_response.json()["detail"], "Project not found")
        self.assertEqual(delete_response.json()["detail"], "Project not found")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.auth_deps import get_current_user, get_db
from src.models import Project, Task
from src.routers.graph import router as graph_router


def make_project(
    *,
    project_id: str,
    user_id: str,
    status: str = "ontology_generated",
    zep_graph_id: str | None = None,
    ontology_path: str | None = "projects/proj_task6/ontology.json",
    extracted_text_path: str | None = "projects/proj_task6/extracted_text.txt",
) -> Project:
    now = datetime.now(timezone.utc)
    return Project(
        id=project_id,
        user_id=user_id,
        name="Task 6 Project",
        status=status,
        zep_graph_id=zep_graph_id,
        simulation_requirement="build graph",
        ontology_path=ontology_path,
        extracted_text_path=extracted_text_path,
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
        task_type="graph_build",
        status="processing",
        progress=66,
        message="processing graph episodes",
        result_json=None,
        progress_detail_json={"stage": "wait_for_episodes"},
        error=None,
        created_at=now,
        updated_at=now,
    )


class GraphBuildApiTestCase(unittest.TestCase):
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

    def test_build_graph_returns_task_id_and_schedules_worker(self) -> None:
        project = make_project(project_id="proj_task6", user_id=self.user.id)
        task = make_task("task_task6", self.user.id, project.id)

        with patch("src.routers.graph.project_repo.get_project_by_id", new=AsyncMock(return_value=project)) as get_mock, patch(
            "src.routers.graph.task_repo.create_task",
            new=AsyncMock(return_value=task),
        ) as create_task_mock, patch("src.routers.graph._schedule_graph_build") as schedule_mock:
            response = self.client.post(
                "/api/graph/build",
                json={
                    "project_id": project.id,
                    "graph_name": "Task 6 Graph",
                    "chunk_size": 600,
                    "chunk_overlap": 60,
                    "batch_size": 4,
                },
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"task_id": "task_task6"})
        self.assertEqual(get_mock.await_args.kwargs["user_id"], self.user.id)
        self.assertEqual(create_task_mock.await_args.kwargs["task_type"], "graph_build")
        schedule_mock.assert_called_once()
        self.assertEqual(schedule_mock.call_args.kwargs["graph_name"], "Task 6 Graph")

    def test_build_graph_rejects_project_without_ontology_artifacts(self) -> None:
        project = make_project(
            project_id="proj_task6_missing",
            user_id=self.user.id,
            status="created",
            ontology_path=None,
            extracted_text_path=None,
        )

        with patch("src.routers.graph.project_repo.get_project_by_id", new=AsyncMock(return_value=project)):
            response = self.client.post("/api/graph/build", json={"project_id": project.id})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Project ontology is not ready")

    def test_build_graph_rejects_invalid_chunk_settings(self) -> None:
        response = self.client.post(
            "/api/graph/build",
            json={"project_id": "proj_task6", "chunk_size": 300, "chunk_overlap": 300},
        )

        self.assertEqual(response.status_code, 422)

    def test_graph_queries_are_user_scoped(self) -> None:
        project = make_project(project_id="proj_task6", user_id=self.user.id, zep_graph_id="graph_owned")

        with patch("src.routers.graph.project_repo.get_project_by_graph_id", new=AsyncMock(return_value=project)) as get_mock, patch(
            "src.routers.graph._get_graph_data_sync",
            return_value={
                "graph_id": "graph_owned",
                "nodes": [
                    {
                        "uuid": "node_1",
                        "name": "Alice",
                        "labels": ["Entity", "Student"],
                        "summary": "node summary",
                        "attributes": {},
                        "created_at": None,
                    }
                ],
                "edges": [
                    {
                        "uuid": "edge_1",
                        "name": "KNOWS",
                        "fact": "Alice knows Bob",
                        "fact_type": "KNOWS",
                        "source_node_uuid": "node_1",
                        "target_node_uuid": "node_2",
                        "source_node_name": "Alice",
                        "target_node_name": "Bob",
                        "attributes": {},
                        "created_at": None,
                        "valid_at": None,
                        "invalid_at": None,
                        "expired_at": None,
                        "episodes": [],
                    }
                ],
                "node_count": 1,
                "edge_count": 1,
            },
        ) as data_mock, patch(
            "src.routers.graph._get_graph_entities_sync",
            return_value={
                "entities": [
                    {
                        "uuid": "node_1",
                        "name": "Alice",
                        "labels": ["Entity", "Student"],
                        "summary": "node summary",
                        "attributes": {},
                        "related_edges": [],
                        "related_nodes": [],
                    }
                ],
                "entity_types": ["Student"],
                "total_count": 2,
                "filtered_count": 1,
            },
        ) as entities_mock:
            data_response = self.client.get("/api/graph/data/graph_owned")
            entities_response = self.client.get("/api/graph/entities/graph_owned")

        self.assertEqual(data_response.status_code, 200)
        self.assertEqual(data_response.json()["graph_id"], "graph_owned")
        self.assertEqual(entities_response.status_code, 200)
        self.assertEqual(entities_response.json()["entity_types"], ["Student"])
        self.assertEqual(get_mock.await_args.kwargs["user_id"], self.user.id)
        data_mock.assert_called_once_with("graph_owned")
        entities_mock.assert_called_once_with("graph_owned")

    def test_graph_queries_return_404_for_other_users(self) -> None:
        with patch("src.routers.graph.project_repo.get_project_by_graph_id", new=AsyncMock(return_value=None)):
            data_response = self.client.get("/api/graph/data/graph_missing")
            entities_response = self.client.get("/api/graph/entities/graph_missing")

        self.assertEqual(data_response.status_code, 404)
        self.assertEqual(entities_response.status_code, 404)
        self.assertEqual(data_response.json()["detail"], "Graph not found")
        self.assertEqual(entities_response.json()["detail"], "Graph not found")


if __name__ == "__main__":
    unittest.main()

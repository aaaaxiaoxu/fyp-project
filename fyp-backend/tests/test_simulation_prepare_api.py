from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.db import get_db
from src.models import Project, Simulation, Task
from src.routers.simulation import router as simulation_router


def make_project(
    *,
    project_id: str,
    zep_graph_id: str | None = "graph_task8",
    extracted_text_path: str | None = "projects/proj_task8/extracted_text.txt",
) -> Project:
    now = datetime.now(timezone.utc)
    return Project(
        id=project_id,
        user_id="0" * 32,
        name="Task 8 Project",
        status="graph_completed",
        zep_graph_id=zep_graph_id,
        simulation_requirement="prepare simulation",
        ontology_path="projects/proj_task8/ontology.json",
        extracted_text_path=extracted_text_path,
        created_at=now,
        updated_at=now,
    )


def make_task(task_id: str, project_id: str) -> Task:
    now = datetime.now(timezone.utc)
    return Task(
        id=task_id,
        project_id=project_id,
        simulation_id=None,
        user_id="0" * 32,
        task_type="simulation_prepare",
        status="processing",
        progress=55,
        message="building profile for Alice",
        result_json=None,
        progress_detail_json={"stage": "generate_profiles"},
        error=None,
        created_at=now,
        updated_at=now,
    )


def make_simulation(simulation_id: str, config_path: str) -> Simulation:
    now = datetime.now(timezone.utc)
    return Simulation(
        id=simulation_id,
        project_id="proj_task8",
        user_id="0" * 32,
        status="ready",
        twitter_enabled=True,
        reddit_enabled=True,
        config_path=config_path,
        profiles_dir="simulations/sim_task8/profiles",
        total_rounds=24,
        current_round=0,
        twitter_actions_count=0,
        reddit_actions_count=0,
        interactive_ready=False,
        error=None,
        started_at=None,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )


class SimulationPrepareApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(simulation_router, prefix="/api/simulation")

        async def fake_db():
            yield object()

        self.app.dependency_overrides[get_db] = fake_db
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()

    def test_prepare_returns_task_id_and_schedules_worker(self) -> None:
        project = make_project(project_id="proj_task8")
        task = make_task("task_task8", project.id)

        with patch("src.routers.simulation.project_repo.get_project_by_id", new=AsyncMock(return_value=project)), patch(
            "src.routers.simulation.task_repo.create_task",
            new=AsyncMock(return_value=task),
        ) as create_task_mock, patch("src.routers.simulation._schedule_prepare_task") as schedule_mock:
            response = self.client.post(
                f"/api/simulation/prepare/{project.id}",
                json={"use_llm_for_profiles": False, "use_llm_for_config": False},
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"task_id": "task_task8"})
        self.assertEqual(create_task_mock.await_args.kwargs["task_type"], "simulation_prepare")
        schedule_mock.assert_called_once()

    def test_prepare_rejects_project_without_graph(self) -> None:
        project = make_project(project_id="proj_task8_missing", zep_graph_id=None)

        with patch("src.routers.simulation.project_repo.get_project_by_id", new=AsyncMock(return_value=project)):
            response = self.client.post("/api/simulation/prepare/proj_task8_missing")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Project graph is not ready.")

    def test_prepare_status_returns_task_payload(self) -> None:
        task = make_task("task_task8", "proj_task8")

        with patch("src.routers.simulation.task_repo.get_task_by_id", new=AsyncMock(return_value=task)):
            response = self.client.get("/api/simulation/prepare/status/task_task8")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["task_id"], "task_task8")
        self.assertEqual(response.json()["progress"], 55)

    def test_get_simulation_config_reads_config_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "simulation_config.json"
            config_path.write_text(json.dumps({"simulation_id": "sim_task8", "agent_configs": []}), encoding="utf-8")
            simulation = make_simulation("sim_task8", "simulations/sim_task8/simulation_config.json")

            with patch(
                "src.routers.simulation.simulation_repo.get_simulation_by_id",
                new=AsyncMock(return_value=simulation),
            ), patch("src.routers.simulation.resolve_upload_path", return_value=config_path):
                response = self.client.get("/api/simulation/sim_task8/config")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["simulation_id"], "sim_task8")

    def test_get_simulation_profiles_reads_primary_profiles_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            primary_profiles_path = Path(temp_dir) / "profiles.json"
            primary_profiles_path.write_text(
                json.dumps(
                    [
                        {
                            "user_id": 1,
                            "username": "agent_1",
                            "name": "Alice",
                            "persona": "Organizer",
                            "follower_count": 320,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            simulation = make_simulation("sim_task8", "simulations/sim_task8/simulation_config.json")

            with patch(
                "src.routers.simulation.simulation_repo.get_simulation_by_id",
                new=AsyncMock(return_value=simulation),
            ), patch("src.routers.simulation.simulation_profiles_path", return_value=primary_profiles_path), patch(
                "src.routers.simulation.simulation_reddit_profiles_path",
                return_value=Path(temp_dir) / "reddit_profiles.json",
            ):
                response = self.client.get("/api/simulation/sim_task8/profiles")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["simulation_id"], "sim_task8")
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["profiles"][0]["username"], "agent_1")
        self.assertEqual(response.json()["profiles"][0]["follower_count"], 320)

    def test_get_simulation_profiles_falls_back_when_primary_file_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            primary_profiles_path = Path(temp_dir) / "profiles.json"
            primary_profiles_path.write_text("{bad json", encoding="utf-8")

            fallback_profiles_path = Path(temp_dir) / "reddit_profiles.json"
            fallback_profiles_path.write_text(
                json.dumps(
                    [
                        {
                            "user_id": 2,
                            "username": "agent_2",
                            "name": "Bob",
                            "persona": "Reporter",
                            "karma": 900,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            simulation = make_simulation("sim_task8", "simulations/sim_task8/simulation_config.json")

            with patch(
                "src.routers.simulation.simulation_repo.get_simulation_by_id",
                new=AsyncMock(return_value=simulation),
            ), patch("src.routers.simulation.simulation_profiles_path", return_value=primary_profiles_path), patch(
                "src.routers.simulation.simulation_reddit_profiles_path",
                return_value=fallback_profiles_path,
            ):
                response = self.client.get("/api/simulation/sim_task8/profiles")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["simulation_id"], "sim_task8")
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["profiles"][0]["username"], "agent_2")
        self.assertEqual(response.json()["profiles"][0]["karma"], 900)


if __name__ == "__main__":
    unittest.main()

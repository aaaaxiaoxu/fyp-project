from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.db import get_db
from src.routers.simulation import router as simulation_router
from src.services import SimulationStartError, SimulationStartResult


class SimulationStartApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(simulation_router, prefix="/api/simulation")

        async def fake_db():
            yield object()

        self.app.dependency_overrides[get_db] = fake_db
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()

    def test_start_returns_running_payload(self) -> None:
        with patch(
            "src.routers.simulation.simulation_manager.start_simulation",
            new=AsyncMock(
                return_value=SimulationStartResult(
                    simulation_id="sim_task10",
                    status="running",
                    pid=4321,
                )
            ),
        ):
            response = self.client.post("/api/simulation/start/sim_task10")

        self.assertEqual(response.status_code, 202)
        self.assertEqual(
            response.json(),
            {
                "simulation_id": "sim_task10",
                "status": "running",
                "pid": 4321,
            },
        )

    def test_start_maps_start_error_to_http_error(self) -> None:
        with patch(
            "src.routers.simulation.simulation_manager.start_simulation",
            new=AsyncMock(
                side_effect=SimulationStartError(
                    "Simulation is not ready to start.",
                    status_code=400,
                )
            ),
        ):
            response = self.client.post("/api/simulation/start/sim_task10")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Simulation is not ready to start.")


if __name__ == "__main__":
    unittest.main()

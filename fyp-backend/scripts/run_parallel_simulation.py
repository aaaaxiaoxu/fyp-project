from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.simulation_manager import SimulationManager


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: run_parallel_simulation.py <simulation_id>")
    SimulationManager().run_parallel_simulation(sys.argv[1])


if __name__ == "__main__":
    main()

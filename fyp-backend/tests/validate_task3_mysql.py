from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

from sqlalchemy import delete

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.task_state_writer import TaskStateWriter
from src.db import SessionLocal, init_db
from src.models import ExplorerSession, Project, ProjectFile, Simulation, Task, User
from src.repositories import explorer_session_repo, project_file_repo, project_repo, simulation_repo, task_repo
from src.utils import path_resolver


async def main() -> None:
    await init_db()

    suffix = uuid.uuid4().hex[:12]
    user_id = uuid.uuid4().hex
    project_id = f"proj_{suffix}"
    project_file_id = f"file_{suffix}"
    simulation_id = f"sim_{suffix}"
    explorer_session_id = f"explorer_{suffix}"
    task_id = f"task_{suffix}"

    async with SessionLocal() as session:
        session.add(
            User(
                id=user_id,
                email=f"task3-{suffix}@example.com",
                password_hash="hashed",
                is_verified=True,
                nickname="task3",
            )
        )
        await session.commit()

        project = await project_repo.create_project(
            session,
            id=project_id,
            user_id=user_id,
            name="Task 3 Project",
            simulation_requirement="validate repository and task state flow",
            ontology_path=path_resolver.project_ontology_path(project_id),
            extracted_text_path=path_resolver.project_extracted_text_path(project_id),
        )
        assert project.ontology_path == f"projects/{project_id}/ontology.json"
        assert project.extracted_text_path == f"projects/{project_id}/extracted_text.txt"

        listed_projects = await project_repo.list_projects_by_user(session, user_id)
        assert any(item.id == project_id for item in listed_projects)

        updated_project = await project_repo.update_project(
            session,
            project_id,
            user_id=user_id,
            status="ontology_generated",
            zep_graph_id="graph_task3",
        )
        assert updated_project is not None
        assert updated_project.status == "ontology_generated"
        assert updated_project.zep_graph_id == "graph_task3"

        project_file = await project_file_repo.create_project_file(
            session,
            id=project_file_id,
            project_id=project_id,
            original_name="source.txt",
            stored_path=path_resolver.project_original_file_path(project_id, "source.txt"),
            file_type="txt",
            size_bytes=256,
        )
        assert project_file.stored_path == f"projects/{project_id}/original/source.txt"

        stored_project_file = await project_file_repo.get_project_file_by_id(session, project_file_id, user_id=user_id)
        assert stored_project_file is not None
        listed_files = await project_file_repo.list_project_files(session, project_id, user_id=user_id)
        assert len(listed_files) == 1

        simulation = await simulation_repo.create_simulation(
            session,
            id=simulation_id,
            project_id=project_id,
            user_id=user_id,
            twitter_enabled=True,
            reddit_enabled=True,
            profiles_dir=path_resolver.simulation_profiles_dir(simulation_id),
            config_path=path_resolver.simulation_config_path(simulation_id),
        )
        assert simulation.config_path == f"simulations/{simulation_id}/simulation_config.json"
        assert simulation.profiles_dir == f"simulations/{simulation_id}/profiles"

        updated_simulation = await simulation_repo.update_simulation(
            session,
            simulation_id,
            user_id=user_id,
            status="preparing",
            total_rounds=12,
            current_round=3,
        )
        assert updated_simulation is not None
        assert updated_simulation.status == "preparing"
        assert updated_simulation.total_rounds == 12
        assert updated_simulation.current_round == 3

        explorer_session = await explorer_session_repo.create_explorer_session(
            session,
            id=explorer_session_id,
            simulation_id=simulation_id,
            user_id=user_id,
            title="Task 3 Session",
            log_path=path_resolver.explorer_session_log_path(simulation_id, explorer_session_id),
        )
        assert explorer_session.log_path == f"explorer/{simulation_id}/sessions/{explorer_session_id}.jsonl"

        updated_session = await explorer_session_repo.update_explorer_session(
            session,
            explorer_session_id,
            user_id=user_id,
            status="closed",
            title="Task 3 Session Closed",
        )
        assert updated_session is not None
        assert updated_session.status == "closed"

        task = await task_repo.create_task(
            session,
            id=task_id,
            user_id=user_id,
            project_id=project_id,
            simulation_id=simulation_id,
            task_type="ontology_generate",
            message="queued",
        )
        assert task.status == "pending"

    writer = TaskStateWriter()
    processing_state = await asyncio.to_thread(
        writer.set_processing,
        task_id,
        user_id=user_id,
        progress=45,
        message="extracting text",
        progress_detail_json={"step": "parse"},
    )
    assert processing_state is not None
    assert processing_state.status == "processing"
    assert processing_state.progress == 45
    assert processing_state.message == "extracting text"

    completed_state = await asyncio.to_thread(
        writer.set_completed,
        task_id,
        user_id=user_id,
        message="ontology generated",
        result_json={"project_id": project_id, "ontology_path": path_resolver.project_relative_path(project_id, "ontology.json")},
        progress_detail_json={"step": "done"},
    )
    assert completed_state is not None
    assert completed_state.status == "completed"
    assert completed_state.progress == 100
    assert completed_state.result_json == {
        "project_id": project_id,
        "ontology_path": f"projects/{project_id}/ontology.json",
    }

    async with SessionLocal() as session:
        stored_task = await task_repo.get_task_by_id(session, task_id, user_id=user_id)
        assert stored_task is not None
        assert stored_task.progress == 100
        assert stored_task.message == "ontology generated"
        assert stored_task.result_json == {
            "project_id": project_id,
            "ontology_path": f"projects/{project_id}/ontology.json",
        }

        all_tasks = await task_repo.list_tasks_by_user(session, user_id, project_id=project_id)
        assert len(all_tasks) == 1

        deleted_file = await project_file_repo.delete_project_file(session, project_file_id, user_id=user_id)
        assert deleted_file is True

        deleted_explorer_session = await explorer_session_repo.delete_explorer_session(
            session,
            explorer_session_id,
            user_id=user_id,
        )
        assert deleted_explorer_session is True

        deleted_task = await task_repo.delete_task(session, task_id, user_id=user_id)
        assert deleted_task is True

        deleted_simulation = await simulation_repo.delete_simulation(session, simulation_id, user_id=user_id)
        assert deleted_simulation is True

        deleted_project = await project_repo.delete_project(session, project_id, user_id=user_id)
        assert deleted_project is True

        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()

    async with SessionLocal() as session:
        assert await session.get(Project, project_id) is None
        assert await session.get(ProjectFile, project_file_id) is None
        assert await session.get(Simulation, simulation_id) is None
        assert await session.get(ExplorerSession, explorer_session_id) is None
        assert await session.get(Task, task_id) is None
        assert await session.get(User, user_id) is None

    print("task3_validation_ok", {"project_id": project_id, "simulation_id": simulation_id, "task_id": task_id})


if __name__ == "__main__":
    asyncio.run(main())

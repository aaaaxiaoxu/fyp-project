from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

from sqlalchemy import delete, inspect, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db import SessionLocal, engine, init_db
from src.models import Project, ProjectFile, Simulation, Task, User


async def main() -> None:
    await init_db()

    async with engine.begin() as conn:
        table_names = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())

    expected = {"projects", "project_files", "simulations", "tasks", "explorer_sessions"}
    missing = expected.difference(table_names)
    if missing:
        raise RuntimeError(f"missing tables: {sorted(missing)}")

    suffix = uuid.uuid4().hex[:12]
    user_id = uuid.uuid4().hex
    project_id = f"proj_{suffix}"
    simulation_id = f"sim_{suffix}"
    task_id = f"task_{suffix}"
    server_default_task_id = f"task_default_{suffix}"
    file_id = f"file_{suffix}"

    async with SessionLocal() as session:
        user = User(
            id=user_id,
            email=f"task2-{suffix}@example.com",
            password_hash="hashed",
            is_verified=True,
            nickname="task2",
        )
        project = Project(
            id=project_id,
            user_id=user_id,
            name="Task 2 MySQL Validation",
            simulation_requirement="validate task 2 schema",
        )
        project_file = ProjectFile(
            id=file_id,
            project_id=project_id,
            original_name="doc.txt",
            stored_path=f"projects/{project_id}/original/doc.txt",
            file_type="txt",
            size_bytes=64,
        )
        simulation = Simulation(
            id=simulation_id,
            project_id=project_id,
            user_id=user_id,
            twitter_enabled=True,
            reddit_enabled=True,
        )
        task = Task(
            id=task_id,
            project_id=project_id,
            simulation_id=simulation_id,
            user_id=user_id,
            task_type="sim_prepare",
        )

        session.add_all([user, project, project_file, simulation, task])
        await session.commit()

        await session.execute(
            Task.__table__.insert().values(
                id=server_default_task_id,
                user_id=user_id,
                task_type="ontology_generate",
                status="pending",
                progress=0,
            )
        )
        await session.commit()

        stored_project = await session.scalar(select(Project).where(Project.id == project_id))
        stored_simulation = await session.scalar(select(Simulation).where(Simulation.id == simulation_id))
        stored_task = await session.scalar(select(Task).where(Task.id == task_id))
        stored_server_default_task = await session.scalar(select(Task).where(Task.id == server_default_task_id))

        assert stored_project is not None
        assert stored_simulation is not None
        assert stored_task is not None
        assert stored_server_default_task is not None
        assert stored_project.user_id == user_id
        assert stored_simulation.user_id == user_id
        assert stored_task.user_id == user_id
        assert stored_simulation.interactive_ready is False
        assert stored_server_default_task.message == ""

        await session.delete(simulation)
        await session.commit()

    async with SessionLocal() as session:
        task_after_simulation_delete = await session.scalar(select(Task).where(Task.id == task_id))
        assert task_after_simulation_delete is not None
        assert task_after_simulation_delete.project_id == project_id
        assert task_after_simulation_delete.simulation_id is None

    async with SessionLocal() as session:
        project = await session.scalar(select(Project).where(Project.id == project_id))
        assert project is not None
        await session.delete(project)
        await session.commit()

    async with SessionLocal() as session:
        task_after_project_delete = await session.scalar(select(Task).where(Task.id == task_id))
        assert task_after_project_delete is not None
        assert task_after_project_delete.project_id is None
        assert task_after_project_delete.simulation_id is None

    async with SessionLocal() as session:
        await session.execute(delete(Task).where(Task.id.in_([task_id, server_default_task_id])))
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()

    print("mysql_validation_ok", sorted(expected))


if __name__ == "__main__":
    asyncio.run(main())

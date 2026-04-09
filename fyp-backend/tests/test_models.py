from __future__ import annotations

import unittest

from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db import Base
from src.models import ExplorerSession, Project, ProjectFile, Simulation, Task, User


class ModelsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        event.listen(self.engine, "connect", self._enable_foreign_keys)
        Base.metadata.create_all(self.engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    @staticmethod
    def _enable_foreign_keys(dbapi_connection, _) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    def test_expected_tables_are_created(self) -> None:
        inspector = inspect(self.engine)
        table_names = set(inspector.get_table_names())

        for table_name in {
            "projects",
            "project_files",
            "simulations",
            "tasks",
            "explorer_sessions",
        }:
            self.assertIn(table_name, table_names)

    def test_can_insert_and_query_core_records(self) -> None:
        with Session(self.engine) as session:
            user = User(
                id="u" * 32,
                email="task2@example.com",
                password_hash="hashed",
                is_verified=True,
                nickname="task2",
            )
            project = Project(
                id="proj_task2",
                user_id=user.id,
                name="Task 2 Project",
                simulation_requirement="simulate a social discussion",
            )
            project_file = ProjectFile(
                id="file_task2",
                project_id=project.id,
                original_name="source.txt",
                stored_path="projects/proj_task2/original/source.txt",
                file_type="txt",
                size_bytes=128,
            )
            simulation = Simulation(
                id="sim_task2",
                project_id=project.id,
                user_id=user.id,
                twitter_enabled=True,
                reddit_enabled=False,
            )
            task = Task(
                id="task_task2",
                project_id=project.id,
                simulation_id=simulation.id,
                user_id=user.id,
                task_type="sim_prepare",
            )
            explorer_session = ExplorerSession(
                id="explorer_task2",
                simulation_id=simulation.id,
                user_id=user.id,
                title="First session",
            )

            session.add_all([user, project, project_file, simulation, task, explorer_session])
            session.commit()

            stored_project = session.scalar(select(Project).where(Project.id == project.id))
            stored_simulation = session.scalar(select(Simulation).where(Simulation.id == simulation.id))
            stored_task = session.scalar(select(Task).where(Task.id == task.id))

            self.assertIsNotNone(stored_project)
            self.assertIsNotNone(stored_simulation)
            self.assertIsNotNone(stored_task)
            self.assertEqual(stored_project.user_id, user.id)
            self.assertEqual(stored_simulation.user_id, user.id)
            self.assertEqual(stored_task.user_id, user.id)
            self.assertFalse(stored_simulation.interactive_ready)

    def test_invalid_task_progress_is_rejected(self) -> None:
        with Session(self.engine) as session:
            user = User(
                id="v" * 32,
                email="constraint@example.com",
                password_hash="hashed",
                is_verified=True,
                nickname="constraint",
            )
            session.add(user)
            session.commit()

            invalid_task = Task(
                id="task_invalid_progress",
                user_id=user.id,
                task_type="ontology_generate",
                progress=101,
            )
            session.add(invalid_task)

            with self.assertRaises(IntegrityError):
                session.commit()

    def test_deleting_simulation_sets_task_simulation_id_to_null(self) -> None:
        with Session(self.engine) as session:
            user = User(
                id="s" * 32,
                email="simulation-delete@example.com",
                password_hash="hashed",
                is_verified=True,
                nickname="simulation-delete",
            )
            project = Project(
                id="proj_sim_delete",
                user_id=user.id,
                name="Simulation delete",
                simulation_requirement="check set null",
            )
            simulation = Simulation(
                id="sim_delete",
                project_id=project.id,
                user_id=user.id,
                twitter_enabled=True,
                reddit_enabled=True,
            )
            task = Task(
                id="task_sim_delete",
                project_id=project.id,
                simulation_id=simulation.id,
                user_id=user.id,
                task_type="sim_prepare",
            )

            session.add_all([user, project, simulation, task])
            session.commit()

            session.delete(simulation)
            session.commit()

            stored_task = session.scalar(select(Task).where(Task.id == task.id))
            self.assertIsNotNone(stored_task)
            self.assertIsNone(stored_task.simulation_id)
            self.assertEqual(stored_task.project_id, project.id)

    def test_deleting_project_sets_task_foreign_keys_to_null(self) -> None:
        with Session(self.engine) as session:
            user = User(
                id="p" * 32,
                email="project-delete@example.com",
                password_hash="hashed",
                is_verified=True,
                nickname="project-delete",
            )
            project = Project(
                id="proj_delete",
                user_id=user.id,
                name="Project delete",
                simulation_requirement="check set null",
            )
            simulation = Simulation(
                id="sim_project_delete",
                project_id=project.id,
                user_id=user.id,
                twitter_enabled=True,
                reddit_enabled=True,
            )
            task = Task(
                id="task_project_delete",
                project_id=project.id,
                simulation_id=simulation.id,
                user_id=user.id,
                task_type="sim_prepare",
            )

            session.add_all([user, project, simulation, task])
            session.commit()

            session.delete(project)
            session.commit()

            stored_task = session.scalar(select(Task).where(Task.id == task.id))
            self.assertIsNotNone(stored_task)
            self.assertIsNone(stored_task.project_id)
            self.assertIsNone(stored_task.simulation_id)

    def test_task_message_uses_server_default_for_core_insert(self) -> None:
        with Session(self.engine) as session:
            user = User(
                id="m" * 32,
                email="message-default@example.com",
                password_hash="hashed",
                is_verified=True,
                nickname="message-default",
            )
            session.add(user)
            session.commit()

            session.execute(
                Task.__table__.insert().values(
                    id="task_message_default",
                    user_id=user.id,
                    task_type="ontology_generate",
                    progress=0,
                    status="pending",
                )
            )
            session.commit()

            stored_task = session.scalar(select(Task).where(Task.id == "task_message_default"))
            self.assertIsNotNone(stored_task)
            self.assertEqual(stored_task.message, "")


if __name__ == "__main__":
    unittest.main()

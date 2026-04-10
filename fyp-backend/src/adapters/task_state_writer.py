from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from ..db import engine as shared_engine
from ..models import Task, TaskStatus
from ..repositories import task_repo

_UNSET = object()


@dataclass(frozen=True, slots=True)
class TaskState:
    id: str
    task_type: str
    status: str
    progress: int
    message: str
    result_json: dict | list | None
    progress_detail_json: dict | list | None
    error: str | None
    project_id: str | None
    simulation_id: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, task: Task) -> "TaskState":
        return cls(
            id=task.id,
            task_type=task.task_type,
            status=task.status,
            progress=task.progress,
            message=task.message,
            result_json=task.result_json,
            progress_detail_json=task.progress_detail_json,
            error=task.error,
            project_id=task.project_id,
            simulation_id=task.simulation_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )


class TaskStateWriter:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        engine_url: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._engine_url = engine_url or shared_engine.url.render_as_string(hide_password=False)
        self._engine_echo = shared_engine.echo

    def create_task(
        self,
        *,
        id: str,
        task_type: str,
        project_id: str | None = None,
        simulation_id: str | None = None,
        status: str = TaskStatus.PENDING.value,
        progress: int = 0,
        message: str = "",
        result_json: dict | list | None = None,
        progress_detail_json: dict | list | None = None,
        error: str | None = None,
    ) -> TaskState:
        task = self._run(
            self._create_task(
                id=id,
                task_type=task_type,
                project_id=project_id,
                simulation_id=simulation_id,
                status=status,
                progress=progress,
                message=message,
                result_json=result_json,
                progress_detail_json=progress_detail_json,
                error=error,
            )
        )
        return TaskState.from_model(task)

    def get_task(self, task_id: str) -> TaskState | None:
        task = self._run(self._get_task(task_id))
        if task is None:
            return None
        return TaskState.from_model(task)

    def update_task(
        self,
        task_id: str,
        *,
        project_id: str | None | object = _UNSET,
        simulation_id: str | None | object = _UNSET,
        task_type: str | object = _UNSET,
        status: str | object = _UNSET,
        progress: int | object = _UNSET,
        message: str | object = _UNSET,
        result_json: dict | list | None | object = _UNSET,
        progress_detail_json: dict | list | None | object = _UNSET,
        error: str | None | object = _UNSET,
    ) -> TaskState | None:
        update_fields = {
            "project_id": project_id,
            "simulation_id": simulation_id,
            "task_type": task_type,
            "status": status,
            "progress": progress,
            "message": message,
            "result_json": result_json,
            "progress_detail_json": progress_detail_json,
            "error": error,
        }
        task = self._run(
            self._update_task(
                task_id,
                **{key: value for key, value in update_fields.items() if value is not _UNSET},
            )
        )
        if task is None:
            return None
        return TaskState.from_model(task)

    def set_processing(
        self,
        task_id: str,
        *,
        progress: int | None = None,
        message: str | None = None,
        progress_detail_json: dict | list | None | object = _UNSET,
    ) -> TaskState | None:
        kwargs: dict[str, object] = {"status": TaskStatus.PROCESSING.value}
        if progress is not None:
            kwargs["progress"] = progress
        if message is not None:
            kwargs["message"] = message
        if progress_detail_json is not _UNSET:
            kwargs["progress_detail_json"] = progress_detail_json
        return self.update_task(task_id, **kwargs)

    def set_completed(
        self,
        task_id: str,
        *,
        message: str | None = None,
        result_json: dict | list | None | object = _UNSET,
        progress_detail_json: dict | list | None | object = _UNSET,
    ) -> TaskState | None:
        kwargs: dict[str, object] = {
            "status": TaskStatus.COMPLETED.value,
            "progress": 100,
            "error": None,
        }
        if message is not None:
            kwargs["message"] = message
        if result_json is not _UNSET:
            kwargs["result_json"] = result_json
        if progress_detail_json is not _UNSET:
            kwargs["progress_detail_json"] = progress_detail_json
        return self.update_task(task_id, **kwargs)

    def set_failed(
        self,
        task_id: str,
        *,
        error: str,
        message: str | None = None,
        progress: int | None = None,
        result_json: dict | list | None | object = _UNSET,
        progress_detail_json: dict | list | None | object = _UNSET,
    ) -> TaskState | None:
        kwargs: dict[str, object] = {
            "status": TaskStatus.FAILED.value,
            "error": error,
        }
        if message is not None:
            kwargs["message"] = message
        if progress is not None:
            kwargs["progress"] = progress
        if result_json is not _UNSET:
            kwargs["result_json"] = result_json
        if progress_detail_json is not _UNSET:
            kwargs["progress_detail_json"] = progress_detail_json
        return self.update_task(task_id, **kwargs)

    async def _create_task(self, **kwargs) -> Task:
        async with self._session_scope() as session:
            return await task_repo.create_task(session, **kwargs)

    async def _get_task(self, task_id: str) -> Task | None:
        async with self._session_scope() as session:
            return await task_repo.get_task_by_id(session, task_id)

    async def _update_task(self, task_id: str, **kwargs) -> Task | None:
        async with self._session_scope() as session:
            return await task_repo.update_task(session, task_id, **kwargs)

    @asynccontextmanager
    async def _session_scope(self) -> AsyncIterator[AsyncSession]:
        if self._session_factory is not None:
            async with self._session_factory() as session:
                yield session
            return

        runtime_engine = create_async_engine(
            self._engine_url,
            echo=self._engine_echo,
            pool_pre_ping=True,
            poolclass=NullPool,
        )
        runtime_session_factory = async_sessionmaker(bind=runtime_engine, expire_on_commit=False)
        try:
            async with runtime_session_factory() as session:
                yield session
        finally:
            await runtime_engine.dispose()

    def _run(self, operation: object):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(operation)
        if hasattr(operation, "close"):
            operation.close()  # type: ignore[union-attr]
        raise RuntimeError(
            "TaskStateWriter must run in a synchronous worker context. "
            "Use the async task_repo API inside request handlers."
        )

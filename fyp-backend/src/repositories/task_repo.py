from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Task, TaskStatus

_UNSET = object()


async def create_task(
    session: AsyncSession,
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
) -> Task:
    task = Task(
        id=id,
        project_id=project_id,
        simulation_id=simulation_id,
        task_type=task_type,
        status=status,
        progress=progress,
        message=message,
        result_json=result_json,
        progress_detail_json=progress_detail_json,
        error=error,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def get_task_by_id(
    session: AsyncSession,
    task_id: str,
) -> Task | None:
    stmt = select(Task).where(Task.id == task_id)
    return await session.scalar(stmt)


async def list_tasks(
    session: AsyncSession,
    *,
    project_id: str | None = None,
    simulation_id: str | None = None,
    task_type: str | None = None,
    status: str | None = None,
) -> list[Task]:
    stmt = select(Task)
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    if simulation_id is not None:
        stmt = stmt.where(Task.simulation_id == simulation_id)
    if task_type is not None:
        stmt = stmt.where(Task.task_type == task_type)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    stmt = stmt.order_by(Task.created_at.desc())
    return list(await session.scalars(stmt))


async def update_task(
    session: AsyncSession,
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
) -> Task | None:
    task = await get_task_by_id(session, task_id)
    if task is None:
        return None

    if project_id is not _UNSET:
        task.project_id = None if project_id is None else str(project_id)
    if simulation_id is not _UNSET:
        task.simulation_id = None if simulation_id is None else str(simulation_id)
    if task_type is not _UNSET:
        task.task_type = str(task_type)
    if status is not _UNSET:
        task.status = str(status)
    if progress is not _UNSET:
        task.progress = int(progress)
    if message is not _UNSET:
        task.message = str(message)
    if result_json is not _UNSET:
        task.result_json = result_json
    if progress_detail_json is not _UNSET:
        task.progress_detail_json = progress_detail_json
    if error is not _UNSET:
        task.error = None if error is None else str(error)

    await session.commit()
    await session.refresh(task)
    return task


async def delete_task(
    session: AsyncSession,
    task_id: str,
) -> bool:
    task = await get_task_by_id(session, task_id)
    if task is None:
        return False

    await session.delete(task)
    await session.commit()
    return True

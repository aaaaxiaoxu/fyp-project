from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Project, ProjectFile
from ..utils.path_resolver import as_upload_relative_path


async def create_project_file(
    session: AsyncSession,
    *,
    id: str,
    project_id: str,
    original_name: str,
    stored_path: str,
    file_type: str,
    size_bytes: int,
) -> ProjectFile:
    project_file = ProjectFile(
        id=id,
        project_id=project_id,
        original_name=original_name,
        stored_path=as_upload_relative_path(stored_path),
        file_type=file_type,
        size_bytes=size_bytes,
    )
    session.add(project_file)
    await session.commit()
    await session.refresh(project_file)
    return project_file


async def get_project_file_by_id(
    session: AsyncSession,
    file_id: str,
    *,
    user_id: str | None = None,
) -> ProjectFile | None:
    stmt = select(ProjectFile).where(ProjectFile.id == file_id)
    if user_id is not None:
        stmt = stmt.join(Project, Project.id == ProjectFile.project_id).where(Project.user_id == user_id)
    return await session.scalar(stmt)


async def list_project_files(
    session: AsyncSession,
    project_id: str,
    *,
    user_id: str | None = None,
) -> list[ProjectFile]:
    stmt = select(ProjectFile).where(ProjectFile.project_id == project_id)
    if user_id is not None:
        stmt = stmt.join(Project, Project.id == ProjectFile.project_id).where(Project.user_id == user_id)
    stmt = stmt.order_by(ProjectFile.created_at.asc())
    return list(await session.scalars(stmt))


async def delete_project_file(
    session: AsyncSession,
    file_id: str,
    *,
    user_id: str | None = None,
) -> bool:
    project_file = await get_project_file_by_id(session, file_id, user_id=user_id)
    if project_file is None:
        return False

    await session.delete(project_file)
    await session.commit()
    return True

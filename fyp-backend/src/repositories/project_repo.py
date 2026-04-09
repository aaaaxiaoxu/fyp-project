from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import SYSTEM_OWNER_ID
from ..models import Project, ProjectStatus
from ..utils.path_resolver import as_upload_relative_path

_UNSET = object()


async def create_project(
    session: AsyncSession,
    *,
    id: str,
    user_id: str = SYSTEM_OWNER_ID,
    name: str,
    simulation_requirement: str,
    status: str = ProjectStatus.CREATED.value,
    zep_graph_id: str | None = None,
    ontology_path: str | None = None,
    extracted_text_path: str | None = None,
) -> Project:
    project = Project(
        id=id,
        user_id=user_id,
        name=name,
        status=status,
        zep_graph_id=zep_graph_id,
        simulation_requirement=simulation_requirement,
        ontology_path=_normalize_optional_upload_path(ontology_path),
        extracted_text_path=_normalize_optional_upload_path(extracted_text_path),
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def get_project_by_id(
    session: AsyncSession,
    project_id: str,
    *,
    user_id: str | None = None,
) -> Project | None:
    stmt = select(Project).where(Project.id == project_id)
    if user_id is not None:
        stmt = stmt.where(Project.user_id == user_id)
    return await session.scalar(stmt)


async def list_projects_by_user(
    session: AsyncSession,
    user_id: str | None = None,
    *,
    status: str | None = None,
) -> list[Project]:
    stmt = select(Project)
    if user_id is not None:
        stmt = stmt.where(Project.user_id == user_id)
    if status is not None:
        stmt = stmt.where(Project.status == status)
    stmt = stmt.order_by(Project.created_at.desc())
    return list(await session.scalars(stmt))


async def get_project_by_graph_id(
    session: AsyncSession,
    graph_id: str,
    *,
    user_id: str | None = None,
) -> Project | None:
    stmt = select(Project).where(Project.zep_graph_id == graph_id)
    if user_id is not None:
        stmt = stmt.where(Project.user_id == user_id)
    return await session.scalar(stmt)


async def update_project(
    session: AsyncSession,
    project_id: str,
    *,
    user_id: str | None = None,
    name: str | object = _UNSET,
    status: str | object = _UNSET,
    zep_graph_id: str | None | object = _UNSET,
    simulation_requirement: str | object = _UNSET,
    ontology_path: str | None | object = _UNSET,
    extracted_text_path: str | None | object = _UNSET,
) -> Project | None:
    project = await get_project_by_id(session, project_id, user_id=user_id)
    if project is None:
        return None

    if name is not _UNSET:
        project.name = str(name)
    if status is not _UNSET:
        project.status = str(status)
    if zep_graph_id is not _UNSET:
        project.zep_graph_id = None if zep_graph_id is None else str(zep_graph_id)
    if simulation_requirement is not _UNSET:
        project.simulation_requirement = str(simulation_requirement)
    if ontology_path is not _UNSET:
        project.ontology_path = _normalize_optional_upload_path(ontology_path)
    if extracted_text_path is not _UNSET:
        project.extracted_text_path = _normalize_optional_upload_path(extracted_text_path)

    await session.commit()
    await session.refresh(project)
    return project


async def delete_project(
    session: AsyncSession,
    project_id: str,
    *,
    user_id: str | None = None,
) -> bool:
    project = await get_project_by_id(session, project_id, user_id=user_id)
    if project is None:
        return False

    await session.delete(project)
    await session.commit()
    return True


def _normalize_optional_upload_path(path: str | None | object) -> str | None:
    if path in (None, _UNSET):
        return None
    return as_upload_relative_path(str(path))

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import SYSTEM_OWNER_ID
from ..models import ExplorerSession, ExplorerSessionStatus, utcnow
from ..utils.path_resolver import as_upload_relative_path

_UNSET = object()


async def create_explorer_session(
    session: AsyncSession,
    *,
    id: str,
    simulation_id: str,
    user_id: str = SYSTEM_OWNER_ID,
    title: str,
    status: str = ExplorerSessionStatus.ACTIVE.value,
    log_path: str | None = None,
) -> ExplorerSession:
    explorer_session = ExplorerSession(
        id=id,
        simulation_id=simulation_id,
        user_id=user_id,
        title=title,
        status=status,
        log_path=_normalize_optional_upload_path(log_path),
    )
    session.add(explorer_session)
    await session.commit()
    await session.refresh(explorer_session)
    return explorer_session


async def get_explorer_session_by_id(
    session: AsyncSession,
    session_id: str,
    *,
    user_id: str | None = None,
) -> ExplorerSession | None:
    stmt = select(ExplorerSession).where(ExplorerSession.id == session_id)
    if user_id is not None:
        stmt = stmt.where(ExplorerSession.user_id == user_id)
    return await session.scalar(stmt)


async def list_explorer_sessions(
    session: AsyncSession,
    *,
    user_id: str | None = None,
    simulation_id: str | None = None,
    status: str | None = None,
) -> list[ExplorerSession]:
    stmt = select(ExplorerSession)
    if user_id is not None:
        stmt = stmt.where(ExplorerSession.user_id == user_id)
    if simulation_id is not None:
        stmt = stmt.where(ExplorerSession.simulation_id == simulation_id)
    if status is not None:
        stmt = stmt.where(ExplorerSession.status == status)
    stmt = stmt.order_by(ExplorerSession.created_at.desc())
    return list(await session.scalars(stmt))


async def update_explorer_session(
    session: AsyncSession,
    session_id: str,
    *,
    user_id: str | None = None,
    title: str | object = _UNSET,
    status: str | object = _UNSET,
    log_path: str | None | object = _UNSET,
    touch: bool = False,
) -> ExplorerSession | None:
    explorer_session = await get_explorer_session_by_id(session, session_id, user_id=user_id)
    if explorer_session is None:
        return None

    if title is not _UNSET:
        explorer_session.title = str(title)
    if status is not _UNSET:
        explorer_session.status = str(status)
    if log_path is not _UNSET:
        explorer_session.log_path = _normalize_optional_upload_path(log_path)
    if touch:
        explorer_session.updated_at = utcnow()

    await session.commit()
    await session.refresh(explorer_session)
    return explorer_session


async def delete_explorer_session(
    session: AsyncSession,
    session_id: str,
    *,
    user_id: str | None = None,
) -> bool:
    explorer_session = await get_explorer_session_by_id(session, session_id, user_id=user_id)
    if explorer_session is None:
        return False

    await session.delete(explorer_session)
    await session.commit()
    return True


def _normalize_optional_upload_path(path: str | None | object) -> str | None:
    if path in (None, _UNSET):
        return None
    return as_upload_relative_path(str(path))

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import SYSTEM_OWNER_ID
from ..models import Simulation, SimulationStatus
from ..utils.path_resolver import as_upload_relative_path

_UNSET = object()


async def create_simulation(
    session: AsyncSession,
    *,
    id: str,
    project_id: str,
    user_id: str = SYSTEM_OWNER_ID,
    twitter_enabled: bool,
    reddit_enabled: bool,
    status: str = SimulationStatus.CREATED.value,
    interactive_ready: bool = False,
    total_rounds: int | None = None,
    current_round: int = 0,
    twitter_actions_count: int = 0,
    reddit_actions_count: int = 0,
    config_path: str | None = None,
    profiles_dir: str | None = None,
    error: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> Simulation:
    simulation = Simulation(
        id=id,
        project_id=project_id,
        user_id=user_id,
        status=status,
        twitter_enabled=twitter_enabled,
        reddit_enabled=reddit_enabled,
        interactive_ready=interactive_ready,
        total_rounds=total_rounds,
        current_round=current_round,
        twitter_actions_count=twitter_actions_count,
        reddit_actions_count=reddit_actions_count,
        config_path=_normalize_optional_upload_path(config_path),
        profiles_dir=_normalize_optional_upload_path(profiles_dir),
        error=error,
        started_at=started_at,
        completed_at=completed_at,
    )
    session.add(simulation)
    await session.commit()
    await session.refresh(simulation)
    return simulation


async def get_simulation_by_id(
    session: AsyncSession,
    simulation_id: str,
    *,
    user_id: str | None = None,
) -> Simulation | None:
    stmt = select(Simulation).where(Simulation.id == simulation_id)
    if user_id is not None:
        stmt = stmt.where(Simulation.user_id == user_id)
    return await session.scalar(stmt)


async def list_simulations_by_user(
    session: AsyncSession,
    user_id: str | None = None,
    *,
    project_id: str | None = None,
    status: str | None = None,
) -> list[Simulation]:
    stmt = select(Simulation)
    if user_id is not None:
        stmt = stmt.where(Simulation.user_id == user_id)
    if project_id is not None:
        stmt = stmt.where(Simulation.project_id == project_id)
    if status is not None:
        stmt = stmt.where(Simulation.status == status)
    stmt = stmt.order_by(Simulation.created_at.desc())
    return list(await session.scalars(stmt))


async def update_simulation(
    session: AsyncSession,
    simulation_id: str,
    *,
    user_id: str | None = None,
    status: str | object = _UNSET,
    twitter_enabled: bool | object = _UNSET,
    reddit_enabled: bool | object = _UNSET,
    interactive_ready: bool | object = _UNSET,
    total_rounds: int | None | object = _UNSET,
    current_round: int | object = _UNSET,
    twitter_actions_count: int | object = _UNSET,
    reddit_actions_count: int | object = _UNSET,
    config_path: str | None | object = _UNSET,
    profiles_dir: str | None | object = _UNSET,
    error: str | None | object = _UNSET,
    started_at: datetime | None | object = _UNSET,
    completed_at: datetime | None | object = _UNSET,
) -> Simulation | None:
    simulation = await get_simulation_by_id(session, simulation_id, user_id=user_id)
    if simulation is None:
        return None

    if status is not _UNSET:
        simulation.status = str(status)
    if twitter_enabled is not _UNSET:
        simulation.twitter_enabled = bool(twitter_enabled)
    if reddit_enabled is not _UNSET:
        simulation.reddit_enabled = bool(reddit_enabled)
    if interactive_ready is not _UNSET:
        simulation.interactive_ready = bool(interactive_ready)
    if total_rounds is not _UNSET:
        simulation.total_rounds = None if total_rounds is None else int(total_rounds)
    if current_round is not _UNSET:
        simulation.current_round = int(current_round)
    if twitter_actions_count is not _UNSET:
        simulation.twitter_actions_count = int(twitter_actions_count)
    if reddit_actions_count is not _UNSET:
        simulation.reddit_actions_count = int(reddit_actions_count)
    if config_path is not _UNSET:
        simulation.config_path = _normalize_optional_upload_path(config_path)
    if profiles_dir is not _UNSET:
        simulation.profiles_dir = _normalize_optional_upload_path(profiles_dir)
    if error is not _UNSET:
        simulation.error = None if error is None else str(error)
    if started_at is not _UNSET:
        simulation.started_at = started_at
    if completed_at is not _UNSET:
        simulation.completed_at = completed_at

    await session.commit()
    await session.refresh(simulation)
    return simulation


async def delete_simulation(
    session: AsyncSession,
    simulation_id: str,
    *,
    user_id: str | None = None,
) -> bool:
    simulation = await get_simulation_by_id(session, simulation_id, user_id=user_id)
    if simulation is None:
        return False

    await session.delete(simulation)
    await session.commit()
    return True


def _normalize_optional_upload_path(path: str | None | object) -> str | None:
    if path in (None, _UNSET):
        return None
    return as_upload_relative_path(str(path))

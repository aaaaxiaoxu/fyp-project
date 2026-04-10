from __future__ import annotations

import asyncio
import csv
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters import TaskStateWriter
from ..db import SessionLocal, get_db
from ..models import Simulation, SimulationStatus, Task, TaskStatus
from ..repositories import project_repo, simulation_repo, task_repo
from ..services import (
    OasisAgentProfile,
    OasisProfileGenerator,
    SimulationConfigGenerator,
    SimulationManager,
    SimulationParameters,
    SimulationStartError,
    SimulationStartResult,
    SimulationStopError,
    SimulationStopResult,
    ZepEntityReader,
)
from ..utils import get_logger
from ..utils.path_resolver import (
    as_upload_relative_path,
    ensure_directory,
    ensure_parent_directory,
    project_graph_data_path,
    resolve_upload_path,
    simulation_config_path,
    simulation_profiles_dir,
    simulation_profiles_path,
    simulation_reddit_profiles_path,
    simulation_reddit_actions_path,
    simulation_twitter_profiles_path,
    simulation_twitter_actions_path,
)

router = APIRouter(tags=["Simulation"])
logger = get_logger("fyp.simulation")
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()
simulation_manager = SimulationManager()


def _new_task_id() -> str:
    return f"task_{uuid4().hex[:12]}"


def _new_simulation_id() -> str:
    return f"sim_{uuid4().hex[:12]}"


class PrepareSimulationRequest(BaseModel):
    entity_types: list[str] | None = None
    use_llm_for_profiles: bool = True
    use_llm_for_config: bool = True
    twitter_enabled: bool = True
    reddit_enabled: bool = True

    @field_validator("entity_types")
    @classmethod
    def validate_entity_types(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [item.strip() for item in value if item.strip()]
        return normalized or None


class CreatePrepareTaskResponse(BaseModel):
    task_id: str


class SimulationTaskResponse(BaseModel):
    task_id: str
    task_type: str
    project_id: str | None
    simulation_id: str | None
    status: str
    progress: int
    message: str
    result_json: dict | list | None
    progress_detail_json: dict | list | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class SimulationProfilesResponse(BaseModel):
    simulation_id: str
    count: int
    profiles: list[dict[str, Any]]


class StartSimulationResponse(BaseModel):
    simulation_id: str
    status: str
    pid: int


class StopSimulationResponse(BaseModel):
    simulation_id: str
    status: str
    command_id: str


class SimulationStatusResponse(BaseModel):
    simulation_id: str
    project_id: str
    status: str
    total_rounds: int | None
    current_round: int
    twitter_enabled: bool
    reddit_enabled: bool
    twitter_actions_count: int
    reddit_actions_count: int
    recent_actions: list[dict[str, Any]]
    interactive_ready: bool
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SimulationActionsResponse(BaseModel):
    simulation_id: str
    count: int
    actions: list[dict[str, Any]]


@router.post(
    "/prepare/{project_id}",
    response_model=CreatePrepareTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def prepare_simulation(
    project_id: str,
    req: PrepareSimulationRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> CreatePrepareTaskResponse:
    request = req or PrepareSimulationRequest()
    if not request.twitter_enabled and not request.reddit_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one simulation platform must be enabled.",
        )

    project = await project_repo.get_project_by_id(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if not project.zep_graph_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project graph is not ready.",
        )

    task = await task_repo.create_task(
        db,
        id=_new_task_id(),
        project_id=project_id,
        task_type="simulation_prepare",
        status=TaskStatus.PENDING.value,
        progress=0,
        message="queued",
    )
    _schedule_prepare_task(
        task_id=task.id,
        project_id=project_id,
        entity_types=request.entity_types,
        use_llm_for_profiles=request.use_llm_for_profiles,
        use_llm_for_config=request.use_llm_for_config,
        twitter_enabled=request.twitter_enabled,
        reddit_enabled=request.reddit_enabled,
    )
    return CreatePrepareTaskResponse(task_id=task.id)


@router.post(
    "/start/{simulation_id}",
    response_model=StartSimulationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_simulation(
    simulation_id: str,
) -> StartSimulationResponse:
    try:
        result = await simulation_manager.start_simulation(simulation_id)
    except SimulationStartError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _to_start_response(result)


@router.get("/status/{simulation_id}", response_model=SimulationStatusResponse)
async def get_simulation_status(
    simulation_id: str,
    recent_limit: int = Query(20, ge=0, le=200),
    db: AsyncSession = Depends(get_db),
) -> SimulationStatusResponse:
    simulation = await simulation_repo.get_simulation_by_id(db, simulation_id)
    if simulation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    recent_actions = await asyncio.to_thread(
        _read_recent_actions,
        simulation_id,
        recent_limit,
    )
    return _to_status_response(simulation, recent_actions)


@router.get("/actions/{simulation_id}", response_model=SimulationActionsResponse)
async def get_simulation_actions(
    simulation_id: str,
    platform: Literal["twitter", "reddit"] | None = None,
    db: AsyncSession = Depends(get_db),
) -> SimulationActionsResponse:
    simulation = await simulation_repo.get_simulation_by_id(db, simulation_id)
    if simulation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    actions = await asyncio.to_thread(_read_actions, simulation_id, platform)
    return SimulationActionsResponse(
        simulation_id=simulation_id,
        count=len(actions),
        actions=actions,
    )


@router.post(
    "/stop/{simulation_id}",
    response_model=StopSimulationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def stop_simulation(
    simulation_id: str,
) -> StopSimulationResponse:
    try:
        result = await simulation_manager.stop_simulation(simulation_id)
    except SimulationStopError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _to_stop_response(result)


@router.get("/prepare/status/{task_id}", response_model=SimulationTaskResponse)
async def get_prepare_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> SimulationTaskResponse:
    task = await task_repo.get_task_by_id(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return _to_task_response(task)


@router.get("/{simulation_id}/config")
async def get_simulation_config(
    simulation_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    simulation = await simulation_repo.get_simulation_by_id(db, simulation_id)
    if simulation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    if not simulation.config_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation config not found")

    config_path = resolve_upload_path(simulation.config_path)
    if not config_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation config not found")
    return await asyncio.to_thread(_read_json_file, config_path)


@router.get("/{simulation_id}/profiles", response_model=SimulationProfilesResponse)
async def get_simulation_profiles(
    simulation_id: str,
    db: AsyncSession = Depends(get_db),
) -> SimulationProfilesResponse:
    simulation = await simulation_repo.get_simulation_by_id(db, simulation_id)
    if simulation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    profiles_path = simulation_profiles_path(simulation_id)
    fallback_path = simulation_reddit_profiles_path(simulation_id)
    profiles: list[dict[str, Any]] | None = None

    if profiles_path.exists():
        try:
            profiles = await asyncio.to_thread(_read_json_list_file, profiles_path)
        except Exception:
            logger.warning("failed to read full simulation profiles %s; falling back", profiles_path, exc_info=True)

    if profiles is None and fallback_path.exists():
        profiles = await asyncio.to_thread(_read_json_list_file, fallback_path)

    if profiles is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation profiles not found")
    return SimulationProfilesResponse(
        simulation_id=simulation_id,
        count=len(profiles),
        profiles=profiles,
    )


def _schedule_prepare_task(
    *,
    task_id: str,
    project_id: str,
    entity_types: list[str] | None,
    use_llm_for_profiles: bool,
    use_llm_for_config: bool,
    twitter_enabled: bool,
    reddit_enabled: bool,
) -> None:
    task = asyncio.create_task(
        _run_prepare_task(
            task_id=task_id,
            project_id=project_id,
            entity_types=entity_types,
            use_llm_for_profiles=use_llm_for_profiles,
            use_llm_for_config=use_llm_for_config,
            twitter_enabled=twitter_enabled,
            reddit_enabled=reddit_enabled,
        )
    )
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_on_background_task_done)


def _on_background_task_done(task: asyncio.Task[None]) -> None:
    _BACKGROUND_TASKS.discard(task)
    try:
        task.result()
    except Exception:
        logger.exception("background simulation prepare task crashed")


async def _run_prepare_task(
    *,
    task_id: str,
    project_id: str,
    entity_types: list[str] | None,
    use_llm_for_profiles: bool,
    use_llm_for_config: bool,
    twitter_enabled: bool,
    reddit_enabled: bool,
) -> None:
    simulation_id = _new_simulation_id()

    try:
        await _update_task_state(
            task_id,
            status=TaskStatus.PROCESSING.value,
            progress=5,
            message="loading simulation inputs",
            progress_detail_json={"stage": "load_inputs"},
        )

        async with SessionLocal() as session:
            project = await project_repo.get_project_by_id(session, project_id)
            if project is None:
                raise RuntimeError("Project not found")
            if not project.zep_graph_id:
                raise RuntimeError("Project graph is not ready")
            extracted_text_path = (
                resolve_upload_path(project.extracted_text_path)
                if project.extracted_text_path
                else None
            )
            graph_id = project.zep_graph_id
            simulation_requirement = project.simulation_requirement

        document_text = ""
        if extracted_text_path is not None and extracted_text_path.exists():
            document_text = await asyncio.to_thread(_read_text_file, extracted_text_path)

        await _update_task_state(
            task_id,
            progress=15,
            message="reading graph entities",
            progress_detail_json={"stage": "read_entities", "graph_id": graph_id},
        )
        filtered_entities = await asyncio.to_thread(
            _filter_project_entities_sync,
            project_id,
            graph_id,
            entity_types,
        )
        if not filtered_entities.entities:
            raise RuntimeError("No eligible graph entities were found for simulation prepare.")

        await _update_task_state(
            task_id,
            progress=25,
            message="graph entities ready",
            progress_detail_json={
                "stage": "entities_ready",
                "entity_count": filtered_entities.filtered_count,
                "entity_types": filtered_entities.to_dict()["entity_types"],
            },
        )

        writer = TaskStateWriter()

        def profile_progress(current: int, total: int, message: str) -> None:
            ratio = current / max(total, 1)
            writer.set_processing(
                task_id,
                progress=min(68, 30 + int(ratio * 35)),
                message=message,
                progress_detail_json={
                    "stage": "generate_profiles",
                    "current": current,
                    "total": total,
                },
            )

        profiles = await asyncio.to_thread(
            _generate_profiles_sync,
            filtered_entities.entities,
            use_llm_for_profiles,
            profile_progress,
        )

        await _update_task_state(
            task_id,
            progress=70,
            message="writing profile artifacts",
            progress_detail_json={"stage": "write_profiles", "profile_count": len(profiles)},
        )
        await asyncio.to_thread(_write_profile_artifacts, simulation_id, profiles)

        def config_progress(current: int, total: int, message: str) -> None:
            ratio = current / max(total, 1)
            writer.set_processing(
                task_id,
                progress=min(92, 72 + int(ratio * 20)),
                message=message,
                progress_detail_json={
                    "stage": "generate_config",
                    "current": current,
                    "total": total,
                },
            )

        config = await asyncio.to_thread(
            _generate_simulation_config_sync,
            simulation_id,
            project_id,
            graph_id,
            simulation_requirement,
            document_text,
            filtered_entities.entities,
            profiles,
            twitter_enabled,
            reddit_enabled,
            use_llm_for_config,
            config_progress,
        )
        await asyncio.to_thread(_write_simulation_config_artifact, simulation_id, config)

        total_rounds = max(
            1,
            int(config.time_config.total_simulation_hours * 60 / max(config.time_config.minutes_per_round, 1)),
        )
        async with SessionLocal() as session:
            simulation = await simulation_repo.create_simulation(
                session,
                id=simulation_id,
                project_id=project_id,
                status=SimulationStatus.READY.value,
                twitter_enabled=twitter_enabled,
                reddit_enabled=reddit_enabled,
                total_rounds=total_rounds,
                config_path=as_upload_relative_path(simulation_config_path(simulation_id)),
                profiles_dir=as_upload_relative_path(simulation_profiles_dir(simulation_id)),
            )

        result_json = {
            "simulation_id": simulation.id,
            "project_id": project_id,
            "graph_id": graph_id,
            "profile_count": len(profiles),
            "entity_count": filtered_entities.filtered_count,
            "entity_types": filtered_entities.to_dict()["entity_types"],
            "config_path": simulation.config_path,
            "profiles_dir": simulation.profiles_dir,
        }
        await _update_task_state(
            task_id,
            simulation_id=simulation.id,
            status=TaskStatus.COMPLETED.value,
            progress=100,
            message="simulation environment prepared",
            result_json=result_json,
            progress_detail_json={"stage": "completed", **result_json},
            error=None,
        )
    except Exception as exc:
        logger.exception("simulation prepare failed")
        await _update_task_state(
            task_id,
            status=TaskStatus.FAILED.value,
            message="simulation prepare failed",
            error=f"{exc}\n{traceback.format_exc()}",
        )


async def _update_task_state(
    task_id: str,
    *,
    simulation_id: str | None | object = None,
    status: str | None = None,
    progress: int | None = None,
    message: str | None = None,
    result_json: dict | list | None = None,
    progress_detail_json: dict | list | None = None,
    error: str | None = None,
) -> None:
    async with SessionLocal() as session:
        kwargs: dict[str, object] = {}
        if simulation_id is not None:
            kwargs["simulation_id"] = simulation_id
        if status is not None:
            kwargs["status"] = status
        if progress is not None:
            kwargs["progress"] = progress
        if message is not None:
            kwargs["message"] = message
        if result_json is not None:
            kwargs["result_json"] = result_json
        if progress_detail_json is not None:
            kwargs["progress_detail_json"] = progress_detail_json
        if error is not None:
            kwargs["error"] = error
        elif status == TaskStatus.COMPLETED.value:
            kwargs["error"] = None
        await task_repo.update_task(session, task_id, **kwargs)


def _filter_project_entities_sync(
    project_id: str, graph_id: str, entity_types: list[str] | None
):
    cache_path = project_graph_data_path(project_id)
    if cache_path.exists():
        logger.info("loading graph entities from cache: %s", cache_path)
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        reader = ZepEntityReader()
        return reader.filter_from_data(nodes, edges, defined_entity_types=entity_types)

    logger.warning("graph cache not found for project %s, fetching from Zep", project_id)
    reader = ZepEntityReader()
    return reader.filter_defined_entities(
        graph_id,
        defined_entity_types=entity_types,
        enrich_with_edges=True,
    )


def _generate_profiles_sync(
    entities: list,
    use_llm_for_profiles: bool,
    progress_callback,
) -> list[OasisAgentProfile]:
    generator = OasisProfileGenerator()
    return generator.generate_profiles_from_entities(
        entities,
        use_llm=use_llm_for_profiles,
        progress_callback=progress_callback,
    )


def _generate_simulation_config_sync(
    simulation_id: str,
    project_id: str,
    graph_id: str,
    simulation_requirement: str,
    document_text: str,
    entities: list,
    profiles: list[OasisAgentProfile],
    twitter_enabled: bool,
    reddit_enabled: bool,
    use_llm_for_config: bool,
    progress_callback,
) -> SimulationParameters:
    generator = SimulationConfigGenerator()
    return generator.generate_config(
        simulation_id=simulation_id,
        project_id=project_id,
        graph_id=graph_id,
        simulation_requirement=simulation_requirement,
        document_text=document_text,
        entities=entities,
        profiles=profiles,
        enable_twitter=twitter_enabled,
        enable_reddit=reddit_enabled,
        use_llm=use_llm_for_config,
        progress_callback=progress_callback,
    )


def _write_profile_artifacts(simulation_id: str, profiles: list[OasisAgentProfile]) -> None:
    profiles_dir = simulation_profiles_dir(simulation_id)
    ensure_directory(profiles_dir)
    _write_json_file(
        simulation_profiles_path(simulation_id),
        [profile.to_dict() for profile in profiles],
    )
    _write_json_file(
        simulation_reddit_profiles_path(simulation_id),
        [profile.to_reddit_format() for profile in profiles],
    )
    _write_twitter_profiles_csv(
        simulation_twitter_profiles_path(simulation_id),
        [profile.to_twitter_format() for profile in profiles],
    )


def _write_simulation_config_artifact(simulation_id: str, config: SimulationParameters) -> None:
    _write_json_file(simulation_config_path(simulation_id), config.to_dict())


def _write_json_file(path: Path, payload: Any) -> None:
    ensure_parent_directory(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_twitter_profiles_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_parent_directory(path)
    normalized_rows = [
        {
            key: "|".join(value) if isinstance(value, list) else value
            for key, value in row.items()
        }
        for row in rows
    ]
    fieldnames: list[str] = []
    for row in normalized_rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(normalized_rows)


def _read_json_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("simulation config file must contain a JSON object")
    return data


def _read_json_list_file(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError("simulation profile file must contain a JSON array of objects")
    return data


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_recent_actions(simulation_id: str, limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    return _read_actions(simulation_id, None)[-limit:]


def _read_actions(
    simulation_id: str,
    platform: Literal["twitter", "reddit"] | None,
) -> list[dict[str, Any]]:
    platforms = [platform] if platform is not None else ["twitter", "reddit"]
    actions: list[dict[str, Any]] = []
    for platform_name in platforms:
        actions.extend(
            _read_action_file(
                simulation_twitter_actions_path(simulation_id)
                if platform_name == "twitter"
                else simulation_reddit_actions_path(simulation_id),
                platform_name,
            )
        )
    return sorted(actions, key=_action_sort_key)


def _read_action_file(path: Path, platform: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    actions: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            raw_line = line.strip()
            if not raw_line:
                continue
            try:
                data = json.loads(raw_line)
                if not isinstance(data, dict):
                    raise ValueError("action log line must contain a JSON object")
                action = dict(data)
                action.setdefault("platform", platform)
                actions.append(action)
            except Exception as exc:
                logger.warning(
                    "failed to parse action log line %s:%s: %s",
                    path,
                    line_number,
                    exc,
                )
    return actions


def _action_sort_key(action: dict[str, Any]) -> tuple[int, str, str, int]:
    try:
        round_number = int(action.get("round_number") or 0)
    except (TypeError, ValueError):
        round_number = 0
    try:
        agent_id = int(action.get("agent_id") or 0)
    except (TypeError, ValueError):
        agent_id = 0
    return (
        round_number,
        str(action.get("created_at") or ""),
        str(action.get("platform") or ""),
        agent_id,
    )


def _to_task_response(task: Task) -> SimulationTaskResponse:
    return SimulationTaskResponse(
        task_id=task.id,
        task_type=task.task_type,
        project_id=task.project_id,
        simulation_id=task.simulation_id,
        status=task.status,
        progress=task.progress,
        message=task.message,
        result_json=task.result_json,
        progress_detail_json=task.progress_detail_json,
        error=task.error,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _to_start_response(result: SimulationStartResult) -> StartSimulationResponse:
    return StartSimulationResponse(
        simulation_id=result.simulation_id,
        status=result.status,
        pid=result.pid,
    )


def _to_stop_response(result: SimulationStopResult) -> StopSimulationResponse:
    return StopSimulationResponse(
        simulation_id=result.simulation_id,
        status=result.status,
        command_id=result.command_id,
    )


def _to_status_response(
    simulation: Simulation,
    recent_actions: list[dict[str, Any]],
) -> SimulationStatusResponse:
    return SimulationStatusResponse(
        simulation_id=simulation.id,
        project_id=simulation.project_id,
        status=simulation.status,
        total_rounds=simulation.total_rounds,
        current_round=simulation.current_round,
        twitter_enabled=simulation.twitter_enabled,
        reddit_enabled=simulation.reddit_enabled,
        twitter_actions_count=simulation.twitter_actions_count,
        reddit_actions_count=simulation.reddit_actions_count,
        recent_actions=recent_actions,
        interactive_ready=simulation.interactive_ready,
        error=simulation.error,
        started_at=simulation.started_at,
        completed_at=simulation.completed_at,
        created_at=simulation.created_at,
        updated_at=simulation.updated_at,
    )

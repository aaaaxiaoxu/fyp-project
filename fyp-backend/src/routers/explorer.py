from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import ExplorerSession, Project, Simulation
from ..repositories import explorer_session_repo, project_repo, simulation_repo
from ..services import ExplorerAgent, ExplorerEvent, ExplorerRunResult, ZepToolsService
from ..utils import get_logger
from ..utils.path_resolver import (
    as_upload_relative_path,
    ensure_parent_directory,
    explorer_console_log_path,
    explorer_session_log_path,
    resolve_upload_path,
    project_graph_data_path,
    simulation_profiles_path,
    simulation_reddit_actions_path,
    simulation_reddit_profiles_path,
    simulation_twitter_actions_path,
)

router = APIRouter(tags=["Explorer"])
logger = get_logger("fyp.explorer")
_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


def _normalize_session_id(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if not _SESSION_ID_PATTERN.fullmatch(stripped):
        raise ValueError("session_id may only contain letters, numbers, underscores, dots, or hyphens")
    return stripped


class ExplorerAskRequest(BaseModel):
    simulation_id: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=64)

    @field_validator("simulation_id", "question")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("session_id")
    @classmethod
    def normalize_session_id(cls, value: str | None) -> str | None:
        return _normalize_session_id(value)


class ExplorerInterviewRequest(BaseModel):
    simulation_id: str = Field(min_length=1)
    question: str = Field(default="What is your view of the simulation outcome?", min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=64)

    @field_validator("simulation_id", "question")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("session_id")
    @classmethod
    def normalize_session_id(cls, value: str | None) -> str | None:
        return _normalize_session_id(value)


class ExplorerTurnResponse(BaseModel):
    turn_id: str
    session_id: str
    simulation_id: str
    mode: str
    question: str
    answer: str
    agent_id: int | None = None
    tool_name: str
    created_at: str


class ExplorerSessionHistoryResponse(BaseModel):
    session_id: str
    simulation_id: str
    title: str
    status: str
    log_path: str | None
    created_at: datetime
    updated_at: datetime
    turns: list[ExplorerTurnResponse]


class ExplorerHistoryResponse(BaseModel):
    simulation_id: str
    count: int
    sessions: list[ExplorerSessionHistoryResponse]


@router.post("/ask")
async def ask_explorer(
    req: ExplorerAskRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    simulation, project = await _get_simulation_and_project(db, req.simulation_id)
    explorer_session = await _ensure_session(db, simulation, req.session_id, _session_title("Ask", req.question))
    agent = await _build_agent(simulation, project)
    try:
        result = await asyncio.to_thread(agent.ask, req.question)
    except Exception as exc:
        logger.exception("explorer ask failed for simulation %s", simulation.id)
        result = _error_result(simulation, project, "ask", str(exc))
    await _persist_turn(
        db,
        explorer_session,
        mode="ask",
        question=req.question,
        result=result,
    )
    return _sse_response(result.events)


@router.post("/interview/{agent_id}")
async def interview_agent(
    agent_id: int,
    req: ExplorerInterviewRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    simulation, project = await _get_simulation_and_project(db, req.simulation_id)
    if not simulation.interactive_ready:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Simulation is not interactive_ready yet. Run or complete the simulation before interviewing agents.",
        )

    explorer_session = await _ensure_session(db, simulation, req.session_id, _session_title("Interview", req.question))
    agent = await _build_agent(simulation, project)
    try:
        result = await asyncio.to_thread(agent.interview, agent_id, req.question)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("explorer interview failed for simulation %s agent %s", simulation.id, agent_id)
        result = _error_result(simulation, project, "interview", str(exc), agent_id=agent_id)
    await _persist_turn(
        db,
        explorer_session,
        mode="interview",
        question=req.question,
        result=result,
        agent_id=agent_id,
    )
    return _sse_response(result.events)


@router.get("/history/{simulation_id}", response_model=ExplorerHistoryResponse)
async def get_explorer_history(
    simulation_id: str,
    db: AsyncSession = Depends(get_db),
) -> ExplorerHistoryResponse:
    simulation = await simulation_repo.get_simulation_by_id(db, simulation_id)
    if simulation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    sessions = await explorer_session_repo.list_explorer_sessions(db, simulation_id=simulation_id)
    records: list[ExplorerSessionHistoryResponse] = []
    for session in sessions:
        turns = await asyncio.to_thread(_read_turns, session.log_path)
        records.append(
            ExplorerSessionHistoryResponse(
                session_id=session.id,
                simulation_id=session.simulation_id,
                title=session.title,
                status=session.status,
                log_path=session.log_path,
                created_at=session.created_at,
                updated_at=session.updated_at,
                turns=[ExplorerTurnResponse(**turn) for turn in turns],
            )
        )
    return ExplorerHistoryResponse(simulation_id=simulation_id, count=len(records), sessions=records)


async def _get_simulation_and_project(
    db: AsyncSession,
    simulation_id: str,
) -> tuple[Simulation, Project]:
    simulation = await simulation_repo.get_simulation_by_id(db, simulation_id)
    if simulation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    project = await project_repo.get_project_by_id(db, simulation.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if not project.zep_graph_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project graph is not ready")
    return simulation, project


async def _ensure_session(
    db: AsyncSession,
    simulation: Simulation,
    requested_session_id: str | None,
    title: str,
) -> ExplorerSession:
    session_id = requested_session_id or _new_session_id()
    log_path = as_upload_relative_path(explorer_session_log_path(simulation.id, session_id))
    existing = await explorer_session_repo.get_explorer_session_by_id(db, session_id)
    if existing is not None:
        if existing.simulation_id != simulation.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Explorer session belongs to another simulation.",
            )
        updated = await explorer_session_repo.update_explorer_session(db, session_id, log_path=log_path, touch=True)
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Explorer session not found")
        return updated

    return await explorer_session_repo.create_explorer_session(
        db,
        id=session_id,
        simulation_id=simulation.id,
        title=title,
        log_path=log_path,
    )


async def _build_agent(simulation: Simulation, project: Project) -> ExplorerAgent:
    graph_path = project_graph_data_path(project.id)
    if not graph_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project graph cache not found")

    graph_data, profiles, actions = await asyncio.gather(
        asyncio.to_thread(_read_json_object, graph_path),
        asyncio.to_thread(_read_profiles, simulation.id),
        asyncio.to_thread(_read_actions, simulation.id),
    )
    tools = ZepToolsService(graph_data, profiles=profiles, actions=actions)
    return ExplorerAgent(
        graph_id=project.zep_graph_id or str(graph_data.get("graph_id") or ""),
        simulation_id=simulation.id,
        simulation_requirement=project.simulation_requirement,
        tools=tools,
    )


async def _persist_turn(
    db: AsyncSession,
    explorer_session: ExplorerSession,
    *,
    mode: str,
    question: str,
    result: ExplorerRunResult,
    agent_id: int | None = None,
) -> None:
    turn = {
        "turn_id": f"turn_{uuid4().hex[:12]}",
        "session_id": explorer_session.id,
        "simulation_id": explorer_session.simulation_id,
        "mode": mode,
        "question": question,
        "answer": result.answer,
        "agent_id": agent_id,
        "tool_name": result.tool_name,
        "tool_result": result.tool_result,
        "events": [{"event": event.event, "data": event.data} for event in result.events],
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    log_path = explorer_session_log_path(explorer_session.simulation_id, explorer_session.id)
    console_path = explorer_console_log_path(explorer_session.simulation_id, explorer_session.id)
    await asyncio.to_thread(_append_jsonl, log_path, turn)
    await asyncio.to_thread(_append_console_log, console_path, turn)
    await explorer_session_repo.update_explorer_session(
        db,
        explorer_session.id,
        log_path=as_upload_relative_path(log_path),
        touch=True,
    )


def _sse_response(events: list[ExplorerEvent]) -> StreamingResponse:
    return StreamingResponse(
        _stream_sse(events),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


def _error_result(
    simulation: Simulation,
    project: Project,
    mode: str,
    message: str,
    *,
    agent_id: int | None = None,
) -> ExplorerRunResult:
    data = {
        "simulation_id": simulation.id,
        "graph_id": project.zep_graph_id,
        "mode": mode,
        "message": message or "Explorer failed.",
        **({"agent_id": agent_id} if agent_id is not None else {}),
    }
    return ExplorerRunResult(
        events=[
            ExplorerEvent("status", {**data, "status": "failed"}),
            ExplorerEvent("error", data),
        ],
        answer="",
        tool_name="error",
        tool_result={"error": data["message"]},
    )


async def _stream_sse(events: list[ExplorerEvent]) -> AsyncIterator[str]:
    for event in events:
        yield f"event: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"


def _new_session_id() -> str:
    return f"explorer_{uuid4().hex[:12]}"


def _session_title(prefix: str, question: str) -> str:
    compact = " ".join(question.split())
    return f"{prefix}: {compact[:80]}" if compact else prefix


def _read_json_object(path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _read_profiles(simulation_id: str) -> list[dict[str, Any]]:
    for path in (simulation_profiles_path(simulation_id), simulation_reddit_profiles_path(simulation_id)):
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [dict(item) for item in payload if isinstance(item, dict)]
    return []


def _read_actions(simulation_id: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for platform, path in (
        ("twitter", simulation_twitter_actions_path(simulation_id)),
        ("reddit", simulation_reddit_actions_path(simulation_id)),
    ):
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                    if isinstance(payload, dict):
                        action = dict(payload)
                        action.setdefault("platform", platform)
                        actions.append(action)
                except json.JSONDecodeError:
                    logger.warning("skipping invalid action log line %s:%s", path, line_number)
    return sorted(actions, key=_action_sort_key)


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


def _append_jsonl(path, payload: dict[str, Any]) -> None:
    ensure_parent_directory(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _append_console_log(path, payload: dict[str, Any]) -> None:
    ensure_parent_directory(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{payload['created_at']}] {payload['mode']} {payload['tool_name']}: {payload['question']}\n")


def _read_turns(log_path: str | None) -> list[dict[str, Any]]:
    if not log_path:
        return []
    try:
        path = resolve_upload_path(log_path)
    except ValueError:
        logger.warning("invalid explorer log path: %s", log_path)
        return []
    if not path.exists():
        return []

    turns: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("skipping invalid explorer history line %s:%s", path, line_number)
                continue
            if not isinstance(payload, dict):
                continue
            turns.append(
                {
                    "turn_id": str(payload.get("turn_id") or ""),
                    "session_id": str(payload.get("session_id") or ""),
                    "simulation_id": str(payload.get("simulation_id") or ""),
                    "mode": str(payload.get("mode") or ""),
                    "question": str(payload.get("question") or ""),
                    "answer": str(payload.get("answer") or ""),
                    "agent_id": payload.get("agent_id"),
                    "tool_name": str(payload.get("tool_name") or ""),
                    "created_at": str(payload.get("created_at") or ""),
                }
            )
    return turns

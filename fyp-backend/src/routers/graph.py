from __future__ import annotations

import asyncio
import json
import re
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters import TaskStateWriter
from ..auth_deps import get_current_user, get_db
from ..db import SessionLocal
from ..models import Project, ProjectStatus, Task, TaskStatus, User
from ..repositories import project_file_repo, project_repo, task_repo
from ..settings import settings
from ..services import GraphBuildResult, GraphBuilderService, OntologyGenerator, TextProcessor, ZepEntityReader
from ..utils import FileParser, get_logger
from ..utils.path_resolver import (
    as_upload_relative_path,
    ensure_directory,
    ensure_parent_directory,
    project_dir,
    project_extracted_text_path,
    project_ontology_path,
    project_original_dir,
    resolve_upload_path,
)

router = APIRouter(tags=["Graph"])
logger = get_logger("fyp.graph")
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()


def _new_project_id() -> str:
    return f"proj_{uuid4().hex[:12]}"


def _new_project_file_id() -> str:
    return f"file_{uuid4().hex[:12]}"


def _new_task_id() -> str:
    return f"task_{uuid4().hex[:12]}"


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    simulation_requirement: str = Field(min_length=1)

    @field_validator("name", "simulation_requirement")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    status: str
    zep_graph_id: str | None
    simulation_requirement: str
    ontology_path: str | None
    extracted_text_path: str | None
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]


class DeleteProjectResponse(BaseModel):
    ok: bool
    project_id: str


class CreateOntologyTaskResponse(BaseModel):
    task_id: str


class BuildGraphRequest(BaseModel):
    project_id: str = Field(min_length=1)
    graph_name: str | None = Field(default=None, max_length=255)
    chunk_size: int = Field(default=settings.DEFAULT_CHUNK_SIZE, ge=100, le=10000)
    chunk_overlap: int = Field(default=settings.DEFAULT_CHUNK_OVERLAP, ge=0, le=5000)
    batch_size: int = Field(default=3, ge=1, le=20)

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("graph_name")
    @classmethod
    def normalize_graph_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_chunk_overlap(self) -> "BuildGraphRequest":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


class GraphTaskResponse(BaseModel):
    task_id: str
    task_type: str
    user_id: str
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


class GraphDataNodeResponse(BaseModel):
    uuid: str
    name: str
    labels: list[str]
    summary: str
    attributes: dict[str, Any]
    created_at: str | None = None


class GraphDataEdgeResponse(BaseModel):
    uuid: str
    name: str
    fact: str
    fact_type: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: str
    target_node_name: str
    attributes: dict[str, Any]
    created_at: str | None = None
    valid_at: str | None = None
    invalid_at: str | None = None
    expired_at: str | None = None
    episodes: list[str]


class GraphDataResponse(BaseModel):
    graph_id: str
    nodes: list[GraphDataNodeResponse]
    edges: list[GraphDataEdgeResponse]
    node_count: int
    edge_count: int


class GraphEntityResponse(BaseModel):
    uuid: str
    name: str
    labels: list[str]
    summary: str
    attributes: dict[str, Any]
    related_edges: list[dict[str, Any]]
    related_nodes: list[dict[str, Any]]


class GraphEntitiesResponse(BaseModel):
    graph_id: str
    entities: list[GraphEntityResponse]
    entity_types: list[str]
    total_count: int
    filtered_count: int


@router.post("/project", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    req: CreateProjectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Project:
    return await project_repo.create_project(
        db,
        id=_new_project_id(),
        user_id=current_user.id,
        name=req.name,
        simulation_requirement=req.simulation_requirement,
    )


@router.get("/project/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Project:
    project = await project_repo.get_project_by_id(db, project_id, user_id=current_user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectListResponse:
    projects = await project_repo.list_projects_by_user(db, current_user.id)
    return ProjectListResponse(projects=projects)


@router.delete("/project/{project_id}", response_model=DeleteProjectResponse)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeleteProjectResponse:
    deleted = await project_repo.delete_project(db, project_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return DeleteProjectResponse(ok=True, project_id=project_id)


@router.post(
    "/ontology/generate",
    response_model=CreateOntologyTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_ontology(
    project_id: str = Form(...),
    files: list[UploadFile] = File(...),
    additional_context: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CreateOntologyTaskResponse:
    project = await project_repo.get_project_by_id(db, project_id, user_id=current_user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    upload_specs = await _read_upload_specs(files)
    if not upload_specs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one file is required")

    task = await task_repo.create_task(
        db,
        id=_new_task_id(),
        user_id=current_user.id,
        project_id=project_id,
        task_type="ontology_generate",
        status=TaskStatus.PENDING.value,
        progress=0,
        message="queued",
    )
    _schedule_ontology_generation(
        task_id=task.id,
        user_id=current_user.id,
        project_id=project_id,
        simulation_requirement=project.simulation_requirement,
        additional_context=additional_context.strip() if additional_context else None,
        uploads=upload_specs,
    )
    return CreateOntologyTaskResponse(task_id=task.id)


@router.get("/task/{task_id}", response_model=GraphTaskResponse)
async def get_graph_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GraphTaskResponse:
    task = await task_repo.get_task_by_id(db, task_id, user_id=current_user.id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return _to_graph_task_response(task)


@router.post("/build", response_model=CreateOntologyTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def build_graph(
    req: BuildGraphRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CreateOntologyTaskResponse:
    project = await project_repo.get_project_by_id(db, req.project_id, user_id=current_user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if not project.ontology_path or not project.extracted_text_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project ontology is not ready",
        )

    task = await task_repo.create_task(
        db,
        id=_new_task_id(),
        user_id=current_user.id,
        project_id=req.project_id,
        task_type="graph_build",
        status=TaskStatus.PENDING.value,
        progress=0,
        message="queued",
    )
    _schedule_graph_build(
        task_id=task.id,
        user_id=current_user.id,
        project_id=req.project_id,
        graph_name=req.graph_name or project.name,
        chunk_size=req.chunk_size,
        chunk_overlap=req.chunk_overlap,
        batch_size=req.batch_size,
    )
    return CreateOntologyTaskResponse(task_id=task.id)


@router.get("/data/{graph_id}", response_model=GraphDataResponse)
async def get_graph_data(
    graph_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GraphDataResponse:
    await _get_owned_project_by_graph_id(db, graph_id, current_user.id)
    data = await asyncio.to_thread(_get_graph_data_sync, graph_id)
    return GraphDataResponse(**data)


@router.get("/entities/{graph_id}", response_model=GraphEntitiesResponse)
async def get_graph_entities(
    graph_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GraphEntitiesResponse:
    await _get_owned_project_by_graph_id(db, graph_id, current_user.id)
    payload = await asyncio.to_thread(_get_graph_entities_sync, graph_id)
    return GraphEntitiesResponse(graph_id=graph_id, **payload)


async def _read_upload_specs(files: list[UploadFile]) -> list[dict[str, str | bytes | int]]:
    upload_specs: list[dict[str, str | bytes | int]] = []
    for upload in files:
        filename = _validate_upload_filename(upload.filename)
        data = await upload.read()
        await upload.close()
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Uploaded file is empty: {filename}",
            )
        if len(data) > settings.MAX_CONTENT_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Uploaded file exceeds size limit: {filename}",
            )
        upload_specs.append(
            {
                "original_name": filename,
                "content": data,
                "size_bytes": len(data),
            }
        )
    return upload_specs


def _validate_upload_filename(filename: str | None) -> str:
    candidate = Path(filename or "").name.strip()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File name is required")

    suffix = Path(candidate).suffix.lower().lstrip(".")
    if suffix not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {candidate}",
        )
    return candidate


def _schedule_ontology_generation(
    *,
    task_id: str,
    user_id: str,
    project_id: str,
    simulation_requirement: str,
    additional_context: str | None,
    uploads: list[dict[str, str | bytes | int]],
) -> None:
    task = asyncio.create_task(
        _run_ontology_generation(
            task_id=task_id,
            user_id=user_id,
            project_id=project_id,
            simulation_requirement=simulation_requirement,
            additional_context=additional_context,
            uploads=uploads,
        )
    )
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_on_background_task_done)


def _schedule_graph_build(
    *,
    task_id: str,
    user_id: str,
    project_id: str,
    graph_name: str,
    chunk_size: int,
    chunk_overlap: int,
    batch_size: int,
) -> None:
    task = asyncio.create_task(
        _run_graph_build(
            task_id=task_id,
            user_id=user_id,
            project_id=project_id,
            graph_name=graph_name,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            batch_size=batch_size,
        )
    )
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_on_background_task_done)


def _on_background_task_done(task: asyncio.Task[None]) -> None:
    _BACKGROUND_TASKS.discard(task)
    try:
        task.result()
    except Exception:
        logger.exception("background ontology generation task crashed")


async def _run_ontology_generation(
    *,
    task_id: str,
    user_id: str,
    project_id: str,
    simulation_requirement: str,
    additional_context: str | None,
    uploads: list[dict[str, str | bytes | int]],
) -> None:
    saved_paths: list[str] = []
    try:
        await _update_task_state(task_id, user_id=user_id, status=TaskStatus.PROCESSING.value, progress=5, message="saving uploaded files")
        saved_files = await asyncio.to_thread(_save_original_uploads, project_id, uploads)
        saved_paths = [item["absolute_path"] for item in saved_files]

        async with SessionLocal() as session:
            for item in saved_files:
                await project_file_repo.create_project_file(
                    session,
                    id=_new_project_file_id(),
                    project_id=project_id,
                    original_name=item["original_name"],
                    stored_path=item["relative_path"],
                    file_type=item["file_type"],
                    size_bytes=item["size_bytes"],
                )

        await _update_task_state(task_id, user_id=user_id, progress=30, message="extracting document text")
        extracted = await asyncio.to_thread(_extract_and_preprocess_documents, saved_paths)

        extracted_text_path = project_extracted_text_path(project_id)
        await asyncio.to_thread(_write_text_file, extracted_text_path, extracted["combined_text"])

        async with SessionLocal() as session:
            await project_repo.update_project(
                session,
                project_id,
                user_id=user_id,
                extracted_text_path=as_upload_relative_path(extracted_text_path),
            )

        await _update_task_state(
            task_id,
            user_id=user_id,
            progress=70,
            message="generating ontology",
            progress_detail_json=extracted["stats"],
        )
        ontology = await asyncio.to_thread(
            _generate_ontology_sync,
            extracted["document_texts"],
            simulation_requirement,
            additional_context,
        )

        ontology_path = project_ontology_path(project_id)
        await asyncio.to_thread(_write_json_file, ontology_path, ontology)

        result_json = {
            "project_id": project_id,
            "ontology_path": as_upload_relative_path(ontology_path),
            "extracted_text_path": as_upload_relative_path(extracted_text_path),
            "file_count": len(saved_files),
        }
        async with SessionLocal() as session:
            await project_repo.update_project(
                session,
                project_id,
                user_id=user_id,
                status=ProjectStatus.ONTOLOGY_GENERATED.value,
                ontology_path=result_json["ontology_path"],
                extracted_text_path=result_json["extracted_text_path"],
            )

        await _update_task_state(
            task_id,
            user_id=user_id,
            status=TaskStatus.COMPLETED.value,
            progress=100,
            message="ontology generated",
            result_json=result_json,
            progress_detail_json=extracted["stats"],
            error=None,
        )
    except Exception as exc:
        logger.exception("ontology generation failed")
        async with SessionLocal() as session:
            await project_repo.update_project(
                session,
                project_id,
                user_id=user_id,
                status=ProjectStatus.FAILED.value,
            )
        await _update_task_state(
            task_id,
            user_id=user_id,
            status=TaskStatus.FAILED.value,
            message="ontology generation failed",
            error=f"{exc}\n{traceback.format_exc()}",
        )


async def _run_graph_build(
    *,
    task_id: str,
    user_id: str,
    project_id: str,
    graph_name: str,
    chunk_size: int,
    chunk_overlap: int,
    batch_size: int,
) -> None:
    try:
        await _update_task_state(
            task_id,
            user_id=user_id,
            status=TaskStatus.PROCESSING.value,
            progress=5,
            message="loading graph build inputs",
            progress_detail_json={"stage": "load_inputs"},
        )

        async with SessionLocal() as session:
            project = await project_repo.get_project_by_id(session, project_id, user_id=user_id)
            if project is None:
                raise RuntimeError("Project not found")
            if not project.ontology_path or not project.extracted_text_path:
                raise RuntimeError("Project ontology is not ready")

            await project_repo.update_project(
                session,
                project_id,
                user_id=user_id,
                status=ProjectStatus.GRAPH_BUILDING.value,
            )
            ontology_path = resolve_upload_path(project.ontology_path)
            extracted_text_path = resolve_upload_path(project.extracted_text_path)

        ontology = await asyncio.to_thread(_read_json_file, ontology_path)
        extracted_text = await asyncio.to_thread(_read_text_file, extracted_text_path)

        result = await asyncio.to_thread(
            _build_graph_sync,
            task_id,
            user_id,
            extracted_text,
            ontology,
            graph_name,
            chunk_size,
            chunk_overlap,
            batch_size,
        )

        result_json = {
            "project_id": project_id,
            "graph_id": result.graph_id,
            "node_count": result.node_count,
            "edge_count": result.edge_count,
            "chunk_count": result.chunk_count,
            "entity_types": result.entity_types,
        }
        async with SessionLocal() as session:
            await project_repo.update_project(
                session,
                project_id,
                user_id=user_id,
                status=ProjectStatus.GRAPH_COMPLETED.value,
                zep_graph_id=result.graph_id,
            )

        await _update_task_state(
            task_id,
            user_id=user_id,
            status=TaskStatus.COMPLETED.value,
            progress=100,
            message="graph built",
            result_json=result_json,
            progress_detail_json={"stage": "completed", **result_json},
            error=None,
        )
    except Exception as exc:
        logger.exception("graph build failed")
        async with SessionLocal() as session:
            await project_repo.update_project(
                session,
                project_id,
                user_id=user_id,
                status=ProjectStatus.FAILED.value,
            )
        await _update_task_state(
            task_id,
            user_id=user_id,
            status=TaskStatus.FAILED.value,
            message="graph build failed",
            error=f"{exc}\n{traceback.format_exc()}",
        )


async def _update_task_state(
    task_id: str,
    *,
    user_id: str,
    status: str | None = None,
    progress: int | None = None,
    message: str | None = None,
    result_json: dict | list | None = None,
    progress_detail_json: dict | list | None = None,
    error: str | None = None,
) -> None:
    async with SessionLocal() as session:
        kwargs: dict[str, object] = {}
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
        await task_repo.update_task(session, task_id, user_id=user_id, **kwargs)


async def _get_owned_project_by_graph_id(
    db: AsyncSession,
    graph_id: str,
    user_id: str,
) -> Project:
    project = await project_repo.get_project_by_graph_id(db, graph_id, user_id=user_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Graph not found")
    return project


def _save_original_uploads(
    project_id: str,
    uploads: list[dict[str, str | bytes | int]],
) -> list[dict[str, str | int]]:
    ensure_directory(project_dir(project_id))
    ensure_directory(project_original_dir(project_id))

    saved_files: list[dict[str, str | int]] = []
    used_filenames: set[str] = set()
    for upload in uploads:
        original_name = str(upload["original_name"])
        stored_name = _build_stored_filename(original_name, used_filenames)
        absolute_path = project_original_dir(project_id) / stored_name
        ensure_parent_directory(absolute_path)
        absolute_path.write_bytes(bytes(upload["content"]))
        saved_files.append(
            {
                "original_name": original_name,
                "stored_name": stored_name,
                "absolute_path": str(absolute_path),
                "relative_path": as_upload_relative_path(absolute_path),
                "size_bytes": int(upload["size_bytes"]),
                "file_type": Path(original_name).suffix.lower().lstrip("."),
            }
        )
    return saved_files


def _build_stored_filename(original_name: str, used_filenames: set[str]) -> str:
    source = Path(original_name)
    sanitized_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", source.stem).strip("._") or "file"
    sanitized_suffix = re.sub(r"[^A-Za-z0-9.]+", "", source.suffix.lower()) or ".txt"
    candidate = f"{sanitized_stem}{sanitized_suffix}"
    counter = 1
    while candidate in used_filenames:
        candidate = f"{sanitized_stem}_{counter}{sanitized_suffix}"
        counter += 1
    used_filenames.add(candidate)
    return candidate


def _extract_and_preprocess_documents(file_paths: list[str]) -> dict[str, object]:
    document_texts: list[str] = []
    combined_parts: list[str] = []
    for index, file_path in enumerate(file_paths, start=1):
        extracted_text = TextProcessor.preprocess_text(FileParser.extract_text(file_path))
        document_texts.append(extracted_text)
        combined_parts.append(f"=== 文档 {index}: {Path(file_path).name} ===\n{extracted_text}")

    combined_text = "\n\n".join(combined_parts).strip()
    return {
        "document_texts": document_texts,
        "combined_text": combined_text,
        "stats": TextProcessor.get_text_stats(combined_text),
    }


def _generate_ontology_sync(
    document_texts: list[str],
    simulation_requirement: str,
    additional_context: str | None,
) -> dict[str, object]:
    generator = OntologyGenerator()
    return generator.generate(
        document_texts=document_texts,
        simulation_requirement=simulation_requirement,
        additional_context=additional_context,
    )


def _build_graph_sync(
    task_id: str,
    user_id: str,
    text: str,
    ontology: dict[str, Any],
    graph_name: str,
    chunk_size: int,
    chunk_overlap: int,
    batch_size: int,
) -> GraphBuildResult:
    writer = TaskStateWriter()

    def progress_callback(progress: int, message: str, detail: dict[str, Any] | None = None) -> None:
        if detail is None:
            writer.set_processing(
                task_id,
                user_id=user_id,
                progress=progress,
                message=message,
            )
        else:
            writer.set_processing(
                task_id,
                user_id=user_id,
                progress=progress,
                message=message,
                progress_detail_json=detail,
            )

    builder = GraphBuilderService()
    return builder.build_graph(
        text=text,
        ontology=ontology,
        graph_name=graph_name,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        batch_size=batch_size,
        progress_callback=progress_callback,
    )


def _write_text_file(path: Path, content: str) -> None:
    ensure_parent_directory(path)
    path.write_text(content, encoding="utf-8")


def _write_json_file(path: Path, content: dict[str, object]) -> None:
    ensure_parent_directory(path)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("ontology file must contain a JSON object")
    return data


def _get_graph_data_sync(graph_id: str) -> dict[str, Any]:
    reader = ZepEntityReader()
    return reader.get_graph_data(graph_id)


def _get_graph_entities_sync(graph_id: str) -> dict[str, Any]:
    reader = ZepEntityReader()
    return reader.filter_defined_entities(graph_id).to_dict()


def _to_graph_task_response(task: Task) -> GraphTaskResponse:
    return GraphTaskResponse(
        task_id=task.id,
        task_type=task.task_type,
        user_id=task.user_id,
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

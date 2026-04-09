from __future__ import annotations

import asyncio
import json
import re
import traceback
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth_deps import get_current_user, get_db
from ..db import SessionLocal
from ..models import Project, ProjectStatus, Task, TaskStatus, User
from ..repositories import project_file_repo, project_repo, task_repo
from ..settings import settings
from ..services import OntologyGenerator, TextProcessor
from ..utils import FileParser, get_logger
from ..utils.path_resolver import (
    as_upload_relative_path,
    ensure_directory,
    ensure_parent_directory,
    project_dir,
    project_extracted_text_path,
    project_ontology_path,
    project_original_dir,
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


def _write_text_file(path: Path, content: str) -> None:
    ensure_parent_directory(path)
    path.write_text(content, encoding="utf-8")


def _write_json_file(path: Path, content: dict[str, object]) -> None:
    ensure_parent_directory(path)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")


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

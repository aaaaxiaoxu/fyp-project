from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth_deps import get_current_user, get_db
from ..models import Project, User
from ..repositories import project_repo

router = APIRouter(tags=["Graph"])


def _new_project_id() -> str:
    return f"proj_{uuid4().hex[:12]}"


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

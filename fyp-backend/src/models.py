from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _enum_check_constraint(column_name: str, enum_cls: type[Enum], name: str) -> CheckConstraint:
    allowed_values = ", ".join(f"'{item.value}'" for item in enum_cls)
    return CheckConstraint(f"{column_name} IN ({allowed_values})", name=name)


class ProjectStatus(str, Enum):
    CREATED = "created"
    ONTOLOGY_GENERATED = "ontology_generated"
    GRAPH_BUILDING = "graph_building"
    GRAPH_COMPLETED = "graph_completed"
    FAILED = "failed"


class SimulationStatus(str, Enum):
    CREATED = "created"
    PREPARING = "preparing"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExplorerSessionStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # uuid hex
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    nickname: Mapped[str] = mapped_column(String(200), default="")
    avatar_url: Mapped[str | None] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    projects: Mapped[list["Project"]] = relationship(back_populates="user")
    simulations: Mapped[list["Simulation"]] = relationship(back_populates="user")
    tasks: Mapped[list["Task"]] = relationship(back_populates="user")
    explorer_sessions: Mapped[list["ExplorerSession"]] = relationship(back_populates="user")


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), index=True)

    token_hash: Mapped[str] = mapped_column(String(64), index=True)  # sha256 hex
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), index=True)

    jti_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # sha256(jti)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        _enum_check_constraint("status", ProjectStatus, "ck_projects_status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(32),
        default=ProjectStatus.CREATED.value,
        server_default=text("'created'"),
        index=True,
    )
    zep_graph_id: Mapped[str | None] = mapped_column(String(255), default=None)
    simulation_requirement: Mapped[str] = mapped_column(Text)
    ontology_path: Mapped[str | None] = mapped_column(String(1024), default=None)
    extracted_text_path: Mapped[str | None] = mapped_column(String(1024), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="projects")
    files: Mapped[list["ProjectFile"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    simulations: Mapped[list["Simulation"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    tasks: Mapped[list["Task"]] = relationship(back_populates="project", passive_deletes=True)


class ProjectFile(Base):
    __tablename__ = "project_files"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="ck_project_files_size_bytes_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(1024))
    file_type: Mapped[str] = mapped_column(String(32))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="files")


class Simulation(Base):
    __tablename__ = "simulations"
    __table_args__ = (
        _enum_check_constraint("status", SimulationStatus, "ck_simulations_status"),
        CheckConstraint("total_rounds IS NULL OR total_rounds >= 0", name="ck_simulations_total_rounds_nonnegative"),
        CheckConstraint("current_round >= 0", name="ck_simulations_current_round_nonnegative"),
        CheckConstraint("twitter_actions_count >= 0", name="ck_simulations_twitter_actions_nonnegative"),
        CheckConstraint("reddit_actions_count >= 0", name="ck_simulations_reddit_actions_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default=SimulationStatus.CREATED.value,
        server_default=text("'created'"),
        index=True,
    )
    twitter_enabled: Mapped[bool] = mapped_column(Boolean)
    reddit_enabled: Mapped[bool] = mapped_column(Boolean)
    interactive_ready: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    total_rounds: Mapped[int | None] = mapped_column(Integer, default=None)
    current_round: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    twitter_actions_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    reddit_actions_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    config_path: Mapped[str | None] = mapped_column(String(1024), default=None)
    profiles_dir: Mapped[str | None] = mapped_column(String(1024), default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project: Mapped[Project] = relationship(back_populates="simulations")
    user: Mapped[User] = relationship(back_populates="simulations")
    tasks: Mapped[list["Task"]] = relationship(back_populates="simulation", passive_deletes=True)
    explorer_sessions: Mapped[list["ExplorerSession"]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
    )


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        _enum_check_constraint("status", TaskStatus, "ck_tasks_status"),
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_tasks_progress_range"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("projects.id", ondelete="SET NULL"),
        index=True,
        default=None,
    )
    simulation_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("simulations.id", ondelete="SET NULL"),
        index=True,
        default=None,
    )
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), index=True)
    task_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default=TaskStatus.PENDING.value,
        server_default=text("'pending'"),
        index=True,
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    message: Mapped[str] = mapped_column(String(1024), default="", server_default=text("''"))
    result_json: Mapped[dict | list | None] = mapped_column(JSON, default=None)
    progress_detail_json: Mapped[dict | list | None] = mapped_column(JSON, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project: Mapped[Project | None] = relationship(back_populates="tasks")
    simulation: Mapped[Simulation | None] = relationship(back_populates="tasks")
    user: Mapped[User] = relationship(back_populates="tasks")


class ExplorerSession(Base):
    __tablename__ = "explorer_sessions"
    __table_args__ = (
        _enum_check_constraint("status", ExplorerSessionStatus, "ck_explorer_sessions_status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    simulation_id: Mapped[str] = mapped_column(String(64), ForeignKey("simulations.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(32),
        default=ExplorerSessionStatus.ACTIVE.value,
        server_default=text("'active'"),
        index=True,
    )
    log_path: Mapped[str | None] = mapped_column(String(1024), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    simulation: Mapped[Simulation] = relationship(back_populates="explorer_sessions")
    user: Mapped[User] = relationship(back_populates="explorer_sessions")

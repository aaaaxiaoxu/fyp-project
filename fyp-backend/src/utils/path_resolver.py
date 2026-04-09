from __future__ import annotations

from pathlib import Path, PurePath

from ..settings import settings


def upload_root() -> Path:
    return Path(settings.UPLOAD_FOLDER).resolve()


def resolve_upload_path(relative_path: str | Path) -> Path:
    return _resolve_within(upload_root(), *_safe_relative_parts(relative_path))


def as_upload_relative_path(path: str | Path) -> str:
    root = upload_root()
    candidate = Path(path)

    if candidate.is_absolute():
        resolved = candidate.resolve(strict=False)
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"path must be under upload root: {resolved}") from exc

    return PurePath(*_safe_relative_parts(path)).as_posix()


def project_path(project_id: str, *parts: str) -> Path:
    return _resolve_within(upload_root(), "projects", _safe_segment(project_id, "project_id"), *_safe_segments(parts))


def project_relative_path(project_id: str, *parts: str) -> str:
    return as_upload_relative_path(project_path(project_id, *parts))


def project_dir(project_id: str) -> Path:
    return project_path(project_id)


def project_original_dir(project_id: str) -> Path:
    return project_path(project_id, "original")


def project_original_file_path(project_id: str, filename: str) -> Path:
    return project_path(project_id, "original", _safe_segment(filename, "filename"))


def project_extracted_text_path(project_id: str) -> Path:
    return project_path(project_id, "extracted_text.txt")


def project_ontology_path(project_id: str) -> Path:
    return project_path(project_id, "ontology.json")


def project_graph_data_path(project_id: str) -> Path:
    return project_path(project_id, "graph_data.json")


def simulation_path(simulation_id: str, *parts: str) -> Path:
    return _resolve_within(
        upload_root(),
        "simulations",
        _safe_segment(simulation_id, "simulation_id"),
        *_safe_segments(parts),
    )


def simulation_relative_path(simulation_id: str, *parts: str) -> str:
    return as_upload_relative_path(simulation_path(simulation_id, *parts))


def simulation_dir(simulation_id: str) -> Path:
    return simulation_path(simulation_id)


def simulation_profiles_dir(simulation_id: str) -> Path:
    return simulation_path(simulation_id, "profiles")


def simulation_profiles_path(simulation_id: str) -> Path:
    return simulation_path(simulation_id, "profiles", "profiles.json")


def simulation_reddit_profiles_path(simulation_id: str) -> Path:
    return simulation_path(simulation_id, "profiles", "reddit_profiles.json")


def simulation_twitter_profiles_path(simulation_id: str) -> Path:
    return simulation_path(simulation_id, "profiles", "twitter_profiles.csv")


def simulation_config_path(simulation_id: str) -> Path:
    return simulation_path(simulation_id, "simulation_config.json")


def simulation_run_state_path(simulation_id: str) -> Path:
    return simulation_path(simulation_id, "run_state.json")


def simulation_env_status_path(simulation_id: str) -> Path:
    return simulation_path(simulation_id, "env_status.json")


def simulation_log_path(simulation_id: str) -> Path:
    return simulation_path(simulation_id, "simulation.log")


def simulation_ipc_commands_dir(simulation_id: str) -> Path:
    return simulation_path(simulation_id, "ipc_commands")


def simulation_ipc_responses_dir(simulation_id: str) -> Path:
    return simulation_path(simulation_id, "ipc_responses")


def simulation_twitter_actions_path(simulation_id: str) -> Path:
    return simulation_path(simulation_id, "twitter", "actions.jsonl")


def simulation_reddit_actions_path(simulation_id: str) -> Path:
    return simulation_path(simulation_id, "reddit", "actions.jsonl")


def simulation_twitter_database_path(simulation_id: str) -> Path:
    return simulation_path(simulation_id, "twitter_simulation.db")


def simulation_reddit_database_path(simulation_id: str) -> Path:
    return simulation_path(simulation_id, "reddit_simulation.db")


def explorer_path(simulation_id: str, *parts: str) -> Path:
    return _resolve_within(
        upload_root(),
        "explorer",
        _safe_segment(simulation_id, "simulation_id"),
        *_safe_segments(parts),
    )


def explorer_relative_path(simulation_id: str, *parts: str) -> str:
    return as_upload_relative_path(explorer_path(simulation_id, *parts))


def explorer_dir(simulation_id: str) -> Path:
    return explorer_path(simulation_id)


def explorer_sessions_dir(simulation_id: str) -> Path:
    return explorer_path(simulation_id, "sessions")


def explorer_session_log_path(simulation_id: str, session_id: str) -> Path:
    filename = f"{_safe_segment(session_id, 'session_id')}.jsonl"
    return explorer_path(simulation_id, "sessions", filename)


def explorer_console_dir(simulation_id: str) -> Path:
    return explorer_path(simulation_id, "console")


def explorer_console_log_path(simulation_id: str, session_id: str) -> Path:
    filename = f"{_safe_segment(session_id, 'session_id')}.log"
    return explorer_path(simulation_id, "console", filename)


def ensure_directory(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def ensure_parent_directory(path: str | Path) -> Path:
    candidate = Path(path)
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate.parent


def _resolve_within(root: Path, *parts: str) -> Path:
    path = root.joinpath(*parts).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes upload root: {path}") from exc
    return path


def _safe_segment(value: str, field_name: str) -> str:
    raw = value.strip()
    if not raw:
        raise ValueError(f"{field_name} cannot be empty")

    pure = PurePath(raw)
    if pure.is_absolute() or len(pure.parts) != 1 or pure.parts[0] in {".", ".."}:
        raise ValueError(f"invalid {field_name}: {value!r}")

    return pure.parts[0]


def _safe_segments(parts: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_safe_segment(part, f"path segment {index}") for index, part in enumerate(parts, start=1))


def _safe_relative_parts(relative_path: str | Path) -> tuple[str, ...]:
    pure = PurePath(str(relative_path))
    if pure.is_absolute():
        raise ValueError(f"expected relative upload path, got absolute path: {relative_path}")

    parts = tuple(part for part in pure.parts if part not in {"", "."})
    if not parts:
        raise ValueError("relative upload path cannot be empty")
    if any(part == ".." for part in parts):
        raise ValueError(f"relative upload path cannot escape upload root: {relative_path}")

    return parts

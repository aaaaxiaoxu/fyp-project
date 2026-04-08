from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    APP_BASE_URL: str = "http://127.0.0.1:8000"

    DATABASE_URL: str = ""
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3307
    MYSQL_DATABASE: str = "fyp_app"
    MYSQL_USER: str = "fyp_user"
    MYSQL_PASSWORD: str = "fyp_password"
    DB_ECHO: bool = False

    JWT_SECRET_KEY: str = "change_me"
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 20
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    ACCESS_COOKIE_NAME: str = "access_token"
    REFRESH_COOKIE_NAME: str = "refresh_token"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_TLS: bool = True

    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-chat"
    TEMPERATURE: float = 0.2
    MAX_TOKENS: int = 1400
    TIMEOUT_S: int = 60
    MAX_RETRIES: int = 5
    RETRY_BACKOFF_S: float = 1.5

    ZEP_API_KEY: str = ""
    ZEP_BASE_URL: str = ""

    NEO4J_URI: str = "neo4j://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_DATABASE: str = "neo4j"

    UPLOAD_ROOT: Path = PROJECT_ROOT / "uploads"
    LOG_DIR: Path = PROJECT_ROOT / "logs"
    MAX_UPLOAD_FILE_SIZE_MB: int = 50
    ALLOWED_UPLOAD_EXTENSIONS: tuple[str, ...] = ("pdf", "md", "markdown", "txt")

    DEFAULT_CHUNK_SIZE: int = 500
    DEFAULT_CHUNK_OVERLAP: int = 50

    OASIS_DEFAULT_MAX_ROUNDS: int = 10
    OASIS_TWITTER_ACTIONS: tuple[str, ...] = (
        "CREATE_POST",
        "LIKE_POST",
        "REPOST",
        "FOLLOW",
        "DO_NOTHING",
        "QUOTE_POST",
    )
    OASIS_REDDIT_ACTIONS: tuple[str, ...] = (
        "LIKE_POST",
        "DISLIKE_POST",
        "CREATE_POST",
        "CREATE_COMMENT",
        "LIKE_COMMENT",
        "DISLIKE_COMMENT",
        "SEARCH_POSTS",
        "SEARCH_USER",
        "TREND",
        "REFRESH",
        "DO_NOTHING",
        "FOLLOW",
        "MUTE",
    )

    GRAPH_MAX_DEPTH: int = 3
    GRAPH_MAX_PATHS: int = 500
    GRAPH_MAX_SNIPPET_LEN: int = 300

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def MAX_CONTENT_LENGTH(self) -> int:
        return self.MAX_UPLOAD_FILE_SIZE_MB * 1024 * 1024

    @property
    def UPLOAD_FOLDER(self) -> str:
        return str(self._resolve_runtime_path(self.UPLOAD_ROOT))

    @property
    def PROJECTS_UPLOAD_DIR(self) -> Path:
        return self._resolve_runtime_path(self.UPLOAD_ROOT) / "projects"

    @property
    def SIMULATIONS_UPLOAD_DIR(self) -> Path:
        return self._resolve_runtime_path(self.UPLOAD_ROOT) / "simulations"

    @property
    def EXPLORER_UPLOAD_DIR(self) -> Path:
        return self._resolve_runtime_path(self.UPLOAD_ROOT) / "explorer"

    @property
    def OASIS_SIMULATION_DATA_DIR(self) -> str:
        return str(self.SIMULATIONS_UPLOAD_DIR)

    @property
    def RESOLVED_LOG_DIR(self) -> Path:
        return self._resolve_runtime_path(self.LOG_DIR)

    def _resolve_runtime_path(self, path: Path) -> Path:
        return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()

    def required_runtime_errors(self) -> list[str]:
        errors: list[str] = []

        if not self.LLM_API_KEY.strip():
            errors.append("LLM_API_KEY 未配置")
        if not self.ZEP_API_KEY.strip():
            errors.append("ZEP_API_KEY 未配置")

        return errors

    def validate_runtime(self) -> None:
        errors = self.required_runtime_errors()
        if errors:
            bullet_list = "\n".join(f"- {item}" for item in errors)
            raise RuntimeError(f"启动失败，缺少关键配置：\n{bullet_list}")

    def ensure_runtime_dirs(self) -> None:
        self._resolve_runtime_path(self.UPLOAD_ROOT).mkdir(parents=True, exist_ok=True)

        for path in (
            self.PROJECTS_UPLOAD_DIR,
            self.SIMULATIONS_UPLOAD_DIR,
            self.EXPLORER_UPLOAD_DIR,
            self.RESOLVED_LOG_DIR,
        ):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()

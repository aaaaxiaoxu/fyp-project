from __future__ import annotations

from urllib.parse import quote_plus

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .settings import settings


class Base(DeclarativeBase):
    pass


def _database_url() -> str:
    if settings.DATABASE_URL:
        return settings.DATABASE_URL

    user = quote_plus(settings.MYSQL_USER)
    password = quote_plus(settings.MYSQL_PASSWORD)
    database = quote_plus(settings.MYSQL_DATABASE)
    return (
        f"mysql+asyncmy://{user}:{password}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{database}?charset=utf8mb4"
    )


engine = create_async_engine(
    _database_url(),
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
)
SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_db():
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from . import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_drop_legacy_user_schema)


def _drop_legacy_user_schema(sync_conn) -> None:
    if sync_conn.dialect.name not in {"mysql", "mariadb"}:
        return

    inspector = inspect(sync_conn)
    table_names = set(inspector.get_table_names())
    quote = sync_conn.dialect.identifier_preparer.quote

    for table_name in ("projects", "simulations", "tasks", "explorer_sessions"):
        if table_name not in table_names:
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "user_id" not in columns:
            continue

        for foreign_key in inspector.get_foreign_keys(table_name):
            constrained_columns = set(foreign_key.get("constrained_columns") or [])
            foreign_key_name = foreign_key.get("name")
            if "user_id" in constrained_columns and foreign_key_name:
                sync_conn.execute(
                    text(
                        f"ALTER TABLE {quote(table_name)} "
                        f"DROP FOREIGN KEY {quote(foreign_key_name)}"
                    )
                )
        sync_conn.execute(text(f"ALTER TABLE {quote(table_name)} DROP COLUMN {quote('user_id')}"))

    for table_name in ("refresh_tokens", "email_verification_tokens", "users"):
        if table_name in table_names:
            sync_conn.execute(text(f"DROP TABLE IF EXISTS {quote(table_name)}"))

from __future__ import annotations

from urllib.parse import quote_plus
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


async def init_db() -> None:
    from . import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

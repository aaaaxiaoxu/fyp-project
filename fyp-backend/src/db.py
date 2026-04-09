from __future__ import annotations

from urllib.parse import quote_plus
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .settings import settings

SYSTEM_OWNER_ID = "00000000000000000000000000000000"
SYSTEM_OWNER_EMAIL = "system@local"


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
    async with SessionLocal() as session:
        owner = await session.get(models.User, SYSTEM_OWNER_ID)
        if owner is None:
            session.add(
                models.User(
                    id=SYSTEM_OWNER_ID,
                    email=SYSTEM_OWNER_EMAIL,
                    password_hash="",
                    is_verified=True,
                    nickname="system",
                    avatar_url=None,
                )
            )
            await session.commit()

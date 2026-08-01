"""Async engine and session factories.

Only the factory is global. Every request or background persistence operation
creates and closes its own ``AsyncSession``.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./data/military_video_gen.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def _ensure_sqlite_directory(database_url: str) -> None:
    prefix = "sqlite+aiosqlite:///"
    if not database_url.startswith(prefix):
        return
    path = database_url.removeprefix(prefix)
    if path and path != ":memory:":
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)


def create_engine(database_url: str = DATABASE_URL) -> AsyncEngine:
    _ensure_sqlite_directory(database_url)
    engine = create_async_engine(database_url, pool_pre_ping=True)
    if database_url.startswith("sqlite"):
        @event.listens_for(engine.sync_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


def create_session_factory(
    database_url: str = DATABASE_URL,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        create_engine(database_url),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


engine = create_engine()
AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    await engine.dispose()

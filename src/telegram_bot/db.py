"""Async SQLAlchemy engine and session management."""

from __future__ import annotations

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

from .models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def database_path() -> Path:
    configured_path = os.getenv("SHOPPING_NOTES_DB", "shopping_notes.db").strip()
    return Path(configured_path or "shopping_notes.db").expanduser()


def database_url() -> str:
    path = database_path()
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+aiosqlite:///{path.resolve().as_posix()}"


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            database_url(),
            connect_args={"timeout": 5},
            pool_pre_ping=True,
        )

        @event.listens_for(_engine.sync_engine, "connect")
        def _configure_sqlite(connection, _record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("PRAGMA busy_timeout = 5000")
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.close()

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), expire_on_commit=False
        )
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Provide a session with commit/rollback handling."""
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def initialize_database() -> None:
    """Create missing tables from ORM metadata for local/dev startup."""
    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


def migrate_database() -> None:
    """Apply Alembic migrations before the bot starts polling."""
    from alembic.config import Config

    from alembic import command

    config_path = Path(os.getenv("ALEMBIC_CONFIG", "alembic.ini"))
    if not config_path.is_absolute() and not config_path.exists():
        config_path = Path(__file__).resolve().parents[2] / config_path
    command.upgrade(Config(str(config_path)), "head")

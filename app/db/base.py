"""SQLAlchemy base metadata and async engine setup."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


@lru_cache
def get_engine():
    """Create and cache the async SQLAlchemy engine with conservative timeout guards."""

    from app.config import get_settings

    settings = get_settings()
    return create_async_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_POOL_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
        connect_args={
            "timeout": settings.DB_CONNECT_TIMEOUT_SECONDS,
            "command_timeout": settings.DB_COMMAND_TIMEOUT_SECONDS,
            "server_settings": {
                "statement_timeout": str(settings.DB_STATEMENT_TIMEOUT_MS),
                "lock_timeout": str(settings.DB_LOCK_TIMEOUT_MS),
            },
        },
    )


def get_async_session_factory(*, bind: Any | None = None):
    if bind is None:
        bind = get_engine()
    return async_sessionmaker(bind=bind, class_=AsyncSession, expire_on_commit=False)


async def check_database_readiness() -> None:
    """Verify the configured database accepts a lightweight readiness query."""

    engine = get_engine()
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    finally:
        await engine.dispose()
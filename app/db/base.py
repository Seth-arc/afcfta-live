"""SQLAlchemy base metadata and async engine setup."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

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


def classify_pool_pressure(checked_out: int, pool_size: int) -> Literal["ok", "elevated", "saturated"]:
    """Classify connection pool pressure from raw checkout counts.

    Uses ``pool_size`` (the configured steady-state capacity) as the denominator
    so pressure is signalled before overflow connections are needed.

    - ``ok``        checked_out / pool_size < 0.75
    - ``elevated``  0.75 <= ratio < 0.95
    - ``saturated`` ratio >= 0.95
    """
    if pool_size <= 0:
        return "ok"
    ratio = checked_out / pool_size
    if ratio >= 0.95:
        return "saturated"
    if ratio >= 0.75:
        return "elevated"
    return "ok"


def get_pool_stats() -> dict[str, object]:
    """Return current connection pool counters and a pressure classification.

    Sources counts directly from SQLAlchemy's QueuePool without any new
    dependencies.  Falls back to zero-counts for pool types that do not
    implement the standard counter interface (e.g. NullPool used in tests).
    """
    pool = get_engine().pool
    try:
        checked_out: int = pool.checkedout()
        pool_size: int = pool.size()
        overflow: int = max(pool.overflow(), 0)
        checked_in: int = pool.checkedin()
    except AttributeError:
        return {
            "checked_out": 0,
            "pool_size": 0,
            "overflow": 0,
            "checked_in": 0,
            "pool_pressure": "ok",
        }
    return {
        "checked_out": checked_out,
        "pool_size": pool_size,
        "overflow": overflow,
        "checked_in": checked_in,
        "pool_pressure": classify_pool_pressure(checked_out, pool_size),
    }


async def check_database_readiness() -> None:
    """Verify the configured database accepts a lightweight readiness query."""

    engine = get_engine()
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    finally:
        await engine.dispose()
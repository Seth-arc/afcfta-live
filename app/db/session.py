"""Async session context management and FastAPI database dependency."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_async_session_factory


@asynccontextmanager
async def session_context() -> AsyncIterator[AsyncSession]:
    """Provide an async SQLAlchemy session context."""

    factory = get_async_session_factory()
    async with factory() as session:
        yield session


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield an async SQLAlchemy session for FastAPI dependencies."""

    async with session_context() as session:
        yield session
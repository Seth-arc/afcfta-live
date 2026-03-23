"""SQLAlchemy base metadata and async engine setup."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


def get_engine():
    from app.config import get_settings
    settings = get_settings()
    return create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)


def get_async_session_factory(*, bind: Any | None = None):
    if bind is None:
        bind = get_engine()
    return async_sessionmaker(bind=bind, class_=AsyncSession, expire_on_commit=False)
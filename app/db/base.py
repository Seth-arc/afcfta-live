"""SQLAlchemy base metadata and async engine setup."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


def get_engine():
    from app.config import get_settings
    settings = get_settings()
    return create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)


def get_async_session_factory():
    return async_sessionmaker(bind=get_engine(), class_=AsyncSession, expire_on_commit=False)
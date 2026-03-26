"""Async session context management and FastAPI database dependency."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EvaluationPersistenceError
from app.db.base import get_async_session_factory, get_engine

ASSESSMENT_ISOLATION_LEVEL = "REPEATABLE READ"
logger = logging.getLogger(__name__)


@asynccontextmanager
async def session_context() -> AsyncIterator[AsyncSession]:
    """Provide an async SQLAlchemy session context."""

    factory = get_async_session_factory()
    async with factory() as session:
        yield session


@asynccontextmanager
async def assessment_session_context() -> AsyncIterator[AsyncSession]:
    """Provide one assessment-scoped session under REPEATABLE READ isolation."""

    engine = get_engine()
    async with engine.connect() as connection:
        connection = await connection.execution_options(
            isolation_level=ASSESSMENT_ISOLATION_LEVEL
        )
        factory = get_async_session_factory(bind=connection)
        async with factory() as session:
            session_body_completed = False
            try:
                async with session.begin():
                    yield session
                    session_body_completed = True
            except EvaluationPersistenceError:
                raise
            except Exception as exc:
                if not session_body_completed:
                    raise
                logger.error(
                    "assessment_transaction_close_failed",
                    exc_info=True,
                    extra={
                        "structured_data": {
                            "event": "assessment_transaction_close_failed",
                            "boundary": "assessment_transaction_close",
                            "reason": "assessment_transaction_close_failed",
                        }
                    },
                )
                raise EvaluationPersistenceError(
                    "Assessment transaction failed while closing the replayable snapshot",
                    detail={"reason": "assessment_transaction_close_failed"},
                ) from exc


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield an async SQLAlchemy session for FastAPI dependencies."""

    async with session_context() as session:
        try:
            yield session
            if session.in_transaction():
                await session.commit()
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise


async def get_assessment_db() -> AsyncIterator[AsyncSession]:
    """Yield an assessment-scoped session bound to a repeatable-read transaction."""

    async with assessment_session_context() as session:
        yield session

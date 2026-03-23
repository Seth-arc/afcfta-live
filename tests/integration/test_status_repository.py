"""Integration tests for status assertion and transition clause lookups."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from datetime import date
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_async_session_factory
from app.repositories.status_repository import StatusRepository


pytestmark = pytest.mark.integration

AS_OF_DATE = date.today()


@pytest_asyncio.fixture
async def status_repository() -> AsyncIterator[tuple[AsyncSession, StatusRepository]]:
    """Provide a live async session plus the repository under test."""

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        yield session, StatusRepository(session)


async def _fetch_one(
    session: AsyncSession,
    query: str,
    params: dict[str, Any] | None = None,
) -> Mapping[str, Any] | None:
    """Return the first row mapping for a SQL query."""

    result = await session.execute(text(query), params or {})
    return result.mappings().first()


async def _fetch_all(
    session: AsyncSession,
    query: str,
    params: dict[str, Any] | None = None,
) -> list[Mapping[str, Any]]:
    """Return all row mappings for a SQL query."""

    result = await session.execute(text(query), params or {})
    return list(result.mappings().all())


def _require_candidate(
    candidate: Mapping[str, Any] | None,
    reason: str,
) -> Mapping[str, Any]:
    """Skip when the live status dataset lacks the needed shape."""

    if candidate is None:
        pytest.skip(reason)
    return candidate


@pytest.mark.asyncio
async def test_get_status_returns_current_corridor_status_row(
    status_repository: tuple[AsyncSession, StatusRepository],
) -> None:
    """The repository should return the active corridor status assertion."""

    session, repository = status_repository
    candidate = _require_candidate(
        await _fetch_one(
            session,
            """
            SELECT sa.entity_type, sa.entity_key
            FROM status_assertion sa
            WHERE sa.entity_type = 'corridor'
              AND (sa.effective_from IS NULL OR sa.effective_from <= :as_of_date)
              AND (sa.effective_to IS NULL OR sa.effective_to >= :as_of_date)
            ORDER BY sa.confidence_score DESC, sa.updated_at DESC
            LIMIT 1
            """,
            {"as_of_date": AS_OF_DATE},
        ),
        "No active corridor status assertion is loaded in the test database.",
    )
    expected = await _fetch_one(
        session,
        """
        SELECT
          sa.status_assertion_id,
          sa.entity_type,
          sa.entity_key,
          sa.status_type,
          sa.status_text_verbatim,
          sa.effective_from,
          sa.effective_to,
          sa.page_ref,
          sa.clause_ref,
          sa.confidence_score,
          sa.source_id,
          sa.created_at,
          sa.updated_at
        FROM status_assertion sa
        WHERE sa.entity_type = :entity_type
          AND sa.entity_key = :entity_key
          AND (sa.effective_from IS NULL OR sa.effective_from <= :as_of_date)
          AND (sa.effective_to IS NULL OR sa.effective_to >= :as_of_date)
        ORDER BY sa.confidence_score DESC, sa.updated_at DESC
        LIMIT 1
        """,
        {
            "entity_type": candidate["entity_type"],
            "entity_key": candidate["entity_key"],
            "as_of_date": AS_OF_DATE,
        },
    )

    resolved = await repository.get_status(
        str(candidate["entity_type"]),
        str(candidate["entity_key"]),
    )

    assert expected is not None
    assert resolved is not None
    assert str(resolved["status_assertion_id"]) == str(expected["status_assertion_id"])
    assert str(resolved["status_type"]) == str(expected["status_type"])
    assert str(resolved["entity_type"]) == "corridor"


@pytest.mark.asyncio
async def test_get_status_returns_current_psr_rule_status_row(
    status_repository: tuple[AsyncSession, StatusRepository],
) -> None:
    """The repository should return the active PSR rule status assertion."""

    session, repository = status_repository
    candidate = _require_candidate(
        await _fetch_one(
            session,
            """
            SELECT sa.entity_type, sa.entity_key
            FROM status_assertion sa
            WHERE sa.entity_type = 'psr_rule'
              AND (sa.effective_from IS NULL OR sa.effective_from <= :as_of_date)
              AND (sa.effective_to IS NULL OR sa.effective_to >= :as_of_date)
            ORDER BY sa.confidence_score DESC, sa.updated_at DESC
            LIMIT 1
            """,
            {"as_of_date": AS_OF_DATE},
        ),
        "No active psr_rule status assertion is loaded in the test database.",
    )
    expected = await _fetch_one(
        session,
        """
        SELECT
          sa.status_assertion_id,
          sa.entity_type,
          sa.entity_key,
          sa.status_type,
          sa.status_text_verbatim,
          sa.effective_from,
          sa.effective_to,
          sa.page_ref,
          sa.clause_ref,
          sa.confidence_score,
          sa.source_id,
          sa.created_at,
          sa.updated_at
        FROM status_assertion sa
        WHERE sa.entity_type = :entity_type
          AND sa.entity_key = :entity_key
          AND (sa.effective_from IS NULL OR sa.effective_from <= :as_of_date)
          AND (sa.effective_to IS NULL OR sa.effective_to >= :as_of_date)
        ORDER BY sa.confidence_score DESC, sa.updated_at DESC
        LIMIT 1
        """,
        {
            "entity_type": candidate["entity_type"],
            "entity_key": candidate["entity_key"],
            "as_of_date": AS_OF_DATE,
        },
    )

    resolved = await repository.get_status(
        str(candidate["entity_type"]),
        str(candidate["entity_key"]),
    )

    assert expected is not None
    assert resolved is not None
    assert str(resolved["status_assertion_id"]) == str(expected["status_assertion_id"])
    assert str(resolved["status_type"]) == str(expected["status_type"])
    assert str(resolved["entity_type"]) == "psr_rule"


@pytest.mark.asyncio
async def test_get_status_ignores_out_of_window_assertions(
    status_repository: tuple[AsyncSession, StatusRepository],
) -> None:
    """Entities with only expired or future assertions should resolve to no current status."""

    session, repository = status_repository
    candidate = _require_candidate(
        await _fetch_one(
            session,
            """
            SELECT sa.entity_type, sa.entity_key
            FROM status_assertion sa
            GROUP BY sa.entity_type, sa.entity_key
            HAVING COUNT(*) > 0
               AND NOT BOOL_OR(
                   (sa.effective_from IS NULL OR sa.effective_from <= :as_of_date)
                   AND (sa.effective_to IS NULL OR sa.effective_to >= :as_of_date)
               )
            ORDER BY sa.entity_type ASC, sa.entity_key ASC
            LIMIT 1
            """,
            {"as_of_date": AS_OF_DATE},
        ),
        "No entity with only out-of-window status assertions is loaded in the test database.",
    )

    resolved = await repository.get_status(
        str(candidate["entity_type"]),
        str(candidate["entity_key"]),
    )

    assert resolved is None


@pytest.mark.asyncio
async def test_get_active_transitions_returns_only_current_rows_in_repository_order(
    status_repository: tuple[AsyncSession, StatusRepository],
) -> None:
    """Transition lookup should filter to current rows and preserve the SQL order."""

    session, repository = status_repository
    candidate = _require_candidate(
        await _fetch_one(
            session,
            """
            SELECT tc.entity_type, tc.entity_key
            FROM transition_clause tc
            WHERE (tc.start_date IS NULL OR tc.start_date <= :as_of_date)
              AND (tc.end_date IS NULL OR tc.end_date >= :as_of_date)
            GROUP BY tc.entity_type, tc.entity_key
            ORDER BY COUNT(*) DESC, tc.entity_type ASC, tc.entity_key ASC
            LIMIT 1
            """,
            {"as_of_date": AS_OF_DATE},
        ),
        "No active transition clause is loaded in the test database.",
    )
    expected = await _fetch_all(
        session,
        """
        SELECT
          tc.transition_id,
          tc.entity_type,
          tc.entity_key,
          tc.transition_type,
          tc.transition_text_verbatim,
          tc.start_date,
          tc.end_date,
          tc.review_trigger,
          tc.page_ref,
          tc.source_id,
          tc.created_at,
          tc.updated_at
        FROM transition_clause tc
        WHERE tc.entity_type = :entity_type
          AND tc.entity_key = :entity_key
          AND (tc.start_date IS NULL OR tc.start_date <= :as_of_date)
          AND (tc.end_date IS NULL OR tc.end_date >= :as_of_date)
        ORDER BY
          COALESCE(tc.end_date, DATE '9999-12-31') ASC,
          tc.start_date DESC,
          tc.updated_at DESC
        """,
        {
            "entity_type": candidate["entity_type"],
            "entity_key": candidate["entity_key"],
            "as_of_date": AS_OF_DATE,
        },
    )

    resolved = await repository.get_active_transitions(
        str(candidate["entity_type"]),
        str(candidate["entity_key"]),
    )

    assert [str(row["transition_id"]) for row in resolved] == [
        str(row["transition_id"]) for row in expected
    ]
    assert [str(row["transition_type"]) for row in resolved] == [
        str(row["transition_type"]) for row in expected
    ]


@pytest.mark.asyncio
async def test_get_active_transitions_returns_empty_for_missing_entity(
    status_repository: tuple[AsyncSession, StatusRepository],
) -> None:
    """A missing entity key should return an empty transition list."""

    _, repository = status_repository

    resolved = await repository.get_active_transitions(
        "corridor",
        "CORRIDOR:ZZZ:ZZZ:000000",
    )

    assert resolved == []
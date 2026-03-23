"""Integration tests for corridor tariff resolution queries."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from datetime import date
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_async_session_factory
from app.repositories.tariffs_repository import TariffsRepository


pytestmark = pytest.mark.integration

DEFAULT_YEAR = 2025


@pytest_asyncio.fixture
async def tariffs_repository() -> AsyncIterator[tuple[AsyncSession, TariffsRepository]]:
    """Provide a live async session plus the repository under test."""

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        yield session, TariffsRepository(session)


async def _fetch_one(
    session: AsyncSession,
    query: str,
    params: dict[str, Any] | None = None,
) -> Mapping[str, Any] | None:
    """Return the first row mapping for a SQL query."""

    result = await session.execute(text(query), params or {})
    return result.mappings().first()


def _require_candidate(
    candidate: Mapping[str, Any] | None,
    reason: str,
) -> Mapping[str, Any]:
    """Skip when the live tariff dataset lacks the needed test shape."""

    if candidate is None:
        pytest.skip(reason)
    return candidate


async def _expected_tariff_bundle(
    session: AsyncSession,
    *,
    exporter: str,
    importer: str,
    hs_version: str,
    hs6_code: str,
    year: int,
    prefix_match: bool,
) -> Mapping[str, Any] | None:
    """Mirror the tariff lookup query so repository output can be compared directly."""

    join_clause = (
        "hp.hs_version = tsh.hs_version AND hp.hs6_code = LEFT(tsl.hs_code, 6)"
        if prefix_match
        else "hp.hs_version = tsh.hs_version AND hp.hs6_code = tsl.hs_code"
    )
    schedule_statement = text(
        f"""
        SELECT
          tsh.schedule_id,
          tsh.source_id AS schedule_source_id,
          tsh.importing_state,
          tsh.exporting_scope,
          tsh.schedule_status,
          tsh.publication_date,
          tsh.effective_date,
          tsh.expiry_date,
          tsh.hs_version,
          tsh.category_system,
          tsh.notes,
          tsl.schedule_line_id,
          hp.hs6_id,
          hp.hs6_code,
          hp.hs6_display,
          tsl.product_description,
          tsl.tariff_category,
          tsl.mfn_base_rate,
          tsl.base_year,
          tsl.target_rate,
          tsl.target_year,
          tsl.staging_type,
          tsl.page_ref AS line_page_ref,
          tsl.table_ref,
          tsl.row_ref,
          tsl.hs_code AS line_hs_code
        FROM tariff_schedule_header tsh
        JOIN tariff_schedule_line tsl
          ON tsl.schedule_id = tsh.schedule_id
        JOIN hs6_product hp
          ON {join_clause}
        WHERE tsh.importing_state = :importer
          AND tsh.exporting_scope = :exporter
          AND hp.hs_version = :hs_version
          AND hp.hs6_code = :hs6_code
          AND (tsh.effective_date IS NULL OR tsh.effective_date <= :year_end)
          AND (tsh.expiry_date IS NULL OR tsh.expiry_date >= :year_start)
        ORDER BY
          CASE tsh.schedule_status
            WHEN 'gazetted' THEN 1
            WHEN 'official' THEN 2
            WHEN 'provisional' THEN 3
            ELSE 9
          END,
          tsh.updated_at DESC
        LIMIT 1
        """
    )
    schedule_row = (
        await session.execute(
            schedule_statement,
            {
                "exporter": exporter,
                "importer": importer,
                "hs_version": hs_version,
                "hs6_code": hs6_code,
                "year_start": date(year, 1, 1),
                "year_end": date(year, 12, 31),
            },
        )
    ).mappings().first()
    if schedule_row is None:
        return None

    rate_statement = text(
        """
        SELECT
          tsry.year_rate_id,
          tsry.calendar_year AS resolved_rate_year,
          tsry.preferential_rate,
          tsry.rate_status,
          tsry.source_id AS rate_source_id,
          tsry.page_ref AS rate_page_ref
        FROM tariff_schedule_rate_by_year tsry
        WHERE tsry.schedule_line_id = :schedule_line_id
          AND tsry.calendar_year <= :year
        ORDER BY
          CASE WHEN tsry.calendar_year = :year THEN 0 ELSE 1 END,
          tsry.calendar_year DESC
        LIMIT 1
        """
    )
    rate_row = (
        await session.execute(
            rate_statement,
            {"schedule_line_id": schedule_row["schedule_line_id"], "year": year},
        )
    ).mappings().first()

    payload = dict(schedule_row)
    payload["requested_year"] = year
    payload["used_fallback_rate"] = False
    if rate_row is None:
        payload.update(
            {
                "year_rate_id": None,
                "resolved_rate_year": None,
                "preferential_rate": None,
                "rate_status": None,
                "rate_source_id": None,
                "rate_page_ref": None,
            }
        )
        return payload

    payload.update(rate_row)
    payload["used_fallback_rate"] = rate_row["resolved_rate_year"] != year
    return payload


@pytest.mark.asyncio
async def test_get_tariff_matches_single_deeper_line_by_hs6_prefix(
    tariffs_repository: tuple[AsyncSession, TariffsRepository],
) -> None:
    """HS6 requests should resolve when the schedule line is stored at deeper digit depth."""

    session, repository = tariffs_repository
    candidate = _require_candidate(
        await _fetch_one(
            session,
            """
            SELECT
              tsh.exporting_scope AS exporter,
              tsh.importing_state AS importer,
              hp.hs_version,
              hp.hs6_code
            FROM tariff_schedule_header tsh
            JOIN tariff_schedule_line tsl ON tsl.schedule_id = tsh.schedule_id
            JOIN hs6_product hp
              ON hp.hs_version = tsh.hs_version
             AND hp.hs6_code = LEFT(tsl.hs_code, 6)
            JOIN tariff_schedule_rate_by_year tsry
              ON tsry.schedule_line_id = tsl.schedule_line_id
             AND tsry.calendar_year = :year
            WHERE LENGTH(tsl.hs_code) > 6
              AND (tsh.effective_date IS NULL OR tsh.effective_date <= :year_end)
              AND (tsh.expiry_date IS NULL OR tsh.expiry_date >= :year_start)
            GROUP BY tsh.exporting_scope, tsh.importing_state, hp.hs_version, hp.hs6_code
            HAVING COUNT(*) = 1
            ORDER BY hp.hs6_code ASC
            LIMIT 1
            """,
            {
                "year": DEFAULT_YEAR,
                "year_start": date(DEFAULT_YEAR, 1, 1),
                "year_end": date(DEFAULT_YEAR, 12, 31),
            },
        ),
        "No live tariff-backed HS6 candidate with a single deeper tariff line is loaded in the test database.",
    )
    expected = await _expected_tariff_bundle(
        session,
        exporter=str(candidate["exporter"]),
        importer=str(candidate["importer"]),
        hs_version=str(candidate["hs_version"]),
        hs6_code=str(candidate["hs6_code"]),
        year=DEFAULT_YEAR,
        prefix_match=True,
    )

    resolved = await repository.get_tariff(
        exporter=str(candidate["exporter"]),
        importer=str(candidate["importer"]),
        hs_version=str(candidate["hs_version"]),
        hs6_code=str(candidate["hs6_code"]),
        year=DEFAULT_YEAR,
    )

    assert expected is not None
    assert resolved is not None
    assert str(resolved["schedule_line_id"]) == str(expected["schedule_line_id"])
    assert str(resolved["hs6_code"]) == str(expected["hs6_code"])
    assert resolved["resolved_rate_year"] == expected["resolved_rate_year"]
    assert resolved["preferential_rate"] == expected["preferential_rate"]


@pytest.mark.asyncio
async def test_get_tariff_returns_exact_requested_year_rate_when_available(
    tariffs_repository: tuple[AsyncSession, TariffsRepository],
) -> None:
    """The repository should return the exact year-specific preferential rate when present."""

    session, repository = tariffs_repository
    candidate = _require_candidate(
        await _fetch_one(
            session,
            """
            SELECT DISTINCT
              tsh.exporting_scope AS exporter,
              tsh.importing_state AS importer,
              hp.hs_version,
              hp.hs6_code
            FROM tariff_schedule_header tsh
            JOIN tariff_schedule_line tsl ON tsl.schedule_id = tsh.schedule_id
            JOIN hs6_product hp
              ON hp.hs_version = tsh.hs_version
             AND hp.hs6_code = LEFT(tsl.hs_code, 6)
            JOIN tariff_schedule_rate_by_year tsry
              ON tsry.schedule_line_id = tsl.schedule_line_id
            WHERE tsry.calendar_year = :year
              AND (tsh.effective_date IS NULL OR tsh.effective_date <= :year_end)
              AND (tsh.expiry_date IS NULL OR tsh.expiry_date >= :year_start)
            ORDER BY hp.hs6_code ASC, tsh.exporting_scope ASC, tsh.importing_state ASC
            LIMIT 1
            """,
            {
                "year": DEFAULT_YEAR,
                "year_start": date(DEFAULT_YEAR, 1, 1),
                "year_end": date(DEFAULT_YEAR, 12, 31),
            },
        ),
        "No tariff-backed candidate with an exact requested-year rate is loaded in the test database.",
    )
    expected = await _expected_tariff_bundle(
        session,
        exporter=str(candidate["exporter"]),
        importer=str(candidate["importer"]),
        hs_version=str(candidate["hs_version"]),
        hs6_code=str(candidate["hs6_code"]),
        year=DEFAULT_YEAR,
        prefix_match=True,
    )

    resolved = await repository.get_tariff(
        exporter=str(candidate["exporter"]),
        importer=str(candidate["importer"]),
        hs_version=str(candidate["hs_version"]),
        hs6_code=str(candidate["hs6_code"]),
        year=DEFAULT_YEAR,
    )

    assert expected is not None
    assert resolved is not None
    assert resolved["resolved_rate_year"] == DEFAULT_YEAR
    assert resolved["used_fallback_rate"] is False
    assert str(resolved["schedule_id"]) == str(expected["schedule_id"])
    assert str(resolved["schedule_line_id"]) == str(expected["schedule_line_id"])
    assert resolved["mfn_base_rate"] == expected["mfn_base_rate"]
    assert resolved["preferential_rate"] == expected["preferential_rate"]


@pytest.mark.asyncio
async def test_get_tariff_falls_back_to_latest_prior_rate_when_requested_year_missing(
    tariffs_repository: tuple[AsyncSession, TariffsRepository],
) -> None:
    """When the exact year is absent, the latest prior year rate should be used."""

    session, repository = tariffs_repository
    candidate = _require_candidate(
        await _fetch_one(
            session,
            """
            WITH line_years AS (
                SELECT
                  tsh.exporting_scope AS exporter,
                  tsh.importing_state AS importer,
                  hp.hs_version,
                  hp.hs6_code,
                  tsl.schedule_line_id,
                                    MAX(tsry.calendar_year) AS fallback_year
                FROM tariff_schedule_header tsh
                JOIN tariff_schedule_line tsl ON tsl.schedule_id = tsh.schedule_id
                JOIN hs6_product hp
                  ON hp.hs_version = tsh.hs_version
                 AND hp.hs6_code = LEFT(tsl.hs_code, 6)
                JOIN tariff_schedule_rate_by_year tsry ON tsry.schedule_line_id = tsl.schedule_line_id
                WHERE tsh.expiry_date IS NULL
                GROUP BY tsh.exporting_scope, tsh.importing_state, hp.hs_version, hp.hs6_code, tsl.schedule_line_id
            )
            SELECT exporter, importer, hs_version, hs6_code, fallback_year, fallback_year + 1 AS requested_year
            FROM line_years
            WHERE NOT EXISTS (
                SELECT 1
                FROM tariff_schedule_rate_by_year future_rate
                WHERE future_rate.schedule_line_id = line_years.schedule_line_id
                  AND future_rate.calendar_year = line_years.fallback_year + 1
            )
            ORDER BY fallback_year DESC, hs6_code ASC
            LIMIT 1
            """,
        ),
        "No tariff-backed candidate with a missing requested year and an available prior-year fallback is loaded in the test database.",
    )
    requested_year = int(candidate["requested_year"])
    expected = await _expected_tariff_bundle(
        session,
        exporter=str(candidate["exporter"]),
        importer=str(candidate["importer"]),
        hs_version=str(candidate["hs_version"]),
        hs6_code=str(candidate["hs6_code"]),
        year=requested_year,
        prefix_match=True,
    )

    resolved = await repository.get_tariff(
        exporter=str(candidate["exporter"]),
        importer=str(candidate["importer"]),
        hs_version=str(candidate["hs_version"]),
        hs6_code=str(candidate["hs6_code"]),
        year=requested_year,
    )

    assert expected is not None
    assert resolved is not None
    assert resolved["resolved_rate_year"] == int(candidate["fallback_year"])
    assert resolved["resolved_rate_year"] < requested_year
    assert resolved["used_fallback_rate"] is True
    assert resolved["preferential_rate"] == expected["preferential_rate"]


@pytest.mark.asyncio
async def test_get_tariff_prefers_highest_priority_schedule_status(
    tariffs_repository: tuple[AsyncSession, TariffsRepository],
) -> None:
    """Gazetted schedules should beat official or provisional schedules for the same lookup."""

    session, repository = tariffs_repository
    candidate = _require_candidate(
        await _fetch_one(
            session,
            """
            SELECT
              tsh.exporting_scope AS exporter,
              tsh.importing_state AS importer,
              hp.hs_version,
              hp.hs6_code
            FROM tariff_schedule_header tsh
            JOIN tariff_schedule_line tsl ON tsl.schedule_id = tsh.schedule_id
            JOIN hs6_product hp
              ON hp.hs_version = tsh.hs_version
             AND hp.hs6_code = LEFT(tsl.hs_code, 6)
            JOIN tariff_schedule_rate_by_year tsry
              ON tsry.schedule_line_id = tsl.schedule_line_id
             AND tsry.calendar_year <= :year
            WHERE (tsh.effective_date IS NULL OR tsh.effective_date <= :year_end)
              AND (tsh.expiry_date IS NULL OR tsh.expiry_date >= :year_start)
            GROUP BY tsh.exporting_scope, tsh.importing_state, hp.hs_version, hp.hs6_code
            HAVING COUNT(DISTINCT tsh.schedule_status) > 1
               AND BOOL_OR(tsh.schedule_status::text IN ('gazetted', 'official', 'provisional'))
            ORDER BY hp.hs6_code ASC
            LIMIT 1
            """,
            {
                "year": DEFAULT_YEAR,
                "year_start": date(DEFAULT_YEAR, 1, 1),
                "year_end": date(DEFAULT_YEAR, 12, 31),
            },
        ),
        "No tariff-backed candidate with multiple active schedule statuses is loaded in the test database.",
    )
    expected = await _expected_tariff_bundle(
        session,
        exporter=str(candidate["exporter"]),
        importer=str(candidate["importer"]),
        hs_version=str(candidate["hs_version"]),
        hs6_code=str(candidate["hs6_code"]),
        year=DEFAULT_YEAR,
        prefix_match=True,
    )

    resolved = await repository.get_tariff(
        exporter=str(candidate["exporter"]),
        importer=str(candidate["importer"]),
        hs_version=str(candidate["hs_version"]),
        hs6_code=str(candidate["hs6_code"]),
        year=DEFAULT_YEAR,
    )

    assert expected is not None
    assert resolved is not None
    assert str(resolved["schedule_id"]) == str(expected["schedule_id"])
    assert str(resolved["schedule_status"]) == str(expected["schedule_status"])
    assert str(resolved["schedule_status"]) in {"gazetted", "official", "provisional"}


@pytest.mark.asyncio
async def test_get_tariff_returns_none_for_missing_corridor(
    tariffs_repository: tuple[AsyncSession, TariffsRepository],
) -> None:
    """The repository should not return a false-positive tariff for an absent corridor."""

    session, repository = tariffs_repository
    candidate = _require_candidate(
        await _fetch_one(
            session,
            """
            SELECT DISTINCT
              tsh.importing_state AS importer,
              hp.hs_version,
              hp.hs6_code
            FROM tariff_schedule_header tsh
            JOIN tariff_schedule_line tsl ON tsl.schedule_id = tsh.schedule_id
            JOIN hs6_product hp
              ON hp.hs_version = tsh.hs_version
             AND hp.hs6_code = LEFT(tsl.hs_code, 6)
            JOIN tariff_schedule_rate_by_year tsry
              ON tsry.schedule_line_id = tsl.schedule_line_id
             AND tsry.calendar_year <= :year
            ORDER BY hp.hs6_code ASC
            LIMIT 1
            """,
            {"year": DEFAULT_YEAR},
        ),
        "No tariff-backed candidate is loaded in the test database.",
    )

    resolved = await repository.get_tariff(
        exporter="ZZZ",
        importer=str(candidate["importer"]),
        hs_version=str(candidate["hs_version"]),
        hs6_code=str(candidate["hs6_code"]),
        year=DEFAULT_YEAR,
    )

    assert resolved is None
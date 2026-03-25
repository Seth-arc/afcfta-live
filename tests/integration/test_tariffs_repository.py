"""Integration tests for corridor tariff resolution queries."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    AuthorityTierEnum,
    RateStatusEnum,
    ScheduleStatusEnum,
    SourceTypeEnum,
    StagingTypeEnum,
    TariffCategoryEnum,
)
from app.db.base import get_async_session_factory
from app.db.models.hs import HS6Product
from app.db.models.sources import SourceRegistry
from app.db.models.tariffs import (
    TariffScheduleHeader,
    TariffScheduleLine,
    TariffScheduleRateByYear,
)
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


def _build_source(tag: str) -> SourceRegistry:
    """Create a minimal source row for seeded tariff fixtures."""

    checksum = uuid4().hex + uuid4().hex
    return SourceRegistry(
        title=f"Tariff fixture {tag}",
        short_title=f"TF-{tag}",
        source_group="pytest",
        source_type=SourceTypeEnum.TARIFF_SCHEDULE,
        authority_tier=AuthorityTierEnum.OFFICIAL_OPERATIONAL,
        issuing_body="pytest",
        jurisdiction_scope="test",
        publication_date=date(DEFAULT_YEAR, 1, 1),
        effective_date=date(DEFAULT_YEAR, 1, 1),
        status="current",
        language="en",
        hs_version="HS2017",
        file_path=f"tests/{tag}.csv",
        mime_type="text/csv",
        checksum_sha256=checksum,
    )


async def _seed_schedule_status_fixture(session: AsyncSession) -> dict[str, str]:
    """Insert two active schedules so status precedence can be asserted deterministically."""

    hs6_code = "990201"
    exporter = "TSTA"
    importer = "TSTB"
    product = HS6Product(
        hs_version="HS2017",
        hs6_code=hs6_code,
        hs6_display=f"{hs6_code} tariff fixture",
        chapter=hs6_code[:2],
        heading=hs6_code[:4],
        description="Synthetic tariff fixture",
        section="XXI",
        section_name="Miscellaneous",
    )
    gazetted_source = _build_source("tariff-gazetted")
    provisional_source = _build_source("tariff-provisional")
    session.add_all([product, gazetted_source, provisional_source])
    await session.flush()

    gazetted_header = TariffScheduleHeader(
        source_id=gazetted_source.source_id,
        importing_state=importer,
        exporting_scope=exporter,
        schedule_status=ScheduleStatusEnum.GAZETTED,
        publication_date=date(DEFAULT_YEAR, 1, 1),
        effective_date=date(DEFAULT_YEAR, 1, 1),
        hs_version="HS2017",
        category_system="pytest",
    )
    provisional_header = TariffScheduleHeader(
        source_id=provisional_source.source_id,
        importing_state=importer,
        exporting_scope=exporter,
        schedule_status=ScheduleStatusEnum.PROVISIONAL,
        publication_date=date(DEFAULT_YEAR, 1, 1),
        effective_date=date(DEFAULT_YEAR, 1, 1),
        hs_version="HS2017",
        category_system="pytest",
    )
    session.add_all([gazetted_header, provisional_header])
    await session.flush()

    gazetted_line = TariffScheduleLine(
        schedule_id=gazetted_header.schedule_id,
        hs_code=f"{hs6_code}00",
        product_description="Synthetic gazetted line",
        tariff_category=TariffCategoryEnum.LIBERALISED,
        mfn_base_rate=Decimal("15.0000"),
        base_year=DEFAULT_YEAR,
        target_rate=Decimal("0.0000"),
        target_year=DEFAULT_YEAR,
        staging_type=StagingTypeEnum.IMMEDIATE,
        row_ref="gazetted",
    )
    provisional_line = TariffScheduleLine(
        schedule_id=provisional_header.schedule_id,
        hs_code=f"{hs6_code}00",
        product_description="Synthetic provisional line",
        tariff_category=TariffCategoryEnum.LIBERALISED,
        mfn_base_rate=Decimal("15.0000"),
        base_year=DEFAULT_YEAR,
        target_rate=Decimal("5.0000"),
        target_year=DEFAULT_YEAR,
        staging_type=StagingTypeEnum.IMMEDIATE,
        row_ref="provisional",
    )
    session.add_all([gazetted_line, provisional_line])
    await session.flush()

    session.add_all(
        [
            TariffScheduleRateByYear(
                schedule_line_id=gazetted_line.schedule_line_id,
                calendar_year=DEFAULT_YEAR,
                preferential_rate=Decimal("0.0000"),
                rate_status=RateStatusEnum.IN_FORCE,
                source_id=gazetted_source.source_id,
            ),
            TariffScheduleRateByYear(
                schedule_line_id=provisional_line.schedule_line_id,
                calendar_year=DEFAULT_YEAR,
                preferential_rate=Decimal("5.0000"),
                rate_status=RateStatusEnum.IN_FORCE,
                source_id=provisional_source.source_id,
            ),
        ]
    )
    await session.flush()
    return {
        "exporter": exporter,
        "importer": importer,
        "hs_version": "HS2017",
        "hs6_code": hs6_code,
    }


async def _seed_mid_year_effectivity_fixture(session: AsyncSession) -> dict[str, str]:
    """Insert one schedule that starts mid-year for exact snapshot-date assertions."""

    hs6_code = "990202"
    exporter = "TSTC"
    importer = "TSTD"
    product = HS6Product(
        hs_version="HS2017",
        hs6_code=hs6_code,
        hs6_display=f"{hs6_code} mid-year tariff fixture",
        chapter=hs6_code[:2],
        heading=hs6_code[:4],
        description="Synthetic mid-year tariff fixture",
        section="XXI",
        section_name="Miscellaneous",
    )
    source = _build_source("tariff-mid-year")
    session.add_all([product, source])
    await session.flush()

    header = TariffScheduleHeader(
        source_id=source.source_id,
        importing_state=importer,
        exporting_scope=exporter,
        schedule_status=ScheduleStatusEnum.OFFICIAL,
        publication_date=date(DEFAULT_YEAR, 6, 1),
        effective_date=date(DEFAULT_YEAR, 7, 1),
        expiry_date=date(DEFAULT_YEAR, 12, 31),
        hs_version="HS2017",
        category_system="pytest",
    )
    session.add(header)
    await session.flush()

    line = TariffScheduleLine(
        schedule_id=header.schedule_id,
        hs_code=f"{hs6_code}00",
        product_description="Synthetic mid-year line",
        tariff_category=TariffCategoryEnum.LIBERALISED,
        mfn_base_rate=Decimal("15.0000"),
        base_year=DEFAULT_YEAR,
        target_rate=Decimal("0.0000"),
        target_year=DEFAULT_YEAR,
        staging_type=StagingTypeEnum.IMMEDIATE,
        row_ref="mid-year",
    )
    session.add(line)
    await session.flush()

    session.add(
        TariffScheduleRateByYear(
            schedule_line_id=line.schedule_line_id,
            calendar_year=DEFAULT_YEAR,
            preferential_rate=Decimal("0.0000"),
            rate_status=RateStatusEnum.IN_FORCE,
            source_id=source.source_id,
        )
    )
    await session.flush()

    return {
        "exporter": exporter,
        "importer": importer,
        "hs_version": "HS2017",
        "hs6_code": hs6_code,
    }


async def _expected_tariff_bundle(
    session: AsyncSession,
    *,
    exporter: str,
    importer: str,
    hs_version: str,
    hs6_code: str,
    year: int,
    assessment_date: date | None,
    prefix_match: bool,
) -> Mapping[str, Any] | None:
    """Mirror the tariff lookup query so repository output can be compared directly."""

    join_clause = (
        "hp.hs_version = tsh.hs_version AND hp.hs6_code = LEFT(tsl.hs_code, 6)"
        if prefix_match
        else "hp.hs_version = tsh.hs_version AND hp.hs6_code = tsl.hs_code"
    )
    resolved_assessment_date = assessment_date or date(year, 1, 1)
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
          AND (tsh.effective_date IS NULL OR tsh.effective_date <= :assessment_date)
          AND (tsh.expiry_date IS NULL OR tsh.expiry_date >= :assessment_date)
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
                "assessment_date": resolved_assessment_date,
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
              AND (tsh.effective_date IS NULL OR tsh.effective_date <= :assessment_date)
              AND (tsh.expiry_date IS NULL OR tsh.expiry_date >= :assessment_date)
            GROUP BY tsh.exporting_scope, tsh.importing_state, hp.hs_version, hp.hs6_code
            HAVING COUNT(*) = 1
            ORDER BY hp.hs6_code ASC
            LIMIT 1
            """,
            {
                "year": DEFAULT_YEAR,
                "assessment_date": date(DEFAULT_YEAR, 1, 1),
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
        assessment_date=None,
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
              AND (tsh.effective_date IS NULL OR tsh.effective_date <= :assessment_date)
              AND (tsh.expiry_date IS NULL OR tsh.expiry_date >= :assessment_date)
            ORDER BY hp.hs6_code ASC, tsh.exporting_scope ASC, tsh.importing_state ASC
            LIMIT 1
            """,
            {
                "year": DEFAULT_YEAR,
                "assessment_date": date(DEFAULT_YEAR, 1, 1),
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
        assessment_date=None,
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
        assessment_date=None,
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
async def test_get_tariff_returns_source_and_reference_provenance_fields(
    tariffs_repository: tuple[AsyncSession, TariffsRepository],
) -> None:
    """Resolved tariff bundles should expose schedule/rate source ids and line/rate references."""

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
            WHERE tsh.source_id IS NOT NULL
            ORDER BY hp.hs6_code ASC, tsh.exporting_scope ASC, tsh.importing_state ASC
            LIMIT 1
            """,
        ),
        "No tariff-backed candidate with provenance source ids is loaded in the test database.",
    )
    expected = await _expected_tariff_bundle(
        session,
        exporter=str(candidate["exporter"]),
        importer=str(candidate["importer"]),
        hs_version=str(candidate["hs_version"]),
        hs6_code=str(candidate["hs6_code"]),
        year=DEFAULT_YEAR,
        assessment_date=None,
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
    assert str(resolved["schedule_source_id"]) == str(expected["schedule_source_id"])
    assert str(resolved["rate_source_id"]) == str(expected["rate_source_id"])
    assert resolved["line_page_ref"] == expected["line_page_ref"]
    assert resolved["rate_page_ref"] == expected["rate_page_ref"]
    assert resolved["table_ref"] == expected["table_ref"]
    assert resolved["row_ref"] == expected["row_ref"]


@pytest.mark.asyncio
async def test_get_tariff_prefers_highest_priority_schedule_status(
    tariffs_repository: tuple[AsyncSession, TariffsRepository],
) -> None:
    """Gazetted schedules should beat official or provisional schedules for the same lookup."""

    session, repository = tariffs_repository
    candidate = await _seed_schedule_status_fixture(session)
    expected = await _expected_tariff_bundle(
        session,
        exporter=str(candidate["exporter"]),
        importer=str(candidate["importer"]),
        hs_version=str(candidate["hs_version"]),
        hs6_code=str(candidate["hs6_code"]),
        year=DEFAULT_YEAR,
        assessment_date=None,
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
    assert str(resolved["schedule_status"]) == "gazetted"


@pytest.mark.asyncio
async def test_get_tariff_honors_exact_mid_year_assessment_date(
    tariffs_repository: tuple[AsyncSession, TariffsRepository],
) -> None:
    """Mid-year schedule windows must be evaluated against the exact assessment date."""

    session, repository = tariffs_repository
    candidate = await _seed_mid_year_effectivity_fixture(session)
    before_effective = await repository.get_tariff(
        exporter=str(candidate["exporter"]),
        importer=str(candidate["importer"]),
        hs_version=str(candidate["hs_version"]),
        hs6_code=str(candidate["hs6_code"]),
        year=DEFAULT_YEAR,
        assessment_date=date(DEFAULT_YEAR, 6, 30),
    )
    on_or_after_effective = await repository.get_tariff(
        exporter=str(candidate["exporter"]),
        importer=str(candidate["importer"]),
        hs_version=str(candidate["hs_version"]),
        hs6_code=str(candidate["hs6_code"]),
        year=DEFAULT_YEAR,
        assessment_date=date(DEFAULT_YEAR, 7, 1),
    )
    after_expiry = await repository.get_tariff(
        exporter=str(candidate["exporter"]),
        importer=str(candidate["importer"]),
        hs_version=str(candidate["hs_version"]),
        hs6_code=str(candidate["hs6_code"]),
        year=DEFAULT_YEAR,
        assessment_date=date(DEFAULT_YEAR + 1, 1, 1),
    )

    assert before_effective is None
    assert on_or_after_effective is not None
    assert on_or_after_effective["resolved_rate_year"] == DEFAULT_YEAR
    assert after_expiry is None


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

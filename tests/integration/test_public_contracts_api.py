from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.countries import V01_COUNTRIES
from app.db.base import get_async_session_factory


pytestmark = pytest.mark.integration


def _sql_tuple(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(f"'{value}'" for value in values) + ")"


async def _select_rule_candidate(year: int = 2025) -> dict[str, Any] | None:
    """Pick one active rule-backed HS6 candidate with a non-null source id."""

    statement = text(
        """
        SELECT hp.hs6_code
        FROM hs6_product hp
        JOIN hs6_psr_applicability pa ON pa.hs6_id = hp.hs6_id
        JOIN psr_rule pr ON pr.psr_id = pa.psr_id
        WHERE hp.hs_version = 'HS2017'
          AND pr.source_id IS NOT NULL
          AND (pa.effective_date IS NULL OR pa.effective_date <= :assessment_date)
          AND (pa.expiry_date IS NULL OR pa.expiry_date >= :assessment_date)
        ORDER BY hp.hs6_code ASC
        LIMIT 1
        """
    )
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(statement, {"assessment_date": date(year, 1, 1)})
        row = result.mappings().first()
    if row is None:
        return None
    return {"hs6_code": row["hs6_code"]}


async def _select_tariff_candidate(year: int = 2025) -> dict[str, Any] | None:
    """Pick one tariff candidate on a supported v0.1 corridor with provenance ids."""

    supported = tuple(sorted(V01_COUNTRIES.keys()))
    statement = text(
        f"""
        SELECT DISTINCT
          tsh.exporting_scope AS exporter,
          tsh.importing_state AS importer,
          hp.hs6_code
        FROM tariff_schedule_header tsh
        JOIN tariff_schedule_line tsl ON tsl.schedule_id = tsh.schedule_id
        JOIN hs6_product hp
          ON hp.hs_version = tsh.hs_version
         AND hp.hs6_code = LEFT(tsl.hs_code, 6)
        JOIN tariff_schedule_rate_by_year tsry
          ON tsry.schedule_line_id = tsl.schedule_line_id
         AND tsry.calendar_year <= :year
        WHERE tsh.source_id IS NOT NULL
          AND tsry.source_id IS NOT NULL
          AND tsh.exporting_scope IN {_sql_tuple(supported)}
          AND tsh.importing_state IN {_sql_tuple(supported)}
          AND (tsh.effective_date IS NULL OR tsh.effective_date <= :assessment_date)
          AND (tsh.expiry_date IS NULL OR tsh.expiry_date >= :assessment_date)
        ORDER BY hp.hs6_code ASC, tsh.exporting_scope ASC, tsh.importing_state ASC
        LIMIT 1
        """
    )
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            statement,
            {"year": year, "assessment_date": date(year, 1, 1)},
        )
        row = result.mappings().first()
    if row is None:
        return None
    return {
        "exporter": row["exporter"],
        "importer": row["importer"],
        "hs6_code": row["hs6_code"],
    }


@pytest.mark.asyncio
async def test_rules_endpoint_exposes_provenance_ids(async_client: AsyncClient) -> None:
    """GET /rules/{hs6} should include provenance_ids for source traversal."""

    candidate = await _select_rule_candidate()
    if candidate is None:
        pytest.skip("No active rule candidate with source provenance is loaded.")

    response = await async_client.get(f"/api/v1/rules/{candidate['hs6_code']}")
    assert response.status_code == 200, response.text
    body = response.json()

    assert "provenance_ids" in body
    assert isinstance(body["provenance_ids"], list)
    assert body.get("source_id") in body["provenance_ids"]


@pytest.mark.asyncio
async def test_tariffs_endpoint_exposes_provenance_ids_and_accepts_as_of_date(
    async_client: AsyncClient,
) -> None:
    """GET /tariffs should expose provenance_ids and honor as_of_date parsing."""

    candidate = await _select_tariff_candidate()
    if candidate is None:
        pytest.skip("No supported tariff candidate with source provenance is loaded.")

    response = await async_client.get(
        "/api/v1/tariffs",
        params={
            "exporter": candidate["exporter"],
            "importer": candidate["importer"],
            "hs6": candidate["hs6_code"],
            "year": 2025,
            "as_of_date": "2025-01-01",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert "provenance_ids" in body
    assert isinstance(body["provenance_ids"], list)
    schedule_source_id = body.get("schedule_source_id")
    rate_source_id = body.get("rate_source_id")
    if schedule_source_id is not None:
        assert schedule_source_id in body["provenance_ids"]
    if rate_source_id is not None:
        assert rate_source_id in body["provenance_ids"]

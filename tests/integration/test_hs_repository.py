"""Integration tests for canonical HS6 backbone repository queries."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Mapping
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.cache as cache
from app.config import get_settings
from app.db.base import get_async_session_factory
from app.db.models.hs import HS6Product
from app.repositories.hs_repository import HSRepository
from tests.fixtures.golden_cases import GOLDEN_CASES


pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def hs_repository() -> AsyncIterator[tuple[AsyncSession, HSRepository]]:
    """Provide a live async session plus the repository under test."""

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        yield session, HSRepository(session)


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
    """Skip when the live HS dataset lacks the needed shape."""

    if candidate is None:
        pytest.skip(reason)
    return candidate


def _extract_search_term(description: str) -> str:
    """Pick a stable word token from a live description for substring search tests."""

    tokens = re.findall(r"[A-Za-z]{4,}", description)
    if not tokens:
        pytest.skip("No HS description with a stable alphabetic token is available in the test database.")
    return tokens[0].lower()


def _golden_case(name_fragment: str) -> Mapping[str, Any]:
    """Return one locked golden case by a stable name fragment."""

    for case in GOLDEN_CASES:
        if name_fragment in str(case["name"]):
            return case
    raise AssertionError(f"Golden case not found for fragment: {name_fragment}")


def _fact_payload(fact_key: str, value: Any) -> dict[str, Any]:
    """Convert one golden-case fact into the live assessment payload shape."""

    payload: dict[str, Any] = {
        "fact_type": fact_key,
        "fact_key": fact_key,
    }
    if isinstance(value, bool):
        payload["fact_value_type"] = "boolean"
        payload["fact_value_boolean"] = value
        return payload
    if isinstance(value, int | float):
        payload["fact_value_type"] = "number"
        payload["fact_value_number"] = value
        return payload
    if isinstance(value, list):
        payload["fact_value_type"] = "list"
        payload["fact_value_json"] = value
        return payload
    if isinstance(value, dict):
        payload["fact_value_type"] = "json"
        payload["fact_value_json"] = value
        return payload

    payload["fact_value_type"] = "text"
    payload["fact_value_text"] = value
    return payload


def _assessment_payload(case: Mapping[str, Any]) -> dict[str, Any]:
    """Build one live assessment request from a locked golden case."""

    case_input = case["input"]
    facts = case_input["facts"]
    return {
        "hs6_code": case_input["hs6_code"],
        "hs_version": case_input["hs_version"],
        "exporter": case_input["exporter"],
        "importer": case_input["importer"],
        "year": case_input["year"],
        "persona_mode": "exporter",
        "production_facts": [
            _fact_payload(fact_key, value) for fact_key, value in facts.items()
        ],
    }


async def _seed_multi_version_fixture(session: AsyncSession) -> str:
    """Insert the same HS6 code across two versions for deterministic scope assertions."""

    hs6_code = "990401"
    session.add_all(
        [
            HS6Product(
                hs_version="HS2017",
                hs6_code=hs6_code,
                hs6_display=f"{hs6_code} test product 2017",
                chapter=hs6_code[:2],
                heading=hs6_code[:4],
                description="Synthetic multi-version fixture 2017",
                section="XXI",
                section_name="Miscellaneous",
            ),
            HS6Product(
                hs_version="HS2022",
                hs6_code=hs6_code,
                hs6_display=f"{hs6_code} test product 2022",
                chapter=hs6_code[:2],
                heading=hs6_code[:4],
                description="Synthetic multi-version fixture 2022",
                section="XXI",
                section_name="Miscellaneous",
            ),
        ]
    )
    await session.flush()
    return hs6_code


@pytest.mark.asyncio
async def test_get_by_code_returns_canonical_hs2017_product(
    hs_repository: tuple[AsyncSession, HSRepository],
) -> None:
    """The repository should return the exact HS2017 backbone row for a 6-digit code."""

    session, repository = hs_repository
    candidate = _require_candidate(
        await _fetch_one(
            session,
            """
            SELECT
              hs6_id,
              hs_version,
              hs6_code,
              hs6_display,
              chapter,
              heading,
              description,
              section,
              section_name
            FROM hs6_product
            WHERE hs_version = 'HS2017'
            ORDER BY hs6_code ASC
            LIMIT 1
            """,
        ),
        "No HS2017 product rows are loaded in the test database.",
    )

    resolved = await repository.get_by_code("HS2017", str(candidate["hs6_code"]))

    assert resolved is not None
    assert str(resolved.hs6_id) == str(candidate["hs6_id"])
    assert resolved.hs_version == candidate["hs_version"]
    assert resolved.hs6_code == candidate["hs6_code"]
    assert resolved.hs6_display == candidate["hs6_display"]
    assert resolved.chapter == candidate["chapter"]
    assert resolved.heading == candidate["heading"]
    assert resolved.description == candidate["description"]
    assert resolved.section == candidate["section"]
    assert resolved.section_name == candidate["section_name"]


@pytest.mark.asyncio
async def test_get_by_code_respects_hs_version_scope_when_same_code_exists_across_versions(
    hs_repository: tuple[AsyncSession, HSRepository],
) -> None:
    """The repository should scope canonical resolution by hs_version plus hs6_code."""

    session, repository = hs_repository
    seeded_hs6_code = await _seed_multi_version_fixture(session)
    expected_rows = await _fetch_all(
        session,
        """
        SELECT hs6_id, hs_version, hs6_code, description
        FROM hs6_product
        WHERE hs6_code = :hs6_code
        ORDER BY hs_version ASC
        """,
        {"hs6_code": seeded_hs6_code},
    )

    assert len(expected_rows) >= 2

    first_version = str(expected_rows[0]["hs_version"])
    second_version = str(expected_rows[1]["hs_version"])
    first_result = await repository.get_by_code(first_version, seeded_hs6_code)
    second_result = await repository.get_by_code(second_version, seeded_hs6_code)

    assert first_result is not None
    assert second_result is not None
    assert first_result.hs_version == first_version
    assert second_result.hs_version == second_version
    assert str(first_result.hs6_id) == str(expected_rows[0]["hs6_id"])
    assert str(second_result.hs6_id) == str(expected_rows[1]["hs6_id"])


@pytest.mark.asyncio
async def test_get_by_code_returns_none_for_missing_exact_hs6_code(
    hs_repository: tuple[AsyncSession, HSRepository],
) -> None:
    """The repository should fail cleanly when the exact canonical HS6 row is absent."""

    _session, repository = hs_repository

    resolved = await repository.get_by_code("HS2017", "999999")

    assert resolved is None


@pytest.mark.asyncio
async def test_search_by_description_returns_ordered_matching_rows(
    hs_repository: tuple[AsyncSession, HSRepository],
) -> None:
    """Description search should match by ILIKE and preserve repository ordering."""

    session, repository = hs_repository
    candidate = _require_candidate(
        await _fetch_one(
            session,
            """
            SELECT description
            FROM hs6_product
            WHERE description ~ '[A-Za-z]{4,}'
            ORDER BY hs_version ASC, hs6_code ASC
            LIMIT 1
            """,
        ),
        "No HS description with a searchable word token is loaded in the test database.",
    )
    search_term = _extract_search_term(str(candidate["description"]))
    expected_rows = await _fetch_all(
        session,
        """
        SELECT hs6_id, hs_version, hs6_code, description
        FROM hs6_product
        WHERE description ILIKE :pattern
        ORDER BY hs_version ASC, hs6_code ASC
        """,
        {"pattern": f"%{search_term}%"},
    )

    results = await repository.search_by_description(search_term)

    assert expected_rows
    assert [str(row.hs6_id) for row in results] == [str(row["hs6_id"]) for row in expected_rows]
    assert [(row.hs_version, row.hs6_code) for row in results] == [
        (str(row["hs_version"]), str(row["hs6_code"])) for row in expected_rows
    ]
    assert all(search_term in row.description.lower() for row in results)


@pytest.mark.asyncio
async def test_list_all_respects_limit_offset_and_repository_order(
    hs_repository: tuple[AsyncSession, HSRepository],
) -> None:
    """Paged listing should use deterministic hs_version and hs6_code ordering."""

    session, repository = hs_repository
    candidate = _require_candidate(
        await _fetch_one(
            session,
            """
            SELECT COUNT(*) AS total_rows
            FROM hs6_product
            """,
        ),
        "The hs6_product table is empty in the test database.",
    )
    total_rows = int(candidate["total_rows"])
    if total_rows < 4:
        pytest.skip("Need at least four HS rows to verify offset paging deterministically.")

    limit = 3
    offset = 1
    expected_rows = await _fetch_all(
        session,
        """
        SELECT hs6_id, hs_version, hs6_code
        FROM hs6_product
        ORDER BY hs_version ASC, hs6_code ASC
        LIMIT :limit OFFSET :offset
        """,
        {"limit": limit, "offset": offset},
    )

    results = await repository.list_all(limit=limit, offset=offset)

    assert len(results) == len(expected_rows) == limit
    assert [str(row.hs6_id) for row in results] == [str(row["hs6_id"]) for row in expected_rows]
    assert [(row.hs_version, row.hs6_code) for row in results] == [
        (str(row["hs_version"]), str(row["hs6_code"])) for row in expected_rows
    ]


@pytest.mark.asyncio
async def test_static_lookup_cache_preserves_hs_resolution_and_assessment_outcome(
    hs_repository: tuple[AsyncSession, HSRepository],
    async_client: AsyncClient,
) -> None:
    """Cold-cache and warm-cache reads must return the same repository row and assessment output."""

    _session, repository = hs_repository
    settings = get_settings()
    case = _golden_case("groats CTH pass")
    hs_version = str(case["input"]["hs_version"])
    hs6_code = str(case["input"]["hs6_code"])
    cache_key = ("hs6", hs_version, hs6_code)

    assert settings.CACHE_STATIC_LOOKUPS is True

    cache.clear_all()

    first_product = await repository.get_by_code(hs_version, hs6_code)
    second_product = await repository.get_by_code(hs_version, hs6_code)

    assert first_product is not None
    assert second_product is not None
    assert cache_key in cache.hs6_store
    assert str(first_product.hs6_id) == str(second_product.hs6_id)
    assert first_product.hs_version == second_product.hs_version
    assert first_product.hs6_code == second_product.hs6_code
    assert first_product.hs6_display == second_product.hs6_display
    assert first_product.description == second_product.description

    cache.clear_all()

    payload = _assessment_payload(case)
    first_response = await async_client.post("/api/v1/assessments", json=payload)
    second_response = await async_client.post("/api/v1/assessments", json=payload)

    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 200, second_response.text
    assert cache.hs6_store
    assert cache.psr_store
    assert cache.tariff_store
    assert first_response.json() == second_response.json()

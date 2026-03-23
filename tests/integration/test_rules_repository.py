"""Integration tests for parser-backed PSR resolution queries."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from datetime import date
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AuthorityTierEnum, HsLevelEnum, RuleStatusEnum, SourceTypeEnum
from app.db.base import get_async_session_factory
from app.db.models.hs import HS6Product
from app.db.models.rules import HS6PSRApplicability, PSRRule
from app.db.models.sources import SourceRegistry
from app.repositories.rules_repository import RulesRepository


pytestmark = pytest.mark.integration

ASSESSMENT_DATE = date(2025, 1, 1)
_WINNER_CTE = """
WITH resolved AS (
    SELECT
        hp.hs6_id,
        hp.hs_version,
        hp.hs6_code,
        pa.psr_id,
        pa.applicability_type,
        pa.priority_rank,
        ROW_NUMBER() OVER (
            PARTITION BY hp.hs6_id
            ORDER BY pa.priority_rank ASC, pr.updated_at DESC
        ) AS winner_rank
    FROM hs6_product hp
    JOIN hs6_psr_applicability pa ON pa.hs6_id = hp.hs6_id
    JOIN psr_rule pr ON pr.psr_id = pa.psr_id
    WHERE hp.hs_version = 'HS2017'
      AND (pa.effective_date IS NULL OR pa.effective_date <= :assessment_date)
      AND (pa.expiry_date IS NULL OR pa.expiry_date >= :assessment_date)
)
"""


@pytest_asyncio.fixture
async def rules_repository() -> AsyncIterator[tuple[AsyncSession, RulesRepository]]:
    """Provide a live async session plus the repository under test."""

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        yield session, RulesRepository(session)


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
    """Skip when the live parser-loaded dataset lacks the needed shape."""

    if candidate is None:
        pytest.skip(reason)
    return candidate


def _priority_ranks(rows: list[Mapping[str, Any]]) -> list[int]:
    """Extract ordered pathway priority ranks from raw query rows."""

    return [int(row["priority_rank"]) for row in rows]


def _pathway_codes(rows: list[Mapping[str, Any]]) -> list[str]:
    """Extract ordered pathway codes from raw query rows."""

    return [str(row["pathway_code"]) for row in rows]


def _build_source(tag: str) -> SourceRegistry:
    """Create a minimal provenance row for seeded repository fixtures."""

    checksum = (uuid4().hex + uuid4().hex)
    return SourceRegistry(
        title=f"Rules fixture {tag}",
        short_title=f"RF-{tag}",
        source_group="pytest",
        source_type=SourceTypeEnum.APPENDIX,
        authority_tier=AuthorityTierEnum.BINDING,
        issuing_body="pytest",
        jurisdiction_scope="test",
        publication_date=ASSESSMENT_DATE,
        effective_date=ASSESSMENT_DATE,
        status="current",
        language="en",
        hs_version="HS2017",
        file_path=f"tests/{tag}.txt",
        mime_type="text/plain",
        checksum_sha256=checksum,
    )


async def _seed_precedence_fixture(
    session: AsyncSession,
    *,
    hs6_code: str,
    applicability_rows: list[tuple[str, int]],
) -> dict[str, Any]:
    """Insert a synthetic HS6 product plus applicability rows for precedence tests."""

    source = _build_source(f"precedence-{hs6_code}")
    product = HS6Product(
        hs_version="HS2017",
        hs6_code=hs6_code,
        hs6_display=f"{hs6_code} precedence fixture",
        chapter=hs6_code[:2],
        heading=hs6_code[:4],
        description="Synthetic precedence fixture",
        section="XXI",
        section_name="Miscellaneous",
    )
    session.add_all([source, product])
    await session.flush()

    seeded_rules: list[PSRRule] = []
    for index, (applicability_type, priority_rank) in enumerate(applicability_rows, start=1):
        rule = PSRRule(
            source_id=source.source_id,
            appendix_version="pytest-fixture",
            hs_version="HS2017",
            hs_code=hs6_code,
            hs_level=HsLevelEnum.SUBHEADING,
            product_description="Synthetic precedence fixture",
            legal_rule_text_verbatim=f"{applicability_type} rule",
            legal_rule_text_normalized=applicability_type,
            rule_status=RuleStatusEnum.AGREED,
            effective_date=ASSESSMENT_DATE,
            row_ref=f"{hs6_code}-{applicability_type}-{index}",
        )
        session.add(rule)
        await session.flush()
        session.add(
            HS6PSRApplicability(
                hs6_id=product.hs6_id,
                psr_id=rule.psr_id,
                applicability_type=applicability_type,
                priority_rank=priority_rank,
                effective_date=ASSESSMENT_DATE,
            )
        )
        seeded_rules.append(rule)

    await session.flush()
    expected_type, expected_priority = min(applicability_rows, key=lambda item: item[1])
    expected_rule = seeded_rules[[row[0] for row in applicability_rows].index(expected_type)]
    return {
        "hs6_id": product.hs6_id,
        "expected_psr_id": expected_rule.psr_id,
        "expected_type": expected_type,
        "expected_priority": expected_priority,
    }


@pytest.mark.asyncio
async def test_resolve_applicable_psr_prefers_direct_applicability_row_when_broader_rows_exist(
    rules_repository: tuple[AsyncSession, RulesRepository],
) -> None:
    """The repository should resolve the active winner from hs6_psr_applicability."""

    session, repository = rules_repository
    candidate = await _seed_precedence_fixture(
        session,
        hs6_code="990101",
        applicability_rows=[
            ("direct", 1),
            ("range", 2),
            ("inherited_heading", 3),
        ],
    )

    resolved = await repository.resolve_applicable_psr(str(candidate["hs6_id"]), ASSESSMENT_DATE)

    assert resolved is not None
    assert candidate["expected_type"] == "direct"
    assert str(resolved["psr_id"]) == str(candidate["expected_psr_id"])
    assert resolved["applicability_type"] == candidate["expected_type"]
    assert resolved["priority_rank"] == candidate["expected_priority"]
    assert str(resolved["rule_status"]) == RuleStatusEnum.AGREED.value


@pytest.mark.asyncio
async def test_resolve_applicable_psr_prefers_range_over_heading_and_chapter_when_no_direct_exists(
    rules_repository: tuple[AsyncSession, RulesRepository],
) -> None:
    """Range applicability should outrank inherited heading and chapter rows."""

    session, repository = rules_repository
    candidate = await _seed_precedence_fixture(
        session,
        hs6_code="990102",
        applicability_rows=[
            ("range", 1),
            ("inherited_heading", 2),
            ("inherited_chapter", 3),
        ],
    )

    resolved = await repository.resolve_applicable_psr(str(candidate["hs6_id"]), ASSESSMENT_DATE)

    assert resolved is not None
    assert candidate["expected_type"] == "range"
    assert str(resolved["psr_id"]) == str(candidate["expected_psr_id"])
    assert resolved["applicability_type"] == "range"
    assert resolved["priority_rank"] == candidate["expected_priority"]


@pytest.mark.asyncio
async def test_resolve_applicable_psr_prefers_heading_over_chapter_when_more_specific_row_is_active(
    rules_repository: tuple[AsyncSession, RulesRepository],
) -> None:
    """Inherited heading applicability should beat inherited chapter applicability."""

    session, repository = rules_repository
    candidate = await _seed_precedence_fixture(
        session,
        hs6_code="990103",
        applicability_rows=[
            ("inherited_heading", 1),
            ("inherited_chapter", 2),
        ],
    )

    resolved = await repository.resolve_applicable_psr(str(candidate["hs6_id"]), ASSESSMENT_DATE)

    assert resolved is not None
    assert candidate["expected_type"] == "inherited_heading"
    assert str(resolved["psr_id"]) == str(candidate["expected_psr_id"])
    assert resolved["applicability_type"] == "inherited_heading"
    assert resolved["priority_rank"] == candidate["expected_priority"]


@pytest.mark.asyncio
async def test_get_rules_by_hs6_returns_pathways_in_priority_order(
    rules_repository: tuple[AsyncSession, RulesRepository],
) -> None:
    """Resolved pathways should come back in ascending priority rank order."""

    session, repository = rules_repository
    candidate = _require_candidate(
        await _fetch_one(
            session,
            _WINNER_CTE
            + """
            SELECT resolved.hs_version, resolved.hs6_code, resolved.psr_id
            FROM resolved
            JOIN eligibility_rule_pathway erp ON erp.psr_id = resolved.psr_id
            WHERE resolved.winner_rank = 1
              AND (erp.effective_date IS NULL OR erp.effective_date <= :assessment_date)
              AND (erp.expiry_date IS NULL OR erp.expiry_date >= :assessment_date)
            GROUP BY resolved.hs_version, resolved.hs6_code, resolved.psr_id
            HAVING COUNT(*) > 1
            ORDER BY resolved.hs6_code ASC
            LIMIT 1
            """,
            {"assessment_date": ASSESSMENT_DATE},
        ),
        "No resolved PSR with multiple active pathways is loaded in the test database.",
    )
    expected_pathways = await _fetch_all(
        session,
        """
        SELECT erp.pathway_code, erp.priority_rank
        FROM eligibility_rule_pathway erp
        WHERE erp.psr_id = :psr_id
          AND (erp.effective_date IS NULL OR erp.effective_date <= :assessment_date)
          AND (erp.expiry_date IS NULL OR erp.expiry_date >= :assessment_date)
        ORDER BY erp.priority_rank ASC
        """,
        {"psr_id": candidate["psr_id"], "assessment_date": ASSESSMENT_DATE},
    )

    bundle = await repository.get_rules_by_hs6(
        str(candidate["hs_version"]),
        str(candidate["hs6_code"]),
        ASSESSMENT_DATE,
    )

    assert bundle is not None
    assert str(bundle["psr"]["psr_id"]) == str(candidate["psr_id"])
    assert _pathway_codes(bundle["pathways"]) == _pathway_codes(expected_pathways)
    assert _priority_ranks(bundle["pathways"]) == _priority_ranks(expected_pathways)
    assert _priority_ranks(bundle["pathways"]) == sorted(_priority_ranks(bundle["pathways"]))


@pytest.mark.asyncio
async def test_get_rules_by_hs6_preserves_pending_note_rows(
    rules_repository: tuple[AsyncSession, RulesRepository],
) -> None:
    """Pending parser-generated NOTE components should be returned intact."""

    session, repository = rules_repository
    candidate = _require_candidate(
        await _fetch_one(
            session,
            _WINNER_CTE
            + """
            SELECT resolved.hs_version, resolved.hs6_code, resolved.psr_id, pr.rule_status::text AS rule_status
            FROM resolved
            JOIN psr_rule pr ON pr.psr_id = resolved.psr_id
            JOIN psr_rule_component prc ON prc.psr_id = resolved.psr_id
            WHERE resolved.winner_rank = 1
              AND pr.rule_status::text = 'pending'
            GROUP BY resolved.hs_version, resolved.hs6_code, resolved.psr_id, pr.rule_status
            HAVING BOOL_OR(prc.component_type::text = 'NOTE')
            ORDER BY resolved.hs6_code ASC
            LIMIT 1
            """,
            {"assessment_date": ASSESSMENT_DATE},
        ),
        "No pending resolved PSR with NOTE components is loaded in the test database.",
    )
    expected_note_components = await _fetch_all(
        session,
        """
        SELECT prc.component_type::text AS component_type, prc.component_order
        FROM psr_rule_component prc
        WHERE prc.psr_id = :psr_id
          AND prc.component_type::text = 'NOTE'
        ORDER BY prc.component_order ASC
        """,
        {"psr_id": candidate["psr_id"]},
    )

    bundle = await repository.get_rules_by_hs6(
        str(candidate["hs_version"]),
        str(candidate["hs6_code"]),
        ASSESSMENT_DATE,
    )

    assert bundle is not None
    assert str(bundle["psr"]["psr_id"]) == str(candidate["psr_id"])
    assert str(bundle["psr"]["rule_status"]) == str(candidate["rule_status"])
    assert str(bundle["psr"]["rule_status"]) == "pending"
    assert [str(component["component_type"]) for component in bundle["components"] if str(component["component_type"]) == "NOTE"] == [
        row["component_type"] for row in expected_note_components
    ]
    assert [
        int(component["component_order"])
        for component in bundle["components"]
        if str(component["component_type"]) == "NOTE"
    ] == [int(row["component_order"]) for row in expected_note_components]


@pytest.mark.asyncio
async def test_get_rules_by_hs6_preserves_process_pathways(
    rules_repository: tuple[AsyncSession, RulesRepository],
) -> None:
    """PROCESS pathways from parser-loaded rules should not be filtered out."""

    session, repository = rules_repository
    candidate = _require_candidate(
        await _fetch_one(
            session,
            _WINNER_CTE
            + """
            SELECT resolved.hs_version, resolved.hs6_code, resolved.psr_id
            FROM resolved
            JOIN eligibility_rule_pathway erp ON erp.psr_id = resolved.psr_id
            WHERE resolved.winner_rank = 1
              AND (erp.effective_date IS NULL OR erp.effective_date <= :assessment_date)
              AND (erp.expiry_date IS NULL OR erp.expiry_date >= :assessment_date)
            GROUP BY resolved.hs_version, resolved.hs6_code, resolved.psr_id
            HAVING BOOL_OR(erp.pathway_code = 'PROCESS')
            ORDER BY resolved.hs6_code ASC
            LIMIT 1
            """,
            {"assessment_date": ASSESSMENT_DATE},
        ),
        "No resolved PSR with PROCESS pathways is loaded in the test database.",
    )
    expected_process_pathways = await _fetch_all(
        session,
        """
        SELECT erp.pathway_code, erp.priority_rank, erp.expression_json
        FROM eligibility_rule_pathway erp
        WHERE erp.psr_id = :psr_id
          AND erp.pathway_code = 'PROCESS'
          AND (erp.effective_date IS NULL OR erp.effective_date <= :assessment_date)
          AND (erp.expiry_date IS NULL OR erp.expiry_date >= :assessment_date)
        ORDER BY erp.priority_rank ASC
        """,
        {"psr_id": candidate["psr_id"], "assessment_date": ASSESSMENT_DATE},
    )

    bundle = await repository.get_rules_by_hs6(
        str(candidate["hs_version"]),
        str(candidate["hs6_code"]),
        ASSESSMENT_DATE,
    )

    assert bundle is not None
    actual_process_pathways = [
        pathway for pathway in bundle["pathways"] if str(pathway["pathway_code"]) == "PROCESS"
    ]
    assert actual_process_pathways
    assert [str(pathway["pathway_code"]) for pathway in actual_process_pathways] == [
        row["pathway_code"] for row in expected_process_pathways
    ]
    assert [int(pathway["priority_rank"]) for pathway in actual_process_pathways] == [
        int(row["priority_rank"]) for row in expected_process_pathways
    ]
    assert [pathway["expression_json"] for pathway in actual_process_pathways] == [
        row["expression_json"] for row in expected_process_pathways
    ]
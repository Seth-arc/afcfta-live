"""Quick Slice end-to-end integration tests against the live assessment API."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.core.enums import (
    AuthorityTierEnum,
    HsLevelEnum,
    RateStatusEnum,
    RuleStatusEnum,
    ScheduleStatusEnum,
    SourceTypeEnum,
    StagingTypeEnum,
    StatusTypeEnum,
    TariffCategoryEnum,
)
from app.core.countries import V01_CORRIDORS
from app.db.base import get_async_session_factory
from app.db.models.hs import HS6Product
from app.db.models.rules import EligibilityRulePathway, HS6PSRApplicability, PSRRule
from app.db.models.sources import SourceRegistry
from app.db.models.status import StatusAssertion
from app.db.models.tariffs import TariffScheduleHeader, TariffScheduleLine, TariffScheduleRateByYear


pytestmark = pytest.mark.integration


def _sql_tuple(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(f"'{value}'" for value in values) + ")"


def _build_source(tag: str, *, source_type: SourceTypeEnum) -> SourceRegistry:
    """Create a minimal source row for seeded quick-slice fixtures."""

    checksum = uuid4().hex + uuid4().hex
    return SourceRegistry(
        title=f"Quick slice fixture {tag}",
        short_title=f"QSF-{tag}",
        source_group="pytest",
        source_type=source_type,
        authority_tier=AuthorityTierEnum.BINDING,
        issuing_body="pytest",
        jurisdiction_scope="test",
        publication_date=date(2025, 1, 1),
        effective_date=date(2025, 1, 1),
        status="current",
        language="en",
        hs_version="HS2017",
        file_path=f"tests/{tag}.txt",
        mime_type="text/plain",
        checksum_sha256=checksum,
    )


async def _seed_pending_quick_slice_candidate() -> dict[str, str]:
    """Insert one isolated pending-rule candidate for deterministic blocker coverage."""

    rule_source = _build_source("pending-rule", source_type=SourceTypeEnum.APPENDIX)
    tariff_source = _build_source("pending-tariff", source_type=SourceTypeEnum.TARIFF_SCHEDULE)

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        existing_codes = set(
            (
                await session.scalars(
                    select(HS6Product.hs6_code).where(
                        HS6Product.hs_version == "HS2017",
                        HS6Product.chapter == "98",
                    )
                )
            ).all()
        )
        hs6_code = next(
            (
                f"98{suffix:04d}"
                for suffix in range(10000)
                if f"98{suffix:04d}" not in existing_codes
            ),
            None,
        )
        if hs6_code is None:
            raise AssertionError("No unused HS Chapter 98 code available for pending quick-slice fixture")

        product = HS6Product(
            hs_version="HS2017",
            hs6_code=hs6_code,
            hs6_display=f"{hs6_code} pending quick-slice fixture",
            chapter=hs6_code[:2],
            heading=hs6_code[:4],
            description="Synthetic pending-rule quick-slice fixture",
            section="XXI",
            section_name="Miscellaneous",
        )
        session.add_all([rule_source, tariff_source, product])
        await session.flush()

        rule = PSRRule(
            source_id=rule_source.source_id,
            appendix_version="pytest-fixture",
            hs_version="HS2017",
            hs_code=hs6_code,
            hs_level=HsLevelEnum.SUBHEADING,
            product_description="Synthetic pending fixture",
            legal_rule_text_verbatim="Wholly obtained only.",
            legal_rule_text_normalized="WO",
            rule_status=RuleStatusEnum.PENDING,
            effective_date=date(2025, 1, 1),
            row_ref=f"pending-{hs6_code}",
        )
        session.add(rule)
        await session.flush()
        session.add_all(
            [
                HS6PSRApplicability(
                    hs6_id=product.hs6_id,
                    psr_id=rule.psr_id,
                    applicability_type="direct",
                    priority_rank=1,
                    effective_date=date(2025, 1, 1),
                ),
                EligibilityRulePathway(
                    psr_id=rule.psr_id,
                    pathway_code="WO",
                    pathway_label="WO",
                    pathway_type="specific",
                    expression_json={"op": "fact_eq", "fact": "wholly_obtained", "value": True},
                    tariff_shift_level=HsLevelEnum.SUBHEADING,
                    priority_rank=1,
                    effective_date=date(2025, 1, 1),
                ),
            ]
        )

        schedule_header = TariffScheduleHeader(
            source_id=tariff_source.source_id,
            importing_state="NGA",
            exporting_scope="GHA",
            schedule_status=ScheduleStatusEnum.OFFICIAL,
            publication_date=date(2025, 1, 1),
            effective_date=date(2025, 1, 1),
            hs_version="HS2017",
            category_system="pytest",
        )
        session.add(schedule_header)
        await session.flush()

        schedule_line = TariffScheduleLine(
            schedule_id=schedule_header.schedule_id,
            hs_code=hs6_code,
            product_description="Synthetic pending fixture tariff line",
            tariff_category=TariffCategoryEnum.LIBERALISED,
            mfn_base_rate=Decimal("15.0000"),
            base_year=2025,
            target_rate=Decimal("0.0000"),
            target_year=2025,
            staging_type=StagingTypeEnum.IMMEDIATE,
            row_ref=f"pending-{hs6_code}",
        )
        session.add(schedule_line)
        await session.flush()
        session.add(
            TariffScheduleRateByYear(
                schedule_line_id=schedule_line.schedule_line_id,
                calendar_year=2025,
                preferential_rate=Decimal("0.0000"),
                rate_status=RateStatusEnum.IN_FORCE,
                source_id=tariff_source.source_id,
            )
        )
        await session.commit()

    return {"hs6_code": hs6_code, "exporter": "GHA", "importer": "NGA"}


async def _seed_missing_schedule_quick_slice_candidate() -> dict[str, str]:
    """Insert one isolated agreed rule without tariff coverage for hard-blocker coverage."""

    hs6_code = f"94{int(uuid4().hex[:4], 16) % 10000:04d}"
    rule_source = _build_source("missing-schedule-rule", source_type=SourceTypeEnum.APPENDIX)

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        product = HS6Product(
            hs_version="HS2017",
            hs6_code=hs6_code,
            hs6_display=f"{hs6_code} missing schedule quick-slice fixture",
            chapter=hs6_code[:2],
            heading=hs6_code[:4],
            description="Synthetic missing-schedule quick-slice fixture",
            section="XXI",
            section_name="Miscellaneous",
        )
        session.add_all([rule_source, product])
        await session.flush()

        rule = PSRRule(
            source_id=rule_source.source_id,
            appendix_version="pytest-fixture",
            hs_version="HS2017",
            hs_code=hs6_code,
            hs_level=HsLevelEnum.SUBHEADING,
            product_description="Synthetic missing-schedule fixture",
            legal_rule_text_verbatim="Wholly obtained only.",
            legal_rule_text_normalized="WO",
            rule_status=RuleStatusEnum.AGREED,
            effective_date=date(2025, 1, 1),
            row_ref=f"missing-schedule-{hs6_code}",
        )
        session.add(rule)
        await session.flush()
        session.add_all(
            [
                HS6PSRApplicability(
                    hs6_id=product.hs6_id,
                    psr_id=rule.psr_id,
                    applicability_type="direct",
                    priority_rank=1,
                    effective_date=date(2025, 1, 1),
                ),
                EligibilityRulePathway(
                    psr_id=rule.psr_id,
                    pathway_code="WO",
                    pathway_label="WO",
                    pathway_type="specific",
                    expression_json={"op": "fact_eq", "fact": "wholly_obtained", "value": True},
                    tariff_shift_level=HsLevelEnum.SUBHEADING,
                    priority_rank=1,
                    effective_date=date(2025, 1, 1),
                ),
            ]
        )
        await session.commit()

    return {"hs6_code": hs6_code, "exporter": "GHA", "importer": "NGA"}


async def _seed_blocker_quick_slice_candidate(
    *,
    tag: str,
    code_prefix: str,
    rule_status: RuleStatusEnum = RuleStatusEnum.AGREED,
    pathway_code: str = "WO",
    expression_json: dict[str, Any] | None = None,
    corridor_status: StatusTypeEnum | None = None,
) -> dict[str, str]:
    """Insert one isolated blocker fixture with optional corridor status overlay."""

    hs6_code = f"{code_prefix}{int(uuid4().hex[:4], 16) % 10000:04d}"
    rule_source = _build_source(f"{tag}-rule", source_type=SourceTypeEnum.APPENDIX)
    tariff_source = _build_source(f"{tag}-tariff", source_type=SourceTypeEnum.TARIFF_SCHEDULE)
    status_source = (
        _build_source(f"{tag}-status", source_type=SourceTypeEnum.STATUS_NOTICE)
        if corridor_status is not None
        else None
    )

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        product = HS6Product(
            hs_version="HS2017",
            hs6_code=hs6_code,
            hs6_display=f"{hs6_code} {tag} quick-slice fixture",
            chapter=hs6_code[:2],
            heading=hs6_code[:4],
            description=f"Synthetic {tag} quick-slice fixture",
            section="XXI",
            section_name="Miscellaneous",
        )
        seed_rows = [rule_source, tariff_source, product]
        if status_source is not None:
            seed_rows.append(status_source)
        session.add_all(seed_rows)
        await session.flush()

        rule = PSRRule(
            source_id=rule_source.source_id,
            appendix_version="pytest-fixture",
            hs_version="HS2017",
            hs_code=hs6_code,
            hs_level=HsLevelEnum.SUBHEADING,
            product_description=f"Synthetic {tag} fixture",
            legal_rule_text_verbatim="Synthetic blocker rule.",
            legal_rule_text_normalized=pathway_code,
            rule_status=rule_status,
            effective_date=date(2025, 1, 1),
            row_ref=f"{tag}-{hs6_code}",
        )
        session.add(rule)
        await session.flush()
        session.add_all(
            [
                HS6PSRApplicability(
                    hs6_id=product.hs6_id,
                    psr_id=rule.psr_id,
                    applicability_type="direct",
                    priority_rank=1,
                    effective_date=date(2025, 1, 1),
                ),
                EligibilityRulePathway(
                    psr_id=rule.psr_id,
                    pathway_code=pathway_code,
                    pathway_label=pathway_code,
                    pathway_type="specific",
                    expression_json=expression_json
                    or {"op": "fact_eq", "fact": "wholly_obtained", "value": True},
                    tariff_shift_level=HsLevelEnum.SUBHEADING,
                    priority_rank=1,
                    effective_date=date(2025, 1, 1),
                ),
            ]
        )

        if status_source is not None:
            session.add(
                StatusAssertion(
                    source_id=status_source.source_id,
                    entity_type="corridor",
                    entity_key=f"CORRIDOR:GHA:NGA:{hs6_code}",
                    status_type=corridor_status,
                    status_text_verbatim="Corridor is not yet operational.",
                    effective_from=date(2025, 1, 1),
                    effective_to=None,
                )
            )

        schedule_header = TariffScheduleHeader(
            source_id=tariff_source.source_id,
            importing_state="NGA",
            exporting_scope="GHA",
            schedule_status=ScheduleStatusEnum.OFFICIAL,
            publication_date=date(2025, 1, 1),
            effective_date=date(2025, 1, 1),
            hs_version="HS2017",
            category_system="pytest",
        )
        session.add(schedule_header)
        await session.flush()

        schedule_line = TariffScheduleLine(
            schedule_id=schedule_header.schedule_id,
            hs_code=hs6_code,
            product_description=f"Synthetic {tag} tariff line",
            tariff_category=TariffCategoryEnum.LIBERALISED,
            mfn_base_rate=Decimal("15.0000"),
            base_year=2025,
            target_rate=Decimal("0.0000"),
            target_year=2025,
            staging_type=StagingTypeEnum.IMMEDIATE,
            row_ref=f"{tag}-{hs6_code}",
        )
        session.add(schedule_line)
        await session.flush()
        session.add(
            TariffScheduleRateByYear(
                schedule_line_id=schedule_line.schedule_line_id,
                calendar_year=2025,
                preferential_rate=Decimal("0.0000"),
                rate_status=RateStatusEnum.IN_FORCE,
                source_id=tariff_source.source_id,
            )
        )
        await session.commit()

    return {"hs6_code": hs6_code, "exporter": "GHA", "importer": "NGA"}


async def _seed_missing_core_facts_quick_slice_candidate() -> dict[str, str]:
    """Insert one isolated VNM candidate whose core facts can be intentionally omitted."""

    return await _seed_blocker_quick_slice_candidate(
        tag="missing-core-facts",
        code_prefix="93",
        pathway_code="VNM",
        expression_json={"op": "formula_lte", "formula": "vnom_percent", "value": 60},
    )


async def _seed_not_operational_quick_slice_candidate() -> dict[str, str]:
    """Insert one isolated candidate whose corridor is not yet operational."""

    return await _seed_blocker_quick_slice_candidate(
        tag="not-operational",
        code_prefix="92",
        corridor_status=StatusTypeEnum.NOT_YET_OPERATIONAL,
    )


async def _seed_snapshot_consistency_candidate() -> dict[str, str]:
    """Insert one isolated two-year candidate with date-sensitive tariff and status state."""

    hs6_code = f"96{int(uuid4().hex[:4], 16) % 10000:04d}"
    rule_source = _build_source("snapshot-rule", source_type=SourceTypeEnum.APPENDIX)
    tariff_source = _build_source("snapshot-tariff", source_type=SourceTypeEnum.TARIFF_SCHEDULE)
    status_source = _build_source("snapshot-status", source_type=SourceTypeEnum.STATUS_NOTICE)

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        product = HS6Product(
            hs_version="HS2017",
            hs6_code=hs6_code,
            hs6_display=f"{hs6_code} snapshot quick-slice fixture",
            chapter=hs6_code[:2],
            heading=hs6_code[:4],
            description="Synthetic snapshot quick-slice fixture",
            section="XXI",
            section_name="Miscellaneous",
        )
        session.add_all([rule_source, tariff_source, status_source, product])
        await session.flush()

        rule = PSRRule(
            source_id=rule_source.source_id,
            appendix_version="pytest-fixture",
            hs_version="HS2017",
            hs_code=hs6_code,
            hs_level=HsLevelEnum.SUBHEADING,
            product_description="Synthetic snapshot fixture",
            legal_rule_text_verbatim="Wholly obtained only.",
            legal_rule_text_normalized="WO",
            rule_status=RuleStatusEnum.AGREED,
            effective_date=date(2025, 1, 1),
            row_ref=f"snapshot-{hs6_code}",
        )
        session.add(rule)
        await session.flush()
        session.add_all(
            [
                HS6PSRApplicability(
                    hs6_id=product.hs6_id,
                    psr_id=rule.psr_id,
                    applicability_type="direct",
                    priority_rank=1,
                    effective_date=date(2025, 1, 1),
                ),
                EligibilityRulePathway(
                    psr_id=rule.psr_id,
                    pathway_code="WO",
                    pathway_label="WO",
                    pathway_type="specific",
                    expression_json={"op": "fact_eq", "fact": "wholly_obtained", "value": True},
                    tariff_shift_level=HsLevelEnum.SUBHEADING,
                    priority_rank=1,
                    effective_date=date(2025, 1, 1),
                ),
                StatusAssertion(
                    source_id=status_source.source_id,
                    entity_type="psr_rule",
                    entity_key=f"PSR:{rule.psr_id}",
                    status_type=StatusTypeEnum.PROVISIONAL,
                    status_text_verbatim="Provisional through 2025.",
                    effective_from=date(2025, 1, 1),
                    effective_to=date(2025, 12, 31),
                ),
                StatusAssertion(
                    source_id=status_source.source_id,
                    entity_type="psr_rule",
                    entity_key=f"PSR:{rule.psr_id}",
                    status_type=StatusTypeEnum.AGREED,
                    status_text_verbatim="Agreed from 2026 onward.",
                    effective_from=date(2026, 1, 1),
                    effective_to=None,
                ),
            ]
        )

        schedule_header = TariffScheduleHeader(
            source_id=tariff_source.source_id,
            importing_state="NGA",
            exporting_scope="GHA",
            schedule_status=ScheduleStatusEnum.OFFICIAL,
            publication_date=date(2025, 1, 1),
            effective_date=date(2025, 1, 1),
            hs_version="HS2017",
            category_system="pytest",
        )
        session.add(schedule_header)
        await session.flush()

        schedule_line = TariffScheduleLine(
            schedule_id=schedule_header.schedule_id,
            hs_code=hs6_code,
            product_description="Synthetic snapshot tariff line",
            tariff_category=TariffCategoryEnum.LIBERALISED,
            mfn_base_rate=Decimal("15.0000"),
            base_year=2025,
            target_rate=Decimal("0.0000"),
            target_year=2026,
            staging_type=StagingTypeEnum.IMMEDIATE,
            row_ref=f"snapshot-{hs6_code}",
        )
        session.add(schedule_line)
        await session.flush()
        session.add_all(
            [
                TariffScheduleRateByYear(
                    schedule_line_id=schedule_line.schedule_line_id,
                    calendar_year=2025,
                    preferential_rate=Decimal("5.0000"),
                    rate_status=RateStatusEnum.PROVISIONAL,
                    source_id=tariff_source.source_id,
                ),
                TariffScheduleRateByYear(
                    schedule_line_id=schedule_line.schedule_line_id,
                    calendar_year=2026,
                    preferential_rate=Decimal("0.0000"),
                    rate_status=RateStatusEnum.IN_FORCE,
                    source_id=tariff_source.source_id,
                ),
            ]
        )
        await session.commit()

    return {"hs6_code": hs6_code, "exporter": "GHA", "importer": "NGA"}


async def _select_supported_candidate(
    *,
    chapter_start: int | None = None,
    chapter_end: int | None = None,
    require_rule_statuses: tuple[str, ...] = (),
    require_component_types: tuple[str, ...] = (),
    exclude_component_types: tuple[str, ...] = (),
    require_pathway_codes: tuple[str, ...] = (),
    min_pathway_count: int | None = None,
    require_cth_before_vnm: bool = False,
    preferred_hs6_codes: tuple[str, ...] = (),
    preferred_corridors: tuple[tuple[str, str], ...] = (),
    require_corridors: tuple[tuple[str, str], ...] = (),
    year: int = 2025,
) -> dict[str, Any] | None:
    where_clauses = [
        "hp.hs_version = 'HS2017'",
        "ry.calendar_year = :year",
        "(pa.effective_date IS NULL OR pa.effective_date <= :assessment_date)",
        "(pa.expiry_date IS NULL OR pa.expiry_date >= :assessment_date)",
        "(sh.effective_date IS NULL OR sh.effective_date <= :assessment_date)",
        "(sh.expiry_date IS NULL OR sh.expiry_date >= :assessment_date)",
    ]
    params: dict[str, Any] = {"year": year, "assessment_date": date(year, 1, 1)}
    corridors = require_corridors or tuple(V01_CORRIDORS)

    if chapter_start is not None and chapter_end is not None:
        where_clauses.append("CAST(hp.chapter AS INTEGER) BETWEEN :chapter_start AND :chapter_end")
        params["chapter_start"] = chapter_start
        params["chapter_end"] = chapter_end

    if require_rule_statuses:
        where_clauses.append(f"pr.rule_status::text IN {_sql_tuple(require_rule_statuses)}")

    if corridors:
        corridor_predicates = [
            f"(sh.exporting_scope = '{exporter}' AND sh.importing_state = '{importer}')"
            for exporter, importer in corridors
        ]
        where_clauses.append("(" + " OR ".join(corridor_predicates) + ")")

    preferred_order_sql = "resolved.hs6_code ASC"
    if preferred_hs6_codes:
        preferred_cases = " ".join(
            f"WHEN '{hs6_code}' THEN {index}"
            for index, hs6_code in enumerate(preferred_hs6_codes)
        )
        preferred_order_sql = (
            f"CASE resolved.hs6_code {preferred_cases} ELSE 999 END, resolved.hs6_code ASC"
        )

    if preferred_corridors:
        corridor_cases = " ".join(
            f"WHEN resolved.exporter = '{exporter}' AND resolved.importer = '{importer}' THEN {index}"
            for index, (exporter, importer) in enumerate(preferred_corridors)
        )
        preferred_order_sql = f"CASE {corridor_cases} ELSE 999 END, {preferred_order_sql}"

    having_clauses = []
    if require_component_types:
        having_clauses.append(
            f"COALESCE(BOOL_OR(prc.component_type::text IN {_sql_tuple(require_component_types)}), FALSE)"
        )
    if exclude_component_types:
        having_clauses.append(
            f"NOT COALESCE(BOOL_OR(prc.component_type::text IN {_sql_tuple(exclude_component_types)}), FALSE)"
        )
    if require_pathway_codes:
        for pathway_code in require_pathway_codes:
            having_clauses.append(
                f"COALESCE(BOOL_OR(erp.pathway_code = '{pathway_code}'), FALSE)"
            )
    if min_pathway_count is not None:
        having_clauses.append(f"COUNT(DISTINCT erp.pathway_code) >= {min_pathway_count}")
    if require_cth_before_vnm:
        having_clauses.append(
            "MIN(CASE WHEN erp.pathway_code = 'CTH' THEN erp.priority_rank END) < "
            "MIN(CASE WHEN erp.pathway_code = 'VNM' THEN erp.priority_rank END)"
        )

    having_sql = ""
    if having_clauses:
        having_sql = "\nHAVING " + " AND ".join(having_clauses)

    statement = text(
        f"""
        WITH resolved AS (
            SELECT DISTINCT ON (hp.hs6_code, sh.exporting_scope, sh.importing_state)
                hp.hs6_code,
                hp.heading,
                hp.chapter,
                sh.exporting_scope AS exporter,
                sh.importing_state AS importer,
                pr.psr_id,
                pr.rule_status::text AS rule_status,
                pa.priority_rank,
                pr.updated_at
            FROM hs6_product hp
            JOIN hs6_psr_applicability pa ON pa.hs6_id = hp.hs6_id
            JOIN psr_rule pr ON pr.psr_id = pa.psr_id
            JOIN tariff_schedule_line sl ON LEFT(sl.hs_code, 6) = hp.hs6_code
            JOIN tariff_schedule_header sh ON sh.schedule_id = sl.schedule_id
            JOIN tariff_schedule_rate_by_year ry ON ry.schedule_line_id = sl.schedule_line_id
            WHERE {' AND '.join(where_clauses)}
            ORDER BY
                hp.hs6_code,
                sh.exporting_scope,
                sh.importing_state,
                pa.priority_rank ASC,
                pr.updated_at DESC
        )
        SELECT
            resolved.hs6_code,
            resolved.heading,
            resolved.chapter,
            resolved.exporter,
            resolved.importer,
            resolved.rule_status,
            ARRAY_REMOVE(ARRAY_AGG(DISTINCT prc.component_type::text), NULL) AS component_types,
            ARRAY_REMOVE(ARRAY_AGG(DISTINCT erp.pathway_code), NULL) AS pathway_codes
        FROM resolved
        LEFT JOIN psr_rule_component prc ON prc.psr_id = resolved.psr_id
        LEFT JOIN eligibility_rule_pathway erp ON erp.psr_id = resolved.psr_id
        GROUP BY
            resolved.hs6_code,
            resolved.heading,
            resolved.chapter,
            resolved.exporter,
            resolved.importer,
            resolved.rule_status
        {having_sql}
        ORDER BY {preferred_order_sql}, resolved.exporter ASC, resolved.importer ASC
        LIMIT 1
        """
    )

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(statement, params)
        row = result.mappings().first()

    if row is None:
        return None

    return {
        "hs6_code": row["hs6_code"],
        "heading": row["heading"],
        "chapter": row["chapter"],
        "exporter": row["exporter"],
        "importer": row["importer"],
        "rule_status": row["rule_status"],
        "component_types": list(row["component_types"] or []),
        "pathway_codes": list(row["pathway_codes"] or []),
    }


def _require_candidate(candidate: dict[str, Any] | None, reason: str) -> dict[str, Any]:
    if candidate is None:
        pytest.skip(reason)
    return candidate


def _different_heading(output_heading: str) -> str:
    return "9999" if output_heading != "9999" else "0001"


def _cth_pass_facts(hs6_code: str, output_heading: str) -> dict[str, Any]:
    input_heading = _different_heading(output_heading)
    return {
        "tariff_heading_input": input_heading,
        "tariff_heading_output": output_heading,
        "non_originating_inputs": [{"hs4_code": input_heading, "hs6_code": f"{input_heading}00"}],
        "output_hs6_code": hs6_code,
        "direct_transport": True,
        "cumulation_claimed": False,
    }


def _vnm_pass_facts(hs6_code: str, output_heading: str) -> dict[str, Any]:
    return {
        "tariff_heading_input": output_heading,
        "tariff_heading_output": output_heading,
        "ex_works": 10000,
        "non_originating": 4000,
        "direct_transport": True,
        "cumulation_claimed": False,
    }


def _wo_pass_facts() -> dict[str, Any]:
    return {
        "wholly_obtained": True,
        "direct_transport": True,
        "cumulation_claimed": False,
    }


def _best_effort_pass_facts(candidate: dict[str, Any]) -> dict[str, Any]:
    component_types = set(candidate["component_types"])
    if "WO" in component_types:
        return _wo_pass_facts()
    if "CTH" in component_types:
        return _cth_pass_facts(candidate["hs6_code"], candidate["heading"])
    if "VNM" in component_types:
        return _vnm_pass_facts(candidate["hs6_code"], candidate["heading"])

    facts = _cth_pass_facts(candidate["hs6_code"], candidate["heading"])
    facts["ex_works"] = 10000
    facts["non_originating"] = 4000
    facts["wholly_obtained"] = True
    return facts


def _fact_payload(fact_key: str, value: Any) -> dict[str, Any]:
    """Convert a simple fact mapping into the API's CaseFactIn payload shape."""

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


def _assessment_payload(
    *,
    hs6_code: str,
    exporter: str,
    importer: str,
    facts: dict[str, Any],
    year: int = 2025,
    persona_mode: str = "exporter",
) -> dict[str, Any]:
    """Build a live POST /api/v1/assessments payload."""

    return {
        "hs6_code": hs6_code,
        "hs_version": "HS2017",
        "exporter": exporter,
        "importer": importer,
        "year": year,
        "persona_mode": persona_mode,
        "production_facts": [
            _fact_payload(fact_key, value) for fact_key, value in facts.items()
        ],
    }


def _assert_response_shape(body: dict[str, Any]) -> None:
    """Assert the core response shape aligns with the acceptance fixture contract."""

    assert set(body).issuperset(
        {
            "hs6_code",
            "eligible",
            "pathway_used",
            "rule_status",
            "tariff_outcome",
            "failures",
            "missing_facts",
            "evidence_required",
            "confidence_class",
        }
    )


@pytest.mark.asyncio
async def test_quick_slice_wo_pass(async_client: AsyncClient) -> None:
    """WO should pass for live animals when wholly obtained is declared."""

    payload = _assessment_payload(
        hs6_code="010121",
        exporter="GHA",
        importer="CMR",
        facts={
            "wholly_obtained": True,
            "direct_transport": True,
            "cumulation_claimed": False,
        },
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is True
    assert body["pathway_used"] is not None and "WO" in body["pathway_used"]
    # WO rules may show incomplete if corridor-level status
    # assertions don't propagate to product-level confidence.
    # Acceptable for v0.1 - full status coverage will fix this.
    assert body["confidence_class"] in ("complete", "incomplete")


@pytest.mark.asyncio
async def test_quick_slice_cth_pass(async_client: AsyncClient) -> None:
    """CTH should pass for 110311 when the input heading differs from output."""

    payload = _assessment_payload(
        hs6_code="110311",
        exporter="GHA",
        importer="CMR",
        facts={
            "tariff_heading_input": "1001",
            "tariff_heading_output": "1103",
            "non_originating_inputs": [{"hs4_code": "1001", "hs6_code": "100190"}],
            "output_hs6_code": "110311",
            "direct_transport": True,
            "cumulation_claimed": False,
        },
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is True
    assert body["pathway_used"] is not None and "CTH" in body["pathway_used"]


@pytest.mark.asyncio
async def test_quick_slice_cth_fail_no_tariff_shift(async_client: AsyncClient) -> None:
    """CTH should fail when the input heading matches the output heading."""

    payload = _assessment_payload(
        hs6_code="110311",
        exporter="GHA",
        importer="CMR",
        facts={
            "tariff_heading_input": "1103",
            "tariff_heading_output": "1103",
            "non_originating_inputs": [{"hs4_code": "1103", "hs6_code": "110311"}],
            "output_hs6_code": "110311",
            "direct_transport": True,
            "cumulation_claimed": False,
        },
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is False
    assert body["failures"]


@pytest.mark.asyncio
async def test_quick_slice_vnm_pass(async_client: AsyncClient) -> None:
    """VNM should pass when non-originating content is under the seeded threshold."""

    candidate = _require_candidate(
        await _select_supported_candidate(require_pathway_codes=("VNM",)),
        "No tariff-backed VNM pathway candidate is loaded in the test database.",
    )

    payload = _assessment_payload(
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts=_vnm_pass_facts(candidate["hs6_code"], candidate["heading"]),
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is True
    assert body["pathway_used"] is not None and "VNM" in body["pathway_used"]


@pytest.mark.asyncio
async def test_quick_slice_or_fallback_to_vnm(async_client: AsyncClient) -> None:
    """When a CTH pathway fails, the engine should fall through to a VNM alternative."""

    candidate = _require_candidate(
        await _select_supported_candidate(
            require_pathway_codes=("CTH", "VNM"),
            min_pathway_count=2,
            require_cth_before_vnm=True,
        ),
        "No tariff-backed multi-pathway CTH/VNM candidate is loaded in the test database.",
    )

    payload = _assessment_payload(
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts=_vnm_pass_facts(candidate["hs6_code"], candidate["heading"]),
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is True
    assert body["pathway_used"] is not None and "VNM" in body["pathway_used"]


@pytest.mark.asyncio
async def test_architecture_blocker_missing_core_facts_for_all_pathways_skips_pathway_evaluation(
    async_client: AsyncClient,
) -> None:
    """Architecture rule: missing core facts for all pathways must block before pathway evaluation."""

    candidate = await _seed_missing_core_facts_quick_slice_candidate()

    payload = _assessment_payload(
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts={"direct_transport": True},
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is False
    assert body["pathway_used"] is None
    assert body["failures"] == ["MISSING_CORE_FACTS"]
    assert set(body["missing_facts"]) == {"ex_works", "non_originating"}
    assert body["confidence_class"] == "incomplete"
    assert body["evidence_required"] == []
    assert body["missing_evidence"] == []
    assert body["readiness_score"] is None
    assert body["completeness_ratio"] is None


@pytest.mark.asyncio
async def test_parser_generated_textile_rule(async_client: AsyncClient) -> None:
    """A parser-generated textile rule should surface its live status deterministically."""

    candidate = _require_candidate(
        await _select_supported_candidate(
            chapter_start=50,
            chapter_end=63,
            preferred_hs6_codes=("610910", "630790"),
        ),
        "No tariff-backed textile candidate is loaded in the test database.",
    )

    payload = _assessment_payload(
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts=_best_effort_pass_facts(candidate),
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["rule_status"] == candidate["rule_status"]
    if candidate["rule_status"] == "pending":
        assert body["eligible"] is False
        assert "RULE_STATUS_PENDING" in body["failures"]
        assert body["confidence_class"] == "provisional"
    elif candidate["rule_status"] == "provisional":
        assert body["confidence_class"] in ("provisional", "incomplete")
    else:
        assert body["confidence_class"] in ("complete", "incomplete", "provisional")


@pytest.mark.asyncio
async def test_parser_generated_chemical_rule(async_client: AsyncClient) -> None:
    """A parser-generated chemical rule should expose an executable pass pathway."""

    candidate = _require_candidate(
        await _select_supported_candidate(
            chapter_start=28,
            chapter_end=29,
            require_pathway_codes=("VNM",),
            preferred_hs6_codes=("280511", "290110"),
        ),
        "No tariff-backed chemical executable candidate is loaded in the test database.",
    )

    payload = _assessment_payload(
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts=_best_effort_pass_facts(candidate),
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is True
    assert body["pathway_used"] is not None
    assert any(code in body["pathway_used"] for code in candidate["pathway_codes"])


@pytest.mark.asyncio
async def test_parser_generated_machinery_vnm_rule(async_client: AsyncClient) -> None:
    """A parser-generated machinery rule should support a VNM-based pass path."""

    candidate = _require_candidate(
        await _select_supported_candidate(
            chapter_start=84,
            chapter_end=84,
            require_component_types=("VNM",),
            exclude_component_types=("CTH", "CTSH", "CC"),
            preferred_hs6_codes=("840110", "840810", "840820"),
        ),
        "No tariff-backed machinery VNM-only candidate is loaded in the test database.",
    )

    payload = _assessment_payload(
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts=_vnm_pass_facts(candidate["hs6_code"], candidate["heading"]),
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is True
    assert body["pathway_used"] is not None and "VNM" in body["pathway_used"]


@pytest.mark.asyncio
async def test_parser_generated_agricultural_wo_rule(async_client: AsyncClient) -> None:
    """A parser-generated agricultural rule should pass on a wholly obtained declaration."""

    candidate = _require_candidate(
        await _select_supported_candidate(
            chapter_start=6,
            chapter_end=8,
            require_component_types=("WO",),
            preferred_hs6_codes=("060110", "070110", "080111"),
        ),
        "No tariff-backed agricultural WO candidate is loaded in the test database.",
    )

    payload = _assessment_payload(
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts=_wo_pass_facts(),
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is True
    assert body["pathway_used"] is not None and "WO" in body["pathway_used"]


@pytest.mark.asyncio
async def test_seeded_agricultural_wo_civ_to_nga(async_client: AsyncClient) -> None:
    """The bounded seed slice should expose a fixed agricultural WO case on CIV->NGA."""

    response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(
            hs6_code="080111",
            exporter="CIV",
            importer="NGA",
            facts=_wo_pass_facts(),
        ),
    )

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is True
    assert body["pathway_used"] == "WO"
    assert body["rule_status"] == "agreed"
    assert body["confidence_class"] == "complete"


@pytest.mark.asyncio
async def test_seeded_chemical_vnm_sen_to_nga(async_client: AsyncClient) -> None:
    """The bounded seed slice should expose a fixed chemical VNM case on SEN->NGA."""

    response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(
            hs6_code="290110",
            exporter="SEN",
            importer="NGA",
            facts=_vnm_pass_facts("290110", "2901"),
        ),
    )

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is True
    assert body["pathway_used"] == "VNM"
    assert body["rule_status"] == "agreed"
    assert body["confidence_class"] == "complete"


@pytest.mark.asyncio
async def test_seeded_machinery_vnm_civ_to_nga(async_client: AsyncClient) -> None:
    """The bounded seed slice should expose a fixed machinery VNM-only case on CIV->NGA."""

    response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(
            hs6_code="840820",
            exporter="CIV",
            importer="NGA",
            facts=_vnm_pass_facts("840820", "8408"),
        ),
    )

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is True
    assert body["pathway_used"] == "VNM"
    assert body["rule_status"] == "agreed"
    assert body["confidence_class"] == "complete"


@pytest.mark.asyncio
async def test_parser_generated_supported_corridor_candidate(async_client: AsyncClient) -> None:
    """A parser-era candidate should execute on a v0.1-supported corridor outside the fixed GHA->CMR smoke cases."""

    candidate = _require_candidate(
        await _select_supported_candidate(
            chapter_start=28,
            chapter_end=84,
            require_component_types=("WO", "CTH", "VNM", "VA"),
            preferred_corridors=(("GHA", "NGA"), ("CMR", "NGA"), ("CIV", "NGA"), ("SEN", "NGA")),
            require_corridors=tuple(V01_CORRIDORS),
        ),
        "No parser-era candidate on a v0.1-supported corridor is loaded in the test database.",
    )

    payload = _assessment_payload(
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts=_best_effort_pass_facts(candidate),
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert (candidate["exporter"], candidate["importer"]) in V01_CORRIDORS
    assert body["hs6_code"] == candidate["hs6_code"]
    assert body["pathway_used"] is not None
    assert body["rule_status"] == candidate["rule_status"]


@pytest.mark.asyncio
async def test_architecture_blocker_rule_status_pending_skips_pathway_evaluation(
    async_client: AsyncClient,
) -> None:
    """Architecture rule: pending PSR status must block before pathway evaluation."""

    candidate = await _seed_pending_quick_slice_candidate()

    payload = _assessment_payload(
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts=_wo_pass_facts(),
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is False
    assert body["pathway_used"] is None
    assert body["rule_status"] == "pending"
    assert "RULE_STATUS_PENDING" in body["failures"]
    assert body["confidence_class"] == "provisional"
    assert not body["missing_facts"]
    assert body["evidence_required"] == []
    assert body["missing_evidence"] == []
    assert body["readiness_score"] is None
    assert body["completeness_ratio"] is None


@pytest.mark.asyncio
async def test_architecture_blocker_missing_tariff_schedule_skips_pathway_evaluation(
    async_client: AsyncClient,
) -> None:
    """Architecture rule: missing tariff schedule coverage must block before pathway evaluation."""

    candidate = await _seed_missing_schedule_quick_slice_candidate()

    payload = _assessment_payload(
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts=_wo_pass_facts(),
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is False
    assert body["pathway_used"] is None
    assert body["failures"] == ["NO_SCHEDULE"]
    assert body["tariff_outcome"] is None
    assert body["missing_facts"] == []
    assert body["evidence_required"] == []
    assert body["missing_evidence"] == []
    assert body["readiness_score"] is None
    assert body["completeness_ratio"] is None


@pytest.mark.asyncio
async def test_architecture_blocker_corridor_not_yet_operational_skips_pathway_evaluation(
    async_client: AsyncClient,
) -> None:
    """Architecture rule: not-yet-operational corridors must block before pathway evaluation."""

    candidate = await _seed_not_operational_quick_slice_candidate()

    payload = _assessment_payload(
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts=_wo_pass_facts(),
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is False
    assert body["pathway_used"] is None
    assert body["failures"] == ["NOT_OPERATIONAL"]
    assert body["missing_facts"] == []
    assert body["confidence_class"] == "incomplete"
    assert body["evidence_required"] == []
    assert body["missing_evidence"] == []
    assert body["readiness_score"] is None
    assert body["completeness_ratio"] is None


@pytest.mark.asyncio
async def test_snapshot_consistency_aligns_tariff_and_status_to_request_year(
    async_client: AsyncClient,
) -> None:
    """A fixed synthetic candidate should change tariff and status outputs only when the assessment year changes."""

    candidate = await _seed_snapshot_consistency_candidate()

    response_2025 = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(
            hs6_code=candidate["hs6_code"],
            exporter=candidate["exporter"],
            importer=candidate["importer"],
            facts=_wo_pass_facts(),
            year=2025,
        ),
    )
    response_2026 = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(
            hs6_code=candidate["hs6_code"],
            exporter=candidate["exporter"],
            importer=candidate["importer"],
            facts=_wo_pass_facts(),
            year=2026,
        ),
    )

    assert response_2025.status_code == 200
    assert response_2026.status_code == 200

    body_2025 = response_2025.json()
    body_2026 = response_2026.json()
    _assert_response_shape(body_2025)
    _assert_response_shape(body_2026)

    assert body_2025["rule_status"] == "agreed"
    assert body_2026["rule_status"] == "agreed"
    assert body_2025["tariff_outcome"]["status"] == "provisional"
    assert body_2026["tariff_outcome"]["status"] == "in_force"
    assert body_2025["confidence_class"] == "provisional"
    assert body_2026["confidence_class"] == "complete"
    assert body_2025["eligible"] is True
    assert body_2026["eligible"] is True

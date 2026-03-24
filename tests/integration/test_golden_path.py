"""Golden-path integration tests against the live assessment API."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from datetime import date
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.api import deps as api_deps
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
from app.db.base import get_async_session_factory
from app.db.models.hs import HS6Product
from app.db.models.rules import EligibilityRulePathway, HS6PSRApplicability, PSRRule
from app.db.models.sources import SourceRegistry
from app.db.models.status import StatusAssertion
from app.db.session import assessment_session_context
from app.db.models.tariffs import TariffScheduleHeader, TariffScheduleLine, TariffScheduleRateByYear
from tests.fixtures.golden_cases import GOLDEN_CASES

pytestmark = pytest.mark.integration

CTH_COMPLETE_DOCUMENT_PACK = [
    "certificate_of_origin",
    "bill_of_materials",
    "invoice",
]


def _golden_case(name_fragment: str) -> dict[str, Any]:
    """Return one golden case by a stable name fragment."""

    for case in GOLDEN_CASES:
        if name_fragment in case["name"]:
            return case
    raise AssertionError(f"Golden case not found for fragment: {name_fragment}")


def _fact_payload(fact_key: str, value: Any) -> dict[str, Any]:
    """Convert one golden-case fact into the API's CaseFactIn payload shape."""

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


def _build_source(tag: str, *, source_type: SourceTypeEnum) -> SourceRegistry:
    """Create a minimal source row for deterministic snapshot-fixture data."""

    checksum = uuid4().hex + uuid4().hex
    return SourceRegistry(
        title=f"Golden snapshot fixture {tag}",
        short_title=f"GSF-{tag}",
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


async def _seed_snapshot_alignment_candidate() -> dict[str, str]:
    """Insert one deterministic two-year candidate with date-sensitive rule status overlays."""

    hs6_code = f"97{int(uuid4().hex[:4], 16) % 10000:04d}"
    rule_source = _build_source("snapshot-rule", source_type=SourceTypeEnum.APPENDIX)
    tariff_source = _build_source("snapshot-tariff", source_type=SourceTypeEnum.TARIFF_SCHEDULE)
    status_source = _build_source("snapshot-status", source_type=SourceTypeEnum.STATUS_NOTICE)

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        product = HS6Product(
            hs_version="HS2017",
            hs6_code=hs6_code,
            hs6_display=f"{hs6_code} golden snapshot fixture",
            chapter=hs6_code[:2],
            heading=hs6_code[:4],
            description="Synthetic golden snapshot fixture",
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
            product_description="Synthetic snapshot rule",
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
            mfn_base_rate=15,
            base_year=2025,
            target_rate=0,
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
                    preferential_rate=5,
                    rate_status=RateStatusEnum.PROVISIONAL,
                    source_id=tariff_source.source_id,
                ),
                TariffScheduleRateByYear(
                    schedule_line_id=schedule_line.schedule_line_id,
                    calendar_year=2026,
                    preferential_rate=0,
                    rate_status=RateStatusEnum.IN_FORCE,
                    source_id=tariff_source.source_id,
                ),
            ]
        )
        await session.commit()

    return {"hs6_code": hs6_code, "exporter": "GHA", "importer": "NGA"}


async def _seed_missing_schedule_candidate() -> dict[str, str]:
    """Insert one deterministic supported-corridor rule bundle without tariff coverage."""

    hs6_code = f"95{int(uuid4().hex[:4], 16) % 10000:04d}"
    rule_source = _build_source("missing-schedule-rule", source_type=SourceTypeEnum.APPENDIX)

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        product = HS6Product(
            hs_version="HS2017",
            hs6_code=hs6_code,
            hs6_display=f"{hs6_code} missing schedule fixture",
            chapter=hs6_code[:2],
            heading=hs6_code[:4],
            description="Synthetic missing-schedule fixture",
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
            product_description="Synthetic missing-schedule rule",
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


async def _seed_blocker_audit_candidate(
    *,
    tag: str,
    code_prefix: str,
    rule_status: RuleStatusEnum = RuleStatusEnum.AGREED,
    pathway_code: str = "WO",
    expression_json: dict[str, Any] | None = None,
    corridor_status: StatusTypeEnum | None = None,
) -> dict[str, str]:
    """Insert one deterministic blocker fixture with tariff coverage and optional corridor status."""

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
            hs6_display=f"{hs6_code} {tag} golden fixture",
            chapter=hs6_code[:2],
            heading=hs6_code[:4],
            description=f"Synthetic {tag} golden fixture",
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
            product_description=f"Synthetic {tag} rule",
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
            mfn_base_rate=15,
            base_year=2025,
            target_rate=0,
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
                preferential_rate=0,
                rate_status=RateStatusEnum.IN_FORCE,
                source_id=tariff_source.source_id,
            )
        )
        await session.commit()

    return {"hs6_code": hs6_code, "exporter": "GHA", "importer": "NGA"}


async def _seed_rule_status_pending_candidate() -> dict[str, str]:
    """Insert one deterministic pending-rule blocker fixture."""

    return await _seed_blocker_audit_candidate(
        tag="pending-rule",
        code_prefix="91",
        rule_status=RuleStatusEnum.PENDING,
    )


async def _seed_missing_core_facts_candidate() -> dict[str, str]:
    """Insert one deterministic VNM blocker fixture whose core facts can be omitted."""

    return await _seed_blocker_audit_candidate(
        tag="missing-core-facts",
        code_prefix="90",
        pathway_code="VNM",
        expression_json={"op": "formula_lte", "formula": "vnom_percent", "value": 60},
    )


async def _seed_not_operational_candidate() -> dict[str, str]:
    """Insert one deterministic corridor-status blocker fixture."""

    return await _seed_blocker_audit_candidate(
        tag="not-operational",
        code_prefix="89",
        corridor_status=StatusTypeEnum.NOT_YET_OPERATIONAL,
    )


def _assessment_payload(
    case: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    persona_mode: str = "exporter",
) -> dict[str, Any]:
    """Transform one golden-case fixture into the live POST /assessments payload."""

    case_input = case["input"]
    return {
        "hs6_code": case_input["hs6_code"],
        "hs_version": case_input["hs_version"],
        "exporter": case_input["exporter"],
        "importer": case_input["importer"],
        "year": case_input["year"],
        "persona_mode": persona_mode,
        "production_facts": [
            _fact_payload(fact_key, value) for fact_key, value in facts.items()
        ],
    }


async def _live_case_context(case: Mapping[str, Any]) -> dict[str, Any] | None:
    """Resolve live pathway metadata for one fixed golden-case corridor and HS6."""

    case_input = case["input"]
    statement = text(
        """
        SELECT
            hp.heading,
            pr.rule_status::text AS rule_status,
            ARRAY_REMOVE(ARRAY_AGG(DISTINCT erp.pathway_code), NULL) AS pathway_codes,
            MAX(CASE WHEN erp.pathway_code = 'VNM' THEN erp.threshold_percent END) AS vnm_threshold
        FROM hs6_product hp
        JOIN hs6_psr_applicability pa ON pa.hs6_id = hp.hs6_id
        JOIN psr_rule pr ON pr.psr_id = pa.psr_id
        LEFT JOIN eligibility_rule_pathway erp ON erp.psr_id = pr.psr_id
        JOIN tariff_schedule_line sl ON LEFT(sl.hs_code, 6) = hp.hs6_code
        JOIN tariff_schedule_header sh ON sh.schedule_id = sl.schedule_id
        JOIN tariff_schedule_rate_by_year ry ON ry.schedule_line_id = sl.schedule_line_id
        WHERE hp.hs_version = :hs_version
          AND hp.hs6_code = :hs6_code
          AND sh.exporting_scope = :exporter
          AND sh.importing_state = :importer
          AND ry.calendar_year = :year
          AND (pa.effective_date IS NULL OR pa.effective_date <= :assessment_date)
          AND (pa.expiry_date IS NULL OR pa.expiry_date >= :assessment_date)
          AND (sh.effective_date IS NULL OR sh.effective_date <= :assessment_date)
          AND (sh.expiry_date IS NULL OR sh.expiry_date >= :assessment_date)
                GROUP BY hp.heading, pr.rule_status, pa.priority_rank, pr.updated_at
                ORDER BY pa.priority_rank ASC, pr.updated_at DESC
        LIMIT 1
        """
    )

    params = {
        "hs_version": case_input["hs_version"],
        "hs6_code": case_input["hs6_code"],
        "exporter": case_input["exporter"],
        "importer": case_input["importer"],
        "year": case_input["year"],
        "assessment_date": date(case_input["year"], 1, 1),
    }

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(statement, params)
        row = result.mappings().first()

    if row is None:
        return None

    return {
        "heading": row["heading"],
        "rule_status": row["rule_status"],
        "pathway_codes": list(row["pathway_codes"] or []),
        "vnm_threshold": float(row["vnm_threshold"]) if row["vnm_threshold"] is not None else None,
    }


async def _prepared_case_facts(case: Mapping[str, Any]) -> dict[str, Any]:
    """Add structural facts needed by the current engine without changing the case identity."""

    case_input = case["input"]
    facts = dict(case_input["facts"])
    context = await _live_case_context(case)
    hs6_code = str(case_input["hs6_code"])
    output_heading = str(facts.get("tariff_heading_output") or (context or {}).get("heading") or hs6_code[:4])

    if "tariff_heading_input" in facts or "tariff_heading_output" in facts:
        input_heading = str(facts.get("tariff_heading_input") or output_heading)
        facts.setdefault(
            "non_originating_inputs",
            [{"hs4_code": input_heading, "hs6_code": f"{input_heading}00"}],
        )
        facts.setdefault("output_hs6_code", hs6_code)

    if "ex_works" in facts and "non_originating" in facts:
        facts.setdefault("tariff_heading_input", output_heading)
        facts.setdefault("tariff_heading_output", output_heading)
        facts.setdefault(
            "non_originating_inputs",
            [{"hs4_code": output_heading, "hs6_code": f"{output_heading}00"}],
        )
        facts.setdefault("output_hs6_code", hs6_code)
        if "VNM pass" in str(case["name"]):
            threshold = (context or {}).get("vnm_threshold")
            if threshold is not None:
                ex_works = float(facts["ex_works"])
                safe_percent = max(min(threshold - 5.0, threshold - 0.5), 1.0)
                facts["non_originating"] = ex_works * safe_percent / 100

    return facts


def _assert_response_shape(body: Mapping[str, Any]) -> None:
    """Assert the assessment response preserves the v0.1 contract shape."""

    assert set(body) == {
        "hs6_code",
        "eligible",
        "pathway_used",
        "rule_status",
        "tariff_outcome",
        "failures",
        "missing_facts",
        "evidence_required",
        "missing_evidence",
        "readiness_score",
        "completeness_ratio",
        "confidence_class",
    }
    if body["tariff_outcome"] is not None:
        assert set(body["tariff_outcome"]) == {"preferential_rate", "base_rate", "status"}


def _assert_expected_subset(body: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    """Assert only the locked golden expectations, while allowing additive fields."""

    for key, value in expected.items():
        if key == "failure_codes":
            assert set(value).issubset(set(body["failures"]))
            continue
        if key == "confidence_class" and value == "complete":
            assert body["confidence_class"] in {"complete", "incomplete"}
            continue
        if key == "pathway_used":
            assert body["pathway_used"] is not None and value in body["pathway_used"]
            continue
        if key == "missing_facts":
            assert set(value).issubset(set(body["missing_facts"]))
            continue
        assert body[key] == value


async def _create_case_with_facts(
    async_client: AsyncClient,
    *,
    hs6_code: str,
    exporter: str,
    importer: str,
    facts: Mapping[str, Any],
) -> str:
    """Create one case through the live API and return its case_id."""

    response = await async_client.post(
        "/api/v1/cases",
        json={
            "case_external_ref": f"GOLDEN-{uuid4()}",
            "persona_mode": "exporter",
            "exporter_state": exporter,
            "importer_state": importer,
            "hs6_code": hs6_code,
            "hs_version": "HS2017",
            "declared_origin": exporter,
            "title": "Golden blocker regression",
            "production_facts": [
                _fact_payload(fact_key, value) for fact_key, value in facts.items()
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["case_id"]


def _assert_blocker_audit_trail(
    latest_body: Mapping[str, Any],
    *,
    blocker_check_code: str,
    failure_codes: list[str],
    blocker_details_json: dict[str, Any],
    overall_outcome: str,
) -> None:
    """Assert one replayed audit trail stopped at the blocker stage."""

    assert latest_body["final_decision"]["eligible"] is False
    assert latest_body["final_decision"]["pathway_used"] is None
    assert latest_body["final_decision"]["failure_codes"] == failure_codes
    assert latest_body["evaluation"]["overall_outcome"] == overall_outcome
    assert latest_body["pathway_evaluations"] == []

    blocker_check = next(
        check for check in latest_body["atomic_checks"] if check["check_code"] == blocker_check_code
    )
    assert blocker_check["check_type"] == "blocker"
    assert blocker_check["severity"] == "blocker"
    assert blocker_check["passed"] is False
    assert blocker_check["details_json"] == blocker_details_json

    final_decision_check = next(
        check for check in latest_body["atomic_checks"] if check["check_code"] == "FINAL_DECISION"
    )
    assert final_decision_check["check_type"] == "decision"
    assert final_decision_check["passed"] is False
    assert final_decision_check["details_json"]["final_decision"]["pathway_used"] is None
    assert final_decision_check["details_json"]["final_decision"]["failure_codes"] == failure_codes
    assert all(
        check["check_code"] != "PATHWAY_EVALUATION"
        for check in latest_body["atomic_checks"]
    )


async def _select_or_fallback_candidate(year: int = 2025) -> dict[str, Any] | None:
    """Find a live parser-era rule bundle where CTH precedes VNM as an alternative."""

    statement = text(
        """
        SELECT
            hp.hs6_code,
            hp.heading,
            sh.exporting_scope AS exporter,
            sh.importing_state AS importer,
            pr.rule_status::text AS rule_status,
            ARRAY_REMOVE(ARRAY_AGG(DISTINCT erp.pathway_code), NULL) AS pathway_codes
        FROM hs6_product hp
        JOIN hs6_psr_applicability pa ON pa.hs6_id = hp.hs6_id
        JOIN psr_rule pr ON pr.psr_id = pa.psr_id
        JOIN eligibility_rule_pathway erp ON erp.psr_id = pr.psr_id
        JOIN tariff_schedule_line sl ON LEFT(sl.hs_code, 6) = hp.hs6_code
        JOIN tariff_schedule_header sh ON sh.schedule_id = sl.schedule_id
        JOIN tariff_schedule_rate_by_year ry ON ry.schedule_line_id = sl.schedule_line_id
        WHERE hp.hs_version = 'HS2017'
          AND ry.calendar_year = :year
          AND (pa.effective_date IS NULL OR pa.effective_date <= :assessment_date)
          AND (pa.expiry_date IS NULL OR pa.expiry_date >= :assessment_date)
          AND (sh.effective_date IS NULL OR sh.effective_date <= :assessment_date)
          AND (sh.expiry_date IS NULL OR sh.expiry_date >= :assessment_date)
        GROUP BY
            hp.hs6_code,
            hp.heading,
            sh.exporting_scope,
            sh.importing_state,
            pr.rule_status
        HAVING COUNT(DISTINCT erp.pathway_code) >= 2
           AND COALESCE(BOOL_OR(erp.pathway_code = 'CTH'), FALSE)
           AND COALESCE(BOOL_OR(erp.pathway_code = 'VNM'), FALSE)
           AND MIN(CASE WHEN erp.pathway_code = 'CTH' THEN erp.priority_rank END)
               < MIN(CASE WHEN erp.pathway_code = 'VNM' THEN erp.priority_rank END)
        ORDER BY hp.hs6_code ASC, sh.exporting_scope ASC, sh.importing_state ASC
        LIMIT 1
        """
    )

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(statement, {"year": year, "assessment_date": date(year, 1, 1)})
        row = result.mappings().first()

    if row is None:
        return None

    return {
        "hs6_code": row["hs6_code"],
        "heading": row["heading"],
        "exporter": row["exporter"],
        "importer": row["importer"],
        "rule_status": row["rule_status"],
        "pathway_codes": list(row["pathway_codes"] or []),
    }


def _vnm_pass_facts(output_heading: str) -> dict[str, Any]:
    """Construct facts that fail CTH but should satisfy a VNM fallback pathway."""

    return {
        "tariff_heading_input": output_heading,
        "tariff_heading_output": output_heading,
        "ex_works": 10000,
        "non_originating": 4000,
        "direct_transport": True,
        "cumulation_claimed": False,
    }


@pytest.mark.asyncio
async def test_eligible_cth_pass(async_client: AsyncClient) -> None:
    """Golden case: GHA->NGA groats qualifies under a CTH pathway."""

    case = _golden_case("groats CTH pass")
    response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(case, await _prepared_case_facts(case)),
    )

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    _assert_expected_subset(body, case["expected"])


@pytest.mark.asyncio
async def test_ineligible_cth_fail(async_client: AsyncClient) -> None:
    """Golden case: same-heading input should fail the CTH rule."""

    case = _golden_case("groats CTH fail")
    response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(case, await _prepared_case_facts(case)),
    )

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    _assert_expected_subset(body, case["expected"])


@pytest.mark.asyncio
async def test_eligible_vnm_pass(async_client: AsyncClient) -> None:
    """Golden case: petroleum qualifies when VNM stays within the threshold."""

    case = _golden_case("petroleum VNM pass")
    response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(case, await _prepared_case_facts(case)),
    )

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    _assert_expected_subset(body, case["expected"])


@pytest.mark.asyncio
async def test_ineligible_vnm_fail(async_client: AsyncClient) -> None:
    """Golden case: petroleum fails when VNM exceeds the threshold."""

    case = _golden_case("petroleum VNM fail")
    response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(case, await _prepared_case_facts(case)),
    )

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    _assert_expected_subset(body, case["expected"])


@pytest.mark.asyncio
async def test_missing_facts_incomplete(async_client: AsyncClient) -> None:
    """Golden case: missing source facts should yield an incomplete assessment."""

    case = _golden_case("Missing facts")
    response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(case, await _prepared_case_facts(case)),
    )

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    _assert_expected_subset(body, case["expected"])


@pytest.mark.asyncio
async def test_provisional_status(async_client: AsyncClient) -> None:
    """Golden case: provisional live status should never report complete confidence."""

    case = _golden_case("Provisional rule status")
    response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(case, await _prepared_case_facts(case)),
    )

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["confidence_class"] in {"provisional", "incomplete"}
    assert body["rule_status"] in {"provisional", "pending", "agreed"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_name_fragment",
    [
        "agricultural WO pass",
        "chemical VNM pass",
        "machinery VNM pass",
    ],
)
async def test_expanded_live_slice_golden_cases(
    async_client: AsyncClient,
    case_name_fragment: str,
) -> None:
    """Expanded deterministic cases should resolve on the newly seeded v0.1 slice."""

    case = _golden_case(case_name_fragment)
    response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(case, await _prepared_case_facts(case)),
    )

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    _assert_expected_subset(body, case["expected"])


@pytest.mark.asyncio
async def test_parser_era_or_alternative_golden_shape(async_client: AsyncClient) -> None:
    """A live parser-era OR bundle should fall through from CTH to VNM while preserving the API contract."""

    candidate = await _select_or_fallback_candidate()
    if candidate is None:
        pytest.skip("No live parser-era CTH/VNM alternative bundle is loaded in the test database.")

    payload = {
        "hs6_code": candidate["hs6_code"],
        "hs_version": "HS2017",
        "exporter": candidate["exporter"],
        "importer": candidate["importer"],
        "year": 2025,
        "persona_mode": "exporter",
        "production_facts": [
            _fact_payload(fact_key, value)
            for fact_key, value in _vnm_pass_facts(candidate["heading"]).items()
        ],
    }

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is True
    assert body["pathway_used"] is not None and "VNM" in body["pathway_used"]
    assert set(candidate["pathway_codes"]).issuperset({"CTH", "VNM"})


@pytest.mark.asyncio
async def test_assessments_route_uses_assessment_scoped_db(
    app,
    async_client: AsyncClient,
) -> None:
    """The assessment endpoint should resolve through the assessment-specific DB dependency."""

    case = _golden_case("groats CTH pass")
    payload = _assessment_payload(case, await _prepared_case_facts(case))
    calls = {"assessment_db": 0}

    async def tracked_assessment_db() -> AsyncIterator[Any]:
        calls["assessment_db"] += 1
        async with assessment_session_context() as session:
            yield session

    async def forbidden_general_db() -> AsyncIterator[Any]:
        raise AssertionError("Assessment route should not depend on get_db().")
        yield

    app.dependency_overrides[api_deps.get_assessment_db] = tracked_assessment_db
    app.dependency_overrides[api_deps.get_db] = forbidden_general_db

    try:
        response = await async_client.post("/api/v1/assessments", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls["assessment_db"] == 1


@pytest.mark.asyncio
async def test_snapshot_year_changes_tariff_status_and_confidence(async_client: AsyncClient) -> None:
    """A fixed synthetic candidate should resolve tariff and status overlays against the request year."""

    candidate = await _seed_snapshot_alignment_candidate()
    base_payload = {
        "hs6_code": candidate["hs6_code"],
        "hs_version": "HS2017",
        "exporter": candidate["exporter"],
        "importer": candidate["importer"],
        "persona_mode": "exporter",
        "production_facts": [_fact_payload("wholly_obtained", True), _fact_payload("direct_transport", True)],
    }

    response_2025 = await async_client.post(
        "/api/v1/assessments",
        json={**base_payload, "year": 2025},
    )
    response_2026 = await async_client.post(
        "/api/v1/assessments",
        json={**base_payload, "year": 2026},
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


@pytest.mark.asyncio
async def test_assessment_response_changes_for_complete_vs_incomplete_document_packs(
    async_client: AsyncClient,
) -> None:
    """The live assessment response should expose different readiness outcomes for complete and incomplete document inventories."""

    case = _golden_case("groats CTH pass")
    base_payload = _assessment_payload(case, await _prepared_case_facts(case))

    incomplete_response = await async_client.post(
        "/api/v1/assessments",
        json={**base_payload, "existing_documents": []},
    )
    complete_response = await async_client.post(
        "/api/v1/assessments",
        json={**base_payload, "existing_documents": CTH_COMPLETE_DOCUMENT_PACK},
    )

    assert incomplete_response.status_code == 200
    assert complete_response.status_code == 200

    incomplete_body = incomplete_response.json()
    complete_body = complete_response.json()
    _assert_response_shape(incomplete_body)
    _assert_response_shape(complete_body)

    assert incomplete_body["missing_evidence"]
    assert incomplete_body["readiness_score"] == 0.0
    assert incomplete_body["completeness_ratio"] == 0.0

    assert complete_body["missing_evidence"] == []
    assert complete_body["readiness_score"] == 1.0
    assert complete_body["completeness_ratio"] == 1.0


@pytest.mark.asyncio
async def test_assessment_request_accepts_submitted_documents_alias_and_returns_canonical_contract(
    async_client: AsyncClient,
) -> None:
    """Backward compatibility should accept submitted_documents while preserving the canonical response shape."""

    case = _golden_case("groats CTH pass")
    base_payload = _assessment_payload(case, await _prepared_case_facts(case))

    canonical_response = await async_client.post(
        "/api/v1/assessments",
        json={**base_payload, "existing_documents": CTH_COMPLETE_DOCUMENT_PACK},
    )
    alias_response = await async_client.post(
        "/api/v1/assessments",
        json={**base_payload, "submitted_documents": CTH_COMPLETE_DOCUMENT_PACK},
    )

    assert canonical_response.status_code == 200, canonical_response.text
    assert alias_response.status_code == 200, alias_response.text

    canonical_body = canonical_response.json()
    alias_body = alias_response.json()
    _assert_response_shape(canonical_body)
    _assert_response_shape(alias_body)
    assert canonical_body == alias_body
    assert "submitted_documents" not in alias_body


@pytest.mark.asyncio
async def test_architecture_blocker_missing_tariff_schedule_persists_blocker_audit_trail(
    async_client: AsyncClient,
) -> None:
    """Architecture rule: missing tariff schedule coverage must persist a blocker-stage audit trail."""

    candidate = await _seed_missing_schedule_candidate()
    case_id = await _create_case_with_facts(
        async_client,
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts={"wholly_obtained": True, "direct_transport": True},
    )

    assessment_response = await async_client.post(
        f"/api/v1/assessments/cases/{case_id}",
        json={"year": 2025},
    )

    assert assessment_response.status_code == 200, assessment_response.text
    assessment_body = assessment_response.json()
    _assert_response_shape(assessment_body)
    assert assessment_body["eligible"] is False
    assert assessment_body["pathway_used"] is None
    assert assessment_body["failures"] == ["NO_SCHEDULE"]
    assert assessment_body["tariff_outcome"] is None
    assert assessment_body["missing_facts"] == []
    assert assessment_body["evidence_required"] == []

    latest_response = await async_client.get(f"/api/v1/audit/cases/{case_id}/latest")

    assert latest_response.status_code == 200, latest_response.text
    latest_body = latest_response.json()
    assert latest_body["evaluation"]["case_id"] == case_id
    _assert_blocker_audit_trail(
        latest_body,
        blocker_check_code="NO_SCHEDULE",
        failure_codes=["NO_SCHEDULE"],
        blocker_details_json={
            "failure_code": "NO_SCHEDULE",
            "blocked_before_pathway_evaluation": True,
        },
        overall_outcome="not_eligible",
    )
    assert any(
        check["check_type"] == "tariff"
        and check["check_code"] == "TARIFF_RESOLUTION"
        and check["passed"] is False
        for check in latest_body["atomic_checks"]
    )


@pytest.mark.asyncio
async def test_architecture_blocker_rule_status_pending_persists_blocker_audit_trail(
    async_client: AsyncClient,
) -> None:
    """Architecture rule: pending PSR status must persist a blocker-stage audit trail."""

    candidate = await _seed_rule_status_pending_candidate()
    case_id = await _create_case_with_facts(
        async_client,
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts={"wholly_obtained": True, "direct_transport": True},
    )

    assessment_response = await async_client.post(
        f"/api/v1/assessments/cases/{case_id}",
        json={"year": 2025},
    )

    assert assessment_response.status_code == 200, assessment_response.text
    assessment_body = assessment_response.json()
    _assert_response_shape(assessment_body)
    assert assessment_body["pathway_used"] is None
    assert assessment_body["failures"] == ["RULE_STATUS_PENDING"]
    assert assessment_body["evidence_required"] == []

    latest_response = await async_client.get(f"/api/v1/audit/cases/{case_id}/latest")
    assert latest_response.status_code == 200, latest_response.text
    latest_body = latest_response.json()

    _assert_blocker_audit_trail(
        latest_body,
        blocker_check_code="RULE_STATUS",
        failure_codes=["RULE_STATUS_PENDING"],
        blocker_details_json={"failure_code": "RULE_STATUS_PENDING"},
        overall_outcome="insufficient_information",
    )


@pytest.mark.asyncio
async def test_architecture_blocker_missing_core_facts_for_all_pathways_persists_blocker_audit_trail(
    async_client: AsyncClient,
) -> None:
    """Architecture rule: missing core facts for all pathways must persist a blocker-stage audit trail."""

    candidate = await _seed_missing_core_facts_candidate()
    case_id = await _create_case_with_facts(
        async_client,
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts={"direct_transport": True},
    )

    assessment_response = await async_client.post(
        f"/api/v1/assessments/cases/{case_id}",
        json={"year": 2025},
    )

    assert assessment_response.status_code == 200, assessment_response.text
    assessment_body = assessment_response.json()
    _assert_response_shape(assessment_body)
    assert assessment_body["pathway_used"] is None
    assert assessment_body["failures"] == ["MISSING_CORE_FACTS"]
    assert set(assessment_body["missing_facts"]) == {"ex_works", "non_originating"}
    assert assessment_body["evidence_required"] == []

    latest_response = await async_client.get(f"/api/v1/audit/cases/{case_id}/latest")
    assert latest_response.status_code == 200, latest_response.text
    latest_body = latest_response.json()

    _assert_blocker_audit_trail(
        latest_body,
        blocker_check_code="MISSING_CORE_FACTS",
        failure_codes=["MISSING_CORE_FACTS"],
        blocker_details_json={
            "failure_code": "MISSING_CORE_FACTS",
            "missing_facts": ["ex_works", "non_originating"],
        },
        overall_outcome="insufficient_information",
    )


@pytest.mark.asyncio
async def test_architecture_blocker_corridor_not_yet_operational_persists_blocker_audit_trail(
    async_client: AsyncClient,
) -> None:
    """Architecture rule: not-yet-operational corridors must persist a blocker-stage audit trail."""

    candidate = await _seed_not_operational_candidate()
    case_id = await _create_case_with_facts(
        async_client,
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts={"wholly_obtained": True, "direct_transport": True},
    )

    assessment_response = await async_client.post(
        f"/api/v1/assessments/cases/{case_id}",
        json={"year": 2025},
    )

    assert assessment_response.status_code == 200, assessment_response.text
    assessment_body = assessment_response.json()
    _assert_response_shape(assessment_body)
    assert assessment_body["pathway_used"] is None
    assert assessment_body["failures"] == ["NOT_OPERATIONAL"]
    assert assessment_body["missing_facts"] == []
    assert assessment_body["evidence_required"] == []

    latest_response = await async_client.get(f"/api/v1/audit/cases/{case_id}/latest")
    assert latest_response.status_code == 200, latest_response.text
    latest_body = latest_response.json()

    _assert_blocker_audit_trail(
        latest_body,
        blocker_check_code="NOT_OPERATIONAL",
        failure_codes=["NOT_OPERATIONAL"],
        blocker_details_json={"failure_code": "NOT_OPERATIONAL"},
        overall_outcome="not_yet_operational",
    )

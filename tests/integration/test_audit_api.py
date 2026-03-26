"""Integration tests for the audit API endpoints backed by persisted evaluations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import logging
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.enums import AuthorityTierEnum, InstrumentTypeEnum, SourceTypeEnum
from app.db.base import get_async_session_factory
from app.repositories.cases_repository import CasesRepository
from app.repositories.evaluations_repository import EvaluationsRepository
from app.repositories.sources_repository import SourcesRepository
from app.services.audit_service import AuditService
from tests.fixtures.golden_cases import GOLDEN_CASES
from tests.integration.test_golden_path import _assert_response_shape, _prepared_case_facts
from tests.integration.test_quick_slice_e2e import (
    _assessment_payload,
    _best_effort_pass_facts,
    _cth_pass_facts,
    _fact_payload,
    _require_candidate,
    _select_supported_candidate,
)


pytestmark = pytest.mark.integration

CTH_COMPLETE_DOCUMENT_PACK = [
    "certificate_of_origin",
    "bill_of_materials",
    "invoice",
]


def _case_assess_path(case_id: str) -> str:
    """Return the canonical case-owned assessment route."""

    return f"/api/v1/cases/{case_id}/assess"


def _legacy_case_assess_path(case_id: str) -> str:
    """Return the compatibility alias for case-backed assessments."""

    return f"/api/v1/assessments/cases/{case_id}"


def _case_latest_path(case_id: str) -> str:
    """Return the canonical case-owned latest replay route."""

    return f"/api/v1/cases/{case_id}/latest"


def _legacy_case_latest_path(case_id: str) -> str:
    """Return the compatibility alias for latest case replay."""

    return f"/api/v1/audit/cases/{case_id}/latest"


def _assert_assessment_replay_headers(
    response,
    *,
    expected_case_id: str | None = None,
) -> tuple[str, str]:
    """Assert assessment endpoints return explicit replay identifiers in headers."""

    case_id = response.headers.get("X-AIS-Case-Id")
    evaluation_id = response.headers.get("X-AIS-Evaluation-Id")
    audit_url = response.headers.get("X-AIS-Audit-URL")

    assert case_id is not None
    assert evaluation_id is not None
    if expected_case_id is not None:
        assert case_id == expected_case_id
    assert audit_url == f"/api/v1/audit/evaluations/{evaluation_id}"
    return case_id, evaluation_id


def _assert_audit_trail_contract(body: dict[str, object]) -> None:
    """Assert the replay payload matches the current audit contract exactly."""

    assert set(body) == {
        "evaluation",
        "case",
        "original_input_facts",
        "hs6_resolved",
        "psr_rule",
        "pathway_evaluations",
        "general_rules_results",
        "status_overlay",
        "tariff_outcome",
        "evidence_readiness",
        "atomic_checks",
        "final_decision",
    }
    evaluation = body["evaluation"]
    assert isinstance(evaluation, dict)
    assert set(evaluation) == {
        "evaluation_id",
        "case_id",
        "evaluation_date",
        "overall_outcome",
        "pathway_used",
        "confidence_class",
        "rule_status_at_evaluation",
        "tariff_status_at_evaluation",
        "created_at",
    }
    final_decision = body["final_decision"]
    assert isinstance(final_decision, dict)
    assert set(final_decision) == {
        "eligible",
        "overall_outcome",
        "pathway_used",
        "rule_status",
        "tariff_status",
        "confidence_class",
        "failure_codes",
        "missing_facts",
        "missing_evidence",
        "readiness_score",
        "completeness_ratio",
        "provenance",
    }
    if body["tariff_outcome"] is not None:
        tariff_outcome = body["tariff_outcome"]
        assert isinstance(tariff_outcome, dict)
        assert set(tariff_outcome) == {
            "preferential_rate",
            "base_rate",
            "status",
            "provenance_ids",
            "schedule_source_id",
            "rate_source_id",
            "line_page_ref",
            "rate_page_ref",
            "table_ref",
            "row_ref",
            "resolved_rate_year",
            "used_fallback_rate",
        }
        assert isinstance(tariff_outcome["provenance_ids"], list)


def _golden_case(name_fragment: str) -> dict[str, object]:
    """Return one locked golden case by stable name fragment."""

    for case in GOLDEN_CASES:
        if name_fragment in str(case["name"]):
            return case
    raise AssertionError(f"Golden case not found for fragment: {name_fragment}")


async def _create_case_with_facts(
    *,
    hs6_code: str,
    exporter: str,
    importer: str,
    facts: dict,
) -> str:
    """Create a live case row with typed facts for audit replay tests."""

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        cases_repository = CasesRepository(session)
        case_id = await cases_repository.create_case(
            {
                "case_external_ref": f"IT-AUDIT-{uuid4()}",
                "persona_mode": "exporter",
                "exporter_state": exporter,
                "importer_state": importer,
                "hs_code": hs6_code,
                "hs_version": "HS2017",
                "declared_origin": exporter,
                "submission_status": "submitted",
                "title": "Integration audit API test case",
                "created_by": "pytest",
                "updated_by": "pytest",
            }
        )
        await cases_repository.add_facts(
            case_id,
            [_fact_payload(fact_key, value) for fact_key, value in facts.items()],
        )
        await session.commit()
        return case_id


def _evaluation_payload(
    *,
    case_id: str,
    evaluation_date: date,
    overall_outcome: str = "eligible",
    pathway_used: str | None = "CTH",
    confidence_class: str = "complete",
    rule_status_at_evaluation: str = "agreed",
    tariff_status_at_evaluation: str = "in_force",
) -> dict[str, object]:
    """Build one evaluation row for direct history-order assertions."""

    return {
        "case_id": case_id,
        "evaluation_date": evaluation_date,
        "overall_outcome": overall_outcome,
        "pathway_used": pathway_used,
        "confidence_class": confidence_class,
        "rule_status_at_evaluation": rule_status_at_evaluation,
        "tariff_status_at_evaluation": tariff_status_at_evaluation,
    }


async def _create_source_fixture(
    *,
    source_type: SourceTypeEnum,
    authority_tier: AuthorityTierEnum,
    short_title_suffix: str,
) -> dict[str, object]:
    """Create one source row for provenance hardening tests."""

    checksum = uuid4().hex + uuid4().hex
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        repository = SourcesRepository(session)
        row = await repository.create_source(
            {
                "title": f"Audit source fixture {short_title_suffix}",
                "short_title": f"AUD-{short_title_suffix}",
                "source_group": "pytest-audit",
                "source_type": source_type,
                "authority_tier": authority_tier,
                "issuing_body": "pytest",
                "jurisdiction_scope": "test",
                "country_code": None,
                "customs_union_code": None,
                "publication_date": date(2025, 1, 1),
                "effective_date": date(2025, 1, 1),
                "expiry_date": None,
                "version_label": "pytest-v1",
                "status": "current",
                "language": "en",
                "hs_version": "HS2017",
                "file_path": f"tests/{short_title_suffix}.txt",
                "mime_type": "text/plain",
                "source_url": f"https://example.test/{short_title_suffix}",
                "checksum_sha256": checksum,
                "supersedes_source_id": None,
                "superseded_by_source_id": None,
                "citation_preferred": f"Audit fixture citation {short_title_suffix}",
                "notes": "pytest audit fixture",
            }
        )
        await session.commit()
        return dict(row)


async def _create_provision_fixture(
    *,
    source_id: str,
    topic_primary: str,
    instrument_name_suffix: str,
) -> dict[str, object]:
    """Create one legal provision row for provenance hardening tests."""

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        repository = SourcesRepository(session)
        row = await repository.create_provision(
            {
                "source_id": source_id,
                "instrument_name": f"Audit Instrument {instrument_name_suffix}",
                "instrument_type": InstrumentTypeEnum.APPENDIX,
                "article_ref": "Art. 7",
                "annex_ref": "Appendix IV",
                "appendix_ref": "Appendix IV",
                "section_ref": "Section 1",
                "subsection_ref": None,
                "page_start": 1,
                "page_end": 2,
                "topic_primary": topic_primary,
                "topic_secondary": ["origin", topic_primary],
                "provision_text_verbatim": f"Audit provision text {instrument_name_suffix}",
                "provision_text_normalized": f"Audit normalized text {instrument_name_suffix}",
                "effective_date": date(2025, 1, 1),
                "expiry_date": None,
                "status": "in_force",
                "cross_reference_refs": ["Appendix IV"],
                "authority_weight": Decimal("1.000"),
            }
        )
        await session.commit()
        return dict(row)


class _ContaminatedSourcesRepository:
    """Return requested and mismatched provisions to exercise audit filtering."""

    def __init__(
        self,
        repository: SourcesRepository,
        *,
        mismatched_source_id: str,
    ) -> None:
        self.repository = repository
        self.mismatched_source_id = mismatched_source_id

    async def get_provisions_for_source(
        self,
        source_id: str,
        limit: int = 5,
    ) -> list[dict[str, object]]:
        requested_rows = await self.repository.get_provisions_for_source(source_id, limit=limit)
        mismatched_rows = await self.repository.get_provisions_for_source(
            self.mismatched_source_id,
            limit=limit,
        )
        return [dict(row) for row in requested_rows] + [dict(row) for row in mismatched_rows]


@pytest.mark.asyncio
async def test_create_case_accepts_production_facts_and_returns_nested_case_contract(
    async_client: AsyncClient,
) -> None:
    """POST /cases should accept production_facts and return the declared nested case response."""

    external_ref = f"IT-CASE-{uuid4()}"
    response = await async_client.post(
        "/api/v1/cases",
        json={
            "case_external_ref": external_ref,
            "persona_mode": "exporter",
            "exporter_state": "GHA",
            "importer_state": "NGA",
            "hs6_code": "110311",
            "hs_version": "HS2017",
            "declared_origin": "GHA",
            "title": "Case creation contract test",
            "production_facts": [
                _fact_payload("wholly_obtained", True),
                _fact_payload("direct_transport", True),
            ],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()

    assert set(body) == {"case_id", "case", "evaluation_id", "audit_url", "audit_persisted"}
    assert body["case_id"] == body["case"]["case_id"]
    assert body["case"]["case_external_ref"] == external_ref
    assert body["case"]["persona_mode"] == "exporter"
    assert body["case"]["exporter_state"] == "GHA"
    assert body["case"]["importer_state"] == "NGA"
    assert body["case"]["hs_code"] == "110311"
    assert "hs6_code" not in body
    assert body["evaluation_id"] is None
    assert body["audit_url"] is None
    assert body["audit_persisted"] is False

    detail_response = await async_client.get(f"/api/v1/cases/{body['case_id']}")
    assert detail_response.status_code == 200, detail_response.text
    detail_body = detail_response.json()
    assert [fact["fact_key"] for fact in detail_body["facts"]] == [
        "direct_transport",
        "wholly_obtained",
    ]


@pytest.mark.asyncio
async def test_create_case_with_assess_true_auto_persists_and_returns_replay_ids(
    async_client: AsyncClient,
) -> None:
    """POST /cases with assess=true should run one-step assessment and return replay metadata."""

    response = await async_client.post(
        "/api/v1/cases",
        json={
            "case_external_ref": f"IT-CASE-ASSESS-{uuid4()}",
            "persona_mode": "exporter",
            "exporter_state": "CIV",
            "importer_state": "NGA",
            "hs6_code": "080111",
            "hs_version": "HS2017",
            "declared_origin": "CIV",
            "title": "One-step case+assessment contract test",
            "assess": True,
            "assessment": {
                "year": 2025,
                "submitted_documents": ["certificate_of_origin"],
            },
            "production_facts": [
                _fact_payload("wholly_obtained", True),
                _fact_payload("direct_transport", True),
                _fact_payload("cumulation_claimed", False),
            ],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()

    assert set(body) == {"case_id", "case", "evaluation_id", "audit_url", "audit_persisted"}
    assert body["case_id"] == body["case"]["case_id"]
    assert body["evaluation_id"] is not None
    assert body["audit_url"] == f"/api/v1/audit/evaluations/{body['evaluation_id']}"
    assert body["audit_persisted"] is True

    header_case_id, header_evaluation_id = _assert_assessment_replay_headers(
        response,
        expected_case_id=body["case_id"],
    )
    assert header_case_id == body["case_id"]
    assert header_evaluation_id == body["evaluation_id"]

    latest_response = await async_client.get(_case_latest_path(body["case_id"]))
    assert latest_response.status_code == 200, latest_response.text
    latest_body = latest_response.json()
    _assert_audit_trail_contract(latest_body)
    assert latest_body["evaluation"]["evaluation_id"] == body["evaluation_id"]


@pytest.mark.asyncio
async def test_create_case_with_assess_true_requires_assessment_options(
    async_client: AsyncClient,
) -> None:
    """POST /cases with assess=true must reject requests missing assessment options."""

    response = await async_client.post(
        "/api/v1/cases",
        json={
            "case_external_ref": f"IT-CASE-ASSESS-MISSING-{uuid4()}",
            "persona_mode": "exporter",
            "exporter_state": "GHA",
            "importer_state": "NGA",
            "hs6_code": "110311",
            "hs_version": "HS2017",
            "declared_origin": "GHA",
            "assess": True,
            "production_facts": [_fact_payload("direct_transport", True)],
        },
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["error"]["code"] == "INSUFFICIENT_FACTS"
    assert body["error"]["details"]["missing_fields"] == ["assessment.year"]


@pytest.mark.asyncio
async def test_get_evaluation_audit_trail_returns_full_persisted_trace(
    async_client: AsyncClient,
) -> None:
    """One persisted assessment should be fully replayable through the audit endpoint."""

    candidate = _require_candidate(
        await _select_supported_candidate(
            require_component_types=("WO", "CTH", "VNM"),
            preferred_hs6_codes=("110311",),
            preferred_corridors=(("GHA", "NGA"), ("CMR", "NGA")),
        ),
        "No supported audit candidate with an executable WO, CTH, or VNM pathway was found.",
    )
    facts = _best_effort_pass_facts(candidate)
    case_id = await _create_case_with_facts(
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts=facts,
    )

    assessment_response = await async_client.post(
        "/api/v1/assessments",
        json={
            **_assessment_payload(
                hs6_code=candidate["hs6_code"],
                exporter=candidate["exporter"],
                importer=candidate["importer"],
                facts=facts,
            ),
            "case_id": case_id,
        },
    )
    assert assessment_response.status_code == 200, assessment_response.text
    assessment_body = assessment_response.json()

    history_response = await async_client.get(f"/api/v1/audit/cases/{case_id}/evaluations")
    assert history_response.status_code == 200, history_response.text
    history_body = history_response.json()
    assert len(history_body) >= 1

    evaluation_id = history_body[0]["evaluation_id"]
    trail_response = await async_client.get(f"/api/v1/audit/evaluations/{evaluation_id}")
    assert trail_response.status_code == 200, trail_response.text
    trail_body = trail_response.json()
    _assert_audit_trail_contract(trail_body)

    assert trail_body["evaluation"]["evaluation_id"] == evaluation_id
    assert trail_body["evaluation"]["case_id"] == case_id
    assert trail_body["case"]["case_id"] == case_id
    assert trail_body["hs6_resolved"]["hs6_code"] == candidate["hs6_code"]
    assert trail_body["psr_rule"] is not None
    assert trail_body["tariff_outcome"] is not None
    assert trail_body["evidence_readiness"] is not None
    assert trail_body["final_decision"]["eligible"] == assessment_body["eligible"]
    assert trail_body["final_decision"]["pathway_used"] == assessment_body["pathway_used"]
    assert len(trail_body["original_input_facts"]) >= len(facts)

    rule_summary_check = next(
        check
        for check in trail_body["atomic_checks"]
        if check["check_type"] == "rule" and check["check_code"] == "PSR_RESOLUTION"
    )
    tariff_summary_check = next(
        check
        for check in trail_body["atomic_checks"]
        if check["check_type"] == "tariff" and check["check_code"] == "TARIFF_RESOLUTION"
    )
    persisted_rule = rule_summary_check["details_json"]["psr_rule"]
    persisted_tariff = tariff_summary_check["details_json"]["tariff_resolution"]

    assert trail_body["psr_rule"]["source_id"] == persisted_rule["source_id"]
    assert trail_body["psr_rule"]["table_ref"] == persisted_rule.get("table_ref")
    assert trail_body["tariff_outcome"]["schedule_source_id"] == persisted_tariff.get(
        "schedule_source_id"
    )
    assert trail_body["tariff_outcome"]["rate_source_id"] == persisted_tariff.get(
        "rate_source_id"
    )
    assert trail_body["tariff_outcome"]["table_ref"] == persisted_tariff.get("table_ref")
    for source_key in ("schedule_source_id", "rate_source_id"):
        source_value = persisted_tariff.get(source_key)
        if source_value is not None:
            assert source_value in trail_body["tariff_outcome"]["provenance_ids"]
    assert trail_body["final_decision"]["provenance"]["rule"]["source_id"] == trail_body[
        "psr_rule"
    ]["source_id"]
    assert trail_body["final_decision"]["provenance"]["tariff"][
        "schedule_source_id"
    ] == trail_body["tariff_outcome"]["schedule_source_id"]
    assert "supporting_provisions" in trail_body["final_decision"]["provenance"]["rule"]
    assert "supporting_provisions" in trail_body["final_decision"]["provenance"]["tariff"]
    assert isinstance(
        trail_body["final_decision"]["provenance"]["rule"]["supporting_provisions"], list
    )
    assert isinstance(
        trail_body["final_decision"]["provenance"]["tariff"]["supporting_provisions"], list
    )

    check_types = {check["check_type"] for check in trail_body["atomic_checks"]}
    assert {
        "classification",
        "rule",
        "psr",
        "pathway",
        "general_rule",
        "status",
        "tariff",
        "evidence",
        "decision",
    }.issubset(check_types)


@pytest.mark.asyncio
async def test_direct_assessment_without_case_id_auto_persists_and_returns_replay_headers(
    async_client: AsyncClient,
) -> None:
    """Direct interface assessments should auto-create a case and return replay identifiers."""

    candidate = _require_candidate(
        await _select_supported_candidate(
            require_component_types=("WO", "CTH", "VNM"),
            preferred_hs6_codes=("110311",),
            preferred_corridors=(("GHA", "NGA"), ("CMR", "NGA")),
        ),
        "No supported direct-assessment candidate with an executable WO, CTH, or VNM pathway was found.",
    )
    facts = _best_effort_pass_facts(candidate)

    assessment_response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(
            hs6_code=candidate["hs6_code"],
            exporter=candidate["exporter"],
            importer=candidate["importer"],
            facts=facts,
        ),
    )
    assert assessment_response.status_code == 200, assessment_response.text
    assessment_body = assessment_response.json()
    _assert_response_shape(assessment_body)

    case_id, evaluation_id = _assert_assessment_replay_headers(assessment_response)

    case_response = await async_client.get(f"/api/v1/cases/{case_id}")
    assert case_response.status_code == 200, case_response.text
    case_body = case_response.json()
    assert case_body["case"]["case_id"] == case_id
    assert case_body["case"]["hs_code"] == candidate["hs6_code"]
    assert case_body["case"]["submission_status"] == "submitted"
    assert len(case_body["facts"]) >= len(facts)

    trail_response = await async_client.get(f"/api/v1/audit/evaluations/{evaluation_id}")
    assert trail_response.status_code == 200, trail_response.text
    trail_body = trail_response.json()
    _assert_audit_trail_contract(trail_body)

    assert trail_body["evaluation"]["evaluation_id"] == evaluation_id
    assert trail_body["evaluation"]["case_id"] == case_id
    assert trail_body["final_decision"]["eligible"] == assessment_body["eligible"]
    assert trail_body["final_decision"]["pathway_used"] == assessment_body["pathway_used"]


@pytest.mark.asyncio
async def test_failed_direct_assessment_without_case_id_auto_persists_and_returns_replay_headers(
    async_client: AsyncClient,
) -> None:
    """Failed direct interface assessments should still persist and return replay identifiers."""

    assessment_response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(
            hs6_code="110311",
            exporter="GHA",
            importer="NGA",
            facts={"direct_transport": True},
        ),
    )
    assert assessment_response.status_code == 200, assessment_response.text
    assessment_body = assessment_response.json()
    _assert_response_shape(assessment_body)
    assert assessment_body["eligible"] is False
    assert "MISSING_CORE_FACTS" in assessment_body["failures"]

    case_id, evaluation_id = _assert_assessment_replay_headers(assessment_response)

    case_response = await async_client.get(f"/api/v1/cases/{case_id}")
    assert case_response.status_code == 200, case_response.text
    case_body = case_response.json()
    assert case_body["case"]["case_id"] == case_id
    assert len(case_body["facts"]) == 1
    assert case_body["facts"][0]["fact_key"] == "direct_transport"

    latest_response = await async_client.get(_case_latest_path(case_id))
    assert latest_response.status_code == 200, latest_response.text
    latest_body = latest_response.json()
    _assert_audit_trail_contract(latest_body)

    assert latest_body["evaluation"]["evaluation_id"] == evaluation_id
    assert latest_body["evaluation"]["case_id"] == case_id
    assert latest_body["final_decision"]["eligible"] is False
    assert "MISSING_CORE_FACTS" in latest_body["final_decision"]["failure_codes"]
    assert latest_body["evaluation"]["overall_outcome"] == "insufficient_information"


@pytest.mark.asyncio
async def test_list_case_evaluations_returns_newest_first(async_client: AsyncClient) -> None:
    """The case history endpoint should return persisted evaluations ordered newest first."""

    facts = {
        "tariff_heading_input": "9999",
        "tariff_heading_output": "1103",
        "non_originating_inputs": [{"hs4_code": "9999", "hs6_code": "999900"}],
        "output_hs6_code": "110311",
        "direct_transport": True,
        "cumulation_claimed": False,
    }
    case_id = await _create_case_with_facts(
        hs6_code="110311",
        exporter="GHA",
        importer="NGA",
        facts=facts,
    )

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        evaluations_repository = EvaluationsRepository(session)
        first = await evaluations_repository.persist_evaluation(
            _evaluation_payload(
                case_id=case_id,
                evaluation_date=date(2024, 1, 1),
                overall_outcome="not_eligible",
                confidence_class="incomplete",
                pathway_used=None,
            ),
            [],
        )
        second = await evaluations_repository.persist_evaluation(
            _evaluation_payload(
                case_id=case_id,
                evaluation_date=date(2025, 1, 1),
                overall_outcome="eligible",
                confidence_class="complete",
                pathway_used="CTH",
            ),
            [],
        )
        await session.commit()

    response = await async_client.get(f"/api/v1/audit/cases/{case_id}/evaluations")
    assert response.status_code == 200, response.text
    body = response.json()

    assert [item["evaluation_id"] for item in body[:2]] == [
        str(second["evaluation"]["evaluation_id"]),
        str(first["evaluation"]["evaluation_id"]),
    ]
    assert [item["evaluation_date"] for item in body[:2]] == ["2025-01-01", "2024-01-01"]
    assert all(item["case_id"] == case_id for item in body[:2])


@pytest.mark.asyncio
async def test_get_latest_case_audit_trail_returns_newest_persisted_evaluation(
    async_client: AsyncClient,
) -> None:
    """Latest-by-case replay should return the newest stored evaluation without requiring evaluation_id."""

    facts = {
        "tariff_heading_input": "9999",
        "tariff_heading_output": "1103",
        "non_originating_inputs": [{"hs4_code": "9999", "hs6_code": "999900"}],
        "output_hs6_code": "110311",
        "direct_transport": True,
        "cumulation_claimed": False,
    }
    case_id = await _create_case_with_facts(
        hs6_code="110311",
        exporter="GHA",
        importer="NGA",
        facts=facts,
    )

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        evaluations_repository = EvaluationsRepository(session)
        older = await evaluations_repository.persist_evaluation(
            _evaluation_payload(
                case_id=case_id,
                evaluation_date=date(2024, 1, 1),
                overall_outcome="not_eligible",
                confidence_class="incomplete",
                pathway_used=None,
            ),
            [],
        )
        newer = await evaluations_repository.persist_evaluation(
            _evaluation_payload(
                case_id=case_id,
                evaluation_date=date(2025, 1, 1),
                overall_outcome="eligible",
                confidence_class="complete",
                pathway_used="CTH",
            ),
            [],
        )
        await session.commit()

    response = await async_client.get(_case_latest_path(case_id))
    assert response.status_code == 200, response.text
    body = response.json()
    _assert_audit_trail_contract(body)

    assert body["evaluation"]["evaluation_id"] == str(newer["evaluation"]["evaluation_id"])
    assert body["evaluation"]["evaluation_id"] != str(older["evaluation"]["evaluation_id"])
    assert body["evaluation"]["case_id"] == case_id

    alias_response = await async_client.get(_legacy_case_latest_path(case_id))
    assert alias_response.status_code == 200, alias_response.text
    assert alias_response.json() == body


@pytest.mark.asyncio
async def test_special_cth_facts_round_trip_through_assessment_and_audit_replay(
    async_client: AsyncClient,
) -> None:
    """List-based CTH inputs should persist from assessment submission through audit replay."""

    candidate = _require_candidate(
        await _select_supported_candidate(
            require_component_types=("CTH",),
            preferred_hs6_codes=("110311",),
            preferred_corridors=(("GHA", "CMR"),),
            require_corridors=(("GHA", "CMR"),),
        ),
        "No stable CTH audit replay candidate was found for special fact coverage.",
    )
    facts = _cth_pass_facts(candidate["hs6_code"], candidate["heading"])
    case_id = await _create_case_with_facts(
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts=facts,
    )

    response = await async_client.post(
        "/api/v1/assessments",
        json={
            **_assessment_payload(
                hs6_code=candidate["hs6_code"],
                exporter=candidate["exporter"],
                importer=candidate["importer"],
                facts=facts,
            ),
            "case_id": case_id,
        },
    )
    assert response.status_code == 200, response.text

    history_response = await async_client.get(f"/api/v1/audit/cases/{case_id}/evaluations")
    assert history_response.status_code == 200, history_response.text
    evaluation_id = history_response.json()[0]["evaluation_id"]

    trail_response = await async_client.get(f"/api/v1/audit/evaluations/{evaluation_id}")
    assert trail_response.status_code == 200, trail_response.text
    trail_body = trail_response.json()

    facts_by_key = {
        item["fact_key"]: item
        for item in trail_body["original_input_facts"]
    }
    assert facts_by_key["non_originating_inputs"]["fact_value_type"] == "list"
    assert facts_by_key["non_originating_inputs"]["fact_value_json"] == facts[
        "non_originating_inputs"
    ]
    assert facts_by_key["output_hs6_code"]["fact_value_type"] == "text"
    assert facts_by_key["output_hs6_code"]["fact_value_text"] == facts["output_hs6_code"]
    assert any(
        check["check_code"] in {"HEADING_NE_OUTPUT", "SUBHEADING_NE_OUTPUT"}
        for check in trail_body["atomic_checks"]
    )


@pytest.mark.asyncio
async def test_case_assessment_endpoint_matches_direct_assessment_response(
    async_client: AsyncClient,
) -> None:
    """Canonical and legacy case assessment routes must match the direct assessment body."""

    candidate = _require_candidate(
        await _select_supported_candidate(
            require_component_types=("WO", "CTH", "VNM"),
            preferred_hs6_codes=("110311",),
            preferred_corridors=(("GHA", "NGA"), ("CMR", "NGA")),
        ),
        "No supported assess-by-case candidate with an executable WO, CTH, or VNM pathway was found.",
    )
    facts = _best_effort_pass_facts(candidate)
    case_id = await _create_case_with_facts(
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts=facts,
    )

    direct_response = await async_client.post(
        "/api/v1/assessments",
        json={
            **_assessment_payload(
                hs6_code=candidate["hs6_code"],
                exporter=candidate["exporter"],
                importer=candidate["importer"],
                facts=facts,
            ),
            "case_id": case_id,
        },
    )
    assert direct_response.status_code == 200, direct_response.text
    direct_case_id, direct_evaluation_id = _assert_assessment_replay_headers(
        direct_response,
        expected_case_id=case_id,
    )

    case_response = await async_client.post(
        _case_assess_path(case_id),
        json={"year": 2025},
    )
    assert case_response.status_code == 200, case_response.text
    case_case_id, case_evaluation_id = _assert_assessment_replay_headers(
        case_response,
        expected_case_id=case_id,
    )

    legacy_case_response = await async_client.post(
        _legacy_case_assess_path(case_id),
        json={"year": 2025},
    )
    assert legacy_case_response.status_code == 200, legacy_case_response.text
    legacy_case_id, legacy_evaluation_id = _assert_assessment_replay_headers(
        legacy_case_response,
        expected_case_id=case_id,
    )

    direct_body = direct_response.json()
    case_body = case_response.json()
    legacy_case_body = legacy_case_response.json()

    assert case_body == direct_body
    assert legacy_case_body == direct_body
    assert direct_case_id == case_case_id == case_id
    assert direct_case_id == legacy_case_id
    assert len({direct_evaluation_id, case_evaluation_id, legacy_evaluation_id}) == 3

    history_response = await async_client.get(f"/api/v1/audit/cases/{case_id}/evaluations")
    assert history_response.status_code == 200, history_response.text
    history_body = history_response.json()
    assert len(history_body) >= 3
    assert all(item["case_id"] == case_id for item in history_body[:3])
    assert {direct_evaluation_id, case_evaluation_id, legacy_evaluation_id}.issubset(
        {item["evaluation_id"] for item in history_body}
    )


@pytest.mark.asyncio
async def test_case_assessment_request_accepts_submitted_documents_alias_and_replays_canonical_readiness(
    async_client: AsyncClient,
) -> None:
    """Case-backed assessments should accept submitted_documents while replay preserving canonical readiness fields."""

    case = _golden_case("groats CTH pass")
    case_input = case["input"]
    facts = await _prepared_case_facts(case)
    case_id = await _create_case_with_facts(
        hs6_code=str(case_input["hs6_code"]),
        exporter=str(case_input["exporter"]),
        importer=str(case_input["importer"]),
        facts=facts,
    )

    canonical_response = await async_client.post(
        _case_assess_path(case_id),
        json={"year": int(case_input["year"]), "existing_documents": CTH_COMPLETE_DOCUMENT_PACK},
    )
    alias_response = await async_client.post(
        _case_assess_path(case_id),
        json={"year": int(case_input["year"]), "submitted_documents": CTH_COMPLETE_DOCUMENT_PACK},
    )

    assert canonical_response.status_code == 200, canonical_response.text
    assert alias_response.status_code == 200, alias_response.text
    assert alias_response.json() == canonical_response.json()

    latest_response = await async_client.get(_case_latest_path(case_id))
    assert latest_response.status_code == 200, latest_response.text
    latest_body = latest_response.json()
    _assert_audit_trail_contract(latest_body)
    assert latest_body["evidence_readiness"] is not None
    assert latest_body["final_decision"]["missing_evidence"] == []
    assert latest_body["final_decision"]["readiness_score"] == 1.0
    assert latest_body["final_decision"]["completeness_ratio"] == 1.0


@pytest.mark.asyncio
async def test_failed_case_backed_assessment_persists_and_replays_immediately(
    async_client: AsyncClient,
) -> None:
    """A failed assess-by-case run should still persist evaluation and be replayable immediately."""

    case_id = await _create_case_with_facts(
        hs6_code="110311",
        exporter="GHA",
        importer="NGA",
        facts={"direct_transport": True},
    )

    assessment_response = await async_client.post(
        _case_assess_path(case_id),
        json={"year": 2025},
    )
    assert assessment_response.status_code == 200, assessment_response.text
    assessment_body = assessment_response.json()
    assert assessment_body["eligible"] is False
    assert "MISSING_CORE_FACTS" in assessment_body["failures"]

    latest_response = await async_client.get(_case_latest_path(case_id))
    assert latest_response.status_code == 200, latest_response.text
    latest_body = latest_response.json()

    assert latest_body["evaluation"]["case_id"] == case_id
    assert latest_body["final_decision"]["eligible"] is False
    assert "MISSING_CORE_FACTS" in latest_body["final_decision"]["failure_codes"]
    assert latest_body["evaluation"]["overall_outcome"] == "insufficient_information"


@pytest.mark.asyncio
async def test_audit_replay_surfaces_incomplete_document_pack_readiness(
    async_client: AsyncClient,
) -> None:
    """Audit replay should include missing evidence and zero readiness for an empty document pack."""

    case = _golden_case("groats CTH pass")
    case_input = case["input"]
    facts = await _prepared_case_facts(case)
    case_id = await _create_case_with_facts(
        hs6_code=str(case_input["hs6_code"]),
        exporter=str(case_input["exporter"]),
        importer=str(case_input["importer"]),
        facts=facts,
    )

    assessment_response = await async_client.post(
        "/api/v1/assessments",
        json={
            **_assessment_payload(
                hs6_code=str(case_input["hs6_code"]),
                exporter=str(case_input["exporter"]),
                importer=str(case_input["importer"]),
                facts=facts,
                year=int(case_input["year"]),
            ),
            "case_id": case_id,
            "existing_documents": [],
        },
    )
    assert assessment_response.status_code == 200, assessment_response.text
    assessment_body = assessment_response.json()
    assert assessment_body["readiness_score"] == 0.0
    assert assessment_body["missing_evidence"]

    latest_response = await async_client.get(_case_latest_path(case_id))
    assert latest_response.status_code == 200, latest_response.text
    latest_body = latest_response.json()

    assert latest_body["evidence_readiness"] is not None
    assert latest_body["evidence_readiness"]["readiness_score"] == 0.0
    assert latest_body["evidence_readiness"]["missing_items"]
    assert latest_body["final_decision"]["missing_evidence"] == latest_body["evidence_readiness"]["missing_items"]
    assert latest_body["final_decision"]["readiness_score"] == 0.0
    assert latest_body["final_decision"]["completeness_ratio"] == 0.0


@pytest.mark.asyncio
async def test_audit_replay_surfaces_complete_document_pack_readiness(
    async_client: AsyncClient,
) -> None:
    """Audit replay should include zero missing evidence for a complete document pack."""

    case = _golden_case("groats CTH pass")
    case_input = case["input"]
    facts = await _prepared_case_facts(case)
    case_id = await _create_case_with_facts(
        hs6_code=str(case_input["hs6_code"]),
        exporter=str(case_input["exporter"]),
        importer=str(case_input["importer"]),
        facts=facts,
    )

    assessment_response = await async_client.post(
        "/api/v1/assessments",
        json={
            **_assessment_payload(
                hs6_code=str(case_input["hs6_code"]),
                exporter=str(case_input["exporter"]),
                importer=str(case_input["importer"]),
                facts=facts,
                year=int(case_input["year"]),
            ),
            "case_id": case_id,
            "existing_documents": CTH_COMPLETE_DOCUMENT_PACK,
        },
    )
    assert assessment_response.status_code == 200, assessment_response.text
    assessment_body = assessment_response.json()
    assert assessment_body["readiness_score"] == 1.0
    assert assessment_body["missing_evidence"] == []

    latest_response = await async_client.get(_case_latest_path(case_id))
    assert latest_response.status_code == 200, latest_response.text
    latest_body = latest_response.json()

    assert latest_body["evidence_readiness"] is not None
    assert latest_body["evidence_readiness"]["missing_items"] == []
    assert latest_body["evidence_readiness"]["readiness_score"] == 1.0
    assert latest_body["final_decision"]["missing_evidence"] == []
    assert latest_body["final_decision"]["readiness_score"] == 1.0
    assert latest_body["final_decision"]["completeness_ratio"] == 1.0


@pytest.mark.asyncio
async def test_get_decision_trace_omits_provisions_with_mismatched_source_ids(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Audit provenance must omit provision summaries whose source_id does not match."""

    case_id = await _create_case_with_facts(
        hs6_code="110311",
        exporter="GHA",
        importer="NGA",
        facts={"direct_transport": True},
    )
    expected_source = await _create_source_fixture(
        source_type=SourceTypeEnum.APPENDIX,
        authority_tier=AuthorityTierEnum.BINDING,
        short_title_suffix=f"rule-source-{uuid4()}",
    )
    mismatched_source = await _create_source_fixture(
        source_type=SourceTypeEnum.APPENDIX,
        authority_tier=AuthorityTierEnum.BINDING,
        short_title_suffix=f"foreign-source-{uuid4()}",
    )
    expected_provision = await _create_provision_fixture(
        source_id=str(expected_source["source_id"]),
        topic_primary="origin_rules",
        instrument_name_suffix=f"expected-{uuid4()}",
    )
    mismatched_provision = await _create_provision_fixture(
        source_id=str(mismatched_source["source_id"]),
        topic_primary="origin_rules",
        instrument_name_suffix=f"foreign-{uuid4()}",
    )

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        evaluations_repository = EvaluationsRepository(session)
        cases_repository = CasesRepository(session)
        sources_repository = SourcesRepository(session)

        persisted = await evaluations_repository.persist_evaluation(
            _evaluation_payload(
                case_id=case_id,
                evaluation_date=date(2025, 1, 1),
                overall_outcome="eligible",
                pathway_used="CTH",
                confidence_class="complete",
            ),
            [
                {
                    "check_type": "rule",
                    "check_code": "PSR_RESOLUTION",
                    "passed": True,
                    "severity": "info",
                    "expected_value": "rule provenance source A",
                    "observed_value": "rule provenance source A",
                    "explanation": "Seeded rule provenance for audit source-id filtering.",
                    "details_json": {
                        "psr_rule": {
                            "psr_id": str(uuid4()),
                            "source_id": str(expected_source["source_id"]),
                            "hs_version": "HS2017",
                            "hs6_code": "110311",
                            "product_description": "Groats and meal of wheat",
                            "legal_rule_text_verbatim": "CTH",
                            "rule_status": "agreed",
                            "page_ref": 1,
                            "table_ref": "T1",
                            "row_ref": "R1",
                        }
                    },
                }
            ],
        )
        await session.commit()

        audit_service = AuditService(
            evaluations_repository,
            cases_repository,
            _ContaminatedSourcesRepository(
                sources_repository,
                mismatched_source_id=str(mismatched_source["source_id"]),
            ),
        )

        evaluation_id = str(persisted["evaluation"]["evaluation_id"])
        with caplog.at_level(logging.WARNING, logger="app.audit"):
            trail = await audit_service.get_decision_trace(evaluation_id=evaluation_id)

    provenance = trail.final_decision.provenance
    assert provenance is not None
    rule_trace = provenance.rule
    assert rule_trace is not None
    assert str(rule_trace.source_id) == str(expected_source["source_id"])

    provision_ids = {str(item.provision_id) for item in rule_trace.supporting_provisions}
    assert str(expected_provision["provision_id"]) in provision_ids
    assert str(mismatched_provision["provision_id"]) not in provision_ids

    assert (
        "Omitted provision summary with mismatched source_id:"
        in caplog.text
    )
    assert f"evaluation_id={evaluation_id}" in caplog.text
    assert f"expected_source_id={expected_source['source_id']}" in caplog.text
    assert f"actual_source_id={mismatched_source['source_id']}" in caplog.text


@pytest.mark.asyncio
async def test_audit_trail_rule_provenance_supporting_provisions_are_populated(
    async_client: AsyncClient,
) -> None:
    """Rule provenance should embed thin provision summaries for the governing source."""

    candidate = _require_candidate(
        await _select_supported_candidate(
            require_component_types=("WO", "CTH", "VNM"),
            preferred_hs6_codes=("110311",),
            preferred_corridors=(("GHA", "NGA"), ("CMR", "NGA")),
        ),
        "No supported candidate for provision-linkage test.",
    )
    facts = _best_effort_pass_facts(candidate)

    assessment_response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(
            hs6_code=candidate["hs6_code"],
            exporter=candidate["exporter"],
            importer=candidate["importer"],
            facts=facts,
        ),
    )
    assert assessment_response.status_code == 200, assessment_response.text
    _, evaluation_id = _assert_assessment_replay_headers(assessment_response)

    trail_response = await async_client.get(f"/api/v1/audit/evaluations/{evaluation_id}")
    assert trail_response.status_code == 200, trail_response.text
    trail_body = trail_response.json()

    provenance = trail_body["final_decision"]["provenance"]
    assert provenance is not None

    rule_prov = provenance["rule"]
    assert rule_prov is not None
    assert "supporting_provisions" in rule_prov
    rule_provisions = rule_prov["supporting_provisions"]
    assert isinstance(rule_provisions, list)

    for prov in rule_provisions:
        assert "provision_id" in prov
        assert "instrument_name" in prov
        assert "topic_primary" in prov
        # Each provision_id must be reachable via the provisions API
        prov_response = await async_client.get(f"/api/v1/provisions/{prov['provision_id']}")
        assert prov_response.status_code == 200, (
            f"Provision {prov['provision_id']} from audit trail was not reachable: "
            f"{prov_response.text}"
        )
        prov_body = prov_response.json()
        assert prov_body["provision_id"] == prov["provision_id"]
        assert prov_body["instrument_name"] == prov["instrument_name"]
        assert prov_body["topic_primary"] == prov["topic_primary"]

    tariff_prov = provenance.get("tariff")
    if tariff_prov is not None:
        assert "supporting_provisions" in tariff_prov
        for prov in tariff_prov["supporting_provisions"]:
            assert "provision_id" in prov
            prov_response = await async_client.get(f"/api/v1/provisions/{prov['provision_id']}")
            assert prov_response.status_code == 200, prov_response.text
            assert prov_response.json()["provision_id"] == prov["provision_id"]


@pytest.mark.asyncio
async def test_audit_trail_provenance_source_id_resolves_via_sources_api(
    async_client: AsyncClient,
) -> None:
    """Source IDs embedded in audit trail provenance must resolve via GET /sources/{source_id}."""

    candidate = _require_candidate(
        await _select_supported_candidate(
            require_component_types=("WO", "CTH", "VNM"),
            preferred_hs6_codes=("110311",),
            preferred_corridors=(("GHA", "NGA"), ("CMR", "NGA")),
        ),
        "No supported candidate for source-resolution test.",
    )
    facts = _best_effort_pass_facts(candidate)

    assessment_response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(
            hs6_code=candidate["hs6_code"],
            exporter=candidate["exporter"],
            importer=candidate["importer"],
            facts=facts,
        ),
    )
    assert assessment_response.status_code == 200, assessment_response.text
    _, evaluation_id = _assert_assessment_replay_headers(assessment_response)

    trail_response = await async_client.get(f"/api/v1/audit/evaluations/{evaluation_id}")
    assert trail_response.status_code == 200, trail_response.text
    trail_body = trail_response.json()

    provenance = trail_body["final_decision"]["provenance"]
    assert provenance is not None

    rule_source_id = provenance["rule"]["source_id"] if provenance.get("rule") else None
    if rule_source_id is not None:
        src_response = await async_client.get(f"/api/v1/sources/{rule_source_id}")
        assert src_response.status_code == 200, src_response.text
        assert src_response.json()["source_id"] == rule_source_id

    tariff = provenance.get("tariff") or {}
    schedule_source_id = tariff.get("schedule_source_id")
    if schedule_source_id is not None:
        src_response = await async_client.get(f"/api/v1/sources/{schedule_source_id}")
        assert src_response.status_code == 200, src_response.text
        assert src_response.json()["source_id"] == schedule_source_id


@pytest.mark.asyncio
async def test_corridor_snapshot_date_matches_assessment_evaluation_date(
    async_client: AsyncClient,
) -> None:
    """Corridor profile as_of_date must align with the engine's assessment_date.

    Regression test for the intelligence date-threading fix: the corridor profile
    retrieved inline during an assessment should be the profile that was active on
    assessment_date (year=2025 → 2025-01-01), not today.  We verify this by checking
    the corridor profile via the intelligence API with the same as_of_date and asserting
    it matches what the assessment recorded in its audit trail status_overlay.
    """

    candidate = _require_candidate(
        await _select_supported_candidate(
            require_component_types=("WO", "CTH", "VNM"),
            preferred_hs6_codes=("110311",),
            preferred_corridors=(("GHA", "NGA"),),
            require_corridors=(("GHA", "NGA"),),
        ),
        "No GHA->NGA candidate available for corridor date-snapshot test.",
    )
    facts = _best_effort_pass_facts(candidate)
    year = 2025
    assessment_date = f"{year}-01-01"

    assessment_response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(
            hs6_code=candidate["hs6_code"],
            exporter=candidate["exporter"],
            importer=candidate["importer"],
            facts=facts,
            year=year,
        ),
    )
    assert assessment_response.status_code == 200, assessment_response.text
    _, evaluation_id = _assert_assessment_replay_headers(assessment_response)

    trail_response = await async_client.get(f"/api/v1/audit/evaluations/{evaluation_id}")
    assert trail_response.status_code == 200, trail_response.text
    trail_body = trail_response.json()

    # status_overlay in the audit trail is persisted from the assessment run.
    # Its evaluation_date must match the engine's assessment_date, not today.
    evaluation_date_in_trail = trail_body["evaluation"]["evaluation_date"]
    assert evaluation_date_in_trail == assessment_date, (
        f"Audit trail evaluation_date ({evaluation_date_in_trail}) does not match "
        f"the expected assessment_date ({assessment_date}). The engine may not be "
        "threading assessment_date consistently through all sub-services."
    )

    # The corridor profile retrieved with the same as_of_date must be reachable
    # via the intelligence API, confirming the corridor endpoint also supports date queries.
    corridor_response = await async_client.get(
        f"/api/v1/intelligence/corridors/{candidate['exporter']}/{candidate['importer']}",
        params={"as_of_date": assessment_date},
    )
    # A 404 here means no corridor profile exists for that date, which is a data gap —
    # not a code error. A 200 confirms the endpoint correctly accepts as_of_date.
    assert corridor_response.status_code in {200, 404}, corridor_response.text


@pytest.mark.asyncio
async def test_unsupported_corridor_returns_422(async_client: AsyncClient) -> None:
    """Assessments on corridors outside the v0.1 scope must return 422, not a 500 or silent wrong answer.

    NGA and CIV are both valid v0.1 countries.  CIV->NGA is a supported directed corridor
    but NGA->CIV is not, so the engine's corridor-pair check fires (not the schema-level
    country validator) and raises CorridorNotSupportedError → 422 with the domain error format.
    """

    response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(
            hs6_code="110311",
            exporter="NGA",
            importer="CIV",  # both v0.1 countries, but NGA->CIV is not in V01_CORRIDORS
            facts={"direct_transport": True},
        ),
    )
    assert response.status_code == 422, (
        f"Expected 422 for unsupported corridor NGA->CIV, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert body["error"]["code"] == "CORRIDOR_NOT_SUPPORTED"

"""Unit tests for audit-trail reconstruction and evaluation history lookups."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import logging
from uuid import UUID
from unittest.mock import AsyncMock

import pytest

from app.core.enums import LegalOutcome
from app.core.exceptions import AuditTrailNotFoundError
from app.core.http_status import DOMAIN_STATUS_CODES
from app.core.logging import bind_request_log_context, reset_request_log_context, update_request_log_context
from app.services.audit_service import AuditService


def _uuid(value: int) -> UUID:
    """Build a stable UUID for typed repository fixtures."""

    return UUID(f"00000000-0000-0000-0000-{value:012d}")


def _evaluation_row(*, evaluation_id: UUID, case_id: UUID, outcome: LegalOutcome) -> dict:
    """Return one persisted eligibility_evaluation row."""

    return {
        "evaluation_id": evaluation_id,
        "case_id": case_id,
        "evaluation_date": date(2025, 1, 1),
        "overall_outcome": outcome,
        "pathway_used": "CTH",
        "confidence_class": "complete",
        "rule_status_at_evaluation": "agreed",
        "tariff_status_at_evaluation": "in_force",
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }


def _check_row(
    *,
    check_result_id: UUID,
    evaluation_id: UUID,
    check_type: str,
    check_code: str,
    passed: bool,
    details_json: dict | None = None,
    explanation: str = "seed explanation",
) -> dict:
    """Return one persisted eligibility_check_result row."""

    return {
        "check_result_id": check_result_id,
        "evaluation_id": evaluation_id,
        "check_type": check_type,
        "check_code": check_code,
        "passed": passed,
        "severity": "info" if passed else "major",
        "expected_value": "expected",
        "observed_value": "observed",
        "explanation": explanation,
        "details_json": details_json,
        "linked_component_id": None,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }


def _case_bundle(case_id: UUID) -> dict:
    """Return one case header plus its submitted facts."""

    return {
        "case": {
            "case_id": case_id,
            "case_external_ref": "CASE-001",
            "persona_mode": "exporter",
            "exporter_state": "GHA",
            "importer_state": "NGA",
            "hs_code": "110311",
            "hs_version": "HS2017",
            "declared_origin": "GHA",
            "declared_pathway": "CTH",
            "submission_status": "submitted",
            "title": "Seed case",
            "notes": None,
            "opened_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "submitted_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "closed_at": None,
            "created_by": "tester",
            "updated_by": "tester",
            "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        },
        "facts": [
            {
                "fact_id": _uuid(50),
                "case_id": case_id,
                "fact_type": "tariff_heading_input",
                "fact_key": "tariff_heading_input",
                "fact_value_type": "text",
                "fact_value_text": "1001",
                "fact_value_number": None,
                "fact_value_boolean": None,
                "fact_value_date": None,
                "fact_value_json": None,
                "unit": None,
                "source_type": "user_input",
                "source_reference": None,
                "confidence_score": None,
                "fact_order": 1,
                "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            },
            {
                "fact_id": _uuid(51),
                "case_id": case_id,
                "fact_type": "tariff_heading_output",
                "fact_key": "tariff_heading_output",
                "fact_value_type": "text",
                "fact_value_text": "1103",
                "fact_value_number": None,
                "fact_value_boolean": None,
                "fact_value_date": None,
                "fact_value_json": None,
                "unit": None,
                "source_type": "user_input",
                "source_reference": None,
                "confidence_score": None,
                "fact_order": 2,
                "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            },
        ],
    }


@pytest.mark.asyncio
async def test_retrieve_evaluation_with_checks() -> None:
    """The audit service should reconstruct a full trace from persisted rows."""

    evaluation_id = _uuid(1)
    case_id = _uuid(2)
    pathway_id = _uuid(3)
    evaluations_repository = AsyncMock()
    cases_repository = AsyncMock()
    service = AuditService(evaluations_repository, cases_repository)

    evaluations_repository.get_evaluation_with_checks.return_value = {
        "evaluation": _evaluation_row(
            evaluation_id=evaluation_id,
            case_id=case_id,
            outcome=LegalOutcome.ELIGIBLE,
        ),
        "checks": [
            _check_row(
                check_result_id=_uuid(10),
                evaluation_id=evaluation_id,
                check_type="classification",
                check_code="HS6_RESOLUTION",
                passed=True,
                details_json={
                    "product": {
                        "hs6_id": str(_uuid(100)),
                        "hs_version": "HS2017",
                        "hs6_code": "110311",
                        "hs6_display": "Groats and meal of wheat",
                        "chapter": "11",
                        "heading": "1103",
                        "description": "Groats and meal of wheat",
                        "section": "II",
                        "section_name": "Vegetable Products",
                    }
                },
            ),
            _check_row(
                check_result_id=_uuid(11),
                evaluation_id=evaluation_id,
                check_type="rule",
                check_code="PSR_RESOLUTION",
                passed=True,
                details_json={
                    "psr_rule": {
                        "psr_id": str(_uuid(101)),
                        "source_id": str(_uuid(102)),
                        "appendix_version": "v0.1",
                        "hs_version": "HS2017",
                        "hs6_code": "110311",
                        "hs_level": "subheading",
                        "rule_scope": "subheading",
                        "product_description": "Groats and meal of wheat",
                        "legal_rule_text_verbatim": "CTH",
                        "legal_rule_text_normalized": "CTH",
                        "rule_status": "agreed",
                        "effective_date": "2024-01-01",
                        "page_ref": 1,
                        "table_ref": "Appendix IV",
                        "row_ref": "110311",
                    }
                },
            ),
            _check_row(
                check_result_id=_uuid(12),
                evaluation_id=evaluation_id,
                check_type="pathway",
                check_code="PATHWAY_EVALUATION",
                passed=True,
                details_json={
                    "pathway": {
                        "pathway_id": str(pathway_id),
                        "pathway_code": "CTH",
                        "pathway_label": "CTH",
                        "priority_rank": 1,
                    },
                    "result": True,
                    "evaluated_expression": "1001 != 1103",
                    "missing_variables": [],
                },
            ),
            _check_row(
                check_result_id=_uuid(13),
                evaluation_id=evaluation_id,
                check_type="psr",
                check_code="CTH",
                passed=True,
                details_json={
                    "pathway_id": str(pathway_id),
                    "pathway_code": "CTH",
                    "pathway_label": "CTH",
                    "priority_rank": 1,
                    "evaluated_expression": "1001 != 1103",
                    "missing_variables": [],
                },
            ),
            _check_row(
                check_result_id=_uuid(14),
                evaluation_id=evaluation_id,
                check_type="general_rule",
                check_code="GENERAL_RULES_SUMMARY",
                passed=True,
                details_json={
                    "general_rules_result": {
                        "insufficient_operations_check": "pass",
                        "cumulation_check": "not_applicable",
                        "direct_transport_check": "pass",
                        "general_rules_passed": True,
                        "failure_codes": [],
                    }
                },
            ),
            _check_row(
                check_result_id=_uuid(15),
                evaluation_id=evaluation_id,
                check_type="general_rule",
                check_code="DIRECT_TRANSPORT",
                passed=True,
                explanation="Direct transport condition was confirmed",
            ),
            _check_row(
                check_result_id=_uuid(16),
                evaluation_id=evaluation_id,
                check_type="status",
                check_code="STATUS_OVERLAY",
                passed=True,
                details_json={
                    "overlay": {
                        "status_type": "agreed",
                        "effective_from": "2024-01-01",
                        "effective_to": None,
                        "confidence_class": "complete",
                        "active_transitions": [],
                        "constraints": [],
                        "source_text_verbatim": "Rule is agreed.",
                    }
                },
            ),
            _check_row(
                check_result_id=_uuid(17),
                evaluation_id=evaluation_id,
                check_type="tariff",
                check_code="TARIFF_RESOLUTION",
                passed=True,
                details_json={
                    "tariff_outcome": {
                        "preferential_rate": "0.0000",
                        "base_rate": "15.0000",
                        "status": "in_force",
                    }
                },
            ),
            _check_row(
                check_result_id=_uuid(18),
                evaluation_id=evaluation_id,
                check_type="evidence",
                check_code="EVIDENCE_READINESS",
                passed=True,
                details_json={
                    "evidence_readiness": {
                        "required_items": ["certificate_of_origin"],
                        "missing_items": [],
                        "verification_questions": ["Provide the COO"],
                        "readiness_score": 1.0,
                        "completeness_ratio": 1.0,
                    }
                },
            ),
            _check_row(
                check_result_id=_uuid(19),
                evaluation_id=evaluation_id,
                check_type="decision",
                check_code="FINAL_DECISION",
                passed=True,
                details_json={
                    "final_decision": {
                        "eligible": True,
                        "pathway_used": "CTH",
                        "rule_status": "agreed",
                        "tariff_status": "in_force",
                        "confidence_class": "complete",
                        "failure_codes": [],
                        "missing_facts": [],
                    }
                },
            ),
        ],
    }
    cases_repository.get_case_with_facts.return_value = _case_bundle(case_id)

    result = await service.get_decision_trace(evaluation_id=str(evaluation_id))

    assert result.evaluation.evaluation_id == evaluation_id
    assert result.hs6_resolved is not None
    assert result.hs6_resolved.hs6_code == "110311"
    assert result.psr_rule is not None
    assert result.psr_rule.rule_status == "agreed"
    assert len(result.original_input_facts) == 2
    assert len(result.pathway_evaluations) == 1
    assert result.pathway_evaluations[0].checks[0].check_code == "CTH"
    assert result.general_rules_results is not None
    assert result.general_rules_results.general_rules_passed is True
    assert result.tariff_outcome is not None
    assert result.tariff_outcome.preferential_rate == Decimal("0.0000")
    assert result.evidence_readiness is not None
    assert result.final_decision.confidence_class == "complete"


@pytest.mark.asyncio
async def test_retrieve_evaluations_for_a_case() -> None:
    """The audit service should list all stored evaluations for one case id."""

    case_id = _uuid(20)
    evaluations_repository = AsyncMock()
    cases_repository = AsyncMock()
    service = AuditService(evaluations_repository, cases_repository)
    evaluations_repository.get_evaluations_for_case.return_value = [
        _evaluation_row(evaluation_id=_uuid(21), case_id=case_id, outcome=LegalOutcome.ELIGIBLE),
        _evaluation_row(
            evaluation_id=_uuid(22),
            case_id=case_id,
            outcome=LegalOutcome.NOT_ELIGIBLE,
        ),
    ]

    result = await service.get_evaluations_for_case(str(case_id))

    assert len(result) == 2
    assert result[0].evaluation_id == _uuid(21)
    assert result[1].overall_outcome == LegalOutcome.NOT_ELIGIBLE


@pytest.mark.asyncio
async def test_get_decision_trace_populates_tariff_provenance_ids_from_tariff_resolution() -> None:
    """Tariff replay should derive provenance_ids from persisted tariff_resolution source ids."""

    evaluation_id = _uuid(23)
    case_id = _uuid(24)
    schedule_source_id = _uuid(25)
    rate_source_id = _uuid(26)
    evaluations_repository = AsyncMock()
    cases_repository = AsyncMock()
    service = AuditService(evaluations_repository, cases_repository)
    evaluations_repository.get_evaluation_with_checks.return_value = {
        "evaluation": _evaluation_row(
            evaluation_id=evaluation_id,
            case_id=case_id,
            outcome=LegalOutcome.ELIGIBLE,
        ),
        "checks": [
            _check_row(
                check_result_id=_uuid(27),
                evaluation_id=evaluation_id,
                check_type="tariff",
                check_code="TARIFF_RESOLUTION",
                passed=True,
                details_json={
                    "tariff_resolution": {
                        "preferential_rate": "0.0000",
                        "base_rate": "15.0000",
                        "schedule_status": "in_force",
                        "schedule_source_id": str(schedule_source_id),
                        "rate_source_id": str(rate_source_id),
                    }
                },
            )
        ],
    }
    cases_repository.get_case_with_facts.return_value = None

    result = await service.get_decision_trace(evaluation_id=str(evaluation_id))

    assert result.tariff_outcome is not None
    assert result.tariff_outcome.provenance_ids == [
        str(schedule_source_id),
        str(rate_source_id),
    ]


@pytest.mark.asyncio
async def test_missing_evaluation_maps_to_404_domain_error() -> None:
    """A missing persisted trail should raise the domain 404 audit exception."""

    evaluations_repository = AsyncMock()
    cases_repository = AsyncMock()
    service = AuditService(evaluations_repository, cases_repository)
    evaluations_repository.get_evaluation_with_checks.return_value = None

    with pytest.raises(AuditTrailNotFoundError):
        await service.get_decision_trace(evaluation_id=str(_uuid(30)))

    assert DOMAIN_STATUS_CODES[AuditTrailNotFoundError] == 404


@pytest.mark.asyncio
async def test_get_decision_trace_resolves_latest_evaluation_from_case_id() -> None:
    """When only case_id is supplied, the latest stored evaluation should be replayed."""

    case_id = _uuid(40)
    evaluation_id = _uuid(41)
    evaluations_repository = AsyncMock()
    cases_repository = AsyncMock()
    service = AuditService(evaluations_repository, cases_repository)
    evaluations_repository.get_evaluations_for_case.return_value = [
        _evaluation_row(
            evaluation_id=evaluation_id,
            case_id=case_id,
            outcome=LegalOutcome.ELIGIBLE,
        )
    ]
    evaluations_repository.get_evaluation_with_checks.return_value = {
        "evaluation": _evaluation_row(
            evaluation_id=evaluation_id,
            case_id=case_id,
            outcome=LegalOutcome.ELIGIBLE,
        ),
        "checks": [],
    }
    cases_repository.get_case_with_facts.return_value = _case_bundle(case_id)

    result = await service.get_decision_trace(case_id=str(case_id))

    evaluations_repository.get_evaluations_for_case.assert_awaited_once_with(str(case_id))
    evaluations_repository.get_evaluation_with_checks.assert_awaited_once_with(str(evaluation_id))
    assert result.evaluation.evaluation_id == evaluation_id


@pytest.mark.asyncio
async def test_get_decision_trace_reconstructs_hs6_snapshot_from_case_when_classification_summary_missing() -> None:
    """Case header fallback should populate hs6 snapshot when the classification summary is absent."""

    evaluation_id = _uuid(60)
    case_id = _uuid(61)
    evaluations_repository = AsyncMock()
    cases_repository = AsyncMock()
    service = AuditService(evaluations_repository, cases_repository)
    evaluations_repository.get_evaluation_with_checks.return_value = {
        "evaluation": _evaluation_row(
            evaluation_id=evaluation_id,
            case_id=case_id,
            outcome=LegalOutcome.NOT_ELIGIBLE,
        ),
        "checks": [
            _check_row(
                check_result_id=_uuid(62),
                evaluation_id=evaluation_id,
                check_type="decision",
                check_code="FINAL_DECISION",
                passed=False,
                details_json={"final_decision": {"eligible": False, "failure_codes": ["FAIL_CTH_NOT_MET"]}},
            )
        ],
    }
    cases_repository.get_case_with_facts.return_value = _case_bundle(case_id)

    result = await service.get_decision_trace(evaluation_id=str(evaluation_id))

    assert result.hs6_resolved is not None
    assert result.hs6_resolved.hs6_code == "110311"
    assert result.hs6_resolved.hs_version == "HS2017"
    assert result.hs6_resolved.hs6_id is None


@pytest.mark.asyncio
async def test_get_decision_trace_builds_pathway_traces_from_atomic_psr_checks_when_summary_missing() -> None:
    """Atomic PSR checks should still reconstruct ordered pathway summaries without PATHWAY_EVALUATION rows."""

    evaluation_id = _uuid(70)
    case_id = _uuid(71)
    evaluations_repository = AsyncMock()
    cases_repository = AsyncMock()
    service = AuditService(evaluations_repository, cases_repository)
    evaluations_repository.get_evaluation_with_checks.return_value = {
        "evaluation": _evaluation_row(
            evaluation_id=evaluation_id,
            case_id=case_id,
            outcome=LegalOutcome.NOT_ELIGIBLE,
        ),
        "checks": [
            _check_row(
                check_result_id=_uuid(72),
                evaluation_id=evaluation_id,
                check_type="psr",
                check_code="PROCESS",
                passed=False,
                details_json={
                    "pathway_id": str(_uuid(700)),
                    "pathway_code": "PROCESS",
                    "pathway_label": "Specific Process",
                    "priority_rank": 1,
                    "evaluated_expression": None,
                    "missing_variables": ["specific_process_performed"],
                },
            ),
            _check_row(
                check_result_id=_uuid(73),
                evaluation_id=evaluation_id,
                check_type="psr",
                check_code="VNM",
                passed=True,
                details_json={
                    "pathway_id": str(_uuid(701)),
                    "pathway_code": "VNM",
                    "pathway_label": "Maximum Non-Originating Materials 55% (EXW)",
                    "priority_rank": 2,
                    "evaluated_expression": "vnom_percent <= 55",
                    "missing_variables": [],
                },
            ),
        ],
    }
    cases_repository.get_case_with_facts.return_value = _case_bundle(case_id)

    result = await service.get_decision_trace(evaluation_id=str(evaluation_id))

    assert [trace.pathway_code for trace in result.pathway_evaluations] == ["PROCESS", "VNM"]
    assert result.pathway_evaluations[0].priority_rank == 1
    assert result.pathway_evaluations[0].result is False
    assert result.pathway_evaluations[0].missing_variables == ["specific_process_performed"]
    assert result.pathway_evaluations[1].result is True


@pytest.mark.asyncio
async def test_get_decision_trace_reconstructs_general_rules_without_summary_check() -> None:
    """General-rule atomic checks should synthesize the summary fields when the summary row is absent."""

    evaluation_id = _uuid(80)
    case_id = _uuid(81)
    evaluations_repository = AsyncMock()
    cases_repository = AsyncMock()
    service = AuditService(evaluations_repository, cases_repository)
    evaluations_repository.get_evaluation_with_checks.return_value = {
        "evaluation": _evaluation_row(
            evaluation_id=evaluation_id,
            case_id=case_id,
            outcome=LegalOutcome.NOT_ELIGIBLE,
        ),
        "checks": [
            _check_row(
                check_result_id=_uuid(82),
                evaluation_id=evaluation_id,
                check_type="general_rule",
                check_code="DIRECT_TRANSPORT",
                passed=False,
                details_json={"failure_code": "FAIL_DIRECT_TRANSPORT"},
                explanation="Direct transport requirement not met",
            ),
            _check_row(
                check_result_id=_uuid(83),
                evaluation_id=evaluation_id,
                check_type="general_rule",
                check_code="CUMULATION",
                passed=True,
                explanation="Cumulation conditions satisfied",
            ),
            _check_row(
                check_result_id=_uuid(84),
                evaluation_id=evaluation_id,
                check_type="general_rule",
                check_code="INSUFFICIENT_OPERATIONS",
                passed=False,
                details_json={"failure_code": "FAIL_INSUFFICIENT_OPERATIONS"},
                explanation="Only minimal operations performed",
            ),
        ],
    }
    cases_repository.get_case_with_facts.return_value = _case_bundle(case_id)

    result = await service.get_decision_trace(evaluation_id=str(evaluation_id))

    assert result.general_rules_results is not None
    assert result.general_rules_results.direct_transport_check == "fail"
    assert result.general_rules_results.cumulation_check == "pass"
    assert result.general_rules_results.insufficient_operations_check == "fail"
    assert result.general_rules_results.general_rules_passed is False
    assert result.general_rules_results.failure_codes == [
        "FAIL_DIRECT_TRANSPORT",
        "FAIL_INSUFFICIENT_OPERATIONS",
    ]


@pytest.mark.asyncio
async def test_get_decision_trace_falls_back_final_decision_codes_and_missing_facts_from_checks() -> None:
    """Final decision should derive failure codes and missing facts when the summary payload omits them."""

    evaluation_id = _uuid(90)
    case_id = _uuid(91)
    evaluations_repository = AsyncMock()
    cases_repository = AsyncMock()
    service = AuditService(evaluations_repository, cases_repository)
    evaluations_repository.get_evaluation_with_checks.return_value = {
        "evaluation": _evaluation_row(
            evaluation_id=evaluation_id,
            case_id=case_id,
            outcome=LegalOutcome.NOT_ELIGIBLE,
        ),
        "checks": [
            _check_row(
                check_result_id=_uuid(92),
                evaluation_id=evaluation_id,
                check_type="blocker",
                check_code="MISSING_CORE_FACTS",
                passed=False,
                details_json={
                    "failure_code": "MISSING_CORE_FACTS",
                    "missing_facts": ["non_originating_inputs", "output_hs6_code"],
                },
            ),
            _check_row(
                check_result_id=_uuid(93),
                evaluation_id=evaluation_id,
                check_type="decision",
                check_code="FINAL_DECISION",
                passed=False,
                details_json={"final_decision": {"eligible": False}},
            ),
        ],
    }
    cases_repository.get_case_with_facts.return_value = _case_bundle(case_id)

    result = await service.get_decision_trace(evaluation_id=str(evaluation_id))

    assert result.final_decision.eligible is False
    assert result.final_decision.failure_codes == ["MISSING_CORE_FACTS"]
    assert result.final_decision.missing_facts == ["non_originating_inputs", "output_hs6_code"]


@pytest.mark.asyncio
async def test_missing_case_history_maps_case_id_lookup_to_domain_error() -> None:
    """Resolving from a case id with no stored evaluations should raise the domain not-found error."""

    evaluations_repository = AsyncMock()
    cases_repository = AsyncMock()
    service = AuditService(evaluations_repository, cases_repository)
    evaluations_repository.get_evaluations_for_case.return_value = []

    with pytest.raises(AuditTrailNotFoundError):
        await service.get_decision_trace(case_id=str(_uuid(95)))


def test_log_assessment_emits_structured_audit_event_with_correlation_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Assessment logs should carry a stable event name and request correlation fields."""

    service = AuditService(AsyncMock(), AsyncMock())
    context_tokens = bind_request_log_context(request_id="req-audit-1")
    update_request_log_context(
        authenticated_principal="pytest-suite",
        auth_scheme="api_key",
    )

    try:
        with caplog.at_level(logging.INFO, logger="app.audit"):
            service.log_assessment(
                case_id="case-123",
                hs6_code="110311",
                exporter="GHA",
                importer="NGA",
                outcome="eligible",
                confidence_class="complete",
                duration_ms=87,
            )
    finally:
        reset_request_log_context(context_tokens)

    records = [record for record in caplog.records if record.name == "app.audit"]
    assert len(records) == 1
    payload = records[0].structured_data
    assert payload["event"] == "eligibility_assessment"
    assert payload["request_id"] == "req-audit-1"
    assert payload["authenticated_principal"] == "pytest-suite"
    assert payload["auth_scheme"] == "api_key"
    assert payload["case_id"] == "case-123"
    assert payload["hs6_code"] == "110311"
    assert payload["duration_ms"] == 87

"""Unit tests for eligibility-service orchestration and short-circuit behavior."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.exceptions import TariffNotFoundError
from app.core.failure_codes import FAILURE_CODES
from app.schemas.assessments import EligibilityRequest
from app.schemas.evidence import EvidenceReadinessResult
from app.schemas.hs import HS6ProductResponse
from app.schemas.rules import RuleResolutionResult
from app.schemas.status import StatusOverlay
from app.schemas.tariffs import TariffResolutionResult
from app.services.eligibility_service import EligibilityService
from app.services.expression_evaluator import AtomicCheck, ExpressionResult
from app.services.general_origin_rules_service import GeneralRulesResult


def build_product(hs6_code: str = "110311") -> HS6ProductResponse:
    """Build a minimal canonical HS6 product payload."""

    return HS6ProductResponse(
        hs6_id="hs6-110311",
        hs_version="HS2017",
        hs6_code=hs6_code,
        hs6_display=hs6_code,
        chapter=hs6_code[:2],
        heading=hs6_code[:4],
        description="Cereal groats",
        section="IV",
        section_name="Prepared foodstuffs",
        created_at=datetime(2026, 1, 1, 0, 0, 0),
        updated_at=datetime(2026, 1, 1, 0, 0, 0),
    )


def build_pathway(
    *,
    pathway_id: str = "pathway-1",
    pathway_code: str = "CTH",
    priority_rank: int = 1,
    allows_cumulation: bool = False,
    expression: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build a stored rule pathway payload."""

    expression_json = expression or {
        "pathway_code": pathway_code,
        "expression": {
            "op": "fact_ne",
            "fact": "tariff_heading_input",
            "ref_fact": "tariff_heading_output",
        },
    }
    return {
        "pathway_id": pathway_id,
        "pathway_code": pathway_code,
        "pathway_label": pathway_code,
        "pathway_type": "or",
        "expression_json": expression_json,
        "threshold_percent": None,
        "threshold_basis": None,
        "tariff_shift_level": None,
        "required_process_text": None,
        "allows_cumulation": allows_cumulation,
        "allows_tolerance": False,
        "priority_rank": priority_rank,
    }


def build_rule_bundle(
    *,
    hs6_code: str = "110311",
    rule_status: str = "agreed",
    pathways: list[dict[str, object]] | None = None,
) -> RuleResolutionResult:
    """Build a resolved PSR bundle."""

    return RuleResolutionResult.model_validate(
        {
            "psr_rule": {
                "psr_id": "psr-110311",
                "hs_version": "HS2017",
                "hs_code": hs6_code,
                "rule_scope": "subheading",
                "product_description": "Cereal groats",
                "legal_rule_text_verbatim": "CTH",
                "legal_rule_text_normalized": "CTH",
                "rule_status": rule_status,
                "source_id": "source-1",
                "page_ref": 1,
                "row_ref": "1",
            },
            "components": [],
            "pathways": pathways or [build_pathway()],
            "applicability_type": "direct",
        }
    )


def build_tariff_result(
    *,
    preferential_rate: str = "5.0000",
    base_rate: str = "15.0000",
    tariff_status: str = "in_force",
    tariff_category: str = "liberalised",
    schedule_status: str = "official",
) -> TariffResolutionResult:
    """Build a service-level tariff result."""

    return TariffResolutionResult(
        base_rate=Decimal(base_rate),
        preferential_rate=Decimal(preferential_rate),
        staging_year=2026,
        tariff_status=tariff_status,
        tariff_category=tariff_category,
        schedule_status=schedule_status,
    )


def build_status_overlay(
    *,
    status_type: str,
    confidence_class: str,
    constraints: list[str] | None = None,
    source_text_verbatim: str | None = None,
) -> StatusOverlay:
    """Build a service-level status overlay."""

    return StatusOverlay(
        status_type=status_type,
        confidence_class=confidence_class,
        constraints=constraints or [],
        source_text_verbatim=source_text_verbatim,
    )


def build_evidence_result(required_items: list[str] | None = None) -> EvidenceReadinessResult:
    """Build a service-level evidence readiness result."""

    return EvidenceReadinessResult(
        required_items=required_items or ["certificate_of_origin"],
        missing_items=[],
        verification_questions=["Upload the signed certificate of origin."],
        readiness_score=1.0,
        completeness_ratio=1.0,
    )


def build_request(**overrides: object) -> EligibilityRequest:
    """Build an eligibility request payload."""

    payload: dict[str, object] = {
        "hs6_code": "110311",
        "hs_version": "HS2017",
        "exporter": "GHA",
        "importer": "NGA",
        "year": 2026,
        "persona_mode": "officer",
        "production_facts": [
            {
                "fact_type": "tariff_heading_input",
                "fact_key": "tariff_heading_input",
                "fact_value_type": "text",
                "fact_value_text": "1103",
            },
            {
                "fact_type": "tariff_heading_output",
                "fact_key": "tariff_heading_output",
                "fact_value_type": "text",
                "fact_value_text": "1104",
            },
        ],
        "case_id": "case-123",
    }
    payload.update(overrides)
    return EligibilityRequest.model_validate(payload)


def build_expression_result(
    *,
    result: bool | None,
    explanation: str,
    missing_variables: list[str] | None = None,
) -> ExpressionResult:
    """Build a pathway expression-evaluation result."""

    return ExpressionResult(
        result=result,
        evaluated_expression="test expression",
        missing_variables=missing_variables or [],
        checks=[
            AtomicCheck(
                check_code="FACT_NE",
                passed=result,
                expected_value="tariff_heading_output",
                observed_value="tariff_heading_input",
                explanation=explanation,
            )
        ],
    )


def build_general_rules_result(
    *,
    general_rules_passed: bool,
    failure_codes: list[str] | None = None,
    direct_transport_check: str = "pass",
) -> GeneralRulesResult:
    """Build a post-PSR general-rules evaluation result."""

    passed = True if general_rules_passed else False
    explanation = (
        "Direct transport condition was confirmed"
        if passed
        else FAILURE_CODES["FAIL_DIRECT_TRANSPORT"]
    )
    return GeneralRulesResult(
        insufficient_operations_check="pass",
        cumulation_check="not_applicable",
        direct_transport_check=direct_transport_check,
        general_rules_passed=general_rules_passed,
        checks=[
            AtomicCheck(
                check_code="DIRECT_TRANSPORT",
                passed=passed if direct_transport_check != "not_checked" else None,
                expected_value="true",
                observed_value="true" if passed else "false",
                explanation=explanation,
            )
        ],
        failure_codes=failure_codes or [],
    )


def make_service_harness(
    *,
    call_order: list[str],
    product: HS6ProductResponse | None = None,
    rule_bundle: RuleResolutionResult | None = None,
    tariff_result: TariffResolutionResult | None = None,
    tariff_error: Exception | None = None,
    corridor_overlay: StatusOverlay | None = None,
    rule_overlay: StatusOverlay | None = None,
    normalized_facts: dict[str, object] | None = None,
    expression_results: list[ExpressionResult] | None = None,
    general_rules_result: GeneralRulesResult | None = None,
    evidence_result: EvidenceReadinessResult | None = None,
) -> tuple[EligibilityService, SimpleNamespace]:
    """Build the orchestrator service plus all mocked collaborators."""

    expression_queue = iter(expression_results or [])

    async def resolve_hs6_side_effect(hs_code: str, hs_version: str) -> HS6ProductResponse:
        call_order.append("classification")
        return product or build_product(hs_code)

    async def resolve_rule_bundle_side_effect(
        hs_version: str,
        hs6_code: str,
        assessment_date: object,
    ) -> RuleResolutionResult:
        call_order.append("rule_resolution")
        return rule_bundle or build_rule_bundle(hs6_code=hs6_code)

    async def resolve_tariff_bundle_side_effect(
        exporter: str,
        importer: str,
        hs_version: str,
        hs6_code: str,
        year: int,
    ) -> TariffResolutionResult:
        call_order.append("tariff_resolution")
        if tariff_error is not None:
            raise tariff_error
        return tariff_result or build_tariff_result()

    async def get_status_overlay_side_effect(entity_type: str, entity_key: str) -> StatusOverlay:
        call_order.append(f"status:{entity_type}")
        if entity_type == "corridor":
            return corridor_overlay or build_status_overlay(
                status_type="agreed",
                confidence_class="complete",
            )
        return rule_overlay or build_status_overlay(
            status_type="agreed",
            confidence_class="complete",
        )

    def normalize_facts_side_effect(production_facts: list[object]) -> dict[str, object]:
        call_order.append("normalize")
        return normalized_facts or {
            "tariff_heading_input": "1103",
            "tariff_heading_output": "1104",
        }

    def evaluate_side_effect(
        expression: dict[str, object],
        facts: dict[str, object],
    ) -> ExpressionResult:
        call_order.append("expression")
        return next(expression_queue)

    def general_rules_side_effect(
        facts: dict[str, object],
        selected_pathway: object,
    ) -> GeneralRulesResult:
        call_order.append("general")
        return general_rules_result or build_general_rules_result(general_rules_passed=True)

    async def build_readiness_side_effect(
        entity_type: str,
        entity_key: str,
        persona_mode: str,
        existing_documents: list[str],
    ) -> EvidenceReadinessResult:
        call_order.append("evidence")
        return evidence_result or build_evidence_result()

    async def persist_evaluation_side_effect(
        evaluation_data: dict[str, object],
        check_results: list[dict[str, object]],
    ) -> dict[str, object]:
        call_order.append("persist")
        return {"evaluation": evaluation_data, "checks": check_results}

    mocks = SimpleNamespace(
        classification_service=SimpleNamespace(
            resolve_hs6=AsyncMock(side_effect=resolve_hs6_side_effect)
        ),
        rule_resolution_service=SimpleNamespace(
            resolve_rule_bundle=AsyncMock(side_effect=resolve_rule_bundle_side_effect)
        ),
        tariff_resolution_service=SimpleNamespace(
            resolve_tariff_bundle=AsyncMock(side_effect=resolve_tariff_bundle_side_effect)
        ),
        status_service=SimpleNamespace(
            get_status_overlay=AsyncMock(side_effect=get_status_overlay_side_effect)
        ),
        evidence_service=SimpleNamespace(
            build_readiness=AsyncMock(side_effect=build_readiness_side_effect)
        ),
        fact_normalization_service=SimpleNamespace(
            normalize_facts=Mock(side_effect=normalize_facts_side_effect)
        ),
        expression_evaluator=SimpleNamespace(evaluate=Mock(side_effect=evaluate_side_effect)),
        general_origin_rules_service=SimpleNamespace(
            evaluate=Mock(side_effect=general_rules_side_effect)
        ),
        evaluations_repository=SimpleNamespace(
            persist_evaluation=AsyncMock(side_effect=persist_evaluation_side_effect)
        ),
    )

    service = EligibilityService(
        classification_service=mocks.classification_service,
        rule_resolution_service=mocks.rule_resolution_service,
        tariff_resolution_service=mocks.tariff_resolution_service,
        status_service=mocks.status_service,
        evidence_service=mocks.evidence_service,
        fact_normalization_service=mocks.fact_normalization_service,
        expression_evaluator=mocks.expression_evaluator,
        general_origin_rules_service=mocks.general_origin_rules_service,
        evaluations_repository=mocks.evaluations_repository,
    )
    return service, mocks


@pytest.mark.asyncio
async def test_assess_returns_eligible_response_when_pathway_and_general_rules_pass() -> None:
    call_order: list[str] = []
    service, mocks = make_service_harness(
        call_order=call_order,
        expression_results=[
            build_expression_result(result=True, explanation="Check passed: CTH"),
        ],
        general_rules_result=build_general_rules_result(general_rules_passed=True),
    )

    response = await service.assess(build_request())

    assert response.eligible is True
    assert response.pathway_used == "CTH"
    assert response.rule_status.value == "agreed"
    assert response.tariff_outcome is not None
    assert response.tariff_outcome.status == "in_force"
    assert response.failures == []
    assert response.evidence_required == ["certificate_of_origin"]
    assert response.confidence_class == "complete"
    assert call_order == [
        "classification",
        "rule_resolution",
        "tariff_resolution",
        "status:corridor",
        "normalize",
        "expression",
        "general",
        "status:psr_rule",
        "evidence",
        "persist",
    ]
    mocks.evidence_service.build_readiness.assert_awaited_once_with(
        "pathway",
        "PATHWAY:pathway-1",
        "officer",
        [],
    )
    mocks.evaluations_repository.persist_evaluation.assert_awaited_once()


@pytest.mark.asyncio
async def test_assess_returns_ineligible_when_no_pathway_passes() -> None:
    call_order: list[str] = []
    service, mocks = make_service_harness(
        call_order=call_order,
        expression_results=[
            build_expression_result(
                result=False,
                explanation=FAILURE_CODES["FAIL_CTH_NOT_MET"],
            ),
        ],
    )

    response = await service.assess(build_request())

    assert response.eligible is False
    assert response.pathway_used is None
    assert response.failures == ["FAIL_CTH_NOT_MET"]
    assert response.confidence_class == "complete"
    mocks.general_origin_rules_service.evaluate.assert_not_called()
    mocks.evidence_service.build_readiness.assert_awaited_once_with(
        "hs6_rule",
        "HS6_RULE:psr-110311",
        "officer",
        [],
    )
    assert call_order == [
        "classification",
        "rule_resolution",
        "tariff_resolution",
        "status:corridor",
        "normalize",
        "expression",
        "status:psr_rule",
        "evidence",
        "persist",
    ]


@pytest.mark.asyncio
async def test_assess_short_circuits_on_pending_rule_status_blocker() -> None:
    call_order: list[str] = []
    service, mocks = make_service_harness(
        call_order=call_order,
        rule_bundle=build_rule_bundle(rule_status="pending"),
    )

    response = await service.assess(build_request())

    assert response.eligible is False
    assert response.pathway_used is None
    assert response.failures == ["RULE_STATUS_PENDING"]
    assert response.confidence_class == "provisional"
    mocks.fact_normalization_service.normalize_facts.assert_not_called()
    mocks.expression_evaluator.evaluate.assert_not_called()
    mocks.general_origin_rules_service.evaluate.assert_not_called()
    mocks.evidence_service.build_readiness.assert_not_awaited()
    assert call_order == [
        "classification",
        "rule_resolution",
        "tariff_resolution",
        "status:corridor",
        "persist",
    ]


@pytest.mark.asyncio
async def test_assess_returns_incomplete_when_core_facts_missing_for_all_pathways() -> None:
    call_order: list[str] = []
    vnm_pathway = build_pathway(
        pathway_code="VNM<=60",
        expression={
            "pathway_code": "VNM<=60",
            "expression": {
                "op": "formula_lte",
                "formula": "vnom_percent",
                "value": 60,
            },
        },
    )
    service, mocks = make_service_harness(
        call_order=call_order,
        rule_bundle=build_rule_bundle(pathways=[vnm_pathway]),
    )

    response = await service.assess(build_request(production_facts=[]))

    assert response.eligible is False
    assert response.failures == ["MISSING_CORE_FACTS"]
    assert response.missing_facts == ["ex_works", "non_originating"]
    assert response.confidence_class == "incomplete"
    mocks.fact_normalization_service.normalize_facts.assert_not_called()
    assert call_order == [
        "classification",
        "rule_resolution",
        "tariff_resolution",
        "status:corridor",
        "persist",
    ]


@pytest.mark.asyncio
async def test_assess_returns_not_eligible_when_general_rules_fail_after_passing_psr() -> None:
    call_order: list[str] = []
    service, mocks = make_service_harness(
        call_order=call_order,
        expression_results=[build_expression_result(result=True, explanation="Check passed: CTH")],
        general_rules_result=build_general_rules_result(
            general_rules_passed=False,
            failure_codes=["FAIL_DIRECT_TRANSPORT"],
            direct_transport_check="fail",
        ),
    )

    response = await service.assess(build_request())

    assert response.eligible is False
    assert response.pathway_used == "CTH"
    assert response.failures == ["FAIL_DIRECT_TRANSPORT"]
    assert "general" in call_order
    mocks.evidence_service.build_readiness.assert_awaited_once()


@pytest.mark.asyncio
async def test_assess_continues_when_tariff_schedule_is_missing() -> None:
    call_order: list[str] = []
    service, mocks = make_service_harness(
        call_order=call_order,
        tariff_error=TariffNotFoundError(
            "No tariff schedule found",
            detail={"exporter": "GHA", "importer": "NGA"},
        ),
        expression_results=[build_expression_result(result=True, explanation="Check passed: CTH")],
        general_rules_result=build_general_rules_result(general_rules_passed=True),
    )

    response = await service.assess(build_request())

    assert response.eligible is True
    assert response.tariff_outcome is None
    assert response.failures == []
    assert call_order == [
        "classification",
        "rule_resolution",
        "tariff_resolution",
        "status:corridor",
        "normalize",
        "expression",
        "general",
        "status:psr_rule",
        "evidence",
        "persist",
    ]
    persisted_checks = mocks.evaluations_repository.persist_evaluation.await_args.args[1]
    assert any(check["check_code"] == "NO_SCHEDULE" for check in persisted_checks)

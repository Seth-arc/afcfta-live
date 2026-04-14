"""Unit tests for the eligibility orchestrator service."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID
from unittest.mock import AsyncMock, Mock, call

import pytest

from app.core.enums import (
    AlertSeverityEnum,
    AlertStatusEnum,
    AlertTypeEnum,
    HsLevelEnum,
    PersonaModeEnum,
    RuleStatusEnum,
    ScheduleStatusEnum,
    TariffCategoryEnum,
)
from app.core.exceptions import CaseNotFoundError, EvaluationPersistenceError, TariffNotFoundError
from app.core.failure_codes import FAILURE_CODES
from app.schemas.assessments import (
    CaseAssessmentRequest,
    EligibilityAssessmentResponse,
    EligibilityRequest,
)
from app.schemas.cases import CaseFactIn
from app.schemas.evidence import EvidenceReadinessResult
from app.schemas.hs import HS6ProductResponse
from app.schemas.rules import PSRRuleResolvedOut, RulePathwayOut, RuleResolutionResult
from app.schemas.status import StatusOverlay
from app.schemas.tariffs import TariffResolutionResult
from app.db import session as session_module
from app.services.eligibility_service import EligibilityService
from app.services.expression_evaluator import AtomicCheck, ExpressionResult
from app.services.general_origin_rules_service import GeneralRulesResult
from app.services.intelligence_service import IntelligenceService


def _uuid(value: int) -> UUID:
    """Build a stable UUID for test fixtures."""

    return UUID(f"00000000-0000-0000-0000-{value:012d}")


def _product(hs6_code: str) -> HS6ProductResponse:
    """Return a canonical classified product."""

    return HS6ProductResponse(
        hs6_id=_uuid(1),
        hs_version="HS2017",
        hs6_code=hs6_code,
        hs6_display=f"{hs6_code} product",
        chapter=hs6_code[:2],
        heading=hs6_code[:4],
        description="Seed product",
        section="II",
        section_name="Vegetable Products",
    )


def _rule_bundle(
    *,
    hs6_code: str,
    rule_status: RuleStatusEnum = RuleStatusEnum.AGREED,
    pathway_code: str = "CTH",
    expression_json: dict | None = None,
) -> RuleResolutionResult:
    """Return one resolved rule bundle."""

    psr_id = _uuid(10)
    return RuleResolutionResult(
        psr_rule=PSRRuleResolvedOut(
            psr_id=psr_id,
            source_id=_uuid(11),
            appendix_version="seed-v0.1",
            hs_version="HS2017",
            hs6_code=hs6_code,
            hs_code_start=None,
            hs_code_end=None,
            hs_level=HsLevelEnum.SUBHEADING,
            rule_scope="subheading",
            product_description="Seed product",
            legal_rule_text_verbatim="Seed rule text.",
            legal_rule_text_normalized=pathway_code,
            rule_status=rule_status,
            effective_date=date(2024, 1, 1),
            page_ref=1,
            table_ref="seed_psr",
            row_ref=hs6_code,
        ),
        components=[],
        pathways=[
            RulePathwayOut(
                pathway_id=_uuid(12),
                psr_id=psr_id,
                pathway_code=pathway_code,
                pathway_label=pathway_code,
                pathway_type="specific",
                expression_json=expression_json
                or {
                    "op": "fact_ne",
                    "fact": "tariff_heading_input",
                    "ref_fact": "tariff_heading_output",
                },
                threshold_percent=None,
                threshold_basis=None,
                tariff_shift_level=HsLevelEnum.HEADING,
                required_process_text=None,
                allows_cumulation=True,
                allows_tolerance=False,
                priority_rank=1,
                effective_date=date(2024, 1, 1),
                expiry_date=None,
            )
        ],
        applicability_type="direct",
    )


def _tariff_result() -> TariffResolutionResult:
    """Return a structured tariff result."""

    return TariffResolutionResult(
        base_rate=Decimal("15.0000"),
        preferential_rate=Decimal("0.0000"),
        staging_year=2025,
        tariff_status="in_force",
        tariff_category=TariffCategoryEnum.LIBERALISED,
        schedule_status=ScheduleStatusEnum.OFFICIAL,
        schedule_id=_uuid(20),
        schedule_line_id=_uuid(21),
        year_rate_id=_uuid(22),
        schedule_source_id=_uuid(23),
        rate_source_id=_uuid(24),
        resolved_rate_year=2025,
        line_page_ref=9,
        rate_page_ref=10,
        table_ref="seed_tariff",
        row_ref="110311",
        used_fallback_rate=False,
    )


def _status_overlay(
    status_type: str,
    confidence_class: str,
    source_text_verbatim: str,
) -> StatusOverlay:
    """Return one status overlay."""

    return StatusOverlay(
        status_type=status_type,
        effective_from=date(2024, 1, 1),
        effective_to=None,
        confidence_class=confidence_class,
        active_transitions=[],
        constraints=[],
        source_text_verbatim=source_text_verbatim,
    )


def _evidence_result() -> EvidenceReadinessResult:
    """Return one readiness result."""

    return EvidenceReadinessResult(
        required_items=["certificate_of_origin"],
        missing_items=["Supplier declaration"],
        verification_questions=[],
        readiness_score=0.5,
        completeness_ratio=0.5,
    )


def _expression_result(
    *,
    passed: bool | None,
    explanation: str,
    missing_variables: list[str] | None = None,
) -> ExpressionResult:
    """Return one evaluator result."""

    return ExpressionResult(
        result=passed,
        evaluated_expression="seed expression",
        missing_variables=missing_variables or [],
        checks=[
            AtomicCheck(
                check_code="PSR_CHECK",
                passed=passed,
                expected_value="expected",
                observed_value="observed",
                explanation=explanation,
            )
        ],
    )


def _general_rules_result(
    *,
    passed: bool,
    failure_codes: list[str] | None = None,
) -> GeneralRulesResult:
    """Return one general-rules evaluation."""

    return GeneralRulesResult(
        insufficient_operations_check="pass",
        cumulation_check="not_applicable",
        direct_transport_check="pass" if passed else "fail",
        general_rules_passed=passed,
        checks=[
            AtomicCheck(
                check_code="DIRECT_TRANSPORT",
                passed=passed,
                expected_value="true",
                observed_value="true" if passed else "false",
                explanation=(
                    "Direct transport satisfied"
                    if passed
                    else FAILURE_CODES["FAIL_DIRECT_TRANSPORT"]
                ),
            )
        ],
        failure_codes=failure_codes or [],
    )


def _fact(fact_key: str, fact_value_type: str, **values: object) -> CaseFactIn:
    """Return one typed production fact."""

    payload = {
        "fact_type": fact_key,
        "fact_key": fact_key,
        "fact_value_type": fact_value_type,
        "source_ref": None,
    }
    payload.update(values)
    return CaseFactIn(**payload)


def _request(
    *,
    hs6_code: str,
    facts: list[CaseFactIn],
    case_id: str | None = None,
) -> EligibilityRequest:
    """Return one orchestrator request."""

    return EligibilityRequest(
        hs6_code=hs6_code,
        hs_version="HS2017",
        exporter="GHA" if hs6_code != "271019" else "CMR",
        importer="NGA",
        year=2025,
        persona_mode="exporter",
        production_facts=facts,
        case_id=case_id,
    )


def _service() -> tuple[EligibilityService, dict[str, object]]:
    """Create the orchestrator with mocked dependencies."""

    rule_resolution_service = AsyncMock()
    shared_rule_resolution = AsyncMock()
    rule_resolution_service.resolve_rule_bundle = shared_rule_resolution
    rule_resolution_service.resolve_rule_bundle_by_hs6_id = shared_rule_resolution
    status_service = AsyncMock()
    evidence_service = AsyncMock()

    async def _get_status_overlays(
        targets: list[tuple[str, str]],
        as_of_date: date | None = None,
    ) -> dict[tuple[str, str], StatusOverlay]:
        overlays: dict[tuple[str, str], StatusOverlay] = {}
        for entity_type, entity_key in targets:
            overlays[(entity_type, entity_key)] = await status_service.get_status_overlay(
                entity_type,
                entity_key,
                as_of_date,
            )
        return overlays

    async def _build_readiness_for_targets(
        targets: list[tuple[str, str]],
        *,
        persona_mode: str,
        existing_documents: list[str],
        confidence_class: str | None = None,
        assessment_date: date | None = None,
    ) -> EvidenceReadinessResult:
        fallback: EvidenceReadinessResult | None = None
        for entity_type, entity_key in targets:
            result = await evidence_service.build_readiness(
                entity_type=entity_type,
                entity_key=entity_key,
                persona_mode=persona_mode,
                existing_documents=existing_documents,
                confidence_class=confidence_class,
                assessment_date=assessment_date,
            )
            if fallback is None:
                fallback = result
            if result.required_items or result.verification_questions:
                return result
        return fallback or EvidenceReadinessResult(
            required_items=[],
            missing_items=[],
            verification_questions=[],
            readiness_score=1.0,
            completeness_ratio=1.0,
        )

    status_service.get_status_overlays.side_effect = _get_status_overlays
    evidence_service.build_readiness_for_targets.side_effect = _build_readiness_for_targets

    intelligence_service = Mock()
    intelligence_service.build_assessment_alert_specs.return_value = []
    sources_repository = AsyncMock()

    async def _get_source_snapshot(source_id: str) -> dict[str, object]:
        source_uuid = UUID(str(source_id))
        return {
            "source": {
                "source_id": source_uuid,
                "short_title": f"Source {str(source_uuid)[-6:]}",
                "version_label": "pytest-v1",
                "publication_date": date(2025, 1, 1),
                "effective_date": date(2025, 1, 1),
            },
            "supporting_provisions": [
                {
                    "provision_id": source_uuid,
                    "source_id": source_uuid,
                    "article_label": "Art. 1",
                    "clause_label": "Clause 1",
                    "topic_primary": "origin_rules",
                    "text_excerpt": f"Seed excerpt {str(source_uuid)[-6:]}",
                }
            ],
        }

    sources_repository.get_source_snapshot.side_effect = _get_source_snapshot

    deps = {
        "classification_service": AsyncMock(),
        "rule_resolution_service": rule_resolution_service,
        "tariff_resolution_service": AsyncMock(),
        "status_service": status_service,
        "evidence_service": evidence_service,
        "fact_normalization_service": Mock(),
        "expression_evaluator": Mock(),
        "general_origin_rules_service": Mock(),
        "cases_repository": AsyncMock(),
        "evaluations_repository": AsyncMock(),
        "sources_repository": sources_repository,
        "intelligence_service": intelligence_service,
    }
    return EligibilityService(**deps), deps


def _assert_persisted_blocker_audit(
    deps: dict[str, object],
    *,
    case_id: str,
    blocker_check_code: str,
    failure_codes: list[str],
    details_json: dict[str, object],
) -> list[dict[str, object]]:
    """Assert one blocker-stage assessment persisted the stop reason and no pathway trace."""

    persisted_evaluation = deps["evaluations_repository"].persist_evaluation.await_args.args[0]
    persisted_checks = deps["evaluations_repository"].persist_evaluation.await_args.args[1]

    assert persisted_evaluation["case_id"] == case_id
    assert persisted_evaluation["pathway_used"] is None

    blocker_check = next(
        check for check in persisted_checks if check["check_code"] == blocker_check_code
    )
    assert blocker_check["check_type"] == "blocker"
    assert blocker_check["severity"] == "blocker"
    assert blocker_check["passed"] is False
    assert blocker_check["details_json"] == details_json

    final_decision_check = next(
        check for check in persisted_checks if check["check_code"] == "FINAL_DECISION"
    )
    assert final_decision_check["check_type"] == "decision"
    assert final_decision_check["passed"] is False
    assert final_decision_check["details_json"]["final_decision"]["pathway_used"] is None
    assert final_decision_check["details_json"]["final_decision"]["failure_codes"] == failure_codes
    assert all(check["check_code"] != "PATHWAY_EVALUATION" for check in persisted_checks)

    return persisted_checks


@pytest.mark.asyncio
async def test_eligible_product_pathway_and_general_rules_pass() -> None:
    """A passing PSR and passing general rules should yield eligibility."""

    service, deps = _service()
    request = _request(
        hs6_code="110311",
        facts=[
            _fact("tariff_heading_input", "text", fact_value_text="1001"),
            _fact("tariff_heading_output", "text", fact_value_text="1103"),
            _fact("direct_transport", "boolean", fact_value_boolean=True),
        ],
    )
    deps["classification_service"].resolve_hs6.return_value = _product("110311")
    deps["rule_resolution_service"].resolve_rule_bundle.return_value = _rule_bundle(hs6_code="110311")
    deps["tariff_resolution_service"].resolve_tariff_bundle.return_value = _tariff_result()
    deps["status_service"].get_status_overlay.side_effect = [
        _status_overlay("in_force", "complete", "Corridor is operational."),
        _status_overlay("agreed", "complete", "Rule is agreed."),
    ]
    deps["fact_normalization_service"].normalize_facts.return_value = {
        "tariff_heading_input": "1001",
        "tariff_heading_output": "1103",
        "direct_transport": True,
    }
    deps["expression_evaluator"].evaluate.return_value = _expression_result(
        passed=True,
        explanation=FAILURE_CODES["FAIL_CTH_NOT_MET"],
    )
    deps["general_origin_rules_service"].evaluate.return_value = _general_rules_result(passed=True)
    deps["evidence_service"].build_readiness.return_value = _evidence_result()

    result = await service.assess(request)

    assert result.eligible is True
    assert result.pathway_used == "CTH"
    assert result.rule_status == "agreed"
    assert result.evidence_required == ["certificate_of_origin"]
    assert result.missing_evidence == ["Supplier declaration"]
    assert result.readiness_score == 0.5
    assert result.completeness_ratio == 0.5
    deps["tariff_resolution_service"].resolve_tariff_bundle.assert_awaited_once_with(
        "GHA",
        "NGA",
        "HS2017",
        "110311",
        2025,
        assessment_date=date(2025, 1, 1),
    )
    assert deps["status_service"].get_status_overlay.await_args_list == [
        call("corridor", "CORRIDOR:GHA:NGA:110311", date(2025, 1, 1)),
        call("psr_rule", f"PSR:{_uuid(10)}", date(2025, 1, 1)),
    ]
    deps["evidence_service"].build_readiness.assert_awaited_once_with(
        entity_type="pathway",
        entity_key=f"PATHWAY:{_uuid(12)}",
        persona_mode=request.persona_mode,
        existing_documents=[],
        confidence_class="complete",
        assessment_date=date(2025, 1, 1),
    )


@pytest.mark.asyncio
async def test_ineligible_product_when_no_pathway_passes() -> None:
    """A failing PSR pathway should yield ineligibility."""

    service, deps = _service()
    request = _request(
        hs6_code="110311",
        facts=[
            _fact("tariff_heading_input", "text", fact_value_text="1103"),
            _fact("tariff_heading_output", "text", fact_value_text="1103"),
            _fact("direct_transport", "boolean", fact_value_boolean=True),
        ],
    )
    deps["classification_service"].resolve_hs6.return_value = _product("110311")
    deps["rule_resolution_service"].resolve_rule_bundle.return_value = _rule_bundle(hs6_code="110311")
    deps["tariff_resolution_service"].resolve_tariff_bundle.return_value = _tariff_result()
    deps["status_service"].get_status_overlay.side_effect = [
        _status_overlay("in_force", "complete", "Corridor is operational."),
        _status_overlay("agreed", "complete", "Rule is agreed."),
    ]
    deps["fact_normalization_service"].normalize_facts.return_value = {
        "tariff_heading_input": "1103",
        "tariff_heading_output": "1103",
        "direct_transport": True,
    }
    deps["expression_evaluator"].evaluate.return_value = _expression_result(
        passed=False,
        explanation=FAILURE_CODES["FAIL_CTH_NOT_MET"],
    )
    deps["evidence_service"].build_readiness.return_value = _evidence_result()

    result = await service.assess(request)

    assert result.eligible is False
    assert "FAIL_CTH_NOT_MET" in result.failures
    deps["general_origin_rules_service"].evaluate.assert_not_called()


@pytest.mark.asyncio
async def test_architecture_blocker_rule_status_pending_skips_pathway_evaluation_and_persists_audit() -> None:
    """Architecture rule: pending PSR status must block before any pathway evaluation."""

    service, deps = _service()
    request = _request(
        hs6_code="030389",
        facts=[_fact("wholly_obtained", "boolean", fact_value_boolean=True)],
        case_id=str(_uuid(230)),
    )
    deps["classification_service"].resolve_hs6.return_value = _product("030389")
    deps["rule_resolution_service"].resolve_rule_bundle.return_value = _rule_bundle(
        hs6_code="030389",
        rule_status=RuleStatusEnum.PENDING,
        pathway_code="WO",
        expression_json={"op": "fact_eq", "fact": "wholly_obtained", "value": True},
    )
    deps["tariff_resolution_service"].resolve_tariff_bundle.return_value = _tariff_result()
    deps["status_service"].get_status_overlay.return_value = _status_overlay(
        "in_force",
        "complete",
        "Corridor is operational.",
    )

    result = await service.assess(request)

    assert result.eligible is False
    assert result.pathway_used is None
    assert result.failures == ["RULE_STATUS_PENDING"]
    assert result.missing_facts == []
    assert result.confidence_class == "provisional"
    deps["intelligence_service"].build_assessment_alert_specs.assert_called_once()
    assert deps["status_service"].get_status_overlay.await_args_list == [
        call("corridor", "CORRIDOR:GHA:NGA:030389", date(2025, 1, 1)),
        call("psr_rule", f"PSR:{_uuid(10)}", date(2025, 1, 1)),
    ]
    deps["fact_normalization_service"].normalize_facts.assert_not_called()
    deps["expression_evaluator"].evaluate.assert_not_called()
    deps["general_origin_rules_service"].evaluate.assert_not_called()
    deps["evidence_service"].build_readiness.assert_not_called()
    _assert_persisted_blocker_audit(
        deps,
        case_id=str(_uuid(230)),
        blocker_check_code="RULE_STATUS",
        failure_codes=["RULE_STATUS_PENDING"],
        details_json={"failure_code": "RULE_STATUS_PENDING"},
    )


@pytest.mark.asyncio
async def test_architecture_blocker_rule_status_partially_agreed_skips_pathway_evaluation_and_persists_audit() -> None:
    """Architecture rule: partially-agreed PSR status must block before any pathway evaluation."""

    service, deps = _service()
    request = _request(
        hs6_code="030389",
        facts=[_fact("wholly_obtained", "boolean", fact_value_boolean=True)],
        case_id=str(_uuid(231)),
    )
    deps["classification_service"].resolve_hs6.return_value = _product("030389")
    deps["rule_resolution_service"].resolve_rule_bundle.return_value = _rule_bundle(
        hs6_code="030389",
        rule_status=RuleStatusEnum.PARTIALLY_AGREED,
        pathway_code="WO",
        expression_json={"op": "fact_eq", "fact": "wholly_obtained", "value": True},
    )
    deps["tariff_resolution_service"].resolve_tariff_bundle.return_value = _tariff_result()
    deps["status_service"].get_status_overlay.return_value = _status_overlay(
        "in_force",
        "complete",
        "Corridor is operational.",
    )

    result = await service.assess(request)

    assert result.eligible is False
    assert result.pathway_used is None
    assert result.failures == ["RULE_STATUS_PENDING"]
    assert result.missing_facts == []
    assert result.confidence_class == "provisional"
    deps["fact_normalization_service"].normalize_facts.assert_not_called()
    deps["expression_evaluator"].evaluate.assert_not_called()
    deps["general_origin_rules_service"].evaluate.assert_not_called()
    deps["evidence_service"].build_readiness.assert_not_called()
    _assert_persisted_blocker_audit(
        deps,
        case_id=str(_uuid(231)),
        blocker_check_code="RULE_STATUS",
        failure_codes=["RULE_STATUS_PENDING"],
        details_json={"failure_code": "RULE_STATUS_PENDING"},
    )


@pytest.mark.asyncio
async def test_missing_facts_returns_incomplete_confidence() -> None:
    """Missing core facts for all pathways should produce an incomplete result."""

    service, deps = _service()
    request = _request(
        hs6_code="271019",
        facts=[_fact("direct_transport", "boolean", fact_value_boolean=True)],
    )
    deps["classification_service"].resolve_hs6.return_value = _product("271019")
    deps["rule_resolution_service"].resolve_rule_bundle.return_value = _rule_bundle(
        hs6_code="271019",
        pathway_code="VNM",
        expression_json={"op": "formula_lte", "formula": "vnom_percent", "value": 60},
    )
    deps["tariff_resolution_service"].resolve_tariff_bundle.return_value = _tariff_result()
    deps["status_service"].get_status_overlay.return_value = _status_overlay(
        "in_force",
        "complete",
        "Corridor is operational.",
    )

    result = await service.assess(request)

    assert result.eligible is False
    assert result.confidence_class == "incomplete"
    assert set(result.missing_facts) == {"ex_works", "non_originating"}


@pytest.mark.asyncio
async def test_architecture_blocker_missing_core_facts_for_all_pathways_skips_pathway_evaluation_and_persists_audit() -> None:
    """Architecture rule: missing core facts for all pathways must block before pathway evaluation."""

    service, deps = _service()
    request = _request(
        hs6_code="110311",
        facts=[_fact("direct_transport", "boolean", fact_value_boolean=True)],
        case_id=str(_uuid(240)),
    )
    deps["classification_service"].resolve_hs6.return_value = _product("110311")
    deps["rule_resolution_service"].resolve_rule_bundle.return_value = _rule_bundle(
        hs6_code="110311",
        pathway_code="CTH",
        expression_json={
            "op": "every_non_originating_input",
            "test": {"op": "heading_ne_output"},
        },
    )
    deps["tariff_resolution_service"].resolve_tariff_bundle.return_value = _tariff_result()
    deps["status_service"].get_status_overlay.return_value = _status_overlay(
        "in_force",
        "complete",
        "Corridor is operational.",
    )

    result = await service.assess(request)

    assert result.eligible is False
    assert result.pathway_used is None
    assert result.confidence_class == "incomplete"
    assert result.missing_facts == ["non_originating_inputs", "output_hs6_code"]
    assert result.failures == ["MISSING_CORE_FACTS"]
    deps["fact_normalization_service"].normalize_facts.assert_not_called()
    deps["expression_evaluator"].evaluate.assert_not_called()
    deps["general_origin_rules_service"].evaluate.assert_not_called()
    deps["evidence_service"].build_readiness.assert_not_called()
    _assert_persisted_blocker_audit(
        deps,
        case_id=str(_uuid(240)),
        blocker_check_code="MISSING_CORE_FACTS",
        failure_codes=["MISSING_CORE_FACTS"],
        details_json={
            "failure_code": "MISSING_CORE_FACTS",
            "missing_facts": ["non_originating_inputs", "output_hs6_code"],
        },
    )


@pytest.mark.asyncio
async def test_assessment_session_context_uses_repeatable_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """Assessment sessions should bind to a repeatable-read transaction."""

    captured: dict[str, object] = {}

    class FakeTransaction:
        async def __aenter__(self) -> None:
            captured["transaction_started"] = True

        async def __aexit__(self, exc_type, exc, tb) -> None:
            captured["transaction_closed"] = True

    class FakeSession:
        async def __aenter__(self) -> FakeSession:
            captured["session_entered"] = True
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            captured["session_exited"] = True

        def begin(self) -> FakeTransaction:
            captured["begin_called"] = True
            return FakeTransaction()

    class FakeFactory:
        def __init__(self, session: FakeSession) -> None:
            self._session = session

        def __call__(self) -> FakeSession:
            captured["factory_called"] = True
            return self._session

    class FakeConnection:
        async def execution_options(self, **kwargs: object) -> FakeConnection:
            captured["execution_options"] = kwargs
            return self

    class FakeConnectionContext:
        def __init__(self, connection: FakeConnection) -> None:
            self._connection = connection

        async def __aenter__(self) -> FakeConnection:
            captured["connection_entered"] = True
            return self._connection

        async def __aexit__(self, exc_type, exc, tb) -> None:
            captured["connection_exited"] = True

    class FakeEngine:
        def __init__(self, connection: FakeConnection) -> None:
            self._connection = connection

        def connect(self) -> FakeConnectionContext:
            captured["connect_called"] = True
            return FakeConnectionContext(self._connection)

    fake_connection = FakeConnection()
    fake_session = FakeSession()

    monkeypatch.setattr(session_module, "get_engine", lambda: FakeEngine(fake_connection))

    def _fake_factory(*, bind=None):
        captured["bound_connection"] = bind
        return FakeFactory(fake_session)

    monkeypatch.setattr(
        session_module,
        "get_async_session_factory",
        _fake_factory,
    )

    async with session_module.assessment_session_context() as session:
        assert session is fake_session

    assert captured["execution_options"] == {
        "isolation_level": session_module.ASSESSMENT_ISOLATION_LEVEL,
    }
    assert captured["bound_connection"] is fake_connection
    assert captured["begin_called"] is True
    assert captured["transaction_started"] is True
    assert captured["transaction_closed"] is True


@pytest.mark.asyncio
async def test_general_rules_fail_after_passing_psr() -> None:
    """A passing pathway can still fail the general rules layer."""

    service, deps = _service()
    request = _request(
        hs6_code="110311",
        facts=[
            _fact("tariff_heading_input", "text", fact_value_text="1001"),
            _fact("tariff_heading_output", "text", fact_value_text="1103"),
            _fact("direct_transport", "boolean", fact_value_boolean=False),
        ],
    )
    deps["classification_service"].resolve_hs6.return_value = _product("110311")
    deps["rule_resolution_service"].resolve_rule_bundle.return_value = _rule_bundle(hs6_code="110311")
    deps["tariff_resolution_service"].resolve_tariff_bundle.return_value = _tariff_result()
    deps["status_service"].get_status_overlay.side_effect = [
        _status_overlay("in_force", "complete", "Corridor is operational."),
        _status_overlay("agreed", "complete", "Rule is agreed."),
    ]
    deps["fact_normalization_service"].normalize_facts.return_value = {
        "tariff_heading_input": "1001",
        "tariff_heading_output": "1103",
        "direct_transport": False,
    }
    deps["expression_evaluator"].evaluate.return_value = _expression_result(
        passed=True,
        explanation=FAILURE_CODES["FAIL_CTH_NOT_MET"],
    )
    deps["general_origin_rules_service"].evaluate.return_value = _general_rules_result(
        passed=False,
        failure_codes=["FAIL_DIRECT_TRANSPORT"],
    )
    deps["evidence_service"].build_readiness.return_value = _evidence_result()

    result = await service.assess(request)

    assert result.eligible is False
    assert "FAIL_DIRECT_TRANSPORT" in result.failures


@pytest.mark.asyncio
async def test_architecture_blocker_missing_tariff_schedule_skips_pathway_evaluation_and_persists_audit() -> None:
    """Architecture rule: missing tariff schedule coverage must block before pathway evaluation."""

    service, deps = _service()
    request = _request(
        hs6_code="110311",
        facts=[
            _fact("tariff_heading_input", "text", fact_value_text="1001"),
            _fact("tariff_heading_output", "text", fact_value_text="1103"),
            _fact("direct_transport", "boolean", fact_value_boolean=True),
        ],
        case_id=str(_uuid(250)),
    )
    deps["classification_service"].resolve_hs6.return_value = _product("110311")
    deps["rule_resolution_service"].resolve_rule_bundle.return_value = _rule_bundle(hs6_code="110311")
    deps["tariff_resolution_service"].resolve_tariff_bundle.side_effect = TariffNotFoundError(
        "No tariff schedule found"
    )
    deps["status_service"].get_status_overlay.side_effect = [
        _status_overlay("in_force", "complete", "Corridor is operational."),
        _status_overlay("agreed", "complete", "Rule is agreed."),
    ]
    result = await service.assess(request)

    assert result.eligible is False
    assert result.pathway_used is None
    assert result.failures == ["NO_SCHEDULE"]
    assert result.missing_facts == []
    assert result.tariff_outcome is None
    assert result.confidence_class == "complete"
    assert deps["status_service"].get_status_overlay.await_args_list == [
        call("corridor", "CORRIDOR:GHA:NGA:110311", date(2025, 1, 1)),
        call("psr_rule", f"PSR:{_uuid(10)}", date(2025, 1, 1)),
    ]
    deps["fact_normalization_service"].normalize_facts.assert_not_called()
    deps["expression_evaluator"].evaluate.assert_not_called()
    deps["general_origin_rules_service"].evaluate.assert_not_called()
    deps["evidence_service"].build_readiness.assert_not_called()
    deps["intelligence_service"].build_assessment_alert_specs.assert_called_once()
    persisted_checks = _assert_persisted_blocker_audit(
        deps,
        case_id=str(_uuid(250)),
        blocker_check_code="NO_SCHEDULE",
        failure_codes=["NO_SCHEDULE"],
        details_json={
            "failure_code": "NO_SCHEDULE",
            "blocked_before_pathway_evaluation": True,
        },
    )
    assert any(
        check["check_code"] == "TARIFF_RESOLUTION" and check["passed"] is False
        for check in persisted_checks
    )


@pytest.mark.asyncio
async def test_architecture_blocker_corridor_not_yet_operational_skips_pathway_evaluation_and_persists_audit() -> None:
    """Architecture rule: not-yet-operational corridors must block before pathway evaluation."""

    service, deps = _service()
    request = _request(
        hs6_code="110311",
        facts=[
            _fact("tariff_heading_input", "text", fact_value_text="1001"),
            _fact("tariff_heading_output", "text", fact_value_text="1103"),
            _fact("direct_transport", "boolean", fact_value_boolean=True),
        ],
        case_id=str(_uuid(260)),
    )
    deps["classification_service"].resolve_hs6.return_value = _product("110311")
    deps["rule_resolution_service"].resolve_rule_bundle.return_value = _rule_bundle(hs6_code="110311")
    deps["tariff_resolution_service"].resolve_tariff_bundle.return_value = _tariff_result()
    deps["status_service"].get_status_overlay.return_value = _status_overlay(
        "not_yet_operational",
        "incomplete",
        "Corridor is not yet operational.",
    )

    result = await service.assess(request)

    assert result.eligible is False
    assert result.pathway_used is None
    assert result.failures == ["NOT_OPERATIONAL"]
    assert result.missing_facts == []
    assert result.confidence_class == "incomplete"
    deps["fact_normalization_service"].normalize_facts.assert_not_called()
    deps["expression_evaluator"].evaluate.assert_not_called()
    deps["general_origin_rules_service"].evaluate.assert_not_called()
    deps["evidence_service"].build_readiness.assert_not_called()
    deps["intelligence_service"].build_assessment_alert_specs.assert_called_once()
    _assert_persisted_blocker_audit(
        deps,
        case_id=str(_uuid(260)),
        blocker_check_code="NOT_OPERATIONAL",
        failure_codes=["NOT_OPERATIONAL"],
        details_json={"failure_code": "NOT_OPERATIONAL"},
    )


@pytest.mark.asyncio
async def test_intelligence_service_emits_expected_alert_types_for_supported_conditions() -> None:
    """The intelligence service should create advisory alerts for the initial trigger set."""

    repository = AsyncMock()
    repository.get_active_alerts.side_effect = [[], [], []]
    repository.create_alert.side_effect = [
        {"alert_type": "rule_status_changed"},
        {"alert_type": "data_quality_issue"},
        {"alert_type": "corridor_risk_changed"},
    ]
    service = IntelligenceService(repository)
    request = EligibilityRequest(
        hs6_code="110311",
        hs_version="HS2017",
        exporter="GHA",
        importer="NGA",
        year=2025,
        persona_mode="exporter",
        production_facts=[_fact("direct_transport", "boolean", fact_value_boolean=True)],
        case_id=str(_uuid(500)),
    )
    assessment_response = EligibilityAssessmentResponse(
        hs6_code="110311",
        eligible=False,
        pathway_used=None,
        rule_status=RuleStatusEnum.PENDING,
        tariff_outcome=None,
        failures=["RULE_STATUS_PENDING", "NOT_OPERATIONAL"],
        missing_facts=[],
        evidence_required=[],
        missing_evidence=[],
        readiness_score=None,
        completeness_ratio=None,
        confidence_class="incomplete",
    )

    created = await service.emit_assessment_alerts(
        request=request,
        rule_bundle=_rule_bundle(hs6_code="110311", rule_status=RuleStatusEnum.PENDING),
        tariff_result=None,
        corridor_overlay=_status_overlay(
            "not_yet_operational",
            "incomplete",
            "Corridor is not yet operational.",
        ),
        response=assessment_response,
    )

    assert len(created) == 3
    assert repository.get_active_alerts.await_count == 3
    created_specs = [call.args[0] for call in repository.create_alert.await_args_list]
    assert [spec["alert_type"] for spec in created_specs] == [
        AlertTypeEnum.RULE_STATUS_CHANGED,
        AlertTypeEnum.DATA_QUALITY_ISSUE,
        AlertTypeEnum.CORRIDOR_RISK_CHANGED,
    ]
    assert [spec["severity"] for spec in created_specs] == [
        AlertSeverityEnum.HIGH,
        AlertSeverityEnum.MEDIUM,
        AlertSeverityEnum.CRITICAL,
    ]
    assert all(spec["alert_status"] == AlertStatusEnum.OPEN for spec in created_specs)
    assert all(spec["alert_payload"]["advisory_only"] is True for spec in created_specs)


@pytest.mark.asyncio
async def test_intelligence_service_skips_duplicate_open_alert_types_for_same_entity() -> None:
    """Open alerts of the same type should not be duplicated for the same entity."""

    repository = AsyncMock()
    repository.get_active_alerts.return_value = [
        {
            "alert_id": _uuid(700),
            "alert_type": AlertTypeEnum.RULE_STATUS_CHANGED.value,
            "entity_type": "psr_rule",
            "entity_key": f"PSR:{_uuid(10)}",
        }
    ]
    service = IntelligenceService(repository)
    request = EligibilityRequest(
        hs6_code="110311",
        hs_version="HS2017",
        exporter="GHA",
        importer="NGA",
        year=2025,
        persona_mode="exporter",
        production_facts=[_fact("direct_transport", "boolean", fact_value_boolean=True)],
    )
    assessment_response = EligibilityAssessmentResponse(
        hs6_code="110311",
        eligible=False,
        pathway_used=None,
        rule_status=RuleStatusEnum.PENDING,
        tariff_outcome=None,
        failures=["RULE_STATUS_PENDING"],
        missing_facts=[],
        evidence_required=[],
        missing_evidence=[],
        readiness_score=None,
        completeness_ratio=None,
        confidence_class="provisional",
    )

    created = await service.emit_assessment_alerts(
        request=request,
        rule_bundle=_rule_bundle(hs6_code="110311", rule_status=RuleStatusEnum.PENDING),
        tariff_result=_tariff_result(),
        corridor_overlay=_status_overlay("in_force", "complete", "Corridor is operational."),
        response=assessment_response,
    )

    assert created == []
    repository.create_alert.assert_not_awaited()


@pytest.mark.asyncio
async def test_assess_case_loads_stored_facts_and_reuses_direct_path() -> None:
    """Stored case facts should be rehydrated into the same direct assessment request shape."""

    service, deps = _service()
    case_id = str(_uuid(300))
    deps["cases_repository"].get_case_with_facts.return_value = {
        "case": {
            "case_id": case_id,
            "hs_code": "110311",
            "hs_version": "HS2017",
            "exporter_state": "GHA",
            "importer_state": "NGA",
            "persona_mode": "exporter",
        },
        "facts": [
            {
                "fact_type": "tariff_heading_input",
                "fact_key": "tariff_heading_input",
                "fact_value_type": "text",
                "fact_value_text": "1001",
                "source_reference": None,
            },
            {
                "fact_type": "tariff_heading_output",
                "fact_key": "tariff_heading_output",
                "fact_value_type": "text",
                "fact_value_text": "1103",
                "source_reference": None,
            },
            {
                "fact_type": "direct_transport",
                "fact_key": "direct_transport",
                "fact_value_type": "boolean",
                "fact_value_boolean": True,
                "source_reference": None,
            },
        ],
    }
    deps["classification_service"].resolve_hs6.return_value = _product("110311")
    deps["rule_resolution_service"].resolve_rule_bundle.return_value = _rule_bundle(hs6_code="110311")
    deps["tariff_resolution_service"].resolve_tariff_bundle.return_value = _tariff_result()
    deps["status_service"].get_status_overlay.side_effect = [
        _status_overlay("in_force", "complete", "Corridor is operational."),
        _status_overlay("agreed", "complete", "Rule is agreed."),
    ]
    deps["fact_normalization_service"].normalize_facts.return_value = {
        "tariff_heading_input": "1001",
        "tariff_heading_output": "1103",
        "direct_transport": True,
    }
    deps["expression_evaluator"].evaluate.return_value = _expression_result(
        passed=True,
        explanation=FAILURE_CODES["FAIL_CTH_NOT_MET"],
    )
    deps["general_origin_rules_service"].evaluate.return_value = _general_rules_result(passed=True)
    deps["evidence_service"].build_readiness.return_value = _evidence_result()

    result = await service.assess_case(
        case_id,
        CaseAssessmentRequest(year=2025, existing_documents=["certificate_of_origin"]),
    )

    assert result.eligible is True
    deps["cases_repository"].get_case_with_facts.assert_awaited_once_with(case_id)
    deps["classification_service"].resolve_hs6.assert_awaited_once_with("110311", "HS2017")
    normalized_facts = deps["fact_normalization_service"].normalize_facts.call_args.args[0]
    assert [fact.fact_key for fact in normalized_facts] == [
        "tariff_heading_input",
        "tariff_heading_output",
        "direct_transport",
    ]
    persisted_evaluation = deps["evaluations_repository"].persist_evaluation.await_args.args[0]
    assert persisted_evaluation["case_id"] == case_id
    deps["evidence_service"].build_readiness.assert_awaited_once_with(
        entity_type="pathway",
        entity_key=f"PATHWAY:{_uuid(12)}",
        persona_mode=PersonaModeEnum.EXPORTER,
        existing_documents=["certificate_of_origin"],
        confidence_class="complete",
        assessment_date=date(2025, 1, 1),
    )


@pytest.mark.asyncio
async def test_assess_case_raises_when_case_is_missing() -> None:
    """Case-backed assessment should surface a domain 404 when the case does not exist."""

    service, deps = _service()
    deps["cases_repository"].get_case_with_facts.return_value = None

    with pytest.raises(CaseNotFoundError):
        await service.assess_case(str(_uuid(301)), CaseAssessmentRequest(year=2025))


@pytest.mark.asyncio
async def test_assess_interface_request_auto_creates_case_and_returns_replay_identifiers() -> None:
    """Direct interface runs without case_id should auto-create a case and hand back replay ids."""

    service, deps = _service()
    request = _request(
        hs6_code="110311",
        facts=[
            _fact("tariff_heading_input", "text", fact_value_text="1001"),
            _fact("tariff_heading_output", "text", fact_value_text="1103"),
            _fact("direct_transport", "boolean", fact_value_boolean=True),
        ],
    )
    auto_case_id = str(_uuid(400))
    evaluation_id = str(_uuid(401))
    pending_alert_spec = {
        "alert_type": "data_quality_issue",
        "entity_type": "corridor",
        "entity_key": "corridor:GHA:NGA:110311",
    }
    deps["cases_repository"].create_case.return_value = auto_case_id
    deps["evaluations_repository"].persist_evaluation.return_value = {
        "evaluation": {"evaluation_id": evaluation_id},
        "checks": [],
    }
    deps["intelligence_service"].build_assessment_alert_specs.return_value = [pending_alert_spec]
    deps["classification_service"].resolve_hs6.return_value = _product("110311")
    deps["rule_resolution_service"].resolve_rule_bundle.return_value = _rule_bundle(hs6_code="110311")
    deps["tariff_resolution_service"].resolve_tariff_bundle.return_value = _tariff_result()
    deps["status_service"].get_status_overlay.side_effect = [
        _status_overlay("in_force", "complete", "Corridor is operational."),
        _status_overlay("agreed", "complete", "Rule is agreed."),
    ]
    deps["fact_normalization_service"].normalize_facts.return_value = {
        "tariff_heading_input": "1001",
        "tariff_heading_output": "1103",
        "direct_transport": True,
    }
    deps["expression_evaluator"].evaluate.return_value = _expression_result(
        passed=True,
        explanation=FAILURE_CODES["FAIL_CTH_NOT_MET"],
    )
    deps["general_origin_rules_service"].evaluate.return_value = _general_rules_result(passed=True)
    deps["evidence_service"].build_readiness.return_value = _evidence_result()

    result = await service.assess_interface_request(request)

    assert result.case_id == auto_case_id
    assert result.evaluation_id == evaluation_id
    assert result.response.eligible is True
    assert result.pending_alert_specs == (pending_alert_spec,)

    deps["cases_repository"].create_case.assert_awaited_once()
    created_case = deps["cases_repository"].create_case.await_args.args[0]
    assert created_case["persona_mode"] == "exporter"
    assert created_case["exporter_state"] == "GHA"
    assert created_case["importer_state"] == "NGA"
    assert created_case["hs6_code"] == "110311"
    assert created_case["hs_version"] == "HS2017"
    assert created_case["submission_status"] == "submitted"
    assert created_case["created_by"] == "api:assessments"
    assert created_case["updated_by"] == "api:assessments"
    assert created_case["case_external_ref"].startswith("IFACE-ASSESS-")

    deps["cases_repository"].add_facts.assert_awaited_once()
    added_facts = deps["cases_repository"].add_facts.await_args.args[1]
    assert [fact["fact_key"] for fact in added_facts] == [
        "tariff_heading_input",
        "tariff_heading_output",
        "direct_transport",
    ]

    persisted_evaluation = deps["evaluations_repository"].persist_evaluation.await_args.args[0]
    assert persisted_evaluation["case_id"] == auto_case_id
    deps["evaluations_repository"].get_latest_evaluation_for_case.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_interface_request_assessment_defers_evaluation_persistence() -> None:
    """Prepared interface runs should capture replay payload without writing the evaluation yet."""

    service, deps = _service()
    request = _request(
        hs6_code="110311",
        facts=[
            _fact("tariff_heading_input", "text", fact_value_text="1001"),
            _fact("tariff_heading_output", "text", fact_value_text="1103"),
            _fact("direct_transport", "boolean", fact_value_boolean=True),
        ],
    )
    auto_case_id = str(_uuid(405))
    pending_alert_spec = {
        "alert_type": "data_quality_issue",
        "entity_type": "corridor",
        "entity_key": "corridor:GHA:NGA:110311",
    }
    deps["cases_repository"].create_case.return_value = auto_case_id
    deps["intelligence_service"].build_assessment_alert_specs.return_value = [pending_alert_spec]
    deps["classification_service"].resolve_hs6.return_value = _product("110311")
    deps["rule_resolution_service"].resolve_rule_bundle.return_value = _rule_bundle(hs6_code="110311")
    deps["tariff_resolution_service"].resolve_tariff_bundle.return_value = _tariff_result()
    deps["status_service"].get_status_overlay.side_effect = [
        _status_overlay("in_force", "complete", "Corridor is operational."),
        _status_overlay("agreed", "complete", "Rule is agreed."),
    ]
    deps["fact_normalization_service"].normalize_facts.return_value = {
        "tariff_heading_input": "1001",
        "tariff_heading_output": "1103",
        "direct_transport": True,
    }
    deps["expression_evaluator"].evaluate.return_value = _expression_result(
        passed=True,
        explanation=FAILURE_CODES["FAIL_CTH_NOT_MET"],
    )
    deps["general_origin_rules_service"].evaluate.return_value = _general_rules_result(passed=True)
    deps["evidence_service"].build_readiness.return_value = _evidence_result()

    prepared = await service.prepare_interface_request_assessment(request)

    assert prepared.case_id == auto_case_id
    assert prepared.response.eligible is True
    assert prepared.response.audit_persisted is False
    assert prepared.pending_alert_specs == (pending_alert_spec,)
    assert prepared.evaluation_persistence is not None
    assert prepared.evaluation_persistence.request.case_id == auto_case_id
    deps["evaluations_repository"].persist_evaluation.assert_not_awaited()


@pytest.mark.asyncio
async def test_assess_interface_request_raises_when_case_creation_fails() -> None:
    """Interface runs should surface case auto-create failures as replay-persistence errors."""

    service, deps = _service()
    request = _request(
        hs6_code="110311",
        facts=[
            _fact("tariff_heading_input", "text", fact_value_text="1001"),
            _fact("tariff_heading_output", "text", fact_value_text="1103"),
            _fact("direct_transport", "boolean", fact_value_boolean=True),
        ],
    )
    deps["cases_repository"].create_case.side_effect = RuntimeError("insert failed")

    with pytest.raises(EvaluationPersistenceError) as exc_info:
        await service.assess_interface_request(request)

    assert exc_info.value.detail == {
        "reason": "case_create_failed",
        "hs6_code": "110311",
    }
    deps["cases_repository"].add_facts.assert_not_awaited()


@pytest.mark.asyncio
async def test_assess_interface_request_raises_when_case_fact_persistence_fails() -> None:
    """Interface runs should surface fact-write failures as replay-persistence errors."""

    service, deps = _service()
    request = _request(
        hs6_code="110311",
        facts=[
            _fact("tariff_heading_input", "text", fact_value_text="1001"),
            _fact("tariff_heading_output", "text", fact_value_text="1103"),
            _fact("direct_transport", "boolean", fact_value_boolean=True),
        ],
    )
    auto_case_id = str(_uuid(403))
    deps["cases_repository"].create_case.return_value = auto_case_id
    deps["cases_repository"].add_facts.side_effect = RuntimeError("fact insert failed")

    with pytest.raises(EvaluationPersistenceError) as exc_info:
        await service.assess_interface_request(request)

    assert exc_info.value.detail == {
        "case_id": auto_case_id,
        "reason": "case_facts_persist_failed",
        "hs6_code": "110311",
    }
    deps["evaluations_repository"].persist_evaluation.assert_not_awaited()


@pytest.mark.asyncio
async def test_assess_interface_request_raises_when_replay_evaluation_is_missing() -> None:
    """Interface runs should fail closed if no persisted evaluation can be resolved after assessment."""

    service, deps = _service()
    request = _request(
        hs6_code="110311",
        facts=[
            _fact("tariff_heading_input", "text", fact_value_text="1001"),
            _fact("tariff_heading_output", "text", fact_value_text="1103"),
            _fact("direct_transport", "boolean", fact_value_boolean=True),
        ],
    )
    auto_case_id = str(_uuid(402))
    deps["cases_repository"].create_case.return_value = auto_case_id
    deps["evaluations_repository"].persist_evaluation.return_value = {
        "evaluation": {},
        "checks": [],
    }
    deps["classification_service"].resolve_hs6.return_value = _product("110311")
    deps["rule_resolution_service"].resolve_rule_bundle.return_value = _rule_bundle(hs6_code="110311")
    deps["tariff_resolution_service"].resolve_tariff_bundle.return_value = _tariff_result()
    deps["status_service"].get_status_overlay.side_effect = [
        _status_overlay("in_force", "complete", "Corridor is operational."),
        _status_overlay("agreed", "complete", "Rule is agreed."),
    ]
    deps["fact_normalization_service"].normalize_facts.return_value = {
        "tariff_heading_input": "1001",
        "tariff_heading_output": "1103",
        "direct_transport": True,
    }
    deps["expression_evaluator"].evaluate.return_value = _expression_result(
        passed=True,
        explanation=FAILURE_CODES["FAIL_CTH_NOT_MET"],
    )
    deps["general_origin_rules_service"].evaluate.return_value = _general_rules_result(passed=True)
    deps["evidence_service"].build_readiness.return_value = _evidence_result()

    with pytest.raises(EvaluationPersistenceError) as exc_info:
        await service.assess_interface_request(request)

    assert exc_info.value.detail == {
        "case_id": auto_case_id,
        "reason": "evaluation_not_persisted",
    }


@pytest.mark.asyncio
async def test_assess_interface_request_raises_when_evaluation_persistence_returns_no_identifier() -> None:
    """Interface runs should fail closed when persistence succeeds without an evaluation id."""

    service, deps = _service()
    request = _request(
        hs6_code="110311",
        facts=[
            _fact("tariff_heading_input", "text", fact_value_text="1001"),
            _fact("tariff_heading_output", "text", fact_value_text="1103"),
            _fact("direct_transport", "boolean", fact_value_boolean=True),
        ],
    )
    auto_case_id = str(_uuid(404))
    deps["cases_repository"].create_case.return_value = auto_case_id
    deps["evaluations_repository"].persist_evaluation.return_value = {"checks": []}
    deps["classification_service"].resolve_hs6.return_value = _product("110311")
    deps["rule_resolution_service"].resolve_rule_bundle.return_value = _rule_bundle(hs6_code="110311")
    deps["tariff_resolution_service"].resolve_tariff_bundle.return_value = _tariff_result()
    deps["status_service"].get_status_overlay.side_effect = [
        _status_overlay("in_force", "complete", "Corridor is operational."),
        _status_overlay("agreed", "complete", "Rule is agreed."),
    ]
    deps["fact_normalization_service"].normalize_facts.return_value = {
        "tariff_heading_input": "1001",
        "tariff_heading_output": "1103",
        "direct_transport": True,
    }
    deps["expression_evaluator"].evaluate.return_value = _expression_result(
        passed=True,
        explanation=FAILURE_CODES["FAIL_CTH_NOT_MET"],
    )
    deps["general_origin_rules_service"].evaluate.return_value = _general_rules_result(passed=True)
    deps["evidence_service"].build_readiness.return_value = _evidence_result()

    with pytest.raises(EvaluationPersistenceError) as exc_info:
        await service.assess_interface_request(request)

    assert exc_info.value.detail == {
        "case_id": auto_case_id,
        "reason": "evaluation_not_persisted",
    }


def test_eligibility_request_defaults_existing_documents_for_backward_compatibility() -> None:
    """Direct assessment callers should remain valid when they omit existing_documents."""

    request = _request(
        hs6_code="110311",
        facts=[_fact("direct_transport", "boolean", fact_value_boolean=True)],
    )

    assert request.existing_documents == []


def test_eligibility_request_accepts_existing_documents_inventory() -> None:
    """Direct assessment requests should accept the shared evidence document inventory field."""

    request = EligibilityRequest(
        hs6_code="110311",
        hs_version="HS2017",
        exporter="GHA",
        importer="NGA",
        year=2025,
        persona_mode="exporter",
        production_facts=[_fact("direct_transport", "boolean", fact_value_boolean=True)],
        existing_documents=["certificate_of_origin", "supplier_declaration"],
    )

    assert request.existing_documents == ["certificate_of_origin", "supplier_declaration"]


def test_case_assessment_request_defaults_existing_documents_for_backward_compatibility() -> None:
    """Case-backed assessment callers should remain valid when they omit existing_documents."""

    request = CaseAssessmentRequest(year=2025)

    assert request.existing_documents == []


def test_case_assessment_request_accepts_existing_documents_inventory() -> None:
    """Case-backed assessment requests should accept the shared evidence document inventory field."""

    request = CaseAssessmentRequest(
        year=2025,
        existing_documents=["certificate_of_origin"],
    )

    assert request.existing_documents == ["certificate_of_origin"]


@pytest.mark.asyncio
async def test_assessment_response_exposes_readiness_fields_from_evidence_service() -> None:
    """Assessment responses should surface missing evidence and readiness scores additively."""

    service, deps = _service()
    request = EligibilityRequest(
        hs6_code="110311",
        hs_version="HS2017",
        exporter="GHA",
        importer="NGA",
        year=2025,
        persona_mode="exporter",
        production_facts=[
            _fact("tariff_heading_input", "text", fact_value_text="1001"),
            _fact("tariff_heading_output", "text", fact_value_text="1103"),
            _fact("direct_transport", "boolean", fact_value_boolean=True),
        ],
        existing_documents=["certificate_of_origin"],
    )
    deps["classification_service"].resolve_hs6.return_value = _product("110311")
    deps["rule_resolution_service"].resolve_rule_bundle.return_value = _rule_bundle(hs6_code="110311")
    deps["tariff_resolution_service"].resolve_tariff_bundle.return_value = _tariff_result()
    deps["status_service"].get_status_overlay.side_effect = [
        _status_overlay("in_force", "complete", "Corridor is operational."),
        _status_overlay("agreed", "complete", "Rule is agreed."),
    ]
    deps["fact_normalization_service"].normalize_facts.return_value = {
        "tariff_heading_input": "1001",
        "tariff_heading_output": "1103",
        "direct_transport": True,
    }
    deps["expression_evaluator"].evaluate.return_value = _expression_result(
        passed=True,
        explanation=FAILURE_CODES["FAIL_CTH_NOT_MET"],
    )
    deps["general_origin_rules_service"].evaluate.return_value = _general_rules_result(passed=True)
    deps["evidence_service"].build_readiness.return_value = EvidenceReadinessResult(
        required_items=["Certificate of origin", "Supplier declaration"],
        missing_items=["Supplier declaration"],
        verification_questions=["Provide the COO"],
        readiness_score=0.5,
        completeness_ratio=0.5,
    )

    result = await service.assess(request)

    assert result.evidence_required == ["Certificate of origin", "Supplier declaration"]
    assert result.missing_evidence == ["Supplier declaration"]
    assert result.readiness_score == 0.5
    assert result.completeness_ratio == 0.5


@pytest.mark.asyncio
async def test_assessment_falls_back_to_rule_type_evidence_when_specific_targets_are_empty() -> None:
    """Readiness should fall back to rule-type templates when pathway and rule-level rows are absent."""

    service, deps = _service()
    request = EligibilityRequest(
        hs6_code="110311",
        hs_version="HS2017",
        exporter="GHA",
        importer="NGA",
        year=2025,
        persona_mode="exporter",
        production_facts=[
            _fact("tariff_heading_input", "text", fact_value_text="1001"),
            _fact("tariff_heading_output", "text", fact_value_text="1103"),
            _fact("direct_transport", "boolean", fact_value_boolean=True),
        ],
        existing_documents=[],
    )
    deps["classification_service"].resolve_hs6.return_value = _product("110311")
    deps["rule_resolution_service"].resolve_rule_bundle.return_value = _rule_bundle(hs6_code="110311")
    deps["tariff_resolution_service"].resolve_tariff_bundle.return_value = _tariff_result()
    deps["status_service"].get_status_overlay.side_effect = [
        _status_overlay("in_force", "complete", "Corridor is operational."),
        _status_overlay("agreed", "complete", "Rule is agreed."),
    ]
    deps["fact_normalization_service"].normalize_facts.return_value = {
        "tariff_heading_input": "1001",
        "tariff_heading_output": "1103",
        "direct_transport": True,
    }
    deps["expression_evaluator"].evaluate.return_value = _expression_result(
        passed=True,
        explanation=FAILURE_CODES["FAIL_CTH_NOT_MET"],
    )
    deps["general_origin_rules_service"].evaluate.return_value = _general_rules_result(passed=True)
    deps["evidence_service"].build_readiness.side_effect = [
        EvidenceReadinessResult(
            required_items=[],
            missing_items=[],
            verification_questions=[],
            readiness_score=1.0,
            completeness_ratio=1.0,
        ),
        EvidenceReadinessResult(
            required_items=[],
            missing_items=[],
            verification_questions=[],
            readiness_score=1.0,
            completeness_ratio=1.0,
        ),
        EvidenceReadinessResult(
            required_items=["Certificate of origin", "Bill of materials"],
            missing_items=["Certificate of origin", "Bill of materials"],
            verification_questions=["Do the documents support CTH?"],
            readiness_score=0.0,
            completeness_ratio=0.0,
        ),
    ]

    result = await service.assess(request)

    assert result.evidence_required == ["Certificate of origin", "Bill of materials"]
    assert result.missing_evidence == ["Certificate of origin", "Bill of materials"]
    assert result.readiness_score == 0.0
    assert result.completeness_ratio == 0.0
    assert deps["evidence_service"].build_readiness.await_args_list == [
        call(
            entity_type="pathway",
            entity_key=f"PATHWAY:{_uuid(12)}",
            persona_mode=request.persona_mode,
            existing_documents=[],
            confidence_class="complete",
            assessment_date=date(2025, 1, 1),
        ),
        call(
            entity_type="hs6_rule",
            entity_key=f"HS6_RULE:{_uuid(10)}",
            persona_mode=request.persona_mode,
            existing_documents=[],
            confidence_class="complete",
            assessment_date=date(2025, 1, 1),
        ),
        call(
            entity_type="rule_type",
            entity_key="CTH",
            persona_mode=request.persona_mode,
            existing_documents=[],
            confidence_class="complete",
            assessment_date=date(2025, 1, 1),
        ),
    ]


@pytest.mark.asyncio
async def test_persist_evaluation_attaches_rule_and_tariff_provenance_snapshots_on_write_path() -> None:
    """Persistence should freeze rule and tariff provenance before the evaluation write commits."""

    service, deps = _service()
    case_id = str(_uuid(500))
    rule_source_id = _uuid(501)
    schedule_source_id = _uuid(502)
    rate_source_id = _uuid(503)
    request = _request(
        hs6_code="110311",
        facts=[_fact("direct_transport", "boolean", fact_value_boolean=True)],
        case_id=case_id,
    )
    rule_bundle = _rule_bundle(hs6_code="110311").model_copy(
        update={
            "psr_rule": _rule_bundle(hs6_code="110311").psr_rule.model_copy(
                update={"source_id": rule_source_id}
            )
        }
    )
    tariff_result = _tariff_result().model_copy(
        update={
            "schedule_source_id": schedule_source_id,
            "rate_source_id": rate_source_id,
        }
    )
    deps["sources_repository"].get_source_snapshot.side_effect = [
        {
            "source": {
                "source_id": rule_source_id,
                "short_title": "Appendix IV",
                "version_label": "2025.01",
                "publication_date": date(2025, 1, 1),
                "effective_date": date(2025, 1, 1),
            },
            "supporting_provisions": [
                {
                    "provision_id": _uuid(510),
                    "source_id": rule_source_id,
                    "article_label": "Art. 6",
                    "clause_label": "Annex 2",
                    "topic_primary": "origin_rules",
                    "text_excerpt": "Change in tariff heading required.",
                }
            ],
        },
        {
            "source": {
                "source_id": schedule_source_id,
                "short_title": "Nigeria Schedule",
                "version_label": "2025-gazette",
                "publication_date": date(2025, 1, 1),
                "effective_date": date(2025, 1, 1),
            },
            "supporting_provisions": [
                {
                    "provision_id": _uuid(511),
                    "source_id": schedule_source_id,
                    "article_label": None,
                    "clause_label": "Schedule A",
                    "topic_primary": "tariff_schedule",
                    "text_excerpt": "Preferential rate is 0%.",
                }
            ],
        },
        {
            "source": {
                "source_id": rate_source_id,
                "short_title": "Rate Gazette",
                "version_label": "2025-rate",
                "publication_date": date(2025, 1, 1),
                "effective_date": date(2025, 1, 1),
            },
            "supporting_provisions": [
                {
                    "provision_id": _uuid(512),
                    "source_id": rate_source_id,
                    "article_label": "Art. 2",
                    "clause_label": "Rate Table",
                    "topic_primary": "tariff_schedule",
                    "text_excerpt": "The in-force preferential rate is 0%.",
                }
            ],
        },
    ]
    deps["evaluations_repository"].persist_evaluation.return_value = {
        "evaluation": {"evaluation_id": str(_uuid(520))},
        "checks": [],
    }
    response = EligibilityAssessmentResponse(
        hs6_code="110311",
        eligible=True,
        pathway_used="CTH",
        rule_status="agreed",
        tariff_outcome=service._build_tariff_outcome(tariff_result),
        failures=[],
        missing_facts=[],
        evidence_required=[],
        missing_evidence=[],
        readiness_score=1.0,
        completeness_ratio=1.0,
        confidence_class="complete",
    )
    audit_checks = [
        service._make_audit_check(
            check_type="rule",
            check_code="PSR_RESOLUTION",
            passed=True,
            severity="info",
            expected_value="110311",
            observed_value=str(rule_bundle.psr_rule.psr_id),
            explanation="Resolved the governing PSR rule bundle",
            details_json={
                "psr_rule": rule_bundle.psr_rule.model_dump(mode="json"),
                "applicability_type": rule_bundle.applicability_type,
            },
        ),
        service._make_tariff_trace_check(tariff_result),
    ]

    persisted = await service._persist_or_prepare_evaluation(
        request=request,
        assessment_date=date(2025, 1, 1),
        rule_bundle=rule_bundle,
        response=response,
        pathway_used="CTH",
        audit_checks=audit_checks,
        persist_evaluation=True,
    )

    assert persisted is True
    persisted_evaluation = deps["evaluations_repository"].persist_evaluation.await_args.args[0]
    decision_snapshot = persisted_evaluation["decision_snapshot_json"]
    rule_snapshot = decision_snapshot["rule_check"]["details_json"]["provenance_snapshot"]
    tariff_snapshot = decision_snapshot["tariff_check"]["details_json"]["provenance_snapshot"]

    assert set(rule_snapshot) == {
        "source_id",
        "short_title",
        "version_label",
        "publication_date",
        "effective_date",
        "page_ref",
        "table_ref",
        "row_ref",
        "captured_at",
        "supporting_provisions",
    }
    assert rule_snapshot["source_id"] == str(rule_source_id)
    assert rule_snapshot["short_title"] == "Appendix IV"
    assert rule_snapshot["supporting_provisions"] == [
        {
            "provision_id": str(_uuid(510)),
            "source_id": str(rule_source_id),
            "article_label": "Art. 6",
            "clause_label": "Annex 2",
            "topic_primary": "origin_rules",
            "text_excerpt": "Change in tariff heading required.",
        }
    ]

    assert set(tariff_snapshot) == {
        "schedule_source_id",
        "rate_source_id",
        "short_title",
        "version_label",
        "publication_date",
        "effective_date",
        "line_page_ref",
        "rate_page_ref",
        "table_ref",
        "row_ref",
        "captured_at",
        "supporting_provisions",
    }
    assert tariff_snapshot["schedule_source_id"] == str(schedule_source_id)
    assert tariff_snapshot["rate_source_id"] == str(rate_source_id)
    assert [item["source_id"] for item in tariff_snapshot["supporting_provisions"]] == [
        str(schedule_source_id),
        str(rate_source_id),
    ]
    assert deps["sources_repository"].get_source_snapshot.await_count == 3


@pytest.mark.asyncio
async def test_persist_evaluation_bounds_and_orders_supporting_provisions_in_snapshots() -> None:
    """Persisted supporting provisions should be deterministic, thin, and capped per source."""

    service, deps = _service()
    case_id = str(_uuid(530))
    rule_source_id = _uuid(531)
    request = _request(
        hs6_code="110311",
        facts=[_fact("direct_transport", "boolean", fact_value_boolean=True)],
        case_id=case_id,
    )
    rule_bundle = _rule_bundle(hs6_code="110311").model_copy(
        update={
            "psr_rule": _rule_bundle(hs6_code="110311").psr_rule.model_copy(
                update={"source_id": rule_source_id}
            )
        }
    )
    tariff_result = _tariff_result()
    long_text = "A" * 320

    async def _snapshot_for_source(source_id: str) -> dict[str, object]:
        if str(source_id) == str(rule_source_id):
            return {
                "source": {
                    "source_id": rule_source_id,
                    "short_title": "Appendix IV",
                    "version_label": "2025.01",
                    "publication_date": date(2025, 1, 1),
                    "effective_date": date(2025, 1, 1),
                },
                "supporting_provisions": [
                    {
                        "provision_id": _uuid(612),
                        "source_id": rule_source_id,
                        "article_ref": "Art. 1",
                        "annex_ref": "Clause A",
                        "topic_primary": "origin_rules",
                        "provision_text_verbatim": long_text,
                        "authority_weight": Decimal("2.000"),
                    },
                    {
                        "provision_id": _uuid(615),
                        "source_id": rule_source_id,
                        "article_ref": "Art. 5",
                        "annex_ref": "Clause E",
                        "topic_primary": "origin_rules",
                        "provision_text_verbatim": "Provision E",
                        "authority_weight": Decimal("0.500"),
                    },
                    {
                        "provision_id": _uuid(610),
                        "source_id": rule_source_id,
                        "article_ref": "Art. 3",
                        "annex_ref": "Clause C",
                        "topic_primary": "origin_rules",
                        "provision_text_verbatim": "Provision C",
                        "authority_weight": Decimal("2.000"),
                    },
                    {
                        "provision_id": _uuid(611),
                        "source_id": rule_source_id,
                        "article_ref": "Art. 1",
                        "annex_ref": "Clause B",
                        "topic_primary": "origin_rules",
                        "provision_text_verbatim": "Provision B",
                        "authority_weight": Decimal("2.000"),
                    },
                    {
                        "provision_id": _uuid(614),
                        "source_id": rule_source_id,
                        "article_ref": "Art. 4",
                        "annex_ref": "Clause D",
                        "topic_primary": "origin_rules",
                        "provision_text_verbatim": "Provision D",
                        "authority_weight": Decimal("1.000"),
                    },
                    {
                        "provision_id": _uuid(616),
                        "source_id": rule_source_id,
                        "article_ref": "Art. 6",
                        "annex_ref": "Clause F",
                        "topic_primary": "origin_rules",
                        "provision_text_verbatim": "Provision F",
                        "authority_weight": Decimal("0.100"),
                    },
                    {
                        "provision_id": _uuid(613),
                        "source_id": rule_source_id,
                        "article_ref": "Art. 2",
                        "annex_ref": "Clause C",
                        "topic_primary": "origin_rules",
                        "provision_text_verbatim": "Provision C2",
                        "authority_weight": Decimal("1.500"),
                    },
                ],
            }

        return {
            "source": {
                "source_id": UUID(str(source_id)),
                "short_title": "Auxiliary source",
                "version_label": "pytest-v1",
                "publication_date": date(2025, 1, 1),
                "effective_date": date(2025, 1, 1),
            },
            "supporting_provisions": [],
        }

    deps["sources_repository"].get_source_snapshot.side_effect = _snapshot_for_source
    deps["evaluations_repository"].persist_evaluation.return_value = {
        "evaluation": {"evaluation_id": str(_uuid(540))},
        "checks": [],
    }
    response = EligibilityAssessmentResponse(
        hs6_code="110311",
        eligible=True,
        pathway_used="CTH",
        rule_status="agreed",
        tariff_outcome=service._build_tariff_outcome(tariff_result),
        failures=[],
        missing_facts=[],
        evidence_required=[],
        missing_evidence=[],
        readiness_score=1.0,
        completeness_ratio=1.0,
        confidence_class="complete",
    )
    audit_checks = [
        service._make_audit_check(
            check_type="rule",
            check_code="PSR_RESOLUTION",
            passed=True,
            severity="info",
            expected_value="110311",
            observed_value=str(rule_bundle.psr_rule.psr_id),
            explanation="Resolved the governing PSR rule bundle",
            details_json={
                "psr_rule": rule_bundle.psr_rule.model_dump(mode="json"),
                "applicability_type": rule_bundle.applicability_type,
            },
        ),
        service._make_tariff_trace_check(tariff_result),
    ]

    persisted = await service._persist_or_prepare_evaluation(
        request=request,
        assessment_date=date(2025, 1, 1),
        rule_bundle=rule_bundle,
        response=response,
        pathway_used="CTH",
        audit_checks=audit_checks,
        persist_evaluation=True,
    )

    assert persisted is True
    persisted_evaluation = deps["evaluations_repository"].persist_evaluation.await_args.args[0]
    rule_provisions = persisted_evaluation["decision_snapshot_json"]["rule_check"]["details_json"][
        "provenance_snapshot"
    ]["supporting_provisions"]

    assert len(rule_provisions) == 5
    assert [item["provision_id"] for item in rule_provisions] == [
        str(_uuid(612)),
        str(_uuid(611)),
        str(_uuid(610)),
        str(_uuid(613)),
        str(_uuid(614)),
    ]
    assert all(
        set(item) == {
            "provision_id",
            "source_id",
            "article_label",
            "clause_label",
            "topic_primary",
            "text_excerpt",
        }
        for item in rule_provisions
    )
    assert rule_provisions[0]["text_excerpt"].endswith("...")
    assert len(rule_provisions[0]["text_excerpt"]) == 280


@pytest.mark.asyncio
async def test_assess_interface_request_fails_closed_when_replay_provenance_snapshot_is_missing() -> None:
    """Interface-triggered persistence must fail closed when rule/tariff provenance cannot be frozen."""

    service, deps = _service()
    request = _request(
        hs6_code="110311",
        facts=[
            _fact("tariff_heading_input", "text", fact_value_text="1001"),
            _fact("tariff_heading_output", "text", fact_value_text="1103"),
            _fact("direct_transport", "boolean", fact_value_boolean=True),
        ],
    )
    auto_case_id = str(_uuid(541))
    deps["cases_repository"].create_case.return_value = auto_case_id
    deps["sources_repository"].get_source_snapshot.side_effect = None
    deps["sources_repository"].get_source_snapshot.return_value = None
    deps["classification_service"].resolve_hs6.return_value = _product("110311")
    deps["rule_resolution_service"].resolve_rule_bundle.return_value = _rule_bundle(hs6_code="110311")
    deps["tariff_resolution_service"].resolve_tariff_bundle.return_value = _tariff_result()
    deps["status_service"].get_status_overlay.side_effect = [
        _status_overlay("in_force", "complete", "Corridor is operational."),
        _status_overlay("agreed", "complete", "Rule is agreed."),
    ]
    deps["fact_normalization_service"].normalize_facts.return_value = {
        "tariff_heading_input": "1001",
        "tariff_heading_output": "1103",
        "direct_transport": True,
    }
    deps["expression_evaluator"].evaluate.return_value = _expression_result(
        passed=True,
        explanation=FAILURE_CODES["FAIL_CTH_NOT_MET"],
    )
    deps["general_origin_rules_service"].evaluate.return_value = _general_rules_result(passed=True)
    deps["evidence_service"].build_readiness.return_value = _evidence_result()

    with pytest.raises(EvaluationPersistenceError) as exc_info:
        await service.assess_interface_request(request)

    assert exc_info.value.detail == {
        "case_id": auto_case_id,
        "reason": "provenance_snapshot_unavailable",
        "check_code": "PSR_RESOLUTION",
        "failure_stage": "source_snapshot_missing",
        "source_id": str(_uuid(11)),
    }
    deps["evaluations_repository"].persist_evaluation.assert_not_awaited()

"""Unit tests for the eligibility orchestrator service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from uuid import UUID
from unittest.mock import AsyncMock, Mock, call

import pytest

from app.core.enums import HsLevelEnum, RuleStatusEnum, ScheduleStatusEnum, TariffCategoryEnum
from app.core.exceptions import TariffNotFoundError
from app.core.failure_codes import FAILURE_CODES
from app.schemas.assessments import EligibilityRequest
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
        resolved_rate_year=2025,
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
        missing_items=[],
        verification_questions=[],
        readiness_score=1.0,
        completeness_ratio=1.0,
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


def _request(*, hs6_code: str, facts: list[CaseFactIn]) -> EligibilityRequest:
    """Return one orchestrator request."""

    return EligibilityRequest(
        hs6_code=hs6_code,
        hs_version="HS2017",
        exporter="GHA" if hs6_code != "271019" else "CMR",
        importer="NGA",
        year=2025,
        persona_mode="exporter",
        production_facts=facts,
    )


def _service() -> tuple[EligibilityService, dict[str, object]]:
    """Create the orchestrator with mocked dependencies."""

    deps = {
        "classification_service": AsyncMock(),
        "rule_resolution_service": AsyncMock(),
        "tariff_resolution_service": AsyncMock(),
        "status_service": AsyncMock(),
        "evidence_service": AsyncMock(),
        "fact_normalization_service": Mock(),
        "expression_evaluator": Mock(),
        "general_origin_rules_service": Mock(),
        "evaluations_repository": AsyncMock(),
    }
    return EligibilityService(**deps), deps


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
    assert deps["status_service"].get_status_overlay.await_args_list == [
        call("corridor", "CORRIDOR:GHA:NGA:110311", date(2025, 1, 1)),
        call("psr_rule", f"PSR:{_uuid(10)}", date(2025, 1, 1)),
    ]


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
async def test_blocker_short_circuits_on_pending_rule_status() -> None:
    """Pending rules should halt assessment before fact normalization."""

    service, deps = _service()
    request = _request(
        hs6_code="030389",
        facts=[_fact("wholly_obtained", "boolean", fact_value_boolean=True)],
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
    assert "RULE_STATUS_PENDING" in result.failures
    deps["fact_normalization_service"].normalize_facts.assert_not_called()
    deps["expression_evaluator"].evaluate.assert_not_called()


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
async def test_missing_every_non_originating_input_facts_block_before_normalization() -> None:
    """CTH/CTSH list-input pathways should declare the special facts as core requirements."""

    service, deps = _service()
    request = _request(
        hs6_code="110311",
        facts=[_fact("direct_transport", "boolean", fact_value_boolean=True)],
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
    assert result.confidence_class == "incomplete"
    assert result.missing_facts == ["non_originating_inputs", "output_hs6_code"]
    assert "MISSING_CORE_FACTS" in result.failures


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
async def test_tariff_not_found_still_returns_assessment() -> None:
    """Missing tariffs should not hard-block the rest of the assessment."""

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
    deps["tariff_resolution_service"].resolve_tariff_bundle.side_effect = TariffNotFoundError(
        "No tariff schedule found"
    )
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
    assert result.tariff_outcome is None

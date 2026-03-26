"""Unit tests for the NIM explanation schema and service.

Tests cover:
- ExplanationResult schema: structured fields, defaults, extra-field rejection.
- ExplanationContext schema: valid construction, extra-field rejection.
- ExplanationService.generate_explanation():
  - NIM text returned when valid JSON and no contradiction.
  - fallback_used=True on NIM disabled, client error, invalid JSON, empty text.
  - fallback text is non-empty and echoes key engine fields.
  - next_steps and warnings always present (deterministic, not from NIM).
  - Contradiction guard rejects ineligible language when eligible=True.
  - Contradiction guard rejects eligible language when eligible=False.
  - Contradiction guard rejects final-determination language for incomplete.
  - Contradiction guard rejects agreed-rule language for non-agreed status.
  - Contradiction guard rejects in-force language for non-in-force tariff.
  - Neutral text passes the guard in both eligible directions.
  - System prompt contains the assessment's eligible value.
  - Persona mode affects the audience in the system prompt.
  - next_steps list missing evidence and facts correctly.
  - warnings list provisional and incomplete confidence correctly.
"""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.core.enums import RuleStatusEnum
from app.schemas.assessments import EligibilityAssessmentResponse, TariffOutcomeResponse
from app.schemas.nim.explanation import ExplanationContext, ExplanationResult
from app.services.nim.client import NimClientError
from app.services.nim.explanation_service import (
    ExplanationService,
    _build_fallback_text,
    _build_next_steps,
    _build_warnings,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assessment(
    hs6_code: str = "110311",
    eligible: bool = True,
    pathway_used: str | None = "CTH",
    rule_status: str = "agreed",
    confidence_class: str = "complete",
    failures: list[str] | None = None,
    missing_facts: list[str] | None = None,
    missing_evidence: list[str] | None = None,
    evidence_required: list[str] | None = None,
    tariff_status: str | None = None,
) -> EligibilityAssessmentResponse:
    tariff = None
    if tariff_status is not None:
        tariff = TariffOutcomeResponse(
            status=tariff_status,
            preferential_rate=Decimal("0.00"),
            base_rate=Decimal("15.00"),
        )
    return EligibilityAssessmentResponse(
        hs6_code=hs6_code,
        eligible=eligible,
        pathway_used=pathway_used,
        rule_status=RuleStatusEnum(rule_status),
        tariff_outcome=tariff,
        failures=failures or [],
        missing_facts=missing_facts or [],
        evidence_required=evidence_required or [],
        missing_evidence=missing_evidence or [],
        confidence_class=confidence_class,
    )


def _mock_client(
    return_value: str | None = None,
    raises: Exception | None = None,
) -> MagicMock:
    client = MagicMock()
    if raises is not None:
        client.generate_json = AsyncMock(side_effect=raises)
    else:
        client.generate_json = AsyncMock(return_value=return_value)
    return client


def _nim_text_json(text: str) -> str:
    return json.dumps({"text": text})


def _service(
    return_value: str | None = None,
    raises: Exception | None = None,
) -> ExplanationService:
    return ExplanationService(_mock_client(return_value, raises))


# Module-level helper so tests can call the guard without instantiating the service
def _passes_contradiction_guard_for(
    text: str, assessment: EligibilityAssessmentResponse
) -> bool:
    svc = ExplanationService(_mock_client())
    return svc._passes_contradiction_guard(text, assessment)


# ---------------------------------------------------------------------------
# ExplanationResult schema
# ---------------------------------------------------------------------------


class TestExplanationResultSchema:
    def test_defaults_are_safe(self) -> None:
        r = ExplanationResult()
        assert r.text is None
        assert r.fallback_used is False
        assert r.next_steps == []
        assert r.warnings == []

    def test_all_fields_accepted(self) -> None:
        r = ExplanationResult(
            text="The goods qualify under CTH.",
            next_steps=["Obtain certificate of origin."],
            warnings=["Rule status is provisional."],
            fallback_used=False,
        )
        assert r.text == "The goods qualify under CTH."
        assert len(r.next_steps) == 1
        assert len(r.warnings) == 1

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExplanationResult(text="ok", invented_field="bad")


class TestExplanationContextSchema:
    def test_valid_context_with_assessment(self) -> None:
        ctx = ExplanationContext(assessment=_assessment())
        assert ctx.assessment.eligible is True
        assert ctx.persona_mode is None

    def test_persona_mode_accepted(self) -> None:
        ctx = ExplanationContext(assessment=_assessment(), persona_mode="exporter")
        assert ctx.persona_mode == "exporter"

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExplanationContext(assessment=_assessment(), extra_flag=True)


# ---------------------------------------------------------------------------
# Contradiction guard — unit tests for _passes_contradiction_guard
# ---------------------------------------------------------------------------


class TestContradictionGuard:
    # eligible=True — must reject ineligible language
    def test_passes_positive_outcome_text_when_eligible(self) -> None:
        a = _assessment(eligible=True)
        assert _passes_contradiction_guard_for(
            "The goods qualify under the CTH rule.", a
        ) is True

    def test_rejects_not_eligible_text_when_eligible_true(self) -> None:
        a = _assessment(eligible=True)
        assert _passes_contradiction_guard_for(
            "The goods are not eligible for preferential treatment.", a
        ) is False

    def test_rejects_ineligible_word_when_eligible_true(self) -> None:
        a = _assessment(eligible=True)
        assert _passes_contradiction_guard_for(
            "The shipment is ineligible.", a
        ) is False

    def test_rejects_does_not_qualify_when_eligible_true(self) -> None:
        a = _assessment(eligible=True)
        assert _passes_contradiction_guard_for(
            "This product does not qualify for the AfCFTA rate.", a
        ) is False

    def test_rejects_will_not_qualify_when_eligible_true(self) -> None:
        a = _assessment(eligible=True)
        assert _passes_contradiction_guard_for(
            "The goods will not qualify under any pathway.", a
        ) is False

    # eligible=False — must reject eligible language
    def test_passes_negative_outcome_text_when_ineligible(self) -> None:
        a = _assessment(eligible=False)
        assert _passes_contradiction_guard_for(
            "The assessment shows the goods do not meet the rules of origin.", a
        ) is True

    def test_rejects_is_eligible_when_eligible_false(self) -> None:
        a = _assessment(eligible=False)
        assert _passes_contradiction_guard_for(
            "The product is eligible for a preferential rate.", a
        ) is False

    def test_rejects_qualifies_for_preferential_when_eligible_false(self) -> None:
        a = _assessment(eligible=False)
        assert _passes_contradiction_guard_for(
            "The goods qualifies for preferential treatment.", a
        ) is False

    def test_rejects_will_qualify_when_eligible_false(self) -> None:
        a = _assessment(eligible=False)
        assert _passes_contradiction_guard_for(
            "With additional facts, this will qualify.", a
        ) is False

    def test_rejects_meets_rules_of_origin_when_eligible_false(self) -> None:
        a = _assessment(eligible=False)
        assert _passes_contradiction_guard_for(
            "The product meets the rules of origin.", a
        ) is False

    # confidence_class incomplete — must reject final determination language
    def test_passes_provisional_language_for_incomplete_assessment(self) -> None:
        a = _assessment(confidence_class="incomplete")
        assert _passes_contradiction_guard_for(
            "The assessment is incomplete due to missing facts.", a
        ) is True

    def test_rejects_final_determination_for_incomplete_assessment(self) -> None:
        a = _assessment(confidence_class="incomplete")
        assert _passes_contradiction_guard_for(
            "This is a final determination of eligibility.", a
        ) is False

    def test_rejects_complete_assessment_phrase_for_incomplete(self) -> None:
        a = _assessment(confidence_class="incomplete")
        assert _passes_contradiction_guard_for(
            "A complete assessment confirms eligibility.", a
        ) is False

    def test_guard_allows_final_determination_for_complete_assessment(self) -> None:
        a = _assessment(confidence_class="complete")
        assert _passes_contradiction_guard_for(
            "This is a final determination based on complete data.", a
        ) is True

    # rule_status not agreed — must reject agreed/binding language
    def test_rejects_agreed_rule_for_provisional_status(self) -> None:
        a = _assessment(rule_status="provisional")
        assert _passes_contradiction_guard_for(
            "The agreed rule under CTH applies.", a
        ) is False

    def test_rejects_binding_rule_for_pending_status(self) -> None:
        a = _assessment(rule_status="pending")
        assert _passes_contradiction_guard_for(
            "This binding rule determines eligibility.", a
        ) is False

    def test_passes_agreed_text_when_rule_status_is_agreed(self) -> None:
        a = _assessment(rule_status="agreed")
        assert _passes_contradiction_guard_for(
            "The agreed rule confirms eligibility.", a
        ) is True

    def test_passes_text_without_rule_language_for_non_agreed(self) -> None:
        a = _assessment(rule_status="provisional")
        assert _passes_contradiction_guard_for(
            "The assessment shows the goods qualify under CTH.", a
        ) is True

    # tariff_outcome.status not in_force — must reject in-force language
    def test_rejects_rate_in_force_when_tariff_is_provisional(self) -> None:
        a = _assessment(tariff_status="provisional")
        assert _passes_contradiction_guard_for(
            "The rate in force is 0%.", a
        ) is False

    def test_rejects_currently_in_force_when_tariff_provisional(self) -> None:
        a = _assessment(tariff_status="provisional")
        assert _passes_contradiction_guard_for(
            "The preferential tariff is currently in force.", a
        ) is False

    def test_passes_in_force_language_when_tariff_is_in_force(self) -> None:
        a = _assessment(tariff_status="in_force")
        assert _passes_contradiction_guard_for(
            "The rate in force is 0% preferential.", a
        ) is True

    def test_passes_text_without_in_force_language_for_non_in_force_tariff(self) -> None:
        a = _assessment(tariff_status="provisional")
        assert _passes_contradiction_guard_for(
            "A provisional preferential rate may apply.", a
        ) is True

    def test_passes_when_no_tariff_outcome_present(self) -> None:
        a = _assessment(tariff_status=None)
        assert _passes_contradiction_guard_for(
            "No tariff outcome is available for this assessment.", a
        ) is True


# ---------------------------------------------------------------------------
# Deterministic helpers — unit tests
# ---------------------------------------------------------------------------


class TestBuildFallbackText:
    def test_eligible_fallback_uses_natural_opening(self) -> None:
        text = _build_fallback_text(_assessment(eligible=True))
        assert (
            "based on the information provided, this product qualifies "
            "for afcfta preferential treatment."
        ) in text.lower()
        assert "assessment outcome" not in text.lower()

    def test_ineligible_fallback_uses_currently_qualify_phrase(self) -> None:
        text = _build_fallback_text(_assessment(eligible=False))
        assert (
            "based on the information provided, this product does not currently "
            "qualify for afcfta preferential treatment."
        ) in text.lower()

    def test_includes_pathway_when_present(self) -> None:
        text = _build_fallback_text(_assessment(pathway_used="CTH"))
        assert "CTH" in text

    def test_includes_rule_status(self) -> None:
        text = _build_fallback_text(_assessment(rule_status="provisional"))
        assert "provisional" in text

    def test_includes_confidence_class(self) -> None:
        text = _build_fallback_text(_assessment(confidence_class="incomplete"))
        assert "incomplete" in text

    def test_includes_failures(self) -> None:
        text = _build_fallback_text(_assessment(failures=["RULE_NOT_MET"]))
        assert "RULE_NOT_MET" in text

    def test_includes_missing_facts(self) -> None:
        text = _build_fallback_text(_assessment(missing_facts=["ex_works"]))
        assert "ex works" in text.lower()

    def test_is_non_empty_string(self) -> None:
        text = _build_fallback_text(_assessment())
        assert isinstance(text, str) and len(text) > 0


class TestBuildNextSteps:
    def test_missing_evidence_generates_obtain_step(self) -> None:
        steps = _build_next_steps(_assessment(missing_evidence=["certificate_of_origin"]))
        assert any("certificate of origin" in s.lower() for s in steps)
        assert any("required to claim the preferential tariff rate" in s.lower() for s in steps)

    def test_missing_facts_generates_provide_step(self) -> None:
        steps = _build_next_steps(_assessment(missing_facts=["ex_works"]))
        assert any("ex works" in s.lower() for s in steps)
        assert any("origin assessment can continue" in s.lower() for s in steps)

    def test_eligible_with_evidence_required_and_no_missing_generates_prepare_step(self) -> None:
        steps = _build_next_steps(
            _assessment(
                eligible=True,
                evidence_required=["certificate_of_origin"],
                missing_evidence=[],
            )
        )
        assert any("prepare" in s.lower() or "evidence" in s.lower() for s in steps)

    def test_ineligible_with_no_gaps_generates_review_step(self) -> None:
        steps = _build_next_steps(
            _assessment(eligible=False, missing_facts=[], missing_evidence=[])
        )
        assert any("review" in s.lower() or "alternative" in s.lower() for s in steps)

    def test_complete_eligible_assessment_with_no_evidence_required_is_empty(self) -> None:
        steps = _build_next_steps(
            _assessment(eligible=True, missing_facts=[], missing_evidence=[], evidence_required=[])
        )
        assert steps == []


class TestBuildWarnings:
    def test_provisional_confidence_generates_warning(self) -> None:
        warnings = _build_warnings(_assessment(confidence_class="provisional", rule_status="provisional"))
        assert any("provisional" in w.lower() for w in warnings)

    def test_incomplete_confidence_generates_warning(self) -> None:
        warnings = _build_warnings(_assessment(confidence_class="incomplete"))
        assert any("incomplete" in w.lower() for w in warnings)

    def test_non_in_force_tariff_generates_warning(self) -> None:
        warnings = _build_warnings(_assessment(tariff_status="provisional"))
        assert any("provisional" in w.lower() for w in warnings)

    def test_complete_agreed_in_force_generates_no_warnings(self) -> None:
        warnings = _build_warnings(
            _assessment(
                confidence_class="complete",
                rule_status="agreed",
                tariff_status="in_force",
            )
        )
        assert warnings == []

    def test_no_tariff_outcome_generates_no_tariff_warning(self) -> None:
        warnings = _build_warnings(_assessment(tariff_status=None))
        # only check no tariff warning; confidence/rule warnings may still appear
        assert not any("tariff" in w.lower() for w in warnings)


# ---------------------------------------------------------------------------
# ExplanationService.generate_explanation — integration-style unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_nim_text_when_valid_and_no_contradiction() -> None:
    nim_text = "Ghana wheat groats qualify under the CTH rule."
    svc = _service(_nim_text_json(nim_text))
    result = await svc.generate_explanation(_assessment())
    assert result.text == nim_text
    assert result.fallback_used is False


@pytest.mark.asyncio
async def test_fallback_used_false_on_nim_success() -> None:
    svc = _service(_nim_text_json("The goods qualify."))
    result = await svc.generate_explanation(_assessment())
    assert result.fallback_used is False


@pytest.mark.asyncio
async def test_fallback_used_true_when_nim_disabled() -> None:
    svc = _service(return_value=None)
    result = await svc.generate_explanation(_assessment())
    assert result.fallback_used is True
    assert result.text is not None and len(result.text) > 0


@pytest.mark.asyncio
async def test_fallback_text_echoes_eligible_outcome() -> None:
    svc = _service(return_value=None)
    result = await svc.generate_explanation(_assessment(eligible=True))
    assert result.text is not None
    assert "qualifies for afcfta preferential treatment" in result.text.lower()


@pytest.mark.asyncio
async def test_fallback_used_true_on_nim_client_error() -> None:
    svc = _service(raises=NimClientError("timeout", reason="timeout"))
    result = await svc.generate_explanation(_assessment())
    assert result.fallback_used is True


@pytest.mark.asyncio
async def test_fallback_used_true_on_invalid_json() -> None:
    svc = _service(return_value="not valid json {{{")
    result = await svc.generate_explanation(_assessment())
    assert result.fallback_used is True


@pytest.mark.asyncio
async def test_fallback_used_true_on_empty_text_from_nim() -> None:
    svc = _service(return_value=json.dumps({"text": ""}))
    result = await svc.generate_explanation(_assessment())
    assert result.fallback_used is True


@pytest.mark.asyncio
async def test_fallback_used_true_when_nim_contradicts_eligible_true() -> None:
    """NIM says goods are ineligible but engine says eligible — guard rejects it."""
    svc = _service(
        return_value=_nim_text_json(
            "The goods are not eligible for preferential treatment under AfCFTA."
        )
    )
    result = await svc.generate_explanation(_assessment(eligible=True))
    assert result.fallback_used is True


@pytest.mark.asyncio
async def test_fallback_used_true_when_nim_contradicts_eligible_false() -> None:
    """NIM says goods are eligible but engine says not eligible — guard rejects it."""
    svc = _service(
        return_value=_nim_text_json(
            "The goods are eligible for a 0% preferential tariff."
        )
    )
    result = await svc.generate_explanation(_assessment(eligible=False))
    assert result.fallback_used is True


@pytest.mark.asyncio
async def test_fallback_used_true_when_nim_claims_final_for_incomplete() -> None:
    svc = _service(
        return_value=_nim_text_json(
            "This is a final determination confirming the goods meet origin requirements."
        )
    )
    result = await svc.generate_explanation(_assessment(confidence_class="incomplete"))
    assert result.fallback_used is True


@pytest.mark.asyncio
async def test_fallback_used_true_when_nim_claims_agreed_for_provisional_rule() -> None:
    svc = _service(
        return_value=_nim_text_json("The agreed rule under CTH has been applied.")
    )
    result = await svc.generate_explanation(_assessment(rule_status="provisional"))
    assert result.fallback_used is True


@pytest.mark.asyncio
async def test_fallback_used_true_when_nim_claims_in_force_for_provisional_tariff() -> None:
    svc = _service(
        return_value=_nim_text_json("The preferential rate in force is 0%.")
    )
    result = await svc.generate_explanation(_assessment(tariff_status="provisional"))
    assert result.fallback_used is True


# ---------------------------------------------------------------------------
# next_steps and warnings always present regardless of NIM outcome
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_next_steps_present_when_nim_succeeds() -> None:
    svc = _service(_nim_text_json("The goods qualify."))
    result = await svc.generate_explanation(
        _assessment(missing_evidence=["certificate_of_origin"])
    )
    assert any("certificate" in s.lower() for s in result.next_steps)


@pytest.mark.asyncio
async def test_next_steps_present_when_nim_fails() -> None:
    svc = _service(return_value=None)
    result = await svc.generate_explanation(
        _assessment(missing_facts=["ex_works"])
    )
    assert any("ex works" in s.lower() for s in result.next_steps)


@pytest.mark.asyncio
async def test_warnings_present_when_nim_succeeds() -> None:
    svc = _service(_nim_text_json("The assessment is provisional."))
    result = await svc.generate_explanation(
        _assessment(confidence_class="provisional", rule_status="provisional")
    )
    assert len(result.warnings) > 0
    assert any("provisional" in w.lower() for w in result.warnings)


@pytest.mark.asyncio
async def test_warnings_empty_for_complete_agreed_assessment() -> None:
    svc = _service(_nim_text_json("The goods qualify under CTH."))
    result = await svc.generate_explanation(
        _assessment(
            confidence_class="complete",
            rule_status="agreed",
            tariff_status="in_force",
        )
    )
    assert result.warnings == []


# ---------------------------------------------------------------------------
# NIM call arguments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_prompt_includes_eligible_value() -> None:
    client = _mock_client(_nim_text_json("The goods qualify."))
    svc = ExplanationService(client)
    await svc.generate_explanation(_assessment(eligible=True))

    _, call_args, _ = client.generate_json.mock_calls[0]
    prompt = call_args[0]
    assert "true" in prompt.lower() or '"eligible": true' in prompt.lower()


@pytest.mark.asyncio
async def test_system_prompt_includes_pathway_used() -> None:
    client = _mock_client(_nim_text_json("Qualifies under CTH."))
    svc = ExplanationService(client)
    await svc.generate_explanation(_assessment(pathway_used="CTH"))

    _, call_args, _ = client.generate_json.mock_calls[0]
    prompt = call_args[0]
    assert "CTH" in prompt


@pytest.mark.asyncio
async def test_system_prompt_includes_trade_context_when_provided() -> None:
    client = _mock_client(_nim_text_json("The goods qualify."))
    svc = ExplanationService(client)
    await svc.generate_explanation(
        _assessment(hs6_code="110311"),
        hs6_code="220710",
        exporter="GHA",
        importer="NGA",
    )

    _, call_args, _ = client.generate_json.mock_calls[0]
    prompt = call_args[0]
    assert "Trade context:" in prompt
    assert "HS6 product 220710" in prompt
    assert "corridor GHA to NGA" in prompt


@pytest.mark.asyncio
async def test_system_prompt_persona_exporter_sets_audience() -> None:
    client = _mock_client(_nim_text_json("You qualify."))
    svc = ExplanationService(client)
    await svc.generate_explanation(_assessment(), persona_mode="exporter")

    _, call_args, _ = client.generate_json.mock_calls[0]
    prompt = call_args[0]
    assert "exporter" in prompt.lower()
    assert "practical" in prompt.lower()
    assert "supportive" in prompt.lower()


@pytest.mark.asyncio
async def test_system_prompt_prohibits_contradiction() -> None:
    client = _mock_client(_nim_text_json("The goods qualify."))
    svc = ExplanationService(client)
    await svc.generate_explanation(_assessment())

    _, call_args, _ = client.generate_json.mock_calls[0]
    prompt = call_args[0]
    assert "contradict" in prompt.lower() or "NOT" in prompt or "not alter" in prompt.lower()


@pytest.mark.asyncio
async def test_generate_explanation_raises_nothing_on_nim_error() -> None:
    """generate_explanation must not raise even when NIM throws."""
    svc = _service(raises=NimClientError("failed", reason="connect_error"))
    result = await svc.generate_explanation(_assessment())
    assert isinstance(result, ExplanationResult)
    assert result.fallback_used is True

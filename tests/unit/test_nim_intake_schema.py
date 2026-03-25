"""Unit tests for NIM intake schemas.

Tests cover:
- HS6Candidate: hs6_code normalisation and validation
- TradeFlow: country code shape and year range
- AssessmentContext: persona_mode typing
- MaterialInput: fact_key registry validation and single-value constraint
- ProductionFacts: list behaviour
- NimConfidence: confidence range enforcement
- NimAssessmentDraft: completeness helpers and metadata separation
- Extra-field rejection on all models
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.nim.intake import (
    AssessmentContext,
    HS6Candidate,
    MaterialInput,
    NimAssessmentDraft,
    NimConfidence,
    ProductionFacts,
    TradeFlow,
)


# ---------------------------------------------------------------------------
# HS6Candidate
# ---------------------------------------------------------------------------


class TestHS6Candidate:
    def test_valid_six_digit_code_passes(self) -> None:
        c = HS6Candidate(hs6_code="110311")
        assert c.hs6_code == "110311"

    def test_punctuation_is_stripped_and_code_normalised(self) -> None:
        c = HS6Candidate(hs6_code="11.03.11")
        assert c.hs6_code == "110311"

    def test_hs8_code_truncated_to_six_digits(self) -> None:
        c = HS6Candidate(hs6_code="11031100")
        assert c.hs6_code == "110311"

    def test_hs10_code_truncated_to_six_digits(self) -> None:
        c = HS6Candidate(hs6_code="1103110000")
        assert c.hs6_code == "110311"

    def test_fewer_than_six_digits_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            HS6Candidate(hs6_code="1103")
        assert "at least 6 digits" in str(exc_info.value)

    def test_none_hs6_code_is_valid(self) -> None:
        c = HS6Candidate(hs6_code=None)
        assert c.hs6_code is None

    def test_default_hs_version_is_hs2017(self) -> None:
        c = HS6Candidate(hs6_code="110311")
        assert c.hs_version == "HS2017"

    def test_product_description_parsed_is_accepted(self) -> None:
        c = HS6Candidate(hs6_code="110311", product_description_parsed="wheat groats")
        assert c.product_description_parsed == "wheat groats"

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            HS6Candidate(hs6_code="110311", invented_field="bad")


# ---------------------------------------------------------------------------
# TradeFlow
# ---------------------------------------------------------------------------


class TestTradeFlow:
    def test_valid_corridor_passes(self) -> None:
        tf = TradeFlow(exporter="GHA", importer="NGA", year=2025)
        assert tf.exporter == "GHA"
        assert tf.importer == "NGA"
        assert tf.year == 2025

    def test_country_codes_upcased(self) -> None:
        tf = TradeFlow(exporter="gha", importer="nga", year=2025)
        assert tf.exporter == "GHA"
        assert tf.importer == "NGA"

    def test_exporter_too_short_raises(self) -> None:
        with pytest.raises(ValidationError):
            TradeFlow(exporter="GH", importer="NGA", year=2025)

    def test_exporter_too_long_raises(self) -> None:
        with pytest.raises(ValidationError):
            TradeFlow(exporter="GHANA", importer="NGA", year=2025)

    def test_year_below_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            TradeFlow(exporter="GHA", importer="NGA", year=2019)

    def test_year_above_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            TradeFlow(exporter="GHA", importer="NGA", year=2041)

    def test_all_fields_optional(self) -> None:
        tf = TradeFlow()
        assert tf.exporter is None
        assert tf.importer is None
        assert tf.year is None

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TradeFlow(exporter="GHA", importer="NGA", year=2025, corridor="GHA-NGA")


# ---------------------------------------------------------------------------
# AssessmentContext
# ---------------------------------------------------------------------------


class TestAssessmentContext:
    def test_valid_persona_modes(self) -> None:
        for mode in ("exporter", "officer", "analyst", "system"):
            ctx = AssessmentContext(persona_mode=mode)
            assert ctx.persona_mode.value == mode

    def test_invalid_persona_mode_raises(self) -> None:
        with pytest.raises(ValidationError):
            AssessmentContext(persona_mode="trader")

    def test_none_persona_mode_is_valid(self) -> None:
        ctx = AssessmentContext()
        assert ctx.persona_mode is None

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AssessmentContext(persona_mode="exporter", source="nim")


# ---------------------------------------------------------------------------
# MaterialInput
# ---------------------------------------------------------------------------


class TestMaterialInput:
    def test_valid_boolean_fact(self) -> None:
        mi = MaterialInput(fact_key="direct_transport", boolean_value=True)
        assert mi.fact_key == "direct_transport"
        assert mi.boolean_value is True

    def test_valid_text_fact(self) -> None:
        mi = MaterialInput(fact_key="tariff_heading_input", text_value="1001")
        assert mi.text_value == "1001"

    def test_valid_number_fact(self) -> None:
        mi = MaterialInput(fact_key="ex_works", number_value=Decimal("50000.00"))
        assert mi.number_value == Decimal("50000.00")

    def test_unit_passed_through(self) -> None:
        mi = MaterialInput(fact_key="ex_works", number_value=Decimal("1000"), unit="USD")
        assert mi.unit == "USD"

    def test_unknown_fact_key_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            MaterialInput(fact_key="invented_key", text_value="x")
        assert "Unknown fact_key" in str(exc_info.value)

    def test_no_value_set_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            MaterialInput(fact_key="direct_transport")
        assert "exactly one value" in str(exc_info.value)

    def test_multiple_values_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            MaterialInput(
                fact_key="tariff_heading_input",
                text_value="1001",
                boolean_value=True,
            )
        assert "exactly one value" in str(exc_info.value)

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MaterialInput(fact_key="direct_transport", boolean_value=True, source="nim")

    @pytest.mark.parametrize("fact_key", [
        "ex_works",
        "non_originating",
        "tariff_heading_input",
        "tariff_heading_output",
        "wholly_obtained",
        "direct_transport",
        "cumulation_claimed",
        "specific_process_performed",
    ])
    def test_all_known_fact_keys_accepted(self, fact_key: str) -> None:
        # Use a compatible value type for each key
        from app.core.fact_keys import PRODUCTION_FACTS
        spec = PRODUCTION_FACTS[fact_key]
        if spec["type"] == "boolean":
            mi = MaterialInput(fact_key=fact_key, boolean_value=False)
        elif spec["type"] == "number":
            mi = MaterialInput(fact_key=fact_key, number_value=Decimal("1"))
        else:
            mi = MaterialInput(fact_key=fact_key, text_value="test")
        assert mi.fact_key == fact_key


# ---------------------------------------------------------------------------
# ProductionFacts
# ---------------------------------------------------------------------------


class TestProductionFacts:
    def test_empty_production_facts_valid(self) -> None:
        pf = ProductionFacts()
        assert pf.material_inputs == []

    def test_multiple_inputs_accepted(self) -> None:
        pf = ProductionFacts(material_inputs=[
            MaterialInput(fact_key="direct_transport", boolean_value=True),
            MaterialInput(fact_key="tariff_heading_input", text_value="1001"),
        ])
        assert len(pf.material_inputs) == 2

    def test_invalid_material_input_propagates_error(self) -> None:
        with pytest.raises(ValidationError):
            ProductionFacts(material_inputs=[
                {"fact_key": "invented_key", "text_value": "x"}
            ])

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProductionFacts(extra_flag=True)


# ---------------------------------------------------------------------------
# NimConfidence
# ---------------------------------------------------------------------------


class TestNimConfidence:
    def test_valid_confidence_scores(self) -> None:
        nc = NimConfidence(
            overall=0.85,
            hs6_confidence=0.9,
            corridor_confidence=0.8,
            facts_confidence=0.7,
        )
        assert nc.overall == pytest.approx(0.85)

    def test_overall_below_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            NimConfidence(overall=-0.1)

    def test_overall_above_one_raises(self) -> None:
        with pytest.raises(ValidationError):
            NimConfidence(overall=1.1)

    def test_sub_score_above_one_raises(self) -> None:
        with pytest.raises(ValidationError):
            NimConfidence(overall=0.9, hs6_confidence=1.5)

    def test_sub_scores_default_to_zero(self) -> None:
        nc = NimConfidence(overall=0.5)
        assert nc.hs6_confidence == pytest.approx(0.0)
        assert nc.corridor_confidence == pytest.approx(0.0)
        assert nc.facts_confidence == pytest.approx(0.0)

    def test_boundary_values_accepted(self) -> None:
        nc = NimConfidence(
            overall=0.0,
            hs6_confidence=1.0,
            corridor_confidence=0.0,
            facts_confidence=1.0,
        )
        assert nc.overall == pytest.approx(0.0)
        assert nc.hs6_confidence == pytest.approx(1.0)

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            NimConfidence(overall=0.9, other_score=0.5)


# ---------------------------------------------------------------------------
# NimAssessmentDraft — structure and metadata separation
# ---------------------------------------------------------------------------


def _complete_draft(**overrides) -> NimAssessmentDraft:
    """Build a draft with all required engine fields populated."""
    defaults = dict(
        product=HS6Candidate(hs6_code="110311"),
        trade_flow=TradeFlow(exporter="GHA", importer="NGA", year=2025),
        context=AssessmentContext(persona_mode="exporter"),
    )
    defaults.update(overrides)
    return NimAssessmentDraft(**defaults)


class TestNimAssessmentDraft:
    def test_complete_draft_is_complete_for_assessment(self) -> None:
        draft = _complete_draft()
        assert draft.is_complete_for_assessment() is True

    def test_missing_hs6_code_not_complete(self) -> None:
        draft = _complete_draft(product=HS6Candidate(hs6_code=None))
        assert draft.is_complete_for_assessment() is False

    def test_missing_product_not_complete(self) -> None:
        draft = _complete_draft(product=None)
        assert draft.is_complete_for_assessment() is False

    def test_missing_exporter_not_complete(self) -> None:
        draft = _complete_draft(trade_flow=TradeFlow(importer="NGA", year=2025))
        assert draft.is_complete_for_assessment() is False

    def test_missing_importer_not_complete(self) -> None:
        draft = _complete_draft(trade_flow=TradeFlow(exporter="GHA", year=2025))
        assert draft.is_complete_for_assessment() is False

    def test_missing_year_not_complete(self) -> None:
        draft = _complete_draft(trade_flow=TradeFlow(exporter="GHA", importer="NGA"))
        assert draft.is_complete_for_assessment() is False

    def test_missing_trade_flow_not_complete(self) -> None:
        draft = _complete_draft(trade_flow=None)
        assert draft.is_complete_for_assessment() is False

    def test_low_nim_confidence_not_complete(self) -> None:
        draft = _complete_draft(
            nim_confidence=NimConfidence(overall=0.5)
        )
        assert draft.is_complete_for_assessment(min_confidence=0.7) is False

    def test_high_nim_confidence_passes_threshold(self) -> None:
        draft = _complete_draft(
            nim_confidence=NimConfidence(overall=0.8)
        )
        assert draft.is_complete_for_assessment(min_confidence=0.7) is True

    def test_missing_required_facts_empty_when_complete(self) -> None:
        draft = _complete_draft()
        assert draft.missing_required_facts() == []

    def test_missing_required_facts_lists_all_absent_fields(self) -> None:
        draft = NimAssessmentDraft()
        missing = draft.missing_required_facts()
        assert "hs6_code" in missing
        assert "exporter" in missing
        assert "importer" in missing
        assert "year" in missing
        assert "persona_mode" in missing

    def test_missing_required_facts_partial(self) -> None:
        draft = NimAssessmentDraft(
            product=HS6Candidate(hs6_code="110311"),
            trade_flow=TradeFlow(exporter="GHA"),  # no importer or year
        )
        missing = draft.missing_required_facts()
        assert "hs6_code" not in missing
        assert "exporter" not in missing
        assert "importer" in missing
        assert "year" in missing

    def test_nim_metadata_does_not_affect_engine_field_presence(self) -> None:
        """nim_confidence and nim_assumptions are present but not engine fields."""
        draft = _complete_draft(
            nim_confidence=NimConfidence(overall=0.95),
            nim_assumptions=["assumed exporter persona from context"],
        )
        assert draft.nim_confidence.overall == pytest.approx(0.95)
        assert draft.nim_assumptions == ["assumed exporter persona from context"]
        # Engine fields still accessible
        assert draft.product.hs6_code == "110311"
        assert draft.trade_flow.exporter == "GHA"

    def test_existing_documents_default_empty(self) -> None:
        draft = _complete_draft()
        assert draft.existing_documents == []

    def test_existing_documents_accepted(self) -> None:
        draft = _complete_draft(
            existing_documents=["certificate_of_origin", "invoice"]
        )
        assert "certificate_of_origin" in draft.existing_documents

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            NimAssessmentDraft(submitted_documents=["certificate_of_origin"])

    def test_submitted_documents_field_name_rejected(self) -> None:
        """submitted_documents must never be accepted — use existing_documents."""
        with pytest.raises(ValidationError):
            NimAssessmentDraft(submitted_documents=["certificate_of_origin"])

    def test_production_facts_populated(self) -> None:
        draft = _complete_draft(
            production_facts=ProductionFacts(material_inputs=[
                MaterialInput(fact_key="direct_transport", boolean_value=True),
            ])
        )
        assert len(draft.production_facts.material_inputs) == 1
        assert draft.production_facts.material_inputs[0].fact_key == "direct_transport"

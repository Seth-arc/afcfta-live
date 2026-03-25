"""Unit tests for IntakeService.to_eligibility_request().

Tests cover:
- All engine fields are mapped from the draft correctly.
- NIM-only metadata (nim_confidence, nim_assumptions,
  product_description_parsed) is dropped before EligibilityRequest is built.
- MaterialInput typed values (boolean, number, text) map to CaseFactIn correctly.
- unit is passed through from MaterialInput.
- existing_documents are passed through.
- fact_type and fact_key are both set to the fact_key value.
- source_type is USER_INPUT for all NIM-extracted facts.
- ValueError is raised when any required engine field is absent.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.enums import FactValueTypeEnum
from app.schemas.nim.intake import (
    AssessmentContext,
    HS6Candidate,
    MaterialInput,
    NimAssessmentDraft,
    NimConfidence,
    ProductionFacts,
    TradeFlow,
)
from app.services.nim.intake_service import IntakeService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _service() -> IntakeService:
    """IntakeService with a None client — safe for mapping tests only."""
    return IntakeService(nim_client=None)  # type: ignore[arg-type]


def _complete_draft(**overrides: object) -> NimAssessmentDraft:
    """Complete draft with all required engine fields populated."""
    defaults: dict[str, object] = dict(
        product=HS6Candidate(hs6_code="110311"),
        trade_flow=TradeFlow(exporter="GHA", importer="NGA", year=2025),
        context=AssessmentContext(persona_mode="exporter"),
    )
    defaults.update(overrides)
    return NimAssessmentDraft(**defaults)


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------


class TestToEligibilityRequestFieldMapping:
    def test_maps_hs6_code(self) -> None:
        req = _service().to_eligibility_request(_complete_draft())
        assert req.hs6_code == "110311"

    def test_maps_hs_version(self) -> None:
        draft = _complete_draft(product=HS6Candidate(hs6_code="110311", hs_version="HS2022"))
        req = _service().to_eligibility_request(draft)
        assert req.hs_version == "HS2022"

    def test_default_hs_version_passed_through(self) -> None:
        req = _service().to_eligibility_request(_complete_draft())
        assert req.hs_version == "HS2017"

    def test_maps_exporter(self) -> None:
        req = _service().to_eligibility_request(_complete_draft())
        assert req.exporter == "GHA"

    def test_maps_importer(self) -> None:
        req = _service().to_eligibility_request(_complete_draft())
        assert req.importer == "NGA"

    def test_maps_year(self) -> None:
        req = _service().to_eligibility_request(_complete_draft())
        assert req.year == 2025

    def test_maps_persona_mode(self) -> None:
        req = _service().to_eligibility_request(_complete_draft())
        assert req.persona_mode.value == "exporter"

    def test_maps_existing_documents(self) -> None:
        draft = _complete_draft(existing_documents=["certificate_of_origin", "invoice"])
        req = _service().to_eligibility_request(draft)
        assert req.existing_documents == ["certificate_of_origin", "invoice"]

    def test_empty_existing_documents_default(self) -> None:
        req = _service().to_eligibility_request(_complete_draft())
        assert req.existing_documents == []

    def test_empty_production_facts_maps_to_empty_list(self) -> None:
        req = _service().to_eligibility_request(_complete_draft())
        assert req.production_facts == []

    def test_none_production_facts_maps_to_empty_list(self) -> None:
        draft = _complete_draft(production_facts=None)
        req = _service().to_eligibility_request(draft)
        assert req.production_facts == []


# ---------------------------------------------------------------------------
# NIM-only metadata is dropped
# ---------------------------------------------------------------------------


class TestNimMetadataDropped:
    def test_nim_confidence_not_in_eligibility_request(self) -> None:
        draft = _complete_draft(nim_confidence=NimConfidence(overall=0.95))
        req = _service().to_eligibility_request(draft)
        assert not hasattr(req, "nim_confidence")

    def test_nim_assumptions_not_in_eligibility_request(self) -> None:
        draft = _complete_draft(nim_assumptions=["assumed exporter from context"])
        req = _service().to_eligibility_request(draft)
        assert not hasattr(req, "nim_assumptions")

    def test_product_description_parsed_not_in_eligibility_request(self) -> None:
        draft = _complete_draft(
            product=HS6Candidate(hs6_code="110311", product_description_parsed="wheat groats")
        )
        req = _service().to_eligibility_request(draft)
        assert not hasattr(req, "product_description_parsed")


# ---------------------------------------------------------------------------
# MaterialInput → CaseFactIn mapping
# ---------------------------------------------------------------------------


class TestMaterialInputMapping:
    def test_boolean_fact_maps_fact_value_type(self) -> None:
        draft = _complete_draft(
            production_facts=ProductionFacts(material_inputs=[
                MaterialInput(fact_key="direct_transport", boolean_value=True),
            ])
        )
        req = _service().to_eligibility_request(draft)
        assert len(req.production_facts) == 1
        fact = req.production_facts[0]
        assert fact.fact_value_type == FactValueTypeEnum.BOOLEAN
        assert fact.fact_value_boolean is True
        assert fact.fact_value_text is None
        assert fact.fact_value_number is None

    def test_boolean_fact_maps_fact_key_and_fact_type(self) -> None:
        draft = _complete_draft(
            production_facts=ProductionFacts(material_inputs=[
                MaterialInput(fact_key="direct_transport", boolean_value=False),
            ])
        )
        req = _service().to_eligibility_request(draft)
        fact = req.production_facts[0]
        assert fact.fact_key == "direct_transport"
        assert fact.fact_type == "direct_transport"

    def test_number_fact_maps_fact_value_type(self) -> None:
        draft = _complete_draft(
            production_facts=ProductionFacts(material_inputs=[
                MaterialInput(fact_key="ex_works", number_value=Decimal("50000.00")),
            ])
        )
        req = _service().to_eligibility_request(draft)
        fact = req.production_facts[0]
        assert fact.fact_value_type == FactValueTypeEnum.NUMBER
        assert fact.fact_value_number == Decimal("50000.00")

    def test_text_fact_maps_fact_value_type(self) -> None:
        draft = _complete_draft(
            production_facts=ProductionFacts(material_inputs=[
                MaterialInput(fact_key="tariff_heading_input", text_value="1001"),
            ])
        )
        req = _service().to_eligibility_request(draft)
        fact = req.production_facts[0]
        assert fact.fact_value_type == FactValueTypeEnum.TEXT
        assert fact.fact_value_text == "1001"

    def test_unit_passed_through(self) -> None:
        draft = _complete_draft(
            production_facts=ProductionFacts(material_inputs=[
                MaterialInput(fact_key="ex_works", number_value=Decimal("1000"), unit="USD"),
            ])
        )
        req = _service().to_eligibility_request(draft)
        assert req.production_facts[0].unit == "USD"

    def test_null_unit_passed_through(self) -> None:
        draft = _complete_draft(
            production_facts=ProductionFacts(material_inputs=[
                MaterialInput(fact_key="direct_transport", boolean_value=True),
            ])
        )
        req = _service().to_eligibility_request(draft)
        assert req.production_facts[0].unit is None

    def test_source_type_is_user_input(self) -> None:
        from app.core.enums import FactSourceTypeEnum
        draft = _complete_draft(
            production_facts=ProductionFacts(material_inputs=[
                MaterialInput(fact_key="direct_transport", boolean_value=True),
            ])
        )
        req = _service().to_eligibility_request(draft)
        assert req.production_facts[0].source_type == FactSourceTypeEnum.USER_INPUT

    def test_multiple_facts_all_mapped(self) -> None:
        draft = _complete_draft(
            production_facts=ProductionFacts(material_inputs=[
                MaterialInput(fact_key="direct_transport", boolean_value=True),
                MaterialInput(fact_key="tariff_heading_input", text_value="1001"),
                MaterialInput(fact_key="ex_works", number_value=Decimal("100")),
            ])
        )
        req = _service().to_eligibility_request(draft)
        assert len(req.production_facts) == 3
        keys = [f.fact_key for f in req.production_facts]
        assert "direct_transport" in keys
        assert "tariff_heading_input" in keys
        assert "ex_works" in keys


# ---------------------------------------------------------------------------
# Missing required fields raise ValueError
# ---------------------------------------------------------------------------


class TestToEligibilityRequestMissingFields:
    def test_raises_if_hs6_code_missing(self) -> None:
        draft = _complete_draft(product=HS6Candidate(hs6_code=None))
        with pytest.raises(ValueError, match="hs6_code"):
            _service().to_eligibility_request(draft)

    def test_raises_if_product_none(self) -> None:
        draft = _complete_draft(product=None)
        with pytest.raises(ValueError, match="hs6_code"):
            _service().to_eligibility_request(draft)

    def test_raises_if_exporter_missing(self) -> None:
        draft = _complete_draft(trade_flow=TradeFlow(importer="NGA", year=2025))
        with pytest.raises(ValueError, match="exporter"):
            _service().to_eligibility_request(draft)

    def test_raises_if_importer_missing(self) -> None:
        draft = _complete_draft(trade_flow=TradeFlow(exporter="GHA", year=2025))
        with pytest.raises(ValueError, match="importer"):
            _service().to_eligibility_request(draft)

    def test_raises_if_year_missing(self) -> None:
        draft = _complete_draft(trade_flow=TradeFlow(exporter="GHA", importer="NGA"))
        with pytest.raises(ValueError, match="year"):
            _service().to_eligibility_request(draft)

    def test_raises_if_trade_flow_none(self) -> None:
        draft = _complete_draft(trade_flow=None)
        with pytest.raises(ValueError, match="exporter"):
            _service().to_eligibility_request(draft)

    def test_raises_if_persona_mode_missing(self) -> None:
        draft = _complete_draft(context=AssessmentContext(persona_mode=None))
        with pytest.raises(ValueError, match="persona_mode"):
            _service().to_eligibility_request(draft)

    def test_raises_if_context_none(self) -> None:
        draft = _complete_draft(context=None)
        with pytest.raises(ValueError, match="persona_mode"):
            _service().to_eligibility_request(draft)

    def test_error_message_lists_all_missing(self) -> None:
        draft = NimAssessmentDraft()
        with pytest.raises(ValueError) as exc_info:
            _service().to_eligibility_request(draft)
        msg = str(exc_info.value)
        assert "hs6_code" in msg
        assert "exporter" in msg
        assert "importer" in msg
        assert "year" in msg
        assert "persona_mode" in msg

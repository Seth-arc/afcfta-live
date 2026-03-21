"""Unit tests for typed fact normalization and derived-variable computation."""

from __future__ import annotations

import logging
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.enums import FactValueTypeEnum
from app.core.exceptions import ExpressionEvaluationError
from app.services.fact_normalization_service import FactNormalizationService


def build_fact(
    fact_key: str,
    fact_value_type: str | FactValueTypeEnum,
    *,
    fact_value_text: str | None = None,
    fact_value_number: float | Decimal | None = None,
    fact_value_boolean: bool | None = None,
    fact_value_json: object | None = None,
) -> dict[str, object]:
    """Build a fact payload shaped like case_input_fact data."""

    return {
        "fact_key": fact_key,
        "fact_value_type": fact_value_type,
        "fact_value_text": fact_value_text,
        "fact_value_number": fact_value_number,
        "fact_value_boolean": fact_value_boolean,
        "fact_value_json": fact_value_json,
    }


def test_normalize_facts_computes_derived_variables_for_complete_inputs() -> None:
    service = FactNormalizationService()
    facts = [
        build_fact("ex_works", "number", fact_value_number=100),
        build_fact("non_originating", "number", fact_value_number=40),
    ]

    result = service.normalize_facts(facts)

    assert result["ex_works"] == Decimal("100")
    assert result["non_originating"] == Decimal("40")
    assert result["vnom_percent"] == Decimal("40")
    assert result["va_percent"] == Decimal("60")


def test_normalize_facts_leaves_derived_variables_absent_when_source_fact_missing() -> None:
    service = FactNormalizationService()
    facts = [build_fact("non_originating", "number", fact_value_number=40)]

    result = service.normalize_facts(facts)

    assert result["non_originating"] == Decimal("40")
    assert "vnom_percent" not in result
    assert "va_percent" not in result


def test_normalize_facts_raises_for_zero_ex_works() -> None:
    service = FactNormalizationService()
    facts = [
        build_fact("ex_works", "number", fact_value_number=0),
        build_fact("non_originating", "number", fact_value_number=40),
    ]

    with pytest.raises(ExpressionEvaluationError) as exc_info:
        service.normalize_facts(facts)

    assert exc_info.value.message == "Division by zero: ex_works is 0"


def test_normalize_facts_accepts_unknown_key_and_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    service = FactNormalizationService()
    facts = [build_fact("warehouse_code", "text", fact_value_text="WH-7")]

    with caplog.at_level(logging.WARNING):
        result = service.normalize_facts(facts)

    assert result["warehouse_code"] == "WH-7"
    assert "Unknown fact key encountered during normalization: warehouse_code" in caplog.text


def test_normalize_facts_handles_mixed_types_from_object_records() -> None:
    service = FactNormalizationService()
    facts = [
        SimpleNamespace(
            fact_key="non_originating",
            fact_value_type=FactValueTypeEnum.NUMBER,
            fact_value_number=12.5,
            fact_value_text=None,
            fact_value_boolean=None,
            fact_value_json=None,
        ),
        SimpleNamespace(
            fact_key="direct_transport",
            fact_value_type=FactValueTypeEnum.BOOLEAN,
            fact_value_number=None,
            fact_value_text=None,
            fact_value_boolean=True,
            fact_value_json=None,
        ),
        SimpleNamespace(
            fact_key="specific_process_description",
            fact_value_type=FactValueTypeEnum.TEXT,
            fact_value_number=None,
            fact_value_text="Milled and polished",
            fact_value_boolean=None,
            fact_value_json=None,
        ),
    ]

    result = service.normalize_facts(facts)

    assert result["non_originating"] == Decimal("12.5")
    assert result["direct_transport"] is True
    assert result["specific_process_description"] == "Milled and polished"

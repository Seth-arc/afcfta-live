"""Normalize case facts into typed values and compute derived variables."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from app.core.exceptions import ExpressionEvaluationError
from app.core.fact_keys import PRODUCTION_FACTS

logger = logging.getLogger(__name__)


class FactNormalizationService:
    """Convert case fact records into a typed dict for expression evaluation."""

    def normalize_facts(self, case_input_facts: list[Any]) -> dict[str, Any]:
        """Normalize typed fact rows and add derived variables when source facts exist."""

        normalized_facts: dict[str, Any] = {}
        for fact in case_input_facts:
            fact_key = self._get_field(fact, "fact_key")
            if not fact_key:
                raise ExpressionEvaluationError("Fact record is missing fact_key")

            if fact_key not in PRODUCTION_FACTS:
                logger.warning("Unknown fact key encountered during normalization: %s", fact_key)

            fact_value_type = self._normalize_value_type(
                self._get_field(fact, "fact_value_type"),
                fact_key,
            )
            self._validate_declared_value_type(fact_key, fact_value_type)
            normalized_facts[fact_key] = self._extract_typed_value(
                fact,
                fact_key,
                fact_value_type,
            )

        self._add_derived_variables(normalized_facts)
        return normalized_facts

    @staticmethod
    def _get_field(fact: Any, field_name: str) -> Any:
        """Read a field from either a dict-like payload or an ORM-style object."""

        if isinstance(fact, dict):
            return fact.get(field_name)
        return getattr(fact, field_name, None)

    @staticmethod
    def _normalize_value_type(raw_value_type: Any, fact_key: str) -> str:
        """Collapse enum-backed value types to their lowercase string values."""

        normalized_value = getattr(raw_value_type, "value", raw_value_type)
        if normalized_value is None:
            raise ExpressionEvaluationError(
                f"Fact '{fact_key}' is missing fact_value_type",
                detail={"fact_key": fact_key},
            )
        return str(normalized_value).lower()

    @staticmethod
    def _validate_declared_value_type(fact_key: str, fact_value_type: str) -> None:
        """Enforce registry-defined value types for known fact keys."""

        expected_value_type = PRODUCTION_FACTS.get(fact_key, {}).get("type")
        if expected_value_type is None:
            return
        if fact_value_type == str(expected_value_type).lower():
            return
        raise ExpressionEvaluationError(
            f"Fact '{fact_key}' must use fact_value_type '{expected_value_type}'",
            detail={
                "fact_key": fact_key,
                "fact_value_type": fact_value_type,
                "expected_fact_value_type": expected_value_type,
            },
        )

    def _extract_typed_value(self, fact: Any, fact_key: str, fact_value_type: str) -> Any:
        """Return the populated typed value for the declared fact_value_type."""

        if fact_value_type == "number":
            return self._to_decimal(self._get_field(fact, "fact_value_number"))
        if fact_value_type == "text":
            return self._get_field(fact, "fact_value_text")
        if fact_value_type == "boolean":
            return self._get_field(fact, "fact_value_boolean")
        if fact_value_type == "date":
            return self._get_field(fact, "fact_value_date")
        if fact_value_type == "json":
            return self._get_field(fact, "fact_value_json")
        if fact_value_type == "list":
            value = self._get_field(fact, "fact_value_json")
            if value is not None and not isinstance(value, list):
                raise ExpressionEvaluationError(
                    f"Fact '{fact_key}' declared as list but does not contain a list value",
                    detail={"fact_key": fact_key, "fact_value_type": fact_value_type},
                )
            return value

        raise ExpressionEvaluationError(
            f"Unsupported fact_value_type '{fact_value_type}' for fact '{fact_key}'",
            detail={"fact_key": fact_key, "fact_value_type": fact_value_type},
        )

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        """Convert numeric inputs to Decimal without defaulting absent values."""

        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, bool):
            raise ExpressionEvaluationError(
                "Boolean value cannot be normalized as a number",
                detail={"value": value},
            )
        return Decimal(str(value))

    def _add_derived_variables(self, facts: dict[str, Any]) -> None:
        """Compute derived rule variables only when their source facts are available."""

        ex_works = facts.get("ex_works")
        non_originating = facts.get("non_originating")
        if ex_works is None or non_originating is None:
            return

        ex_works_decimal = self._to_decimal(ex_works)
        non_originating_decimal = self._to_decimal(non_originating)
        if ex_works_decimal == Decimal("0"):
            raise ExpressionEvaluationError("Division by zero: ex_works is 0")

        facts["vnom_percent"] = (non_originating_decimal / ex_works_decimal) * Decimal("100")
        facts["va_percent"] = (
            (ex_works_decimal - non_originating_decimal) / ex_works_decimal
        ) * Decimal("100")

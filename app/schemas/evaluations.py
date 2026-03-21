"""Pydantic response schemas for persisted evaluations and audit replay."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.core.enums import CheckSeverity, LegalOutcome, RuleStatusEnum


class EligibilityCheckResultResponse(BaseModel):
    """Serialized atomic check captured during an eligibility evaluation."""

    check_result_id: str
    evaluation_id: str
    check_type: Literal["psr", "general_rule", "status", "blocker"]
    check_code: str
    passed: bool
    severity: CheckSeverity
    expected_value: str | None = None
    observed_value: str | None = None
    explanation: str
    details_json: dict[str, Any] | list[Any] | None = None
    linked_component_id: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EligibilityEvaluationResponse(BaseModel):
    """Serialized persisted evaluation row."""

    evaluation_id: str
    case_id: str
    evaluation_date: date
    overall_outcome: LegalOutcome
    pathway_used: str | None = None
    confidence_class: Literal["complete", "provisional", "incomplete"]
    rule_status_at_evaluation: RuleStatusEnum
    tariff_status_at_evaluation: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EligibilityEvaluationAuditResponse(BaseModel):
    """Audit replay payload consisting of one evaluation and its checks."""

    evaluation: EligibilityEvaluationResponse
    checks: list[EligibilityCheckResultResponse]

    model_config = ConfigDict(from_attributes=True)

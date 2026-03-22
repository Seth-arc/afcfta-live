"""Pydantic schemas for persisted eligibility evaluations and audit checks."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import CheckSeverity, LegalOutcome, RuleStatusEnum


class EligibilityEvaluationResponse(BaseModel):
    """Stored top-level eligibility evaluation row."""

    evaluation_id: UUID
    case_id: UUID
    evaluation_date: date
    overall_outcome: LegalOutcome
    pathway_used: str | None = None
    confidence_class: str
    rule_status_at_evaluation: RuleStatusEnum | str
    tariff_status_at_evaluation: str
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class EligibilityCheckResultResponse(BaseModel):
    """Stored atomic check row linked to one evaluation."""

    check_result_id: UUID
    evaluation_id: UUID
    check_type: str
    check_code: str
    passed: bool
    severity: CheckSeverity | str
    expected_value: str | None = None
    observed_value: str | None = None
    explanation: str
    details_json: dict[str, Any] | None = None
    linked_component_id: UUID | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class EligibilityEvaluationWithChecksResponse(BaseModel):
    """Full audit replay payload for one evaluation."""

    evaluation: EligibilityEvaluationResponse
    checks: list[EligibilityCheckResultResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


EligibilityEvaluationOut = EligibilityEvaluationResponse
EligibilityCheckResultOut = EligibilityCheckResultResponse

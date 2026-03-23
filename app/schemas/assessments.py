"""Pydantic schemas for eligibility assessment requests and responses."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.countries import V01_COUNTRIES
from app.core.enums import PersonaModeEnum, RuleStatusEnum
from app.schemas.cases import CaseFactIn


def _normalize_hs6_code(value: str) -> str:
    digits_only = "".join(char for char in value if char.isdigit())
    if len(digits_only) < 6:
        raise ValueError("HS code must contain at least 6 digits")
    return digits_only[:6]


class EligibilityRequest(BaseModel):
    """Eligibility-assessment request payload for the orchestrator service."""

    hs6_code: str
    hs_version: str = "HS2017"
    exporter: str = Field(min_length=3, max_length=3)
    importer: str = Field(min_length=3, max_length=3)
    year: int = Field(ge=2020, le=2040)
    persona_mode: PersonaModeEnum
    production_facts: list[CaseFactIn]
    case_id: str | None = None

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("hs6_code")
    @classmethod
    def normalize_hs6_code(cls, value: str) -> str:
        return _normalize_hs6_code(value)

    @field_validator("exporter", "importer")
    @classmethod
    def validate_country_code(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in V01_COUNTRIES:
            raise ValueError("country code must be one of the v0.1 supported ISO alpha-3 values")
        return normalized


class CaseAssessmentRequest(BaseModel):
    """Request payload for assessing a previously stored case."""

    year: int = Field(ge=2020, le=2040)


class TariffOutcomeResponse(BaseModel):
    """Tariff outcome embedded in the final eligibility response."""

    preferential_rate: Decimal | None = None
    base_rate: Decimal | None = None
    status: str

    model_config = ConfigDict(from_attributes=True)


class EligibilityAssessmentResponse(BaseModel):
    """Final deterministic eligibility assessment response."""

    hs6_code: str
    eligible: bool
    pathway_used: str | None = None
    rule_status: RuleStatusEnum
    tariff_outcome: TariffOutcomeResponse | None = None
    failures: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    evidence_required: list[str] = Field(default_factory=list)
    confidence_class: Literal["complete", "provisional", "incomplete"]

    model_config = ConfigDict(from_attributes=True)


AssessmentRequest = EligibilityRequest
AssessmentResponse = EligibilityAssessmentResponse

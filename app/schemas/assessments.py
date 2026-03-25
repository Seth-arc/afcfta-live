"""Pydantic schemas for eligibility assessment requests and responses."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from app.core.countries import V01_COUNTRIES
from app.core.enums import PersonaModeEnum, RuleStatusEnum
from app.schemas.cases import CaseFactIn


def _normalize_hs6_code(value: str) -> str:
    digits_only = "".join(char for char in value if char.isdigit())
    if len(digits_only) < 6:
        raise ValueError("HS code must contain at least 6 digits")
    return digits_only[:6]


DOCUMENT_INVENTORY_ALIAS = AliasChoices("existing_documents", "submitted_documents")


class EligibilityRequest(BaseModel):
    """Eligibility-assessment request payload for the orchestrator service."""

    hs6_code: str
    hs_version: str = "HS2017"
    exporter: str = Field(min_length=3, max_length=3)
    importer: str = Field(min_length=3, max_length=3)
    year: int = Field(ge=2020, le=2040)
    persona_mode: PersonaModeEnum
    production_facts: list[CaseFactIn]
    existing_documents: list[str] = Field(
        default_factory=list,
        validation_alias=DOCUMENT_INVENTORY_ALIAS,
    )
    case_id: str | None = None

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "hs6_code": "110311",
                    "hs_version": "HS2017",
                    "exporter": "GHA",
                    "importer": "NGA",
                    "year": 2025,
                    "persona_mode": "exporter",
                    "production_facts": [
                        {
                            "fact_type": "tariff_heading_input",
                            "fact_key": "tariff_heading_input",
                            "fact_value_type": "text",
                            "fact_value_text": "1001",
                        },
                        {
                            "fact_type": "tariff_heading_output",
                            "fact_key": "tariff_heading_output",
                            "fact_value_type": "text",
                            "fact_value_text": "1103",
                        },
                        {
                            "fact_type": "direct_transport",
                            "fact_key": "direct_transport",
                            "fact_value_type": "boolean",
                            "fact_value_boolean": True,
                        },
                    ],
                    "existing_documents": [
                        "certificate_of_origin",
                        "bill_of_materials",
                        "invoice",
                    ],
                }
            ]
        },
    )

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
    existing_documents: list[str] = Field(
        default_factory=list,
        validation_alias=DOCUMENT_INVENTORY_ALIAS,
    )

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "year": 2025,
                    "existing_documents": [
                        "certificate_of_origin",
                        "bill_of_materials",
                        "invoice",
                    ],
                }
            ]
        },
    )


class TariffOutcomeResponse(BaseModel):
    """Tariff outcome embedded in the final eligibility response."""

    preferential_rate: Decimal | None = None
    base_rate: Decimal | None = None
    status: str
    provenance_ids: list[str] = Field(default_factory=list)

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
    missing_evidence: list[str] = Field(default_factory=list)
    readiness_score: float | None = None
    completeness_ratio: float | None = None
    confidence_class: Literal["complete", "provisional", "incomplete"]
    audit_persisted: bool = False

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "hs6_code": "110311",
                    "eligible": True,
                    "pathway_used": "CTH",
                    "rule_status": "agreed",
                    "tariff_outcome": {
                        "preferential_rate": "0.0000",
                        "base_rate": "15.0000",
                        "status": "in_force",
                        "provenance_ids": [
                            "c3d3fd71-d1b2-412e-a708-1685f1f2299f"
                        ],
                    },
                    "failures": [],
                    "missing_facts": [],
                    "evidence_required": [
                        "Certificate of origin",
                        "Bill of materials",
                        "Invoice",
                    ],
                    "missing_evidence": [],
                    "readiness_score": 1.0,
                    "completeness_ratio": 1.0,
                    "confidence_class": "complete",
                }
            ]
        },
    )


AssessmentRequest = EligibilityRequest
AssessmentResponse = EligibilityAssessmentResponse

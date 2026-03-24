"""Pydantic schemas for evidence requirements, questions, and readiness."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.enums import PersonaModeEnum, RequirementTypeEnum, VerificationRiskCategoryEnum
from pydantic import AliasChoices, BaseModel, ConfigDict, Field


DOCUMENT_INVENTORY_ALIAS = AliasChoices("existing_documents", "submitted_documents")


class EvidenceRequirementResponse(BaseModel):
    """One evidence requirement row."""

    evidence_id: UUID
    entity_type: str
    entity_key: str
    persona_mode: PersonaModeEnum
    requirement_type: RequirementTypeEnum
    requirement_description: str
    legal_basis_provision_id: UUID | None = None
    required: bool = True
    conditional_on: dict[str, Any] | None = None
    priority_level: int = 1

    model_config = ConfigDict(from_attributes=True)


class VerificationQuestionResponse(BaseModel):
    """One verification checklist question row."""

    question_id: UUID
    entity_type: str
    entity_key: str
    persona_mode: PersonaModeEnum
    question_text: str
    purpose: str
    legal_basis_provision_id: UUID | None = None
    risk_category: VerificationRiskCategoryEnum
    priority_level: int = 1
    active: bool = True
    question_order: int = 1

    model_config = ConfigDict(from_attributes=True)


class DocumentReadinessTemplateResponse(BaseModel):
    """Reusable template for expected document packs."""

    template_id: UUID
    hs_code: str
    hs_version: str | None = None
    corridor_scope: str
    origin_pathway_type: str | None = None
    required_docs: list[dict[str, Any]]
    optional_docs: list[dict[str, Any]] | None = None
    common_weaknesses: list[dict[str, Any]] | None = None
    officer_focus_points: list[dict[str, Any]] | None = None
    legal_basis_provision_ids: list[UUID] | None = None
    active: bool = True
    version_label: str | None = None
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class EvidenceReadinessRequest(BaseModel):
    """API request payload for evidence readiness checks."""

    entity_type: str
    entity_key: str
    persona_mode: PersonaModeEnum
    existing_documents: list[str] = Field(
        default_factory=list,
        validation_alias=DOCUMENT_INVENTORY_ALIAS,
    )

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "entity_type": "hs6_rule",
                    "entity_key": "HS6_RULE:8c6a4b89-4d4e-4d5b-9eb4-4d1775edb3b0",
                    "persona_mode": "exporter",
                    "existing_documents": ["certificate_of_origin"],
                }
            ]
        },
    )


class EvidenceReadinessResult(BaseModel):
    """Computed evidence readiness output."""

    required_items: list[str] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    verification_questions: list[str] = Field(default_factory=list)
    readiness_score: float
    completeness_ratio: float

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "required_items": [
                        "Certificate of origin",
                        "Bill of materials",
                        "Invoice",
                    ],
                    "missing_items": [],
                    "verification_questions": [
                        "Can the exporter provide a valid certificate of origin?"
                    ],
                    "readiness_score": 1.0,
                    "completeness_ratio": 1.0,
                }
            ]
        },
    )


EvidenceRequirementOut = EvidenceRequirementResponse
VerificationQuestionOut = VerificationQuestionResponse
DocumentReadinessTemplateOut = DocumentReadinessTemplateResponse

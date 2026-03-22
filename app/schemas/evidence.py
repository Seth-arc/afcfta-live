"""Pydantic schemas for evidence requirements, questions, and readiness."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import PersonaModeEnum, RequirementTypeEnum, VerificationRiskCategoryEnum


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
    existing_documents: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class EvidenceReadinessResult(BaseModel):
    """Computed evidence readiness output."""

    required_items: list[str] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    verification_questions: list[str] = Field(default_factory=list)
    readiness_score: float
    completeness_ratio: float

    model_config = ConfigDict(from_attributes=True)


EvidenceRequirementOut = EvidenceRequirementResponse
VerificationQuestionOut = VerificationQuestionResponse
DocumentReadinessTemplateOut = DocumentReadinessTemplateResponse

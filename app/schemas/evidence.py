"""Pydantic schemas for evidence requirements, questions, and readiness templates."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import PersonaModeEnum, RequirementTypeEnum, VerificationRiskCategoryEnum


class EvidenceRequirementResponse(BaseModel):
    """Serialized evidence requirement row."""

    evidence_id: str
    entity_type: str
    entity_key: str
    persona_mode: PersonaModeEnum
    requirement_type: RequirementTypeEnum
    requirement_description: str
    legal_basis_provision_id: str | None = None
    required: bool
    conditional_on: dict[str, Any] | None = None
    priority_level: int = Field(ge=1, le=5)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VerificationQuestionResponse(BaseModel):
    """Serialized verification question row."""

    question_id: str
    entity_type: str
    entity_key: str
    persona_mode: PersonaModeEnum
    question_text: str
    purpose: str
    legal_basis_provision_id: str | None = None
    risk_category: VerificationRiskCategoryEnum
    priority_level: int = Field(ge=1, le=5)
    active: bool
    question_order: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentReadinessTemplateResponse(BaseModel):
    """Serialized reusable document readiness pack template."""

    template_id: str
    hs_code: str = Field(pattern=r"^\d{6}$")
    hs_version: str | None = None
    corridor_scope: str
    origin_pathway_type: str | None = None
    required_docs: list[dict[str, Any]]
    optional_docs: list[dict[str, Any]] | None = None
    common_weaknesses: list[dict[str, Any]] | None = None
    officer_focus_points: list[dict[str, Any]] | None = None
    legal_basis_provision_ids: list[str] | None = None
    active: bool
    version_label: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvidenceReadinessResult(BaseModel):
    """Service-level evidence readiness summary for one entity and persona."""

    required_items: list[str] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    verification_questions: list[str] = Field(default_factory=list)
    readiness_score: float = Field(ge=0.0, le=1.0)
    completeness_ratio: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(from_attributes=True)

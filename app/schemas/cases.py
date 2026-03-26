"""Pydantic schemas for case creation and case-detail responses."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.core.enums import (
    CaseSubmissionStatusEnum,
    FactSourceTypeEnum,
    FactValueTypeEnum,
    PersonaModeEnum,
)

DOCUMENT_INVENTORY_ALIAS = AliasChoices("existing_documents", "submitted_documents")


class CaseFactIn(BaseModel):
    """Typed fact payload accepted by case creation and assessments."""

    fact_type: str
    fact_key: str
    fact_value_type: FactValueTypeEnum
    fact_value_text: str | None = None
    fact_value_number: Decimal | None = None
    fact_value_boolean: bool | None = None
    fact_value_date: date | None = None
    fact_value_json: dict[str, Any] | list[Any] | None = None
    unit: str | None = None
    source_type: FactSourceTypeEnum = FactSourceTypeEnum.USER_INPUT
    source_ref: str | None = None
    fact_order: int = 1

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class CaseCreateAssessmentOptions(BaseModel):
    """Optional one-step assessment options for POST /cases."""

    year: int = Field(ge=2020, le=2040)
    existing_documents: list[str] = Field(
        default_factory=list,
        validation_alias=DOCUMENT_INVENTORY_ALIAS,
    )

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class CaseCreateRequest(BaseModel):
    """API request payload for creating a case and attaching facts."""

    persona_mode: PersonaModeEnum
    exporter_state: str | None = None
    importer_state: str | None = None
    hs6_code: str | None = None
    hs_version: str | None = None
    declared_origin: str | None = None
    declared_pathway: str | None = None
    title: str | None = None
    notes: str | None = None
    case_external_ref: str
    assess: bool = False
    assessment: CaseCreateAssessmentOptions | None = None
    production_facts: list[CaseFactIn] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class CaseFactResponse(BaseModel):
    """Stored case fact row."""

    fact_id: UUID
    case_id: UUID
    fact_type: str
    fact_key: str
    fact_value_type: FactValueTypeEnum
    fact_value_text: str | None = None
    fact_value_number: Decimal | None = None
    fact_value_boolean: bool | None = None
    fact_value_date: date | None = None
    fact_value_json: dict[str, Any] | list[Any] | None = None
    unit: str | None = None
    source_type: FactSourceTypeEnum | None = None
    source_reference: str | None = None
    confidence_score: Decimal | None = None
    fact_order: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CaseSummaryResponse(BaseModel):
    """Stored case header row."""

    case_id: UUID
    case_external_ref: str
    persona_mode: PersonaModeEnum
    exporter_state: str | None = None
    importer_state: str | None = None
    hs_code: str | None = None
    hs_version: str | None = None
    declared_origin: str | None = None
    declared_pathway: str | None = None
    submission_status: CaseSubmissionStatusEnum
    title: str | None = None
    notes: str | None = None
    opened_at: datetime | None = None
    submitted_at: datetime | None = None
    closed_at: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CaseCreateResponse(BaseModel):
    """API response after creating a case, with optional one-step replay metadata."""

    case_id: UUID
    case: CaseSummaryResponse
    evaluation_id: UUID | None = None
    audit_url: str | None = None
    audit_persisted: bool = False

    model_config = ConfigDict(from_attributes=True)


class CaseStatusResponse(BaseModel):
    """Read model for case evaluation presence without reconstructing an audit trail."""

    case_id: UUID
    has_evaluation: bool
    latest_evaluation_id: UUID | None

    model_config = ConfigDict(from_attributes=True)


class CaseDetailResponse(BaseModel):
    """Full case payload with facts."""

    case: CaseSummaryResponse
    facts: list[CaseFactResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


CaseFileResponse = CaseSummaryResponse
CaseInputFactResponse = CaseFactResponse

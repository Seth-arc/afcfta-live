"""Pydantic schemas for case creation and case-detail responses."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    CaseSubmissionStatusEnum,
    FactSourceTypeEnum,
    FactValueTypeEnum,
    PersonaModeEnum,
)


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
    """API response after creating a case."""

    case_id: UUID
    case: CaseSummaryResponse

    model_config = ConfigDict(from_attributes=True)


class CaseDetailResponse(BaseModel):
    """Full case payload with facts."""

    case: CaseSummaryResponse
    facts: list[CaseFactResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


CaseFileResponse = CaseSummaryResponse
CaseInputFactResponse = CaseFactResponse

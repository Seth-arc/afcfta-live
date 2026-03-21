"""Pydantic schemas for status assertions and transition clauses."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import StatusTypeEnum


class StatusAssertionResponse(BaseModel):
    """Serialized current or historical status assertion row."""

    status_assertion_id: str
    source_id: str
    entity_type: str
    entity_key: str
    status_type: StatusTypeEnum
    status_text_verbatim: str
    effective_from: date | None = None
    effective_to: date | None = None
    page_ref: int | None = None
    clause_ref: str | None = None
    confidence_score: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransitionClauseResponse(BaseModel):
    """Serialized time-bound transition clause row."""

    transition_id: str
    source_id: str
    entity_type: str
    entity_key: str
    transition_type: str
    transition_text_verbatim: str
    start_date: date | None = None
    end_date: date | None = None
    review_trigger: str | None = None
    page_ref: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActiveTransitionOverlay(BaseModel):
    """Reduced transition-clause payload used by the status service overlay."""

    transition_type: str
    description: str
    start_date: date | None = None
    end_date: date | None = None
    review_trigger: str | None = None

    model_config = ConfigDict(from_attributes=True)


class StatusOverlay(BaseModel):
    """Service-level status overlay with confidence and constraint guidance."""

    status_type: StatusTypeEnum | Literal["unknown"]
    effective_from: date | None = None
    effective_to: date | None = None
    confidence_class: Literal["complete", "provisional", "incomplete"]
    active_transitions: list[ActiveTransitionOverlay] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    source_text_verbatim: str | None = None

    model_config = ConfigDict(from_attributes=True)

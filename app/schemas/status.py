"""Pydantic schemas for status assertions, transitions, and overlays."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import StatusTypeEnum


class StatusAssertionResponse(BaseModel):
    """One current or historical status assertion row."""

    status_assertion_id: UUID
    source_id: UUID
    entity_type: str
    entity_key: str
    status_type: StatusTypeEnum | str
    status_text_verbatim: str
    effective_from: date | None = None
    effective_to: date | None = None
    page_ref: int | None = None
    clause_ref: str | None = None
    confidence_score: Decimal | None = None

    model_config = ConfigDict(from_attributes=True)


class TransitionClauseResponse(BaseModel):
    """One active or historical transition clause row."""

    transition_id: UUID
    source_id: UUID
    entity_type: str
    entity_key: str
    transition_type: str
    transition_text_verbatim: str
    start_date: date | None = None
    end_date: date | None = None
    review_trigger: str | None = None
    page_ref: int | None = None

    model_config = ConfigDict(from_attributes=True)


class ActiveTransitionOverlay(BaseModel):
    """Simplified transition warning embedded in status overlays."""

    transition_type: str
    description: str
    start_date: date | None = None
    end_date: date | None = None
    review_trigger: str | None = None

    model_config = ConfigDict(from_attributes=True)


class StatusOverlay(BaseModel):
    """Computed status layer attached to engine outputs."""

    status_type: StatusTypeEnum | str
    effective_from: date | None = None
    effective_to: date | None = None
    confidence_class: str
    active_transitions: list[ActiveTransitionOverlay] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    source_text_verbatim: str | None = None

    model_config = ConfigDict(from_attributes=True)


StatusAssertionOut = StatusAssertionResponse
TransitionClauseOut = TransitionClauseResponse

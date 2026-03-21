"""Pydantic response schemas for corridor intelligence and alerts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    AlertSeverityEnum,
    AlertStatusEnum,
    AlertTypeEnum,
    CorridorStatusEnum,
)


class AlertEventResponse(BaseModel):
    """Serialized alert event row."""

    alert_id: str
    alert_type: AlertTypeEnum
    entity_type: str
    entity_key: str
    related_case_id: str | None = None
    related_assessment_id: str | None = None
    related_change_id: str | None = None
    severity: AlertSeverityEnum
    alert_status: AlertStatusEnum
    alert_message: str
    alert_payload: dict[str, Any] | None = None
    triggered_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    owner: str | None = None
    resolution_note: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CorridorProfileResponse(BaseModel):
    """Serialized corridor profile row."""

    corridor_profile_id: str
    exporter_state: str = Field(min_length=3, max_length=3)
    importer_state: str = Field(min_length=3, max_length=3)
    corridor_status: CorridorStatusEnum
    schedule_maturity_score: float = Field(ge=0, le=100)
    documentation_complexity_score: float = Field(ge=0, le=100)
    verification_risk_score: float = Field(ge=0, le=100)
    transition_exposure_score: float = Field(ge=0, le=100)
    average_tariff_relief_score: float | None = Field(default=None, ge=0, le=100)
    pending_rule_exposure_score: float | None = Field(default=None, ge=0, le=100)
    operational_notes: str | None = None
    source_summary: dict[str, Any] | None = None
    method_version: str
    active: bool
    effective_from: date | None = None
    effective_to: date | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

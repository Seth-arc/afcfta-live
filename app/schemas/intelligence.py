"""Pydantic schemas for corridor intelligence and alerts."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import AlertSeverityEnum, AlertStatusEnum, AlertTypeEnum, CorridorStatusEnum


class CorridorProfileResponse(BaseModel):
    """Corridor intelligence profile."""

    corridor_profile_id: UUID
    exporter_state: str
    importer_state: str
    corridor_status: CorridorStatusEnum
    schedule_maturity_score: Decimal
    documentation_complexity_score: Decimal
    verification_risk_score: Decimal
    transition_exposure_score: Decimal
    average_tariff_relief_score: Decimal | None = None
    pending_rule_exposure_score: Decimal | None = None
    operational_notes: str | None = None
    source_summary: dict[str, Any] | None = None
    method_version: str
    active: bool
    effective_from: date | None = None
    effective_to: date | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AlertEventResponse(BaseModel):
    """Alert notification row."""

    alert_id: UUID
    alert_type: AlertTypeEnum
    entity_type: str
    entity_key: str
    related_case_id: UUID | None = None
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
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


CorridorProfileOut = CorridorProfileResponse
AlertEventOut = AlertEventResponse

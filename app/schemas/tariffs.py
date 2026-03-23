"""Pydantic schemas for tariff schedule resolution."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.enums import RateStatusEnum, ScheduleStatusEnum, StagingTypeEnum, TariffCategoryEnum


class TariffScheduleHeaderOut(BaseModel):
    """Schedule header metadata for a corridor."""

    schedule_id: UUID
    source_id: UUID | None = None
    importing_state: str
    exporting_scope: str
    schedule_status: ScheduleStatusEnum
    publication_date: date | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    hs_version: str
    category_system: str | None = None
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class TariffScheduleLineOut(BaseModel):
    """Tariff line metadata resolved for one HS6 code."""

    schedule_line_id: UUID
    schedule_id: UUID
    hs6_id: UUID | None = None
    hs6_code: str
    hs6_display: str | None = None
    product_description: str
    tariff_category: TariffCategoryEnum
    mfn_base_rate: Decimal | None = None
    base_year: int | None = None
    target_rate: Decimal | None = None
    target_year: int | None = None
    staging_type: StagingTypeEnum
    line_page_ref: int | None = None
    table_ref: str | None = None
    row_ref: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class TariffYearRateOut(BaseModel):
    """Year-rate row, including fallback-year metadata."""

    year_rate_id: UUID | None = None
    schedule_line_id: UUID
    requested_year: int | None = None
    resolved_rate_year: int | None = None
    preferential_rate: Decimal | None = None
    rate_status: RateStatusEnum | None = None
    rate_source_id: UUID | None = None
    rate_page_ref: int | None = None
    used_fallback_rate: bool = False

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class TariffLookupResponse(BaseModel):
    """Full joined tariff lookup payload."""

    header: TariffScheduleHeaderOut
    line: TariffScheduleLineOut
    rate: TariffYearRateOut

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class TariffResolutionResult(BaseModel):
    """Collapsed tariff output used by service and route layers."""

    base_rate: Decimal | None = None
    preferential_rate: Decimal | None = None
    staging_year: int | None = None
    tariff_status: str
    tariff_category: TariffCategoryEnum | None = None
    schedule_status: ScheduleStatusEnum | None = None
    schedule_id: UUID | None = None
    schedule_line_id: UUID | None = None
    year_rate_id: UUID | None = None
    schedule_source_id: UUID | None = None
    rate_source_id: UUID | None = None
    resolved_rate_year: int | None = None
    line_page_ref: int | None = None
    rate_page_ref: int | None = None
    table_ref: str | None = None
    row_ref: str | None = None
    used_fallback_rate: bool = False

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def normalize_service_output(cls, value: Any) -> Any:
        """Accept either the service's collapsed output or a repository-style row mapping."""

        if value is None or isinstance(value, dict):
            payload = dict(value or {})
        elif hasattr(value, "model_dump"):
            payload = value.model_dump(mode="python")
        elif hasattr(value, "_mapping"):
            payload = dict(value._mapping)
        else:
            return value

        if "base_rate" not in payload and "mfn_base_rate" in payload:
            payload["base_rate"] = payload.get("mfn_base_rate")
        if "staging_year" not in payload and "resolved_rate_year" in payload:
            payload["staging_year"] = payload.get("resolved_rate_year")
        if "tariff_status" not in payload:
            payload["tariff_status"] = (
                payload.get("tariff_status")
                or payload.get("rate_status")
                or payload.get("schedule_status")
                or "unknown"
            )
        return payload


TariffScheduleRateOut = TariffYearRateOut
TariffScheduleRateByYearOut = TariffYearRateOut

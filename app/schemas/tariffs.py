"""Pydantic schemas for tariff schedule tables and tariff lookup responses."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    RateStatusEnum,
    ScheduleStatusEnum,
    StagingTypeEnum,
    TariffCategoryEnum,
)


class TariffScheduleHeaderResponse(BaseModel):
    """Serialized tariff schedule header row."""

    schedule_id: str
    source_id: str
    importing_state: str
    exporting_scope: str
    schedule_status: ScheduleStatusEnum
    publication_date: date | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    hs_version: str
    category_system: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TariffScheduleLineResponse(BaseModel):
    """Serialized tariff schedule line row."""

    schedule_line_id: str
    schedule_id: str
    hs_code: str = Field(pattern=r"^\d{6}$")
    product_description: str
    tariff_category: TariffCategoryEnum
    mfn_base_rate: Decimal | None = None
    base_year: int | None = None
    target_rate: Decimal | None = None
    target_year: int | None = None
    staging_type: StagingTypeEnum
    page_ref: int | None = None
    table_ref: str | None = None
    row_ref: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TariffScheduleRateByYearResponse(BaseModel):
    """Serialized year-specific preferential rate row."""

    year_rate_id: str
    schedule_line_id: str
    calendar_year: int
    preferential_rate: Decimal
    rate_status: RateStatusEnum
    source_id: str
    page_ref: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TariffLookupResponse(BaseModel):
    """Joined tariff lookup result for a corridor, HS6 code, and requested year."""

    schedule_id: str
    schedule_source_id: str
    importing_state: str
    exporting_scope: str
    schedule_status: ScheduleStatusEnum
    publication_date: date | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    hs_version: str
    category_system: str | None = None
    notes: str | None = None
    schedule_line_id: str
    hs6_id: str
    hs6_code: str = Field(pattern=r"^\d{6}$")
    hs6_display: str
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
    requested_year: int
    year_rate_id: str | None = None
    resolved_rate_year: int | None = None
    preferential_rate: Decimal | None = None
    rate_status: RateStatusEnum | None = None
    rate_source_id: str | None = None
    rate_page_ref: int | None = None
    used_fallback_rate: bool

    model_config = ConfigDict(from_attributes=True)


class TariffResolutionResult(BaseModel):
    """Service-level tariff resolution output for one corridor and HS6/year."""

    base_rate: Decimal | None = None
    preferential_rate: Decimal | None = None
    staging_year: int | None = None
    tariff_status: RateStatusEnum | Literal["incomplete"]
    tariff_category: TariffCategoryEnum
    schedule_status: ScheduleStatusEnum

    model_config = ConfigDict(from_attributes=True)

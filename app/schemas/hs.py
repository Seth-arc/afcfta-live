"""Pydantic schemas for canonical HS6 product payloads."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HS6ProductResponse(BaseModel):
    """Serialized representation of a canonical HS6 product row."""

    hs6_id: str
    hs_version: str
    hs6_code: str = Field(pattern=r"^\d{6}$")
    hs6_display: str
    chapter: str
    heading: str
    description: str
    section: str | None = None
    section_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

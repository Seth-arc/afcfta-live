"""Pydantic schemas for HS6 product responses."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class HS6ProductResponse(BaseModel):
    """Canonical HS6 product payload returned by classification lookups."""

    hs6_id: UUID
    hs_version: str
    hs6_code: str
    hs6_display: str
    chapter: str
    heading: str
    description: str
    section: str | None = None
    section_name: str | None = None

    model_config = ConfigDict(from_attributes=True)

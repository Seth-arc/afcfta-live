"""Pydantic schemas for provenance sources and legal provisions."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import (
    AuthorityTierEnum,
    InstrumentTypeEnum,
    ProvisionStatusEnum,
    SourceStatusEnum,
    SourceTypeEnum,
)


class SourceRegistryResponse(BaseModel):
    """Tracked source document metadata."""

    source_id: UUID
    title: str
    short_title: str
    source_group: str
    source_type: SourceTypeEnum
    authority_tier: AuthorityTierEnum
    issuing_body: str
    jurisdiction_scope: str
    country_code: str | None = None
    customs_union_code: str | None = None
    publication_date: date | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    version_label: str | None = None
    status: SourceStatusEnum
    language: str
    hs_version: str | None = None
    file_path: str
    mime_type: str
    source_url: str | None = None
    checksum_sha256: str
    supersedes_source_id: UUID | None = None
    superseded_by_source_id: UUID | None = None
    citation_preferred: str | None = None
    ingested_at: datetime | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class LegalProvisionResponse(BaseModel):
    """Extracted legal provision with provenance."""

    provision_id: UUID
    source_id: UUID
    instrument_name: str
    instrument_type: InstrumentTypeEnum
    article_ref: str | None = None
    annex_ref: str | None = None
    appendix_ref: str | None = None
    section_ref: str | None = None
    subsection_ref: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    topic_primary: str
    topic_secondary: list[str] | None = None
    provision_text_verbatim: str
    provision_text_normalized: str | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    status: ProvisionStatusEnum
    cross_reference_refs: list[str] | None = None
    authority_weight: Decimal | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


SourceRegistryOut = SourceRegistryResponse
LegalProvisionOut = LegalProvisionResponse

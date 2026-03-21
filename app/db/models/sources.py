"""SQLAlchemy ORM models for provenance sources and extracted legal provisions."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import (
    AuthorityTierEnum,
    InstrumentTypeEnum,
    ProvisionStatusEnum,
    SourceStatusEnum,
    SourceTypeEnum,
)
from app.db.base import Base


def _enum_type(enum_cls: type, name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
    )


class SourceRegistry(Base):
    """Tracked ingested legal or operational source document."""

    __tablename__ = "source_registry"
    __table_args__ = (
        CheckConstraint(
            "expiry_date IS NULL OR effective_date IS NULL OR expiry_date >= effective_date",
            name="chk_source_dates",
        ),
        Index("idx_source_registry_type", "source_type"),
        Index("idx_source_registry_tier", "authority_tier"),
        Index("idx_source_registry_status", "status"),
        Index("idx_source_registry_country", "country_code"),
        Index("idx_source_registry_effective_date", "effective_date"),
    )

    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    short_title: Mapped[str] = mapped_column(Text, nullable=False)
    source_group: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[SourceTypeEnum] = mapped_column(
        _enum_type(SourceTypeEnum, "source_type_enum"),
        nullable=False,
    )
    authority_tier: Mapped[AuthorityTierEnum] = mapped_column(
        _enum_type(AuthorityTierEnum, "authority_tier_enum"),
        nullable=False,
    )
    issuing_body: Mapped[str] = mapped_column(Text, nullable=False)
    jurisdiction_scope: Mapped[str] = mapped_column(Text, nullable=False)
    country_code: Mapped[str | None] = mapped_column(Text)
    customs_union_code: Mapped[str | None] = mapped_column(Text)
    publication_date: Mapped[date | None] = mapped_column(Date)
    effective_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    version_label: Mapped[str | None] = mapped_column(Text)
    status: Mapped[SourceStatusEnum] = mapped_column(
        _enum_type(SourceStatusEnum, "source_status_enum"),
        nullable=False,
        server_default=text("'current'"),
    )
    language: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'en'"))
    hs_version: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    checksum_sha256: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    supersedes_source_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("source_registry.source_id"),
    )
    superseded_by_source_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("source_registry.source_id"),
    )
    citation_preferred: Mapped[str | None] = mapped_column(Text)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class LegalProvision(Base):
    """Extracted legal provision with normalized topic tags and provenance."""

    __tablename__ = "legal_provision"
    __table_args__ = (
        CheckConstraint(
            "page_start IS NULL OR page_end IS NULL OR page_end >= page_start",
            name="chk_legal_provision_pages",
        ),
        CheckConstraint(
            "authority_weight >= 0.000 AND authority_weight <= 9.999",
            name="chk_legal_provision_weight",
        ),
        Index("idx_legal_provision_source", "source_id"),
        Index("idx_legal_provision_topic_primary", "topic_primary"),
        Index("idx_legal_provision_status", "status"),
        Index("idx_legal_provision_article_ref", "article_ref"),
        Index("idx_legal_provision_annex_ref", "annex_ref"),
        Index("idx_legal_provision_topic_secondary_gin", "topic_secondary", postgresql_using="gin"),
        Index("idx_legal_provision_crossrefs_gin", "cross_reference_refs", postgresql_using="gin"),
        Index(
            "idx_legal_provision_text_trgm",
            "provision_text_verbatim",
            postgresql_using="gin",
            postgresql_ops={"provision_text_verbatim": "gin_trgm_ops"},
        ),
    )

    provision_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("source_registry.source_id", ondelete="RESTRICT"),
        nullable=False,
    )
    instrument_name: Mapped[str] = mapped_column(Text, nullable=False)
    instrument_type: Mapped[InstrumentTypeEnum] = mapped_column(
        _enum_type(InstrumentTypeEnum, "instrument_type_enum"),
        nullable=False,
    )
    article_ref: Mapped[str | None] = mapped_column(Text)
    annex_ref: Mapped[str | None] = mapped_column(Text)
    appendix_ref: Mapped[str | None] = mapped_column(Text)
    section_ref: Mapped[str | None] = mapped_column(Text)
    subsection_ref: Mapped[str | None] = mapped_column(Text)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    topic_primary: Mapped[str] = mapped_column(Text, nullable=False)
    topic_secondary: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    provision_text_verbatim: Mapped[str] = mapped_column(Text, nullable=False)
    provision_text_normalized: Mapped[str | None] = mapped_column(Text)
    effective_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[ProvisionStatusEnum] = mapped_column(
        _enum_type(ProvisionStatusEnum, "provision_status_enum"),
        nullable=False,
        server_default=text("'in_force'"),
    )
    cross_reference_refs: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    authority_weight: Mapped[Decimal] = mapped_column(
        Numeric(4, 3),
        nullable=False,
        server_default=text("1.000"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

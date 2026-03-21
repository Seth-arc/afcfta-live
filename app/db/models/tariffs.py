"""SQLAlchemy ORM models for tariff schedule and yearly preferential rates."""

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
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import (
    RateStatusEnum,
    ScheduleStatusEnum,
    StagingTypeEnum,
    TariffCategoryEnum,
)
from app.db.base import Base


def _enum_type(enum_cls: type, name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
    )


class TariffScheduleHeader(Base):
    """Schedule metadata for an exporter-importer corridor and HS version."""

    __tablename__ = "tariff_schedule_header"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "importing_state",
            "exporting_scope",
            "hs_version",
            name="uq_tariff_schedule_header_source_corridor_hs_version",
        ),
        Index("idx_tariff_schedule_header_source", "source_id"),
        Index("idx_tariff_schedule_header_importing_state", "importing_state"),
        Index("idx_tariff_schedule_header_status", "schedule_status"),
        Index("idx_tariff_schedule_header_effective_date", "effective_date"),
        Index(
            "idx_tariff_schedule_header_corridor",
            "importing_state",
            "exporting_scope",
            "schedule_status",
            "effective_date",
        ),
    )

    schedule_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("source_registry.source_id", ondelete="RESTRICT"),
        nullable=False,
    )
    importing_state: Mapped[str] = mapped_column(Text, nullable=False)
    exporting_scope: Mapped[str] = mapped_column(Text, nullable=False)
    schedule_status: Mapped[ScheduleStatusEnum] = mapped_column(
        _enum_type(ScheduleStatusEnum, "schedule_status_enum"),
        nullable=False,
    )
    publication_date: Mapped[date | None] = mapped_column(Date)
    effective_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    hs_version: Mapped[str] = mapped_column(Text, nullable=False)
    category_system: Mapped[str | None] = mapped_column(Text)
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


class TariffScheduleLine(Base):
    """Tariff schedule line keyed by schedule and HS code."""

    __tablename__ = "tariff_schedule_line"
    __table_args__ = (
        CheckConstraint(
            "(mfn_base_rate IS NULL OR (mfn_base_rate >= 0 AND mfn_base_rate <= 1000)) "
            "AND (target_rate IS NULL OR (target_rate >= 0 AND target_rate <= 1000))",
            name="chk_tariff_schedule_line_rates",
        ),
        CheckConstraint(
            "target_year IS NULL OR base_year IS NULL OR target_year >= base_year",
            name="chk_tariff_schedule_line_years",
        ),
        Index(
            "uq_tariff_schedule_line_schedule_hs_code_row_ref",
            "schedule_id",
            "hs_code",
            text("COALESCE(row_ref, '')"),
            unique=True,
        ),
        Index("idx_tariff_schedule_line_schedule", "schedule_id"),
        Index("idx_tariff_schedule_line_hs_code", "hs_code"),
        Index("idx_tariff_schedule_line_category", "tariff_category"),
        Index("idx_tariff_schedule_line_target_year", "target_year"),
        Index(
            "idx_tariff_schedule_line_desc_trgm",
            "product_description",
            postgresql_using="gin",
            postgresql_ops={"product_description": "gin_trgm_ops"},
        ),
    )

    schedule_line_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    schedule_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tariff_schedule_header.schedule_id", ondelete="CASCADE"),
        nullable=False,
    )
    hs_code: Mapped[str] = mapped_column(Text, nullable=False)
    product_description: Mapped[str] = mapped_column(Text, nullable=False)
    tariff_category: Mapped[TariffCategoryEnum] = mapped_column(
        _enum_type(TariffCategoryEnum, "tariff_category_enum"),
        nullable=False,
        server_default=text("'unknown'"),
    )
    mfn_base_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    base_year: Mapped[int | None] = mapped_column(Integer)
    target_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    target_year: Mapped[int | None] = mapped_column(Integer)
    staging_type: Mapped[StagingTypeEnum] = mapped_column(
        _enum_type(StagingTypeEnum, "staging_type_enum"),
        nullable=False,
        server_default=text("'unknown'"),
    )
    page_ref: Mapped[int | None] = mapped_column(Integer)
    table_ref: Mapped[str | None] = mapped_column(Text)
    row_ref: Mapped[str | None] = mapped_column(Text)
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


class TariffScheduleRateByYear(Base):
    """Year-specific preferential tariff rate resolved from a schedule line."""

    __tablename__ = "tariff_schedule_rate_by_year"
    __table_args__ = (
        CheckConstraint(
            "preferential_rate >= 0 AND preferential_rate <= 1000",
            name="chk_tariff_rate_preferential_rate",
        ),
        UniqueConstraint(
            "schedule_line_id",
            "calendar_year",
            name="uq_tariff_schedule_rate_by_year_line_year",
        ),
        Index("idx_tariff_rate_year_line", "schedule_line_id"),
        Index("idx_tariff_rate_year_calendar", "calendar_year"),
        Index("idx_tariff_rate_year_status", "rate_status"),
        Index("idx_tariff_rate_year_lookup", "schedule_line_id", "calendar_year"),
    )

    year_rate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    schedule_line_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tariff_schedule_line.schedule_line_id", ondelete="CASCADE"),
        nullable=False,
    )
    calendar_year: Mapped[int] = mapped_column(Integer, nullable=False)
    preferential_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    rate_status: Mapped[RateStatusEnum] = mapped_column(
        _enum_type(RateStatusEnum, "rate_status_enum"),
        nullable=False,
        server_default=text("'in_force'"),
    )
    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("source_registry.source_id", ondelete="RESTRICT"),
        nullable=False,
    )
    page_ref: Mapped[int | None] = mapped_column(Integer)
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

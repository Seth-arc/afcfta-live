"""SQLAlchemy ORM models for PSR rule applicability tables."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HS6PSRApplicability(Base):
    """Materialized resolver that maps each HS6 product to its applicable PSR."""

    __tablename__ = "hs6_psr_applicability"
    __table_args__ = (
        UniqueConstraint("hs6_id", "psr_id"),
        Index(
            "idx_hs6_psr_applicability_lookup",
            "hs6_id",
            "priority_rank",
            "effective_date",
            "expiry_date",
        ),
    )

    applicability_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    hs6_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("hs6_product.hs6_id", ondelete="CASCADE"),
        nullable=False,
    )
    psr_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("psr_rule.psr_id", ondelete="CASCADE"),
        nullable=False,
    )
    applicability_type: Mapped[str] = mapped_column(Text, nullable=False)
    priority_rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    effective_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

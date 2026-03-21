"""SQLAlchemy ORM model for the canonical HS6 product backbone table."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Index, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HS6Product(Base):
    """Canonical HS6 product table that anchors all operational joins."""

    __tablename__ = "hs6_product"
    __table_args__ = (
        UniqueConstraint("hs_version", "hs6_code"),
        Index("idx_hs6_product_ver_code", "hs_version", "hs6_code"),
        Index("idx_hs6_product_chapter", "chapter"),
        Index("idx_hs6_product_heading", "heading"),
        Index(
            "idx_hs6_product_desc_trgm",
            "description",
            postgresql_using="gin",
            postgresql_ops={"description": "gin_trgm_ops"},
        ),
    )

    hs6_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    hs_version: Mapped[str] = mapped_column(Text, nullable=False)
    hs6_code: Mapped[str] = mapped_column(Text, nullable=False)
    hs6_display: Mapped[str] = mapped_column(Text, nullable=False)
    chapter: Mapped[str] = mapped_column(Text, nullable=False)
    heading: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    section: Mapped[str | None] = mapped_column(Text)
    section_name: Mapped[str | None] = mapped_column(Text)
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

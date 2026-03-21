"""Create hs6_psr_applicability materialized resolver table."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_create_hs6_psr_applicability"
down_revision: str | None = "0002_create_hs6_product"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hs6_psr_applicability",
        sa.Column(
            "applicability_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("hs6_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("psr_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("applicability_type", sa.Text(), nullable=False),
        sa.Column(
            "priority_rank",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["hs6_id"], ["hs6_product.hs6_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["psr_id"], ["psr_rule.psr_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("hs6_id", "psr_id"),
    )
    op.create_index(
        "idx_hs6_psr_applicability_lookup",
        "hs6_psr_applicability",
        ["hs6_id", "priority_rank", "effective_date", "expiry_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_hs6_psr_applicability_lookup",
        table_name="hs6_psr_applicability",
    )
    op.drop_table("hs6_psr_applicability")

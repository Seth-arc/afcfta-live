"""Add evidence effective-date windows."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0012_evidence_effective_dates"
down_revision: str | None = "0011_expand_checktype"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evidence_requirement",
        sa.Column("effective_from", sa.Date(), nullable=True),
    )
    op.add_column(
        "evidence_requirement",
        sa.Column("effective_to", sa.Date(), nullable=True),
    )
    op.create_index(
        "idx_evidence_requirement_effective_window",
        "evidence_requirement",
        ["effective_from", "effective_to"],
        unique=False,
    )

    op.add_column(
        "verification_question",
        sa.Column("effective_from", sa.Date(), nullable=True),
    )
    op.add_column(
        "verification_question",
        sa.Column("effective_to", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("verification_question", "effective_to")
    op.drop_column("verification_question", "effective_from")

    op.drop_index(
        "idx_evidence_requirement_effective_window",
        table_name="evidence_requirement",
    )
    op.drop_column("evidence_requirement", "effective_to")
    op.drop_column("evidence_requirement", "effective_from")

"""Add compact decision snapshot storage to eligibility evaluations."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0013_evaluation_decision_snapshot"
down_revision: str | None = "0012_evidence_effective_dates"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "eligibility_evaluation",
        sa.Column("decision_snapshot_json", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("eligibility_evaluation", "decision_snapshot_json")

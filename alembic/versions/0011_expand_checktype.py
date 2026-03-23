"""Expand persisted audit check_type constraint."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0011_expand_checktype"
down_revision: str | None = "0010_create_intelligence_layer"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE eligibility_check_result
        DROP CONSTRAINT IF EXISTS chk_eligibility_check_result_type;
        """
    )
    op.execute(
        """
        ALTER TABLE eligibility_check_result
        ADD CONSTRAINT chk_eligibility_check_result_type
        CHECK (
          check_type IN (
            'classification',
            'rule',
            'psr',
            'pathway',
            'general_rule',
            'status',
            'tariff',
            'evidence',
            'decision',
            'blocker'
          )
        );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE eligibility_check_result
        DROP CONSTRAINT IF EXISTS chk_eligibility_check_result_type;
        """
    )
    op.execute(
        """
        ALTER TABLE eligibility_check_result
        ADD CONSTRAINT chk_eligibility_check_result_type
        CHECK (check_type IN ('psr', 'general_rule', 'status', 'blocker'));
        """
    )
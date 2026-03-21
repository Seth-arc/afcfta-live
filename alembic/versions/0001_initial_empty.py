"""Initial empty migration."""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0001_initial_empty"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

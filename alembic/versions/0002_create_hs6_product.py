"""Create hs6_product backbone table."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_create_hs6_product"
down_revision: str | None = "0001_initial_empty"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    op.create_table(
        "hs6_product",
        sa.Column(
            "hs6_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("hs_version", sa.Text(), nullable=False),
        sa.Column("hs6_code", sa.Text(), nullable=False),
        sa.Column("hs6_display", sa.Text(), nullable=False),
        sa.Column("chapter", sa.Text(), nullable=False),
        sa.Column("heading", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("section", sa.Text(), nullable=True),
        sa.Column("section_name", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("hs_version", "hs6_code"),
    )

    op.create_index(
        "idx_hs6_product_ver_code",
        "hs6_product",
        ["hs_version", "hs6_code"],
        unique=False,
    )
    op.create_index("idx_hs6_product_chapter", "hs6_product", ["chapter"], unique=False)
    op.create_index("idx_hs6_product_heading", "hs6_product", ["heading"], unique=False)
    op.create_index(
        "idx_hs6_product_desc_trgm",
        "hs6_product",
        ["description"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"description": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("idx_hs6_product_desc_trgm", table_name="hs6_product")
    op.drop_index("idx_hs6_product_heading", table_name="hs6_product")
    op.drop_index("idx_hs6_product_chapter", table_name="hs6_product")
    op.drop_index("idx_hs6_product_ver_code", table_name="hs6_product")
    op.drop_table("hs6_product")

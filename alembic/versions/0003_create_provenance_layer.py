"""Create provenance source and legal provision tables."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003_create_provenance_layer"
down_revision: str | None = "0002_create_hs6_product"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    op.execute(
        """
        DO $$
        BEGIN
          CREATE TYPE authority_tier_enum AS ENUM (
            'binding',
            'official_operational',
            'interpretive',
            'analytic_enrichment'
          );
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          CREATE TYPE source_type_enum AS ENUM (
            'agreement',
            'protocol',
            'annex',
            'appendix',
            'tariff_schedule',
            'ministerial_decision',
            'status_notice',
            'implementation_circular',
            'guidance_note',
            'manual',
            'analytics_reference',
            'other'
          );
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          CREATE TYPE source_status_enum AS ENUM (
            'current',
            'superseded',
            'provisional',
            'draft',
            'pending',
            'archived'
          );
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          CREATE TYPE instrument_type_enum AS ENUM (
            'agreement',
            'protocol',
            'annex',
            'appendix',
            'decision',
            'circular',
            'guidance',
            'manual',
            'other'
          );
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          CREATE TYPE provision_status_enum AS ENUM (
            'in_force',
            'provisional',
            'pending',
            'superseded',
            'expired'
          );
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          CREATE TYPE hs_level_enum AS ENUM (
            'chapter',
            'heading',
            'subheading',
            'tariff_line'
          );
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          CREATE TYPE rule_status_enum AS ENUM (
            'agreed',
            'pending',
            'partially_agreed',
            'provisional',
            'superseded'
          );
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          CREATE TYPE rule_component_type_enum AS ENUM (
            'WO',
            'VA',
            'VNM',
            'CTH',
            'CTSH',
            'CC',
            'PROCESS',
            'ALT_RULE',
            'EXCEPTION',
            'NOTE'
          );
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          CREATE TYPE operator_type_enum AS ENUM (
            'and',
            'or',
            'not',
            'standalone'
          );
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          CREATE TYPE threshold_basis_enum AS ENUM (
            'ex_works',
            'fob',
            'value_of_non_originating_materials',
            'customs_value',
            'unknown'
          );
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE source_registry (
          source_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          title text NOT NULL,
          short_title text NOT NULL,
          source_group text NOT NULL,
          source_type source_type_enum NOT NULL,
          authority_tier authority_tier_enum NOT NULL,
          issuing_body text NOT NULL,
          jurisdiction_scope text NOT NULL,
          country_code text,
          customs_union_code text,
          publication_date date,
          effective_date date,
          expiry_date date,
          version_label text,
          status source_status_enum NOT NULL DEFAULT 'current',
          language text NOT NULL DEFAULT 'en',
          hs_version text,
          file_path text NOT NULL,
          mime_type text NOT NULL,
          source_url text,
          checksum_sha256 text NOT NULL UNIQUE,
          supersedes_source_id uuid REFERENCES source_registry(source_id),
          superseded_by_source_id uuid REFERENCES source_registry(source_id),
          citation_preferred text,
          ingested_at timestamptz NOT NULL DEFAULT now(),
          notes text,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT chk_source_dates
            CHECK (expiry_date IS NULL OR effective_date IS NULL OR expiry_date >= effective_date)
        );
        """
    )
    op.execute("CREATE INDEX idx_source_registry_type ON source_registry(source_type);")
    op.execute("CREATE INDEX idx_source_registry_tier ON source_registry(authority_tier);")
    op.execute("CREATE INDEX idx_source_registry_status ON source_registry(status);")
    op.execute("CREATE INDEX idx_source_registry_country ON source_registry(country_code);")
    op.execute("CREATE INDEX idx_source_registry_effective_date ON source_registry(effective_date);")

    op.execute(
        """
        CREATE TABLE legal_provision (
          provision_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          source_id uuid NOT NULL REFERENCES source_registry(source_id) ON DELETE RESTRICT,
          instrument_name text NOT NULL,
          instrument_type instrument_type_enum NOT NULL,
          article_ref text,
          annex_ref text,
          appendix_ref text,
          section_ref text,
          subsection_ref text,
          page_start integer,
          page_end integer,
          topic_primary text NOT NULL,
          topic_secondary text[],
          provision_text_verbatim text NOT NULL,
          provision_text_normalized text,
          effective_date date,
          expiry_date date,
          status provision_status_enum NOT NULL DEFAULT 'in_force',
          cross_reference_refs text[],
          authority_weight numeric(4,3) NOT NULL DEFAULT 1.000,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT chk_legal_provision_pages
            CHECK (page_start IS NULL OR page_end IS NULL OR page_end >= page_start),
          CONSTRAINT chk_legal_provision_weight
            CHECK (authority_weight >= 0.000 AND authority_weight <= 9.999)
        );
        """
    )
    op.execute("CREATE INDEX idx_legal_provision_source ON legal_provision(source_id);")
    op.execute("CREATE INDEX idx_legal_provision_topic_primary ON legal_provision(topic_primary);")
    op.execute("CREATE INDEX idx_legal_provision_status ON legal_provision(status);")
    op.execute("CREATE INDEX idx_legal_provision_article_ref ON legal_provision(article_ref);")
    op.execute("CREATE INDEX idx_legal_provision_annex_ref ON legal_provision(annex_ref);")
    op.execute(
        """
        CREATE INDEX idx_legal_provision_topic_secondary_gin
        ON legal_provision USING GIN(topic_secondary);
        """
    )
    op.execute(
        """
        CREATE INDEX idx_legal_provision_crossrefs_gin
        ON legal_provision USING GIN(cross_reference_refs);
        """
    )
    op.execute(
        """
        CREATE INDEX idx_legal_provision_text_trgm
        ON legal_provision USING GIN(provision_text_verbatim gin_trgm_ops);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS legal_provision;")
    op.execute("DROP TABLE IF EXISTS source_registry;")

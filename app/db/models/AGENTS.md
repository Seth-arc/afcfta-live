# ORM Model Rules

Every model in this directory represents a PostgreSQL table. The DDL is the
source of truth, not the other way around.

## Column Fidelity

- Every column name, type, and constraint must match docs/Concrete_Contract.md
- Do not rename columns for "Pythonic" style (e.g., keep hs6_id, not hs6Id)
- Do not add columns that are not in the DDL
- Do not skip columns because they seem optional

## Types

- UUID primary keys: server_default=text("uuid_generate_v4()")
- All timestamps: timestamptz with server_default=func.now()
- Enum columns: use the Python enums from app/core/enums.py, never inline strings
- Numeric columns for rates/thresholds: use Numeric(precision, scale) matching DDL
- Text columns for verbatim legal text: use Text, not String(n)
- JSONB columns: use JSONB from sqlalchemy.dialects.postgresql

## Constraints and Indexes

- Include every CHECK constraint from the DDL
- Include every index from the DDL
- Include every UNIQUE constraint
- Foreign key on_delete behavior must match the DDL exactly:
  RESTRICT, SET NULL, and CASCADE are used differently across tables

## After Creating a Model

- Create an Alembic migration (but do not run it — the human will run it)
- Verify the migration SQL matches the DDL in Concrete_Contract.md

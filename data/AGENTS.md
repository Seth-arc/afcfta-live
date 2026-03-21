# Data Directory Rules

Source document corpus organized by authority tier. File store, not code.

## Structure

- raw/      — original source documents, NEVER modified after ingestion
- staged/   — intermediate extraction and normalization outputs
- processed/ — final structured outputs ready for database loading

## Immutability

- Files in raw/ are never modified after ingestion
- Each file must have a source_registry record with SHA-256 checksum
- Superseded documents stay in raw/; source_registry tracks the chain

## v0.1 Scope

Only documents for: NGA, GHA, CIV, SEN, CMR

# Pydantic Schema Rules

Schemas define the API contract. They are what external consumers see.

## Mandatory Response Fields

Every response model that touches eligibility, rules, or tariffs MUST include:
- rule_status
- tariff_status (where applicable)
- confidence_class

The AssessmentResponse contract in docs/v1_scope.md Section 7.1 is canonical.

## Type Rules

- Use enums from app/core/enums.py for all status and type fields — never str
- Use Optional[] with explicit None defaults for fields that may be absent
- Never silently omit a field — Optional[X] = None is different from missing
- Use UUID as str in schemas (not uuid.UUID) for JSON serialization

## Validation

- HS6 codes: must be exactly 6 digits after normalization
- Country codes: must be ISO alpha-3 from app/core/countries.py
- Year: reasonable calendar year (2020-2040)
- persona_mode: one of officer, analyst, exporter, system

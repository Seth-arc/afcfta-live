# Repository Rules

Repositories are the data access layer. They contain SQL and return raw results.
No business logic lives here.

## Join Rules

- ALL operational joins resolve through hs_version + hs6_id
- Never join on raw HS text, product descriptions, or display names
- PSR lookup MUST go through hs6_psr_applicability (materialized resolver),
  not live inheritance logic
- Use the exact SQL from docs/Join_Strategy.md Sections 2.1-2.8 as the
  reference implementation for every query

## Boundaries

- Repositories return raw query results (row mappings or ORM objects)
- Never return Pydantic models — transformation happens in the service layer
- No business logic: no if/else on rule_status, no eligibility decisions,
  no derived variable computation
- No direct imports from app/services/

## Polymorphic Lookups

- status_assertion and evidence_requirement use entity_type + entity_key
- Use the key patterns from app/core/entity_keys.py
- Always include the date window filter for effective_date and expiry_date

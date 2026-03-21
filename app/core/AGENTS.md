# Core Module Rules

These files are the system's reference data and type definitions. Most are
locked and must not be modified.

## Locked Files — Do Not Modify

- countries.py — v0.1 country codes, ISO mappings, bloc membership, corridors
- fact_keys.py — valid production fact types and which rule types require them
- entity_keys.py — entity key patterns for polymorphic lookups (status, evidence)
- failure_codes.py — canonical failure codes for the eligibility engine

Do not rename, restructure, reformat, add to, or "improve" these files unless
the human explicitly asks you to.

## Enums (enums.py)

- Must match docs/Concrete_Contract.md Section 1.2 exactly
- Do not add, remove, rename, or reorder any enum values
- Use the (str, Enum) pattern so values serialize cleanly in Pydantic
- If a new enum value is needed, check Concrete_Contract.md first — if it is
  not in the DDL, do not add it

## Exceptions (exceptions.py)

- All domain exceptions inherit from AISBaseException
- Each exception accepts a message (str) and optional detail (dict)
- Add new exception types if genuinely needed but do not change existing ones
- Exception names are used in API error handlers — renaming breaks the contract

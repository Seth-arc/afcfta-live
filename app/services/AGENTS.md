# Service Layer Rules

All business logic lives in services. This is the core of the system.

## Architectural Boundaries

- Services call repositories, never the database session directly
- Services return Pydantic schemas, not ORM objects
- Route handlers call services — services never import from app/api/
- Services may call other services (eligibility_service orchestrates all)

## Critical Separations

- PSR rules and general origin rules are SEPARATE services. Never merge them.
- The expression_evaluator takes an expression + facts dict, returns bool.
  It does not call repositories or know about cases.
- The eligibility_service calls everything else in strict 8-step order.

## Safety Rules

- Never use eval(), exec(), or compile() in the expression evaluator
- Never infer or default missing fact values — flag them in missing_facts
- Never assume a status — return "unknown" if no status_assertion exists
- Division by zero (ex_works == 0) is an error, not a silent default

## Derived Variables (computed, never stored)

vnom_percent = non_originating / ex_works * 100
va_percent   = (ex_works - non_originating) / ex_works * 100

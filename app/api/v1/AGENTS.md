# Route Handler Rules

Handlers are thin wrappers. Validate input, call a service, return a response.
If a handler has more than ~10 lines of logic, extract to a service.

## Mandatory Response Fields

Every response touching eligibility, rules, or tariffs includes:
- rule_status
- tariff_status (where applicable)
- confidence_class

## Error Handling

- Domain exceptions are caught by global handlers in main.py — do not catch here
- Use Pydantic response models from app/schemas/ — never return raw dicts
- Error responses use app/schemas/common.ErrorResponse format

## Dependencies

- All services injected via Depends() using factories from app/api/deps.py
- Do not instantiate services directly in handlers
- Do not import repositories in handlers — that crosses the layer boundary

## Route Prefix

/api/v1 prefix is set in app/api/router.py — do not repeat it in handlers

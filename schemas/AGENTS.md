# Schema Definitions

Formal schema definitions — separate from runtime Pydantic models in app/schemas/.

- sql/ — PostgreSQL DDL. Must match docs/Concrete_Contract.md exactly.
- json/ — JSON Schema for pipeline formats and expression_json structure.
- contracts/ — OpenAPI/REST API contracts matching docs/FastAPI_layout.md.

These are specifications that code must conform to, not generated from code.

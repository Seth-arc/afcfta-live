# AIS API Overview

## What This API Does

The AfCFTA Intelligence System (AIS) API is a deterministic trade-compliance
engine for AfCFTA preferential trade analysis.

Given:

- a product code at the HS6 level
- an exporter and importer corridor
- production facts such as tariff-heading shifts, ex-works value, or direct transport

the API can answer:

- does the product qualify for AfCFTA origin treatment?
- which legal pathway was satisfied, such as `CTH`, `VNM`, or `WO`?
- what tariff rates apply on the corridor?
- what evidence is needed to support the claim?
- what legal or operational status constraints apply?

The engine is deterministic. It does not score probability, infer missing facts,
or use dynamic execution of legal logic.

## Base URL

All endpoints are served under:

```text
/api/v1
```

Examples in this documentation assume a local development host such as:

```text
http://localhost:8000/api/v1
```

## Authentication

Authentication is enforced with an API-key header on all protected routes.

- Header: `X-API-Key`
- Public routes: `GET /api/v1/health`, `GET /api/v1/health/ready`
- Protected routes: all other `/api/v1/*` endpoints
- Failure mode: HTTP `401` with the shared structured error envelope

Deployments should still treat the configured key as a shared secret and rotate
it through environment management rather than hardcoding it into client code.

## Request And Response Format

- Content type: `application/json`
- Request bodies: JSON
- Success responses: endpoint-specific JSON payloads
- Error responses: structured JSON envelope

Error responses follow this shape:

```json
{
  "error": {
    "code": "RULE_NOT_FOUND",
    "message": "No PSR found for hs_version 'HS2017' and hs6_code '999999'",
    "details": {
      "hs_version": "HS2017",
      "hs6_code": "999999"
    }
  },
  "meta": {
    "request_id": "9b50d5d6-7f5e-46f7-9d63-2d6a7e2b9622",
    "timestamp": "2026-03-21T15:04:12.101245Z"
  }
}
```

## Tracing And Request IDs

Every HTTP response includes an `X-Request-ID` header for tracing.

Structured error bodies also include the same value in:

```json
meta.request_id
```

Use that request id when correlating client errors with server logs or audit records.

## Versioning

Versioning is path-based:

```text
/api/v1
```

Backward-incompatible contract changes should be introduced under a new major
path such as `/api/v2`.

## Rate Limits

- Assessment routes default to `10` requests per `60` seconds per principal.
- Other protected routes default to `120` requests per `60` seconds per principal.
- The limiter can be disabled for controlled load testing with `RATE_LIMIT_ENABLED=false`.

For multi-worker deployments, keep `REDIS_URL` configured so rate limits remain
shared across workers.

## Supported Scope In v0.1

- Countries: `NGA`, `GHA`, `CIV`, `SEN`, `CMR`
- Published active corridor profiles: `GHA -> NGA`, `CMR -> NGA`, `CIV -> NGA`,
  `SEN -> NGA`, `GHA -> CMR`
- Core example corridor in this documentation: `GHA -> NGA`
- Core product example in this documentation: HS6 `110311` for groats and meal of wheat

The locked golden assessment corpus is broader than the published corridor-profile
surface. A valid v0.1 assessment corridor can still return `404` from the
intelligence profile endpoint when no active `corridor_profile` row is published
for that exact exporter/importer pair.

## User-Facing Versus Internal Layers

User-facing API capabilities in v0.1:

- direct assessments
- case-backed assessments using stored case facts
- evidence readiness and audit replay
- source and legal provision lookup
- corridor profile and alert listing

Internal infrastructure that supports those APIs but is not exposed as a public endpoint:

- repositories and ORM models
- parser artifact generation and promotion scripts
- seed-data loaders and development fixtures
- Alembic migrations and operator workflow runbooks

## Response Design Notes

Two integration details matter:

1. Success payloads are not wrapped in a global `data` envelope.
2. Error payloads are wrapped and always include a machine-readable `code`.

That means client code should parse:

- success responses according to the endpoint contract
- error responses according to the shared error envelope

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

Authentication is planned as an API-key header.

- Planned header: `X-API-Key`
- v0.1 status: not enforced

You can call the API in v0.1 without authentication unless your deployment
adds it at the gateway or reverse proxy.

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

- v0.1: none

If you place AIS behind an API gateway, apply rate limits there.

## Supported Scope In v0.1

- Countries: `NGA`, `GHA`, `CIV`, `SEN`, `CMR`
- Core example corridor in this documentation: `GHA -> NGA`
- Core product example in this documentation: HS6 `110311` for groats and meal of wheat

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

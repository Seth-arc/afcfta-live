# AIS API Endpoints

Examples use the seeded v0.1 data set, especially HS6 `110311` on the
`GHA -> NGA` corridor. Runtime-created ids such as `case_id` and `evaluation_id`
are shown as example UUIDs.

Unless stated otherwise, authenticated examples assume:

```text
X-API-Key: <your-api-key>
```

## GET /api/v1/health

Liveness check.

**Parameters**

- none

**curl**

```bash
curl http://localhost:8000/api/v1/health
```

**Sample response**

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

## GET /api/v1/rules/{hs6}

Resolves the governing product-specific rule bundle for a product.

**Path parameters**

- `hs6`: product code. The API strips punctuation and truncates HS8/HS10 input to HS6.

**Query parameters**

- `hs_version`: optional, default `HS2017`

**curl**

```bash
curl "http://localhost:8000/api/v1/rules/110311?hs_version=HS2017"
```

**Sample response**

```json
{
  "psr_id": "8c6a4b89-4d4e-4d5b-9eb4-4d1775edb3b0",
  "source_id": "c3d3fd71-d1b2-412e-a708-1685f1f2299f",
  "appendix_version": "v0.1",
  "hs_version": "HS2017",
  "hs6_code": "110311",
  "hs_level": "subheading",
  "rule_scope": "subheading",
  "product_description": "Groats and meal of wheat",
  "legal_rule_text_verbatim": "CTH",
  "legal_rule_text_normalized": "CTH",
  "rule_status": "agreed",
  "effective_date": "2024-01-01",
  "page_ref": 1,
  "row_ref": "110311",
  "applicability_type": "direct",
  "components": [
    {
      "component_id": "f00a4232-2fd0-4ee2-99d4-7fbc778a93f3",
      "psr_id": "8c6a4b89-4d4e-4d5b-9eb4-4d1775edb3b0",
      "component_type": "tariff_shift",
      "operator_type": "ne",
      "tariff_shift_level": "heading",
      "component_text_verbatim": "Change in tariff heading",
      "normalized_expression": "tariff_heading_input != tariff_heading_output",
      "component_order": 1
    }
  ],
  "pathways": [
    {
      "pathway_id": "240f3cbf-f2a3-4f9e-97a2-c6b96ea28f55",
      "psr_id": "8c6a4b89-4d4e-4d5b-9eb4-4d1775edb3b0",
      "pathway_code": "CTH",
      "pathway_label": "CTH",
      "pathway_type": "specific",
      "expression_json": {
        "op": "fact_ne",
        "fact": "tariff_heading_input",
        "ref_fact": "tariff_heading_output"
      },
      "allows_cumulation": true,
      "allows_tolerance": true,
      "priority_rank": 1,
      "effective_date": "2024-01-01",
      "expiry_date": null
    }
  ]
}
```

## GET /api/v1/tariffs

Returns the tariff outcome for a corridor, HS6 code, and year.

**Query parameters**

- `exporter`: required ISO alpha-3 exporter code
- `importer`: required ISO alpha-3 importer code
- `hs6`: required HS6 code
- `year`: required calendar year
- `hs_version`: optional, default `HS2017`

**curl**

```bash
curl "http://localhost:8000/api/v1/tariffs?exporter=GHA&importer=NGA&hs6=110311&year=2025&hs_version=HS2017"
```

**Sample response**

```json
{
  "base_rate": "15.0000",
  "preferential_rate": "0.0000",
  "staging_year": 2025,
  "tariff_status": "in_force",
  "tariff_category": "liberalised",
  "schedule_status": "official",
  "schedule_id": "f81a16be-f0af-40b8-a940-a13cfa3d5683",
  "schedule_line_id": "8d03282d-5440-4886-8e75-c6d7a93d16a9",
  "year_rate_id": "a83d8f47-8131-4cdc-b441-f6e85bf2b33a",
  "resolved_rate_year": 2025,
  "used_fallback_rate": false
}
```

## POST /api/v1/cases

Creates a case and stores submitted production facts.

**Request body**

Top-level fields:

- `persona_mode`
- `exporter_state`
- `importer_state`
- `hs6_code`
- `hs_version`
- `declared_origin`
- `declared_pathway`
- `title`
- `notes`
- `case_external_ref`
- `production_facts`

Each `production_facts[]` item uses:

- `fact_type`
- `fact_key`
- `fact_value_type`
- one typed value field such as `fact_value_text`, `fact_value_number`, or `fact_value_boolean`

**curl**

```bash
curl -X POST http://localhost:8000/api/v1/cases \
  -H "Content-Type: application/json" \
  -d '{
    "persona_mode": "exporter",
    "exporter_state": "GHA",
    "importer_state": "NGA",
    "hs6_code": "110311",
    "hs_version": "HS2017",
    "declared_origin": "GHA",
    "declared_pathway": "CTH",
    "title": "GHA wheat groats claim",
    "notes": "Seed example case",
    "case_external_ref": "CASE-GHA-110311-001",
    "production_facts": [
      {
        "fact_type": "tariff_heading_input",
        "fact_key": "tariff_heading_input",
        "fact_value_type": "text",
        "fact_value_text": "1001"
      }
    ]
  }'
```

**Sample response**

```json
{
  "case_id": "29dc2946-6ef0-46a0-b3eb-0f6a64e40db7",
  "case": {
    "case_id": "29dc2946-6ef0-46a0-b3eb-0f6a64e40db7",
    "case_external_ref": "CASE-GHA-110311-001",
    "persona_mode": "exporter",
    "exporter_state": "GHA",
    "importer_state": "NGA",
    "hs_code": "110311",
    "hs_version": "HS2017",
    "declared_origin": "GHA",
    "declared_pathway": "CTH",
    "submission_status": "draft",
    "title": "GHA wheat groats claim",
    "notes": "Seed example case"
  }
}
```

## GET /api/v1/cases/{case_id}

Returns a case and all stored facts.

**Path parameters**

- `case_id`: case UUID

**curl**

```bash
curl http://localhost:8000/api/v1/cases/29dc2946-6ef0-46a0-b3eb-0f6a64e40db7
```

**Sample response**

```json
{
  "case": {
    "case_id": "29dc2946-6ef0-46a0-b3eb-0f6a64e40db7",
    "case_external_ref": "CASE-GHA-110311-001",
    "persona_mode": "exporter",
    "exporter_state": "GHA",
    "importer_state": "NGA",
    "hs_code": "110311",
    "hs_version": "HS2017",
    "declared_origin": "GHA",
    "declared_pathway": "CTH",
    "submission_status": "draft",
    "title": "GHA wheat groats claim",
    "notes": "Seed example case"
  },
  "facts": [
    {
      "fact_id": "470e2e93-5d6b-4b42-b141-756c0377f9d7",
      "case_id": "29dc2946-6ef0-46a0-b3eb-0f6a64e40db7",
      "fact_type": "tariff_heading_input",
      "fact_key": "tariff_heading_input",
      "fact_value_type": "text",
      "fact_value_text": "1001",
      "source_type": "user_input",
      "fact_order": 1
    }
  ]
}
```

## POST /api/v1/assessments

Runs the full deterministic eligibility engine.

**Request body**

- `hs6_code`
- `hs_version`
- `exporter`
- `importer`
- `year`
- `persona_mode`
- `production_facts`
- optional canonical `existing_documents`
- optional `case_id`

Compatibility:

- `existing_documents` is the canonical request field for document inventory.
- `submitted_documents` is accepted as an input-only alias for backward compatibility.

Replay guarantee:

- If `case_id` is omitted, AIS auto-creates a submitted case before running the engine.
- The response body remains the frozen assessment contract.
- The response headers expose the replay identifiers explicitly:
- `X-AIS-Case-Id`
- `X-AIS-Evaluation-Id`
- `X-AIS-Audit-URL`

**curl**

```bash
curl -X POST http://localhost:8000/api/v1/assessments \
  -H "Content-Type: application/json" \
  -d '{
    "hs6_code": "110311",
    "hs_version": "HS2017",
    "exporter": "GHA",
    "importer": "NGA",
    "year": 2025,
    "persona_mode": "exporter",
    "existing_documents": [
      "certificate_of_origin",
      "bill_of_materials",
      "invoice"
    ],
    "production_facts": [
      {
        "fact_type": "tariff_heading_input",
        "fact_key": "tariff_heading_input",
        "fact_value_type": "text",
        "fact_value_text": "1001"
      },
      {
        "fact_type": "tariff_heading_output",
        "fact_key": "tariff_heading_output",
        "fact_value_type": "text",
        "fact_value_text": "1103"
      },
      {
        "fact_type": "direct_transport",
        "fact_key": "direct_transport",
        "fact_value_type": "boolean",
        "fact_value_boolean": true
      }
    ]
  }'
```

**Sample response**

Response headers:

```text
X-AIS-Case-Id: 29dc2946-6ef0-46a0-b3eb-0f6a64e40db7
X-AIS-Evaluation-Id: 4c651cd2-8f0f-4c16-9f37-8dfceef41f26
X-AIS-Audit-URL: /api/v1/audit/evaluations/4c651cd2-8f0f-4c16-9f37-8dfceef41f26
```

```json
{
  "hs6_code": "110311",
  "eligible": true,
  "pathway_used": "CTH",
  "rule_status": "agreed",
  "tariff_outcome": {
    "preferential_rate": "0.0000",
    "base_rate": "15.0000",
    "status": "in_force"
  },
  "failures": [],
  "missing_facts": [],
  "evidence_required": [
    "Certificate of origin",
    "Bill of materials",
    "Invoice"
  ],
  "missing_evidence": [],
  "readiness_score": 1.0,
  "completeness_ratio": 1.0,
  "confidence_class": "complete"
}
```

## POST /api/v1/assessments/cases/{case_id}

Runs the same assessment flow using facts already stored on a case.

**Path parameters**

- `case_id`: case UUID

**Request body**

- `year`
- optional canonical `existing_documents`

Compatibility:

- `submitted_documents` is accepted as an input-only alias for backward compatibility.

Replay headers:

- `X-AIS-Case-Id`
- `X-AIS-Evaluation-Id`
- `X-AIS-Audit-URL`

**curl**

```bash
curl -X POST http://localhost:8000/api/v1/assessments/cases/29dc2946-6ef0-46a0-b3eb-0f6a64e40db7 \
  -H "Content-Type: application/json" \
  -d '{
    "year": 2025,
    "existing_documents": ["certificate_of_origin"]
  }'
```

**Sample response**

The response shape is the same as `POST /api/v1/assessments`.

## POST /api/v1/evidence/readiness

Checks evidence readiness for a legal entity target such as a rule or pathway.

**Request body**

- `entity_type`
- `entity_key`
- `persona_mode`
- `existing_documents`

For rule-level evidence, `entity_key` uses the pattern:

```text
HS6_RULE:{psr_id}
```

**curl**

```bash
curl -X POST http://localhost:8000/api/v1/evidence/readiness \
  -H "Content-Type: application/json" \
  -d '{
    "entity_type": "hs6_rule",
    "entity_key": "HS6_RULE:8c6a4b89-4d4e-4d5b-9eb4-4d1775edb3b0",
    "persona_mode": "exporter",
    "existing_documents": ["certificate_of_origin"]
  }'
```

**Sample response**

```json
{
  "required_items": [
    "Certificate of Origin",
    "Supplier declaration"
  ],
  "missing_items": [
    "Supplier declaration"
  ],
  "verification_questions": [
    "Can the exporter provide a valid certificate of origin?",
    "Does the supplier declaration support the claimed origin inputs?"
  ],
  "readiness_score": 0.5,
  "completeness_ratio": 0.5
}
```

## GET /api/v1/audit/evaluations/{evaluation_id}

Reconstructs the stored decision trace for one persisted evaluation.

**Path parameters**

- `evaluation_id`: evaluation UUID

**curl**

```bash
curl http://localhost:8000/api/v1/audit/evaluations/4c651cd2-8f0f-4c16-9f37-8dfceef41f26
```

**Sample response**

```json
{
  "evaluation": {
    "evaluation_id": "4c651cd2-8f0f-4c16-9f37-8dfceef41f26",
    "case_id": "29dc2946-6ef0-46a0-b3eb-0f6a64e40db7",
    "evaluation_date": "2025-01-01",
    "overall_outcome": "eligible",
    "pathway_used": "CTH",
    "confidence_class": "complete",
    "rule_status_at_evaluation": "agreed",
    "tariff_status_at_evaluation": "in_force",
    "created_at": "2026-03-21T15:47:19.000000Z"
  },
  "case": {
    "case_id": "29dc2946-6ef0-46a0-b3eb-0f6a64e40db7",
    "case_external_ref": "CASE-GHA-110311-001",
    "persona_mode": "exporter",
    "exporter_state": "GHA",
    "importer_state": "NGA",
    "hs_code": "110311",
    "hs_version": "HS2017",
    "submission_status": "draft"
  },
  "original_input_facts": [],
  "hs6_resolved": {
    "hs6_code": "110311",
    "hs_version": "HS2017",
    "description": "Groats and meal of wheat"
  },
  "psr_rule": {
    "psr_id": "8c6a4b89-4d4e-4d5b-9eb4-4d1775edb3b0",
    "hs6_code": "110311",
    "product_description": "Groats and meal of wheat",
    "legal_rule_text_verbatim": "CTH",
    "rule_status": "agreed"
  },
  "pathway_evaluations": [
    {
      "pathway_code": "CTH",
      "priority_rank": 1,
      "evaluated_expression": "1001 != 1103",
      "result": true,
      "missing_variables": [],
      "checks": []
    }
  ],
  "general_rules_results": {
    "insufficient_operations_check": "pass",
    "cumulation_check": "not_applicable",
    "direct_transport_check": "pass",
    "general_rules_passed": true,
    "failure_codes": [],
    "checks": []
  },
  "status_overlay": {
    "status_type": "agreed",
    "confidence_class": "complete",
    "active_transitions": [],
    "constraints": [],
    "source_text_verbatim": "Rule is agreed."
  },
  "tariff_outcome": {
    "preferential_rate": "0.0000",
    "base_rate": "15.0000",
    "status": "in_force"
  },
  "evidence_readiness": {
    "required_items": [
      "Certificate of origin",
      "Bill of materials",
      "Invoice"
    ],
    "missing_items": [],
    "verification_questions": [
      "Can the exporter provide a valid certificate of origin?"
    ],
    "readiness_score": 1.0,
    "completeness_ratio": 1.0
  },
  "atomic_checks": [],
  "final_decision": {
    "eligible": true,
    "overall_outcome": "eligible",
    "pathway_used": "CTH",
    "rule_status": "agreed",
    "tariff_status": "in_force",
    "confidence_class": "complete",
    "failure_codes": [],
    "missing_facts": [],
    "missing_evidence": [],
    "readiness_score": 1.0,
    "completeness_ratio": 1.0,
    "provenance": {
      "rule": {
        "source_id": "c3d3fd71-d1b2-412e-a708-1685f1f2299f"
      },
      "tariff": {
        "schedule_source_id": "c3d3fd71-d1b2-412e-a708-1685f1f2299f"
      }
    }
  }
}
```

This audit replay contract is frozen in integration coverage at:

- [tests/integration/test_audit_api.py](tests/integration/test_audit_api.py#L27)
- [tests/integration/test_audit_api.py](tests/integration/test_audit_api.py#L132)

## GET /api/v1/audit/cases/{case_id}/evaluations

Lists all evaluations stored for a case.

**Path parameters**

- `case_id`: case UUID

**curl**

```bash
curl http://localhost:8000/api/v1/audit/cases/29dc2946-6ef0-46a0-b3eb-0f6a64e40db7/evaluations
```

**Sample response**

```json
[
  {
    "evaluation_id": "4c651cd2-8f0f-4c16-9f37-8dfceef41f26",
    "case_id": "29dc2946-6ef0-46a0-b3eb-0f6a64e40db7",
    "evaluation_date": "2025-01-01",
    "overall_outcome": "eligible",
    "pathway_used": "CTH",
    "confidence_class": "complete",
    "rule_status_at_evaluation": "agreed",
    "tariff_status_at_evaluation": "in_force",
    "created_at": "2026-03-21T15:47:19.000000Z"
  }
]
```

## GET /api/v1/audit/cases/{case_id}/latest

Returns the latest persisted audit trail for a case without requiring the caller to know the newest `evaluation_id`.

**Path parameters**

- `case_id`: case UUID

**curl**

```bash
curl http://localhost:8000/api/v1/audit/cases/29dc2946-6ef0-46a0-b3eb-0f6a64e40db7/latest
```

**Sample response**

The response shape is the same as `GET /api/v1/audit/evaluations/{evaluation_id}`.

## GET /api/v1/sources

Lists provenance source records.

**Query parameters**

- `source_type`
- `authority_tier`
- `status`
- `limit`
- `offset`

## GET /api/v1/sources/{source_id}

Returns one provenance source record by `source_id`.

## GET /api/v1/provisions

Lists legal provisions.

**Query parameters**

- `topic_primary`
- `source_id`
- `annex_ref`
- `limit`
- `offset`

## GET /api/v1/provisions/{provision_id}

Returns one legal provision by `provision_id`.

## GET /api/v1/intelligence/corridors/{exporter}/{importer}

Returns the active corridor profile for one supported corridor.

Published seeded profile surface as of March 30, 2026:

- `GHA -> NGA`
- `CMR -> NGA`
- `CIV -> NGA`
- `SEN -> NGA`
- `GHA -> CMR`

The locked assessment corpus includes additional synthetic test-only corridors.
Those scenarios validate deterministic assessments, but they do not imply that
this endpoint will return a published `corridor_profile` row for every v0.1
golden-case pair.

## GET /api/v1/intelligence/alerts

Lists alerts filtered by status, severity, and optional entity scope.

**Query parameters**

- `status`
- `severity`
- `entity_type`
- `entity_key`
- `limit`

## Error Shape

All endpoints can return the shared structured error envelope:

```json
{
  "error": {
    "code": "CORRIDOR_NOT_SUPPORTED",
    "message": "Country 'ZZZ' is not supported in v0.1",
    "details": {
      "country_code": "ZZZ"
    }
  },
  "meta": {
    "request_id": "7dd4a6fa-2c12-4f7d-8b41-cfc1063a3b74",
    "timestamp": "2026-03-21T16:17:31.334040Z"
  }
}
```

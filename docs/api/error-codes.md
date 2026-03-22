# AIS Error Codes

AIS returns structured error responses in this format:

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
    "request_id": "f141f5fc-c7bc-43e1-96b8-2d48d21fa95f",
    "timestamp": "2026-03-21T16:12:08.441178Z"
  }
}
```

Use `error.code` for programmatic handling and `meta.request_id` when tracing issues in server logs.

## Domain Errors

| HTTP status | Code | Exception | When it occurs | What to do |
|---|---|---|---|---|
| `400` | `AIS_ERROR` | `AISBaseException` | Generic domain-level error not mapped to a more specific subclass. | Inspect `message` and `details`, log the `request_id`, and treat it as a bad request unless your deployment documents something more specific. |
| `404` | `CLASSIFICATION_ERROR` | `ClassificationError` | AIS could not resolve the supplied code to a canonical HS6 product. | Verify the product code, send at least 6 digits, and confirm the correct HS version. |
| `404` | `RULE_NOT_FOUND` | `RuleNotFoundError` | No applicable PSR exists for the resolved HS6. | Recheck the HS6 code and HS version. If correct, treat it as a legal-data gap rather than a pass. |
| `404` | `TARIFF_NOT_FOUND` | `TariffNotFoundError` | No tariff schedule exists for the corridor and product. | Verify exporter/importer support, year coverage, and whether the corridor is loaded in v0.1. |
| `404` | `STATUS_UNKNOWN` | `StatusUnknownError` | No status assertion exists for the requested entity key. | Recheck the entity key format and whether status data has been loaded. |
| `404` | `AUDIT_TRAIL_NOT_FOUND` | `AuditTrailNotFoundError` | No persisted evaluation exists for the requested `evaluation_id` or `case_id`. | Confirm the case or evaluation id and ensure the assessment was run with audit persistence enabled. |
| `422` | `CORRIDOR_NOT_SUPPORTED` | `CorridorNotSupportedError` | The exporter or importer is outside the locked v0.1 corridor list. | Use one of the supported country codes: `NGA`, `GHA`, `CIV`, `SEN`, `CMR`. |
| `422` | `INSUFFICIENT_FACTS` | `InsufficientFactsError` | The request lacks facts required for deterministic evaluation. | Supply the missing production facts and retry. |
| `500` | `EXPRESSION_EVALUATION_ERROR` | `ExpressionEvaluationError` | The safe expression evaluator could not evaluate the rule expression. | Capture the `request_id`, inspect the stored rule expression and facts, and treat it as a server-side issue. |

## Unhandled Errors

| HTTP status | Code | When it occurs | What to do |
|---|---|---|---|
| `500` | `INTERNAL_ERROR` | Any unhandled exception in the request pipeline. The response body never includes a traceback. | Log the `request_id` and investigate the server logs. Retry only if the failure appears transient. |

## Validation Errors

FastAPI can also return request-validation errors before application code runs,
for example when:

- a required field is missing
- a country code fails request validation
- a query parameter has the wrong type

Those are framework-level 422 responses rather than domain exceptions.

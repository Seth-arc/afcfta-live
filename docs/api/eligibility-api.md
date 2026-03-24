# Eligibility Assessment API

## Endpoint

```text
POST /api/v1/assessments
```

This is the main decision endpoint in AIS. It runs the full deterministic
AfCFTA eligibility engine and returns a structured origin decision.

Important trade terms:

- **HS6**: the six-digit Harmonized System product classification used as the canonical product spine.
- **PSR**: product-specific rule from the AfCFTA rules of origin.
- **CTH**: change in tariff heading. The non-originating input heading and the finished-product heading must differ.
- **VNM**: value of non-originating materials. Non-originating content must stay at or below a legal threshold.
- **WO**: wholly obtained. The product must be wholly obtained in the territory.

## Request Schema

### Top-Level Fields

| Field | Type | Required | Trade meaning |
|---|---|---|---|
| `hs6_code` | string | Yes | Product code supplied by the caller. AIS normalizes it to six digits. |
| `hs_version` | string | No | HS nomenclature version. Defaults to `HS2017`. |
| `exporter` | string | Yes | ISO alpha-3 exporter country code. |
| `importer` | string | Yes | ISO alpha-3 importer country code. |
| `year` | integer | Yes | Year used for tariff lookup and date-scoped legal resolution. |
| `persona_mode` | string | Yes | User perspective such as `exporter`, `officer`, or `analyst`. This affects evidence output. |
| `production_facts` | array | Yes | Typed factual inputs used by pathway logic and general rules. |
| `existing_documents` | array | No | Canonical submitted document inventory used to compute readiness during the assessment. |
| `case_id` | string or UUID | No | Existing case id. When supplied, the service persists the evaluation trace against that case. When omitted, the interface layer auto-creates a submitted case so the response is still replayable. |

Compatibility note:

- `existing_documents` is the canonical request field for assessments.
- `submitted_documents` is accepted as an input-only alias for backward compatibility.
- Responses and documentation always use the canonical field name `existing_documents`.

## Case-Backed Assessment Endpoint

AIS also supports assessing facts already stored on an existing case:

```text
POST /api/v1/assessments/cases/{case_id}
```

That request only needs:

- `year`
- optional `existing_documents`

The same compatibility rule applies here:

- canonical `existing_documents`
- input-only alias `submitted_documents`

The service loads stored case facts, normalizes them through the same path as direct assessments, and persists the resulting evaluation and audit trail against the case.

## Replay Identifiers

Both assessment endpoints return the same JSON response body, plus these response headers:

- `X-AIS-Case-Id`: case identifier that owns the persisted evaluation.
- `X-AIS-Evaluation-Id`: newly persisted evaluation identifier.
- `X-AIS-Audit-URL`: relative audit replay URL for the returned evaluation.

Direct `POST /api/v1/assessments` calls never return an unreplayable legal decision. If the caller omits `case_id`, AIS auto-creates a submitted case, persists the evaluation and atomic checks against it, and returns the generated identifiers in these headers.

### `production_facts[]` Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `fact_type` | string | Yes | Fact family or label. In practice it usually mirrors `fact_key`. |
| `fact_key` | string | Yes | Canonical variable name used by rule evaluation, such as `tariff_heading_input`, `ex_works`, or `direct_transport`. |
| `fact_value_type` | string | Yes | Type selector: `text`, `number`, `boolean`, `date`, or `json`. |
| `fact_value_text` | string | Conditional | Used when `fact_value_type = "text"`. |
| `fact_value_number` | number or string | Conditional | Used when `fact_value_type = "number"`. |
| `fact_value_boolean` | boolean | Conditional | Used when `fact_value_type = "boolean"`. |
| `fact_value_date` | date | Conditional | Used when `fact_value_type = "date"`. |
| `fact_value_json` | object or array | Conditional | Used for JSON or list-style inputs. |
| `unit` | string | No | Optional unit for numeric facts. |
| `source_type` | string | No | Provenance of the fact. Defaults to `user_input`. |
| `source_ref` | string | No | Optional document or source reference. |
| `fact_order` | integer | No | Ordering hint when multiple facts of the same type are sent. |

## Response Schema

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

### Field Meanings

| Field | Meaning |
|---|---|
| `eligible` | Final result. `true` means at least one pathway passed, general rules passed, and no hard blocker stopped the run. |
| `pathway_used` | The legal pathway that passed, such as `CTH`, `VNM`, or `WO`. If no pathway passed, this is `null`. |
| `rule_status` | Legal status of the governing PSR, such as `agreed`, `provisional`, or `pending`. |
| `confidence_class` | Structural completeness of the assessment: `complete`, `provisional`, or `incomplete`. |
| `tariff_outcome` | Tariff context for the corridor and year. This can be `null` if no schedule exists. |
| `tariff_outcome.preferential_rate` | Preferential AfCFTA rate for the resolved year. |
| `tariff_outcome.base_rate` | MFN or base rate for comparison. |
| `tariff_outcome.status` | Tariff-layer status, such as `in_force` or a provisional schedule state. |
| `failures` | Machine-readable failure codes explaining why the product did not qualify or why the result is constrained. |
| `missing_facts` | Facts required for deterministic evaluation but not supplied. AIS never silently defaults them. |
| `evidence_required` | Human-readable evidence items that would normally be needed to support the claim. |
| `missing_evidence` | Required evidence items not present in the submitted document inventory. |
| `readiness_score` | Convenience readiness metric derived from the evidence service. |
| `completeness_ratio` | Fraction of required evidence items already present. |

This assessment contract is frozen in integration coverage at:

- [tests/integration/test_golden_path.py](tests/integration/test_golden_path.py#L574)
- [tests/integration/test_golden_path.py](tests/integration/test_golden_path.py#L988)
- [tests/integration/test_audit_api.py](tests/integration/test_audit_api.py#L27)

## Failure Codes

These codes come from `app/core/failure_codes.py`.

| Failure code | Meaning | What the user should do |
|---|---|---|
| `UNKNOWN_HS6` | The product code could not be resolved to a supported HS6 product. | Send at least 6 valid HS digits, verify the first 6 digits, and confirm the HS version. |
| `NO_PSR_FOUND` | AIS has no applicable product-specific rule for the resolved HS6. | Recheck the HS6 code and HS version. If correct, treat it as a legal-data gap. |
| `NO_SCHEDULE` | No tariff schedule was found for the corridor. | Verify exporter/importer support and whether the corridor is loaded in v0.1. |
| `NOT_OPERATIONAL` | The corridor or instrument is not yet operational. | Do not rely on AfCFTA treatment for that corridor until status changes. |
| `MISSING_CORE_FACTS` | AIS could not evaluate any rule pathway because required production data was missing. | Supply the key facts needed for the relevant pathway. |
| `FAIL_CTH_NOT_MET` | Change in tariff heading was not demonstrated. | Show that the input heading differs from the output heading, or qualify under another pathway. |
| `FAIL_CTSH_NOT_MET` | Change in tariff subheading was not demonstrated. | Show that the input subheading differs from the output subheading. |
| `FAIL_VNM_EXCEEDED` | Non-originating material value exceeded the legal threshold. | Reduce non-originating content or qualify under a different pathway. |
| `FAIL_VA_INSUFFICIENT` | Regional value added was below the required threshold. | Increase local or originating value added and reassess. |
| `FAIL_WO_NOT_MET` | The product was not proven to be wholly obtained. | Supply wholly-obtained evidence, or qualify under a non-WO pathway if available. |
| `FAIL_PROCESS_NOT_MET` | The required specific process was not performed or not evidenced. | Perform the required process or provide process evidence. |
| `FAIL_INSUFFICIENT_OPERATIONS` | Only minimal or insufficient operations were performed. | Show substantial transformation beyond simple operations. |
| `FAIL_DIRECT_TRANSPORT` | Direct transport or permitted transit was not demonstrated. | Provide transport evidence or correct the logistics path. |
| `FAIL_CUMULATION_INVALID` | A cumulation claim was made but the legal conditions were not satisfied. | Provide valid cumulation-partner evidence and ensure the selected pathway allows cumulation. |
| `RULE_STATUS_PENDING` | The PSR is pending and not yet enforceable. | Treat the rule as unavailable for a binding origin claim. |
| `RULE_STATUS_PROVISIONAL` | The rule exists but remains provisional. | Proceed cautiously and verify whether a more authoritative update exists. |
| `SCHEDULE_PROVISIONAL` | The tariff schedule is provisional. | Treat tariff outputs as provisional and verify official publication. |
| `SCHEDULE_NOT_GAZETTED` | The schedule has not yet been gazetted or formally published. | Confirm publication status before operational use. |

## Worked Example: HS6 110311, GHA -> NGA, CTH Pass

### Scenario

- Product: `110311`
- Product description: groats and meal of wheat
- Exporter: `GHA`
- Importer: `NGA`
- Year: `2025`
- Rule pathway: `CTH`

### Example Request

```json
{
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
}
```

### How AIS Evaluates It

1. `110311` resolves to the canonical HS6 backbone record for groats and meal of wheat.
2. AIS resolves the governing PSR through the precomputed applicability table.
3. The applicable pathway is `CTH`.
4. AIS compares:
   - `tariff_heading_input = 1001`
   - `tariff_heading_output = 1103`
5. The headings differ, so the `CTH` pathway passes.
6. General rules pass because:
   - there is no failing insufficient-operations declaration
   - there is no invalid cumulation claim
   - `direct_transport = true`
7. The rule status is `agreed`.
8. The tariff layer resolves `GHA -> NGA` for 2025 and returns a 0% preferential rate against a 15% base rate.

### Example Response

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

### Why This Result Is `complete`

It is `complete` because:

- the governing rule is `agreed`
- the necessary `CTH` facts were present
- no hard blocker fired
- the direct transport fact was present and passed

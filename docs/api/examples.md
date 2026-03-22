# AIS API Examples

These examples assume:

```text
http://localhost:8000/api/v1
```

Authentication is not enforced in v0.1. If your deployment adds API-key auth,
include your gateway-specific header such as `X-API-Key`.

## Look Up The Rule For A Product

### curl

```bash
curl "http://localhost:8000/api/v1/rules/110311?hs_version=HS2017"
```

### Python (`requests`)

```python
import requests

base_url = "http://localhost:8000/api/v1"
response = requests.get(
    f"{base_url}/rules/110311",
    params={"hs_version": "HS2017"},
    timeout=30,
)
response.raise_for_status()
rule = response.json()

print(rule["hs6_code"])
print(rule["rule_status"])
print(rule["pathways"][0]["pathway_code"])
```

## Check The Tariff For A Corridor

### curl

```bash
curl "http://localhost:8000/api/v1/tariffs?exporter=GHA&importer=NGA&hs6=110311&year=2025&hs_version=HS2017"
```

### Python (`requests`)

```python
import requests

base_url = "http://localhost:8000/api/v1"
response = requests.get(
    f"{base_url}/tariffs",
    params={
        "exporter": "GHA",
        "importer": "NGA",
        "hs6": "110311",
        "year": 2025,
        "hs_version": "HS2017",
    },
    timeout=30,
)
response.raise_for_status()
tariff = response.json()

print("Preferential rate:", tariff["preferential_rate"])
print("Base rate:", tariff["base_rate"])
print("Category:", tariff["tariff_category"])
```

## Run An Eligibility Assessment

### curl

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

### Python (`requests`)

```python
import requests

base_url = "http://localhost:8000/api/v1"
payload = {
    "hs6_code": "110311",
    "hs_version": "HS2017",
    "exporter": "GHA",
    "importer": "NGA",
    "year": 2025,
    "persona_mode": "exporter",
    "production_facts": [
        {
            "fact_type": "tariff_heading_input",
            "fact_key": "tariff_heading_input",
            "fact_value_type": "text",
            "fact_value_text": "1001",
        },
        {
            "fact_type": "tariff_heading_output",
            "fact_key": "tariff_heading_output",
            "fact_value_type": "text",
            "fact_value_text": "1103",
        },
        {
            "fact_type": "direct_transport",
            "fact_key": "direct_transport",
            "fact_value_type": "boolean",
            "fact_value_boolean": True,
        },
    ],
}

response = requests.post(f"{base_url}/assessments", json=payload, timeout=30)
response.raise_for_status()
assessment = response.json()

print("Eligible:", assessment["eligible"])
print("Pathway:", assessment["pathway_used"])
print("Failures:", assessment["failures"])
```

## Check Evidence Readiness

For rule-level evidence, `entity_key` uses this format:

```text
HS6_RULE:{psr_id}
```

You can get `psr_id` from `GET /rules/{hs6}`.

### curl

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

### Python (`requests`)

```python
import requests

base_url = "http://localhost:8000/api/v1"
payload = {
    "entity_type": "hs6_rule",
    "entity_key": "HS6_RULE:8c6a4b89-4d4e-4d5b-9eb4-4d1775edb3b0",
    "persona_mode": "exporter",
    "existing_documents": ["certificate_of_origin"],
}

response = requests.post(
    f"{base_url}/evidence/readiness",
    json=payload,
    timeout=30,
)
response.raise_for_status()
readiness = response.json()

print("Missing items:", readiness["missing_items"])
print("Readiness score:", readiness["readiness_score"])
```

## Retrieve An Audit Trail

Typical flow:

1. create or know a `case_id`
2. run an assessment with that `case_id`
3. list evaluations for the case
4. fetch one full trace by `evaluation_id`

### curl

```bash
curl http://localhost:8000/api/v1/audit/cases/29dc2946-6ef0-46a0-b3eb-0f6a64e40db7/evaluations
curl http://localhost:8000/api/v1/audit/evaluations/4c651cd2-8f0f-4c16-9f37-8dfceef41f26
```

### Python (`requests`)

```python
import requests

base_url = "http://localhost:8000/api/v1"
case_id = "29dc2946-6ef0-46a0-b3eb-0f6a64e40db7"

evals_response = requests.get(
    f"{base_url}/audit/cases/{case_id}/evaluations",
    timeout=30,
)
evals_response.raise_for_status()
evaluations = evals_response.json()

evaluation_id = evaluations[0]["evaluation_id"]

trail_response = requests.get(
    f"{base_url}/audit/evaluations/{evaluation_id}",
    timeout=30,
)
trail_response.raise_for_status()
trail = trail_response.json()

print("Outcome:", trail["final_decision"]["overall_outcome"])
print("Pathway:", trail["final_decision"]["pathway_used"])
print("Atomic checks:", len(trail["atomic_checks"]))
```

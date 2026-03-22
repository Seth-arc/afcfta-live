# Quickstart

## I have an HS6 code and want to know if my product qualifies

This is the fastest way to get a first result from AIS.

Example product:

- HS6: `110311`
- Product: groats and meal of wheat
- Exporter: `GHA` (Ghana)
- Importer: `NGA` (Nigeria)
- Year: `2025`

## What You Need

Before you run an assessment, collect:

- the **HS6 code**
  An HS6 code is the 6-digit product classification used in customs and tariff schedules.
- the **exporter country**
- the **importer country**
- the **year**
- the key **production facts**
  For this example, the rule is `CTH`, which means **change in tariff heading**.
  You need to know:
  - the tariff heading of the non-originating input
  - the tariff heading of the finished product
  - whether the goods were shipped under direct transport

## Run One Assessment

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

## How To Read The Result

Example response:

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
    "Certificate of Origin",
    "Supplier declaration"
  ],
  "confidence_class": "complete"
}
```

In plain language:

- `eligible: true` means the product passed the legal rule test for origin.
- `pathway_used: "CTH"` means it qualified through the change-in-tariff-heading rule.
- `rule_status: "agreed"` means the rule is treated as settled, not provisional or pending.
- `tariff_outcome` shows the tariff context for that corridor and year.
- `failures: []` means no legal test failed.
- `missing_facts: []` means you gave the engine the facts it needed.
- `evidence_required` tells you which documents you would normally need to support the claim.
- `confidence_class: "complete"` means the result is structurally complete: the key facts were present and the rule status is agreed.

If you only do one thing first, do this:

1. run the assessment
2. check `eligible`
3. check `pathway_used`
4. check `failures` and `missing_facts`

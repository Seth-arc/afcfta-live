# Eligibility Walkthrough

This walkthrough shows one full eligibility assessment from start to finish.

We use:

- HS6 `110311`
- exporter `GHA` (Ghana)
- importer `NGA` (Nigeria)
- year `2025`

## Step 1: Understand The Product

HS6 `110311` is:

- **groats and meal of wheat**

An **HS6 code** is the 6-digit product code used in customs classification and tariff schedules.
AIS uses HS6 as the canonical product spine for every decision.

## Step 2: Understand The Rule

For this product, the governing rule is:

- **CTH**

`CTH` means **change in tariff heading**.

A **tariff heading** is the first 4 digits of the tariff classification.
In plain language, this rule asks:

> Did the non-originating input and the finished product end up in different 4-digit headings?

If yes, the product may qualify under that rule.
If no, it fails that rule.

## Step 3: Know What Facts You Need

For this product, you do not start with a complex value calculation.
You start with the heading comparison.

You need:

- the heading of the non-originating input
- the heading of the finished product
- whether the goods were shipped under direct transport

For the **pass** example, we use:

- input heading: `1001`
- output heading: `1103`
- direct transport: `true`

Because `1001` and `1103` are different, the tariff-heading test passes.

## Step 4: Submit The Assessment

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

## Step 5: Read The Response

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

Now read it as a human story:

### `hs6_code: "110311"`

This confirms the product that AIS actually assessed.

### `eligible: true`

The product qualified for preferential treatment under the loaded rule set,
given the facts you supplied.

This does **not** mean customs clearance is guaranteed.
It means the product passed the legal test AIS could evaluate from the published rule set and supplied facts.

### `pathway_used: "CTH"`

This tells you which legal pathway was satisfied.

In this example, the product qualified because the input heading and output heading were different.

### `rule_status: "agreed"`

This tells you the legal status of the rule itself.

`agreed` means the rule is being treated as settled rather than provisional or pending.

### `tariff_outcome`

```json
{
  "preferential_rate": "0.0000",
  "base_rate": "15.0000",
  "status": "in_force"
}
```

This tells you the tariff context:

- `preferential_rate`: the AfCFTA rate that would apply if the claim is accepted
- `base_rate`: the normal rate for comparison
- `status`: whether that tariff position is treated as in force or still provisional

### `failures: []`

No legal test failed.

### `missing_facts: []`

You gave AIS the facts it needed to evaluate the rule.

AIS never silently fills in missing facts. If something was missing, it would appear here.

### `evidence_required`

This lists the documents you would normally need to support the origin claim.

In this example:

- Certificate of Origin
- Supplier declaration

### `confidence_class: "complete"`

This means:

- the key facts were present
- the rule status is agreed
- there is no structural data gap in this result

## What `eligible: true` Means Legally

In legal terms, `eligible: true` means:

- AIS found an applicable product-specific rule
- the submitted facts satisfied that rule
- no separate general origin rule blocked the claim
- no hard blocker stopped the assessment

It does **not** mean:

- customs must accept the claim automatically
- documentary review is unnecessary
- competent authorities are bound by this software output alone

It is decision support anchored to loaded legal text.

## Now The Fail Case: No Tariff Shift

Let’s keep the same product and corridor, but change the facts so the input heading and output heading are the same.

That means:

- input heading: `1103`
- output heading: `1103`

Now the product does **not** demonstrate a change in tariff heading.

### Fail Request

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
        "fact_value_text": "1103"
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

### Example Failure Response

```json
{
  "hs6_code": "110311",
  "eligible": false,
  "pathway_used": null,
  "rule_status": "agreed",
  "tariff_outcome": {
    "preferential_rate": "0.0000",
    "base_rate": "15.0000",
    "status": "in_force"
  },
  "failures": [
    "FAIL_CTH_NOT_MET"
  ],
  "missing_facts": [],
  "evidence_required": [
    "Certificate of Origin",
    "Supplier declaration"
  ],
  "confidence_class": "complete"
}
```

## Read The Failure Response Field By Field

### `eligible: false`

The product did not qualify under the loaded rule set and supplied facts.

### `pathway_used: null`

No legal pathway passed.

### `rule_status: "agreed"`

The rule itself is still settled and valid. The failure is not because the rule is pending.

### `tariff_outcome`

You still get tariff context even though the product did not qualify.
That is useful for comparing what the importer would pay if the preferential claim fails.

### `failures: ["FAIL_CTH_NOT_MET"]`

This is the key reason.

In plain language:

- the product needed a change in tariff heading
- the headings were the same
- the rule was not met

### `missing_facts: []`

The system had enough information to decide.
This is a real fail, not a missing-data situation.

### `evidence_required`

These are still shown because they are the normal documents tied to the claim context,
even if the legal test itself failed.

### `confidence_class: "complete"`

This is still `complete` because the facts were sufficient and the rule status is agreed.
`complete` does **not** mean the claim succeeded.
It means the decision was made on a complete enough footing.

## What You Learned From This Example

For HS6 `110311`:

- the legal pathway is `CTH`
- the critical question is whether the input and output headings differ
- different headings can produce `eligible: true`
- same headings can produce `eligible: false`
- the response tells you not just the result, but exactly why

# How Eligibility Works

This document explains, in plain language, how AIS decides whether a product
qualifies for AfCFTA preferential treatment.

It is written for officers, reviewers, and compliance decision-makers who need
to understand the logic before trusting the output.

The core principle is simple:

- AIS is **deterministic**
- it does **not** guess
- it does **not** fill in missing facts silently
- it does **not** use machine learning to score likelihood

The same inputs always produce the same result.

## The 8-Step Eligibility Pipeline

The decision process is easiest to understand in eight stages.

### Step 1: Identify The Product

AIS first resolves the product to a canonical **HS6** code.

An **HS6 code** is the six-digit Harmonized System product classification used
for customs and tariff schedules.

If a user supplies:

- `110311`
- `1103.11`
- a longer HS8 or HS10 code beginning with `110311`

AIS normalizes the input to `110311`.

Why this matters:

- the system does not decide against free-text product names
- it does not match on descriptions
- it anchors the whole decision on one canonical product identifier

### Step 2: Find The Applicable Rule

Once the product is identified, AIS finds the governing **product-specific
rule**, or **PSR**.

It does not do this by guessing from text.
It uses a precomputed applicability table that links each HS6 product to the
rule that governs it.

That matters because AfCFTA rules can apply at different levels:

- chapter
- heading
- subheading

AIS resolves that inheritance in advance and stores the result, so the engine
does not have to reconstruct rule inheritance on the fly.

### Step 3: Check For Blockers

Before AIS tries to decide eligibility, it asks whether there is any reason
the assessment should stop early.

Examples of blockers:

- the rule is still `pending`
- the corridor is not yet operational
- the essential facts for every pathway are missing

This is a trust feature.
The system refuses to present a blocked or incomplete situation as a settled
pass/fail result.

### Step 4: Evaluate The Rule

If there is no hard blocker, AIS evaluates the applicable rule against the
submitted production facts.

The rule may contain:

- one legal pathway
- or several alternative pathways

If several pathways exist, they are alternatives.
AIS tries them in priority order.

Within a pathway:

- all conditions must be satisfied

Across pathways:

- the first passing pathway wins

### Step 5: Apply General Origin Rules

A product can pass its product-specific rule and still fail the broader rules
of origin.

AIS therefore checks the general rules separately, including:

- insufficient operations
- cumulation
- direct transport

This separation is important.
It prevents a product from appearing eligible just because it satisfied one
technical PSR while failing a broader legal condition.

### Step 6: Check Legal Status

AIS then applies the legal status layer.

It checks whether the rule or corridor context is:

- `agreed`
- `provisional`
- `pending`
- `partially_agreed`

This ensures the system never presents a still-negotiated rule as settled law.

### Step 7: Look Up The Tariff

AIS then resolves the tariff position for the corridor and year:

- preferential rate
- base rate
- tariff status

This tells the user not only whether the product may qualify, but what the
tariff consequence would be if the preference were accepted.

### Step 8: Determine Evidence Requirements

Finally, AIS identifies the evidence normally needed to support the claim.

Examples:

- Certificate of Origin
- Supplier declaration

This turns the assessment from a pure legal conclusion into something useful
for operations and file preparation.

## Worked Example: HS6 110311, GHA -> NGA

We will follow one product through all eight stages.

### The Product

- HS6: `110311`
- Product: groats and meal of wheat
- Exporter: `GHA`
- Importer: `NGA`
- Year: `2025`

### The Rule

For this product, the applicable rule is:

- `CTH`

`CTH` means **change in tariff heading**.

In plain terms, AIS asks:

> Are the non-originating input and the finished product classified under different 4-digit tariff headings?

### Pass Scenario

Submitted facts:

- `tariff_heading_input = 1001`
- `tariff_heading_output = 1103`
- `direct_transport = true`

Now walk through the pipeline.

#### Step 1: Identify The Product

AIS resolves `110311` to the canonical HS6 product record for groats and meal of wheat.

Conclusion:

- product identity confirmed

#### Step 2: Find The Applicable Rule

AIS looks up the applicable PSR through the applicability table.

It finds:

- rule type: `CTH`
- rule status: `agreed`
- applicability type: `direct`

Conclusion:

- there is a valid governing rule for this HS6

#### Step 3: Check For Blockers

AIS checks whether the assessment should stop before legal evaluation.

It asks:

- is the rule pending?
- is the corridor non-operational?
- are core facts missing?

In this example:

- rule is not pending
- corridor is operational
- the necessary `CTH` facts are present

Conclusion:

- no hard blocker

#### Step 4: Evaluate The Rule

AIS evaluates the `CTH` pathway against the facts:

- input heading: `1001`
- output heading: `1103`

The headings differ.

Conclusion:

- the `CTH` pathway passes

#### Step 5: Apply General Origin Rules

AIS now checks the broader rules:

- no failing insufficient-operations flag
- no invalid cumulation claim
- `direct_transport = true`

Conclusion:

- general rules pass

#### Step 6: Check Legal Status

AIS applies the status overlay.

In this example:

- rule status is `agreed`

Conclusion:

- no status-based downgrade to a provisional result

#### Step 7: Look Up The Tariff

AIS resolves the tariff for `GHA -> NGA` in `2025`.

Example tariff outcome:

- preferential rate: `0.0000`
- base rate: `15.0000`
- tariff status: `in_force`

Conclusion:

- tariff context is available and operational

#### Step 8: Determine Evidence Requirements

AIS resolves the supporting evidence normally required for the claim.

Example result:

- Certificate of Origin
- Supplier declaration

Conclusion:

- the user now knows both the legal outcome and the likely documentation burden

### Final Result In The Pass Scenario

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

What this means:

- the product satisfied the applicable rule
- the broader origin rules did not disqualify it
- the rule status was settled enough to support a complete result
- the system can explain exactly why it passed

## The Same Product Failing

Now take the same product and corridor, but change the production facts:

- `tariff_heading_input = 1103`
- `tariff_heading_output = 1103`
- `direct_transport = true`

This means there is **no tariff heading change**.

### What Happens

#### Step 1: Product Identification

Still resolves to `110311`.

#### Step 2: Rule Lookup

Still resolves to the `CTH` rule.

#### Step 3: Blockers

Still no hard blocker.

#### Step 4: Rule Evaluation

AIS compares:

- input heading `1103`
- output heading `1103`

They are the same.

Conclusion:

- the `CTH` pathway fails

#### Step 5: General Origin Rules

Even if general rules are fine, they do not rescue a failed PSR pathway.

Conclusion:

- the product remains not eligible

#### Step 6: Status Check

The rule may still be `agreed`.
That means the failure is a real legal failure, not a status problem.

#### Step 7: Tariff Lookup

Tariff context can still be returned.
This is useful for understanding the cost difference between successful and unsuccessful qualification.

#### Step 8: Evidence Requirements

Evidence requirements may still be shown, because they describe the normal claim context.

### Final Result In The Fail Scenario

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

What this tells the officer:

- the rule was found
- the system had enough facts to decide
- the product failed the legal pathway
- the result is still structurally complete because the facts were sufficient and the rule status was agreed

## Why This Matters For Trust

AIS is designed so that a user can inspect not only the final answer, but the
route taken to get there.

That is why the system:

- separates rule lookup from general-rule checks
- refuses silent inference
- marks unsettled law as provisional or pending
- preserves verbatim legal text

Every step produces an auditable record. You can retrieve the full decision
trace for any assessment and see exactly what was checked, what passed, what
failed, and which legal text was used.

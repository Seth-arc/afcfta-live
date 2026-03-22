# Understanding Results

When AIS returns an assessment response, it is telling you:

- what product it assessed
- whether the product qualified under the loaded rules
- which legal pathway was used, if any
- what facts were missing
- what documents would usually be needed
- what tariff outcome applies in the corridor context

Here is the typical response shape:

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

## `eligible`

This answers the core question:

> Does this product qualify for preferential treatment under the loaded AfCFTA rule set, based on the facts provided?

- `true` means the product passed at least one legal pathway and no hard blocker stopped the decision.
- `false` means it did not qualify, or the system could not get to a qualifying result.

## `pathway_used`

This tells you **which legal test was satisfied**.

Examples:

- `CTH` = change in tariff heading
- `VNM` = value of non-originating materials
- `VA` = value added
- `WO` = wholly obtained

If this field is `null`, no pathway passed.

## `rule_status`

This tells you whether the governing rule is treated as settled law or still in a provisional state.

Examples:

- `agreed`
- `provisional`
- `pending`

In plain terms:

- `agreed` means the rule is treated as settled
- `provisional` means the rule exists but may still change
- `pending` means it is not yet enforceable

## `confidence_class`

This tells you **how complete the assessment is structurally**.

It is not a probability score.

### `complete`

Use this when:

- the required facts were present
- the rule is agreed
- there is no structural gap preventing a firm engine result

### `provisional`

Use this when:

- the rule or schedule is provisional
- or the legal basis is still unsettled

### `incomplete`

Use this when:

- key facts are missing
- or an operational/legal blocker prevents a full assessment

Important:

- `complete` does not mean the product qualifies
- `incomplete` does not automatically mean it fails legally
- it means the engine does not have enough complete footing for a settled result

## `failures`

This list tells you **why the product did not qualify**, using machine-readable codes.

Below is each code in plain language.

### `UNKNOWN_HS6`

The product code could not be resolved.

Plain meaning:

- AIS could not match the product to a valid HS6 record.

What to do:

- check the first six digits of the HS code
- verify the classification

### `NO_PSR_FOUND`

No product-specific rule was found.

Plain meaning:

- AIS has no applicable origin rule loaded for that product.

What to do:

- verify the HS6 code
- confirm the rule exists in the current dataset

### `NO_SCHEDULE`

No tariff schedule was found for that corridor.

Plain meaning:

- the rule assessment may still run, but tariff data is missing.

What to do:

- verify the exporter and importer
- check whether that corridor is loaded in v0.1

### `NOT_OPERATIONAL`

The corridor or instrument is not yet operational.

Plain meaning:

- even if a legal rule exists, the corridor may not yet be in an operational state for use.

What to do:

- verify current corridor status with the competent authority

### `MISSING_CORE_FACTS`

The system was missing the facts required to evaluate the relevant pathway.

Plain meaning:

- AIS could not make a proper legal test because the core production data was absent.

What to do:

- provide the missing headings, values, process facts, or transport facts

### `FAIL_CTH_NOT_MET`

Change in tariff heading was not demonstrated.

Plain meaning:

- the input and output headings did not change the way the rule requires.

### `FAIL_CTSH_NOT_MET`

Change in tariff subheading was not demonstrated.

Plain meaning:

- the input and output subheadings did not change as required.

### `FAIL_VNM_EXCEEDED`

The value of non-originating materials was too high.

Plain meaning:

- too much non-originating content remained in the product.

### `FAIL_VA_INSUFFICIENT`

Value added was too low.

Plain meaning:

- the local or originating value contribution did not reach the legal threshold.

### `FAIL_WO_NOT_MET`

Wholly obtained status was not proven.

Plain meaning:

- the product did not meet the wholly-obtained rule or the facts did not support it.

### `FAIL_PROCESS_NOT_MET`

The required specific process was not performed.

Plain meaning:

- the rule required a particular manufacturing or processing step and AIS did not see support for it.

### `FAIL_INSUFFICIENT_OPERATIONS`

Only minimal operations were performed.

Plain meaning:

- simple or insufficient operations alone do not confer origin.

### `FAIL_DIRECT_TRANSPORT`

The direct transport requirement was not met.

Plain meaning:

- the goods were not shown to move directly, or through permitted transit, the way the rule requires.

### `FAIL_CUMULATION_INVALID`

The cumulation claim was invalid.

Plain meaning:

- the claim relied on AfCFTA-origin inputs from another state party, but the legal conditions for cumulation were not satisfied.

### `RULE_STATUS_PENDING`

The PSR is pending.

Plain meaning:

- the rule is not yet enforceable.

### `RULE_STATUS_PROVISIONAL`

The PSR is provisional.

Plain meaning:

- the rule exists, but the legal status is not fully settled.

### `SCHEDULE_PROVISIONAL`

The tariff schedule is provisional.

Plain meaning:

- tariff numbers may still change or may not yet be final.

### `SCHEDULE_NOT_GAZETTED`

The tariff schedule is not gazetted.

Plain meaning:

- the schedule may not yet be formally published or operationalized.

## `missing_facts`

This field tells you what information AIS needed but did not receive.

Examples:

- `tariff_heading_input`
- `tariff_heading_output`
- `ex_works`
- `non_originating`
- `direct_transport`

This is one of the most useful fields operationally.
It tells you exactly what to collect next.

## `evidence_required`

This lists the documents normally needed to support the claim.

Examples:

- Certificate of Origin
- Supplier declaration

This is not the same as `missing_facts`.

- `missing_facts` are data needed for the engine decision
- `evidence_required` are documents you would normally need to prove the claim in practice

## `tariff_outcome`

This tells you what the tariff picture looks like for that corridor and year.

### `preferential_rate`

The preferential AfCFTA rate that would apply if the claim is accepted.

### `base_rate`

The ordinary rate for comparison, often the MFN or base rate.

### `status`

The tariff-layer status, such as:

- `in_force`
- `provisional`

In plain language:

- this tells you whether the tariff result is operational and how settled it is

## What This System Does NOT Tell You

AIS is not:

- legal advice
- a guarantee of customs clearance
- a substitute for professional customs guidance
- a customs declaration system

What it does do:

- compute eligibility against the loaded rule set
- show you which legal pathway passed or failed
- tell you which facts were missing
- tell you which legal text produced the result through the audit trail

What you still must do:

- verify the result with your competent authority
- confirm that the legal and tariff data is current enough for your use case
- ensure your supporting documents match the claim you intend to make

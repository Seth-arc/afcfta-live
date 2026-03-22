# Status And Confidence

AIS does not treat every rule and tariff line as equally settled.

That is deliberate.

The AfCFTA is still being implemented, and not every rule, schedule, or
operational instrument is in the same legal state at the same time.

That is why every important output carries:

- **status**
- **confidence**

These fields are central to trust.
They prevent the system from presenting uncertain or still-negotiated material
as though it were settled law.

## Why Status Exists

AIS is not just asking:

> Did the product satisfy a technical rule?

It is also asking:

> What is the legal state of that rule and the surrounding operational context?

That matters because a product can:

- satisfy a pathway technically
- but still sit under a rule or corridor condition that is provisional, pending, or incomplete

## Rule Status Values

The main rule-status values used in AIS are:

- `agreed`
- `provisional`
- `pending`
- `partially_agreed`

## `agreed`

In practice, this means the rule is treated as settled and usable as a firm legal basis within the loaded dataset.

What users should infer:

- this is the strongest footing available in AIS
- a positive result under an agreed rule is more decision-ready than one under a provisional rule

## `provisional`

In practice, this means the rule exists and can be evaluated, but its legal
position is not fully settled.

What users should infer:

- the result may still be operationally useful
- but extra caution is required
- users should verify with the competent authority before relying on it for a live compliance decision

## `pending`

In practice, this means the rule is not yet enforceable as settled law.

What users should infer:

- even if the technical pathway appears satisfiable, AIS should not present that as a clean settled result
- a pending rule is a serious limitation for operational reliance

## `partially_agreed`

In practice, this means the legal material is only partly settled.

What users should infer:

- some structure exists
- but the rule is not yet strong enough to be treated as fully settled

This is a caution condition, not a green light.

## Why Status Matters For Compliance Decisions

A technical origin pass and a legally mature basis are not the same thing.

For example:

- a product may satisfy a `CTH` pathway
- but if the rule status is still `pending`, the user should not treat that outcome as settled law

That is why AIS carries status into the output rather than hiding it in a footnote.

## Confidence Class Values

AIS also produces:

- `complete`
- `provisional`
- `incomplete`

This is not a probability score.
It is a structural classification of how decision-ready the assessment is.

## `complete`

This means:

- the required facts were present
- the rule status is settled enough for a full decision
- there is no structural gap preventing a reliable engine result

What users should do:

- review the outcome
- review evidence requirements
- verify supporting documents
- use the audit trail if a deeper review is needed

## `provisional`

This means:

- the engine could evaluate the case
- but part of the legal or tariff footing is still provisional or pending

What users should do:

- do not treat the output as the final word
- verify the relevant rule or schedule with the competent authority
- treat the result as decision support rather than operational clearance confidence

## `incomplete`

This means:

- some required facts were missing
- or an operational or legal blocker prevented a fully settled assessment

What users should do:

- check `missing_facts`
- collect the missing production data
- verify corridor and status conditions
- rerun the assessment once the missing elements are resolved

## Why AIS Refuses To Present Uncertain Rules As Settled Law

This is one of the main reasons AIS is trustworthy.

The system does **not** say:

- “eligible” without status context
- “all clear” when the rule is still pending
- “pass” when required facts are missing

Instead, it exposes the uncertainty directly.

This is a design choice rooted in compliance integrity.

## “Eligible” Is Not The Same As “Will Clear Customs”

AIS computes eligibility against the loaded legal and operational rules.

Customs officers and competent authorities still make final determinations.

That means:

- AIS can tell you whether the product qualifies under the loaded rules
- AIS can tell you which facts and legal tests drove the result
- AIS cannot guarantee border treatment, acceptance of documents, or administrative clearance

This distinction is essential.

## How Status And Confidence Propagate Through The Assessment

Status is not an afterthought.
It affects how the result should be read.

Examples:

### Agreed Rule, Complete Facts

Possible outcome:

- `eligible: true`
- `rule_status: agreed`
- `confidence_class: complete`

Interpretation:

- technically passed
- legally on the strongest footing available in AIS

### Provisional Rule, Sufficient Facts

Possible outcome:

- `eligible: true`
- `rule_status: provisional`
- `confidence_class: provisional`

Interpretation:

- the pathway passed
- but the legal footing is not fully settled

### Pending Rule

Possible outcome:

- `eligible: false`
- `rule_status: pending`
- failure reflecting the status limitation

Interpretation:

- AIS refuses to present a pending rule as a settled basis for qualification

### Missing Facts

Possible outcome:

- `eligible: false`
- `missing_facts` is non-empty
- `confidence_class: incomplete`

Interpretation:

- the system could not responsibly finish the legal evaluation

## Why This Supports Trust

Users should trust AIS not because it always says “yes” or “no,” but because it
is explicit about what it knows, what it checked, and what remains uncertain.

That is why:

- every important output carries status
- every assessment carries a confidence class
- missing facts are listed explicitly
- unsettled law is shown as unsettled, not hidden

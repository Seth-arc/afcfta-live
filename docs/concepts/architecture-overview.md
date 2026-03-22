# Architecture Overview

This document is for technical evaluators who need to judge whether AIS is a
sound compliance engine.

It explains the system at a high level and focuses on the design choices that
matter for trust, auditability, and reproducibility.

## The HS6 Spine

AIS is built around a single canonical product spine:

- `hs_version + hs6_id`

Every operational layer joins through that canonical product identifier.

Why this matters:

- it eliminates ambiguity from text matching
- it avoids joining by product description
- it reduces the risk of inconsistent rule, tariff, and status resolution across layers

In practical terms, AIS does not decide against free-text descriptions like
“wheat meal” or “frozen fish.”
It decides against the canonical HS6 product record.

## Seven Data Layers

AIS is structured as a layered data system.

## 1. Backbone

Stores the canonical product spine.

Purpose:

- stable product identity for the whole engine

## 2. Rules

Stores:

- product-specific rules
- rule components
- eligibility pathways
- precomputed applicability records

Purpose:

- turn Appendix IV rules into executable but auditable structures

## 3. Tariffs

Stores:

- tariff schedule headers
- line items
- year-by-year preferential rates

Purpose:

- resolve tariff outcomes by corridor, product, and year

## 4. Status

Stores:

- status assertions
- transition clauses

Purpose:

- ensure the engine knows whether a rule or corridor condition is agreed, provisional, pending, or otherwise constrained

## 5. Evidence

Stores:

- evidence requirements
- verification questions
- readiness templates

Purpose:

- connect legal outcomes to documentation and verification needs

## 6. Decision

Stores:

- case files
- input facts
- persisted evaluations
- atomic check results

Purpose:

- preserve assessment inputs, outputs, and replayable audit traces

## 7. Intelligence

Stores:

- corridor profiles
- alert events

Purpose:

- provide higher-level corridor and monitoring context

## The Deterministic Guarantee

AIS is a deterministic engine.

That means:

- same inputs
- same rules
- same statuses
- same tariff data

produce the same outputs.

It does **not** use:

- ML scoring
- probabilistic inference
- heuristic ranking instead of legal evaluation

Instead, it executes boolean and structured rule logic against supplied facts.

This is one of the most important trust properties in the system.

## Service Boundaries

AIS enforces a clear separation of concerns:

- API handlers are thin
- services contain business logic
- repositories contain SQL and data access

Why this matters:

- route behavior stays simple and inspectable
- business logic can be tested independently
- SQL behavior can be reviewed separately from decision logic
- audit and legal review are easier because responsibilities are not mixed together

This also makes defects easier to isolate:

- a bad query is a repository issue
- a wrong legal decision path is a service issue
- a bad HTTP contract is a route issue

## The Expression Evaluator

AIS includes a dedicated expression evaluator for pathway logic.

It uses:

- a safe parser
- an explicit whitelist of allowed operations
- capped nesting depth
- bounded text-expression length

It does **not** use dynamic execution of rule text.

Why this matters:

- security
- reproducibility
- legal trust

A reviewer can inspect the evaluator logic and see that legal expressions are
parsed within a constrained grammar rather than executed as arbitrary code.

## Transaction Isolation

Assessments are meant to read from a consistent database snapshot.

Why this matters:

Without consistent reads, a system could theoretically:

- resolve a rule
- then read a different status state
- then read a different tariff snapshot

within one logical assessment.

AIS avoids that conceptual drift by treating the assessment as one coherent decision context.

This matters for auditability because a replayable decision must rest on a stable data view.

## Why The Architecture Supports Trust

The architecture is designed to answer not only:

- what was the result?

but also:

- what product was identified?
- what rule was applied?
- what facts were evaluated?
- what failed?
- what source text supported the result?

That is why AIS is structured around:

- a canonical product spine
- deterministic execution
- explicit status handling
- separated service boundaries
- replayable audit records
- provenance-preserving legal storage

## Important Limitations

AIS is sound only within the scope of the data and rules loaded into it.

It does not claim:

- full Africa-wide coverage
- real-time legal updates
- automatic legal completeness beyond the loaded dataset
- substitution for customs rulings or legal advice

A technical evaluator should therefore judge AIS as:

- a deterministic, auditable compliance engine within a defined scope
- not a universal or self-updating legal oracle

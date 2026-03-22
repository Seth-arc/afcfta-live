# Data Provenance

This document explains how AIS supports verification.

It answers the question:

> Can I trace this decision back to real legal text and a known source?

The answer is yes, within the limits of the data loaded into the system.

AIS is designed so that:

- every important legal record comes from a known source
- every source is registered
- verbatim legal text is preserved
- every assessment can be replayed through an audit trail

## Source Registry

Every ingested source document is recorded in the **source registry**.

The source registry captures key provenance fields such as:

- authority tier
- source type
- issuing body
- jurisdiction scope
- effective date
- SHA-256 checksum
- supersedes and superseded-by links

Why this matters:

- users can identify where a rule or tariff line came from
- reviewers can verify that the stored source is the expected document
- the checksum provides a tamper-evident fingerprint of the ingested document

## Authority Tiers

AIS uses source authority tiers because not all documents carry the same legal weight.

The main tiers are:

### Binding

Examples:

- the Agreement
- Appendix IV

Role:

- highest authority for the substantive rules of origin

### Operational

Examples:

- tariff schedules
- circulars

Role:

- operational implementation material

### Interpretive

Examples:

- manuals
- guides

Role:

- explanatory or supporting reference

### Analytic

Examples:

- corridor data
- trade baselines

Role:

- contextual and analytic support, not primary legal authority

Higher tiers override lower ones.
This is essential for legal confidence and conflict resolution.

## Legal Provisions

AIS does not only store whole documents.
It also stores extracted **legal provisions**.

A legal provision links an individual clause or provision back to:

- its source document
- the article reference
- annex or section references where applicable
- the text itself

Why this matters:

- reviewers can inspect the clause-level source for a rule or requirement
- the system can preserve legal wording instead of paraphrasing away the legal meaning

## PSR Rules

Every product-specific rule in AIS traces back to a specific legal source row.

AIS preserves:

- the **verbatim legal text**
- the normalized rule components used for execution

This is critical.
It means the engine does not replace legal text with a black-box conclusion.
It keeps both:

- what the legal text said
- how AIS normalized it into executable components

For example, a `CTH` rule can be preserved as:

- original legal wording
- normalized pathway logic
- component-level structure such as tariff-shift comparisons

## The Audit Trail

Every stored assessment can be replayed through an audit trail.

That trail records:

- the original input facts
- the resolved HS6 product
- the resolved PSR rule
- pathway evaluation results
- general-rules results
- status overlay
- tariff outcome
- evidence readiness
- atomic checks showing what passed and what failed
- the final decision and confidence classification

Why this matters:

- a reviewer is not forced to trust a summary result
- the underlying checks can be inspected directly
- the final answer can be traced back through the whole decision path

## Immutability And Version Chains

AIS is designed around preservation, not replacement.

Raw source documents are not silently rewritten after ingestion.

Instead:

- documents are preserved
- superseded documents remain in the history
- version chains indicate what replaced what

Why this matters:

- reviewers can understand historical decisions in their original legal context
- changes over time do not erase the basis on which earlier decisions were made

## What This Means For Auditors And Legal Reviewers

AIS should be understood as a traceable legal-computing system, not just a yes/no engine.

A reviewer can ask:

- Which source document did this rule come from?
- What authority tier did that source have?
- What legal text was preserved?
- Which pathway was evaluated?
- Which check failed?
- What facts were missing?

Those questions are answerable because provenance is built into the data model and audit trail.

## Important Limitation

Provenance depends on what has actually been loaded into the system.

AIS can only trace back to:

- the sources that were ingested
- the provisions that were extracted
- the rules and operational materials present in the current dataset

So provenance is strong within the loaded scope, but it does not claim to represent every relevant legal source outside that scope.

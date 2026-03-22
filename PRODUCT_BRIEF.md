# AfCFTA Intelligence System (AIS)

## The Problem

The African Continental Free Trade Area is the world’s largest free trade area by country count, but using it in practice is difficult. There are thousands of product-specific rules, tariff schedules that vary by corridor and year, and many rules and operational conditions are still under negotiation or implementation. No existing tool in this project scope computes eligibility deterministically across these dimensions while preserving a full legal trail for review.

## The Solution

AIS is a deterministic compliance engine that answers a practical question: can this product qualify for AfCFTA preferential treatment? It does so by applying published rules against structured production facts and tracing every output to specific legal text. There is no AI interpretation, no probabilistic scoring, and no black-box result: each decision is auditable.

## Who It Serves

- **Customs officers** who need legally defensible, status-aware decision support
- **Policy analysts** who need structured visibility into rules, tariffs, evidence, and constraints
- **Exporters** who need pre-shipment validation before making a preferential origin claim

## What It Does Today

AIS v0.1 covers five West and Central African countries and provides:

- HS6 product resolution
- Rule lookup
- Tariff lookup
- Eligibility assessment
- Evidence readiness
- Decision audit trails

The current prototype focuses on a defined regional scope so that the logic, traceability, and auditability are correct before wider expansion.

## What Makes It Different

- **Deterministic**: the same inputs always produce the same outputs
- **Auditable**: every decision step is recorded and can be replayed
- **Status-aware**: the system never presents uncertain or still-negotiated rules as settled law
- **Traceable**: every result links back to source legal text, including references such as page-level provenance where available

## What’s Next

Next steps include ingestion of real AfCFTA source documents at scale, broader country and corridor coverage, and frontend interfaces tailored to officers, analysts, and exporters. The long-term goal is a legally traceable decision-support platform that can be used operationally across a much wider AfCFTA footprint.

## Contact / Next Steps

To be added.

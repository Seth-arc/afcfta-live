# AfCFTA Intelligence System (AIS)

**Deterministic RegTech decision-support platform for African Continental Free Trade Area compliance**

Version: v0.1 (Prototype) | Status: Active Development

---

## What This System Does

AIS is a deterministic trade-compliance engine that answers five questions for any HS6 product across supported AfCFTA corridors:

1. **Qualification** — Can this product qualify under AfCFTA preferential treatment?
2. **Pathway** — Under which legal rule (WO, CTH, VNM, VA, PROCESS)?
3. **Tariff** — What preferential and base rates apply?
4. **Evidence** — What documentation is required to prove origin?
5. **Constraints** — What legal or status limitations exist?

Every output is structured, auditable, and reproducible. There are no probabilistic scores, no silent inference, and no RAG-only answers.

---

## Who It Serves

| Persona | Primary Need | Output Mode |
|---|---|---|
| **Competent Authority Officer** | Legal defensibility, audit trails | Structured + evidentiary, case-by-case |
| **Policy Analyst** | System-level insight, scenario modeling | Rule + tariff + status overlays |
| **Exporter** | Actionable clarity, pre-shipment validation | Pass/fail + checklist |

---

## v0.1 Scope (Locked)

**Countries:** Nigeria, Ghana, Cote d'Ivoire, Senegal, Cameroon

**Product Resolution:** HS6 canonical only (HS8/10 stored but not computed)

**Capabilities:** Rule lookup, tariff lookup, eligibility engine, evidence readiness, status-aware outputs

**Success Criteria:** Evaluate 5+ HS6 products end-to-end across 2+ corridors (e.g. GHA-NGA, CMR-NGA), producing eligibility decisions, tariff outcomes, failure reasoning, and evidence checklists — including graceful handling of missing facts, ambiguous rules, and status variability.

---

## Architecture Overview

The system follows a layered architecture with seven data layers and a service orchestration tier, all joined on a single canonical spine: `hs_version + hs6_id`.

### Data Layers

| Layer | Key Tables | Purpose |
|---|---|---|
| L1 — Backbone | `hs6_product`, `hs_code_alias`, `hs_version_crosswalk` | Canonical product spine |
| L2 — Rules | `psr_rule`, `psr_rule_component`, `eligibility_rule_pathway`, `hs6_psr_applicability` | Appendix IV normalized rules |
| L3 — Tariffs | `tariff_schedule_header`, `tariff_schedule_line`, `tariff_schedule_rate_by_year` | Schedule rates by corridor and year |
| L4 — Status | `status_assertion`, `transition_clause` | Pending/provisional/agreed tracking |
| L5 — Evidence | `evidence_requirement`, `verification_question`, `document_readiness_template` | Documentation requirements |
| L6 — Decision | `case_file`, `case_input_fact`, `case_failure_mode`, `case_counterfactual` | Case assessment storage |
| L7 — Intelligence | `corridor_profile`, `alert_event` | Corridor risk and alerting |

### Core Services

The orchestration layer coordinates these services in a strict execution order:

```
classification_service        — HS6 resolution
rule_resolution_service       — PSR lookup + pathway expansion
tariff_resolution_service     — Corridor-aware rate retrieval
status_service                — Constraint and status overlay
evidence_service              — Document requirement generation
eligibility_service           — Deterministic pass/fail evaluation
expression_evaluator          — Boolean expression execution
general_origin_rules_service  — Cumulation, direct transport, insufficient operations
fact_normalization_service    — Input fact standardization
audit_service                 — Decision trace logging
```

### Deterministic Engine Execution Order

```
1. Resolve HS6
2. Fetch PSR(s)
3. Expand pathways (AND/OR)
4. Evaluate expressions
5. Apply general rules (insufficient operations, cumulation, direct transport)
6. Apply status constraints
7. Compute tariff
8. Generate evidence requirements
```

### Join Principle

All operational joins resolve through `hs_version + hs6_id`. There is no join on raw HS text or product descriptions. The HS6 layer is the single stable spine for the entire system.

---

## Tech Stack

| Component | Technology |
|---|---|
| API Framework | FastAPI (Python) |
| Database | PostgreSQL 15+ |
| Embeddings | pgvector |
| Full-text Search | Postgres full-text / OpenSearch |
| Object Storage | Raw source documents |
| Models | Pydantic (request/response schemas) |
| Auth | API key / JWT (v0.1 minimal) |

---

## Repository Structure

```
afcfta-intelligence/
├── app/
│   ├── main.py                    # FastAPI application entry
│   ├── config.py                  # Environment and settings
│   ├── db/
│   │   ├── base.py                # SQLAlchemy base
│   │   ├── session.py             # DB session management
│   │   └── models/                # ORM models (hs, rules, tariffs, status, evidence, cases, evaluations)
│   ├── schemas/                   # Pydantic request/response models
│   ├── api/
│   │   ├── deps.py                # Dependency injection
│   │   ├── router.py              # Root router
│   │   └── v1/                    # Versioned route handlers
│   ├── services/                  # Business logic (eligibility, rules, tariffs, etc.)
│   └── repositories/              # Data access layer
├── data/
│   ├── raw/                       # Tiered source documents
│   │   ├── tier1_binding/         # Agreement, annexes, appendices, schedules
│   │   ├── tier2_operational/     # e-Tariff Book, circulars, guidance
│   │   ├── tier3_support/         # Manuals, guides
│   │   └── tier4_analytics/       # Corridor metrics, trade baselines
│   ├── staged/                    # Extracted text, tables, OCR, metadata
│   └── processed/                 # Chunks, entities, rules, tariffs, statuses
├── schemas/                       # SQL DDL, JSON schemas, API contracts
├── pipelines/                     # Acquire, parse, normalize, enrich, assess, index, alert, QA
├── eval/                          # Gold sets, benchmarks, regression tests
└── docs/                          # Developer documentation (read in phase order)
    ├── README.md                  # This file — start here
    ├── phase1_product_context/    # PRD, v1_scope
    ├── phase2_architecture/       # Implementation_Blueprint, Canonical_Corpus, diagrams
    └── phase3_implementation/     # Concrete_Contract, Join_Strategy, FastAPI_layout
```

---

## API Endpoints (v1)

### Rule Lookup

```
GET /v1/rules/{hs6}
```

Returns PSR pathways (WO/VNM/CTH/etc.), thresholds, verbatim legal text, and rule status for a given HS6 code.

### Tariff Query

```
GET /v1/tariffs?exporter={country}&importer={country}&hs6={code}&year={year}
```

Returns base rate, preferential rate, staging year, and tariff status for a specific trade corridor.

### Case Creation

```
POST /v1/cases
```

Creates a new assessment case with input facts for eligibility evaluation.

### Eligibility Assessment

```
POST /v1/assessments
```

Executes deterministic eligibility evaluation. Returns eligible/not-eligible, pathway used, failure codes, missing facts, evidence required, and confidence class.

### Sample Response

```json
{
  "hs6_code": "110311",
  "eligible": true,
  "pathway_used": "CTH",
  "rule_status": "agreed",
  "tariff_outcome": {
    "preferential_rate": 0,
    "base_rate": 15,
    "status": "provisional"
  },
  "failures": [],
  "missing_facts": [],
  "evidence_required": ["certificate_of_origin"],
  "confidence_class": "complete"
}
```

Every response includes `rule_status`, `tariff_status`, `legal_basis`, and `confidence_class` (a measure of structural completeness, not probability).

---

## Documentation Index

Read these in order. Each document assumes context from the ones before it.

### Phase 1 — Why and What (Product Context)

Establishes what the system does, who it serves, and what is in scope for v0.1. Read this before touching any architecture or code.

| Order | Document | What It Unlocks |
|---|---|---|
| 1 | `phase1_product_context/PRD.md` | Product purpose, three user personas, five core capabilities, non-negotiables around deterministic output |
| 2 | `phase1_product_context/v1_scope.md` | What is in/out for v0.1, locked countries, success criteria, the Cameroon rationale, allowed simplifications |

### Phase 2 — How It Fits Together (Architecture)

Maps the product vision to technical structure — layers, modules, data sources, and governance. Read this before looking at any schema or code.

| Order | Document | What It Unlocks |
|---|---|---|
| 3 | `phase2_architecture/Implementation_Blueprint.md` | Five-layer architecture, capability modules, source tiers, evaluation framework, governance model, deployment stack |
| 4 | `phase2_architecture/Canonical_Corpus.md` | Exact source documents to ingest, authority tier per document, mapping of sources to use cases |

### Phase 3 — How to Build It (Implementation)

Concrete schema, join logic, query patterns, and codebase structure. Each document builds on the one before it.

| Order | Document | What It Unlocks |
|---|---|---|
| 5 | `phase3_implementation/Concrete_Contract.md` | PostgreSQL DDL for all core tables, column types, enums, foreign keys, REST API response contracts |
| 6 | `phase3_implementation/Join_Strategy.md` | How every table connects through the HS6 spine, inheritance resolution, production query patterns, execution pseudocode |
| 7 | `phase3_implementation/FastAPI_layout.md` | Repo structure, route handlers, Pydantic models, service boundaries, repository pattern |

### Architecture Diagrams

Reference these alongside the Phase 2 documents.

| Diagram | Description |
|---|---|
| `phase2_architecture/system_architecture_diagram_for_the_AfCFTA_Intelligence_System.png` | Full system architecture — users through application layer, orchestration, services, and data stores |
| `phase2_architecture/Layered_view.png` | Layered architecture view |
| `phase2_architecture/Runtime_request_flow.png` | Runtime request flow through the deterministic engine |

---

## Key Design Decisions

**Deterministic over probabilistic.** The eligibility engine executes boolean expressions against structured rules. There is no ML scoring or confidence estimation — outputs are pass/fail with explicit failure codes.

**HS6 as canonical spine.** Every table in the system joins through `hs_version + hs6_id`. This eliminates ambiguity from text-based matching and ensures a single source of truth for product resolution.

**Status is mandatory, not optional.** Every output carries `rule_status`, `tariff_status`, and `confidence_class`. The system never presents a provisional rule as settled law.

**Verbatim legal text preserved.** The parser layer normalizes rules into executable components but always retains the original legal text with full provenance. Nothing is paraphrased or inferred.

**PSR rules and general rules are separate engine layers.** Product-specific rules (Appendix IV) and general origin rules (cumulation, direct transport, insufficient operations) are evaluated independently and then combined. This prevents false qualification.

---

## Derived Variables

The eligibility engine computes two core derived variables from input facts:

```
vnom_percent = non_originating / ex_works * 100
va_percent   = (ex_works - non_originating) / ex_works * 100
```

These feed into VNM and VA pathway boolean expressions during eligibility evaluation.

---

## Source Authority Tiers

The system enforces strict source precedence. Higher tiers override lower tiers in all conflict resolution.

| Tier | Source Type | Role |
|---|---|---|
| 1 | Agreement + Appendix IV | Binding legal authority |
| 2 | Tariff schedules, circulars | Operational reference |
| 3 | Manuals, guides | Interpretive support |
| 4 | Corridor data, trade baselines | Analytic enrichment |

---

## What Is NOT in v0.1

- HS8/10 computation
- ML or probabilistic scoring
- Automatic HS classification
- Full Africa coverage (5 countries only)
- Real-time legal update feeds

**Allowed simplifications:** Partial tariff schedules are acceptable if flagged. Missing data produces explicit flags rather than silent gaps. Evidence requirements are template-based. Corridor intelligence is coarse-grained.

---

## Roadmap

**v0.2** — HS8/10 expansion, additional countries, cumulation intelligence

**v0.3** — Trade anomaly detection (CTAD integration), corridor risk scoring, predictive compliance

**v1.0** — Full Africa coverage, API monetization layer, embedded compliance engine for ERP/logistics

---

## Strategic Context

The competitive moat is not the rules, tariffs, or documents themselves — those are commoditized. The moat is the **execution layer + structured normalization + deterministic audit trail**. This system proves that trade compliance can be computed rather than interpreted, and that eligibility decisions can be simulated before export.

The Cameroon inclusion (replacing Kenya in v0.1) is deliberate: it introduces ECCAS/CEMAC logic, Francophone legal parsing, weaker digitization stress-testing, and the high-friction Nigeria-Cameroon corridor — all of which are more representative of real AfCFTA usage than clean East African systems.

Developer:
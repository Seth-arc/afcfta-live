# AfCFTA Intelligence System (AIS)

Deterministic trade-compliance engine for the African Continental Free Trade Area.

## What It Does

AIS answers five practical questions for a product moving across a supported AfCFTA corridor:

- Does this product qualify for AfCFTA preferential treatment?
- Which legal pathway applies, such as `WO`, `CTH`, `VNM`, `VA`, or `PROCESS`?
- What preferential and base tariff rates apply?
- What evidence is normally required to support the claim?
- What legal or operational constraints affect the result?

## Why It Exists

AfCFTA is the world's largest free trade area by country count. Using it in practice is hard because product rules, tariff schedules, status conditions, and evidence requirements must all line up. AIS computes eligibility deterministically and traces every result to specific legal text.

## Current Status

`v0.1 Prototype`

- 5 countries in scope: Nigeria, Ghana, Cote d'Ivoire, Senegal, Cameroon
- HS6 resolution
- Rule lookup
- Tariff lookup
- Direct and case-backed eligibility assessment
- Evidence readiness
- Status-aware outputs with snapshot-aligned rule and tariff resolution
- Full audit trail, including latest-evaluation retrieval by case
- Source and legal provision lookup APIs
- Corridor profile and alert listing APIs
- Repeatable parser promotion runbook for Appendix IV artifacts
- Deterministic seed slice spanning 8 HS6 products across 4 supported corridors

## Product Surface

User-facing capabilities exposed by the API:

- rules and tariff lookup
- direct assessments and assess-by-case execution
- evidence readiness and decision-time readiness scoring
- audit replay by evaluation or by case
- provenance lookup for sources and legal provisions
- corridor intelligence profiles and alert listing

Internal infrastructure that supports those capabilities but is not itself a user API:

- repositories and database models
- parser artifact generation and promotion scripts
- seed-data and operator workflow scripts
- Alembic migrations and development-only fixtures

## Who It Serves

| Persona | What AIS helps them do |
|---|---|
| Officer | Review a claim consistently, inspect the rule path, and replay the audit trail |
| Analyst | Compare corridor conditions, rules, statuses, and evidence requirements |
| Exporter | Check likely qualification early and see what facts and documents are needed |

## Quick Start

```bash
git clone <repo-url>
cd afcfta-live
docker compose up -d
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python scripts/seed_data.py
python -m uvicorn app.main:app --reload
```

First working API call:

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

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Liveness check |
| `GET` | `/api/v1/rules/{hs6}` | Resolve the governing PSR rule bundle |
| `GET` | `/api/v1/tariffs` | Resolve tariff outcome for a corridor, product, and year |
| `POST` | `/api/v1/cases` | Create a case and store submitted production facts |
| `GET` | `/api/v1/cases/{case_id}` | Retrieve a case and its stored facts |
| `POST` | `/api/v1/assessments` | Run the full eligibility engine |
| `POST` | `/api/v1/assessments/cases/{case_id}` | Run an assessment using facts already stored on a case |
| `POST` | `/api/v1/evidence/readiness` | Check document readiness for a rule or pathway |
| `GET` | `/api/v1/audit/evaluations/{evaluation_id}` | Retrieve a full decision trace |
| `GET` | `/api/v1/audit/cases/{case_id}/evaluations` | List evaluations stored for a case |
| `GET` | `/api/v1/audit/cases/{case_id}/latest` | Retrieve the latest persisted decision trace for a case |
| `GET` | `/api/v1/sources` | List provenance source records |
| `GET` | `/api/v1/sources/{source_id}` | Retrieve one provenance source record |
| `GET` | `/api/v1/provisions` | List legal provisions |
| `GET` | `/api/v1/provisions/{provision_id}` | Retrieve one legal provision |
| `GET` | `/api/v1/intelligence/corridors/{exporter}/{importer}` | Retrieve an active corridor profile |
| `GET` | `/api/v1/intelligence/alerts` | List alerts by status, severity, or entity scope |

## Architecture

AIS uses a layered architecture: thin API handlers, business logic in services, SQL in repositories, and explicit database models and schemas underneath. Every operational layer resolves through a canonical HS6 product spine, which eliminates text-matching ambiguity across rules, tariffs, statuses, and evidence. The engine is deterministic boolean execution, not ML scoring, so the same inputs produce the same outputs.

More detail: [docs/concepts/architecture-overview.md](docs/concepts/architecture-overview.md)

For operator-facing parser promotion steps, see [docs/dev/parser_promotion_workflow.md](docs/dev/parser_promotion_workflow.md).

## Documentation

| Area | Location |
|---|---|
| User Guide | [docs/user-guide/](docs/user-guide/) |
| API Reference | [docs/api/](docs/api/) |
| Concepts | [docs/concepts/](docs/concepts/) |
| Developer Guide | [docs/dev/](docs/dev/) |
| Product Brief | [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |

## What This Is Not

AIS is not legal advice, not a customs declaration system, not probabilistic scoring, and not AI-generated legal interpretation. It executes published rules deterministically, preserves the underlying legal text, and shows its work through structured outputs and audit traces. Users must still verify important decisions with their competent authority.

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

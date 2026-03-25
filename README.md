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

Before starting the API locally, create `.env` from `.env.example` and set at least the required runtime variables:

```bash
cp .env.example .env
```

Minimum local values:

```env
DATABASE_URL=postgresql+asyncpg://afcfta:afcfta_dev@localhost:5432/afcfta
DATABASE_URL_SYNC=postgresql://afcfta:afcfta_dev@localhost:5432/afcfta
API_AUTH_KEY=replace-with-a-local-dev-secret
```

Production container deployment uses the checked-in [Dockerfile](Dockerfile) and [docker-compose.prod.yml](docker-compose.prod.yml). The runtime container will exit immediately if `DATABASE_URL`, `API_AUTH_KEY`, or `ENV` are missing.

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
    "existing_documents": [
      "certificate_of_origin",
      "bill_of_materials",
      "invoice"
    ],
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

Contract compatibility note:

- `existing_documents` is the canonical document-inventory field for assessment and evidence-readiness requests.
- `submitted_documents` is accepted as an input-only alias for backward compatibility.
- Responses and documentation always use the canonical field name `existing_documents`.
- Assessment endpoints also return replay identifiers in response headers: `X-AIS-Case-Id`, `X-AIS-Evaluation-Id`, and `X-AIS-Audit-URL`.
- `POST /api/v1/assessments` auto-creates a submitted case when `case_id` is omitted so every interface-triggered assessment remains replayable.

Assessment responses are frozen to this field set:

- `hs6_code`
- `eligible`
- `pathway_used`
- `rule_status`
- `tariff_outcome`
- `failures`
- `missing_facts`
- `evidence_required`
- `missing_evidence`
- `readiness_score`
- `completeness_ratio`
- `confidence_class`

Audit replay responses are frozen to this top-level field set:

- `evaluation`
- `case`
- `original_input_facts`
- `hs6_resolved`
- `psr_rule`
- `pathway_evaluations`
- `general_rules_results`
- `status_overlay`
- `tariff_outcome`
- `evidence_readiness`
- `atomic_checks`
- `final_decision`

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Liveness check |
| `GET` | `/api/v1/health/ready` | Readiness check for database connectivity |
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

Runtime logging is configured through `LOG_LEVEL`, `LOG_FORMAT`, `LOG_REQUESTS_ENABLED`, and `LOG_DISABLE_UVICORN_ACCESS_LOG`. The API emits structured request logs with stable correlation fields such as `request_id`, `authenticated_principal`, `method`, `route`, `status_code`, and `latency_ms`, while assessment decisions continue to emit a separate `eligibility_assessment` audit event.

## Environment Variables

The checked-in [`.env.example`](.env.example) is the canonical environment-variable template.

Required runtime settings:

- `DATABASE_URL`
- `API_AUTH_KEY`

Required in containerized production deployments:

- `DATABASE_URL`
- `API_AUTH_KEY`
- `ENV`
- `POSTGRES_PASSWORD` when using the bundled `db` service from [docker-compose.prod.yml](docker-compose.prod.yml)

When `POSTGRES_PASSWORD` contains reserved URL characters such as `%`, `@`, `:`, `/`, or `;`, keep `POSTGRES_PASSWORD` as the raw password but URL-encode that same password inside `DATABASE_URL` and `DATABASE_URL_SYNC`.

Optional but recommended outside the app server process:

- `DATABASE_URL_SYNC` for Alembic and sync tooling
- `ENV` to distinguish `development`, `staging`, and `production`
- the DB timeout controls
- the rate-limit controls
- the logging controls
- optional external error-tracking settings

Variables are grouped by concern in [`.env.example`](.env.example):

- application and deployment
- database
- API authentication
- rate limiting
- logging
- optional external error tracking

Production timeout and error-tracking configuration is intentionally minimal:

- In-process DB safeguards: `DB_CONNECT_TIMEOUT_SECONDS`, `DB_COMMAND_TIMEOUT_SECONDS`, `DB_POOL_TIMEOUT_SECONDS`, `DB_STATEMENT_TIMEOUT_MS`, and `DB_LOCK_TIMEOUT_MS` bound connection acquisition, driver command time, server-side statement time, and lock wait time.
- Optional external error tracking: `ERROR_TRACKING_BACKEND=none|sentry`, `SENTRY_DSN`, and `SENTRY_TRACES_SAMPLE_RATE` enable a Sentry hook only when explicitly configured and the dependency is installed.
- Structured API error responses remain in-process and always active; optional error tracking only mirrors unexpected exceptions to external infrastructure and does not replace the existing JSON error envelope.

What still requires external infrastructure:

- Error aggregation, retention, alerting, and dashboards require a configured external service such as Sentry.
- Long-term latency metrics, failure-rate alerting, and operator notifications still require metrics and monitoring infrastructure outside the application process.

Development-only defaults to review before production:

- `ENV=development`
- `LOG_LEVEL=INFO` is safe, but `DEBUG` should remain local-only
- the default rate limits and timeout values are conservative starting points, not production capacity planning
- `ERROR_TRACKING_BACKEND=none` disables external aggregation until infrastructure is intentionally configured

## Production Containers

Build the production image:

```bash
docker build -t afcfta-intelligence:prod .
```

Create a dedicated production environment file before starting the production compose stack:

```bash
cp ./.env.example ./.env.prod
```

Set at least these values in `./.env.prod`:

```env
ENV=production
DATABASE_URL=postgresql+asyncpg://afcfta:<replace-password>@db:5432/afcfta
API_AUTH_KEY=<replace-with-a-long-random-secret>
POSTGRES_PASSWORD=<replace-with-a-database-password>
```

Start the production-oriented stack:

```bash
docker compose -f ./docker-compose.prod.yml up --build -d
```

The runtime container starts the API with:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2}
```

Production compose characteristics:

- no source-code bind mounts
- a multi-stage application image rather than an ad hoc dev container
- readiness health checks against `/api/v1/health/ready`
- restart policies for long-running services
- explicit required environment-variable checks for production startup
- container runtime settings are loaded from `./.env.prod`, preventing exported host-shell `DATABASE_URL` values from silently overriding the production DSN

The production health check uses the readiness endpoint, not just liveness, so database connectivity must be healthy before the container is considered ready.

If the API container exits immediately, that means `./.env.prod` is absent or incomplete and the runtime fail-fast check rejected missing mandatory settings such as `API_AUTH_KEY`, `DATABASE_URL`, or `ENV`.

## Continuous Integration

The repository CI workflow lives at [`.github/workflows/ci.yml`](.github/workflows/ci.yml) and runs four incremental stages:

- lint via `ruff`
- unit tests with coverage report
- integration tests against PostgreSQL with migrations, seed data, and enforced coverage threshold
- production Docker image build validation

CI report locations:

| Artifact name | File | Contents |
|---|---|---|
| `unit-test-report` | `artifacts/unit-tests.xml` | JUnit XML for unit tests |
| `unit-coverage-report` | `artifacts/coverage.xml` | Cobertura XML coverage for unit run |
| `integration-test-report` | `artifacts/integration-tests.xml` | JUnit XML for integration tests |
| `integration-coverage-report` | `artifacts/coverage.xml` | Cobertura XML coverage for full-stack run |

The integration job enforces a **75 % minimum coverage threshold** against the `app` source tree.
This is the measured first-pass floor: unit tests alone reach 84 %, and 75 % leaves headroom
for DB-dependent repository paths only reachable with a live stack.
See [docs/dev/testing.md](docs/dev/testing.md) for the explicit coverage commands and the list of
code areas that need the next wave of tests.

## Load Testing

A lightweight load test harness lives in [`tests/load/`](tests/load/).
It requires no special tooling — only a running stack and `httpx` (already a dev dependency).

```bash
export RATE_LIMIT_ENABLED=false   # required — default limit is 10 req/60 s
export AIS_API_KEY=your-api-key

python tests/load/run_load_test.py --concurrency 50 --requests 200
```

The harness sends 200 requests across 5 deterministic seeded payloads (GHA→NGA CTH,
CMR→NGA VNM, CIV→NGA WO, SEN→NGA VNM, CMR→NGA VNM-fail) with 50 concurrent workers.
It captures success rate, throughput (req/s), and latency percentiles (p50/p75/p95/p99)
for successful requests only.

Output: human-readable terminal summary + `artifacts/load-report.json`.
Exit code 1 if success rate falls below `--fail-under` (default 95 %).

See [docs/dev/testing.md](docs/dev/testing.md) for full documentation including
prerequisites, interpretation guidance, and the gap list for true performance infrastructure.

## Architecture

AIS uses a layered architecture: thin API handlers, business logic in services, SQL in repositories, and explicit database models and schemas underneath. Every operational layer resolves through a canonical HS6 product spine, which eliminates text-matching ambiguity across rules, tariffs, statuses, and evidence. The engine is deterministic boolean execution, not ML scoring, so the same inputs produce the same outputs.

More detail: [docs/concepts/architecture-overview.md](docs/concepts/architecture-overview.md)

For operator-facing parser promotion steps, see [docs/dev/parser_promotion_workflow.md](docs/dev/parser_promotion_workflow.md).

### NIM Orchestration Boundary

When a conversational assistant layer (NIM) is added on top of this engine, it must respect a hard boundary:

- NIM may parse natural-language queries, ask clarifying questions, and explain engine outputs.
- NIM must never decide eligibility, override deterministic output fields, or fabricate legal facts.
- Every assessment triggered through the assistant path must produce a persisted, replayable record. The engine auto-creates a case when `case_id` is omitted. The `audit_persisted` field in the assessment response confirms the write succeeded; the assistant must not present the result as legally recorded when `audit_persisted` is `false`.
- NIM-only metadata such as parse confidence or session state must be stripped before the request reaches the deterministic engine.
- The canonical document-inventory field is `existing_documents`. The older alias `submitted_documents` is accepted on input only for backward compatibility and must not appear in assistant schemas or response contracts.

## Documentation

| Area | Location |
|---|---|
| User Guide | [docs/user-guide/](docs/user-guide/) |
| API Reference | [docs/api/](docs/api/) |
| Concepts | [docs/concepts/](docs/concepts/) |
| Developer Guide | [docs/dev/](docs/dev/) |
| Production Runbook | [docs/dev/production_runbook.md](docs/dev/production_runbook.md) |
| Parser Promotion | [docs/dev/parser_promotion_workflow.md](docs/dev/parser_promotion_workflow.md) |
| Product Brief | [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |

## What This Is Not

AIS is not legal advice, not a customs declaration system, not probabilistic scoring, and not AI-generated legal interpretation. It executes published rules deterministically, preserves the underlying legal text, and shows its work through structured outputs and audit traces. Users must still verify important decisions with their competent authority.

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

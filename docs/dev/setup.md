# Development Setup

This guide gets a new developer from zero to a running AIS instance in about 15 minutes.

## Prerequisites

Install these first:

- Python 3.11+
- Docker Desktop
- Git

Windows notes:

- Prefer Git Bash or WSL for shell commands.
- Use the `python -m` prefix for Python tools such as `pytest`, `uvicorn`, and `alembic`.
- If `DATABASE_URL` is already set in your system environment, it overrides `.env`.
- If a synchronous PostgreSQL driver is missing for local tooling, you may need:

```bash
python -m pip install psycopg2-binary
```

## 1. Clone The Repository

```bash
git clone <your-repo-url>
cd afcfta-live
```

## 2. Start PostgreSQL

This repo uses Docker Compose for local infrastructure.

```bash
docker compose up -d
```

This local compose file remains development-oriented and only starts PostgreSQL with a local named volume. Production uses [docker-compose.prod.yml](../../docker-compose.prod.yml), which builds the API image, removes development bind-mount assumptions, and adds service health checks.

## 3. Create `.env` From `.env.example`

Copy the example file:

```bash
cp .env.example .env
```

The application settings loaded by `app/config.py` are:

- Database
  - `DATABASE_URL` required
  - `DATABASE_URL_SYNC` optional for the API process but recommended for local Alembic and sync tooling
  - `DB_CONNECT_TIMEOUT_SECONDS` optional
  - `DB_COMMAND_TIMEOUT_SECONDS` optional
  - `DB_POOL_TIMEOUT_SECONDS` optional
  - `DB_STATEMENT_TIMEOUT_MS` optional
  - `DB_LOCK_TIMEOUT_MS` optional
- API authentication
  - `API_AUTH_KEY` required
  - `API_AUTH_PRINCIPAL` optional
  - `API_AUTH_HEADER_NAME` optional
- Rate limiting
  - `RATE_LIMIT_ENABLED` optional
  - `RATE_LIMIT_WINDOW_SECONDS` optional
  - `RATE_LIMIT_DEFAULT_MAX_REQUESTS` optional
  - `RATE_LIMIT_ASSESSMENTS_MAX_REQUESTS` optional
- Deployment/runtime mode
  - `ENV` optional locally, required in staging and production for clean environment labeling
  - `APP_TITLE` optional
  - `APP_VERSION` optional
- Logging
  - `LOG_LEVEL` optional
  - `LOG_FORMAT` optional
  - `LOG_REQUESTS_ENABLED` optional
  - `LOG_DISABLE_UVICORN_ACCESS_LOG` optional
- Optional external error tracking
  - `ERROR_TRACKING_BACKEND` optional
  - `SENTRY_DSN` optional
  - `SENTRY_TRACES_SAMPLE_RATE` optional

A working local example looks like this:

```env
DATABASE_URL=postgresql+asyncpg://afcfta:afcfta_dev@localhost:5432/afcfta
DATABASE_URL_SYNC=postgresql://afcfta:afcfta_dev@localhost:5432/afcfta
API_AUTH_KEY=replace-with-a-local-dev-secret
ENV=development
LOG_LEVEL=INFO
APP_TITLE=AfCFTA Intelligence API
APP_VERSION=0.1.0
```

Local development keeps secrets out of the repository by using `.env`, which is ignored by git, while `.env.example` contains only safe placeholders.

Mandatory versus optional guidance:

- Mandatory for local API startup: `DATABASE_URL`, `API_AUTH_KEY`
- Mandatory for production: `DATABASE_URL`, `API_AUTH_KEY`, and `ENV`
- Optional local conveniences: `DATABASE_URL_SYNC`, logging controls, rate-limit overrides, and error-tracking settings
- Optional production integrations: Sentry-related settings remain optional unless external error aggregation is part of the deployment

## CORS And Browser Clients

Before any Decision Renderer or other browser-based trader UI development begins, add the staging and production Decision Renderer origins to `CORS_ALLOW_ORIGINS`. Use the assigned browser origins in the format `https://decision-renderer-staging.afcfta.example` and `https://decision-renderer.afcfta.example`; do not rely on `http://localhost:3000` beyond local placeholder or development use.

For the full setting contract and example values, see [app/config.py](../../app/config.py) and [.env.example](../../.env.example).

## Metrics And Observability

Prometheus scraping is disabled by default. Set `METRICS_ENABLED=true` to expose the scrape endpoint at `/metrics` on the root app path. When the flag is left at `false`, `/metrics` is not mounted and returns `404`.

The metrics endpoint is intended for pull-based collectors such as Prometheus or Grafana Agent. It is intentionally unauthenticated, so expose it only on trusted internal network paths or behind infrastructure controls. The environment setting is defined in [app/config.py](../../app/config.py), and the example env block lives in [.env.example](../../.env.example).

Recommended Prometheus scrape configuration:

```yaml
scrape_configs:
  - job_name: afcfta-intelligence-api
    metrics_path: /metrics
    static_configs:
      - targets:
          - api.internal.afcfta.example:8000
```

## 4. Install Dependencies

Use an editable install with dev dependencies:

```bash
python -m pip install -e ".[dev]"
```

If `setuptools` complains about multiple packages during editable install,
add this to `pyproject.toml`:

```toml
[tool.setuptools.packages.find]
include = ["app*"]
```

## 5. Run Migrations

```bash
python -m alembic upgrade head
```

## 6. Seed The Database

The seed process loads the v0.1 reference dataset, including:

- source documents
- legal provisions
- HS6 products
- rules and pathways
- tariff data
- statuses
- evidence requirements
- corridor profiles

Run:

```bash
python scripts/seed_data.py
```

## 7. Run Tests

```bash
python -m pytest tests/ -v
```

## 8. Start The Server

```bash
python -m uvicorn app.main:app --reload
```

## Production Containers

Use the production artifacts when you want a containerized runtime closer to staging or production:

```bash
docker build -t afcfta-intelligence:prod .
cp ./.env.example ./.env.prod
```

Populate `./.env.prod` with at least:

```env
ENV=production
DATABASE_URL=postgresql+asyncpg://afcfta:<replace-password>@db:5432/afcfta
API_AUTH_KEY=<replace-with-a-long-random-secret>
POSTGRES_PASSWORD=<replace-with-a-database-password>
```

That `DATABASE_URL` example is for `docker-compose.prod.yml` only. The hostname
`db` is the Compose service name provided by that stack.

If the database password includes reserved URL characters such as `%`, `@`, `:`, `/`, or `;`, use the raw value in `POSTGRES_PASSWORD` and the URL-encoded form of that same password in `DATABASE_URL` and `DATABASE_URL_SYNC`.

Then start the production stack with the explicit env file:

```bash
docker compose -f ./docker-compose.prod.yml up --build -d
```

The production compose file reads container runtime variables directly from `./.env.prod`, which avoids accidentally leaking a host-shell `DATABASE_URL` like `localhost` into the API container.

Required production environment variables for the API container:

- `DATABASE_URL`
- `API_AUTH_KEY`
- `ENV`

Required if you use the bundled PostgreSQL service in `docker-compose.prod.yml`:

- `POSTGRES_PASSWORD`

Optional production overrides:

- `DATABASE_URL_SYNC`
- DB timeout controls
- `CACHE_STATIC_LOOKUPS` for local no-cache baselines or strict promotion windows
- `CACHE_TTL_SECONDS` if you need a TTL other than the 5-minute default
- rate-limit controls
- logging controls
- `ERROR_TRACKING_BACKEND`, `SENTRY_DSN`, and `SENTRY_TRACES_SAMPLE_RATE`
- `UVICORN_WORKERS` for direct `docker run` deployments; `docker-compose.prod.yml` pins `--workers 1`

`docker-compose.prod.yml` is the canonical production entrypoint. It overrides the
image command and keeps `--workers 1` explicit until Redis-backed rate limiting
is configured.

The image-level production command is:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:?UVICORN_WORKERS must be set explicitly — do not rely on the default. Set 1 for InMemoryRateLimiter deployments, higher only after REDIS_URL is configured}
```

The container fails fast if `DATABASE_URL`, `API_AUTH_KEY`, or `ENV` are missing, and its health check targets `/api/v1/health/ready` so the process is not marked healthy until database connectivity is working.

If the API container exits before serving traffic, that is expected fail-fast behavior for an incomplete production env file.

For non-compose deployments, set `UVICORN_WORKERS` explicitly on `docker run`:

```bash
docker run --rm -p 8000:8000 --env-file ./.env.prod -e UVICORN_WORKERS=1 afcfta-intelligence:prod
```

Before running that command, update `./.env.prod` for the standalone case:

- `docker-compose.prod.yml`: `DATABASE_URL=postgresql+asyncpg://afcfta:<replace-password>@db:5432/afcfta`
- direct `docker run`: `DATABASE_URL=postgresql+asyncpg://afcfta:<replace-password>@<reachable-db-host>:5432/afcfta`

For direct `docker run`, `<reachable-db-host>` must be a database address that
the standalone API container can actually resolve and reach. A hostname like
`db` works in `docker-compose.prod.yml` because Compose provides that service DNS
name; it does not work automatically for a standalone container.

## Parser Promotion Cache Invalidation

Static reference caching is enabled by default in production
(`CACHE_STATIC_LOOKUPS=true`) with a 5-minute TTL
(`CACHE_TTL_SECONDS=300`). Follow [parser_promotion_workflow.md](./parser_promotion_workflow.md)
for the staged-to-operational promotion itself, then invalidate API worker caches
explicitly using one of these two approaches:

1. Preferred zero-downtime path: complete the parser promotion, validate the DB state,
   then perform a rolling restart of API workers. This evicts all in-process cached HS,
   PSR, and tariff lookups immediately.
2. Strict immediate-consistency path: set `CACHE_STATIC_LOOKUPS=false`, restart API
   workers before the promotion window, complete the promotion and validation with the
   cache disabled, then optionally set `CACHE_STATIC_LOOKUPS=true` again and perform
   another rolling restart after the promotion is confirmed.

If a restart window is missed, the TTL caps stale static-reference reads at 5 minutes,
but operator guidance should still treat a rolling restart as the standard post-promotion
step.

## 9. Verify The API Is Running

```bash
curl http://localhost:8000/api/v1/health
```

Expected response:

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

## Troubleshooting

## Docker Is Running But The App Cannot Connect

Check:

- PostgreSQL is actually up: `docker compose ps`
- `DATABASE_URL` and `DATABASE_URL_SYNC` point to the same local database you started
- you do not have conflicting database environment variables in your shell or system settings

## `.env` Changes Are Ignored

Most often this means one of these:

- the variable is already exported in your shell
- the variable exists in the Windows system environment

The runtime environment takes precedence over `.env`.

## Alembic Or Scripts Fail On Windows

Use the module form instead of bare command names:

```bash
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
python -m pytest tests/ -v
```

## First-Day Sanity Check

If all of the following work, your local setup is in a good state:

1. `docker compose up -d`
2. `python -m alembic upgrade head`
3. `python scripts/seed_data.py`
4. `python -m pytest tests/ -v`
5. `python -m uvicorn app.main:app --reload`
6. `curl http://localhost:8000/api/v1/health`

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
- rate-limit controls
- logging controls
- `ERROR_TRACKING_BACKEND`, `SENTRY_DSN`, and `SENTRY_TRACES_SAMPLE_RATE`
- `UVICORN_WORKERS`

The production container starts with:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2}
```

The container fails fast if `DATABASE_URL`, `API_AUTH_KEY`, or `ENV` are missing, and its health check targets `/api/v1/health/ready` so the process is not marked healthy until database connectivity is working.

If the API container exits before serving traffic, that is expected fail-fast behavior for an incomplete production env file.

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

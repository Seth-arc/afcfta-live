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

## 3. Create `.env` From `.env.example`

Copy the example file:

```bash
cp .env.example .env
```

The application settings loaded by `app/config.py` are:

- `DATABASE_URL`
- `DATABASE_URL_SYNC`
- `ENV`
- `LOG_LEVEL`
- `APP_TITLE`
- `APP_VERSION`

A working local example looks like this:

```env
DATABASE_URL=postgresql+asyncpg://afcfta:afcfta_dev@localhost:5432/afcfta
DATABASE_URL_SYNC=postgresql://afcfta:afcfta_dev@localhost:5432/afcfta
ENV=development
LOG_LEVEL=INFO
APP_TITLE=AfCFTA Intelligence API
APP_VERSION=0.1.0
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

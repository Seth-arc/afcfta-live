# Rollback Runbook

## When to use this runbook

Use this runbook when any of the following occur after a production deployment:

- The API container fails its health check (`/api/v1/health/ready`) repeatedly.
- The assessment endpoint returns HTTP 500.
- A migration was applied but the previous image is needed to restore service.

## Step 1 — Pin the last known-good image

Identify the previous image tag from the CI docker-build job artifact. In GitHub
Actions, each successful build pushes `afcfta-intelligence:ci-<sha>` where `<sha>`
is the short commit hash.

1. Open the GitHub Actions run for the last **successful** deployment.
2. Note the image tag from the build step output (e.g. `afcfta-intelligence:ci-b74f9f2`).
3. Edit `docker-compose.prod.yml` and replace the image on both the `migrate` and
   `api` services:

```yaml
services:
  migrate:
    image: afcfta-intelligence:ci-<last-good-sha>
    # ...

  api:
    image: afcfta-intelligence:ci-<last-good-sha>
    # ...
```

Do **not** run `docker compose up` yet — reverse the migration first.

## Step 2 — Reverse the migration

### Back up the database first

Downgrade can destroy data for destructive migrations (`DROP COLUMN`, `DROP TABLE`).
**Always** take a backup before downgrading:

```bash
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U afcfta afcfta > backup-$(date +%Y%m%d-%H%M).sql
```

### Run the downgrade

```bash
docker compose -f docker-compose.prod.yml run --rm \
  -e "$(cat .env.prod | grep DATABASE_URL)" \
  migrate python -m alembic downgrade -1
```

`downgrade -1` reverses only the last applied revision. To reverse multiple
revisions, either repeat the command or supply the target revision ID explicitly:

```bash
docker compose -f docker-compose.prod.yml run --rm \
  -e "$(cat .env.prod | grep DATABASE_URL)" \
  migrate python -m alembic downgrade <target-revision-id>
```

## Step 3 — Restart with the pinned image

```bash
docker compose -f docker-compose.prod.yml up -d api
```

The `migrate` service will run automatically on `up` because the `api` service
depends on it. Since the pinned image contains the older Alembic head, the
migrate service will be a no-op (schema already matches that revision).

## Step 4 — Verify rollback

Curl the health endpoint:

```bash
curl http://localhost:8000/api/v1/health/ready
```

Then hit a golden assessment endpoint to confirm the previous version is serving
correctly:

```bash
curl -H "Authorization: Bearer <API_AUTH_KEY>" \
  http://localhost:8000/api/v1/assessments/<known-good-id>
```

Both should return HTTP 200 with valid JSON.

## Re-deploy after root cause fix

After the root cause is fixed in a new commit:

1. Build a new image from the fixed commit.
2. Update `docker-compose.prod.yml` to reference the new image tag.
3. A new migration may be needed to re-apply the failed schema change. Never
   re-apply a reversed migration without a corresponding code fix.
4. Follow the normal deployment process (`docker compose up --build -d`).

## Alembic revision reference

Update this table after every new migration is merged.

| Revision ID                       | Description                  |
| --------------------------------- | ---------------------------- |
| `0001_initial_empty`              | Initial empty migration      |
| `0002_create_hs6_product`         | Create HS6 product table     |
| `0003_create_provenance_layer`    | Create provenance layer      |
| `0004_create_rules_layer`         | Create rules layer           |
| `0005_create_tariff_layer`        | Create tariff layer          |
| `0006_create_status_layer`        | Create status layer          |
| `0007_create_evidence_layer`      | Create evidence layer        |
| `0008_create_case_layer`          | Create case layer            |
| `0009_create_audit_layer`         | Create evaluation audit layer|
| `0010_create_intelligence_layer`  | Create intelligence layer    |
| `0011_expand_checktype`           | Expand check type enum       |
| `0012_evidence_effective_dates`   | Add evidence effective dates |

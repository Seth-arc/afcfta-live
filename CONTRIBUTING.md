# Contributing

Thanks for contributing to AIS.

AIS is a deterministic trade-compliance engine. Contributions are expected to
preserve auditability, traceability, and the architecture invariants in `AGENTS.md`.

## Getting Started

Start with the development setup guide:

- [docs/dev/setup.md](docs/dev/setup.md)

Then read:

- `AGENTS.md`
- `docs/dev/project-structure.md`
- `docs/dev/testing.md`

## Code Style

The project uses:

- Ruff
- line length `100`
- Python `3.11`

Keep changes small, explicit, and easy to review.

## Branch And PR Process

Keep the process simple:

1. create a short descriptive branch from your main integration branch
2. make focused changes
3. add or update tests
4. open a pull request with:
   - what changed
   - why it changed
   - any schema, rule, or migration impact

Small PRs are preferred over broad refactors.

## What Must Have Tests

At minimum, add tests for:

- every new service method
- every new failure code path
- every new endpoint behavior that changes request or response handling
- any change to audit persistence or replay

If you add a new failure outcome, test the specific machine-readable code, not just a generic false result.

## What Needs Extra Review

Changes in these areas require especially careful review:

- the expression evaluator
- locked reference files in `app/core/`
- database schemas and migrations
- rule-resolution logic
- audit persistence and replay logic

In particular, any change to the expression evaluator should be reviewed for:

- safety
- deterministic behavior
- grammar compatibility

## Locked Files

Do not casually edit these hand-maintained reference files:

- `app/core/countries.py`
- `app/core/fact_keys.py`
- `app/core/entity_keys.py`
- `app/core/failure_codes.py`
- `tests/fixtures/golden_cases.py`

If one of these files truly needs to change, call it out explicitly in the PR and request targeted review.

## Reporting Issues

When reporting a bug, include:

- a short description
- steps to reproduce
- expected behavior
- actual behavior
- request id, if the issue came from an API call
- relevant input payload or fixture data

For eligibility defects, include the exact:

- HS6 code
- exporter/importer
- year
- production facts

That makes the issue reproducible.

## Code Of Conduct

Be professional.

That means:

- critique code, not people
- assume good intent
- be clear and specific
- keep review comments technical and constructive

AIS deals with legal and compliance-sensitive logic. Precision and professionalism matter.

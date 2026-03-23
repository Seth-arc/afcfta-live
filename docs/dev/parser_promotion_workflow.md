# Parser Promotion Workflow

This runbook documents the repeatable staged-to-operational promotion workflow for Appendix IV parser artifacts.

## Purpose

Use this workflow when you want to move parser-generated Appendix IV artifacts from staged CSV outputs into the operational PSR tables.

The workflow is intentionally split into explicit steps:

1. Generate staged artifacts
2. Validate staged artifacts
3. Preview the promotion plan
4. Promote into operational tables
5. Validate database state

This separation makes failures visible before database mutation.

## Expected Input Files

The promotion step expects these files to exist:

- `data/staged/raw_csv/appendix_iv_decomposed.csv`
- `data/processed/rules/appendix_iv_pathways.csv`
- `data/processed/rules/appendix_iv_applicability.csv`

These are produced by the parser pipeline steps before promotion.

## Recommended Operator Sequence

### 1. Build staged artifacts only

Run the parser pipeline without database mutation:

```bash
python scripts/parsers/run_full_pipeline.py --skip-insert
```

This should produce the staged and processed CSV artifacts.

### 2. Validate staged artifacts

Run artifact-only validation first:

```bash
python scripts/parsers/validation_runner.py --scope artifacts
```

What this does:

- validates decomposed component rows
- validates pathway payload structure and expression compatibility
- validates applicability rows and precedence ranks
- fails before any database write if malformed artifacts are present

### 3. Preview the promotion plan

Run a dry-run promotion:

```bash
python scripts/parsers/psr_db_inserter.py --dry-run
```

What this does:

- re-validates staged artifacts
- builds the exact promotion plan the inserter would use
- reports planned insert counts for each operational table
- aborts on cross-artifact mapping gaps by default
- does not write to the database

Cross-artifact mapping gaps include:

- decomposed rows that do not resolve to a promoted rule
- pathway rows that do not resolve to a promoted rule
- applicability rows that do not resolve to a promoted PSR rule

If you explicitly want to inspect a partial promotion plan, you can use:

```bash
python scripts/parsers/psr_db_inserter.py --dry-run --allow-partial-mappings
```

That mode is diagnostic only. Normal promotion should not rely on partial mappings.

### 4. Promote into operational tables

When the dry-run is clean, promote:

```bash
python scripts/parsers/psr_db_inserter.py
```

What this does:

- validates staged artifacts
- builds a promotion plan
- clears existing Appendix IV source rows in FK-safe order
- inserts replacement rows in FK order
- performs the clear-and-replace operation atomically in one transaction

Operational insert order:

1. `psr_rule`
2. `psr_rule_component`
3. `eligibility_rule_pathway`
4. `hs6_psr_applicability`

## 5. Validate database state

After promotion, validate database state explicitly:

```bash
python scripts/parsers/validation_runner.py --scope db
```

This checks:

- row counts
- referential integrity
- enum validity
- expression presence counts
- confidence distribution
- HS6 coverage
- spot checks for known Appendix IV expectations

## Optional Single-Run Promotion Plus DB Validation

If you want the inserter to run DB validation immediately after promotion:

```bash
python scripts/parsers/psr_db_inserter.py --post-validate
```

This is convenient for operators, but the recommended workflow is still to run the validation step explicitly so artifact validation and DB validation remain distinct.

## Failure Points

The workflow is expected to fail fast at these points:

1. Missing input artifacts
2. Malformed staged artifacts
3. Cross-artifact mapping inconsistencies
4. Missing Appendix IV source registry row
5. Database FK or constraint violations
6. Post-promotion validation failures

Each failure point is designed to stop the workflow with a direct message about what broke.

## Idempotency Notes

The promotion workflow is repeatable at the dataset level:

- it always targets the same Appendix IV source identifier
- it clears prior Appendix IV rows before inserting replacement rows
- the clear-and-replace step runs in one transaction

UUIDs are regenerated on each promotion run, so row identities are not stable across promotions. The workflow is therefore repeatable for operational content, not immutable row identity.

## Resume Patterns

Common restart patterns:

Validate artifacts only:

```bash
python scripts/parsers/validation_runner.py --scope artifacts
```

Resume the pipeline from promotion onward:

```bash
python scripts/parsers/run_full_pipeline.py --start-from 7
```

Run database validation only:

```bash
python scripts/parsers/validation_runner.py --scope db
```

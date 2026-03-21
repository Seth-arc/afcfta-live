# Pipeline Rules

Pipelines move data: raw sources → extraction → normalization → database.

## Stages (in order)

acquire → parse → normalize → enrich → assess → index → alerts → qa

## Critical Rules

- Verbatim legal text always preserved alongside normalization
- HS codes normalized to digits only, stored with hs_version
- Every output record traces to a source_id in source_registry
- Never infer status — flag ambiguity instead
- Rates preserve original precision — do not round
- Pipeline reruns must be idempotent

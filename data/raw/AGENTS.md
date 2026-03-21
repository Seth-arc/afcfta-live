# Raw Source Documents — Never Modified After Ingestion

## Authority Tiers

| Tier | Directory | Role |
|------|-----------|------|
| 1 | tier1_binding/ | Binding legal authority (Agreement, Annexes, Appendix IV, Schedules) |
| 2 | tier2_operational/ | Operational reference (e-Tariff Book, circulars, guidance) |
| 3 | tier3_support/ | Interpretive support (manuals, guides) |
| 4 | tier4_analytics/ | Analytic enrichment (corridor metrics, trade baselines) |

Higher tiers override lower tiers in all conflict resolution.

## Ingestion Checklist

For every file added:
1. Compute SHA-256 checksum
2. Create source_registry record
3. Record file_path relative to data/raw/
4. If superseding an older version, update supersedes/superseded_by chain

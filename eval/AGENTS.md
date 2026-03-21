# Evaluation and Benchmarking

- gold_sets/ — manually verified correct answers (rule lookups, tariff queries,
  eligibility cases, evidence readiness)
- benchmarks/ — performance: query latency, throughput
- regression/ — must-pass suites before any release

## Gold Set Coverage Targets

75 rule lookups, 75 tariff queries, 50 eligibility cases, 50 evidence cases,
30 counterfactual scenarios.

## Regression Rules

Re-run full suite when: new source ingested, parser changes, service logic
changes, or schema changes.

# Dev Prompt Books

This folder contains the working prompt books and runbooks for staged backend and interface delivery.

## Prompt Book Summary

| File | Use When | Primary Scope | Start Here? |
|------|----------|---------------|-------------|
| [AIS_v01_delivery_vibecoding_prompts.md](AIS_v01_delivery_vibecoding_prompts.md) | You want the original v0.1 delivery sequence that completed the March 23 build-out | Historical delivery path for core engine, audit, evidence, provenance, and intelligence milestones | No |
| [Production Readiness — Vibecoding Prompts.md](Production%20Readiness%20%E2%80%94%20Vibecoding%20Prompts.md) | You need the top-level execution order across the split production-readiness books | Index and sequencing guide for backend hardening and NIM readiness | Yes |
| [Backend Hardening — Vibecoding Prompts.md](Backend%20Hardening%20%E2%80%94%20Vibecoding%20Prompts.md) | You are making the service deterministic, replay-safe, secure, observable, and deployable before interface work | Engine correctness, contract freeze, auth, rate limiting, health, logging, CI, Docker, coverage, ops | Yes |
| [NIM Readiness — Vibecoding Prompts.md](NIM%20Readiness%20%E2%80%94%20Vibecoding%20Prompts.md) | Backend hardening is complete and you are ready to build the safe assistant layer | Assistant contract harness, NIM services, orchestration, hallucination guards, full-flow validation | After backend hardening |
| [NIM Integration — Vibecoding Prompts.md](NIM%20Integration%20%E2%80%94%20Vibecoding%20Prompts.md) | The NIM readiness book is already complete and you want post-readiness improvements | Advanced NIM tuning, rollout controls, analytics, session enhancements, evaluation harnesses | After NIM readiness |
| [AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md](AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md) | You need the gap analysis and fix prioritization that drove the production-readiness books | Audit findings, blockers, readiness scores, recommended fix order | Reference |
| [delivery_plan_and_backlog.md](delivery_plan_and_backlog.md) | You need the milestone-oriented backlog that guided the delivered v0.1 work | Delivery plan and milestone backlog | Reference |
| [parser_promotion_workflow.md](parser_promotion_workflow.md) | You are promoting staged Appendix IV parser artifacts into operational PSR tables | Parser validation and promotion operator workflow | Reference |
| [setup.md](setup.md) | You need development environment setup instructions | Local setup and environment guidance | Reference |
| [testing.md](testing.md) | You need the testing conventions and command patterns | Unit and integration testing guidance | Reference |
| [project-structure.md](project-structure.md) | You need a quick reference for repository layout | Development structure reference | Reference |

## Recommended Order

1. Read [AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md](AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md).
2. Start with [Production Readiness — Vibecoding Prompts.md](Production%20Readiness%20%E2%80%94%20Vibecoding%20Prompts.md).
3. Execute [Backend Hardening — Vibecoding Prompts.md](Backend%20Hardening%20%E2%80%94%20Vibecoding%20Prompts.md).
4. Execute [NIM Readiness — Vibecoding Prompts.md](NIM%20Readiness%20%E2%80%94%20Vibecoding%20Prompts.md).
5. Use [NIM Integration — Vibecoding Prompts.md](NIM%20Integration%20%E2%80%94%20Vibecoding%20Prompts.md) only for post-readiness enhancement work.

## Quick Rule

- If the backend is not yet replay-safe and contract-stable, use the backend hardening book.
- If the backend is stable and you are building the first safe assistant layer, use the NIM readiness book.
- If the assistant layer already exists and you are tuning or extending it, use the NIM integration companion book.
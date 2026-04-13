# Dev Prompt Books

This folder contains the working prompt books and runbooks for staged backend and interface delivery.

## Prompt Book Summary

| File | Use When | Primary Scope | Start Here? |
|------|----------|---------------|-------------|
| [AIS_v01_delivery_vibecoding_prompts.md](prompts/AIS_v01_delivery_vibecoding_prompts.md) | You want the original v0.1 delivery sequence that completed the March 23 build-out | Historical delivery path for core engine, audit, evidence, provenance, and intelligence milestones | No |
| [Production Readiness - Vibecoding Prompts.md](prompts/Production%20Readiness%20%E2%80%94%20Vibecoding%20Prompts.md) | You need the top-level execution order across the split production-readiness books | Index and sequencing guide for backend hardening and NIM readiness | Yes |
| [Backend Hardening - Vibecoding Prompts.md](prompts/Backend%20Hardening%20%E2%80%94%20Vibecoding%20Prompts.md) | You are making the service deterministic, replay-safe, secure, observable, and deployable before interface work | Engine correctness, contract freeze, auth, rate limiting, health, logging, CI, Docker, coverage, ops | Yes |
| [NIM Readiness - Vibecoding Prompts.md](prompts/NIM%20Readiness%20%E2%80%94%20Vibecoding%20Prompts%20(1).md) | Backend hardening is complete and you are ready to build the safe assistant layer | Assistant contract harness, NIM services, orchestration, hallucination guards, full-flow validation | After backend hardening |
| [NIM Integration - Vibecoding Prompts.md](prompts/NIM%20Integration%20%E2%80%94%20Vibecoding%20Prompts%20(3).md) | The NIM readiness book is already complete and you want post-readiness improvements | Advanced NIM tuning, rollout controls, analytics, session enhancements, evaluation harnesses | After NIM readiness |
| [AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md](prompts/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md) | You need the gap analysis and fix prioritization that drove the production-readiness books | Audit findings, blockers, readiness scores, recommended fix order | Reference |
| [AFCFTA-LIVE_BUILD_PROGRESS_HANDBOOK_2026-04-10.md](prompts/AFCFTA-LIVE_BUILD_PROGRESS_HANDBOOK_2026-04-10.md) | You need the current weighted completion estimate, workstream-by-workstream progress, and the detailed missing components still blocking launch | Progress dashboard, gap detail, completion rationale, missing components by workstream | Reference |
| [AFCFTA-LIVE_BUILD_GAP_CLOSURE_PROMPT_HANDBOOK_2026-04-11.md](prompts/AFCFTA-LIVE_BUILD_GAP_CLOSURE_PROMPT_HANDBOOK_2026-04-11.md) | You want the most detailed current launch-closure prompt book derived from the 2026-04-10 build-progress gaps | Implementation-grade prompts for replay freeze, browser-safe auth, verification bundles, 10c/100c recovery, dataset manifests, trader trust UX, and final launch gating | Yes, after reading the build-progress handbook |
| [delivery_plan_and_backlog.md](delivery_plan_and_backlog.md) | You need the milestone-oriented backlog that guided the delivered v0.1 work | Delivery plan and milestone backlog | Reference |
| [parser_promotion_workflow.md](parser_promotion_workflow.md) | You are promoting staged Appendix IV parser artifacts into operational PSR tables | Parser validation and promotion operator workflow | Reference |
| [setup.md](setup.md) | You need development environment setup instructions | Local setup and environment guidance | Reference |
| [testing.md](testing.md) | You need the testing conventions and command patterns | Unit and integration testing guidance | Reference |
| [project-structure.md](project-structure.md) | You need a quick reference for repository layout | Development structure reference | Reference |

## Recommended Order

1. Read [AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md](prompts/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md).
2. Read [AFCFTA-LIVE_BUILD_PROGRESS_HANDBOOK_2026-04-10.md](prompts/AFCFTA-LIVE_BUILD_PROGRESS_HANDBOOK_2026-04-10.md) if you need the current weighted status and launch-gap detail before choosing a prompt book.
3. If you want the most detailed current closure plan, start with [AFCFTA-LIVE_BUILD_GAP_CLOSURE_PROMPT_HANDBOOK_2026-04-11.md](prompts/AFCFTA-LIVE_BUILD_GAP_CLOSURE_PROMPT_HANDBOOK_2026-04-11.md).
4. Otherwise start with [Production Readiness - Vibecoding Prompts.md](prompts/Production%20Readiness%20%E2%80%94%20Vibecoding%20Prompts.md).
5. Execute [Backend Hardening - Vibecoding Prompts.md](prompts/Backend%20Hardening%20%E2%80%94%20Vibecoding%20Prompts.md).
6. Execute [NIM Readiness - Vibecoding Prompts.md](prompts/NIM%20Readiness%20%E2%80%94%20Vibecoding%20Prompts%20(1).md).
7. Use [NIM Integration - Vibecoding Prompts.md](prompts/NIM%20Integration%20%E2%80%94%20Vibecoding%20Prompts%20(3).md) only for post-readiness enhancement work.

## Quick Rule

- If the backend is not yet replay-safe and contract-stable, use the backend hardening book.
- If you already have the post-audit books and want the most detailed remaining launch-gap closure sequence, use the new build-gap closure handbook.
- If the backend is stable and you are building the first safe assistant layer, use the NIM readiness book.
- If the assistant layer already exists and you are tuning or extending it, use the NIM integration companion book.

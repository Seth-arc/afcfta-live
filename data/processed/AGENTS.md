# Processed Data — Database-Ready Structured Outputs

## Directory → Database Table Mapping

| Directory | Target Tables |
|-----------|---------------|
| entities/ | hs6_product, hs_code_alias |
| provisions/ | legal_provision |
| rules/ | psr_rule, psr_rule_component, eligibility_rule_pathway, hs6_psr_applicability |
| tariffs/ | tariff_schedule_header, tariff_schedule_line, tariff_schedule_rate_by_year |
| statuses/ | status_assertion, transition_clause |
| evidence/ | evidence_requirement, verification_question, document_readiness_template |
| analytics/ | corridor_profile, alert_event |

## Rules

- Every record must include source_id tracing to source_registry
- HS codes normalized to 6 digits, no dots, no spaces
- Country codes ISO alpha-3 from app/core/countries.py
- Enum values must exactly match docs/Concrete_Contract.md
- Verbatim legal text preserved alongside normalized versions
- Load in FK dependency order (see loading order in full AGENTS.md reference)

"""
Entity key conventions for polymorphic lookups
(status_assertion, evidence_requirement).
From Join_Strategy.md Section 1.3.
"""

ENTITY_KEY_PATTERNS = {
    "psr_rule": "PSR:{psr_id}",
    "schedule": "SCHEDULE:{schedule_id}",
    "schedule_line": "SCHEDULE_LINE:{schedule_line_id}",
    "corridor": "CORRIDOR:{exporter}:{importer}:{hs6_code}",
    "country": "COUNTRY:{iso3}",
    "pathway": "PATHWAY:{pathway_id}",
    "hs6_rule": "HS6_RULE:{psr_id}",
}

def make_entity_key(entity_type: str, **kwargs) -> str:
    pattern = ENTITY_KEY_PATTERNS[entity_type]
    return pattern.format(**kwargs)
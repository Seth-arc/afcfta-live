"""Frozen public contract constants for assessment and assistant APIs."""

from __future__ import annotations

ASSESSMENT_REQUEST_FIELD_ORDER = (
    "hs6_code",
    "hs_version",
    "exporter",
    "importer",
    "year",
    "persona_mode",
    "production_facts",
    "existing_documents",
    "case_id",
)

CASE_ASSESSMENT_REQUEST_FIELD_ORDER = (
    "year",
    "existing_documents",
)

TARIFF_OUTCOME_FIELDS = frozenset({
    "preferential_rate",
    "base_rate",
    "status",
    "provenance_ids",
})

ELIGIBILITY_ASSESSMENT_RESPONSE_FIELDS = frozenset({
    "hs6_code",
    "eligible",
    "pathway_used",
    "rule_status",
    "tariff_outcome",
    "failures",
    "missing_facts",
    "evidence_required",
    "missing_evidence",
    "readiness_score",
    "completeness_ratio",
    "confidence_class",
    "audit_persisted",
})

ASSISTANT_CONTEXT_FIELD_ORDER = (
    "persona_mode",
    "exporter",
    "importer",
    "year",
)

ASSISTANT_REQUEST_FIELD_ORDER = (
    "user_input",
    "context",
)

ASSISTANT_RESPONSE_ENVELOPE_FIELDS = frozenset({
    "response_type",
    "case_id",
    "evaluation_id",
    "audit_url",
    "audit_persisted",
    "assessment",
    "clarification",
    "explanation",
    "explanation_fallback_used",
    "error",
})

CLARIFICATION_FIELDS = frozenset({
    "question",
    "missing_facts",
    "missing_evidence",
})

ASSISTANT_ERROR_FIELDS = frozenset({
    "code",
    "message",
    "detail",
})

ENGINE_DECISION_FIELDS = frozenset({
    "eligible",
    "pathway_used",
    "rule_status",
    "tariff_outcome",
    "confidence_class",
})

ALL_REQUIRED_DRAFT_FACTS = frozenset({
    "hs6_code",
    "exporter",
    "importer",
    "year",
    "persona_mode",
})

VALID_ASSISTANT_RESPONSE_TYPES = frozenset({
    "clarification",
    "assessment",
    "error",
})

VALID_CONFIDENCE_CLASSES = frozenset({
    "complete",
    "provisional",
    "incomplete",
})

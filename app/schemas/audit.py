"""Pydantic schemas for reconstructed evaluation traces and audit summaries."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import LegalOutcome
from app.schemas.assessments import TariffOutcomeResponse
from app.schemas.cases import CaseFactResponse, CaseSummaryResponse
from app.schemas.evaluations import (
    EligibilityCheckResultResponse,
    EligibilityEvaluationResponse,
)
from app.schemas.evidence import EvidenceReadinessResult
from app.schemas.rules import PSRRuleResolvedOut
from app.schemas.status import StatusOverlay


class HS6ResolvedSnapshot(BaseModel):
    """Canonical HS6 product detail captured for an assessment trace."""

    hs6_id: UUID | None = None
    hs_version: str | None = None
    hs6_code: str
    hs6_display: str | None = None
    chapter: str | None = None
    heading: str | None = None
    description: str | None = None
    section: str | None = None
    section_name: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class PathwayEvaluationTrace(BaseModel):
    """One pathway attempt plus its atomic evaluator checks."""

    pathway_id: UUID | None = None
    pathway_code: str | None = None
    pathway_label: str | None = None
    priority_rank: int | None = None
    evaluated_expression: str | None = None
    result: bool | None = None
    missing_variables: list[str] = Field(default_factory=list)
    checks: list[EligibilityCheckResultResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class GeneralRulesTrace(BaseModel):
    """Persisted general-origin-rules outcome reconstructed from audit checks."""

    insufficient_operations_check: str | None = None
    cumulation_check: str | None = None
    direct_transport_check: str | None = None
    general_rules_passed: bool | None = None
    failure_codes: list[str] = Field(default_factory=list)
    checks: list[EligibilityCheckResultResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class RuleProvenanceTrace(BaseModel):
    """Compact provenance references for one resolved PSR rule."""

    source_id: UUID | None = None
    page_ref: int | None = None
    table_ref: str | None = None
    row_ref: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class TariffProvenanceTrace(BaseModel):
    """Compact provenance references for one resolved tariff outcome."""

    schedule_source_id: UUID | None = None
    rate_source_id: UUID | None = None
    line_page_ref: int | None = None
    rate_page_ref: int | None = None
    table_ref: str | None = None
    row_ref: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class DecisionProvenanceTrace(BaseModel):
    """Rolled-up provenance references for the final decision summary."""

    rule: RuleProvenanceTrace | None = None
    tariff: TariffProvenanceTrace | None = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class AuditTariffOutcomeTrace(TariffOutcomeResponse):
    """Tariff replay summary with additive provenance references."""

    schedule_source_id: UUID | None = None
    rate_source_id: UUID | None = None
    line_page_ref: int | None = None
    rate_page_ref: int | None = None
    table_ref: str | None = None
    row_ref: str | None = None
    resolved_rate_year: int | None = None
    used_fallback_rate: bool = False

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class FinalDecisionTrace(BaseModel):
    """Collapsed final decision summary for an evaluation."""

    eligible: bool
    overall_outcome: LegalOutcome | str
    pathway_used: str | None = None
    rule_status: str | None = None
    tariff_status: str | None = None
    confidence_class: str
    failure_codes: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    readiness_score: float | None = None
    completeness_ratio: float | None = None
    provenance: DecisionProvenanceTrace | None = None

    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "eligible": True,
                    "overall_outcome": "eligible",
                    "pathway_used": "CTH",
                    "rule_status": "agreed",
                    "tariff_status": "in_force",
                    "confidence_class": "complete",
                    "failure_codes": [],
                    "missing_facts": [],
                    "missing_evidence": [],
                    "readiness_score": 1.0,
                    "completeness_ratio": 1.0,
                    "provenance": {
                        "rule": {"source_id": "c3d3fd71-d1b2-412e-a708-1685f1f2299f"},
                        "tariff": {"schedule_source_id": "c3d3fd71-d1b2-412e-a708-1685f1f2299f"},
                    },
                }
            ]
        },
    )


class AuditTrail(BaseModel):
    """Reconstructed decision trace for one persisted eligibility evaluation."""

    evaluation: EligibilityEvaluationResponse
    case: CaseSummaryResponse | None = None
    original_input_facts: list[CaseFactResponse] = Field(default_factory=list)
    hs6_resolved: HS6ResolvedSnapshot | None = None
    psr_rule: PSRRuleResolvedOut | None = None
    pathway_evaluations: list[PathwayEvaluationTrace] = Field(default_factory=list)
    general_rules_results: GeneralRulesTrace | None = None
    status_overlay: StatusOverlay | None = None
    tariff_outcome: AuditTariffOutcomeTrace | None = None
    evidence_readiness: EvidenceReadinessResult | None = None
    atomic_checks: list[EligibilityCheckResultResponse] = Field(default_factory=list)
    final_decision: FinalDecisionTrace

    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "evaluation": {
                        "evaluation_id": "4c651cd2-8f0f-4c16-9f37-8dfceef41f26",
                        "case_id": "29dc2946-6ef0-46a0-b3eb-0f6a64e40db7",
                        "evaluation_date": "2025-01-01",
                        "overall_outcome": "eligible",
                        "pathway_used": "CTH",
                        "confidence_class": "complete",
                        "rule_status_at_evaluation": "agreed",
                        "tariff_status_at_evaluation": "in_force",
                    },
                    "case": {
                        "case_id": "29dc2946-6ef0-46a0-b3eb-0f6a64e40db7",
                        "case_external_ref": "CASE-GHA-110311-001",
                        "persona_mode": "exporter",
                        "exporter_state": "GHA",
                        "importer_state": "NGA",
                        "hs_code": "110311",
                        "hs_version": "HS2017",
                        "submission_status": "draft",
                    },
                    "original_input_facts": [],
                    "hs6_resolved": {
                        "hs6_code": "110311",
                        "hs_version": "HS2017",
                        "description": "Groats and meal of wheat",
                    },
                    "psr_rule": {
                        "psr_id": "8c6a4b89-4d4e-4d5b-9eb4-4d1775edb3b0",
                        "hs6_code": "110311",
                        "product_description": "Groats and meal of wheat",
                        "legal_rule_text_verbatim": "CTH",
                        "rule_status": "agreed",
                    },
                    "pathway_evaluations": [],
                    "general_rules_results": {
                        "general_rules_passed": True,
                        "failure_codes": [],
                        "checks": [],
                    },
                    "status_overlay": {
                        "status_type": "agreed",
                        "confidence_class": "complete",
                        "active_transitions": [],
                        "constraints": [],
                        "source_text_verbatim": "Rule is agreed.",
                    },
                    "tariff_outcome": {
                        "preferential_rate": "0.0000",
                        "base_rate": "15.0000",
                        "status": "in_force",
                    },
                    "evidence_readiness": {
                        "required_items": [
                            "Certificate of origin",
                            "Bill of materials",
                            "Invoice",
                        ],
                        "missing_items": [],
                        "verification_questions": [
                            "Can the exporter provide a valid certificate of origin?"
                        ],
                        "readiness_score": 1.0,
                        "completeness_ratio": 1.0,
                    },
                    "atomic_checks": [],
                    "final_decision": {
                        "eligible": True,
                        "overall_outcome": "eligible",
                        "pathway_used": "CTH",
                        "rule_status": "agreed",
                        "tariff_status": "in_force",
                        "confidence_class": "complete",
                        "failure_codes": [],
                        "missing_facts": [],
                        "missing_evidence": [],
                        "readiness_score": 1.0,
                        "completeness_ratio": 1.0,
                    },
                }
            ]
        },
    )

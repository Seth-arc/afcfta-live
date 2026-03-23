"""Pydantic schemas for reconstructed evaluation traces and audit summaries."""

from __future__ import annotations

from typing import Any
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

    model_config = ConfigDict(from_attributes=True, extra="ignore")


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
    tariff_outcome: TariffOutcomeResponse | None = None
    evidence_readiness: EvidenceReadinessResult | None = None
    atomic_checks: list[EligibilityCheckResultResponse] = Field(default_factory=list)
    final_decision: FinalDecisionTrace

    model_config = ConfigDict(from_attributes=True, extra="ignore")

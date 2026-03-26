"""Reconstruct persisted evaluation trails and emit structured assessment logs."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from app.core.exceptions import AuditTrailNotFoundError
from app.core.logging import log_event
from app.schemas.audit import (
    AuditTariffOutcomeTrace,
    AuditTrail,
    DecisionProvenanceTrace,
    FinalDecisionTrace,
    GeneralRulesTrace,
    HS6ResolvedSnapshot,
    PathwayEvaluationTrace,
    ProvisionSummary,
    RuleProvenanceTrace,
    TariffProvenanceTrace,
)
from app.schemas.cases import CaseFactResponse, CaseSummaryResponse
from app.schemas.evaluations import (
    EligibilityCheckResultResponse,
    EligibilityEvaluationResponse,
)
from app.schemas.evidence import EvidenceReadinessResult
from app.schemas.rules import PSRRuleResolvedOut
from app.schemas.status import StatusOverlay

logger = logging.getLogger("app.audit")


class AuditService:
    """Service for audit-trail replay and structured assessment logging."""

    def __init__(
        self,
        evaluations_repository: Any,
        cases_repository: Any,
        sources_repository: Any | None = None,
    ) -> None:
        self.evaluations_repository = evaluations_repository
        self.cases_repository = cases_repository
        self.sources_repository = sources_repository

    async def get_decision_trace(
        self,
        *,
        evaluation_id: str | None = None,
        case_id: str | None = None,
    ) -> AuditTrail:
        """Return the reconstructed audit trail for one evaluation or the latest case run."""

        resolved_evaluation_id = await self._resolve_evaluation_id(
            evaluation_id=evaluation_id,
            case_id=case_id,
        )
        evaluation_bundle = await self.evaluations_repository.get_evaluation_with_checks(
            resolved_evaluation_id
        )
        if evaluation_bundle is None:
            raise AuditTrailNotFoundError(
                f"No persisted audit trail was found for evaluation '{resolved_evaluation_id}'",
                detail={"evaluation_id": resolved_evaluation_id},
            )

        evaluation = EligibilityEvaluationResponse.model_validate(evaluation_bundle["evaluation"])
        checks = [
            EligibilityCheckResultResponse.model_validate(check)
            for check in evaluation_bundle["checks"]
        ]

        case_bundle = await self.cases_repository.get_case_with_facts(str(evaluation.case_id))
        case = (
            CaseSummaryResponse.model_validate(case_bundle["case"])
            if case_bundle is not None
            else None
        )
        facts = (
            [CaseFactResponse.model_validate(fact) for fact in case_bundle["facts"]]
            if case_bundle is not None
            else []
        )

        provenance = await self._build_decision_provenance(
            checks,
            evaluation_id=str(evaluation.evaluation_id),
        )
        return AuditTrail(
            evaluation=evaluation,
            case=case,
            original_input_facts=facts,
            hs6_resolved=self._build_hs6_snapshot(case, checks),
            psr_rule=self._decode_summary_model(
                checks,
                check_type="rule",
                check_code="PSR_RESOLUTION",
                payload_key="psr_rule",
                model_cls=PSRRuleResolvedOut,
            ),
            pathway_evaluations=self._build_pathway_evaluations(checks),
            general_rules_results=self._build_general_rules_trace(checks),
            status_overlay=self._decode_summary_model(
                checks,
                check_type="status",
                check_code="STATUS_OVERLAY",
                payload_key="overlay",
                model_cls=StatusOverlay,
            ),
            tariff_outcome=self._build_tariff_outcome(checks),
            evidence_readiness=self._decode_summary_model(
                checks,
                check_type="evidence",
                check_code="EVIDENCE_READINESS",
                payload_key="evidence_readiness",
                model_cls=EvidenceReadinessResult,
            ),
            atomic_checks=checks,
            final_decision=self._build_final_decision(evaluation, checks, provenance),
        )

    async def get_evaluations_for_case(
        self,
        case_id: str,
    ) -> list[EligibilityEvaluationResponse]:
        """Return all stored evaluations for a case, newest first."""

        evaluations = await self.evaluations_repository.get_evaluations_for_case(case_id)
        return [
            EligibilityEvaluationResponse.model_validate(evaluation)
            for evaluation in evaluations
        ]

    async def get_latest_decision_trace(self, case_id: str) -> AuditTrail:
        """Return the reconstructed audit trail for the newest stored evaluation on a case."""

        return await self.get_decision_trace(case_id=case_id)

    def log_assessment(
        self,
        *,
        case_id: str | None,
        hs6_code: str,
        exporter: str,
        importer: str,
        outcome: str,
        confidence_class: str,
        duration_ms: int,
        blockers: Sequence[str] | None = None,
        missing_facts: Sequence[str] | None = None,
    ) -> None:
        """Emit a structured log payload for one assessment run."""

        blockers = list(blockers or [])
        missing_facts = list(missing_facts or [])
        level = logging.WARNING if blockers or missing_facts else logging.INFO
        log_event(
            logger,
            level,
            event="eligibility_assessment",
            message="Eligibility assessment completed",
            case_id=case_id,
            hs6_code=hs6_code,
            exporter=exporter,
            importer=importer,
            outcome=outcome,
            confidence_class=confidence_class,
            duration_ms=duration_ms,
            blockers=blockers,
            missing_facts=missing_facts,
        )

    async def _resolve_evaluation_id(
        self,
        *,
        evaluation_id: str | None,
        case_id: str | None,
    ) -> str:
        """Resolve the evaluation id directly or from the latest stored case run."""

        if evaluation_id is not None:
            return evaluation_id
        if case_id is None:
            raise ValueError("Either evaluation_id or case_id is required")

        evaluations = await self.evaluations_repository.get_evaluations_for_case(case_id)
        if not evaluations:
            raise AuditTrailNotFoundError(
                f"No persisted audit trail was found for case '{case_id}'",
                detail={"case_id": case_id},
            )
        return str(evaluations[0]["evaluation_id"])

    def _build_hs6_snapshot(
        self,
        case: CaseSummaryResponse | None,
        checks: Sequence[EligibilityCheckResultResponse],
    ) -> HS6ResolvedSnapshot | None:
        """Return the canonical HS6 snapshot captured for the evaluation."""

        summary_product = self._decode_summary_payload(
            checks,
            check_type="classification",
            check_code="HS6_RESOLUTION",
            payload_key="product",
        )
        if isinstance(summary_product, dict):
            return HS6ResolvedSnapshot.model_validate(summary_product)

        if case is None or case.hs_code is None:
            return None

        return HS6ResolvedSnapshot(
            hs6_code=case.hs_code,
            hs_version=case.hs_version,
        )

    def _build_pathway_evaluations(
        self,
        checks: Sequence[EligibilityCheckResultResponse],
    ) -> list[PathwayEvaluationTrace]:
        """Group persisted PSR checks under their evaluated pathway summaries."""

        atomic_by_pathway: dict[str, list[EligibilityCheckResultResponse]] = defaultdict(list)
        for check in checks:
            if check.check_type != "psr":
                continue
            details = self._details(check)
            pathway_key = str(
                details.get("pathway_id")
                or details.get("pathway_code")
                or "unknown"
            )
            atomic_by_pathway[pathway_key].append(check)

        pathway_traces: list[PathwayEvaluationTrace] = []
        for check in checks:
            if check.check_type != "pathway" or check.check_code != "PATHWAY_EVALUATION":
                continue
            details = self._details(check)
            pathway_payload = details.get("pathway") or {}
            pathway_key = str(
                pathway_payload.get("pathway_id")
                or pathway_payload.get("pathway_code")
                or "unknown"
            )
            pathway_traces.append(
                PathwayEvaluationTrace(
                    pathway_id=pathway_payload.get("pathway_id"),
                    pathway_code=pathway_payload.get("pathway_code"),
                    pathway_label=pathway_payload.get("pathway_label"),
                    priority_rank=pathway_payload.get("priority_rank"),
                    evaluated_expression=details.get("evaluated_expression"),
                    result=details.get("result"),
                    missing_variables=list(details.get("missing_variables", [])),
                    checks=atomic_by_pathway.get(pathway_key, []),
                )
            )

        if pathway_traces:
            return pathway_traces

        fallback_traces: list[PathwayEvaluationTrace] = []
        for pathway_key, atomic_checks in atomic_by_pathway.items():
            first_details = self._details(atomic_checks[0]) if atomic_checks else {}
            fallback_traces.append(
                PathwayEvaluationTrace(
                    pathway_id=first_details.get("pathway_id"),
                    pathway_code=first_details.get("pathway_code") or pathway_key,
                    pathway_label=first_details.get("pathway_label"),
                    priority_rank=first_details.get("priority_rank"),
                    evaluated_expression=first_details.get("evaluated_expression"),
                    result=self._aggregate_atomic_result(atomic_checks),
                    missing_variables=list(first_details.get("missing_variables", [])),
                    checks=atomic_checks,
                )
            )
        return sorted(
            fallback_traces,
            key=lambda item: (
                item.priority_rank if item.priority_rank is not None else 10_000,
                item.pathway_code or "",
            ),
        )

    def _build_general_rules_trace(
        self,
        checks: Sequence[EligibilityCheckResultResponse],
    ) -> GeneralRulesTrace | None:
        """Reconstruct the post-PSR general-rules outcome from persisted checks."""

        general_checks = [
            check
            for check in checks
            if check.check_type == "general_rule" and check.check_code != "GENERAL_RULES_SUMMARY"
        ]
        summary = self._decode_summary_payload(
            checks,
            check_type="general_rule",
            check_code="GENERAL_RULES_SUMMARY",
            payload_key="general_rules_result",
        )
        if summary is None and not general_checks:
            return None

        payload = dict(summary or {})
        if "insufficient_operations_check" not in payload:
            payload["insufficient_operations_check"] = self._derive_general_check_state(
                general_checks,
                "INSUFFICIENT_OPERATIONS",
            )
        if "cumulation_check" not in payload:
            payload["cumulation_check"] = self._derive_general_check_state(
                general_checks,
                "CUMULATION",
            )
        if "direct_transport_check" not in payload:
            payload["direct_transport_check"] = self._derive_general_check_state(
                general_checks,
                "DIRECT_TRANSPORT",
            )
        if "general_rules_passed" not in payload:
            payload["general_rules_passed"] = all(
                check.passed is not False for check in general_checks
            ) and any(
                check.check_code == "DIRECT_TRANSPORT" and check.passed is True
                for check in general_checks
            )
        if not isinstance(payload.get("failure_codes"), list):
            payload["failure_codes"] = self._failure_codes_from_checks(general_checks)
        payload["checks"] = general_checks
        return GeneralRulesTrace.model_validate(payload)

    def _build_tariff_outcome(
        self,
        checks: Sequence[EligibilityCheckResultResponse],
    ) -> AuditTariffOutcomeTrace | None:
        """Decode the persisted tariff outcome summary when present."""

        tariff_resolution = self._decode_summary_payload(
            checks,
            check_type="tariff",
            check_code="TARIFF_RESOLUTION",
            payload_key="tariff_resolution",
        )
        if isinstance(tariff_resolution, dict):
            return AuditTariffOutcomeTrace(
                preferential_rate=self._decimal_or_none(tariff_resolution.get("preferential_rate")),
                base_rate=self._decimal_or_none(tariff_resolution.get("base_rate")),
                status=self._tariff_status_from_payload(tariff_resolution),
                provenance_ids=self._tariff_provenance_ids_from_payload(tariff_resolution),
                schedule_source_id=tariff_resolution.get("schedule_source_id"),
                rate_source_id=tariff_resolution.get("rate_source_id"),
                line_page_ref=tariff_resolution.get("line_page_ref"),
                rate_page_ref=tariff_resolution.get("rate_page_ref"),
                table_ref=tariff_resolution.get("table_ref"),
                row_ref=tariff_resolution.get("row_ref"),
                resolved_rate_year=tariff_resolution.get("resolved_rate_year"),
                used_fallback_rate=bool(tariff_resolution.get("used_fallback_rate", False)),
            )

        tariff_outcome = self._decode_summary_payload(
            checks,
            check_type="tariff",
            check_code="TARIFF_RESOLUTION",
            payload_key="tariff_outcome",
        )
        if not isinstance(tariff_outcome, dict):
            return None
        tariff_outcome_payload = dict(tariff_outcome)
        tariff_outcome_payload["provenance_ids"] = self._tariff_provenance_ids_from_payload(
            tariff_outcome_payload
        )
        return AuditTariffOutcomeTrace.model_validate(tariff_outcome_payload)

    def _build_final_decision(
        self,
        evaluation: EligibilityEvaluationResponse,
        checks: Sequence[EligibilityCheckResultResponse],
        provenance: DecisionProvenanceTrace | None,
    ) -> FinalDecisionTrace:
        """Build the final decision summary from the evaluation row and decision trace."""

        payload = self._decode_summary_payload(
            checks,
            check_type="decision",
            check_code="FINAL_DECISION",
            payload_key="final_decision",
        ) or {}
        eligible = payload.get("eligible")
        if eligible is None:
            overall_outcome = str(
                getattr(evaluation.overall_outcome, "value", evaluation.overall_outcome)
            )
            eligible = overall_outcome == "eligible"
        failure_codes = payload.get("failure_codes")
        if not isinstance(failure_codes, list):
            failure_codes = self._failure_codes_from_checks(checks)
        missing_facts = payload.get("missing_facts")
        if not isinstance(missing_facts, list):
            missing_facts = self._missing_facts_from_checks(checks)
        evidence_readiness = self._decode_summary_model(
            checks,
            check_type="evidence",
            check_code="EVIDENCE_READINESS",
            payload_key="evidence_readiness",
            model_cls=EvidenceReadinessResult,
        )
        missing_evidence = payload.get("missing_evidence")
        if not isinstance(missing_evidence, list):
            missing_evidence = (
                list(evidence_readiness.missing_items) if evidence_readiness is not None else []
            )
        readiness_score = payload.get("readiness_score")
        if readiness_score is None and evidence_readiness is not None:
            readiness_score = evidence_readiness.readiness_score
        completeness_ratio = payload.get("completeness_ratio")
        if completeness_ratio is None and evidence_readiness is not None:
            completeness_ratio = evidence_readiness.completeness_ratio
        return FinalDecisionTrace(
            eligible=bool(eligible),
            overall_outcome=evaluation.overall_outcome,
            pathway_used=payload.get("pathway_used", evaluation.pathway_used),
            rule_status=payload.get("rule_status", evaluation.rule_status_at_evaluation),
            tariff_status=payload.get("tariff_status", evaluation.tariff_status_at_evaluation),
            confidence_class=payload.get("confidence_class", evaluation.confidence_class),
            failure_codes=list(failure_codes),
            missing_facts=list(missing_facts),
            missing_evidence=list(missing_evidence),
            readiness_score=readiness_score,
            completeness_ratio=completeness_ratio,
            provenance=provenance,
        )

    async def _build_decision_provenance(
        self,
        checks: Sequence[EligibilityCheckResultResponse],
        *,
        evaluation_id: str,
    ) -> DecisionProvenanceTrace | None:
        """Roll rule and tariff provenance into one summary-level decision trace.

        When a ``sources_repository`` is available, thin provision summaries are fetched
        for each source reference and embedded directly in the trace so clients can traverse
        from decision replay to supporting legal text without a separate lookup step.
        """

        rule_payload = self._decode_summary_payload(
            checks,
            check_type="rule",
            check_code="PSR_RESOLUTION",
            payload_key="psr_rule",
        )
        tariff_payload = self._decode_summary_payload(
            checks,
            check_type="tariff",
            check_code="TARIFF_RESOLUTION",
            payload_key="tariff_resolution",
        )

        rule_trace = None
        if isinstance(rule_payload, dict):
            rule_source_id = rule_payload.get("source_id")
            rule_provisions = (
                await self._fetch_provision_summaries(
                    str(rule_source_id),
                    evaluation_id=evaluation_id,
                )
                if rule_source_id is not None
                else []
            )
            rule_trace = RuleProvenanceTrace(
                source_id=rule_source_id,
                page_ref=rule_payload.get("page_ref"),
                table_ref=rule_payload.get("table_ref"),
                row_ref=rule_payload.get("row_ref"),
                supporting_provisions=rule_provisions,
            )

        tariff_trace = None
        if isinstance(tariff_payload, dict):
            schedule_source_id = tariff_payload.get("schedule_source_id")
            tariff_provisions = (
                await self._fetch_provision_summaries(
                    str(schedule_source_id),
                    evaluation_id=evaluation_id,
                )
                if schedule_source_id is not None
                else []
            )
            tariff_trace = TariffProvenanceTrace(
                schedule_source_id=schedule_source_id,
                rate_source_id=tariff_payload.get("rate_source_id"),
                line_page_ref=tariff_payload.get("line_page_ref"),
                rate_page_ref=tariff_payload.get("rate_page_ref"),
                table_ref=tariff_payload.get("table_ref"),
                row_ref=tariff_payload.get("row_ref"),
                supporting_provisions=tariff_provisions,
            )

        if rule_trace is None and tariff_trace is None:
            return None
        return DecisionProvenanceTrace(rule=rule_trace, tariff=tariff_trace)

    async def _fetch_provision_summaries(
        self,
        source_id: str,
        *,
        evaluation_id: str,
    ) -> list[ProvisionSummary]:
        """Return thin provision summaries for one source, or an empty list when unavailable."""

        if self.sources_repository is None:
            return []
        try:
            rows = await self.sources_repository.get_provisions_for_source(source_id, limit=5)
            summaries: list[ProvisionSummary] = []
            for row in rows:
                row_data = dict(row)
                actual_source_id = row_data.get("source_id")
                if actual_source_id is not None and str(actual_source_id) != source_id:
                    logger.warning(
                        "Omitted provision summary with mismatched source_id: "
                        "evaluation_id=%s expected_source_id=%s actual_source_id=%s",
                        evaluation_id,
                        source_id,
                        actual_source_id,
                    )
                    continue
                summaries.append(ProvisionSummary.model_validate(row_data))
            return summaries
        except Exception:
            return []

    def _decode_summary_model(
        self,
        checks: Sequence[EligibilityCheckResultResponse],
        *,
        check_type: str,
        check_code: str,
        payload_key: str,
        model_cls: type[Any],
    ) -> Any | None:
        """Decode one summary-check payload into a typed Pydantic model."""

        payload = self._decode_summary_payload(
            checks,
            check_type=check_type,
            check_code=check_code,
            payload_key=payload_key,
        )
        if payload is None:
            return None
        return model_cls.model_validate(payload)

    def _decode_summary_payload(
        self,
        checks: Sequence[EligibilityCheckResultResponse],
        *,
        check_type: str,
        check_code: str,
        payload_key: str,
    ) -> dict[str, Any] | None:
        """Return the JSON payload nested under a summary-check details key."""

        for check in checks:
            if check.check_type != check_type or check.check_code != check_code:
                continue
            details = self._details(check)
            payload = details.get(payload_key)
            if isinstance(payload, dict):
                return payload
            if payload is None and payload_key in details:
                return None
        return None

    @staticmethod
    def _decimal_or_none(value: Any) -> Decimal | None:
        """Preserve decimal-like values from persisted payloads when present."""

        if value is None:
            return None
        return Decimal(str(value))

    @staticmethod
    def _tariff_status_from_payload(payload: dict[str, Any]) -> str:
        """Mirror the assessment tariff status precedence for replayed tariff summaries."""

        schedule_status = str(payload.get("schedule_status") or "").lower()
        if schedule_status in {"provisional", "draft", "superseded"}:
            return schedule_status
        if payload.get("tariff_status") is not None:
            return str(payload["tariff_status"])
        if payload.get("status") is not None:
            return str(payload["status"])
        return "unknown"

    @staticmethod
    def _tariff_provenance_ids_from_payload(payload: dict[str, Any]) -> list[str]:
        """Collect stable tariff provenance ids from explicit and legacy payload fields."""

        provenance_ids: list[str] = []

        explicit_ids = payload.get("provenance_ids")
        if isinstance(explicit_ids, list):
            for raw_value in explicit_ids:
                if raw_value is None:
                    continue
                value = str(raw_value)
                if value not in provenance_ids:
                    provenance_ids.append(value)

        for source_key in ("schedule_source_id", "rate_source_id"):
            raw_value = payload.get(source_key)
            if raw_value is None:
                continue
            value = str(raw_value)
            if value not in provenance_ids:
                provenance_ids.append(value)

        return provenance_ids

    @staticmethod
    def _details(check: EligibilityCheckResultResponse) -> dict[str, Any]:
        """Return a normalized details payload for one persisted check."""

        if isinstance(check.details_json, dict):
            return check.details_json
        return {}

    @staticmethod
    def _aggregate_atomic_result(checks: Sequence[EligibilityCheckResultResponse]) -> bool | None:
        """Collapse multiple atomic checks into one pathway-level pass/fail summary."""

        if not checks:
            return None
        if any(check.passed is False for check in checks):
            return False
        if all(check.passed is True for check in checks):
            return True
        return None

    @staticmethod
    def _derive_general_check_state(
        checks: Sequence[EligibilityCheckResultResponse],
        check_code: str,
    ) -> str | None:
        """Map persisted general-rule atomic checks back to rule-state labels."""

        for check in checks:
            if check.check_code != check_code:
                continue
            details = check.details_json or {}
            if isinstance(details, dict) and details.get("indeterminate") is True:
                if check_code == "DIRECT_TRANSPORT":
                    return "not_checked"
                return "not_applicable"
            if check.passed is True:
                return "pass"
            if check.passed is False:
                return "fail"
        return None

    @staticmethod
    def _failure_codes_from_checks(
        checks: Sequence[EligibilityCheckResultResponse],
    ) -> list[str]:
        """Extract canonical failure codes from persisted check details when present."""

        codes: list[str] = []
        for check in checks:
            details = check.details_json or {}
            if not isinstance(details, dict):
                continue
            failure_code = details.get("failure_code")
            if isinstance(failure_code, str) and failure_code not in codes:
                codes.append(failure_code)
            for code in details.get("failure_codes", []):
                if isinstance(code, str) and code not in codes:
                    codes.append(code)
        return codes

    @staticmethod
    def _missing_facts_from_checks(
        checks: Sequence[EligibilityCheckResultResponse],
    ) -> list[str]:
        """Extract missing facts captured in blocker or pathway trace details."""

        missing: list[str] = []
        for check in checks:
            details = check.details_json or {}
            if not isinstance(details, dict):
                continue
            values = details.get("missing_facts") or details.get("missing_variables") or []
            for value in values:
                if isinstance(value, str) and value not in missing:
                    missing.append(value)
        return missing

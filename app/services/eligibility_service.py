"""Orchestrate the full deterministic eligibility pipeline and persist audit checks."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from app.core.countries import V01_CORRIDORS
from app.core.entity_keys import make_entity_key
from app.core.enums import LegalOutcome
from app.core.exceptions import (
    CaseNotFoundError,
    CorridorNotSupportedError,
    EvaluationPersistenceError,
    InsufficientFactsError,
    TariffNotFoundError,
)
from app.core.failure_codes import FAILURE_CODES
from app.core.fact_keys import (
    DERIVED_VARIABLES,
    EVERY_NON_ORIGINATING_INPUT_FACTS,
    PRODUCTION_FACTS,
)
from app.schemas.assessments import (
    CaseAssessmentRequest,
    EligibilityAssessmentResponse,
    EligibilityRequest,
    TariffOutcomeResponse,
)
from app.schemas.rules import RulePathwayOut, RuleResolutionResult
from app.schemas.status import StatusOverlay
from app.schemas.tariffs import TariffResolutionResult
from app.services.expression_evaluator import AtomicCheck, ExpressionResult
from app.services.general_origin_rules_service import GeneralRulesResult

FAILURE_MESSAGES_TO_CODES = {message: code for code, message in FAILURE_CODES.items()}
PATHWAY_RULE_TYPES = {"WO", "CTH", "CTSH", "VNM", "VA", "PROCESS"}
MAX_PROVENANCE_PROVISIONS_PER_SOURCE = 5
MAX_PROVENANCE_TEXT_EXCERPT_CHARS = 280

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InterfaceAssessmentResult:
    """Assessment response plus explicit replay identifiers for interface callers."""

    response: EligibilityAssessmentResponse
    case_id: str
    evaluation_id: str
    pending_alert_specs: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class PreparedEvaluationPersistence:
    """Replay-critical payload captured during assessment for deferred persistence."""

    request: EligibilityRequest
    assessment_date: date
    rule_bundle: RuleResolutionResult
    pathway_used: str | None
    audit_checks: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class PreparedInterfaceAssessment:
    """Interface assessment plus deferred persistence payload after the read snapshot closes."""

    response: EligibilityAssessmentResponse
    case_id: str
    pending_alert_specs: tuple[dict[str, Any], ...] = ()
    evaluation_persistence: PreparedEvaluationPersistence | None = None


class EligibilityService:
    """Run the deterministic engine in the locked execution order."""

    def __init__(
        self,
        classification_service: Any,
        rule_resolution_service: Any,
        tariff_resolution_service: Any,
        status_service: Any,
        evidence_service: Any,
        fact_normalization_service: Any,
        expression_evaluator: Any,
        general_origin_rules_service: Any,
        cases_repository: Any | None,
        evaluations_repository: Any | None,
        sources_repository: Any | None = None,
        intelligence_service: Any | None = None,
        audit_service: Any | None = None,
    ) -> None:
        self.classification_service = classification_service
        self.rule_resolution_service = rule_resolution_service
        self.tariff_resolution_service = tariff_resolution_service
        self.status_service = status_service
        self.evidence_service = evidence_service
        self.fact_normalization_service = fact_normalization_service
        self.expression_evaluator = expression_evaluator
        self.general_origin_rules_service = general_origin_rules_service
        self.cases_repository = cases_repository
        self.evaluations_repository = evaluations_repository
        self.sources_repository = sources_repository
        self.intelligence_service = intelligence_service
        self.audit_service = audit_service
        self._last_persisted_evaluation_id: str | None = None
        self._last_pending_alert_specs: tuple[dict[str, Any], ...] = ()
        self._last_prepared_persistence: PreparedEvaluationPersistence | None = None
        self._last_persistence_failure_detail: dict[str, Any] | None = None

    async def assess_case(
        self,
        case_id: str,
        request: CaseAssessmentRequest,
        *,
        persist_evaluation: bool = True,
    ) -> EligibilityAssessmentResponse:
        """Load one stored case, rehydrate its facts, and assess it through the direct path.

        Because the hydrated request carries the originating case_id, both successful and
        failed engine outcomes follow the normal evaluation-persistence path.
        """

        eligibility_request = await self._build_request_from_case(
            case_id=case_id,
            year=request.year,
            existing_documents=request.existing_documents,
        )
        return await self.assess(
            eligibility_request,
            persist_evaluation=persist_evaluation,
        )

    async def assess_interface_request(
        self,
        request: EligibilityRequest,
    ) -> InterfaceAssessmentResult:
        """Guarantee a replayable persisted evaluation for interface-triggered direct runs."""

        self._last_persisted_evaluation_id = None
        self._last_pending_alert_specs = ()
        self._last_prepared_persistence = None
        self._last_persistence_failure_detail = None
        replayable_request = await self._ensure_replayable_request(request)
        response = await self.assess(replayable_request)
        evaluation_id = self._require_persisted_evaluation_id(replayable_request.case_id)
        return InterfaceAssessmentResult(
            response=response,
            case_id=str(replayable_request.case_id),
            evaluation_id=evaluation_id,
            pending_alert_specs=self._consume_pending_alert_specs(),
        )

    async def assess_interface_case(
        self,
        case_id: str,
        request: CaseAssessmentRequest,
    ) -> InterfaceAssessmentResult:
        """Return a case-backed assessment together with explicit replay identifiers."""

        self._last_persisted_evaluation_id = None
        self._last_pending_alert_specs = ()
        self._last_prepared_persistence = None
        self._last_persistence_failure_detail = None
        response = await self.assess_case(case_id, request)
        evaluation_id = self._require_persisted_evaluation_id(case_id)
        return InterfaceAssessmentResult(
            response=response,
            case_id=case_id,
            evaluation_id=evaluation_id,
            pending_alert_specs=self._consume_pending_alert_specs(),
        )

    async def prepare_interface_request_assessment(
        self,
        request: EligibilityRequest,
    ) -> PreparedInterfaceAssessment:
        """Compute one interface-triggered assessment and defer replay persistence."""

        self._last_persisted_evaluation_id = None
        self._last_pending_alert_specs = ()
        self._last_prepared_persistence = None
        self._last_persistence_failure_detail = None
        replayable_request = await self._ensure_replayable_request(request)
        response = await self.assess(replayable_request, persist_evaluation=False)
        return PreparedInterfaceAssessment(
            response=response,
            case_id=str(replayable_request.case_id),
            pending_alert_specs=self._consume_pending_alert_specs(),
            evaluation_persistence=self._require_prepared_persistence(
                str(replayable_request.case_id)
            ),
        )

    async def prepare_interface_case_assessment(
        self,
        case_id: str,
        request: CaseAssessmentRequest,
    ) -> PreparedInterfaceAssessment:
        """Compute one case-backed assessment and defer replay persistence."""

        self._last_persisted_evaluation_id = None
        self._last_pending_alert_specs = ()
        self._last_prepared_persistence = None
        self._last_persistence_failure_detail = None
        response = await self.assess_case(case_id, request, persist_evaluation=False)
        return PreparedInterfaceAssessment(
            response=response,
            case_id=case_id,
            pending_alert_specs=self._consume_pending_alert_specs(),
            evaluation_persistence=self._require_prepared_persistence(case_id),
        )

    async def finalize_prepared_interface_assessment(
        self,
        prepared: PreparedInterfaceAssessment,
    ) -> InterfaceAssessmentResult:
        """Persist one prepared assessment on a short-lived detached write session."""

        response = prepared.response.model_copy(deep=True)
        persistence = prepared.evaluation_persistence
        if persistence is None:
            raise EvaluationPersistenceError(
                "Prepared interface assessment did not capture a replayable evaluation payload",
                detail={"case_id": prepared.case_id, "reason": "evaluation_not_prepared"},
            )

        self._last_persisted_evaluation_id = None
        self._last_pending_alert_specs = ()
        self._last_prepared_persistence = None
        self._last_persistence_failure_detail = None
        response.audit_persisted = await self._persist_evaluation_if_possible(
            request=persistence.request,
            assessment_date=persistence.assessment_date,
            rule_bundle=persistence.rule_bundle,
            response=response,
            pathway_used=persistence.pathway_used,
            audit_checks=persistence.audit_checks,
        )
        evaluation_id = self._require_persisted_evaluation_id(prepared.case_id)
        return InterfaceAssessmentResult(
            response=response,
            case_id=prepared.case_id,
            evaluation_id=evaluation_id,
            pending_alert_specs=prepared.pending_alert_specs,
        )

    async def assess(
        self,
        request: EligibilityRequest,
        *,
        persist_evaluation: bool = True,
    ) -> EligibilityAssessmentResponse:
        """Execute one full assessment inside the caller's request-scoped DB snapshot."""

        self._last_persisted_evaluation_id = None
        self._last_pending_alert_specs = ()
        self._last_prepared_persistence = None
        self._last_persistence_failure_detail = None
        started_at = perf_counter()
        assessment_date = date(request.year, 1, 1)

        corridor = (request.exporter.upper(), request.importer.upper())
        if corridor not in V01_CORRIDORS:
            raise CorridorNotSupportedError(
                f"Corridor '{request.exporter.upper()}->{request.importer.upper()}' "
                "is not supported in v0.1.",
                detail={
                    "exporter": request.exporter.upper(),
                    "importer": request.importer.upper(),
                    "supported_corridors": [f"{e}->{i}" for e, i in V01_CORRIDORS],
                },
            )

        audit_checks: list[dict[str, Any]] = []
        product = await self.classification_service.resolve_hs6(
            request.hs6_code,
            request.hs_version,
        )
        audit_checks.append(
            self._make_audit_check(
                check_type="classification",
                check_code="HS6_RESOLUTION",
                passed=True,
                severity="info",
                expected_value=request.hs6_code,
                observed_value=product.hs6_code,
                explanation="Resolved input HS code to the canonical HS6 product",
                details_json={"product": product.model_dump(mode="json")},
            )
        )
        rule_bundle = await self.rule_resolution_service.resolve_rule_bundle_by_hs6_id(
            str(product.hs6_id),
            hs_version=request.hs_version,
            hs6_code=product.hs6_code,
            assessment_date=assessment_date,
        )
        audit_checks.append(
            self._make_audit_check(
                check_type="rule",
                check_code="PSR_RESOLUTION",
                passed=True,
                severity="info",
                expected_value=product.hs6_code,
                observed_value=str(rule_bundle.psr_rule.psr_id),
                explanation="Resolved the governing PSR rule bundle",
                details_json={
                    "psr_rule": rule_bundle.psr_rule.model_dump(mode="json"),
                    "applicability_type": rule_bundle.applicability_type,
                },
            )
        )

        corridor_key = make_entity_key(
            "corridor",
            exporter=request.exporter,
            importer=request.importer,
            hs6_code=product.hs6_code,
        )
        rule_key = make_entity_key("psr_rule", psr_id=rule_bundle.psr_rule.psr_id)
        try:
            tariff_lookup = await self.tariff_resolution_service.resolve_tariff_bundle(
                request.exporter,
                request.importer,
                request.hs_version,
                product.hs6_code,
                request.year,
                assessment_date=assessment_date,
            )
        except TariffNotFoundError as exc:
            tariff_lookup = exc
        status_overlays = await self.status_service.get_status_overlays(
            [
                ("corridor", corridor_key),
                ("psr_rule", rule_key),
            ],
            assessment_date,
        )
        corridor_overlay = status_overlays[("corridor", corridor_key)]
        rule_overlay = status_overlays[("psr_rule", rule_key)]

        tariff_result: TariffResolutionResult | None
        if isinstance(tariff_lookup, TariffNotFoundError):
            tariff_result = None
            audit_checks.append(
                self._make_audit_check(
                    check_type="tariff",
                    check_code="TARIFF_RESOLUTION",
                    passed=False,
                    severity="major",
                    expected_value=str(request.year),
                    observed_value="not found",
                    explanation="No tariff schedule was found for the requested corridor",
                    details_json={"tariff_outcome": None},
                )
            )
        elif isinstance(tariff_lookup, Exception):
            raise tariff_lookup
        else:
            tariff_result = tariff_lookup
            audit_checks.append(self._make_tariff_trace_check(tariff_result))

        blocker_checks, blocker_failure_codes, blocker_missing_facts = self._run_blocker_checks(
            rule_bundle=rule_bundle,
            production_facts=request.production_facts,
            tariff_result=tariff_result,
            corridor_overlay=corridor_overlay,
        )
        audit_checks.extend(blocker_checks)

        if self._has_hard_blocker(blocker_checks):
            response = EligibilityAssessmentResponse(
                hs6_code=product.hs6_code,
                eligible=False,
                pathway_used=None,
                rule_status=rule_bundle.psr_rule.rule_status,
                tariff_outcome=self._build_tariff_outcome(tariff_result),
                failures=blocker_failure_codes,
                missing_facts=blocker_missing_facts,
                evidence_required=[],
                missing_evidence=[],
                readiness_score=None,
                completeness_ratio=None,
                confidence_class=self._blocked_confidence_class(
                    rule_status=rule_bundle.psr_rule.rule_status,
                    corridor_overlay=corridor_overlay,
                    missing_facts=blocker_missing_facts,
                ),
            )
            audit_checks.append(self._make_decision_trace_check(response))
            response.audit_persisted = await self._persist_or_prepare_evaluation(
                request=request,
                assessment_date=assessment_date,
                rule_bundle=rule_bundle,
                response=response,
                pathway_used=None,
                audit_checks=audit_checks,
                persist_evaluation=persist_evaluation,
            )
            self._last_pending_alert_specs = self._build_pending_alert_specs_if_possible(
                request=request,
                rule_bundle=rule_bundle,
                tariff_result=tariff_result,
                corridor_overlay=corridor_overlay,
                response=response,
            )
            self._log_assessment(
                request=request,
                response=response,
                blocker_checks=blocker_checks,
                started_at=started_at,
            )
            return response

        normalized_facts = self.fact_normalization_service.normalize_facts(request.production_facts)

        selected_pathway: RulePathwayOut | None = None
        pathway_failure_codes: list[str] = []
        missing_facts: list[str] = []

        for pathway in sorted(rule_bundle.pathways, key=lambda item: item.priority_rank):
            expression = self._extract_pathway_expression(pathway.expression_json)
            if not self._is_executable_expression(expression):
                audit_checks.append(self._make_non_executable_pathway_check(pathway))
                continue
            evaluation = self.expression_evaluator.evaluate(expression, normalized_facts)
            audit_checks.extend(self._serialize_expression_checks(pathway, evaluation))
            audit_checks.append(self._make_pathway_trace_check(pathway, evaluation))
            missing_facts = self._merge_unique(missing_facts, evaluation.missing_variables)
            pathway_failure_codes = self._merge_unique(
                pathway_failure_codes,
                self._failure_codes_from_atomic_checks(evaluation.checks),
            )
            if evaluation.result is True:
                selected_pathway = pathway
                break

        general_rules_result: GeneralRulesResult | None = None
        if selected_pathway is not None:
            general_rules_result = self.general_origin_rules_service.evaluate(
                normalized_facts,
                selected_pathway,
            )
            audit_checks.extend(self._serialize_general_checks(general_rules_result))
            audit_checks.append(self._make_general_rules_summary_check(general_rules_result))
            if general_rules_result.direct_transport_check == "not_checked":
                missing_facts = self._merge_unique(missing_facts, ["direct_transport"])

        audit_checks.extend(self._serialize_status_overlay(rule_overlay))

        confidence_class = self._combine_confidence_class(
            base_confidence=rule_overlay.confidence_class,
            missing_facts=missing_facts,
        )
        evidence_result = await self._build_evidence_readiness(
            rule_bundle=rule_bundle,
            selected_pathway=selected_pathway,
            persona_mode=request.persona_mode,
            existing_documents=request.existing_documents,
            confidence_class=confidence_class,
            assessment_date=assessment_date,
        )
        audit_checks.append(self._make_evidence_trace_check(evidence_result))

        final_failure_codes = self._derive_final_failure_codes(
            selected_pathway=selected_pathway,
            pathway_failure_codes=pathway_failure_codes,
            general_rules_result=general_rules_result,
        )
        eligible = selected_pathway is not None and bool(
            general_rules_result is not None and general_rules_result.general_rules_passed
        )
        response = EligibilityAssessmentResponse(
            hs6_code=product.hs6_code,
            eligible=eligible,
            pathway_used=selected_pathway.pathway_code if selected_pathway is not None else None,
            rule_status=rule_bundle.psr_rule.rule_status,
            tariff_outcome=self._build_tariff_outcome(tariff_result),
            failures=final_failure_codes,
            missing_facts=missing_facts,
            evidence_required=evidence_result.required_items,
            missing_evidence=evidence_result.missing_items,
            readiness_score=evidence_result.readiness_score,
            completeness_ratio=evidence_result.completeness_ratio,
            confidence_class=confidence_class,
        )
        audit_checks.append(self._make_decision_trace_check(response))
        response.audit_persisted = await self._persist_or_prepare_evaluation(
            request=request,
            assessment_date=assessment_date,
            rule_bundle=rule_bundle,
            response=response,
            pathway_used=response.pathway_used,
            audit_checks=audit_checks,
            persist_evaluation=persist_evaluation,
        )
        self._last_pending_alert_specs = self._build_pending_alert_specs_if_possible(
            request=request,
            rule_bundle=rule_bundle,
            tariff_result=tariff_result,
            corridor_overlay=corridor_overlay,
            response=response,
        )
        self._log_assessment(
            request=request,
            response=response,
            blocker_checks=blocker_checks,
            started_at=started_at,
        )
        return response

    def _consume_pending_alert_specs(self) -> tuple[dict[str, Any], ...]:
        """Return and clear any advisory alert specs prepared during the last assessment."""

        pending = self._last_pending_alert_specs
        self._last_pending_alert_specs = ()
        return pending

    def _require_prepared_persistence(
        self,
        case_id: str,
    ) -> PreparedEvaluationPersistence:
        """Return and clear the deferred replay payload captured during assessment."""

        prepared = self._last_prepared_persistence
        self._last_prepared_persistence = None
        if prepared is None:
            raise EvaluationPersistenceError(
                "Interface assessment did not capture a replayable evaluation payload",
                detail={"case_id": case_id, "reason": "evaluation_not_prepared"},
            )
        return prepared

    async def _build_request_from_case(
        self,
        *,
        case_id: str,
        year: int,
        existing_documents: Sequence[str],
    ) -> EligibilityRequest:
        """Convert one stored case header plus facts into a standard assessment request."""

        if self.cases_repository is None:
            raise CaseNotFoundError(
                "Case-backed assessment is unavailable because no cases repository is configured",
                detail={"case_id": case_id},
            )

        case_bundle = await self.cases_repository.get_case_with_facts(case_id)
        if case_bundle is None:
            raise CaseNotFoundError(
                f"Case '{case_id}' was not found",
                detail={"case_id": case_id},
            )

        case_row = dict(case_bundle["case"])
        facts = [self._case_fact_to_request_fact(fact) for fact in case_bundle["facts"]]
        request_payload = {
            "hs6_code": case_row.get("hs_code"),
            "hs_version": case_row.get("hs_version") or "HS2017",
            "exporter": case_row.get("exporter_state"),
            "importer": case_row.get("importer_state"),
            "year": year,
            "persona_mode": case_row.get("persona_mode"),
            "production_facts": facts,
            "existing_documents": list(existing_documents),
            "case_id": case_id,
        }

        missing_fields = [
            field_name
            for field_name, value in {
                "hs6_code": request_payload["hs6_code"],
                "exporter": request_payload["exporter"],
                "importer": request_payload["importer"],
                "persona_mode": request_payload["persona_mode"],
            }.items()
            if value in {None, ""}
        ]
        if missing_fields:
            raise InsufficientFactsError(
                "Stored case is missing required assessment header fields",
                detail={"case_id": case_id, "missing_fields": missing_fields},
            )

        try:
            return EligibilityRequest.model_validate(request_payload)
        except ValidationError as exc:
            raise InsufficientFactsError(
                "Stored case could not be converted into a valid assessment request",
                detail={"case_id": case_id, "errors": exc.errors()},
            ) from exc

    @staticmethod
    def _case_fact_to_request_fact(fact: Any) -> Any:
        """Normalize one persisted case fact into the shared assessment fact schema."""

        payload = dict(fact)
        if "source_reference" in payload and "source_ref" not in payload:
            payload["source_ref"] = payload.pop("source_reference")
        return payload

    async def _ensure_replayable_request(self, request: EligibilityRequest) -> EligibilityRequest:
        """Ensure interface-triggered direct assessments always run with a persisted case_id."""

        if request.case_id is not None:
            return request

        if self.cases_repository is None:
            raise EvaluationPersistenceError(
                "Interface assessment cannot create a replayable case because cases persistence is unavailable",
                detail={"reason": "cases_repository_unavailable"},
            )

        try:
            case_id = await self.cases_repository.create_case(
                {
                    "case_external_ref": f"IFACE-ASSESS-{uuid4()}",
                    "persona_mode": request.persona_mode,
                    "exporter_state": request.exporter,
                    "importer_state": request.importer,
                    "hs6_code": request.hs6_code,
                    "hs_version": request.hs_version,
                    "submission_status": "submitted",
                    "title": "Interface-triggered eligibility assessment",
                    "created_by": "api:assessments",
                    "updated_by": "api:assessments",
                }
            )
        except Exception as exc:
            self._log_interface_persistence_failure(
                boundary="case_create",
                reason="case_create_failed",
                hs6_code=request.hs6_code,
                case_id=None,
                exc=exc,
            )
            raise EvaluationPersistenceError(
                "Interface assessment could not create a replayable case",
                detail={
                    "reason": "case_create_failed",
                    "hs6_code": request.hs6_code,
                },
            ) from exc

        try:
            await self.cases_repository.add_facts(
                case_id,
                [fact.model_dump(by_alias=True) for fact in request.production_facts],
                return_ids=False,
            )
        except Exception as exc:
            self._log_interface_persistence_failure(
                boundary="case_facts_persist",
                reason="case_facts_persist_failed",
                hs6_code=request.hs6_code,
                case_id=case_id,
                exc=exc,
            )
            raise EvaluationPersistenceError(
                "Interface assessment could not persist replayable case facts",
                detail={
                    "case_id": case_id,
                    "reason": "case_facts_persist_failed",
                    "hs6_code": request.hs6_code,
                },
            ) from exc
        return request.model_copy(update={"case_id": case_id})

    def _require_persisted_evaluation_id(self, case_id: str | None) -> str:
        """Return the in-transaction evaluation id captured during persistence."""

        if case_id is None:
            raise EvaluationPersistenceError(
                "Interface assessment completed without a case identifier",
                detail={"reason": "missing_case_id"},
            )

        if self._last_persisted_evaluation_id is None:
            raise EvaluationPersistenceError(
                "Interface assessment did not produce a replayable evaluation trail",
                detail=self._last_persistence_failure_detail
                or {"case_id": case_id, "reason": "evaluation_not_persisted"},
            )
        return self._last_persisted_evaluation_id

    def _log_interface_persistence_failure(
        self,
        *,
        boundary: str,
        reason: str,
        hs6_code: str | None,
        case_id: str | None,
        exc: Exception,
    ) -> None:
        """Emit one structured error log for interface persistence failures."""

        _logger.error(
            "assessment_interface_persistence_failed",
            exc_info=True,
            extra={
                "structured_data": {
                    "event": "assessment_interface_persistence_failed",
                    "boundary": boundary,
                    "reason": reason,
                    "hs6_code": hs6_code,
                    "case_id": case_id,
                }
            },
        )

    def _run_blocker_checks(
        self,
        *,
        rule_bundle: RuleResolutionResult,
        production_facts: Sequence[Any],
        tariff_result: TariffResolutionResult | None,
        corridor_overlay: StatusOverlay,
    ) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        """Evaluate blocker-stage checks before pathway execution."""

        checks: list[dict[str, Any]] = []
        failure_codes: list[str] = []
        missing_facts: list[str] = []
        rule_status = self._normalize_value(rule_bundle.psr_rule.rule_status)

        if rule_status in {"pending", "partially_agreed"}:
            checks.append(
                self._make_audit_check(
                    check_type="blocker",
                    check_code="RULE_STATUS",
                    passed=False,
                    severity="blocker",
                    expected_value="agreed or provisional",
                    observed_value=rule_status,
                    explanation=FAILURE_CODES["RULE_STATUS_PENDING"],
                    details_json={"failure_code": "RULE_STATUS_PENDING"},
                )
            )
            failure_codes = self._merge_unique(failure_codes, ["RULE_STATUS_PENDING"])

        if tariff_result is None:
            checks.append(
                self._make_audit_check(
                    check_type="blocker",
                    check_code="NO_SCHEDULE",
                    passed=False,
                    severity="blocker",
                    expected_value="tariff schedule available",
                    observed_value="not found",
                    explanation=FAILURE_CODES["NO_SCHEDULE"],
                    details_json={
                        "failure_code": "NO_SCHEDULE",
                        "blocked_before_pathway_evaluation": True,
                    },
                )
            )
            failure_codes = self._merge_unique(failure_codes, ["NO_SCHEDULE"])

        present_fact_keys = self._present_fact_keys(production_facts)
        pathway_missing = [
            self._missing_required_facts_for_pathway(pathway, present_fact_keys)
            for pathway in rule_bundle.pathways
        ]
        missing_pathways = [missing for missing in pathway_missing if missing]
        if missing_pathways and len(missing_pathways) == len(rule_bundle.pathways):
            missing_facts = self._merge_unique(*missing_pathways)
            checks.append(
                self._make_audit_check(
                    check_type="blocker",
                    check_code="MISSING_CORE_FACTS",
                    passed=False,
                    severity="blocker",
                    expected_value="core pathway facts present",
                    observed_value=", ".join(missing_facts),
                    explanation=FAILURE_CODES["MISSING_CORE_FACTS"],
                    details_json={
                        "failure_code": "MISSING_CORE_FACTS",
                        "missing_facts": missing_facts,
                    },
                )
            )
            failure_codes = self._merge_unique(failure_codes, ["MISSING_CORE_FACTS"])

        corridor_status = self._normalize_value(corridor_overlay.status_type)
        if corridor_status == "not_yet_operational":
            checks.append(
                self._make_audit_check(
                    check_type="blocker",
                    check_code="NOT_OPERATIONAL",
                    passed=False,
                    severity="blocker",
                    expected_value="operational corridor",
                    observed_value=corridor_status,
                    explanation=FAILURE_CODES["NOT_OPERATIONAL"],
                    details_json={"failure_code": "NOT_OPERATIONAL"},
                )
            )
            failure_codes = self._merge_unique(failure_codes, ["NOT_OPERATIONAL"])

        return checks, failure_codes, missing_facts

    @staticmethod
    def _has_hard_blocker(checks: Sequence[Mapping[str, Any]]) -> bool:
        """Return True when any blocker-severity check failed."""

        return any(
            check.get("severity") == "blocker" and check.get("passed") is False for check in checks
        )

    def _present_fact_keys(self, production_facts: Sequence[Any]) -> set[str]:
        """Collect submitted fact keys from request payloads."""

        keys: set[str] = set()
        for fact in production_facts:
            fact_key = self._read_fact_field(
                fact,
                "fact_key",
            ) or self._read_fact_field(fact, "fact_type")
            if fact_key:
                keys.add(str(fact_key))
        return keys

    def _missing_required_facts_for_pathway(
        self,
        pathway: RulePathwayOut,
        present_fact_keys: set[str],
    ) -> list[str]:
        """Return the list of core facts absent for a given pathway."""

        required = self._required_facts_for_pathway(pathway)
        return [fact_key for fact_key in required if fact_key not in present_fact_keys]

    def _required_facts_for_pathway(self, pathway: RulePathwayOut) -> list[str]:
        """Infer required facts from pathway labels plus expression_json structure."""

        expression = self._extract_pathway_expression(pathway.expression_json)
        expression_required = self._required_facts_from_expression(expression)
        if self._is_executable_expression(expression) and expression_required:
            return expression_required

        required: list[str] = []
        pathway_markers = {
            marker
            for marker in PATHWAY_RULE_TYPES
            if marker in pathway.pathway_code.upper() or marker in pathway.pathway_label.upper()
        }
        for fact_key, metadata in PRODUCTION_FACTS.items():
            rule_types = {entry.upper() for entry in metadata.get("required_for", [])}
            if rule_types.intersection(pathway_markers):
                required = self._merge_unique(required, [fact_key])

        return required

    def _required_facts_from_expression(self, expression: Any) -> list[str]:
        """Walk the supported expression tree to extract referenced facts."""

        if not isinstance(expression, dict):
            return []

        op = expression.get("op")
        if op in {"all", "any"}:
            required: list[str] = []
            for child in expression.get("args", []):
                required = self._merge_unique(required, self._required_facts_from_expression(child))
            return required

        if op in {"formula_lte", "formula_gte"}:
            formula = expression.get("formula")
            if formula in DERIVED_VARIABLES:
                return ["ex_works", "non_originating"]
            return [str(formula)] if isinstance(formula, str) else []

        if op == "fact_eq":
            fact_name = expression.get("fact")
            return [str(fact_name)] if isinstance(fact_name, str) else []

        if op == "fact_ne":
            required: list[str] = []
            fact_name = expression.get("fact")
            ref_fact = expression.get("ref_fact")
            if isinstance(fact_name, str):
                required.append(fact_name)
            if isinstance(ref_fact, str):
                required.append(ref_fact)
            return required

        if op == "every_non_originating_input":
            return list(EVERY_NON_ORIGINATING_INPUT_FACTS)

        return []

    @staticmethod
    def _extract_pathway_expression(expression_json: dict[str, Any]) -> dict[str, Any]:
        """Unwrap the nested pathway JSON shape used by the stored rule pathways."""

        if "op" in expression_json:
            return expression_json
        nested = expression_json.get("expression")
        if isinstance(nested, dict):
            return nested
        return expression_json

    @staticmethod
    def _is_executable_expression(expression: Any) -> bool:
        """Return True when the stored pathway contains an executable expression tree."""

        return isinstance(expression, dict) and isinstance(expression.get("op"), str)

    def _make_non_executable_pathway_check(self, pathway: RulePathwayOut) -> dict[str, Any]:
        """Record that a manual-review-only pathway was skipped during execution."""

        return self._make_audit_check(
            check_type="psr",
            check_code="PATHWAY_SKIPPED",
            passed=False,
            severity="minor",
            expected_value="executable expression",
            observed_value="manual review required",
            explanation=(
                f"Skipped pathway {pathway.pathway_code} because it does not contain an executable expression"
            ),
            details_json={
                "pathway_id": str(pathway.pathway_id),
                "pathway_code": pathway.pathway_code,
                "pathway_label": pathway.pathway_label,
                "priority_rank": pathway.priority_rank,
                "expression_json": pathway.expression_json,
            },
        )

    def _serialize_expression_checks(
        self,
        pathway: RulePathwayOut,
        result: ExpressionResult,
    ) -> list[dict[str, Any]]:
        """Convert evaluator atomic checks to persisted audit rows."""

        checks: list[dict[str, Any]] = []
        for check in result.checks:
            passed = check.passed if check.passed is not None else False
            details_json: dict[str, Any] | None = {
                "pathway_id": str(pathway.pathway_id),
                "pathway_code": pathway.pathway_code,
                "pathway_label": pathway.pathway_label,
                "priority_rank": pathway.priority_rank,
                "evaluated_expression": result.evaluated_expression,
                "missing_variables": result.missing_variables,
            }
            if check.passed is None:
                details_json["indeterminate"] = True
            checks.append(
                self._make_audit_check(
                    check_type="psr",
                    check_code=check.check_code,
                    passed=passed,
                    severity=self._severity_for_atomic_check(check),
                    expected_value=check.expected_value,
                    observed_value=check.observed_value,
                    explanation=check.explanation,
                    details_json=details_json,
                )
            )
        return checks

    def _serialize_general_checks(self, result: GeneralRulesResult) -> list[dict[str, Any]]:
        """Convert general-origin checks to persisted audit rows."""

        checks: list[dict[str, Any]] = []
        for check in result.checks:
            passed = check.passed if check.passed is not None else False
            details_json: dict[str, Any] | None = None
            if check.passed is None:
                details_json = {"indeterminate": True}
            checks.append(
                self._make_audit_check(
                    check_type="general_rule",
                    check_code=check.check_code,
                    passed=passed,
                    severity="major" if check.passed is False else "info",
                    expected_value=check.expected_value,
                    observed_value=check.observed_value,
                    explanation=check.explanation,
                    details_json=details_json,
                )
            )
        return checks

    def _serialize_status_overlay(self, overlay: StatusOverlay) -> list[dict[str, Any]]:
        """Convert the final status overlay into one persisted audit check."""

        status_type = self._normalize_value(overlay.status_type)
        passed = status_type in {"agreed", "in_force"}
        severity = "info" if passed else "minor"
        explanation = overlay.source_text_verbatim or (
            "; ".join(overlay.constraints) if overlay.constraints else f"Status is {status_type}"
        )
        return [
            self._make_audit_check(
                check_type="status",
                check_code="STATUS_OVERLAY",
                passed=passed,
                severity=severity,
                expected_value="agreed or in_force",
                observed_value=status_type,
                explanation=explanation,
                details_json={"overlay": overlay.model_dump(mode="json")},
            )
        ]

    @staticmethod
    def _severity_for_atomic_check(check: AtomicCheck) -> str:
        """Map PSR atomic checks to audit severities."""

        if check.passed is False:
            return "major"
        return "info"

    def _derive_final_failure_codes(
        self,
        *,
        selected_pathway: RulePathwayOut | None,
        pathway_failure_codes: Sequence[str],
        general_rules_result: GeneralRulesResult | None,
    ) -> list[str]:
        """Return only business-result failure codes, excluding warnings."""

        if selected_pathway is None:
            return list(pathway_failure_codes)
        if general_rules_result is None:
            return []
        return list(general_rules_result.failure_codes)

    def _build_tariff_outcome(
        self,
        tariff_result: TariffResolutionResult | None,
    ) -> TariffOutcomeResponse | None:
        """Collapse the tariff bundle into the API contract."""

        if tariff_result is None:
            return None

        return TariffOutcomeResponse(
            preferential_rate=tariff_result.preferential_rate,
            base_rate=tariff_result.base_rate,
            status=self._tariff_status_for_response(tariff_result),
            provenance_ids=[str(source_id) for source_id in tariff_result.provenance_ids],
        )

    def _tariff_status_for_response(self, tariff_result: TariffResolutionResult) -> str:
        """Prefer schedule-level provisional states over the year-rate status."""

        schedule_status = self._normalize_value(tariff_result.schedule_status)
        if schedule_status in {"provisional", "draft", "superseded"}:
            return schedule_status
        return self._normalize_value(tariff_result.tariff_status)

    @staticmethod
    def _combine_confidence_class(
        *,
        base_confidence: str,
        missing_facts: Sequence[str],
    ) -> str:
        """Downgrade confidence when facts are missing."""

        if missing_facts:
            return "incomplete"
        return base_confidence

    def _blocked_confidence_class(
        self,
        *,
        rule_status: Any,
        corridor_overlay: StatusOverlay,
        missing_facts: Sequence[str],
    ) -> str:
        """Resolve confidence when the assessment stops at the blocker stage."""

        if (
            missing_facts
            or self._normalize_value(corridor_overlay.status_type) == "not_yet_operational"
        ):
            return "incomplete"
        if self._normalize_value(rule_status) in {"pending", "partially_agreed", "provisional"}:
            return "provisional"
        return corridor_overlay.confidence_class

    async def _build_evidence_readiness(
        self,
        *,
        rule_bundle: RuleResolutionResult,
        selected_pathway: RulePathwayOut | None,
        persona_mode: str,
        existing_documents: Sequence[str],
        confidence_class: str | None,
        assessment_date: date,
    ) -> Any:
        """Resolve readiness from the most specific evidence target with compatibility fallbacks."""

        return await self.evidence_service.build_readiness_for_targets(
            self._resolve_evidence_targets(
                rule_bundle=rule_bundle,
                selected_pathway=selected_pathway,
            ),
            persona_mode=persona_mode,
            existing_documents=list(existing_documents),
            confidence_class=confidence_class,
            assessment_date=assessment_date,
        )

    def _resolve_evidence_targets(
        self,
        *,
        rule_bundle: RuleResolutionResult,
        selected_pathway: RulePathwayOut | None,
    ) -> list[tuple[str, str]]:
        """Choose evidence lookup targets from most specific to compatibility fallback."""

        if selected_pathway is not None:
            return [
                ("pathway", make_entity_key("pathway", pathway_id=selected_pathway.pathway_id)),
                ("hs6_rule", make_entity_key("hs6_rule", psr_id=rule_bundle.psr_rule.psr_id)),
                ("rule_type", selected_pathway.pathway_code),
            ]
        return [("hs6_rule", make_entity_key("hs6_rule", psr_id=rule_bundle.psr_rule.psr_id))]

    @staticmethod
    def _evidence_result_has_content(result: Any) -> bool:
        """Return True when a readiness result includes actual requirements or questions."""

        required_items = getattr(result, "required_items", None)
        verification_questions = getattr(result, "verification_questions", None)
        return bool(required_items or verification_questions)

    async def _attach_provenance_snapshots(
        self,
        audit_checks: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Attach immutable provenance snapshots to persisted summary checks.

        New replay-safe evaluations must freeze rule and tariff provenance before
        the assessment leaves the request-scoped snapshot. When that cannot be
        done, the evaluation may still be legally correct but it must not be
        treated as replay-safe.
        """

        snapshot_cache: dict[str, dict[str, Any] | None] = {}
        captured_at = datetime.now(timezone.utc).isoformat()

        rule_check = self._select_snapshot_check(
            audit_checks,
            check_type="rule",
            check_code="PSR_RESOLUTION",
        )
        rule_failure = await self._attach_rule_provenance_snapshot(
            rule_check,
            snapshot_cache=snapshot_cache,
            captured_at=captured_at,
        )
        if rule_failure is not None:
            return rule_failure

        tariff_check = self._select_snapshot_check(
            audit_checks,
            check_type="tariff",
            check_code="TARIFF_RESOLUTION",
        )
        tariff_failure = await self._attach_tariff_provenance_snapshot(
            tariff_check,
            snapshot_cache=snapshot_cache,
            captured_at=captured_at,
        )
        if tariff_failure is not None:
            return tariff_failure

        return None

    async def _attach_rule_provenance_snapshot(
        self,
        summary_check: Mapping[str, Any] | None,
        *,
        snapshot_cache: dict[str, dict[str, Any] | None],
        captured_at: str,
    ) -> dict[str, Any] | None:
        """Freeze the rule provenance snapshot required for replay-safe persistence."""

        if summary_check is None:
            return None

        details = summary_check.get("details_json")
        if not isinstance(details, dict):
            return None
        if "provenance_snapshot" in details:
            return None

        payload = details.get("psr_rule")
        if not isinstance(payload, Mapping):
            return None

        source_id = payload.get("source_id")
        if source_id is None:
            return self._provenance_failure_detail(
                check_code="PSR_RESOLUTION",
                reason="missing_source_id",
            )

        source_snapshot = await self._load_source_snapshot(
            str(source_id),
            snapshot_cache=snapshot_cache,
        )
        if source_snapshot is None:
            return self._provenance_failure_detail(
                check_code="PSR_RESOLUTION",
                reason="source_snapshot_missing",
                source_id=str(source_id),
            )

        details["provenance_snapshot"] = {
            "source_id": source_id,
            "short_title": source_snapshot.get("short_title"),
            "version_label": source_snapshot.get("version_label"),
            "publication_date": source_snapshot.get("publication_date"),
            "effective_date": source_snapshot.get("effective_date"),
            "page_ref": payload.get("page_ref"),
            "table_ref": payload.get("table_ref"),
            "row_ref": payload.get("row_ref"),
            "captured_at": captured_at,
            "supporting_provisions": list(source_snapshot.get("supporting_provisions", [])),
        }
        return None

    async def _attach_tariff_provenance_snapshot(
        self,
        summary_check: Mapping[str, Any] | None,
        *,
        snapshot_cache: dict[str, dict[str, Any] | None],
        captured_at: str,
    ) -> dict[str, Any] | None:
        """Freeze the tariff provenance snapshot required for replay-safe persistence."""

        if summary_check is None:
            return None

        details = summary_check.get("details_json")
        if not isinstance(details, dict):
            return None
        if "provenance_snapshot" in details:
            return None

        payload = details.get("tariff_resolution")
        if not isinstance(payload, Mapping):
            return None

        schedule_source_id = payload.get("schedule_source_id")
        rate_source_id = payload.get("rate_source_id")
        if schedule_source_id is None:
            return self._provenance_failure_detail(
                check_code="TARIFF_RESOLUTION",
                reason="missing_schedule_source_id",
            )
        if rate_source_id is None:
            return self._provenance_failure_detail(
                check_code="TARIFF_RESOLUTION",
                reason="missing_rate_source_id",
                source_id=str(schedule_source_id),
            )

        schedule_snapshot = await self._load_source_snapshot(
            str(schedule_source_id),
            snapshot_cache=snapshot_cache,
        )
        if schedule_snapshot is None:
            return self._provenance_failure_detail(
                check_code="TARIFF_RESOLUTION",
                reason="schedule_source_snapshot_missing",
                source_id=str(schedule_source_id),
            )

        supporting_provisions = list(schedule_snapshot.get("supporting_provisions", []))
        if str(rate_source_id) != str(schedule_source_id):
            rate_snapshot = await self._load_source_snapshot(
                str(rate_source_id),
                snapshot_cache=snapshot_cache,
            )
            if rate_snapshot is None:
                return self._provenance_failure_detail(
                    check_code="TARIFF_RESOLUTION",
                    reason="rate_source_snapshot_missing",
                    source_id=str(rate_source_id),
                )
            supporting_provisions.extend(rate_snapshot.get("supporting_provisions", []))

        details["provenance_snapshot"] = {
            "schedule_source_id": schedule_source_id,
            "rate_source_id": rate_source_id,
            "short_title": schedule_snapshot.get("short_title"),
            "version_label": schedule_snapshot.get("version_label"),
            "publication_date": schedule_snapshot.get("publication_date"),
            "effective_date": schedule_snapshot.get("effective_date"),
            "line_page_ref": payload.get("line_page_ref"),
            "rate_page_ref": payload.get("rate_page_ref"),
            "table_ref": payload.get("table_ref"),
            "row_ref": payload.get("row_ref"),
            "captured_at": captured_at,
            "supporting_provisions": supporting_provisions,
        }
        return None

    async def _load_source_snapshot(
        self,
        source_id: str,
        *,
        snapshot_cache: dict[str, dict[str, Any] | None],
    ) -> dict[str, Any] | None:
        """Load and normalize one thin provenance snapshot for a source."""

        if source_id in snapshot_cache:
            return snapshot_cache[source_id]

        if self.sources_repository is None:
            snapshot_cache[source_id] = None
            return None

        try:
            raw_snapshot = await self.sources_repository.get_source_snapshot(source_id)
        except Exception:
            raw_snapshot = None

        normalized = (
            self._normalize_source_snapshot(raw_snapshot)
            if isinstance(raw_snapshot, Mapping)
            else None
        )
        snapshot_cache[source_id] = normalized
        return normalized

    @staticmethod
    def _normalize_source_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any] | None:
        """Normalize one repository source snapshot into the persisted thin shape."""

        source = snapshot.get("source")
        if not isinstance(source, Mapping):
            return None

        normalized_provisions = EligibilityService._normalize_supporting_provisions(
            snapshot.get("supporting_provisions")
        )
        return {
            "source_id": source.get("source_id"),
            "short_title": source.get("short_title"),
            "version_label": source.get("version_label"),
            "publication_date": source.get("publication_date"),
            "effective_date": source.get("effective_date"),
            "supporting_provisions": normalized_provisions,
        }

    @staticmethod
    def _normalize_supporting_provisions(provisions: Any) -> list[dict[str, Any]]:
        """Bound and normalize provision summaries for persisted provenance snapshots."""

        if not isinstance(provisions, Sequence):
            return []

        normalized_rows: list[dict[str, Any]] = []
        for provision in provisions:
            if not isinstance(provision, Mapping):
                continue
            payload = dict(provision)
            normalized_rows.append(
                {
                    "provision_id": payload.get("provision_id"),
                    "source_id": payload.get("source_id"),
                    "article_label": payload.get("article_label") or payload.get("article_ref"),
                    "clause_label": (
                        payload.get("clause_label")
                        or payload.get("subsection_ref")
                        or payload.get("section_ref")
                        or payload.get("annex_ref")
                        or payload.get("appendix_ref")
                    ),
                    "topic_primary": payload.get("topic_primary"),
                    "text_excerpt": EligibilityService._truncate_provision_excerpt(
                        payload.get("text_excerpt")
                        or payload.get("provision_text_verbatim")
                        or payload.get("provision_text_normalized")
                    ),
                    "_authority_weight": float(payload.get("authority_weight") or 0),
                }
            )

        normalized_rows.sort(
            key=lambda item: (
                str(item.get("source_id") or ""),
                -item.get("_authority_weight", 0),
                str(item.get("article_label") or ""),
                str(item.get("clause_label") or ""),
                str(item.get("provision_id") or ""),
            )
        )
        bounded_rows: list[dict[str, Any]] = []
        per_source_counts: dict[str, int] = {}
        for item in normalized_rows:
            item.pop("_authority_weight", None)
            source_key = str(item.get("source_id") or "")
            current_count = per_source_counts.get(source_key, 0)
            if current_count >= MAX_PROVENANCE_PROVISIONS_PER_SOURCE:
                continue
            per_source_counts[source_key] = current_count + 1
            bounded_rows.append(item)
        return bounded_rows

    @staticmethod
    def _truncate_provision_excerpt(value: Any) -> str | None:
        """Trim one supporting provision text field to the replay snapshot budget."""

        if value is None:
            return None
        text = str(value).strip()
        if len(text) <= MAX_PROVENANCE_TEXT_EXCERPT_CHARS:
            return text
        return text[: MAX_PROVENANCE_TEXT_EXCERPT_CHARS - 3].rstrip() + "..."

    @staticmethod
    def _provenance_failure_detail(
        *,
        check_code: str,
        reason: str,
        source_id: str | None = None,
    ) -> dict[str, Any]:
        """Build one structured persistence-failure payload for replay safety."""

        detail = {
            "reason": "provenance_snapshot_unavailable",
            "check_code": check_code,
            "failure_stage": reason,
        }
        if source_id is not None:
            detail["source_id"] = source_id
        return detail

    def _build_decision_snapshot(
        self,
        audit_checks: Sequence[Mapping[str, Any]],
        *,
        selected_pathway_code: str | None,
    ) -> dict[str, Any]:
        """Collapse the replay-critical audit trace into one compact persisted payload."""

        snapshot: dict[str, Any] = {
            "snapshot_version": 1,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        summary_targets = {
            "classification_check": ("classification", "HS6_RESOLUTION"),
            "rule_check": ("rule", "PSR_RESOLUTION"),
            "general_rules_check": ("general_rule", "GENERAL_RULES_SUMMARY"),
            "status_check": ("status", "STATUS_OVERLAY"),
            "tariff_check": ("tariff", "TARIFF_RESOLUTION"),
            "evidence_check": ("evidence", "EVIDENCE_READINESS"),
            "final_decision_check": ("decision", "FINAL_DECISION"),
        }
        for snapshot_key, (check_type, check_code) in summary_targets.items():
            check = self._select_snapshot_check(
                audit_checks,
                check_type=check_type,
                check_code=check_code,
            )
            if check is not None:
                snapshot[snapshot_key] = self._snapshot_check_payload(check)

        selected_pathway_check = self._select_selected_pathway_check(
            audit_checks,
            selected_pathway_code=selected_pathway_code,
        )
        if selected_pathway_check is not None:
            snapshot["selected_pathway_check"] = self._snapshot_check_payload(
                selected_pathway_check
            )

        blocker_checks = [
            self._snapshot_check_payload(check)
            for check in audit_checks
            if check.get("check_type") == "blocker" and check.get("passed") is False
        ]
        if blocker_checks:
            snapshot["blocker_checks"] = blocker_checks

        return jsonable_encoder(snapshot)

    @staticmethod
    def _select_snapshot_check(
        audit_checks: Sequence[Mapping[str, Any]],
        *,
        check_type: str,
        check_code: str,
    ) -> Mapping[str, Any] | None:
        """Return the first summary check matching the given type/code pair."""

        return next(
            (
                check
                for check in audit_checks
                if check.get("check_type") == check_type and check.get("check_code") == check_code
            ),
            None,
        )

    @staticmethod
    def _snapshot_check_payload(check: Mapping[str, Any]) -> dict[str, Any]:
        """Trim one in-memory audit check down to its persisted replay fields."""

        return jsonable_encoder(
            {
                "check_type": check.get("check_type"),
                "check_code": check.get("check_code"),
                "passed": check.get("passed"),
                "severity": check.get("severity"),
                "expected_value": check.get("expected_value"),
                "observed_value": check.get("observed_value"),
                "explanation": check.get("explanation"),
                "details_json": EligibilityService._compact_snapshot_details(
                    check_type=check.get("check_type"),
                    check_code=check.get("check_code"),
                    details=check.get("details_json"),
                ),
                "linked_component_id": check.get("linked_component_id"),
            }
        )

    @staticmethod
    def _compact_snapshot_details(
        *,
        check_type: Any,
        check_code: Any,
        details: Any,
    ) -> dict[str, Any] | None:
        """Persist only the replay-critical subset of each summary payload."""

        if not isinstance(details, Mapping):
            return None

        if check_type == "classification" and check_code == "HS6_RESOLUTION":
            product = details.get("product")
            if isinstance(product, Mapping):
                return {
                    "product": {
                        "hs6_id": product.get("hs6_id"),
                        "hs_version": product.get("hs_version"),
                        "hs6_code": product.get("hs6_code"),
                        "hs6_display": product.get("hs6_display"),
                        "chapter": product.get("chapter"),
                        "heading": product.get("heading"),
                        "description": product.get("description"),
                        "section": product.get("section"),
                        "section_name": product.get("section_name"),
                    }
                }
            return None

        if check_type == "rule" and check_code == "PSR_RESOLUTION":
            psr_rule = details.get("psr_rule")
            payload: dict[str, Any] = {
                "psr_rule": dict(psr_rule) if isinstance(psr_rule, Mapping) else None,
            }
            if "applicability_type" in details:
                payload["applicability_type"] = details.get("applicability_type")
            provenance_snapshot = EligibilityService._compact_provenance_snapshot(
                details.get("provenance_snapshot")
            )
            if provenance_snapshot is not None:
                payload["provenance_snapshot"] = provenance_snapshot
            return payload

        if check_type == "pathway" and check_code == "PATHWAY_EVALUATION":
            pathway = details.get("pathway")
            return {
                "pathway": (
                    {
                        "pathway_id": pathway.get("pathway_id"),
                        "pathway_code": pathway.get("pathway_code"),
                        "pathway_label": pathway.get("pathway_label"),
                        "priority_rank": pathway.get("priority_rank"),
                    }
                    if isinstance(pathway, Mapping)
                    else None
                ),
                "result": details.get("result"),
                "evaluated_expression": details.get("evaluated_expression"),
                "missing_variables": details.get("missing_variables", []),
                **(
                    {"indeterminate": True}
                    if details.get("indeterminate") is True
                    else {}
                ),
            }

        if check_type == "tariff" and check_code == "TARIFF_RESOLUTION":
            tariff_resolution = details.get("tariff_resolution")
            if isinstance(tariff_resolution, Mapping):
                payload = {
                    "tariff_resolution": {
                        "preferential_rate": tariff_resolution.get("preferential_rate"),
                        "base_rate": tariff_resolution.get("base_rate"),
                        "schedule_status": tariff_resolution.get("schedule_status"),
                        "tariff_status": tariff_resolution.get("tariff_status"),
                        "provenance_ids": tariff_resolution.get("provenance_ids", []),
                        "schedule_source_id": tariff_resolution.get("schedule_source_id"),
                        "rate_source_id": tariff_resolution.get("rate_source_id"),
                        "line_page_ref": tariff_resolution.get("line_page_ref"),
                        "rate_page_ref": tariff_resolution.get("rate_page_ref"),
                        "table_ref": tariff_resolution.get("table_ref"),
                        "row_ref": tariff_resolution.get("row_ref"),
                        "resolved_rate_year": tariff_resolution.get("resolved_rate_year"),
                        "used_fallback_rate": tariff_resolution.get("used_fallback_rate", False),
                    }
                }
                provenance_snapshot = EligibilityService._compact_provenance_snapshot(
                    details.get("provenance_snapshot")
                )
                if provenance_snapshot is not None:
                    payload["provenance_snapshot"] = provenance_snapshot
                return payload
            tariff_outcome = details.get("tariff_outcome")
            if isinstance(tariff_outcome, Mapping):
                payload = {"tariff_outcome": dict(tariff_outcome)}
                provenance_snapshot = EligibilityService._compact_provenance_snapshot(
                    details.get("provenance_snapshot")
                )
                if provenance_snapshot is not None:
                    payload["provenance_snapshot"] = provenance_snapshot
                return payload
            return None

        return dict(details)

    @staticmethod
    def _compact_provenance_snapshot(snapshot: Any) -> dict[str, Any] | None:
        """Persist only the bounded provenance snapshot fields needed for replay."""

        if not isinstance(snapshot, Mapping):
            return None

        supporting_provisions = EligibilityService._compact_supporting_provisions(
            snapshot.get("supporting_provisions")
        )
        if "schedule_source_id" in snapshot or "rate_source_id" in snapshot:
            return {
                "schedule_source_id": snapshot.get("schedule_source_id"),
                "rate_source_id": snapshot.get("rate_source_id"),
                "short_title": snapshot.get("short_title"),
                "version_label": snapshot.get("version_label"),
                "publication_date": snapshot.get("publication_date"),
                "effective_date": snapshot.get("effective_date"),
                "line_page_ref": snapshot.get("line_page_ref"),
                "rate_page_ref": snapshot.get("rate_page_ref"),
                "table_ref": snapshot.get("table_ref"),
                "row_ref": snapshot.get("row_ref"),
                "captured_at": snapshot.get("captured_at"),
                "supporting_provisions": supporting_provisions,
            }

        return {
            "source_id": snapshot.get("source_id"),
            "short_title": snapshot.get("short_title"),
            "version_label": snapshot.get("version_label"),
            "publication_date": snapshot.get("publication_date"),
            "effective_date": snapshot.get("effective_date"),
            "page_ref": snapshot.get("page_ref"),
            "table_ref": snapshot.get("table_ref"),
            "row_ref": snapshot.get("row_ref"),
            "captured_at": snapshot.get("captured_at"),
            "supporting_provisions": supporting_provisions,
        }

    @staticmethod
    def _compact_supporting_provisions(provisions: Any) -> list[dict[str, Any]]:
        """Trim supporting provisions to the thin persisted shape while preserving order."""

        if not isinstance(provisions, Sequence):
            return []

        compacted_rows: list[dict[str, Any]] = []
        per_source_counts: dict[str, int] = {}
        for provision in provisions:
            if not isinstance(provision, Mapping):
                continue

            payload = dict(provision)
            source_key = str(payload.get("source_id") or "")
            current_count = per_source_counts.get(source_key, 0)
            if current_count >= MAX_PROVENANCE_PROVISIONS_PER_SOURCE:
                continue

            per_source_counts[source_key] = current_count + 1
            compacted_rows.append(
                {
                    "provision_id": payload.get("provision_id"),
                    "source_id": payload.get("source_id"),
                    "article_label": payload.get("article_label") or payload.get("article_ref"),
                    "clause_label": (
                        payload.get("clause_label")
                        or payload.get("subsection_ref")
                        or payload.get("section_ref")
                        or payload.get("annex_ref")
                        or payload.get("appendix_ref")
                    ),
                    "topic_primary": payload.get("topic_primary"),
                    "text_excerpt": EligibilityService._truncate_provision_excerpt(
                        payload.get("text_excerpt")
                        or payload.get("provision_text_verbatim")
                        or payload.get("provision_text_normalized")
                    ),
                }
            )

        return compacted_rows

    def _select_selected_pathway_check(
        self,
        audit_checks: Sequence[Mapping[str, Any]],
        *,
        selected_pathway_code: str | None,
    ) -> Mapping[str, Any] | None:
        """Return the summary row for the chosen pathway when one exists."""

        pathway_checks = [
            check
            for check in audit_checks
            if check.get("check_type") == "pathway"
            and check.get("check_code") == "PATHWAY_EVALUATION"
        ]
        if not pathway_checks:
            return None
        if selected_pathway_code is None:
            return next((check for check in pathway_checks if check.get("passed") is True), None)

        for check in pathway_checks:
            details = check.get("details_json")
            if not isinstance(details, Mapping):
                continue
            pathway = details.get("pathway")
            if not isinstance(pathway, Mapping):
                continue
            if pathway.get("pathway_code") == selected_pathway_code:
                return check
        return None

    async def _persist_evaluation_if_possible(
        self,
        *,
        request: EligibilityRequest,
        assessment_date: date,
        rule_bundle: RuleResolutionResult,
        response: EligibilityAssessmentResponse,
        pathway_used: str | None,
        audit_checks: Sequence[Mapping[str, Any]],
    ) -> bool:
        """Persist the evaluation plus checks when a case_id and repository are available.

        Returns True when the audit record was successfully written, False otherwise.
        A False return means the assessment result is still valid but is not replayable
        via the audit layer. NIM must not claim audit compliance when this returns False.
        """

        if self.evaluations_repository is None or request.case_id is None:
            self._last_persisted_evaluation_id = None
            return False

        evaluation_data = {
            "case_id": request.case_id,
            "evaluation_date": assessment_date,
            "overall_outcome": self._overall_outcome(response),
            "pathway_used": pathway_used,
            "confidence_class": response.confidence_class,
            "rule_status_at_evaluation": rule_bundle.psr_rule.rule_status,
            "tariff_status_at_evaluation": (
                response.tariff_outcome.status
                if response.tariff_outcome is not None
                else "incomplete"
            ),
        }
        try:
            mutable_checks = [dict(check) for check in audit_checks]
            evaluation_data["decision_snapshot_json"] = self._build_decision_snapshot(
                mutable_checks,
                selected_pathway_code=response.pathway_used,
            )
            persisted = await self.evaluations_repository.persist_evaluation(
                evaluation_data,
                mutable_checks,
                lock_case=False,
                persist_check_results=False,
                return_inserted_checks=False,
            )
            evaluation_row = (
                persisted.get("evaluation")
                if isinstance(persisted, Mapping)
                else None
            )
            evaluation_id = (
                evaluation_row.get("evaluation_id")
                if isinstance(evaluation_row, Mapping)
                else None
            )
            self._last_persisted_evaluation_id = (
                str(evaluation_id) if evaluation_id is not None else None
            )
            self._last_persistence_failure_detail = None
            if isinstance(persisted, Mapping) and evaluation_id is None:
                return False
            return True
        except Exception:
            self._last_persisted_evaluation_id = None
            _logger.error(
                "evaluation_persistence_failed",
                exc_info=True,
                extra={"case_id": request.case_id, "hs6_code": response.hs6_code},
            )
            return False

    async def _prepare_replay_persistence_checks(
        self,
        audit_checks: Sequence[Mapping[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """Clone one assessment trace and attach replay-safe provenance snapshots."""

        cloned_checks = jsonable_encoder(list(audit_checks))
        mutable_checks = [
            dict(check)
            for check in cloned_checks
            if isinstance(check, Mapping)
        ]
        failure_detail = await self._attach_provenance_snapshots(mutable_checks)
        return mutable_checks, failure_detail

    async def _persist_or_prepare_evaluation(
        self,
        *,
        request: EligibilityRequest,
        assessment_date: date,
        rule_bundle: RuleResolutionResult,
        response: EligibilityAssessmentResponse,
        pathway_used: str | None,
        audit_checks: Sequence[Mapping[str, Any]],
        persist_evaluation: bool,
    ) -> bool:
        """Persist immediately or capture a compact replay payload for detached writes."""

        mutable_checks, failure_detail = await self._prepare_replay_persistence_checks(
            audit_checks
        )
        if failure_detail is not None:
            failure_detail = {
                "case_id": request.case_id,
                **failure_detail,
            }
            self._last_persistence_failure_detail = failure_detail
            self._last_persisted_evaluation_id = None
            self._last_prepared_persistence = None
            if not persist_evaluation:
                raise EvaluationPersistenceError(
                    "Interface assessment could not freeze replay-safe provenance",
                    detail=failure_detail,
                )
            return False

        if persist_evaluation:
            self._last_prepared_persistence = None
            return await self._persist_evaluation_if_possible(
                request=request,
                assessment_date=assessment_date,
                rule_bundle=rule_bundle,
                response=response,
                pathway_used=pathway_used,
                audit_checks=mutable_checks,
            )

        self._last_persisted_evaluation_id = None
        self._last_persistence_failure_detail = None
        self._last_prepared_persistence = PreparedEvaluationPersistence(
            request=request.model_copy(deep=True),
            assessment_date=assessment_date,
            rule_bundle=rule_bundle,
            pathway_used=pathway_used,
            audit_checks=tuple(dict(check) for check in mutable_checks),
        )
        return False

    def _build_pending_alert_specs_if_possible(
        self,
        *,
        request: EligibilityRequest,
        rule_bundle: RuleResolutionResult,
        tariff_result: TariffResolutionResult | None,
        corridor_overlay: StatusOverlay,
        response: EligibilityAssessmentResponse,
    ) -> tuple[dict[str, Any], ...]:
        """Build advisory alert specs without blocking the synchronous response path."""

        if self.intelligence_service is None:
            return ()

        return tuple(
            self.intelligence_service.build_assessment_alert_specs(
                request=request,
                rule_bundle=rule_bundle,
                tariff_result=tariff_result,
                corridor_overlay=corridor_overlay,
                response=response,
            )
        )

    @staticmethod
    def _overall_outcome(response: EligibilityAssessmentResponse) -> LegalOutcome:
        """Map the API response to the persisted overall outcome enum."""

        if response.eligible:
            return LegalOutcome.ELIGIBLE
        if "NOT_OPERATIONAL" in response.failures:
            return LegalOutcome.NOT_YET_OPERATIONAL
        if response.missing_facts or "RULE_STATUS_PENDING" in response.failures:
            return LegalOutcome.INSUFFICIENT_INFORMATION
        return LegalOutcome.NOT_ELIGIBLE

    @staticmethod
    def _make_audit_check(
        *,
        check_type: str,
        check_code: str,
        passed: bool,
        severity: str,
        expected_value: str,
        observed_value: str,
        explanation: str,
        details_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create one persisted eligibility_check_result payload."""

        return {
            "check_type": check_type,
            "check_code": check_code,
            "passed": passed,
            "severity": severity,
            "expected_value": expected_value,
            "observed_value": observed_value,
            "explanation": explanation,
            "details_json": details_json,
            "linked_component_id": None,
        }

    def _make_pathway_trace_check(
        self,
        pathway: RulePathwayOut,
        result: ExpressionResult,
    ) -> dict[str, Any]:
        """Persist one pathway-level summary alongside the atomic evaluator checks."""

        passed = result.result if result.result is not None else False
        details_json = {
            "pathway": pathway.model_dump(mode="json"),
            "result": result.result,
            "evaluated_expression": result.evaluated_expression,
            "missing_variables": result.missing_variables,
        }
        if result.result is None:
            details_json["indeterminate"] = True

        return self._make_audit_check(
            check_type="pathway",
            check_code="PATHWAY_EVALUATION",
            passed=passed,
            severity="info" if result.result is True else "major",
            expected_value="pathway passes",
            observed_value=str(result.result).lower() if result.result is not None else "unknown",
            explanation=f"Evaluated pathway {pathway.pathway_code}",
            details_json=details_json,
        )

    def _make_general_rules_summary_check(
        self,
        result: GeneralRulesResult,
    ) -> dict[str, Any]:
        """Persist the aggregated general-rules outcome for later audit replay."""

        return self._make_audit_check(
            check_type="general_rule",
            check_code="GENERAL_RULES_SUMMARY",
            passed=result.general_rules_passed,
            severity="info" if result.general_rules_passed else "major",
            expected_value="all general rules pass",
            observed_value=str(result.general_rules_passed).lower(),
            explanation="Applied the post-PSR general origin rules",
            details_json={
                "general_rules_result": {
                    "insufficient_operations_check": result.insufficient_operations_check,
                    "cumulation_check": result.cumulation_check,
                    "direct_transport_check": result.direct_transport_check,
                    "general_rules_passed": result.general_rules_passed,
                    "failure_codes": result.failure_codes,
                }
            },
        )

    def _make_tariff_trace_check(
        self,
        tariff_result: TariffResolutionResult,
    ) -> dict[str, Any]:
        """Persist the resolved tariff snapshot used by the assessment."""

        tariff_outcome = self._build_tariff_outcome(tariff_result)
        return self._make_audit_check(
            check_type="tariff",
            check_code="TARIFF_RESOLUTION",
            passed=True,
            severity="info",
            expected_value="tariff schedule available",
            observed_value=self._normalize_value(tariff_result.tariff_status),
            explanation="Resolved the corridor tariff schedule and year-rate outcome",
            details_json={
                "tariff_outcome": (
                    tariff_outcome.model_dump(mode="json") if tariff_outcome is not None else None
                ),
                "tariff_resolution": tariff_result.model_dump(mode="json"),
            },
        )

    def _make_evidence_trace_check(self, evidence_result: Any) -> dict[str, Any]:
        """Persist the evidence readiness bundle returned by the evidence service."""

        payload = (
            evidence_result.model_dump(mode="json")
            if hasattr(evidence_result, "model_dump")
            else dict(evidence_result)
        )
        return self._make_audit_check(
            check_type="evidence",
            check_code="EVIDENCE_READINESS",
            passed=True,
            severity="info",
            expected_value="evidence readiness computed",
            observed_value=str(payload.get("readiness_score")),
            explanation="Built the evidence readiness checklist for this assessment",
            details_json={"evidence_readiness": payload},
        )

    def _make_decision_trace_check(
        self,
        response: EligibilityAssessmentResponse,
    ) -> dict[str, Any]:
        """Persist the final API response fields needed for audit replay."""

        return self._make_audit_check(
            check_type="decision",
            check_code="FINAL_DECISION",
            passed=response.eligible,
            severity="info" if response.eligible else "major",
            expected_value="eligible determination",
            observed_value=str(response.eligible).lower(),
            explanation="Calculated the final deterministic eligibility decision",
            details_json={
                "final_decision": {
                    "eligible": response.eligible,
                    "pathway_used": response.pathway_used,
                    "rule_status": self._normalize_value(response.rule_status),
                    "tariff_status": (
                        response.tariff_outcome.status
                        if response.tariff_outcome is not None
                        else None
                    ),
                    "confidence_class": response.confidence_class,
                    "failure_codes": response.failures,
                    "missing_facts": response.missing_facts,
                    "missing_evidence": response.missing_evidence,
                    "readiness_score": response.readiness_score,
                    "completeness_ratio": response.completeness_ratio,
                }
            },
        )

    def _log_assessment(
        self,
        *,
        request: EligibilityRequest,
        response: EligibilityAssessmentResponse,
        blocker_checks: Sequence[Mapping[str, Any]],
        started_at: float,
    ) -> None:
        """Emit the structured audit log for the completed assessment when enabled."""

        if self.audit_service is None:
            return

        self.audit_service.log_assessment(
            case_id=request.case_id,
            hs6_code=response.hs6_code,
            exporter=request.exporter,
            importer=request.importer,
            outcome="eligible" if response.eligible else "not_eligible",
            confidence_class=response.confidence_class,
            duration_ms=int((perf_counter() - started_at) * 1000),
            blockers=[
                str(check["check_code"])
                for check in blocker_checks
                if check.get("passed") is False and check.get("severity") == "blocker"
            ],
            missing_facts=response.missing_facts,
        )

    @staticmethod
    def _read_fact_field(fact: Any, field_name: str) -> Any:
        """Read a field from either a dict-like or object-like fact payload."""

        if isinstance(fact, Mapping):
            return fact.get(field_name)
        return getattr(fact, field_name, None)

    def _failure_codes_from_atomic_checks(self, checks: Sequence[AtomicCheck]) -> list[str]:
        """Map atomic-check explanations back to canonical failure codes."""

        failure_codes: list[str] = []
        for check in checks:
            if check.passed is not False:
                continue
            failure_code = FAILURE_MESSAGES_TO_CODES.get(check.explanation)
            if failure_code is not None:
                failure_codes = self._merge_unique(failure_codes, [failure_code])
        return failure_codes

    @staticmethod
    def _normalize_value(value: Any) -> str:
        """Collapse enum-backed values to raw strings."""

        return str(getattr(value, "value", value))

    @staticmethod
    def _merge_unique(*groups: Sequence[str]) -> list[str]:
        """Merge string groups while preserving first-seen order."""

        merged: list[str] = []
        for group in groups:
            for value in group:
                if value not in merged:
                    merged.append(value)
        return merged

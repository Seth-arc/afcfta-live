"""Build persona-aware evidence readiness from requirement and question lookups."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
import logging

from app.core.logging import log_event
from app.repositories.evidence_repository import EvidenceRepository
from app.schemas.evidence import EvidenceReadinessResult

# Maps confidence class to verification question risk tier.
_CONFIDENCE_TO_RISK: dict[str, str | None] = {
    "complete": None,
    "incomplete": "documentary_gap",
    "insufficient": "origin_claim",
    "provisional": None,
}

_logger = logging.getLogger("app.evidence")


class EvidenceService:
    """Service for evidence requirement comparison and readiness scoring."""

    def __init__(self, evidence_repository: EvidenceRepository) -> None:
        self.evidence_repository = evidence_repository

    async def build_readiness(
        self,
        entity_type: str,
        entity_key: str,
        persona_mode: str,
        existing_documents: list[str],
        confidence_class: str | None = None,
        assessment_date: date | None = None,
    ) -> EvidenceReadinessResult:
        """Return required, missing, and verification items for a persona/entity pair.

        When assessment_date is omitted, evidence lookups rely on the caller to keep
        all reads inside the same repeatable-read transaction boundary.
        """

        if assessment_date is None:
            log_event(
                _logger,
                logging.WARNING,
                event="evidence_service_missing_assessment_date",
                message="evidence_service called without assessment_date — snapshot isolation relies on caller transaction boundary",
                entity_type=entity_type,
                entity_key=entity_key,
            )
        resolved_persona = self._normalize_persona_mode(persona_mode)
        risk_category = (
            None if confidence_class is None else _CONFIDENCE_TO_RISK.get(confidence_class)
        )
        requirements = await self.evidence_repository.get_requirements(
            entity_type=entity_type,
            entity_key=entity_key,
            persona_mode=resolved_persona,
            as_of_date=assessment_date,
        )
        questions = await self.evidence_repository.get_verification_questions(
            entity_type=entity_type,
            entity_key=entity_key,
            risk_category=risk_category,
            as_of_date=assessment_date,
        )
        return self._build_result(
            requirements=requirements,
            questions=questions,
            persona_mode=resolved_persona,
            existing_documents=existing_documents,
        )

    async def build_readiness_for_targets(
        self,
        targets: list[tuple[str, str]],
        *,
        persona_mode: str,
        existing_documents: list[str],
        confidence_class: str | None = None,
        assessment_date: date | None = None,
    ) -> EvidenceReadinessResult:
        """Resolve ordered evidence targets in one repository round trip."""

        if assessment_date is None:
            log_event(
                _logger,
                logging.WARNING,
                event="evidence_service_missing_assessment_date",
                message="evidence_service called without assessment_date â€” snapshot isolation relies on caller transaction boundary",
            )

        resolved_persona = self._normalize_persona_mode(persona_mode)
        risk_category = (
            None if confidence_class is None else _CONFIDENCE_TO_RISK.get(confidence_class)
        )
        lookup_rows = await self.evidence_repository.get_readiness_inputs_for_targets(
            targets,
            persona_mode=resolved_persona,
            risk_category=risk_category,
            as_of_date=assessment_date,
        )

        fallback_result: EvidenceReadinessResult | None = None
        for row in lookup_rows:
            result = self._build_result(
                requirements=row.get("requirements") or [],
                questions=row.get("questions") or [],
                persona_mode=resolved_persona,
                existing_documents=existing_documents,
            )
            if fallback_result is None:
                fallback_result = result
            if self._result_has_content(result):
                return result

        return fallback_result or EvidenceReadinessResult(
            required_items=[],
            missing_items=[],
            verification_questions=[],
            readiness_score=1.0,
            completeness_ratio=1.0,
        )

    def _build_result(
        self,
        *,
        requirements: list[Mapping[str, object]],
        questions: list[Mapping[str, object]],
        persona_mode: str,
        existing_documents: list[str],
    ) -> EvidenceReadinessResult:
        """Construct one readiness result from repository rows."""

        required_map: dict[str, str] = {}
        for requirement in requirements:
            if requirement["required"] is not True:
                continue
            requirement_type = self._normalize_value(requirement["requirement_type"]).lower()
            required_map.setdefault(
                requirement_type,
                requirement["requirement_description"],
            )

        provided_documents = {
            self._normalize_value(document).strip().lower()
            for document in existing_documents
            if self._normalize_value(document).strip()
        }
        missing_items = [
            description
            for requirement_type, description in required_map.items()
            if requirement_type not in provided_documents
        ]
        required_items = list(required_map.values())
        provided_count = sum(
            1 for requirement_type in required_map if requirement_type in provided_documents
        )
        total_required = len(required_map)
        readiness_score = 1.0 if total_required == 0 else provided_count / total_required

        verification_questions = [
            question["question_text"]
            for question in questions
            if self._normalize_value(question["persona_mode"]) in {persona_mode, "system"}
        ]

        return EvidenceReadinessResult(
            required_items=required_items,
            missing_items=missing_items,
            verification_questions=verification_questions,
            readiness_score=readiness_score,
            completeness_ratio=readiness_score,
        )

    @staticmethod
    def _result_has_content(result: EvidenceReadinessResult) -> bool:
        """Return True when a readiness result includes actual requirements or questions."""

        return bool(result.required_items or result.verification_questions)

    async def get_readiness(
        self,
        entity_type: str,
        entity_key: str,
        persona_mode: str,
        existing_documents: list[str],
        confidence_class: str | None = None,
        assessment_date: date | None = None,
    ) -> EvidenceReadinessResult:
        """Compatibility wrapper for API handlers that call the service via get_readiness()."""

        return await self.build_readiness(
            entity_type=entity_type,
            entity_key=entity_key,
            persona_mode=persona_mode,
            existing_documents=existing_documents,
            confidence_class=confidence_class,
            assessment_date=assessment_date,
        )

    @staticmethod
    def _normalize_persona_mode(persona_mode: str) -> str:
        """Collapse enum-backed persona values to their lowercase string representation."""

        return EvidenceService._normalize_value(persona_mode).lower()

    @staticmethod
    def _normalize_value(value: object) -> str:
        """Collapse enum-backed values to their raw string payload."""

        return str(getattr(value, "value", value))

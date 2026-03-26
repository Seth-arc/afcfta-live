"""Build persona-aware evidence readiness from requirement and question lookups."""

from __future__ import annotations

from app.repositories.evidence_repository import EvidenceRepository
from app.schemas.evidence import EvidenceReadinessResult

# `scripts/sql/seed_evidence_requirements.sql` currently seeds only
# `evidence_requirement` rows. The seeded verification-question data in
# `scripts/seed_data.py` uses `origin_claim`, `valuation_risk`,
# `tariff_classification_risk`, and the fallback `general`, not the
# confidence classes directly. Until dedicated `documentary_gap` question rows
# exist in the checked-in seed data, `incomplete` maps to the generic
# documentary-check bucket (`general`) and `insufficient` maps to
# `origin_claim`.
_CONFIDENCE_TO_RISK: dict[str, str | None] = {
    "complete": None,
    "incomplete": "general",
    "insufficient": "origin_claim",
    "provisional": None,
}


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
    ) -> EvidenceReadinessResult:
        """Return required, missing, and verification items for a persona/entity pair.

        The current evidence tables are not date-windowed, so readiness remains
        assessment-snapshot consistent by running inside the same repeatable-read
        transaction as the rest of the assessment.
        """

        resolved_persona = self._normalize_persona_mode(persona_mode)
        risk_category = (
            None if confidence_class is None else _CONFIDENCE_TO_RISK.get(confidence_class)
        )
        requirements = await self.evidence_repository.get_requirements(
            entity_type=entity_type,
            entity_key=entity_key,
            persona_mode=resolved_persona,
        )
        questions = await self.evidence_repository.get_verification_questions(
            entity_type=entity_type,
            entity_key=entity_key,
            risk_category=risk_category,
        )

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
            if self._normalize_value(question["persona_mode"]) in {resolved_persona, "system"}
        ]

        return EvidenceReadinessResult(
            required_items=required_items,
            missing_items=missing_items,
            verification_questions=verification_questions,
            readiness_score=readiness_score,
            completeness_ratio=readiness_score,
        )

    async def get_readiness(
        self,
        entity_type: str,
        entity_key: str,
        persona_mode: str,
        existing_documents: list[str],
        confidence_class: str | None = None,
    ) -> EvidenceReadinessResult:
        """Compatibility wrapper for API handlers that call the service via get_readiness()."""

        return await self.build_readiness(
            entity_type=entity_type,
            entity_key=entity_key,
            persona_mode=persona_mode,
            existing_documents=existing_documents,
            confidence_class=confidence_class,
        )

    @staticmethod
    def _normalize_persona_mode(persona_mode: str) -> str:
        """Collapse enum-backed persona values to their lowercase string representation."""

        return EvidenceService._normalize_value(persona_mode).lower()

    @staticmethod
    def _normalize_value(value: object) -> str:
        """Collapse enum-backed values to their raw string payload."""

        return str(getattr(value, "value", value))

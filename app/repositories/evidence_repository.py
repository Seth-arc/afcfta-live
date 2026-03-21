"""Data access for evidence requirements and verification questions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class EvidenceRepository:
    """Repository for persona-aware evidence lookups."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_requirements(
        self,
        entity_type: str,
        entity_key: str,
        persona_mode: str,
    ) -> list[Mapping[str, Any]]:
        """Return evidence requirements for one entity key, including system requirements."""

        statement = text(
            """
            SELECT
              er.evidence_id,
              er.entity_type,
              er.entity_key,
              er.persona_mode,
              er.requirement_type,
              er.requirement_description,
              er.legal_basis_provision_id,
              er.required,
              er.conditional_on,
              er.priority_level,
              er.created_at,
              er.updated_at
            FROM evidence_requirement er
            WHERE er.persona_mode IN (:persona_mode, 'system')
              AND er.entity_type = :entity_type
              AND er.entity_key = :entity_key
            ORDER BY er.priority_level ASC, er.requirement_type ASC
            """
        )
        result = await self.session.execute(
            statement,
            {
                "persona_mode": persona_mode,
                "entity_type": entity_type,
                "entity_key": entity_key,
            },
        )
        return list(result.mappings().all())

    async def get_verification_questions(
        self,
        entity_type: str,
        entity_key: str,
        risk_category: str | None,
    ) -> list[Mapping[str, Any]]:
        """Return active verification questions for an entity key, optionally filtered by risk."""

        params: dict[str, Any] = {
            "entity_type": entity_type,
            "entity_key": entity_key,
        }
        statement_text = """
            SELECT
              vq.question_id,
              vq.entity_type,
              vq.entity_key,
              vq.persona_mode,
              vq.question_text,
              vq.purpose,
              vq.legal_basis_provision_id,
              vq.risk_category,
              vq.priority_level,
              vq.active,
              vq.question_order,
              vq.created_at,
              vq.updated_at
            FROM verification_question vq
            WHERE vq.entity_type = :entity_type
              AND vq.entity_key = :entity_key
              AND vq.active = true
        """
        if risk_category is not None:
            statement_text += "\n  AND vq.risk_category = :risk_category"
            params["risk_category"] = risk_category
        statement_text += """
            ORDER BY
              vq.priority_level ASC,
              vq.question_order ASC,
              vq.persona_mode ASC
        """
        result = await self.session.execute(text(statement_text), params)
        return list(result.mappings().all())

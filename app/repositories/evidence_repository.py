"""Data access for evidence requirements and verification questions."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.cache as cache
from app.config import get_settings


class EvidenceRepository:
    """Repository for persona-aware evidence lookups."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_requirements(
        self,
        entity_type: str,
        entity_key: str,
        persona_mode: str,
        as_of_date: date | None = None,
    ) -> list[Mapping[str, Any]]:
        """Return evidence requirements for one entity key, including system requirements."""

        settings = get_settings()
        cache_key = (
            "evidence-requirements",
            entity_type,
            entity_key,
            persona_mode,
            as_of_date.isoformat() if as_of_date is not None else None,
        )
        if settings.CACHE_STATIC_LOOKUPS:
            hit, cached = cache.get(cache.evidence_store, cache_key)
            if hit:
                return cached

        statement_text = """
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
        """
        params: dict[str, Any] = {
            "persona_mode": persona_mode,
            "entity_type": entity_type,
            "entity_key": entity_key,
        }
        if as_of_date is not None:
            statement_text += """
              AND (er.effective_from IS NULL OR er.effective_from <= :as_of_date)
              AND (er.effective_to IS NULL OR er.effective_to >= :as_of_date)
            """
            params["as_of_date"] = as_of_date
        statement_text += "\nORDER BY er.priority_level ASC, er.requirement_type ASC"
        result = await self.session.execute(
            text(statement_text),
            params,
        )
        rows = list(result.mappings().all())
        if settings.CACHE_STATIC_LOOKUPS:
            cache.put(cache.evidence_store, cache_key, rows, settings.CACHE_TTL_SECONDS)
        return rows

    async def get_verification_questions(
        self,
        entity_type: str,
        entity_key: str,
        risk_category: str | None,
        as_of_date: date | None = None,
    ) -> list[Mapping[str, Any]]:
        """Return active verification questions for an entity key, optionally filtered by risk."""

        settings = get_settings()
        cache_key = (
            "verification-questions",
            entity_type,
            entity_key,
            risk_category,
            as_of_date.isoformat() if as_of_date is not None else None,
        )
        if settings.CACHE_STATIC_LOOKUPS:
            hit, cached = cache.get(cache.evidence_store, cache_key)
            if hit:
                return cached

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
        if as_of_date is not None:
            statement_text += """
              AND (vq.effective_from IS NULL OR vq.effective_from <= :as_of_date)
              AND (vq.effective_to IS NULL OR vq.effective_to >= :as_of_date)
            """
            params["as_of_date"] = as_of_date
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
        rows = list(result.mappings().all())
        if settings.CACHE_STATIC_LOOKUPS:
            cache.put(cache.evidence_store, cache_key, rows, settings.CACHE_TTL_SECONDS)
        return rows

    async def get_readiness_inputs_for_targets(
        self,
        targets: list[tuple[str, str]],
        *,
        persona_mode: str,
        risk_category: str | None,
        as_of_date: date | None = None,
    ) -> list[Mapping[str, Any]]:
        """Return ordered requirement/question bundles for one or more evidence targets."""

        if not targets:
            return []

        settings = get_settings()
        cache_key = (
            "evidence-readiness-targets",
            tuple(targets),
            persona_mode,
            risk_category,
            as_of_date.isoformat() if as_of_date is not None else None,
        )
        if settings.CACHE_STATIC_LOOKUPS:
            hit, cached = cache.get(cache.evidence_store, cache_key)
            if hit:
                return cached

        value_fragments: list[str] = []
        params: dict[str, Any] = {"persona_mode": persona_mode}
        for ordinal, (entity_type, entity_key) in enumerate(targets):
            value_fragments.append(
                "("
                f"CAST(:entity_type_{ordinal} AS text), "
                f"CAST(:entity_key_{ordinal} AS text), "
                f"CAST(:ordinal_{ordinal} AS integer)"
                ")"
            )
            params[f"entity_type_{ordinal}"] = entity_type
            params[f"entity_key_{ordinal}"] = entity_key
            params[f"ordinal_{ordinal}"] = ordinal

        requirement_window_clause = ""
        question_window_clause = ""
        if as_of_date is not None:
            requirement_window_clause = """
                    AND (er.effective_from IS NULL OR er.effective_from <= :as_of_date)
                    AND (er.effective_to IS NULL OR er.effective_to >= :as_of_date)
            """
            question_window_clause = """
                    AND (vq.effective_from IS NULL OR vq.effective_from <= :as_of_date)
                    AND (vq.effective_to IS NULL OR vq.effective_to >= :as_of_date)
            """
            params["as_of_date"] = as_of_date

        risk_clause = ""
        if risk_category is not None:
            risk_clause = "\n                    AND vq.risk_category = :risk_category"
            params["risk_category"] = risk_category

        # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
        # SQL text is parameterized; VALUES slots are generated from bound placeholders only.
        statement = text(
            f"""
            WITH targets(entity_type, entity_key, ordinal) AS (
              VALUES {", ".join(value_fragments)}
            )
            SELECT
              targets.ordinal,
              targets.entity_type,
              targets.entity_key,
              COALESCE(
                (
                  SELECT json_agg(
                    json_build_object(
                      'evidence_id', er.evidence_id,
                      'entity_type', er.entity_type,
                      'entity_key', er.entity_key,
                      'persona_mode', er.persona_mode,
                      'requirement_type', er.requirement_type,
                      'requirement_description', er.requirement_description,
                      'legal_basis_provision_id', er.legal_basis_provision_id,
                      'required', er.required,
                      'conditional_on', er.conditional_on,
                      'priority_level', er.priority_level,
                      'effective_from', er.effective_from,
                      'effective_to', er.effective_to,
                      'created_at', er.created_at,
                      'updated_at', er.updated_at
                    )
                    ORDER BY er.priority_level ASC, er.requirement_type ASC
                  )
                  FROM evidence_requirement er
                  WHERE er.persona_mode IN (:persona_mode, 'system')
                    AND er.entity_type = targets.entity_type
                    AND er.entity_key = targets.entity_key
                    {requirement_window_clause}
                ),
                '[]'::json
              ) AS requirements,
              COALESCE(
                (
                  SELECT json_agg(
                    json_build_object(
                      'question_id', vq.question_id,
                      'entity_type', vq.entity_type,
                      'entity_key', vq.entity_key,
                      'persona_mode', vq.persona_mode,
                      'question_text', vq.question_text,
                      'purpose', vq.purpose,
                      'legal_basis_provision_id', vq.legal_basis_provision_id,
                      'risk_category', vq.risk_category,
                      'priority_level', vq.priority_level,
                      'active', vq.active,
                      'question_order', vq.question_order,
                      'effective_from', vq.effective_from,
                      'effective_to', vq.effective_to,
                      'created_at', vq.created_at,
                      'updated_at', vq.updated_at
                    )
                    ORDER BY
                      vq.priority_level ASC,
                      vq.question_order ASC,
                      vq.persona_mode ASC
                  )
                  FROM verification_question vq
                  WHERE vq.entity_type = targets.entity_type
                    AND vq.entity_key = targets.entity_key
                    AND vq.active = true
                    {question_window_clause}{risk_clause}
                ),
                '[]'::json
              ) AS questions
            FROM targets
            ORDER BY targets.ordinal ASC
            """
        )
        result = await self.session.execute(statement, params)
        rows = [dict(row) for row in result.mappings().all()]
        if settings.CACHE_STATIC_LOOKUPS:
            cache.put(cache.evidence_store, cache_key, rows, settings.CACHE_TTL_SECONDS)
        return rows

"""Data access for source registry and extracted legal provisions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.cache as cache
from app.config import get_settings
from app.db.models.sources import LegalProvision, SourceRegistry


class SourcesRepository:
    """Repository for provenance-layer CRUD and topic lookup."""

    MAX_AUDIT_PROVISIONS_PER_SOURCE = 5
    MAX_PROVISION_TEXT_EXCERPT_CHARS = 280

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_source(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        source_table = SourceRegistry.__table__
        statement = insert(source_table).values(**values).returning(*source_table.c)
        result = await self.session.execute(statement)
        return result.mappings().one()

    async def get_source(self, source_id: str) -> Mapping[str, Any] | None:
        source_table = SourceRegistry.__table__
        statement = select(*source_table.c).where(source_table.c.source_id == source_id)
        result = await self.session.execute(statement)
        return result.mappings().first()

    async def list_sources(
        self,
        *,
        source_type: str | None = None,
        authority_tier: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Mapping[str, Any]]:
        source_table = SourceRegistry.__table__
        statement = select(*source_table.c)
        if source_type is not None:
            statement = statement.where(source_table.c.source_type == source_type)
        if authority_tier is not None:
            statement = statement.where(source_table.c.authority_tier == authority_tier)
        if status is not None:
            statement = statement.where(source_table.c.status == status)
        statement = statement.order_by(
            source_table.c.effective_date.desc(),
            source_table.c.created_at.desc(),
        )
        statement = statement.limit(limit).offset(offset)
        result = await self.session.execute(statement)
        return list(result.mappings().all())

    async def list_sources_by_topic(
        self,
        *,
        topic: str,
        source_type: str | None = None,
        authority_tier: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Mapping[str, Any]]:
        """Return distinct sources that back provisions tagged to the requested topic."""

        source_table = SourceRegistry.__table__
        provision_table = LegalProvision.__table__

        statement = (
            select(*source_table.c)
            .distinct()
            .join(
                provision_table,
                provision_table.c.source_id == source_table.c.source_id,
            )
            .where(
                (provision_table.c.topic_primary == topic)
                | provision_table.c.topic_secondary.contains([topic])
            )
        )
        if source_type is not None:
            statement = statement.where(source_table.c.source_type == source_type)
        if authority_tier is not None:
            statement = statement.where(source_table.c.authority_tier == authority_tier)
        if status is not None:
            statement = statement.where(source_table.c.status == status)
        statement = statement.order_by(
            source_table.c.effective_date.desc(),
            source_table.c.created_at.desc(),
        )
        statement = statement.limit(limit).offset(offset)
        result = await self.session.execute(statement)
        return list(result.mappings().all())

    async def update_source(
        self,
        source_id: str,
        values: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        if not values:
            return await self.get_source(source_id)
        source_table = SourceRegistry.__table__
        statement = (
            update(source_table)
            .where(source_table.c.source_id == source_id)
            .values(**values)
            .returning(*source_table.c)
        )
        result = await self.session.execute(statement)
        return result.mappings().first()

    async def delete_source(self, source_id: str) -> Mapping[str, Any] | None:
        source_table = SourceRegistry.__table__
        statement = (
            delete(source_table)
            .where(source_table.c.source_id == source_id)
            .returning(*source_table.c)
        )
        result = await self.session.execute(statement)
        return result.mappings().first()

    async def create_provision(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        provision_table = LegalProvision.__table__
        statement = insert(provision_table).values(**values).returning(*provision_table.c)
        result = await self.session.execute(statement)
        return result.mappings().one()

    async def get_provision(self, provision_id: str) -> Mapping[str, Any] | None:
        provision_table = LegalProvision.__table__
        statement = select(*provision_table.c).where(provision_table.c.provision_id == provision_id)
        result = await self.session.execute(statement)
        return result.mappings().first()

    async def list_provisions(
        self,
        *,
        topic_primary: str | None = None,
        annex_ref: str | None = None,
        source_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Mapping[str, Any]]:
        provision_table = LegalProvision.__table__
        statement = select(*provision_table.c)
        if topic_primary is not None:
            statement = statement.where(provision_table.c.topic_primary == topic_primary)
        if annex_ref is not None:
            statement = statement.where(provision_table.c.annex_ref == annex_ref)
        if source_id is not None:
            statement = statement.where(provision_table.c.source_id == source_id)
        statement = statement.order_by(
            provision_table.c.authority_weight.desc(),
            provision_table.c.created_at.desc(),
        )
        statement = statement.limit(limit).offset(offset)
        result = await self.session.execute(statement)
        return list(result.mappings().all())

    async def update_provision(
        self,
        provision_id: str,
        values: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        if not values:
            return await self.get_provision(provision_id)
        provision_table = LegalProvision.__table__
        statement = (
            update(provision_table)
            .where(provision_table.c.provision_id == provision_id)
            .values(**values)
            .returning(*provision_table.c)
        )
        result = await self.session.execute(statement)
        return result.mappings().first()

    async def delete_provision(self, provision_id: str) -> Mapping[str, Any] | None:
        provision_table = LegalProvision.__table__
        statement = (
            delete(provision_table)
            .where(provision_table.c.provision_id == provision_id)
            .returning(*provision_table.c)
        )
        result = await self.session.execute(statement)
        return result.mappings().first()

    async def get_provisions_for_source(
        self,
        source_id: str,
        limit: int = 5,
        *,
        include_text: bool = False,
    ) -> list[Mapping[str, Any]]:
        """Return thin provision summaries for one source, ordered by authority weight.

        Projects only the bounded audit-trail fields plus ``source_id`` so callers
        can verify that the returned provision still belongs to the requested
        source. ``include_text`` is retained for compatibility but the method
        always returns a thin ``text_excerpt`` instead of full provision bodies.
        """

        settings = get_settings()
        cache_key = ("source_provisions", source_id, limit, include_text)
        if settings.CACHE_STATIC_LOOKUPS:
            hit, cached = cache.get(cache.provenance_store, cache_key)
            if hit:
                return cached

        provision_table = LegalProvision.__table__
        selected_columns = [
            provision_table.c.provision_id,
            provision_table.c.source_id,
            provision_table.c.article_ref,
            provision_table.c.annex_ref,
            provision_table.c.appendix_ref,
            provision_table.c.section_ref,
            provision_table.c.subsection_ref,
            provision_table.c.topic_primary,
            provision_table.c.provision_text_verbatim,
            provision_table.c.authority_weight,
        ]
        statement = (
            select(*selected_columns)
            .where(provision_table.c.source_id == source_id)
            .order_by(
                provision_table.c.authority_weight.desc(),
                provision_table.c.article_ref.asc().nulls_last(),
                provision_table.c.subsection_ref.asc().nulls_last(),
                provision_table.c.section_ref.asc().nulls_last(),
                provision_table.c.annex_ref.asc().nulls_last(),
                provision_table.c.appendix_ref.asc().nulls_last(),
                provision_table.c.provision_id.asc(),
            )
            .limit(min(limit, self.MAX_AUDIT_PROVISIONS_PER_SOURCE))
        )
        result = await self.session.execute(statement)
        rows = [
            self._compact_provision_summary(dict(row))
            for row in result.mappings().all()
        ]
        if settings.CACHE_STATIC_LOOKUPS:
            cache.put(cache.provenance_store, cache_key, rows, settings.CACHE_TTL_SECONDS)
        return rows

    async def get_source_snapshot(
        self,
        source_id: str,
        *,
        provision_limit: int = 5,
    ) -> Mapping[str, Any] | None:
        """Return thin source metadata plus bounded provision snapshots for audit persistence."""

        settings = get_settings()
        cache_key = ("source_snapshot", source_id, provision_limit)
        if settings.CACHE_STATIC_LOOKUPS:
            hit, cached = cache.get(cache.provenance_store, cache_key)
            if hit:
                return cached

        source = await self.get_source(source_id)
        if source is None:
            if settings.CACHE_STATIC_LOOKUPS:
                cache.put(cache.provenance_store, cache_key, None, settings.CACHE_TTL_SECONDS)
            return None

        snapshot = {
            "source": {
                "source_id": source.get("source_id"),
                "short_title": source.get("short_title"),
                "version_label": source.get("version_label"),
                "publication_date": source.get("publication_date"),
                "effective_date": source.get("effective_date"),
            },
            "supporting_provisions": await self.get_provisions_for_source(
                source_id,
                limit=min(provision_limit, self.MAX_AUDIT_PROVISIONS_PER_SOURCE),
            ),
        }
        if settings.CACHE_STATIC_LOOKUPS:
            cache.put(cache.provenance_store, cache_key, snapshot, settings.CACHE_TTL_SECONDS)
        return snapshot

    @classmethod
    def _compact_provision_summary(cls, row: Mapping[str, Any]) -> dict[str, Any]:
        """Normalize one legal provision row into the bounded audit snapshot shape."""

        clause_label = (
            row.get("subsection_ref")
            or row.get("section_ref")
            or row.get("annex_ref")
            or row.get("appendix_ref")
        )
        text_excerpt = cls._truncate_text_excerpt(row.get("provision_text_verbatim"))
        return {
            "provision_id": row.get("provision_id"),
            "source_id": row.get("source_id"),
            "article_label": row.get("article_ref"),
            "clause_label": clause_label,
            "topic_primary": row.get("topic_primary"),
            "text_excerpt": text_excerpt,
        }

    @classmethod
    def _truncate_text_excerpt(cls, value: Any) -> str | None:
        """Trim one provision text field to the deterministic audit excerpt budget."""

        if value is None:
            return None
        text = str(value).strip()
        if len(text) <= cls.MAX_PROVISION_TEXT_EXCERPT_CHARS:
            return text
        return text[: cls.MAX_PROVISION_TEXT_EXCERPT_CHARS - 3].rstrip() + "..."

    async def lookup_by_topic(self, topic: str, limit: int = 10) -> list[Mapping[str, Any]]:
        provision_table = LegalProvision.__table__
        statement = (
            select(*provision_table.c)
            .where(
                (provision_table.c.topic_primary == topic)
                | provision_table.c.topic_secondary.contains([topic])
            )
            .order_by(
                provision_table.c.authority_weight.desc(),
                provision_table.c.updated_at.desc(),
            )
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.mappings().all())

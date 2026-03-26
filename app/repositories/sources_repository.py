"""Data access for source registry and extracted legal provisions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sources import LegalProvision, SourceRegistry


class SourcesRepository:
    """Repository for provenance-layer CRUD and topic lookup."""

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
    ) -> list[Mapping[str, Any]]:
        """Return thin provision summaries for one source, ordered by authority weight.

        Projects the compact audit-trail fields plus ``source_id`` so callers can
        verify that the returned provision still belongs to the requested source.
        Full text is excluded to keep audit responses compact. Callers follow
        ``provision_id`` to ``GET /api/v1/provisions/{provision_id}`` for the
        verbatim text.
        """

        provision_table = LegalProvision.__table__
        statement = (
            select(
                provision_table.c.provision_id,
                provision_table.c.source_id,
                provision_table.c.instrument_name,
                provision_table.c.article_ref,
                provision_table.c.annex_ref,
                provision_table.c.topic_primary,
                provision_table.c.page_start,
                provision_table.c.page_end,
            )
            .where(provision_table.c.source_id == source_id)
            .order_by(
                provision_table.c.authority_weight.desc(),
                provision_table.c.created_at.asc(),
            )
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.mappings().all())

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

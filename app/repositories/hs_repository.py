"""Data access for canonical HS6 product resolution."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.hs import HS6Product


class HSRepository:
    """Repository for the canonical HS6 backbone table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_code(self, hs_version: str, hs6_code: str) -> HS6Product | None:
        """Fetch a canonical HS6 product by version and 6-digit code."""

        statement = select(HS6Product).where(
            HS6Product.hs_version == hs_version,
            HS6Product.hs6_code == hs6_code,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def search_by_description(self, query: str) -> list[HS6Product]:
        """Search canonical HS6 products by description text."""

        statement = (
            select(HS6Product)
            .where(HS6Product.description.ilike(f"%{query}%"))
            .order_by(HS6Product.hs_version, HS6Product.hs6_code)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def list_all(self, limit: int, offset: int) -> list[HS6Product]:
        """List canonical HS6 products with deterministic paging."""

        statement = (
            select(HS6Product)
            .order_by(HS6Product.hs_version, HS6Product.hs6_code)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

"""Helpers for seeding collision-free synthetic HS6 fixtures in integration tests."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.hs import HS6Product


async def allocate_unused_hs6_code(
    session: AsyncSession,
    *,
    prefix: str,
    hs_version: str = "HS2017",
) -> str:
    """Return the first unused 6-digit HS6 code for the requested prefix.

    Integration fixtures seed synthetic products directly into the shared test
    database, so random suffixes are not safe on reruns or against expanded live
    seed slices. The allocator scans existing codes under the prefix and chooses
    the first open slot deterministically.
    """

    normalized_prefix = "".join(character for character in prefix if character.isdigit())
    if not normalized_prefix:
        raise ValueError("prefix must contain at least one digit")
    if len(normalized_prefix) >= 6:
        raise ValueError("prefix must be shorter than 6 digits")

    suffix_width = 6 - len(normalized_prefix)
    existing_codes = set(
        (
            await session.scalars(
                select(HS6Product.hs6_code).where(
                    HS6Product.hs_version == hs_version,
                    HS6Product.hs6_code.like(f"{normalized_prefix}%"),
                )
            )
        ).all()
    )

    for suffix in range(10**suffix_width):
        candidate = f"{normalized_prefix}{suffix:0{suffix_width}d}"
        if candidate not in existing_codes:
            return candidate

    raise AssertionError(
        f"No unused HS6 codes remain for prefix {normalized_prefix} in {hs_version}."
    )

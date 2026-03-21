"""Normalize raw HS input and resolve the canonical HS6 product."""

from __future__ import annotations

from app.core.exceptions import ClassificationError
from app.repositories.hs_repository import HSRepository
from app.schemas.hs import HS6ProductResponse


class ClassificationService:
    """Resolve raw HS input to the canonical HS6 backbone record."""

    def __init__(self, hs_repository: HSRepository) -> None:
        self.hs_repository = hs_repository

    async def resolve_hs6(
        self,
        hs_code: str,
        hs_version: str | None = "HS2017",
    ) -> HS6ProductResponse:
        """Normalize an HS code, truncate to HS6, and return the canonical product."""

        resolved_version = hs_version or "HS2017"
        normalized_code = self._normalize_hs6_code(hs_code)
        product = await self.hs_repository.get_by_code(resolved_version, normalized_code)
        if product is None:
            raise ClassificationError(
                f"HS6 code '{normalized_code}' not found for hs_version '{resolved_version}'",
                detail={"attempted_code": normalized_code, "hs_version": resolved_version},
            )
        return HS6ProductResponse.model_validate(product, from_attributes=True)

    @staticmethod
    def _normalize_hs6_code(hs_code: str) -> str:
        """Strip separators, keep digits only, and truncate longer inputs to HS6."""

        digits_only = "".join(character for character in hs_code if character.isdigit())
        if len(digits_only) < 6:
            raise ClassificationError(
                f"HS code '{hs_code}' is too short to resolve to HS6",
                detail={"attempted_code": digits_only, "original_input": hs_code},
            )
        return digits_only[:6]

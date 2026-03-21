"""Unit tests for HS6 classification service normalization and lookup."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ClassificationError
from app.repositories.hs_repository import HSRepository
from app.schemas.hs import HS6ProductResponse
from app.services.classification_service import ClassificationService


def build_product(hs6_code: str) -> SimpleNamespace:
    """Build a minimal HS6 product-like object for service tests."""

    timestamp = datetime.now(UTC)
    return SimpleNamespace(
        hs6_id="11111111-1111-1111-1111-111111111111",
        hs_version="HS2017",
        hs6_code=hs6_code,
        hs6_display=f"{hs6_code} Sample product",
        chapter=hs6_code[:2],
        heading=hs6_code[:4],
        description="Sample description",
        section="I",
        section_name="Sample section",
        created_at=timestamp,
        updated_at=timestamp,
    )


@pytest.mark.asyncio
async def test_resolve_hs6_exact_six_digit_match() -> None:
    repository = AsyncMock(spec=HSRepository)
    repository.get_by_code.return_value = build_product("110311")
    service = ClassificationService(repository)

    result = await service.resolve_hs6("110311")

    repository.get_by_code.assert_awaited_once_with("HS2017", "110311")
    assert isinstance(result, HS6ProductResponse)
    assert result.hs6_code == "110311"


@pytest.mark.asyncio
async def test_resolve_hs6_truncates_hs8_to_hs6() -> None:
    repository = AsyncMock(spec=HSRepository)
    repository.get_by_code.return_value = build_product("110311")
    service = ClassificationService(repository)

    result = await service.resolve_hs6("11031199")

    repository.get_by_code.assert_awaited_once_with("HS2017", "110311")
    assert result.hs6_code == "110311"


@pytest.mark.asyncio
async def test_resolve_hs6_truncates_hs10_to_hs6() -> None:
    repository = AsyncMock(spec=HSRepository)
    repository.get_by_code.return_value = build_product("110311")
    service = ClassificationService(repository)

    result = await service.resolve_hs6("1103110010")

    repository.get_by_code.assert_awaited_once_with("HS2017", "110311")
    assert result.hs6_code == "110311"


@pytest.mark.asyncio
async def test_resolve_hs6_cleans_dots_and_spaces() -> None:
    repository = AsyncMock(spec=HSRepository)
    repository.get_by_code.return_value = build_product("110311")
    service = ClassificationService(repository)

    result = await service.resolve_hs6("11 03.11")

    repository.get_by_code.assert_awaited_once_with("HS2017", "110311")
    assert result.hs6_code == "110311"


@pytest.mark.asyncio
async def test_resolve_hs6_raises_for_code_too_short() -> None:
    repository = AsyncMock(spec=HSRepository)
    service = ClassificationService(repository)

    with pytest.raises(ClassificationError) as exc_info:
        await service.resolve_hs6("11031")

    repository.get_by_code.assert_not_awaited()
    assert "too short" in exc_info.value.message


@pytest.mark.asyncio
async def test_resolve_hs6_raises_when_code_not_found() -> None:
    repository = AsyncMock(spec=HSRepository)
    repository.get_by_code.return_value = None
    service = ClassificationService(repository)

    with pytest.raises(ClassificationError) as exc_info:
        await service.resolve_hs6("999999")

    repository.get_by_code.assert_awaited_once_with("HS2017", "999999")
    assert exc_info.value.detail == {
        "attempted_code": "999999",
        "hs_version": "HS2017",
    }

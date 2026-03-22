"""Unit tests for the status overlay service."""

from __future__ import annotations

from datetime import date
from uuid import UUID
from unittest.mock import AsyncMock

import pytest

from app.services.status_service import StatusService


def _uuid(value: int) -> UUID:
    """Build a stable UUID for test fixtures."""

    return UUID(f"00000000-0000-0000-0000-{value:012d}")


def _status_row(status_type: str) -> dict[str, object]:
    """Return one repository status row."""

    return {
        "status_assertion_id": _uuid(1),
        "source_id": _uuid(2),
        "entity_type": "psr_rule",
        "entity_key": f"PSR:{_uuid(3)}",
        "status_type": status_type,
        "status_text_verbatim": f"Status is {status_type}.",
        "effective_from": date(2024, 1, 1),
        "effective_to": None,
        "page_ref": 1,
        "clause_ref": "Art. 1",
        "confidence_score": 1,
    }


def _transition_row(description: str) -> dict[str, object]:
    """Return one repository transition row."""

    return {
        "transition_id": _uuid(4),
        "source_id": _uuid(5),
        "entity_type": "psr_rule",
        "entity_key": f"PSR:{_uuid(3)}",
        "transition_type": "phase_in",
        "transition_text_verbatim": description,
        "start_date": date(2024, 1, 1),
        "end_date": date(2026, 12, 31),
        "review_trigger": "Scheduled review",
        "page_ref": 2,
    }


@pytest.mark.asyncio
async def test_agreed_status_maps_to_complete_confidence() -> None:
    """Agreed status should produce complete confidence."""

    repository = AsyncMock()
    repository.get_status.return_value = _status_row("agreed")
    repository.get_active_transitions.return_value = []
    service = StatusService(repository)

    result = await service.get_status_overlay("psr_rule", f"PSR:{_uuid(3)}")

    assert result.status_type == "agreed"
    assert result.confidence_class == "complete"


@pytest.mark.asyncio
async def test_provisional_status_maps_to_provisional_confidence() -> None:
    """Provisional status should downgrade confidence."""

    repository = AsyncMock()
    repository.get_status.return_value = _status_row("provisional")
    repository.get_active_transitions.return_value = []
    service = StatusService(repository)

    result = await service.get_status_overlay("psr_rule", f"PSR:{_uuid(3)}")

    assert result.status_type == "provisional"
    assert result.confidence_class == "provisional"


@pytest.mark.asyncio
async def test_pending_status_adds_constraint_message() -> None:
    """Pending status should carry the enforceability warning."""

    repository = AsyncMock()
    repository.get_status.return_value = _status_row("pending")
    repository.get_active_transitions.return_value = []
    service = StatusService(repository)

    result = await service.get_status_overlay("psr_rule", f"PSR:{_uuid(3)}")

    assert result.status_type == "pending"
    assert result.confidence_class == "provisional"
    assert "Rule is pending" in result.constraints[0]


@pytest.mark.asyncio
async def test_no_status_found_returns_unknown_overlay() -> None:
    """The service must never return null when no assertion exists."""

    repository = AsyncMock()
    repository.get_status.return_value = None
    repository.get_active_transitions.return_value = []
    service = StatusService(repository)

    result = await service.get_status_overlay("psr_rule", f"PSR:{_uuid(3)}")

    assert result.status_type == "unknown"
    assert result.confidence_class == "incomplete"


@pytest.mark.asyncio
async def test_active_transition_is_included_in_overlay() -> None:
    """Active transitions should surface in both transitions and constraints."""

    repository = AsyncMock()
    repository.get_status.return_value = _status_row("agreed")
    repository.get_active_transitions.return_value = [
        _transition_row("Transitional quota applies through 2026.")
    ]
    service = StatusService(repository)

    result = await service.get_status_overlay("psr_rule", f"PSR:{_uuid(3)}")

    assert result.active_transitions[0].description == "Transitional quota applies through 2026."
    assert "Transitional quota applies through 2026." in result.constraints

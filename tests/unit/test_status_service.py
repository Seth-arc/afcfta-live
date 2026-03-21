"""Unit tests for status overlay reduction and confidence mapping."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.repositories.status_repository import StatusRepository
from app.schemas.status import StatusOverlay
from app.services.status_service import StatusService


def build_status(status_type: str) -> dict[str, object]:
    """Build a minimal current status assertion mapping for tests."""

    return {
        "status_type": status_type,
        "effective_from": date(2025, 1, 1),
        "effective_to": None,
        "status_text_verbatim": f"Status is {status_type}.",
    }


def build_transition(description: str) -> dict[str, object]:
    """Build a minimal active transition mapping for tests."""

    return {
        "transition_type": "phase_down",
        "transition_text_verbatim": description,
        "start_date": date(2025, 1, 1),
        "end_date": date(2027, 12, 31),
        "review_trigger": "annual_review",
    }


@pytest.mark.asyncio
async def test_get_status_overlay_agreed_is_complete() -> None:
    repository = AsyncMock(spec=StatusRepository)
    repository.get_status.return_value = build_status("agreed")
    repository.get_active_transitions.return_value = []
    service = StatusService(repository)

    result = await service.get_status_overlay("psr_rule", "PSR:psr-123")

    repository.get_status.assert_awaited_once_with("psr_rule", "PSR:psr-123")
    repository.get_active_transitions.assert_awaited_once_with("psr_rule", "PSR:psr-123")
    assert isinstance(result, StatusOverlay)
    assert result.status_type.value == "agreed"
    assert result.confidence_class == "complete"
    assert result.constraints == []


@pytest.mark.asyncio
async def test_get_status_overlay_provisional_is_provisional() -> None:
    repository = AsyncMock(spec=StatusRepository)
    repository.get_status.return_value = build_status("provisional")
    repository.get_active_transitions.return_value = []
    service = StatusService(repository)

    result = await service.get_status_overlay("psr_rule", "PSR:psr-123")

    assert result.status_type.value == "provisional"
    assert result.confidence_class == "provisional"
    assert "Rule is provisional — subject to change" in result.constraints


@pytest.mark.asyncio
async def test_get_status_overlay_pending_adds_constraint() -> None:
    repository = AsyncMock(spec=StatusRepository)
    repository.get_status.return_value = build_status("pending")
    repository.get_active_transitions.return_value = []
    service = StatusService(repository)

    result = await service.get_status_overlay("schedule", "SCHEDULE:schedule-123")

    assert result.status_type.value == "pending"
    assert result.confidence_class == "provisional"
    assert "Rule is pending — not yet enforceable" in result.constraints


@pytest.mark.asyncio
async def test_get_status_overlay_returns_unknown_when_no_status_found() -> None:
    repository = AsyncMock(spec=StatusRepository)
    repository.get_status.return_value = None
    repository.get_active_transitions.return_value = []
    service = StatusService(repository)

    result = await service.get_status_overlay("corridor", "CORRIDOR:GHA:NGA:110311")

    assert result.status_type == "unknown"
    assert result.confidence_class == "incomplete"
    assert result.source_text_verbatim is None
    assert result.active_transitions == []


@pytest.mark.asyncio
async def test_get_status_overlay_includes_active_transition_descriptions() -> None:
    repository = AsyncMock(spec=StatusRepository)
    repository.get_status.return_value = build_status("agreed")
    repository.get_active_transitions.return_value = [
        build_transition("Preferential rate phases down through 2027."),
    ]
    service = StatusService(repository)

    result = await service.get_status_overlay("schedule_line", "SCHEDULE_LINE:line-123")

    assert result.confidence_class == "complete"
    assert len(result.active_transitions) == 1
    assert result.active_transitions[0].description == "Preferential rate phases down through 2027."
    assert "Preferential rate phases down through 2027." in result.constraints

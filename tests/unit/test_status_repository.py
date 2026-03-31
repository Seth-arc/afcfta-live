"""Unit tests for StatusRepository cache-aware batch overlay lookups."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.repositories.status_repository import StatusRepository

from ._repo_fakes import FakeResult, RecordingSession


@pytest.mark.asyncio
async def test_get_status_overlay_rows_returns_cached_value_on_cache_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = RecordingSession([])
    repository = StatusRepository(session)
    cached_rows = [
        {
            "entity_type": "corridor",
            "entity_key": "CORRIDOR:GHA:NGA:110311",
            "status": {"status_type": "in_force"},
            "transitions": [],
        }
    ]

    monkeypatch.setattr(
        "app.repositories.status_repository.get_settings",
        lambda: SimpleNamespace(CACHE_STATUS_LOOKUPS=True, CACHE_TTL_SECONDS=300),
    )
    monkeypatch.setattr(
        "app.repositories.status_repository.cache.get",
        lambda store, key: (True, cached_rows),
    )

    result = await repository.get_status_overlay_rows(
        [("corridor", "CORRIDOR:GHA:NGA:110311")],
        date(2025, 1, 1),
    )

    assert result == cached_rows
    assert session.calls == []


@pytest.mark.asyncio
async def test_get_status_overlay_rows_queries_and_caches_on_cache_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {
        "ordinal": 0,
        "entity_type": "corridor",
        "entity_key": "CORRIDOR:GHA:NGA:110311",
        "status": {"status_type": "in_force"},
        "transitions": [],
    }
    session = RecordingSession([FakeResult(all_mappings=[row])])
    repository = StatusRepository(session)
    put_calls: list[tuple[object, object, object, object]] = []

    monkeypatch.setattr(
        "app.repositories.status_repository.get_settings",
        lambda: SimpleNamespace(CACHE_STATUS_LOOKUPS=True, CACHE_TTL_SECONDS=300),
    )
    monkeypatch.setattr(
        "app.repositories.status_repository.cache.get",
        lambda store, key: (False, None),
    )
    monkeypatch.setattr(
        "app.repositories.status_repository.cache.put",
        lambda store, key, value, ttl: put_calls.append((store, key, value, ttl)),
    )

    result = await repository.get_status_overlay_rows(
        [("corridor", "CORRIDOR:GHA:NGA:110311")],
        date(2025, 1, 1),
    )

    assert result == [row]
    assert put_calls

"""Unit tests for RulesRepository cache and query branches."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.repositories.rules_repository import RulesRepository

from ._repo_fakes import FakeResult, RecordingSession


@pytest.mark.asyncio
async def test_resolve_applicable_psr_returns_cached_value_on_cache_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = RecordingSession([])
    repository = RulesRepository(session)
    cached_row = {"psr_id": uuid4()}

    monkeypatch.setattr(
        "app.repositories.rules_repository.get_settings",
        lambda: SimpleNamespace(CACHE_STATIC_LOOKUPS=True, CACHE_TTL_SECONDS=300),
    )
    monkeypatch.setattr(
        "app.repositories.rules_repository.cache.get",
        lambda store, key: (True, cached_row),
    )

    result = await repository.resolve_applicable_psr(str(uuid4()), date(2025, 1, 1))

    assert result == cached_row
    assert session.calls == []


@pytest.mark.asyncio
async def test_resolve_applicable_psr_queries_and_caches_on_cache_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {"psr_id": uuid4()}
    session = RecordingSession([FakeResult(first_mapping=row)])
    repository = RulesRepository(session)
    put_calls: list[tuple[object, object, object, object]] = []

    monkeypatch.setattr(
        "app.repositories.rules_repository.get_settings",
        lambda: SimpleNamespace(CACHE_STATIC_LOOKUPS=True, CACHE_TTL_SECONDS=300),
    )
    monkeypatch.setattr(
        "app.repositories.rules_repository.cache.get",
        lambda store, key: (False, None),
    )
    monkeypatch.setattr(
        "app.repositories.rules_repository.cache.put",
        lambda store, key, value, ttl: put_calls.append((store, key, value, ttl)),
    )

    result = await repository.resolve_applicable_psr(str(uuid4()), date(2025, 1, 1))

    assert result == row
    assert put_calls


@pytest.mark.asyncio
async def test_get_rules_by_hs6_returns_none_when_psr_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = RecordingSession([FakeResult(first_mapping=None)])
    repository = RulesRepository(session)

    monkeypatch.setattr(
        "app.repositories.rules_repository.get_settings",
        lambda: SimpleNamespace(CACHE_STATIC_LOOKUPS=False, CACHE_TTL_SECONDS=300),
    )

    assert await repository.get_rules_by_hs6("HS2017", "110311", date(2025, 1, 1)) is None


@pytest.mark.asyncio
async def test_get_rules_by_hs6_returns_bundle_with_components_and_pathways(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    psr_id = uuid4()
    psr_row = {"psr_id": psr_id, "source_id": uuid4()}
    component_row = {"component_id": uuid4()}
    pathway_row = {"pathway_id": uuid4()}
    session = RecordingSession(
        [
            FakeResult(first_mapping=psr_row),
            FakeResult(all_mappings=[component_row]),
            FakeResult(all_mappings=[pathway_row]),
        ]
    )
    repository = RulesRepository(session)

    monkeypatch.setattr(
        "app.repositories.rules_repository.get_settings",
        lambda: SimpleNamespace(CACHE_STATIC_LOOKUPS=False, CACHE_TTL_SECONDS=300),
    )

    result = await repository.get_rules_by_hs6("HS2017", "110311", date(2025, 1, 1))

    assert result == {"psr": psr_row, "components": [component_row], "pathways": [pathway_row]}


@pytest.mark.asyncio
async def test_get_psr_components_uses_cache_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = RecordingSession([])
    repository = RulesRepository(session)
    cached_rows = [{"component_id": uuid4()}]

    monkeypatch.setattr(
        "app.repositories.rules_repository.get_settings",
        lambda: SimpleNamespace(CACHE_STATIC_LOOKUPS=True, CACHE_TTL_SECONDS=300),
    )
    monkeypatch.setattr(
        "app.repositories.rules_repository.cache.get",
        lambda store, key: (True, cached_rows),
    )

    assert await repository.get_psr_components(str(uuid4())) == cached_rows
    assert session.calls == []


@pytest.mark.asyncio
async def test_get_psr_components_queries_and_caches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [{"component_id": uuid4()}]
    session = RecordingSession([FakeResult(all_mappings=rows)])
    repository = RulesRepository(session)
    put_calls: list[tuple[object, object, object, object]] = []

    monkeypatch.setattr(
        "app.repositories.rules_repository.get_settings",
        lambda: SimpleNamespace(CACHE_STATIC_LOOKUPS=True, CACHE_TTL_SECONDS=300),
    )
    monkeypatch.setattr(
        "app.repositories.rules_repository.cache.get",
        lambda store, key: (False, None),
    )
    monkeypatch.setattr(
        "app.repositories.rules_repository.cache.put",
        lambda store, key, value, ttl: put_calls.append((store, key, value, ttl)),
    )

    assert await repository.get_psr_components(str(uuid4())) == rows
    assert put_calls


@pytest.mark.asyncio
async def test_get_pathways_uses_cache_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = RecordingSession([])
    repository = RulesRepository(session)
    cached_rows = [{"pathway_id": uuid4()}]

    monkeypatch.setattr(
        "app.repositories.rules_repository.get_settings",
        lambda: SimpleNamespace(CACHE_STATIC_LOOKUPS=True, CACHE_TTL_SECONDS=300),
    )
    monkeypatch.setattr(
        "app.repositories.rules_repository.cache.get",
        lambda store, key: (True, cached_rows),
    )

    assert await repository.get_pathways(str(uuid4()), date(2025, 1, 1)) == cached_rows
    assert session.calls == []


@pytest.mark.asyncio
async def test_get_pathways_queries_and_caches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [{"pathway_id": uuid4()}]
    session = RecordingSession([FakeResult(all_mappings=rows)])
    repository = RulesRepository(session)
    put_calls: list[tuple[object, object, object, object]] = []

    monkeypatch.setattr(
        "app.repositories.rules_repository.get_settings",
        lambda: SimpleNamespace(CACHE_STATIC_LOOKUPS=True, CACHE_TTL_SECONDS=300),
    )
    monkeypatch.setattr(
        "app.repositories.rules_repository.cache.get",
        lambda store, key: (False, None),
    )
    monkeypatch.setattr(
        "app.repositories.rules_repository.cache.put",
        lambda store, key, value, ttl: put_calls.append((store, key, value, ttl)),
    )

    assert await repository.get_pathways(str(uuid4()), date(2025, 1, 1)) == rows
    assert put_calls

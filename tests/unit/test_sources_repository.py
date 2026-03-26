"""Unit tests for SourcesRepository SQL-building branches."""

from __future__ import annotations

from uuid import uuid4

from app.repositories.sources_repository import SourcesRepository

from ._repo_fakes import FakeResult, RecordingSession


async def test_sources_repository_crud_and_listing_paths() -> None:
    source_id = str(uuid4())
    provision_id = str(uuid4())
    row = {"source_id": source_id}
    provision_row = {"provision_id": provision_id, "source_id": source_id}
    session = RecordingSession(
        [
            FakeResult(one_mapping=row),
            FakeResult(first_mapping=row),
            FakeResult(all_mappings=[row]),
            FakeResult(first_mapping=row),
            FakeResult(first_mapping=row),
            FakeResult(one_mapping=provision_row),
            FakeResult(first_mapping=provision_row),
            FakeResult(all_mappings=[provision_row]),
            FakeResult(first_mapping=provision_row),
            FakeResult(first_mapping=provision_row),
            FakeResult(all_mappings=[provision_row]),
            FakeResult(all_mappings=[provision_row]),
        ]
    )
    repository = SourcesRepository(session)

    assert await repository.create_source({"title": "Source"}) == row
    assert await repository.get_source(source_id) == row
    assert await repository.list_sources(
        source_type="appendix",
        authority_tier="binding",
        status="current",
        limit=5,
        offset=2,
    ) == [row]
    assert await repository.update_source(source_id, {"title": "Updated"}) == row
    assert await repository.delete_source(source_id) == row

    assert await repository.create_provision({"topic_primary": "origin_rules"}) == provision_row
    assert await repository.get_provision(provision_id) == provision_row
    assert await repository.list_provisions(
        topic_primary="origin_rules",
        annex_ref="Appendix IV",
        source_id=source_id,
        limit=3,
        offset=1,
    ) == [provision_row]
    assert await repository.update_provision(provision_id, {"annex_ref": "Appendix IV"}) == provision_row
    assert await repository.delete_provision(provision_id) == provision_row
    assert await repository.get_provisions_for_source(source_id, limit=5) == [provision_row]
    assert await repository.lookup_by_topic("origin_rules", limit=7) == [provision_row]


async def test_sources_repository_update_empty_values_falls_back_to_getters() -> None:
    source_id = str(uuid4())
    provision_id = str(uuid4())
    row = {"source_id": source_id}
    provision_row = {"provision_id": provision_id}
    session = RecordingSession(
        [
            FakeResult(first_mapping=row),
            FakeResult(first_mapping=provision_row),
        ]
    )
    repository = SourcesRepository(session)

    assert await repository.update_source(source_id, {}) == row
    assert await repository.update_provision(provision_id, {}) == provision_row

    assert len(session.calls) == 2

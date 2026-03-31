from __future__ import annotations

from app.core.load_test_fixtures import LOAD_FIXTURE_CREATED_BY, LOAD_TEST_FIXTURES
from scripts.seed_data import SEEDED_CORRIDORS, build_load_case_rows, build_seed_rows


def test_corridor_profiles_are_explicitly_narrowed_to_seeded_pairs() -> None:
    seed_rows = build_seed_rows()

    actual_corridors = {
        (row["exporter_state"], row["importer_state"])
        for row in seed_rows["corridor_profile"]["rows"]
    }

    assert actual_corridors == set(SEEDED_CORRIDORS)


def test_load_fixtures_stay_within_seeded_corridor_profile_surface() -> None:
    seeded_corridors = set(SEEDED_CORRIDORS)
    fixture_corridors = {
        (str(fixture["request"]["exporter"]), str(fixture["request"]["importer"]))
        for fixture in LOAD_TEST_FIXTURES
    }

    assert fixture_corridors <= seeded_corridors


def test_build_load_case_rows_mark_seed_owned_cases_for_gate_load_reuse() -> None:
    load_cases, _ = build_load_case_rows()

    assert len(load_cases) == len(LOAD_TEST_FIXTURES)
    assert {str(row["case_id"]) for row in load_cases} == {
        str(fixture["case_id"]) for fixture in LOAD_TEST_FIXTURES
    }
    assert {row["created_by"] for row in load_cases} == {LOAD_FIXTURE_CREATED_BY}
    assert {row["updated_by"] for row in load_cases} == {LOAD_FIXTURE_CREATED_BY}

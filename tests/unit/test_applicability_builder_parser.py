"""Fixture-driven unit tests for Appendix IV applicability generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.parsers.applicability_builder import applicability_summary, build_applicability_rows


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "appendix_iv_applicability_cases.json"


def _load_cases() -> list[dict[str, Any]]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def _row_summary(rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "hs6_code": row.hs6_code,
            "hs6_id": row.hs6_id,
            "psr_hs_code": row.psr_hs_code,
            "applicability_type": row.applicability_type,
            "priority_rank": row.priority_rank,
        }
        for row in rows
    ]


@pytest.mark.parametrize(
    ("case_id", "pathway_rows", "hs6_rows", "expected_rows", "expected_stats"),
    [
        (
            case["case_id"],
            case["pathway_rows"],
            case["hs6_rows"],
            case["expected_rows"],
            case["expected_stats"],
        )
        for case in _load_cases()
    ],
    ids=[case["case_id"] for case in _load_cases()],
)
def test_build_applicability_rows_matches_expected_fixtures(
    case_id: str,
    pathway_rows: list[dict[str, str]],
    hs6_rows: list[dict[str, str]],
    expected_rows: list[dict[str, Any]],
    expected_stats: dict[str, int],
) -> None:
    """The applicability builder should preserve most-specific-wins precedence over fixed inputs."""

    actual_rows, actual_stats = build_applicability_rows(pathway_rows, hs6_rows)

    assert _row_summary(actual_rows) == expected_rows, case_id
    assert actual_stats == expected_stats, case_id


def test_applicability_summary_counts_each_applicability_type() -> None:
    """Summary counts should reflect the output applicability categories."""

    pathway_rows = [
        {"hs_code": "01", "hs_level": "chapter", "page_ref": "1", "legal_rule_text_verbatim": "chapter"},
        {"hs_code": "0101", "hs_level": "heading", "page_ref": "2", "legal_rule_text_verbatim": "heading"},
        {
            "hs_code": "0101RANGE",
            "hs_level": "subheading",
            "page_ref": "3",
            "legal_rule_text_verbatim": "range",
            "hs_code_start": "010120",
            "hs_code_end": "010129",
        },
        {"hs_code": "010110", "hs_level": "subheading", "page_ref": "4", "legal_rule_text_verbatim": "direct"},
    ]
    hs6_rows = [
        {"hs6_id": "1", "hs6_code": "010110"},
        {"hs6_id": "2", "hs6_code": "010121"},
        {"hs6_id": "3", "hs6_code": "010130"},
        {"hs6_id": "4", "hs6_code": "019999"},
    ]

    rows, _stats = build_applicability_rows(pathway_rows, hs6_rows)

    assert applicability_summary(rows) == {
        "direct": 1,
        "range": 1,
        "inherited_heading": 1,
        "inherited_chapter": 1,
    }


def test_range_rule_beats_heading_and_chapter_when_boundaries_match() -> None:
    """Range matches should win before inherited heading and chapter fallbacks."""

    pathway_rows = [
        {"hs_code": "01", "hs_level": "chapter", "page_ref": "1", "legal_rule_text_verbatim": "chapter"},
        {"hs_code": "0101", "hs_level": "heading", "page_ref": "2", "legal_rule_text_verbatim": "heading"},
        {
            "hs_code": "0101RANGE",
            "hs_level": "subheading",
            "page_ref": "3",
            "legal_rule_text_verbatim": "range",
            "hs_code_start": "010120",
            "hs_code_end": "010129",
        },
    ]
    hs6_rows = [{"hs6_id": "2", "hs6_code": "010121"}]

    rows, stats = build_applicability_rows(pathway_rows, hs6_rows)

    assert _row_summary(rows) == [
        {
            "hs6_code": "010121",
            "hs6_id": "2",
            "psr_hs_code": "0101RANGE",
            "applicability_type": "range",
            "priority_rank": 1,
        }
    ]
    assert stats["range_rules"] == 1
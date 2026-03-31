"""Unit tests for verification-harness git dirtiness filtering."""

from __future__ import annotations

from scripts import run_verification


def test_is_ignored_git_status_path_treats_generated_cache_as_non_blocking() -> None:
    """Generated Python/Hypothesis artifacts should not block release verification."""

    assert run_verification._is_ignored_git_status_path(
        "app/api/__pycache__/deps.cpython-311.pyc"
    )
    assert run_verification._is_ignored_git_status_path(
        "tests\\unit\\__pycache__\\test_cases_api.cpython-311-pytest-9.0.2.pyc"
    )
    assert run_verification._is_ignored_git_status_path(".hypothesis/constants/abcdef1234567890")
    assert run_verification._is_ignored_git_status_path(".coverage")
    assert run_verification._is_ignored_git_status_path(".coverage.unit")


def test_is_ignored_git_status_path_keeps_real_repo_changes_blocking() -> None:
    """Tracked source edits must still fail the clean-worktree gate."""

    assert not run_verification._is_ignored_git_status_path("app/services/eligibility_service.py")
    assert not run_verification._is_ignored_git_status_path("tests/unit/test_eligibility_service.py")
    assert not run_verification._is_ignored_git_status_path("README.md")

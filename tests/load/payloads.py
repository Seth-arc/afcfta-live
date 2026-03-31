"""Deterministic steady-state payloads for the AIS load test harness.

These payloads include preseeded ``case_id`` values so the harness measures the
repeatable assessment path used by trader workflows after case creation, rather
than repeatedly benchmarking one-time case bootstrap overhead.
"""

from __future__ import annotations

from copy import deepcopy

from app.core.load_test_fixtures import LOAD_TEST_FIXTURES


LOAD_PAYLOADS: list[dict] = [
    deepcopy(fixture["request"]) for fixture in LOAD_TEST_FIXTURES
]

"""Minimal in-process TTL caches for repeatable read-heavy lookups.

This module provides named dict-backed TTL caches for data that is safe to
reuse within one worker process:

- HS6 product rows
- PSR rules, components, and pathways
- tariff schedule + year-rate bundles
- immutable source/provision snapshots used for audit provenance
- read-only case bundles used by replay/load flows
- opt-in status-overlay batches used only for frozen gate datasets

Status overlays are special: they remain time-windowed and operator-mutable, so
they are not cached by default. Set ``CACHE_STATUS_LOOKUPS=true`` only for
frozen, operator-controlled datasets such as the March 30 load/gate rerun where
``status_assertion`` and ``transition_clause`` are not changing mid-run.
"""

from __future__ import annotations

import time
from typing import Any

# ---------------------------------------------------------------------------
# Named stores - one dict per domain so targeted clearing is straightforward.
# Each entry: hashable_key -> (value, expires_at_monotonic_seconds)
# ---------------------------------------------------------------------------

hs6_store: dict[tuple, tuple[Any, float]] = {}
psr_store: dict[tuple, tuple[Any, float]] = {}
tariff_store: dict[tuple, tuple[Any, float]] = {}
evidence_store: dict[tuple, tuple[Any, float]] = {}
provenance_store: dict[tuple, tuple[Any, float]] = {}
case_store: dict[tuple, tuple[Any, float]] = {}
status_store: dict[tuple, tuple[Any, float]] = {}


def get(store: dict[tuple, tuple[Any, float]], key: tuple) -> tuple[bool, Any]:
    """Return ``(True, value)`` on a live hit, ``(False, None)`` on a miss."""

    entry = store.get(key)
    if entry is None:
        return False, None
    value, expires_at = entry
    if time.monotonic() > expires_at:
        del store[key]
        return False, None
    return True, value


def put(
    store: dict[tuple, tuple[Any, float]],
    key: tuple,
    value: Any,
    ttl_seconds: int,
) -> None:
    """Insert or refresh one cache entry with an absolute expiry timestamp."""

    store[key] = (value, time.monotonic() + ttl_seconds)


def clear_all() -> None:
    """Evict every cached entry across all stores.

    Call this:
    - after any parser or tariff-schedule promotion
    - after any manual source/provision/status correction
    - in integration test teardown when the database state has changed
    - whenever you need to force a cold-cache measurement in load testing
    """

    hs6_store.clear()
    psr_store.clear()
    tariff_store.clear()
    evidence_store.clear()
    provenance_store.clear()
    case_store.clear()
    status_store.clear()

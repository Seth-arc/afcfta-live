"""Minimal in-process TTL cache for static reference lookups.

This module provides three named dict-backed TTL caches for reference data
that is safe to cache in-process: HS6 product codes, PSR rules (with
components and pathways), and tariff schedule lines.

Why these three and nothing else
---------------------------------
- HS6 product rows are international classification standards.  They change
  only when a new HS version is seeded.  Repeated assessments for the same
  product hit the same row every time.
- PSR rules and pathways are published legal text that changes only through a
  formal parser promotion.  They are the 3 heaviest DB queries per assessment.
- Tariff schedule + year-rate rows are gazette-sourced.  They change only
  through a tariff-schedule promotion.  They are the 2 remaining DB queries
  per assessment.

What is intentionally NOT cached
----------------------------------
- Eligibility decisions  — must never be cached (correctness requirement).
- Status assertions      — time-windowed; could change with operator updates
                           mid-day.  Caching would serve stale legal status.
- Cases and evaluations  — user-specific and append-only.
- Evidence requirements  — small result set, not on the high-frequency path.
- Intelligence / alerts  — operator-mutable, low query volume.

Invalidation assumptions
------------------------
Each in-process cache is a dict scoped to one uvicorn worker process.  With
multiple workers, each process holds its own cache copy and invalidation is
not coordinated across processes.

After any of the following events, the cache MUST be considered stale:
  1. A parser promotion (HS6, PSR rules, or tariff schedules updated).
  2. A manual data correction applied directly to the database.

Safe strategies:
  a. Set CACHE_STATIC_LOOKUPS=false and restart workers during the promotion
     window, then re-enable after the promotion is confirmed.
  b. Accept that the TTL (default 5 minutes) limits the stale-data window if
     the restart window is missed — no cached entry survives longer than the
     configured TTL regardless.

The cache is enabled by default for static reference data so production
deployments benefit without extra configuration.  Set
CACHE_STATIC_LOOKUPS=false when you need a no-cache baseline or a strict
immediate-consistency promotion window.
"""

from __future__ import annotations

import time
from typing import Any

# ---------------------------------------------------------------------------
# Named stores — one dict per domain so targeted clearing is straightforward.
# Each entry: hashable_key → (value, expires_at_monotonic_seconds)
# ---------------------------------------------------------------------------

hs6_store: dict[tuple, tuple[Any, float]] = {}
psr_store: dict[tuple, tuple[Any, float]] = {}
tariff_store: dict[tuple, tuple[Any, float]] = {}


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------


def get(store: dict[tuple, tuple[Any, float]], key: tuple) -> tuple[bool, Any]:
    """Return ``(True, value)`` on a live hit, ``(False, None)`` on a miss.

    Expired entries are evicted lazily on access so the cache never serves
    stale data.
    """
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
    """Evict every cached entry across all three stores.

    Call this:
    - after any parser or tariff-schedule promotion
    - in integration test teardown when the database state has changed
    - whenever you need to force a cold-cache measurement in load testing
    """
    hs6_store.clear()
    psr_store.clear()
    tariff_store.clear()

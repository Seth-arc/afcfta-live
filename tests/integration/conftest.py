"""Integration test configuration.

Three Windows-specific issues are addressed here:

1.  RuntimeError: Event loop is closed  (affects API tests that hit assessment routes)
    Root cause: app/db/session.py imports get_engine via a direct ``from … import``
    name binding. Patching app.db.base.get_engine alone does not reach the copy
    already bound inside app.db.session. Both module-level names must be replaced.

2.  AttributeError: 'NoneType' object has no attribute 'send'  (affects repository tests)
    Root cause: Python 3.11 on Windows defaults to ProactorEventLoop. Its
    IocpProactor.close() nulls _loop._proactor during teardown; any in-flight asyncpg
    write attempt then raises AttributeError. Switching to WindowsSelectorEventLoopPolicy
    replaces the proactor transport with a selector transport whose close path drops
    pending writes silently rather than raising.

3.  RuntimeError: Task <Task pending coro=<AsyncSession.close()>>  (affects repository tests)
    Root cause: SQLAlchemy's async session teardown schedules an internal
    AsyncSession.close() Task on the event loop during fixture cleanup. The fixture's
    teardown coroutine returns before that task executes, and pytest-asyncio closes
    the loop while the task is still pending. The _drain_async_tasks autouse fixture
    sits in the outer (conftest) scope so it tears down AFTER each test's per-test
    session fixture. Its yield-then-sleep loop gives the event loop several extra
    turns to drain any pending cleanup tasks before the loop is closed.

All patches are integration-only and do not change production behaviour.
NullPool is kept as belt-and-suspenders: no pooled connections can leak across
event-loop boundaries between tests.
"""

from __future__ import annotations

import asyncio
import sys

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import text

import app.core.cache as reference_cache
import app.db.base as _db_base
import app.db.session as _db_session
from app.core.load_test_fixtures import LOAD_FIXTURE_CREATED_BY

# Switch to SelectorEventLoop on Windows so that asyncpg transport teardown
# drops pending writes silently instead of crashing with AttributeError.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(autouse=True, scope="session")
def _nullpool_engine() -> None:  # type: ignore[return]
    """Replace every reference to the shared engine with a NullPool engine.

    Patches both app.db.base.get_engine (used by get_async_session_factory)
    and app.db.session.get_engine (used by assessment_session_context) so that
    every DB call in integration tests opens and closes its own connection
    within the same event loop and never holds a connection across test boundaries.
    """
    from app.config import get_settings

    _db_base.get_engine.cache_clear()
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)

    _orig_base = _db_base.get_engine
    _orig_session = _db_session.get_engine

    _db_base.get_engine = lambda: engine  # type: ignore[assignment]
    _db_session.get_engine = lambda: engine  # type: ignore[assignment]

    yield

    _db_base.get_engine = _orig_base  # type: ignore[assignment]
    _db_session.get_engine = _orig_session  # type: ignore[assignment]
    _db_base.get_engine.cache_clear()


@pytest_asyncio.fixture(autouse=True, scope="session")
async def _reset_mutable_integration_state(
    _nullpool_engine: None,
) -> None:  # type: ignore[return]
    """Clear prior synthetic state so integration suites are rerunnable on the same DB.

    The local pre-production audit runs integration files multiple times against one
    seeded database. Without a session-start cleanup, previously inserted synthetic
    rows can collide with deterministic fixture codes or fixed repository fixtures.
    """

    reference_cache.clear_all()
    session_factory = _db_base.get_async_session_factory()
    async with session_factory() as session:
        async with session.begin():
            statements = [
                "DELETE FROM eligibility_check_result",
                "DELETE FROM eligibility_evaluation",
                "DELETE FROM alert_event",
                f"""
                DELETE FROM case_input_fact
                WHERE case_id IN (
                    SELECT case_id
                    FROM case_file
                    WHERE created_by IS DISTINCT FROM '{LOAD_FIXTURE_CREATED_BY}'
                )
                """,
                f"""
                DELETE FROM case_file
                WHERE created_by IS DISTINCT FROM '{LOAD_FIXTURE_CREATED_BY}'
                """,
                """
                DELETE FROM transition_clause
                WHERE source_id IN (
                    SELECT source_id FROM source_registry WHERE source_group = 'pytest'
                )
                """,
                """
                DELETE FROM status_assertion
                WHERE source_id IN (
                    SELECT source_id FROM source_registry WHERE source_group = 'pytest'
                )
                """,
                """
                DELETE FROM legal_provision
                WHERE source_id IN (
                    SELECT source_id FROM source_registry WHERE source_group = 'pytest'
                )
                """,
                """
                DELETE FROM tariff_schedule_rate_by_year
                WHERE source_id IN (
                    SELECT source_id FROM source_registry WHERE source_group = 'pytest'
                )
                OR schedule_line_id IN (
                    SELECT tsl.schedule_line_id
                    FROM tariff_schedule_line tsl
                    JOIN tariff_schedule_header tsh
                      ON tsh.schedule_id = tsl.schedule_id
                    JOIN source_registry sr
                      ON sr.source_id = tsh.source_id
                    WHERE sr.source_group = 'pytest'
                )
                """,
                """
                DELETE FROM tariff_schedule_line
                WHERE schedule_id IN (
                    SELECT tsh.schedule_id
                    FROM tariff_schedule_header tsh
                    JOIN source_registry sr
                      ON sr.source_id = tsh.source_id
                    WHERE sr.source_group = 'pytest'
                )
                """,
                """
                DELETE FROM tariff_schedule_header
                WHERE source_id IN (
                    SELECT source_id FROM source_registry WHERE source_group = 'pytest'
                )
                """,
                """
                DELETE FROM hs6_psr_applicability
                WHERE psr_id IN (
                    SELECT psr_id FROM psr_rule
                    WHERE source_id IN (
                        SELECT source_id FROM source_registry WHERE source_group = 'pytest'
                    )
                )
                """,
                """
                DELETE FROM eligibility_rule_pathway
                WHERE psr_id IN (
                    SELECT psr_id FROM psr_rule
                    WHERE source_id IN (
                        SELECT source_id FROM source_registry WHERE source_group = 'pytest'
                    )
                )
                """,
                """
                DELETE FROM psr_rule_component
                WHERE psr_id IN (
                    SELECT psr_id FROM psr_rule
                    WHERE source_id IN (
                        SELECT source_id FROM source_registry WHERE source_group = 'pytest'
                    )
                )
                """,
                """
                DELETE FROM psr_rule
                WHERE source_id IN (
                    SELECT source_id FROM source_registry WHERE source_group = 'pytest'
                )
                """,
                """
                DELETE FROM hs6_product
                WHERE description LIKE 'Synthetic %'
                """,
                """
                DELETE FROM source_registry
                WHERE source_group = 'pytest'
                """,
            ]
            for statement in statements:
                await session.execute(text(statement))
    reference_cache.clear_all()
    yield
    reference_cache.clear_all()


@pytest.fixture(autouse=True)
async def _drain_async_tasks() -> None:  # type: ignore[return]
    """Drain pending async tasks after each test's fixtures have cleaned up.

    This fixture lives in the outer (conftest) scope.  pytest tears down
    fixtures in reverse setup order, so this fixture's teardown runs AFTER
    the per-test async session fixtures defined in individual test files.
    The repeated sleep(0) calls yield control to the event loop, allowing
    any SQLAlchemy/asyncpg cleanup Tasks that were scheduled-but-not-yet-run
    during session fixture teardown to complete before the loop closes.
    """
    yield
    for _ in range(10):
        await asyncio.sleep(0)


@pytest.fixture(autouse=True)
def _clear_static_reference_cache() -> None:  # type: ignore[return]
    """Keep integration tests isolated when static lookup caching is enabled."""

    reference_cache.clear_all()
    yield
    reference_cache.clear_all()

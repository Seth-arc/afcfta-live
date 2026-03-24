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
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import app.db.base as _db_base
import app.db.session as _db_session

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

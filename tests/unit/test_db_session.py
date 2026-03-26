"""Unit tests for database session lifecycle helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import EvaluationPersistenceError
from app.db import session as db_session


class _FakeConnection:
    async def execution_options(self, **_kwargs):
        return self


class _FakeConnectionContext:
    async def __aenter__(self) -> _FakeConnection:
        return _FakeConnection()

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeEngine:
    def connect(self) -> _FakeConnectionContext:
        return _FakeConnectionContext()


class _FakeBeginContext:
    def __init__(self, *, fail_on_exit: bool) -> None:
        self.fail_on_exit = fail_on_exit

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None and self.fail_on_exit:
            raise RuntimeError("commit failed")
        return False


class _FakeSession:
    def __init__(self, *, fail_on_exit: bool) -> None:
        self.fail_on_exit = fail_on_exit

    def begin(self) -> _FakeBeginContext:
        return _FakeBeginContext(fail_on_exit=self.fail_on_exit)


class _FakeSessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> _FakeSession:
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def _fake_factory(*, fail_on_exit: bool):
    session = _FakeSession(fail_on_exit=fail_on_exit)

    def _factory(bind=None):
        return _FakeSessionContext(session)

    return _factory


@pytest.mark.asyncio
async def test_assessment_session_context_wraps_commit_close_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(db_session, "get_engine", lambda: _FakeEngine())
    monkeypatch.setattr(
        db_session,
        "get_async_session_factory",
        lambda bind=None: _fake_factory(fail_on_exit=True),
    )

    with pytest.raises(EvaluationPersistenceError) as exc_info:
        async with db_session.assessment_session_context():
            pass

    assert exc_info.value.detail == {"reason": "assessment_transaction_close_failed"}


@pytest.mark.asyncio
async def test_assessment_session_context_preserves_body_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(db_session, "get_engine", lambda: _FakeEngine())
    monkeypatch.setattr(
        db_session,
        "get_async_session_factory",
        lambda bind=None: _fake_factory(fail_on_exit=False),
    )

    with pytest.raises(RuntimeError, match="body failed"):
        async with db_session.assessment_session_context():
            raise RuntimeError("body failed")

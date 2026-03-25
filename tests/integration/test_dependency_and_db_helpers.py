"""Integration-targeted tests for dependency factories and database helpers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID
from unittest.mock import AsyncMock

import pytest

import app.api.deps as deps
import app.db.base as db_base
import app.db.session as db_session
from app.config import Settings
from app.schemas.health import PoolStats
from app.services.eligibility_service import EligibilityService


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_redis_rate_limiter_uses_atomic_eval_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []

    class FakeRedisClient:
        async def eval(self, *args: object) -> list[int]:
            calls.append(args)
            return [1, 0, 3]

    monkeypatch.setattr(deps.time, "time", lambda: 100.0)
    monkeypatch.setattr(
        deps.uuid,
        "uuid4",
        lambda: UUID("00000000-0000-0000-0000-000000000001"),
    )

    limiter = deps.RedisRateLimiter(FakeRedisClient())
    policy = deps.RateLimitPolicy(policy_name="default", max_requests=4, window_seconds=60)

    result = await limiter.check(subject="pytest-suite", policy=policy)

    assert result == {
        "allowed": True,
        "retry_after_seconds": 0,
        "remaining": 3,
    }
    assert calls == [
        (
            deps._SLIDING_WINDOW_LUA,
            1,
            "rl:default:pytest-suite",
            "100.0",
            "40.0",
            "4",
            "60",
            "00000000-0000-0000-0000-000000000001",
        )
    ]


@pytest.mark.asyncio
async def test_require_rate_limit_returns_early_when_disabled(
    test_settings: Settings,
) -> None:
    limiter = SimpleNamespace(check=AsyncMock())
    request = SimpleNamespace(
        state=SimpleNamespace(),
        client=None,
        app=SimpleNamespace(state=SimpleNamespace(rate_limiter=limiter)),
    )
    enforce = deps.require_rate_limit("default")

    await enforce(
        request,
        test_settings.model_copy(update={"RATE_LIMIT_ENABLED": False}),
    )

    limiter.check.assert_not_awaited()


@pytest.mark.asyncio
async def test_require_rate_limit_uses_anonymous_subject_when_request_has_no_client(
    test_settings: Settings,
) -> None:
    calls: list[tuple[str, deps.RateLimitPolicy]] = []

    class FakeLimiter:
        async def check(
            self,
            *,
            subject: str,
            policy: deps.RateLimitPolicy,
        ) -> dict[str, int | bool]:
            calls.append((subject, policy))
            return {
                "allowed": True,
                "retry_after_seconds": 0,
                "remaining": 7,
            }

    request = SimpleNamespace(
        state=SimpleNamespace(),
        client=None,
        app=SimpleNamespace(state=SimpleNamespace(rate_limiter=FakeLimiter())),
    )
    enforce = deps.require_rate_limit("default")

    await enforce(request, test_settings)

    assert calls and calls[0][0] == "anonymous"
    assert request.state.rate_limit_policy == "default"
    assert request.state.rate_limit_remaining == 7


@pytest.mark.asyncio
async def test_service_factories_bind_the_provided_session() -> None:
    session = object()

    cases_repository = await deps.get_cases_repository(session)
    sources_repository = await deps.get_sources_repository(session)
    intelligence_repository = await deps.get_intelligence_repository(session)
    audit_service = await deps.get_audit_service(session)
    classification_service = await deps.get_classification_service(session)
    rule_service = await deps.get_rule_resolution_service(session)
    tariff_service = await deps.get_tariff_resolution_service(session)
    status_service = await deps.get_status_service(session)
    evidence_service = await deps.get_evidence_service(session)
    fact_normalization_service = await deps.get_fact_normalization_service(session)
    expression_evaluator = await deps.get_expression_evaluator(session)
    general_rules_service = await deps.get_general_origin_rules_service(session)
    eligibility_service = await deps.get_eligibility_service(session)
    assessment_service = await deps.get_assessment_eligibility_service(session)

    assert cases_repository.session is session
    assert sources_repository.session is session
    assert intelligence_repository.session is session
    assert audit_service.evaluations_repository.session is session
    assert classification_service.hs_repository.session is session
    assert rule_service.hs_repository.session is session
    assert rule_service.rules_repository.session is session
    assert tariff_service.tariffs_repository.session is session
    assert status_service.status_repository.session is session
    assert evidence_service.evidence_repository.session is session
    assert fact_normalization_service.__class__.__name__ == "FactNormalizationService"
    assert expression_evaluator.__class__.__name__ == "ExpressionEvaluator"
    assert general_rules_service.__class__.__name__ == "GeneralOriginRulesService"
    assert isinstance(eligibility_service, EligibilityService)
    assert eligibility_service.classification_service.hs_repository.session is session
    assert eligibility_service.audit_service.sources_repository.session is session
    assert isinstance(assessment_service, EligibilityService)
    assert assessment_service.cases_repository.session is session


@pytest.mark.asyncio
async def test_assessment_eligibility_service_context_builds_only_when_entered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered: list[str] = []
    built_with: list[object] = []

    @asynccontextmanager
    async def fake_assessment_session_context():
        entered.append("entered")
        yield "repeatable-read-session"

    def fake_build(session: object) -> str:
        built_with.append(session)
        return "eligibility-service"

    monkeypatch.setattr("app.db.session.assessment_session_context", fake_assessment_session_context)
    monkeypatch.setattr(deps, "_build_eligibility_service", fake_build)

    context = deps.assessment_eligibility_service_context()

    assert entered == []
    assert built_with == []

    async with context as service:
        assert service == "eligibility-service"

    assert entered == ["entered"]
    assert built_with == ["repeatable-read-session"]


def test_get_async_session_factory_uses_engine_when_bind_is_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_async_sessionmaker(*, bind: object, class_: object, expire_on_commit: bool) -> str:
        captured["bind"] = bind
        captured["class_"] = class_
        captured["expire_on_commit"] = expire_on_commit
        return "factory"

    monkeypatch.setattr(db_base, "get_engine", lambda: "default-engine")
    monkeypatch.setattr(db_base, "async_sessionmaker", fake_async_sessionmaker)

    factory = db_base.get_async_session_factory()

    assert factory == "factory"
    assert captured["bind"] == "default-engine"
    assert captured["expire_on_commit"] is False


def test_get_async_session_factory_preserves_explicit_bind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_async_sessionmaker(*, bind: object, class_: object, expire_on_commit: bool) -> str:
        captured["bind"] = bind
        return "factory"

    explicit_bind = object()
    monkeypatch.setattr(db_base, "async_sessionmaker", fake_async_sessionmaker)

    factory = db_base.get_async_session_factory(bind=explicit_bind)

    assert factory == "factory"
    assert captured["bind"] is explicit_bind


@pytest.mark.parametrize(
    ("checked_out", "pool_size", "expected"),
    [
        (0, 0, "ok"),
        (2, 4, "ok"),
        (3, 4, "elevated"),
        (19, 20, "saturated"),
    ],
)
def test_classify_pool_pressure_boundaries(
    checked_out: int,
    pool_size: int,
    expected: str,
) -> None:
    assert db_base.classify_pool_pressure(checked_out, pool_size) == expected


def test_get_pool_stats_reports_counts_from_queue_pool_like_interface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_pool = SimpleNamespace(
        checkedout=lambda: 3,
        size=lambda: 4,
        overflow=lambda: -2,
        checkedin=lambda: 1,
    )
    monkeypatch.setattr(db_base, "get_engine", lambda: SimpleNamespace(pool=fake_pool))

    result = db_base.get_pool_stats()

    assert result == {
        "checked_out": 3,
        "pool_size": 4,
        "overflow": 0,
        "checked_in": 1,
        "pool_pressure": "elevated",
    }


def test_get_pool_stats_falls_back_when_pool_has_no_standard_counters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(db_base, "get_engine", lambda: SimpleNamespace(pool=object()))

    result = db_base.get_pool_stats()

    assert result == {
        "checked_out": 0,
        "pool_size": 0,
        "overflow": 0,
        "checked_in": 0,
        "pool_pressure": "ok",
    }


@pytest.mark.asyncio
async def test_check_database_readiness_executes_probe_and_disposes_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed: list[str] = []
    disposed: list[str] = []

    class FakeConnection:
        async def execute(self, statement: object) -> None:
            executed.append(str(statement))

    class FakeConnectContext:
        async def __aenter__(self) -> FakeConnection:
            return FakeConnection()

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

    class FakeEngine:
        def connect(self) -> FakeConnectContext:
            return FakeConnectContext()

        async def dispose(self) -> None:
            disposed.append("dispose")

    monkeypatch.setattr(db_base, "get_engine", lambda: FakeEngine())

    await db_base.check_database_readiness()

    assert executed == ["SELECT 1"]
    assert disposed == ["dispose"]


@pytest.mark.asyncio
async def test_session_context_yields_session_from_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_session = object()

    class FakeSessionContext:
        async def __aenter__(self) -> object:
            return fake_session

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

    monkeypatch.setattr(db_session, "get_async_session_factory", lambda bind=None: FakeSessionContext)

    async with db_session.session_context() as session:
        assert session is fake_session


@pytest.mark.asyncio
async def test_assessment_session_context_applies_repeatable_read_and_wraps_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_session = SimpleNamespace(begin=lambda: FakeAsyncContextManager("transaction"))
    captured: dict[str, object] = {}

    class FakeConnection:
        async def execution_options(self, *, isolation_level: str) -> "FakeConnection":
            captured["isolation_level"] = isolation_level
            return self

    fake_connection = FakeConnection()

    class FakeEngineConnectContext:
        async def __aenter__(self) -> FakeConnection:
            return fake_connection

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

    class FakeEngine:
        def connect(self) -> FakeEngineConnectContext:
            return FakeEngineConnectContext()

    def fake_factory(*, bind: object | None = None):
        captured["bind"] = bind
        return lambda: FakeAsyncContextManager(fake_session)

    monkeypatch.setattr(db_session, "get_engine", lambda: FakeEngine())
    monkeypatch.setattr(db_session, "get_async_session_factory", fake_factory)

    async with db_session.assessment_session_context() as yielded_session:
        assert yielded_session is fake_session

    assert captured["isolation_level"] == db_session.ASSESSMENT_ISOLATION_LEVEL
    assert captured["bind"] is fake_connection


@pytest.mark.asyncio
async def test_get_db_commits_when_transaction_is_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SimpleNamespace(
        in_transaction=lambda: True,
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )

    @asynccontextmanager
    async def fake_session_context():
        yield session

    monkeypatch.setattr(db_session, "session_context", fake_session_context)

    generator = db_session.get_db()
    yielded_session = await anext(generator)
    assert yielded_session is session

    with pytest.raises(StopAsyncIteration):
        await generator.asend(None)

    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_db_rolls_back_when_downstream_code_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SimpleNamespace(
        in_transaction=lambda: True,
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )

    @asynccontextmanager
    async def fake_session_context():
        yield session

    monkeypatch.setattr(db_session, "session_context", fake_session_context)

    generator = db_session.get_db()
    yielded_session = await anext(generator)
    assert yielded_session is session

    with pytest.raises(RuntimeError, match="boom"):
        await generator.athrow(RuntimeError("boom"))

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_assessment_db_yields_assessment_scoped_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_session = object()

    @asynccontextmanager
    async def fake_assessment_context():
        yield fake_session

    monkeypatch.setattr(db_session, "assessment_session_context", fake_assessment_context)

    generator = db_session.get_assessment_db()
    yielded_session = await anext(generator)
    assert yielded_session is fake_session

    with pytest.raises(StopAsyncIteration):
        await generator.asend(None)


def test_health_pool_stats_schema_accepts_expected_payload() -> None:
    stats = PoolStats(
        checked_out=3,
        pool_size=4,
        overflow=0,
        checked_in=1,
        pool_pressure="elevated",
    )

    assert stats.pool_pressure == "elevated"


class FakeAsyncContextManager:
    def __init__(self, value: object) -> None:
        self._value = value

    async def __aenter__(self) -> object:
        return self._value

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

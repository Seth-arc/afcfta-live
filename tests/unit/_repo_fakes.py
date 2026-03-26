"""Reusable async-session fakes for repository unit tests."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class FakeMappings:
    def __init__(
        self,
        *,
        one_value: Any = None,
        first_value: Any = None,
        all_values: Iterable[Any] = (),
    ) -> None:
        self._one_value = one_value
        self._first_value = first_value
        self._all_values = list(all_values)

    def one(self) -> Any:
        return self._one_value

    def first(self) -> Any:
        return self._first_value

    def all(self) -> list[Any]:
        return list(self._all_values)


class FakeScalars:
    def __init__(self, *, one_value: Any = None, all_values: Iterable[Any] = ()) -> None:
        self._one_value = one_value
        self._all_values = list(all_values)

    def one(self) -> Any:
        return self._one_value

    def all(self) -> list[Any]:
        return list(self._all_values)


class FakeResult:
    def __init__(
        self,
        *,
        one_mapping: Any = None,
        first_mapping: Any = None,
        all_mappings: Iterable[Any] = (),
        scalar_one_value: Any = None,
        scalar_all_values: Iterable[Any] = (),
    ) -> None:
        self._mappings = FakeMappings(
            one_value=one_mapping,
            first_value=first_mapping,
            all_values=all_mappings,
        )
        self._scalars = FakeScalars(
            one_value=scalar_one_value,
            all_values=scalar_all_values,
        )

    def mappings(self) -> FakeMappings:
        return self._mappings

    def scalars(self) -> FakeScalars:
        return self._scalars

    def scalar_one(self) -> Any:
        return self._scalars.one()


class FakeAsyncContextManager:
    def __init__(self, events: list[str], label: str) -> None:
        self.events = events
        self.label = label

    async def __aenter__(self) -> None:
        self.events.append(f"enter:{self.label}")
        return None

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self.events.append(f"exit:{self.label}")
        return False


class RecordingSession:
    def __init__(
        self,
        results: Iterable[FakeResult],
        *,
        in_transaction: bool = False,
    ) -> None:
        self.calls: list[tuple[Any, Any]] = []
        self._results = list(results)
        self._in_transaction = in_transaction
        self.events: list[str] = []

    async def execute(self, statement, params=None):
        self.calls.append((statement, params))
        if not self._results:
            raise AssertionError("No fake result configured for execute()")
        return self._results.pop(0)

    def in_transaction(self) -> bool:
        return self._in_transaction

    def begin(self) -> FakeAsyncContextManager:
        return FakeAsyncContextManager(self.events, "begin")

    def begin_nested(self) -> FakeAsyncContextManager:
        return FakeAsyncContextManager(self.events, "begin_nested")

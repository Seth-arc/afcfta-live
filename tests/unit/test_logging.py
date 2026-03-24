"""Focused unit tests for request-scoped structured logging."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_sources_repository
from app.core.enums import AuthorityTierEnum, SourceStatusEnum, SourceTypeEnum
from app.core.logging import (
    JsonLogFormatter,
    bind_request_log_context,
    reset_request_log_context,
    update_request_log_context,
)


def test_json_log_formatter_merges_request_context_and_structured_fields() -> None:
    """Structured JSON logs should include request correlation fields and event payload data."""

    formatter = JsonLogFormatter()
    context_tokens = bind_request_log_context(request_id="req-logging-1")
    update_request_log_context(
        authenticated_principal="pytest-suite",
        auth_scheme="api_key",
    )

    try:
        record = logging.LogRecord(
            name="app.request",
            level=logging.INFO,
            pathname=__file__,
            lineno=20,
            msg="Request completed",
            args=(),
            exc_info=None,
        )
        record.structured_data = {
            "event": "http_request",
            "method": "GET",
            "status_code": 200,
            "latency_ms": 12,
        }
        payload = json.loads(formatter.format(record))
    finally:
        reset_request_log_context(context_tokens)

    assert payload["event"] == "http_request"
    assert payload["request_id"] == "req-logging-1"
    assert payload["authenticated_principal"] == "pytest-suite"
    assert payload["auth_scheme"] == "api_key"
    assert payload["method"] == "GET"
    assert payload["status_code"] == 200
    assert payload["latency_ms"] == 12
    assert payload["message"] == "Request completed"


@pytest.mark.asyncio
async def test_request_logging_emits_authenticated_principal_for_protected_routes(
    app: FastAPI,
    async_client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Protected route request logs should include the authenticated principal and request id."""

    class FakeSourcesRepository:
        async def list_sources(
            self,
            *,
            source_type: str | None,
            authority_tier: str | None,
            status: str | None,
            limit: int,
            offset: int,
        ) -> list[dict[str, object]]:
            del source_type, authority_tier, status, limit, offset
            return [
                {
                    "source_id": uuid4(),
                    "title": "Test Source",
                    "short_title": "Test Source",
                    "source_group": "agreement",
                    "source_type": SourceTypeEnum.AGREEMENT,
                    "authority_tier": AuthorityTierEnum.BINDING,
                    "issuing_body": "AfCFTA Secretariat",
                    "jurisdiction_scope": "afcfta",
                    "status": SourceStatusEnum.CURRENT,
                    "language": "en",
                    "file_path": "data/test-source.pdf",
                    "mime_type": "application/pdf",
                    "checksum_sha256": "a" * 64,
                    "publication_date": date(2024, 1, 1),
                    "effective_date": date(2024, 1, 1),
                    "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
                    "updated_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
                }
            ]

    async def override_sources_repository() -> FakeSourcesRepository:
        return FakeSourcesRepository()

    app.dependency_overrides[get_sources_repository] = override_sources_repository

    try:
        with caplog.at_level(logging.INFO, logger="app.request"):
            response = await async_client.get(
                "/api/v1/sources",
                params={"limit": 1},
                headers={"X-Request-ID": "req-http-1"},
            )
    finally:
        app.dependency_overrides.pop(get_sources_repository, None)

    assert response.status_code == 200, response.text
    records = [record for record in caplog.records if record.name == "app.request"]
    assert len(records) == 1
    payload = records[0].structured_data
    assert payload["event"] == "http_request"
    assert payload["request_id"] == "req-http-1"
    assert payload["authenticated_principal"] == "pytest-suite"
    assert payload["auth_scheme"] == "api_key"
    assert payload["method"] == "GET"
    assert payload["path"] == "/api/v1/sources"
    assert payload["route"] in {"/api/v1/sources", "/sources"}
    assert payload["status_code"] == 200
    assert isinstance(payload["latency_ms"], int)
    assert payload["latency_ms"] >= 0
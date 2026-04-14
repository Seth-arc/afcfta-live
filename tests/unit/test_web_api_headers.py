"""Unit tests for browser-route response header hygiene."""

from __future__ import annotations

from starlette.responses import Response

from app.api.deps import scrub_browser_response_auth_headers


def test_scrub_browser_response_auth_headers_removes_internal_auth_headers(
    test_settings,
) -> None:
    """Browser-facing responses must never expose reusable internal credentials."""

    response = Response()
    response.headers["X-API-Key"] = "should-not-leak"
    response.headers["X-Metrics-Key"] = "should-not-leak"
    response.headers["Authorization"] = "Bearer should-not-leak"
    response.headers["Proxy-Authorization"] = "Basic should-not-leak"
    response.headers["X-AIS-Evaluation-Id"] = "eval-123"

    scrub_browser_response_auth_headers(response, settings=test_settings)

    assert "X-API-Key" not in response.headers
    assert "X-Metrics-Key" not in response.headers
    assert "Authorization" not in response.headers
    assert "Proxy-Authorization" not in response.headers
    assert response.headers["X-AIS-Evaluation-Id"] == "eval-123"

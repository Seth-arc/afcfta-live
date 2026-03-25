"""Unit tests for NimClient: request format, retry behaviour, and failure surfaces."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.nim.client import NimClient, NimClientError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SUCCESS_BODY = {"choices": [{"message": {"content": '{"result": "ok"}'}}]}
_VALID_JSON_STRING = '{"result": "ok"}'


def _make_response(status_code: int, body: dict | None = None) -> MagicMock:
    """Build a minimal mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json.return_value = body if body is not None else _SUCCESS_BODY
    return resp


def _patch_client(response: MagicMock | list[MagicMock]):
    """Patch httpx.AsyncClient so post() returns the given response(s).

    If a list is supplied, successive post() calls return successive items.
    """
    if isinstance(response, list):
        post_mock = AsyncMock(side_effect=response)
    else:
        post_mock = AsyncMock(return_value=response)

    mock_http = AsyncMock()
    mock_http.post = post_mock

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_http)
    mock_context.__aexit__ = AsyncMock(return_value=False)

    return patch("app.services.nim.client.httpx.AsyncClient", return_value=mock_context)


def _client(**kwargs) -> NimClient:
    defaults = dict(
        base_url="https://nim.example.com/v1",
        api_key="test-key",
        model="meta/llama-3.1-8b-instruct",
        enabled=True,
        timeout_seconds=5.0,
        max_retries=2,
    )
    defaults.update(kwargs)
    return NimClient(**defaults)


# ---------------------------------------------------------------------------
# Disabled client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_json_returns_none_when_disabled() -> None:
    """NimClient returns None immediately when enabled=False, no HTTP call made."""

    client = _client(enabled=False)
    with patch("app.services.nim.client.httpx.AsyncClient") as mock_cls:
        result = await client.generate_json("system", "user input")

    assert result is None
    mock_cls.assert_not_called()


# ---------------------------------------------------------------------------
# Request format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_json_posts_to_chat_completions_path() -> None:
    """The URL must be base_url + /chat/completions."""

    client = _client(base_url="https://nim.example.com/v1")

    with _patch_client(_make_response(200)) as mock_cls:
        await client.generate_json("sys", "user")

    instance = mock_cls.return_value.__aenter__.return_value
    call_args = instance.post.call_args
    assert call_args[0][0] == "https://nim.example.com/v1/chat/completions"


@pytest.mark.asyncio
async def test_generate_json_strips_trailing_slash_from_base_url() -> None:
    """Trailing slashes on base_url must not produce double-slash URLs."""

    client = _client(base_url="https://nim.example.com/v1/")

    with _patch_client(_make_response(200)) as mock_cls:
        await client.generate_json("sys", "user")

    instance = mock_cls.return_value.__aenter__.return_value
    url = instance.post.call_args[0][0]
    assert "//" not in url.replace("https://", ""), f"Double slash in URL: {url}"


@pytest.mark.asyncio
async def test_generate_json_request_body_structure() -> None:
    """Request body must use chat completions format with json_object response_format."""

    client = _client(model="meta/llama-3.1-8b-instruct")

    with _patch_client(_make_response(200)) as mock_cls:
        await client.generate_json("be a parser", "export wheat from Ghana")

    instance = mock_cls.return_value.__aenter__.return_value
    body = instance.post.call_args[1]["json"]

    assert body["model"] == "meta/llama-3.1-8b-instruct"
    assert body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}
    messages = body["messages"]
    assert messages[0] == {"role": "system", "content": "be a parser"}
    assert messages[1] == {"role": "user", "content": "export wheat from Ghana"}


@pytest.mark.asyncio
async def test_generate_json_sends_bearer_auth_header() -> None:
    """Authorization header must be 'Bearer <api_key>'."""

    client = _client(api_key="secret-nim-key")

    with _patch_client(_make_response(200)) as mock_cls:
        await client.generate_json("sys", "user")

    instance = mock_cls.return_value.__aenter__.return_value
    headers = instance.post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer secret-nim-key"


@pytest.mark.asyncio
async def test_generate_json_passes_timeout_to_async_client() -> None:
    """The AsyncClient must be constructed with the configured timeout."""

    client = _client(timeout_seconds=42.0)

    with _patch_client(_make_response(200)) as mock_cls:
        await client.generate_json("sys", "user")

    mock_cls.assert_called_once_with(timeout=42.0)


# ---------------------------------------------------------------------------
# Successful response extraction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_json_returns_raw_content_string() -> None:
    """The raw content string from choices[0].message.content is returned unchanged."""

    raw = '{"hs6_code": "110311", "exporter": "GHA"}'
    body = {"choices": [{"message": {"content": raw}}]}

    with _patch_client(_make_response(200, body)):
        result = await _client().generate_json("sys", "user")

    assert result == raw


@pytest.mark.asyncio
async def test_generate_json_does_not_parse_model_output() -> None:
    """Return value must be a string, not a parsed dict, even for valid JSON."""

    with _patch_client(_make_response(200)):
        result = await _client().generate_json("sys", "user")

    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Retry behaviour — transient errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_json_retries_on_timeout_and_succeeds() -> None:
    """A single timeout followed by a success must succeed after one retry."""

    client = _client(max_retries=2)
    success_response = _make_response(200)

    with patch("app.services.nim.client.asyncio.sleep", new_callable=AsyncMock):
        with patch("app.services.nim.client.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(
                side_effect=[httpx.TimeoutException("timeout"), success_response]
            )
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(return_value=mock_http)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = ctx

            result = await client.generate_json("sys", "user")

    assert result == _VALID_JSON_STRING
    assert mock_http.post.call_count == 2


@pytest.mark.asyncio
async def test_generate_json_retries_on_connect_error_and_succeeds() -> None:
    """A single connection error followed by a success must succeed after one retry."""

    client = _client(max_retries=2)
    success_response = _make_response(200)

    with patch("app.services.nim.client.asyncio.sleep", new_callable=AsyncMock):
        with patch("app.services.nim.client.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(
                side_effect=[httpx.ConnectError("refused"), success_response]
            )
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(return_value=mock_http)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = ctx

            result = await client.generate_json("sys", "user")

    assert result == _VALID_JSON_STRING


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
async def test_generate_json_retries_on_retryable_status_and_succeeds(
    status_code: int,
) -> None:
    """Retryable HTTP status codes must trigger a retry and ultimately succeed."""

    client = _client(max_retries=2)
    transient = _make_response(status_code)
    success = _make_response(200)

    with patch("app.services.nim.client.asyncio.sleep", new_callable=AsyncMock):
        with patch("app.services.nim.client.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(side_effect=[transient, success])
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(return_value=mock_http)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = ctx

            result = await client.generate_json("sys", "user")

    assert result == _VALID_JSON_STRING


@pytest.mark.asyncio
async def test_generate_json_raises_after_exhausting_retries_on_timeout() -> None:
    """Exhausting all retries on timeouts must raise NimClientError(reason='timeout')."""

    client = _client(max_retries=2)

    with patch("app.services.nim.client.asyncio.sleep", new_callable=AsyncMock):
        with patch("app.services.nim.client.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(return_value=mock_http)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = ctx

            with pytest.raises(NimClientError) as exc_info:
                await client.generate_json("sys", "user")

    assert exc_info.value.reason == "timeout"
    assert exc_info.value.status_code is None
    assert mock_http.post.call_count == 3  # initial + 2 retries


@pytest.mark.asyncio
async def test_generate_json_raises_after_exhausting_retries_on_retryable_status() -> None:
    """Exhausting retries on a retryable status must raise NimClientError."""

    client = _client(max_retries=1)

    with patch("app.services.nim.client.asyncio.sleep", new_callable=AsyncMock):
        with patch("app.services.nim.client.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=_make_response(503))
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(return_value=mock_http)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = ctx

            with pytest.raises(NimClientError) as exc_info:
                await client.generate_json("sys", "user")

    err = exc_info.value
    assert err.status_code == 503
    assert err.reason == "max_retries_exceeded"
    assert mock_http.post.call_count == 2  # initial + 1 retry


@pytest.mark.asyncio
async def test_generate_json_uses_exponential_backoff() -> None:
    """Sleep durations between retries must follow exponential backoff (0.5 * 2^attempt)."""

    client = _client(max_retries=2)

    with patch("app.services.nim.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with patch("app.services.nim.client.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(return_value=mock_http)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = ctx

            with pytest.raises(NimClientError):
                await client.generate_json("sys", "user")

    # attempt 0: no sleep; attempt 1: sleep(0.5); attempt 2: sleep(1.0)
    assert mock_sleep.call_count == 2
    assert mock_sleep.call_args_list[0][0][0] == pytest.approx(0.5)
    assert mock_sleep.call_args_list[1][0][0] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Permanent failures — no retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
async def test_generate_json_raises_immediately_on_permanent_http_error(
    status_code: int,
) -> None:
    """Non-retryable 4xx errors must raise NimClientError on the first attempt."""

    client = _client(max_retries=2)

    with patch("app.services.nim.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with _patch_client(_make_response(status_code)):
            with pytest.raises(NimClientError) as exc_info:
                await client.generate_json("sys", "user")

    assert exc_info.value.status_code == status_code
    assert exc_info.value.reason == "http_error"
    mock_sleep.assert_not_called()  # no retry for permanent errors


@pytest.mark.asyncio
async def test_generate_json_raises_on_unexpected_response_shape() -> None:
    """A 200 with missing choices structure must raise NimClientError immediately."""

    bad_body = {"not_choices": []}

    with _patch_client(_make_response(200, bad_body)):
        with pytest.raises(NimClientError) as exc_info:
            await _client().generate_json("sys", "user")

    assert exc_info.value.reason == "unexpected_response_shape"
    assert exc_info.value.status_code == 200


# ---------------------------------------------------------------------------
# NimClientError attributes
# ---------------------------------------------------------------------------


def test_nim_client_error_carries_structured_fields() -> None:
    """NimClientError must expose status_code, reason, and attempt as attributes."""

    err = NimClientError("failed", status_code=503, reason="max_retries_exceeded", attempt=2)

    assert str(err) == "failed"
    assert err.status_code == 503
    assert err.reason == "max_retries_exceeded"
    assert err.attempt == 2


def test_nim_client_error_defaults() -> None:
    """NimClientError defaults must be safe for callers that only supply a message."""

    err = NimClientError("oops")

    assert err.status_code is None
    assert err.reason == "unknown"
    assert err.attempt == 0

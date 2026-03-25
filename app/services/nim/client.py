"""NIM model API client.

Wraps a single async HTTP call to the NIM inference endpoint. This layer:
- Accepts a system prompt and user input.
- Returns the raw JSON string from the model response.
- Does NOT parse or validate the model output — that is the caller's responsibility.
- Surfaces all failures as NimClientError so the orchestration layer can handle
  them deterministically without crashing the assistant path.

Request format: OpenAI-compatible chat completions (POST /chat/completions).
The model is instructed to return JSON via response_format={"type": "json_object"}.

Retry behaviour: transient failures (timeout, connection error, HTTP 429/5xx) are
retried up to NIM_MAX_RETRIES times with exponential backoff (0.5 * 2^attempt s).
Permanent failures (HTTP 4xx except 429) raise NimClientError immediately.

Environment variables consumed (set via app/config.py and .env.example):
- NIM_ENABLED          Set to false to disable model calls (generate_json returns None)
- NIM_BASE_URL         Base URL for the NIM inference endpoint
- NIM_API_KEY          Bearer token for authenticating to NIM
- NIM_MODEL            Model name / identifier passed in each request
- NIM_TIMEOUT_SECONDS  Per-attempt HTTP timeout (default 30)
- NIM_MAX_RETRIES      Additional attempts on transient errors (default 2)
"""

from __future__ import annotations

import asyncio

import httpx

_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


class NimClientError(Exception):
    """Raised when the NIM model API call fails after all retry attempts.

    Callers must catch this and fall back to deterministic behaviour.
    Structured fields allow the orchestration layer to log context without
    re-parsing the exception message.

    Attributes:
        status_code: HTTP status code from the last attempt, or None for
                     network-level failures (timeout, connection error).
        reason:      Short machine-readable failure category:
                     "timeout", "connect_error", "http_error",
                     "unexpected_response_shape", "max_retries_exceeded".
        attempt:     Zero-based index of the attempt that produced this error.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        reason: str = "unknown",
        attempt: int = 0,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason
        self.attempt = attempt


class NimClient:
    """Async HTTP client for the NIM inference API.

    Dependency-injected into intake_service, clarification_service, and
    explanation_service. Constructed once per request via a factory in
    app/api/deps.py (wired in Prompt 9).

    All services that use this client must catch NimClientError and fall
    back to deterministic behaviour rather than surfacing failures to the
    caller as 500 responses.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        enabled: bool = True,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    async def generate_json(self, prompt: str, input_text: str) -> str | None:
        """Send a generation request and return the raw JSON string from the model.

        Constructs an OpenAI-compatible chat completions request with the
        supplied system prompt and user input. Extracts the content string
        from `choices[0].message.content` and returns it unchanged. The
        caller is responsible for all further parsing and validation.

        Args:
            prompt:     System prompt instructing the model on output format.
            input_text: User-provided text to be processed by the model.

        Returns:
            Raw JSON string from the model response, or None when
            NIM_ENABLED is False.

        Raises:
            NimClientError: On timeout, connection failure, non-2xx response
                            after all retry attempts, or unexpected response shape.
        """
        if not self.enabled:
            return None

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": input_text},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }

        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as http:
                    response = await http.post(url, json=body, headers=headers)
            except httpx.TimeoutException as exc:
                if attempt < self.max_retries:
                    continue
                raise NimClientError(
                    f"NIM request timed out after {self.timeout_seconds}s "
                    f"(attempt {attempt + 1}/{self.max_retries + 1})",
                    status_code=None,
                    reason="timeout",
                    attempt=attempt,
                ) from exc
            except httpx.ConnectError as exc:
                if attempt < self.max_retries:
                    continue
                raise NimClientError(
                    f"NIM connection failed "
                    f"(attempt {attempt + 1}/{self.max_retries + 1})",
                    status_code=None,
                    reason="connect_error",
                    attempt=attempt,
                ) from exc

            if response.status_code in _RETRYABLE_STATUS_CODES:
                if attempt < self.max_retries:
                    continue
                raise NimClientError(
                    f"NIM returned HTTP {response.status_code} "
                    f"(attempt {attempt + 1}/{self.max_retries + 1})",
                    status_code=response.status_code,
                    reason="max_retries_exceeded",
                    attempt=attempt,
                )

            if not response.is_success:
                raise NimClientError(
                    f"NIM returned HTTP {response.status_code}",
                    status_code=response.status_code,
                    reason="http_error",
                    attempt=attempt,
                )

            try:
                data = response.json()
                return str(data["choices"][0]["message"]["content"])
            except (KeyError, IndexError) as exc:
                raise NimClientError(
                    "NIM response missing choices[0].message.content",
                    status_code=response.status_code,
                    reason="unexpected_response_shape",
                    attempt=attempt,
                ) from exc

        # Unreachable: every loop iteration either returns, continues, or raises.
        raise NimClientError(  # pragma: no cover
            f"NIM failed after {self.max_retries + 1} attempt(s)",
            status_code=None,
            reason="max_retries_exceeded",
            attempt=self.max_retries,
        )

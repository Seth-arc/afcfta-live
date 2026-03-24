"""Shared structured logging helpers for the AfCFTA Intelligence API."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from decimal import Decimal
from typing import Any, Mapping


_AIS_HANDLER_MARKER = "_ais_structured_handler"
_request_id_context: ContextVar[str | None] = ContextVar("ais_request_id", default=None)
_principal_context: ContextVar[str | None] = ContextVar("ais_authenticated_principal", default=None)
_auth_scheme_context: ContextVar[str | None] = ContextVar("ais_auth_scheme", default=None)


@dataclass(frozen=True)
class RequestLogContextTokens:
    """Tokens used to restore per-request log context after response completion."""

    request_id: Token[str | None]
    authenticated_principal: Token[str | None]
    auth_scheme: Token[str | None]


def bind_request_log_context(
    *,
    request_id: str,
    authenticated_principal: str | None = None,
    auth_scheme: str | None = None,
) -> RequestLogContextTokens:
    """Bind request-scoped correlation fields into context-local storage."""

    return RequestLogContextTokens(
        request_id=_request_id_context.set(request_id),
        authenticated_principal=_principal_context.set(authenticated_principal),
        auth_scheme=_auth_scheme_context.set(auth_scheme),
    )


def update_request_log_context(
    *,
    authenticated_principal: str | None = None,
    auth_scheme: str | None = None,
) -> None:
    """Update request-scoped authentication metadata after a caller is authenticated."""

    _principal_context.set(authenticated_principal)
    _auth_scheme_context.set(auth_scheme)


def reset_request_log_context(tokens: RequestLogContextTokens) -> None:
    """Restore log context variables to their prior state."""

    _request_id_context.reset(tokens.request_id)
    _principal_context.reset(tokens.authenticated_principal)
    _auth_scheme_context.reset(tokens.auth_scheme)


def get_request_log_context() -> dict[str, Any]:
    """Return the current request-scoped logging correlation fields."""

    context = {
        "request_id": _request_id_context.get(),
        "authenticated_principal": _principal_context.get(),
        "auth_scheme": _auth_scheme_context.get(),
    }
    return {key: value for key, value in context.items() if value is not None}


def _serialize_log_value(value: Any) -> Any:
    """Convert log field values into JSON-safe primitives."""

    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _serialize_log_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_serialize_log_value(item) for item in value]
    return str(value)


class JsonLogFormatter(logging.Formatter):
    """Render application logs as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            **get_request_log_context(),
        }

        structured_data = getattr(record, "structured_data", None)
        if isinstance(structured_data, Mapping):
            payload.update(
                {
                    str(key): _serialize_log_value(value)
                    for key, value in structured_data.items()
                    if value is not None
                }
            )

        message = record.getMessage()
        if message and payload.get("message") is None:
            payload["message"] = message

        if record.exc_info is not None:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, sort_keys=True)


def log_event(
    logger: logging.Logger,
    level: int,
    *,
    event: str,
    message: str,
    **fields: Any,
) -> None:
    """Emit one structured log event with stable correlation fields."""

    payload = {
        **get_request_log_context(),
        "event": event,
        **fields,
    }
    logger.log(level, message, extra={"structured_data": payload})


def configure_logging(settings: Any) -> None:
    """Configure root logging once using environment-driven application settings."""

    level_name = str(getattr(settings, "LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    log_format = str(getattr(settings, "LOG_FORMAT", "json")).lower()

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    handler = next(
        (existing for existing in root_logger.handlers if getattr(existing, _AIS_HANDLER_MARKER, False)),
        None,
    )
    if handler is None:
        handler = logging.StreamHandler()
        setattr(handler, _AIS_HANDLER_MARKER, True)
        root_logger.addHandler(handler)

    handler.setLevel(level)
    if log_format == "json":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    disable_uvicorn_access_log = bool(
        getattr(settings, "LOG_DISABLE_UVICORN_ACCESS_LOG", True)
    )
    uvicorn_access_logger.disabled = disable_uvicorn_access_log
    if disable_uvicorn_access_log:
        uvicorn_access_logger.propagate = False

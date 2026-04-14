"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.local_db import (
    DEFAULT_LOCAL_DB_HOST,
    DEFAULT_LOCAL_DB_NAME,
    DEFAULT_LOCAL_DB_PASSWORD,
    DEFAULT_LOCAL_DB_PORT,
    DEFAULT_LOCAL_DB_USER,
    build_local_database_urls,
)


class Settings(BaseSettings):
    """Runtime settings for the AfCFTA Intelligence API.

    Production-critical settings must be supplied through the process
    environment or a local `.env` / `.env.prod` file. Local development and
    test environments may derive DATABASE_URL and DATABASE_URL_SYNC from the
    shared LOCAL_DB_* contract below.
    """

    # Database
    DATABASE_URL: str = ""
    DATABASE_URL_SYNC: str | None = None
    LOCAL_DB_HOST: str = DEFAULT_LOCAL_DB_HOST
    LOCAL_DB_PORT: int = DEFAULT_LOCAL_DB_PORT
    LOCAL_DB_NAME: str = DEFAULT_LOCAL_DB_NAME
    LOCAL_DB_USER: str = DEFAULT_LOCAL_DB_USER
    LOCAL_DB_PASSWORD: str = DEFAULT_LOCAL_DB_PASSWORD
    DB_CONNECT_TIMEOUT_SECONDS: float = 10.0
    DB_COMMAND_TIMEOUT_SECONDS: float = 15.0
    DB_POOL_TIMEOUT_SECONDS: float = 30.0
    DB_STATEMENT_TIMEOUT_MS: int = 15000
    DB_LOCK_TIMEOUT_MS: int = 5000
    DB_POOL_SIZE: int = 5
    DB_POOL_MAX_OVERFLOW: int = 10

    # In-process cache for static reference lookups
    CACHE_STATIC_LOOKUPS: bool = True
    CACHE_STATUS_LOOKUPS: bool = False
    CACHE_TTL_SECONDS: int = 300

    # API authentication
    API_AUTH_KEY: str
    API_AUTH_PRINCIPAL: str = "configured-api-client"
    API_AUTH_HEADER_NAME: str = "X-API-Key"

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_DEFAULT_MAX_REQUESTS: int = 120
    RATE_LIMIT_ASSESSMENTS_MAX_REQUESTS: int = 10

    # Redis (optional — enables multi-worker rate limiting when set)
    # When empty the API falls back to InMemoryRateLimiter (UVICORN_WORKERS=1 only).
    REDIS_URL: str = ""

    # Deployment/runtime mode
    ENV: str = "development"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_REQUESTS_ENABLED: bool = True
    LOG_DISABLE_UVICORN_ACCESS_LOG: bool = True

    # Prometheus metrics scraping
    # When True, expose Prometheus-compatible metrics at /metrics for scrapers.
    # Outside development/test/ci, metrics must remain authenticated.
    METRICS_ENABLED: bool = False
    METRICS_AUTH_REQUIRED: bool = True
    METRICS_AUTH_HEADER_NAME: str = "X-Metrics-Key"
    METRICS_AUTH_KEY: str = ""

    # Optional external error tracking
    ERROR_TRACKING_BACKEND: str = "none"
    SENTRY_DSN: str | None = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0

    # NIM assistant integration
    # Set NIM_ENABLED=false to disable model calls and return None from NimClient.
    # NIM_BASE_URL, NIM_API_KEY, and NIM_MODEL must be non-empty when NIM_ENABLED=true.
    # The deps factory validates this at startup.
    NIM_ENABLED: bool = False
    NIM_BASE_URL: str = ""
    NIM_API_KEY: str = ""
    NIM_MODEL: str = ""
    NIM_TIMEOUT_SECONDS: float = 30.0
    NIM_MAX_RETRIES: int = 2
    # When True, logs user_input_char_count (integer only — never the raw text).
    # Leave False in production unless a redaction-safe logging pipeline is in place.
    NIM_LOG_IO: bool = False

    # Uvicorn worker count — read by the app at startup to validate Redis requirement.
    # When UVICORN_WORKERS > 1 and REDIS_URL is empty the startup guard in _lifespan
    # raises RuntimeError because InMemoryRateLimiter is per-process only.
    UVICORN_WORKERS: int = 1

    # CORS — set CORS_ALLOW_ORIGINS to a comma-separated list of allowed origins.
    # Leave empty to disable CORS headers (suitable for pure API / non-browser clients).
    # Example: CORS_ALLOW_ORIGINS=https://trader.afcfta.example,https://staging.afcfta.example
    CORS_ALLOW_ORIGINS: str = ""
    ALLOWED_HOSTS: str = ""

    # Application metadata
    APP_TITLE: str = "AfCFTA Intelligence API"
    APP_VERSION: str = "0.1.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @model_validator(mode="before")
    @classmethod
    def _derive_local_database_urls(cls, data: object) -> object:
        """Allow local development/test environments to derive URLs from one contract."""

        if not isinstance(data, dict):
            return data

        values = dict(data)
        environment = str(values.get("ENV") or "development")
        if values.get("DATABASE_URL") or environment not in {"development", "test", "ci"}:
            return values

        async_url, sync_url = build_local_database_urls(values)
        values["DATABASE_URL"] = async_url
        if not values.get("DATABASE_URL_SYNC"):
            values["DATABASE_URL_SYNC"] = sync_url
        return values

    @model_validator(mode="after")
    def _nim_enabled_requires_companions(self) -> "Settings":
        """When NIM_ENABLED=true, NIM_BASE_URL, NIM_API_KEY, and NIM_MODEL must be non-empty."""
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL must be set.")

        if not self.NIM_ENABLED:
            pass
        else:
            missing: list[str] = []
            if not self.NIM_BASE_URL:
                missing.append("NIM_BASE_URL")
            if not self.NIM_API_KEY:
                missing.append("NIM_API_KEY")
            if not self.NIM_MODEL:
                missing.append("NIM_MODEL")
            if missing:
                raise ValueError(
                    f"NIM_ENABLED=true but the following required fields are empty: "
                    f"{', '.join(missing)}"
                )

        if self.METRICS_ENABLED and not self.METRICS_AUTH_REQUIRED and self.ENV not in {
            "development",
            "test",
            "ci",
        }:
            raise ValueError(
                "METRICS_AUTH_REQUIRED must remain true when METRICS_ENABLED=true "
                "outside development/test/ci."
            )
        if self.ENV not in {"development", "test", "ci"} and not self.ALLOWED_HOSTS.strip():
            raise ValueError(
                "ALLOWED_HOSTS must be set outside development/test/ci."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()

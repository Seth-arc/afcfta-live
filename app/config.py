"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the AfCFTA Intelligence API.

    Required settings have no default and must be supplied through the process
    environment or a local `.env` file. All other settings default to
    development-safe values and can be overridden per environment.
    """

    # Database
    DATABASE_URL: str
    DATABASE_URL_SYNC: str | None = None
    DB_CONNECT_TIMEOUT_SECONDS: float = 10.0
    DB_COMMAND_TIMEOUT_SECONDS: float = 15.0
    DB_POOL_TIMEOUT_SECONDS: float = 30.0
    DB_STATEMENT_TIMEOUT_MS: int = 15000
    DB_LOCK_TIMEOUT_MS: int = 5000
    DB_POOL_SIZE: int = 5
    DB_POOL_MAX_OVERFLOW: int = 10

    # In-process cache for static reference lookups
    CACHE_STATIC_LOOKUPS: bool = True
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
    # Leave False unless a Prometheus-compatible collector is configured.
    METRICS_ENABLED: bool = False

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

    # Application metadata
    APP_TITLE: str = "AfCFTA Intelligence API"
    APP_VERSION: str = "0.1.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def _nim_enabled_requires_companions(self) -> "Settings":
        """When NIM_ENABLED=true, NIM_BASE_URL, NIM_API_KEY, and NIM_MODEL must be non-empty."""
        if not self.NIM_ENABLED:
            return self
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
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()

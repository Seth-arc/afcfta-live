"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

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
    CACHE_STATIC_LOOKUPS: bool = False
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

    # Deployment/runtime mode
    ENV: str = "development"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_REQUESTS_ENABLED: bool = True
    LOG_DISABLE_UVICORN_ACCESS_LOG: bool = True

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

    # Application metadata
    APP_TITLE: str = "AfCFTA Intelligence API"
    APP_VERSION: str = "0.1.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()

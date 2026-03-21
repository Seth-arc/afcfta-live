"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the AfCFTA Intelligence API."""

    DATABASE_URL: str
    DATABASE_URL_SYNC: str | None = None
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"
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

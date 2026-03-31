"""Unit tests for NIM-related configuration validation in Settings."""

import pytest
from pydantic import ValidationError

from app.config import Settings

# Shared kwargs that satisfy the non-NIM required fields so tests
# never depend on real environment variables.
_BASE_KWARGS = {
    "DATABASE_URL": "postgresql+asyncpg://u:p@localhost/db",
    "API_AUTH_KEY": "test-key",
    "ENV": "test",
}


class TestNimConfigValidation:
    """Verify the model_validator that guards NIM companion fields."""

    def test_nim_disabled_requires_no_companions(self) -> None:
        """NIM_ENABLED=false must not raise even when companion fields are empty."""
        settings = Settings(
            **_BASE_KWARGS,
            NIM_ENABLED=False,
            NIM_BASE_URL="",
            NIM_API_KEY="",
            NIM_MODEL="",
        )
        assert settings.NIM_ENABLED is False

    def test_nim_enabled_with_all_fields_valid(self) -> None:
        """NIM_ENABLED=true with all companions set must succeed."""
        settings = Settings(
            **_BASE_KWARGS,
            NIM_ENABLED=True,
            NIM_BASE_URL="https://nim.example.com",
            NIM_API_KEY="secret",
            NIM_MODEL="meta/llama-3.1-70b-instruct",
        )
        assert settings.NIM_ENABLED is True
        assert settings.NIM_BASE_URL == "https://nim.example.com"

    def test_nim_enabled_without_base_url_raises(self) -> None:
        """NIM_ENABLED=true with empty NIM_BASE_URL must raise naming the field."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                **_BASE_KWARGS,
                NIM_ENABLED=True,
                NIM_BASE_URL="",
                NIM_API_KEY="key",
                NIM_MODEL="test",
            )
        assert "NIM_BASE_URL" in str(exc_info.value)

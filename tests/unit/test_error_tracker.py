"""Tests for the optional external error-tracking seam."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.main import ErrorTracker, _configure_error_tracker


# ---------------------------------------------------------------------------
# ErrorTracker behaviour
# ---------------------------------------------------------------------------


def test_error_tracker_noop_when_backend_is_none() -> None:
    """A tracker with no capture function silently swallows exceptions."""
    tracker = ErrorTracker(capture_exception=None)
    tracker.capture_exception(Exception("test"))  # must not raise


def test_error_tracker_calls_capture_when_wired() -> None:
    """A tracker with a wired capture function delegates to it."""
    mock_capture = MagicMock()
    tracker = ErrorTracker(capture_exception=mock_capture)

    exc = Exception("x")
    tracker.capture_exception(exc)

    mock_capture.assert_called_once_with(exc)


# ---------------------------------------------------------------------------
# _configure_error_tracker factory
# ---------------------------------------------------------------------------


def test_configure_error_tracker_returns_noop_for_unsupported_backend() -> None:
    """An unsupported backend name produces a tracker with no capture wired."""
    settings = MagicMock()
    settings.ERROR_TRACKING_BACKEND = "datadog"

    tracker = _configure_error_tracker(settings)

    assert tracker._capture_exception is None

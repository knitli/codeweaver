# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Tests for telemetry integration in server initialization.

Validates:
- Telemetry client is properly initialized from settings
- Telemetry client is properly shutdown on server exit
- Graceful fallback when posthog is not installed
- Telemetry respects disable_telemetry setting
"""

from __future__ import annotations

import sys

from unittest.mock import MagicMock, patch

import pytest

from codeweaver.common.telemetry.client import PostHogClient
from codeweaver.config.settings import CodeWeaverSettings
from codeweaver.config.telemetry import TelemetrySettings


pytestmark = [pytest.mark.unit, pytest.mark.server]


class TestTelemetryIntegration:
    """Test telemetry integration in server initialization."""

    def test_posthog_client_handles_import_error(self) -> None:
        """Test that PostHogClient gracefully handles missing posthog package."""
        # Temporarily hide posthog module
        with patch.dict(sys.modules, {"posthog": None}):
            client = PostHogClient(enabled=True)

            # Client should be disabled and not raise an error
            assert client.enabled is False
            assert client._client is None

            # Capture should not fail
            client.capture("test_event", {"key": "value"})

    def test_posthog_client_respects_disabled_setting(self) -> None:
        """Test that PostHogClient respects enabled=False setting."""
        client = PostHogClient(enabled=False)

        assert client.enabled is False
        assert client._client is None

        # Capture should be a no-op
        client.capture("test_event", {"key": "value"})

    def test_from_settings_respects_disable_telemetry(self) -> None:
        """Test that from_settings respects disable_telemetry setting."""
        # Create a mock settings object with telemetry disabled
        mock_settings = MagicMock(spec=CodeWeaverSettings)
        mock_telemetry = MagicMock(spec=TelemetrySettings)
        mock_telemetry.enabled = False
        mock_telemetry.disable_telemetry = True
        mock_settings.telemetry = mock_telemetry

        with patch("codeweaver.common.telemetry.client.get_settings", return_value=mock_settings):
            client = PostHogClient.from_settings()

            assert client.enabled is False
            assert client._client is None

    def test_from_settings_with_no_api_key(self) -> None:
        """Test that from_settings handles missing API key."""
        mock_settings = MagicMock(spec=CodeWeaverSettings)
        mock_telemetry = MagicMock(spec=TelemetrySettings)
        mock_telemetry.enabled = True
        mock_telemetry.disable_telemetry = False
        mock_telemetry.posthog_project_key = None
        mock_telemetry.posthog_host = "https://us.i.posthog.com"
        mock_settings.telemetry = mock_telemetry

        with patch("codeweaver.common.telemetry.client.get_settings", return_value=mock_settings):
            client = PostHogClient.from_settings()

            assert client.enabled is False
            assert client._client is None

    def test_shutdown_with_no_client(self) -> None:
        """Test that shutdown handles case when client is None."""
        client = PostHogClient(enabled=False)

        # Should not raise an error
        client.shutdown()

    def test_shutdown_with_client_error(self) -> None:
        """Test that shutdown handles errors from posthog client."""
        client = PostHogClient(enabled=False)
        client._client = MagicMock()
        client._client.flush.side_effect = Exception("Test error")

        # Should not raise an error, just log it
        client.shutdown()

    def test_capture_never_raises(self) -> None:
        """Test that capture method never raises exceptions."""
        client = PostHogClient(enabled=False)
        client._client = MagicMock()
        client._client.capture.side_effect = Exception("Test error")
        client.enabled = True  # Force it to try to capture

        # Should not raise, just log the error
        client.capture("test_event", {"key": "value"})

    def test_capture_with_serialization(self) -> None:
        """Test capture_with_serialization with a serializable object."""
        from codeweaver.core.types.models import BasedModel

        class TestModel(BasedModel):
            field1: str = "value1"

            def _telemetry_keys(self):
                return None

        client = PostHogClient(enabled=False)
        obj = TestModel()

        # Should not raise an error even when disabled
        client.capture_with_serialization("test_event", obj)

    def test_capture_from_event(self) -> None:
        """Test capture_from_event with a telemetry event object."""
        from codeweaver.common.telemetry.events import SessionSummaryEvent

        # Test data: 3000 delivered + 7000 saved = 10000 generated (70% reduction)
        event = SessionSummaryEvent(
            session_duration_minutes=5.0,
            total_searches=10,
            successful_searches=9,
            failed_searches=1,
            success_rate=0.9,
            avg_response_ms=1000.0,
            median_response_ms=900.0,
            p95_response_ms=1500.0,
            total_tokens_generated=10000,
            total_tokens_delivered=3000,
            total_tokens_saved=7000,
            context_reduction_pct=70.0,
            estimated_cost_savings_usd=0.05,
        )

        client = PostHogClient(enabled=False)

        # Should not raise an error even when disabled
        client.capture_from_event(event)

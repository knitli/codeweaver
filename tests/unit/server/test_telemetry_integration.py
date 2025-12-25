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
- New SessionEvent and SearchEvent classes
- PostHog context management (start_session, end_session)
- Privacy controls and serialize_for_telemetry integration
"""

from __future__ import annotations

import sys

from unittest.mock import MagicMock, patch

import pytest

from codeweaver.common.telemetry.client import PostHogClient
from codeweaver.config.settings import CodeWeaverSettings
from codeweaver.config.telemetry import TelemetrySettings


pytestmark = [pytest.mark.unit, pytest.mark.server]


def create_session_statistics():
    """Create a SessionStatistics instance with all required fields."""
    from codeweaver.common.statistics import (
        FailoverStats,
        FileStatistics,
        SessionStatistics,
        TimingStatistics,
        TokenCounter,
    )

    return SessionStatistics(
        index_statistics=FileStatistics(),
        token_statistics=TokenCounter(),
        timing_statistics=TimingStatistics(),
        semantic_statistics=None,  # Optional field
        failover_statistics=FailoverStats(),
        _successful_request_log=[],
        _failed_request_log=[],
        _successful_http_request_log=[],
        _failed_http_request_log=[],
    )


def create_find_code_response(
    *,
    matches=None,
    summary="Test summary",
    total_matches=0,
    total_results=0,
    token_count=0,
    execution_time_ms=100.0,
    status="success",
    indexing_state="complete",
    index_coverage=100.0,
):
    """Create a FindCodeResponseSummary with all required fields."""
    from codeweaver.agent_api.find_code.intent import IntentType
    from codeweaver.core.types.search import SearchStrategy

    return FindCodeResponseSummary(
        matches=matches or [],
        summary=summary,
        query_intent=IntentType.UNDERSTAND,
        total_matches=total_matches,
        total_results=total_results,
        token_count=token_count,
        execution_time_ms=execution_time_ms,
        search_strategy=(SearchStrategy.HYBRID_SEARCH,),
        status=status,
        warnings=[],
        indexing_state=indexing_state,
        index_coverage=index_coverage,
        search_mode="hybrid",
        languages_found=(),
        metadata=None,
    )


@pytest.mark.mock_only
@pytest.mark.telemetry
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

        with patch("codeweaver.config.settings.get_settings", return_value=mock_settings):
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

        with patch("codeweaver.config.settings.get_settings", return_value=mock_settings):
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
        from codeweaver.common.telemetry.events import SessionEvent

        # Create SessionStatistics with all required fields
        stats = create_session_statistics()

        # Create SessionEvent using the new API
        event = SessionEvent.from_statistics(
            stats,
            version="0.5.0",
            setup_success=True,
            setup_attempts=1,
            config_errors=None,
            duration_seconds=300.0,
        )

        client = PostHogClient(enabled=False)

        # Should not raise an error even when disabled
        client.capture_from_event(event)


@pytest.mark.mock_only
@pytest.mark.telemetry
class TestSessionEvent:
    """Test SessionEvent telemetry event."""

    def test_session_event_creation(self) -> None:
        """Test SessionEvent can be created from statistics."""
        from codeweaver.common.telemetry.events import SessionEvent

        stats = create_session_statistics()
        event = SessionEvent.from_statistics(
            stats,
            version="0.5.0",
            setup_success=True,
            setup_attempts=1,
            config_errors=None,
            duration_seconds=300.0,
        )

        assert event._version == "0.5.0"
        assert event._setup_success is True
        assert event._duration_seconds == 300.0

    def test_session_event_to_posthog_event(self) -> None:
        """Test SessionEvent converts to PostHog event format."""
        from codeweaver.common.telemetry.events import SessionEvent

        stats = create_session_statistics()
        event = SessionEvent.from_statistics(
            stats,
            version="0.5.0",
            setup_success=True,
            setup_attempts=2,
            config_errors=["missing_key"],
            duration_seconds=300.0,
        )

        event_name, properties = event.to_posthog_event()

        assert event_name == "codeweaver_session"
        assert "$set_once" in properties
        assert "$set" in properties
        assert properties["$set"]["codeweaver_version"] == "0.5.0"
        assert properties["duration_seconds"] == 300.0
        assert properties["setup"]["success"] is True
        assert properties["setup"]["attempts"] == 2
        assert properties["setup"]["errors"] == ["missing_key"]
        assert "requests" in properties

    def test_session_event_empty_stats(self) -> None:
        """Test SessionEvent handles empty statistics."""
        from codeweaver.common.telemetry.events import SessionEvent

        event = SessionEvent()
        event_name, properties = event.to_posthog_event()

        assert event_name == "codeweaver_session"
        assert properties == {}


@pytest.mark.mock_only
@pytest.mark.telemetry
class TestSearchEvent:
    """Test SearchEvent telemetry event."""

    def test_search_event_creation(self) -> None:
        """Test SearchEvent can be created."""
        from codeweaver.agent_api.find_code.intent import IntentType
        from codeweaver.common.telemetry.events import SearchEvent
        from codeweaver.core.types.search import SearchStrategy

        response = create_find_code_response()

        event = SearchEvent(
            response=response,
            query="test query",
            intent_type=IntentType.UNDERSTAND,
            strategies=[SearchStrategy.HYBRID_SEARCH],
            execution_time_ms=100.0,
            tools_over_privacy=False,
            feature_flags={"test-flag": "variant-a"},
        )

        assert event._query == "test query"
        assert event._tools_over_privacy is False

    def test_search_event_to_posthog_event(self) -> None:
        """Test SearchEvent converts to PostHog event format."""
        from codeweaver.agent_api.find_code.intent import IntentType
        from codeweaver.common.telemetry.events import SearchEvent
        from codeweaver.core.types.search import SearchStrategy

        response = create_find_code_response(
            total_matches=10,
            total_results=5,
            token_count=1000,
            execution_time_ms=150.0,
            status="success",
            indexing_state="complete",
            index_coverage=95.0,
        )

        event = SearchEvent(
            response=response,
            query="test query",
            intent_type=IntentType.UNDERSTAND,
            strategies=[SearchStrategy.HYBRID_SEARCH],
            execution_time_ms=150.0,
            tools_over_privacy=False,
            feature_flags={"search-ranking-v2": "variant-a"},
        )

        event_name, properties = event.to_posthog_event()

        assert event_name == "codeweaver_search"
        assert properties["intent"] == "understand"
        assert properties["execution_time_ms"] == 150.0
        assert properties["results"]["candidates"] == 10
        assert properties["results"]["returned"] == 5
        assert properties["status"] == "success"
        assert properties["index"]["state"] == "complete"
        assert "$feature/search-ranking-v2" in properties

    def test_search_event_with_tools_over_privacy(self) -> None:
        """Test SearchEvent includes query details when tools_over_privacy=True."""
        from codeweaver.agent_api.find_code.intent import IntentType
        from codeweaver.common.telemetry.events import SearchEvent
        from codeweaver.core.types.search import SearchStrategy

        response = create_find_code_response()

        event = SearchEvent(
            response=response,
            query="find authentication functions",
            intent_type=IntentType.UNDERSTAND,
            strategies=[SearchStrategy.HYBRID_SEARCH],
            execution_time_ms=100.0,
            tools_over_privacy=True,  # Opt-in to detailed tracking
            feature_flags=None,
        )

        _event_name, properties = event.to_posthog_event()

        # Query details should be included
        assert "query" in properties
        assert properties["query"]["token_count"] == 3  # "find authentication functions"
        assert properties["query"]["char_count"] == len("find authentication functions")
        # The query dict includes redacted query and results, not a hash
        assert "query" in properties["query"]  # The redacted query string
        assert "results" in properties["query"]  # The redacted results JSON

    def test_search_event_without_tools_over_privacy(self) -> None:
        """Test SearchEvent excludes query details when tools_over_privacy=False."""
        from codeweaver.agent_api.find_code.intent import IntentType
        from codeweaver.common.telemetry.events import SearchEvent
        from codeweaver.core.types.search import SearchStrategy

        response = create_find_code_response()

        event = SearchEvent(
            response=response,
            query="find authentication functions",
            intent_type=IntentType.UNDERSTAND,
            strategies=[SearchStrategy.HYBRID_SEARCH],
            execution_time_ms=100.0,
            tools_over_privacy=False,  # Privacy mode
            feature_flags=None,
        )

        _event_name, properties = event.to_posthog_event()

        # Query details should NOT be included
        assert "query" not in properties


@pytest.mark.mock_only
@pytest.mark.telemetry
class TestContextManagement:
    """Test PostHog context management."""

    def test_start_session(self) -> None:
        """Test start_session initializes context."""
        client = PostHogClient(enabled=False)

        # Should not raise even when disabled
        client.start_session({"version": "0.5.0"})

        # Session should not be started when disabled
        assert client._session_started is False

    def test_end_session(self) -> None:
        """Test end_session cleans up context."""
        client = PostHogClient(enabled=False)

        # Should not raise even when disabled
        client.end_session()

    def test_context_manager(self) -> None:
        """Test PostHogClient works as context manager."""
        with PostHogClient(enabled=False) as client:
            assert client.enabled is False
            client.capture("test_event", {"key": "value"})

        # end_session should have been called

    def test_feature_flag_returns_none_when_disabled(self) -> None:
        """Test feature flag returns None when client is disabled."""
        client = PostHogClient(enabled=False)

        result = client.get_feature_flag("test-flag")

        assert result is None

    def test_get_all_feature_flags_returns_empty_when_disabled(self) -> None:
        """Test get_all_feature_flags returns empty dict when disabled."""
        client = PostHogClient(enabled=False)

        result = client.get_all_feature_flags()

        assert result == {}


@pytest.mark.mock_only
@pytest.mark.telemetry
class TestConvenienceFunctions:
    """Test convenience functions for capturing events."""

    def test_capture_session_event_respects_opt_out(self) -> None:
        """Test capture_session_event doesn't capture when disabled."""
        from codeweaver.common.telemetry.events import capture_session_event

        with patch("codeweaver.common.telemetry.get_telemetry_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.enabled = False
            mock_get_client.return_value = mock_client

            stats = create_session_statistics()
            capture_session_event(stats, version="0.5.0", duration_seconds=100.0)

            # capture should not be called when disabled
            mock_client.capture.assert_not_called()

    def test_capture_search_event_respects_opt_out(self) -> None:
        """Test capture_search_event doesn't capture when disabled."""
        from codeweaver.agent_api.find_code.intent import IntentType
        from codeweaver.common.telemetry.events import capture_search_event
        from codeweaver.core.types.search import SearchStrategy

        with patch("codeweaver.common.telemetry.get_telemetry_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.enabled = False
            mock_get_client.return_value = mock_client

            response = create_find_code_response()

            capture_search_event(
                response=response,
                query="test",
                intent_type=IntentType.UNDERSTAND,
                strategies=[SearchStrategy.HYBRID_SEARCH],
                execution_time_ms=100.0,
            )

            # capture should not be called when disabled
            mock_client.capture.assert_not_called()

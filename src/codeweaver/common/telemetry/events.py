# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Telemetry event schemas for PostHog integration.

Defines two primary events that leverage PostHog's property system:
1. SessionEvent - Aggregated session statistics for understanding usage patterns
2. SearchEvent - Per-search metrics for find_code with A/B testing support

All events use privacy-safe, anonymized data with support for opt-in detailed tracking.
"""

from __future__ import annotations

import hashlib
import statistics

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, Self


if TYPE_CHECKING:
    from codeweaver.agent_api.find_code.intent import IntentType
    from codeweaver.agent_api.find_code.types import FindCodeResponseSummary, SearchStrategy
    from codeweaver.common.statistics import SessionStatistics


class TelemetryEvent(Protocol):
    """Protocol for telemetry events."""

    def to_posthog_event(self) -> tuple[str, dict[str, Any]]:
        """
        Convert event to PostHog format.

        Returns:
            Tuple of (event_name, properties_dict)
        """
        ...


class SessionEvent:
    """
    Session telemetry event for understanding usage patterns.

    Serializes SessionStatistics to track:
    - Setup success/failure for identifying trouble spots
    - Request statistics and performance
    - Token economics and savings
    - Repository characteristics (languages, file counts)
    - Failover statistics

    Leverages PostHog properties:
    - $set_once for first-session tracking
    - $set for updateable properties
    - Nested properties for logical grouping
    """

    EVENT_NAME = "codeweaver_session"

    @classmethod
    def from_statistics(
        cls,
        stats: SessionStatistics,
        *,
        version: str = "unknown",
        setup_success: bool = True,
        setup_attempts: int = 1,
        config_errors: list[str] | None = None,
        duration_seconds: float = 0.0,
    ) -> Self:
        """
        Create SessionEvent from SessionStatistics.

        Args:
            stats: Session statistics to serialize
            version: CodeWeaver version
            setup_success: Whether setup completed successfully
            setup_attempts: Number of setup attempts before success
            config_errors: List of configuration error types encountered
            duration_seconds: Total session duration

        Returns:
            SessionEvent instance
        """
        instance = cls()
        instance._stats = stats
        instance._version = version
        instance._setup_success = setup_success
        instance._setup_attempts = setup_attempts
        instance._config_errors = config_errors or []
        instance._duration_seconds = duration_seconds
        return instance

    def __init__(self) -> None:
        """Initialize empty SessionEvent (use from_statistics classmethod)."""
        self._stats: SessionStatistics | None = None
        self._version = "unknown"
        self._setup_success = True
        self._setup_attempts = 1
        self._config_errors: list[str] = []
        self._duration_seconds = 0.0

    def to_posthog_event(self) -> tuple[str, dict[str, Any]]:
        """Convert to PostHog event format with structured properties.

        Uses serialize_for_telemetry() to apply anonymization rules defined
        in _telemetry_keys() for each statistics component.
        """
        if not self._stats:
            return (self.EVENT_NAME, {})

        stats = self._stats

        # Use serialize_for_telemetry() to get properly anonymized base data
        # This applies _telemetry_keys() rules (COUNT, TEXT_COUNT, FORBIDDEN, etc.)
        base_data = stats.serialize_for_telemetry()

        properties: dict[str, Any] = {
            # PostHog special properties for person tracking
            "$set_once": {"first_seen": datetime.now(UTC).isoformat()},
            "$set": {
                "last_active": datetime.now(UTC).isoformat(),
                "codeweaver_version": self._version,
            },
            # Session duration
            "duration_seconds": round(self._duration_seconds, 2),
            # Setup success metrics (primary interest for identifying trouble spots)
            "setup": {
                "success": self._setup_success,
                "attempts": self._setup_attempts,
                "errors": self._config_errors,
            },
            # Request statistics (from computed properties, always safe)
            "requests": {
                "total": stats.total_requests,
                "successful": stats.successful_requests,
                "failed": stats.failed_requests,
                "success_rate": round(stats.success_rate, 3),
            },
            # HTTP request statistics
            "http_requests": {
                "total": stats.total_http_requests,
                "successful": stats.successful_http_requests,
                "failed": stats.failed_http_requests,
                "success_rate": round(stats.http_success_rate, 3),
            },
        }

        # Add timing statistics if available (from anonymized base data)
        if base_data.get("timing_statistics"):
            timing_data = base_data["timing_statistics"]
            if "timing_summary" in timing_data:
                timing_summary = timing_data["timing_summary"]
                properties["timing"] = {
                    "tool_calls": {
                        "avg_ms": timing_summary.get("averages", {})
                        .get("on_call_tool_requests", {})
                        .get("combined", 0.0),
                        "count": timing_summary.get("counts", {})
                        .get("on_call_tool_requests", {})
                        .get("combined", 0),
                    },
                    "http": {
                        "health_avg_ms": timing_summary.get("averages", {})
                        .get("http_requests", {})
                        .get("health", 0.0),
                        "health_count": timing_summary.get("counts", {})
                        .get("http_requests", {})
                        .get("health", 0),
                    },
                }

        # Add token statistics if available (from anonymized base data)
        if base_data.get("token_statistics"):
            tokens = base_data["token_statistics"]
            properties["tokens"] = {
                "embedding": tokens.get("total_generated", 0),
                "delivered": tokens.get("total_used", 0),
                "saved": tokens.get("context_saved", 0),
                "savings_usd": round(tokens.get("money_saved", 0.0), 4),
            }

        # Add index/file statistics if available (from anonymized base data)
        if base_data.get("index_statistics"):
            idx = base_data["index_statistics"]
            properties["index"] = {
                "total_files": idx.get("total_file_count", 0),
                "by_category": idx.get("file_count_by_category", {}),
                "total_operations": idx.get("total_operations", 0),
                "languages": idx.get("language_counts", {}),
            }

        # Add failover statistics if available (from anonymized base data)
        if base_data.get("failover_statistics"):
            failover = base_data["failover_statistics"]
            properties["failover"] = {
                "occurred": failover.get("failover_active", False)
                or failover.get("failover_count", 0) > 0,
                "count": failover.get("failover_count", 0),
                "time_seconds": round(failover.get("total_failover_time_seconds", 0.0), 2),
                "active_store": failover.get("active_store_type"),
            }

        return (self.EVENT_NAME, properties)


class SearchEvent:
    """
    Per-search telemetry event for find_code analytics.

    Tracks:
    - Search intent and strategies used
    - Performance timing
    - Result quality metrics
    - Index state
    - Feature flags for A/B testing

    Supports privacy-aware detailed tracking via tools_over_privacy setting.
    """

    EVENT_NAME = "codeweaver_search"

    def __init__(
        self,
        response: FindCodeResponseSummary,
        query: str,
        intent_type: IntentType,
        strategies: list[SearchStrategy],
        execution_time_ms: float,
        *,
        tools_over_privacy: bool = False,
        feature_flags: dict[str, str | None] | None = None,
    ) -> None:
        """
        Initialize SearchEvent.

        Args:
            response: FindCodeResponseSummary from find_code
            query: Original search query
            intent_type: Detected or specified intent
            strategies: Search strategies used
            execution_time_ms: Total execution time
            tools_over_privacy: Whether to include detailed query data
            feature_flags: Feature flag variants for A/B testing
        """
        self._response = response
        self._query = query
        self._intent_type = intent_type
        self._strategies = strategies
        self._execution_time_ms = execution_time_ms
        self._tools_over_privacy = tools_over_privacy
        self._feature_flags = feature_flags or {}

    def to_posthog_event(self) -> tuple[str, dict[str, Any]]:
        """Convert to PostHog event format with structured properties.

        Uses serialize_for_telemetry() to apply anonymization rules defined
        in _telemetry_keys() for FindCodeResponseSummary and CodeMatch.
        """
        response = self._response

        # Use serialize_for_telemetry() to get properly anonymized base data
        # This applies _telemetry_keys() rules (e.g., summary -> TEXT_COUNT, related_symbols -> COUNT)
        base_data = response.serialize_for_telemetry()

        properties: dict[str, Any] = {
            # Core search info
            "intent": self._intent_type.value
            if hasattr(self._intent_type, "value")
            else str(self._intent_type),
            "strategies": [s.value if hasattr(s, "value") else str(s) for s in self._strategies],
            "search_mode": base_data.get("search_mode"),
            # Timing
            "execution_time_ms": round(self._execution_time_ms, 2),
            # Results (from anonymized data)
            "results": {
                "candidates": base_data.get("total_matches", 0),
                "returned": base_data.get("total_results", 0),
                "token_count": base_data.get("token_count", 0),
            },
            # Status
            "status": base_data.get("status", "unknown"),
            "has_warnings": bool(base_data.get("warnings")),
            "warning_count": len(base_data.get("warnings", [])),
            # Index state
            "index": {
                "state": base_data.get("indexing_state"),
                "coverage": round(base_data.get("index_coverage", 0), 2)
                if base_data.get("index_coverage")
                else None,
            },
            # Language distribution (count only for privacy)
            "language_count": len(base_data.get("languages_found", [])),
            # Summary is anonymized to TEXT_COUNT by _telemetry_keys()
            "summary_length": base_data.get("summary", 0)
            if isinstance(base_data.get("summary"), int)
            else len(str(base_data.get("summary", ""))),
        }

        if (matches_data := base_data.get("matches", [])) and (
            scores := [
                m.get("relevance_score", 0)
                for m in matches_data
                if m.get("relevance_score") is not None
            ]
        ):
            properties["quality"] = {
                "avg_score": round(statistics.mean(scores), 3),
                "min_score": round(min(scores), 3),
                "max_score": round(max(scores), 3),
                "median_score": round(statistics.median(scores), 3),
            }

            # Match type distribution
            match_types: dict[str, int] = {}
            for match in matches_data:
                mt = match.get("match_type", "unknown")
                if hasattr(mt, "value"):
                    mt = mt.value
                match_types[str(mt)] = match_types.get(str(mt), 0) + 1
            properties["match_types"] = match_types

            # Match count (related_symbols is anonymized to COUNT)
            properties["match_count"] = len(matches_data)

        # Feature flags for A/B testing (using PostHog's $feature/ prefix)
        for flag_key, variant in self._feature_flags.items():
            if variant is not None:
                properties[f"$feature/{flag_key}"] = variant

        # Opt-in detailed tracking (only when tools_over_privacy=True)
        if self._tools_over_privacy:
            properties["query"] = {
                "token_count": len(self._query.split()),
                "char_count": len(self._query),
                # Hash for pattern analysis without content
                "hash": hashlib.sha256(self._query.encode()).hexdigest()[:16],
            }

        return (self.EVENT_NAME, properties)


def capture_session_event(
    stats: SessionStatistics,
    *,
    version: str = "unknown",
    setup_success: bool = True,
    setup_attempts: int = 1,
    config_errors: list[str] | None = None,
    duration_seconds: float = 0.0,
) -> None:
    """
    Convenience function to capture a session event.

    Args:
        stats: Session statistics to serialize
        version: CodeWeaver version
        setup_success: Whether setup completed successfully
        setup_attempts: Number of setup attempts
        config_errors: Configuration errors encountered
        duration_seconds: Session duration
    """
    from codeweaver.common.telemetry import get_telemetry_client

    client = get_telemetry_client()
    if not client.enabled:
        return

    event = SessionEvent.from_statistics(
        stats,
        version=version,
        setup_success=setup_success,
        setup_attempts=setup_attempts,
        config_errors=config_errors,
        duration_seconds=duration_seconds,
    )

    event_name, properties = event.to_posthog_event()
    client.capture(event_name, properties)


def capture_search_event(
    response: FindCodeResponseSummary,
    query: str,
    intent_type: IntentType,
    strategies: list[SearchStrategy],
    execution_time_ms: float,
    *,
    tools_over_privacy: bool = False,
    feature_flags: dict[str, str | None] | None = None,
) -> None:
    """
    Convenience function to capture a search event.

    Args:
        response: FindCodeResponseSummary from find_code
        query: Original search query
        intent_type: Detected or specified intent
        strategies: Search strategies used
        execution_time_ms: Total execution time
        tools_over_privacy: Whether to include detailed query data
        feature_flags: Feature flag variants for A/B testing
    """
    from codeweaver.common.telemetry import get_telemetry_client

    client = get_telemetry_client()
    if not client.enabled:
        return

    event = SearchEvent(
        response=response,
        query=query,
        intent_type=intent_type,
        strategies=strategies,
        execution_time_ms=execution_time_ms,
        tools_over_privacy=tools_over_privacy,
        feature_flags=feature_flags,
    )

    event_name, properties = event.to_posthog_event()
    client.capture(event_name, properties)


__all__ = (
    "SearchEvent",
    "SessionEvent",
    "TelemetryEvent",
    "capture_search_event",
    "capture_session_event",
)

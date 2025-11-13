# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Telemetry event schemas.

Defines structured event types for CodeWeaver telemetry with privacy-safe schemas.
All events use only aggregated, anonymized data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Protocol, Self

from pydantic import Field, NonNegativeFloat, NonNegativeInt
from pydantic.dataclasses import dataclass

from codeweaver.core.types.models import DATACLASS_CONFIG, DataclassSerializationMixin


if TYPE_CHECKING:
    from codeweaver.common.statistics import SessionStatistics
    from codeweaver.core.types.aliases import FilteredKeyT
    from codeweaver.core.types.enum import AnonymityConversion
    from codeweaver.server.server import AppState


def _get_statistics() -> SessionStatistics:
    """Helper to get current session statistics."""
    from codeweaver.common.statistics import get_session_statistics

    return get_session_statistics()


def _get_state() -> AppState:
    """Helper to get current application state."""
    from codeweaver.server.server import get_state

    return get_state()


class TelemetryEvent(Protocol):
    """Protocol for telemetry events."""

    @classmethod
    def generate_payload(cls, **kwargs: Any) -> Self:
        """
        Generate telemetry payload.

        Returns:
            Tuple of (event_name, properties_dict)
        """
        ...

    def to_posthog_event(self) -> tuple[str, dict]:
        """
        Convert event to PostHog format.

        Returns:
            Tuple of (event_name, properties_dict)
        """
        ...


@dataclass(config=DATACLASS_CONFIG)
class SessionSummaryEvent(DataclassSerializationMixin):
    """
    Session summary telemetry event.

    Aggregated statistics for a complete session. Sent at session end
    or periodically during long-running sessions.
    """

    session_duration_minutes: Annotated[
        NonNegativeFloat, Field(description="Total session duration in minutes")
    ]

    total_searches: Annotated[
        NonNegativeInt, Field(description="Total number of searches performed")
    ]

    successful_searches: Annotated[
        NonNegativeInt, Field(description="Number of successful searches")
    ]

    failed_searches: Annotated[NonNegativeInt, Field(description="Number of failed searches")]

    success_rate: Annotated[
        NonNegativeFloat, Field(description="Success rate as decimal (0.0-1.0)", ge=0.0, le=1.0)
    ]

    avg_response_ms: Annotated[
        NonNegativeFloat, Field(description="Average response time in milliseconds")
    ]

    median_response_ms: Annotated[
        NonNegativeFloat, Field(description="Median response time in milliseconds")
    ]

    p95_response_ms: Annotated[
        NonNegativeFloat, Field(description="95th percentile response time in milliseconds")
    ]

    total_tokens_generated: Annotated[
        NonNegativeInt, Field(description="Total tokens generated for embeddings")
    ]

    total_tokens_delivered: Annotated[
        NonNegativeInt, Field(description="Total tokens delivered to user agent")
    ]

    total_tokens_saved: Annotated[
        NonNegativeInt, Field(description="Total tokens saved vs baseline")
    ]

    context_reduction_pct: Annotated[
        NonNegativeFloat,
        Field(description="Context reduction percentage vs baseline", ge=0.0, le=100.0),
    ]

    estimated_cost_savings_usd: Annotated[
        NonNegativeFloat, Field(description="Estimated cost savings in USD")
    ]

    languages: Annotated[
        dict[str, NonNegativeInt],
        Field(description="Anonymized language distribution (counts only)"),
    ]

    semantic_frequencies: Annotated[
        dict[str, NonNegativeFloat],
        Field(description="Semantic category usage frequencies (percentages)"),
    ]

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """All fields in SessionSummaryEvent are already aggregated and safe for telemetry."""
        return None

    @classmethod
    def generate_payload(cls, **kwargs: Any) -> Self:
        """
        Generate telemetry payload.

        Returns:
            Instance of SessionSummaryEvent
        """
        return cls(**kwargs)

    def to_posthog_event(self) -> tuple[str, dict]:
        """Convert to PostHog event format."""
        return (
            "codeweaver_session_summary",
            {
                "session_duration_minutes": self.session_duration_minutes,
                "total_searches": self.total_searches,
                "successful_searches": self.successful_searches,
                "failed_searches": self.failed_searches,
                "success_rate": self.success_rate,
                "timing": {
                    "avg_response_ms": self.avg_response_ms,
                    "median_response_ms": self.median_response_ms,
                    "p95_response_ms": self.p95_response_ms,
                },
                "tokens": {
                    "total_generated": self.total_tokens_generated,
                    "total_delivered": self.total_tokens_delivered,
                    "total_saved": self.total_tokens_saved,
                    "context_reduction_pct": self.context_reduction_pct,
                    "estimated_cost_savings_usd": self.estimated_cost_savings_usd,
                },
                "languages": self.languages,
                "semantic_frequencies": self.semantic_frequencies,
            },
        )


@dataclass(config=DATACLASS_CONFIG)
class PerformanceBenchmarkEvent(DataclassSerializationMixin):
    """
    Performance benchmark telemetry event.

    Compares CodeWeaver performance against baseline naive approaches.
    Demonstrates efficiency improvements with concrete metrics.
    """

    comparison_type: Annotated[
        str, Field(description="Type of comparison (e.g., 'naive_vs_codeweaver')")
    ]

    baseline_approach: Annotated[
        str, Field(description="Baseline approach name (e.g., 'grep_full_files')")
    ]

    baseline_estimated_files: Annotated[
        NonNegativeInt, Field(description="Estimated files matched by baseline")
    ]

    baseline_estimated_lines: Annotated[
        NonNegativeInt, Field(description="Estimated lines returned by baseline")
    ]

    baseline_estimated_tokens: Annotated[
        NonNegativeInt, Field(description="Estimated tokens for baseline")
    ]

    baseline_estimated_cost_usd: Annotated[
        NonNegativeFloat, Field(description="Estimated cost for baseline in USD")
    ]

    codeweaver_files_returned: Annotated[
        NonNegativeInt, Field(description="Actual files returned by CodeWeaver")
    ]

    codeweaver_lines_returned: Annotated[
        NonNegativeInt, Field(description="Actual lines returned by CodeWeaver")
    ]

    codeweaver_tokens_delivered: Annotated[
        NonNegativeInt, Field(description="Actual tokens delivered by CodeWeaver")
    ]

    codeweaver_actual_cost_usd: Annotated[
        NonNegativeFloat, Field(description="Actual cost for CodeWeaver in USD")
    ]

    files_reduction_pct: Annotated[
        NonNegativeFloat, Field(description="File count reduction percentage", ge=0.0, le=100.0)
    ]

    lines_reduction_pct: Annotated[
        NonNegativeFloat, Field(description="Line count reduction percentage", ge=0.0, le=100.0)
    ]

    tokens_reduction_pct: Annotated[
        NonNegativeFloat, Field(description="Token count reduction percentage", ge=0.0, le=100.0)
    ]

    cost_savings_pct: Annotated[
        NonNegativeFloat, Field(description="Cost savings percentage", ge=0.0, le=100.0)
    ]

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """All fields in PerformanceBenchmarkEvent are already aggregated and safe for telemetry."""
        return None

    def to_posthog_event(self) -> tuple[str, dict]:
        """Convert to PostHog event format."""
        return (
            "codeweaver_performance_benchmark",
            {
                "comparison_type": self.comparison_type,
                "baseline": {
                    "approach": self.baseline_approach,
                    "estimated_files": self.baseline_estimated_files,
                    "estimated_lines": self.baseline_estimated_lines,
                    "estimated_tokens": self.baseline_estimated_tokens,
                    "estimated_cost_usd": self.baseline_estimated_cost_usd,
                },
                "codeweaver": {
                    "files_returned": self.codeweaver_files_returned,
                    "lines_returned": self.codeweaver_lines_returned,
                    "tokens_delivered": self.codeweaver_tokens_delivered,
                    "actual_cost_usd": self.codeweaver_actual_cost_usd,
                },
                "improvement": {
                    "files_reduction_pct": self.files_reduction_pct,
                    "lines_reduction_pct": self.lines_reduction_pct,
                    "tokens_reduction_pct": self.tokens_reduction_pct,
                    "cost_savings_pct": self.cost_savings_pct,
                },
            },
        )


@dataclass(config=DATACLASS_CONFIG)
class SemanticValidationEvent(DataclassSerializationMixin):
    """
    Semantic category validation telemetry event.

    Analyzes semantic category usage patterns to validate and tune
    the importance scoring system.
    """

    period: Annotated[str, Field(description="Analysis period (e.g., 'daily', 'weekly')")]

    total_chunks_analyzed: Annotated[
        NonNegativeInt, Field(description="Total code chunks analyzed")
    ]

    category_usage: Annotated[
        dict[str, NonNegativeInt], Field(description="Usage counts by semantic category")
    ]

    usage_frequencies: Annotated[
        dict[str, NonNegativeFloat], Field(description="Usage frequencies by semantic category")
    ]

    correlation: Annotated[
        NonNegativeFloat,
        Field(description="Correlation between usage and importance scores", ge=-1.0, le=1.0),
    ]

    note: Annotated[str, Field(description="Analysis note or interpretation")]

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """All fields in SemanticValidationEvent are already aggregated and safe for telemetry."""
        return None

    def to_posthog_event(self) -> tuple[str, dict]:
        """Convert to PostHog event format."""
        return (
            "codeweaver_semantic_validation",
            {
                "period": self.period,
                "total_chunks_analyzed": self.total_chunks_analyzed,
                "category_usage": self.category_usage,
                "usage_frequencies": self.usage_frequencies,
                "alignment_with_scores": {"correlation": self.correlation, "note": self.note},
            },
        )


__all__ = (
    "PerformanceBenchmarkEvent",
    "SemanticValidationEvent",
    "SessionSummaryEvent",
    "TelemetryEvent",
)

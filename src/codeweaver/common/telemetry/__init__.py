# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Privacy-preserving telemetry system for CodeWeaver.

This module provides telemetry infrastructure for collecting anonymized,
aggregated metrics to understand CodeWeaver usage patterns and identify
trouble spots while maintaining strict privacy guarantees.

Key Principles:
- Never collect PII, code, or repository information
- Aggregated statistics only
- Easy opt-out mechanism
- Fail-safe (errors don't affect application)
- PostHog v7 context API for session tracking

Events:
- SessionEvent: Aggregated session statistics (usage patterns, setup success)
- SearchEvent: Per-search metrics (performance, quality, A/B testing)

Example:
    >>> from codeweaver.common.telemetry import (
    ...     get_telemetry_client,
    ...     capture_search_event,
    ... )
    >>> client = get_telemetry_client()
    >>> client.start_session({"version": "0.5.0"})
    >>> if client.enabled:
    ...     client.capture("codeweaver_session", {"searches": 10})
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    # Import everything for IDE and type checker support
    # These imports are never executed at runtime, only during type checking
    from codeweaver.common.telemetry.client import SESSION_ID, PostHogClient, get_telemetry_client
    from codeweaver.common.telemetry.events import (
        SearchEvent,
        SessionEvent,
        TelemetryEvent,
        capture_search_event,
        capture_session_event,
    )


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "PostHogClient": (__spec__.parent, "client"),
    "SESSION_ID": (__spec__.parent, "client"),
    "SearchEvent": (__spec__.parent, "events"),
    "SessionEvent": (__spec__.parent, "events"),
    "TelemetryEvent": (__spec__.parent, "events"),
    "capture_search_event": (__spec__.parent, "events"),
    "capture_session_event": (__spec__.parent, "events"),
    "get_telemetry_client": (__spec__.parent, "client"),
})


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "SESSION_ID",
    "PostHogClient",
    "SearchEvent",
    "SessionEvent",
    "TelemetryEvent",
    "capture_search_event",
    "capture_session_event",
    "get_telemetry_client",
)


def __dir__() -> list[str]:
    """List available attributes for the module."""
    return list(__all__)

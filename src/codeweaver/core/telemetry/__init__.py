# SPDX-FileCopyrightText: 2026 Knitli Inc.
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
    >>> from codeweaver.core.telemetry import get_telemetry_client, capture_search_event
    >>> client = get_telemetry_client()
    >>> client.start_session({"version": "0.5.0"})
    >>> if client.enabled:
    ...     client.capture("codeweaver_session", {"searches": 10})
"""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.core.telemetry._project import CODEWEAVER_POSTHOG_PROJECT_KEY
    from codeweaver.core.telemetry.client import (
        NO_HOG,
        SESSION_ID,
        TelemetryService,
        get_telemetry_client,
    )
    from codeweaver.core.telemetry.events import (
        SearchEvent,
        SessionEvent,
        TelemetryEvent,
        capture_search_event,
        capture_session_event,
    )
    from codeweaver.core.telemetry.utils import (
        PATTERNS,
        IntifyingPatterns,
        find_identifiable_info,
        redact_identifiable_info,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CODEWEAVER_POSTHOG_PROJECT_KEY": (__spec__.parent, "_project"),
    "NO_HOG": (__spec__.parent, "client"),
    "PATTERNS": (__spec__.parent, "utils"),
    "SESSION_ID": (__spec__.parent, "client"),
    "IntifyingPatterns": (__spec__.parent, "utils"),
    "SearchEvent": (__spec__.parent, "events"),
    "SessionEvent": (__spec__.parent, "events"),
    "TelemetryEvent": (__spec__.parent, "events"),
    "TelemetryService": (__spec__.parent, "client"),
    "capture_search_event": (__spec__.parent, "events"),
    "capture_session_event": (__spec__.parent, "events"),
    "find_identifiable_info": (__spec__.parent, "utils"),
    "get_telemetry_client": (__spec__.parent, "client"),
    "redact_identifiable_info": (__spec__.parent, "utils"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "CODEWEAVER_POSTHOG_PROJECT_KEY",
    "NO_HOG",
    "PATTERNS",
    "SESSION_ID",
    "IntifyingPatterns",
    "SearchEvent",
    "SessionEvent",
    "TelemetryEvent",
    "TelemetryService",
    "capture_search_event",
    "capture_session_event",
    "find_identifiable_info",
    "get_telemetry_client",
    "redact_identifiable_info",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Privacy-preserving telemetry system for CodeWeaver.

This module provides telemetry infrastructure for collecting anonymized,
aggregated metrics to prove CodeWeaver's efficiency claims while maintaining
strict privacy guarantees.

Key Principles:
- Never collect PII, code, or repository information
- Aggregated statistics only
- Easy opt-out mechanism
- Fail-safe (errors don't affect application)

Example:
    >>> from codeweaver.telemetry import get_telemetry_client
    >>> client = get_telemetry_client()
    >>> if client.enabled:
    ...     client.capture("session_summary", {"searches": 10})
"""

from __future__ import annotations

from codeweaver.telemetry.client import PostHogClient, get_telemetry_client
from codeweaver.telemetry.config import TelemetrySettings, get_telemetry_settings
from codeweaver.telemetry.events import (
    PerformanceBenchmarkEvent,
    SessionSummaryEvent,
    TelemetryEvent,
)
from codeweaver.telemetry.privacy import PrivacyFilter

__all__ = (
    "PostHogClient",
    "PrivacyFilter",
    "TelemetrySettings",
    "TelemetryEvent",
    "SessionSummaryEvent",
    "PerformanceBenchmarkEvent",
    "get_telemetry_client",
    "get_telemetry_settings",
)

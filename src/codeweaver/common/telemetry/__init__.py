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
    >>> from codeweaver.common.telemetry import get_telemetry_client
    >>> client = get_telemetry_client()
    >>> if client.enabled:
    ...     client.capture("session_summary", {"searches": 10})
"""

from __future__ import annotations

from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    # Import everything for IDE and type checker support
    # These imports are never executed at runtime, only during type checking
    from codeweaver.common.telemetry.client import PostHogClient, get_telemetry_client
    from codeweaver.common.telemetry.events import (
        PerformanceBenchmarkEvent,
        SessionSummaryEvent,
        TelemetryEvent,
    )


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "PerformanceBenchmarkEvent": (__spec__.parent, "events"),
    "PostHogClient": (__spec__.parent, "client"),
    "SessionSummaryEvent": (__spec__.parent, "events"),
    "TelemetryEvent": (__spec__.parent, "events"),
    "get_telemetry_client": (__spec__.parent, "client"),
})


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the telemetry package."""
    if name in _dynamic_imports:
        module_name, submodule_name = _dynamic_imports[name]
        module = import_module(f"{module_name}.{submodule_name}")
        result = getattr(module, name)
        globals()[name] = result  # Cache in globals for future access
        return result
    if globals().get(name) is not None:
        return globals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = (
    "PerformanceBenchmarkEvent",
    "PostHogClient",
    "SessionSummaryEvent",
    "TelemetryEvent",
    "get_telemetry_client",
)


def __dir__() -> list[str]:
    """List available attributes for the module."""
    return list(__all__)

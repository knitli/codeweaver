# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Dependency injection types and factories for core services."""

from __future__ import annotations

from codeweaver.core.dependencies.utils import ensure_settings_initialized


ensure_settings_initialized()


from typing import Annotated

from codeweaver.core.di.depends import depends
from codeweaver.core.di.utils import dependency_provider
from codeweaver.core.statistics import SessionStatistics


@dependency_provider(SessionStatistics, scope="singleton")
def _get_statistics() -> SessionStatistics:
    from codeweaver.core.statistics import SessionStatistics

    return SessionStatistics(
        _successful_request_log=[],
        _failed_request_log=[],
        _successful_http_request_log=[],
        _failed_http_request_log=[],
    )


type StatisticsDep = Annotated[SessionStatistics, depends(_get_statistics)]


from codeweaver.core.telemetry.client import TelemetryService


type TelemetryServiceDep = Annotated[TelemetryService, depends()]


from codeweaver.core.ui_protocol import (
    NoOpProgressReporter,
    ProgressReporter,
    RichConsoleProgressReporter,
)


@dependency_provider(ProgressReporter, scope="singleton")
def _create_progress_reporter() -> ProgressReporter:
    """Factory for progress reporter.

    Returns:
        - NoOpProgressReporter for testing
        - RichConsoleProgressReporter for server/daemon (uses Rich Console)
        - CLI can override with StatusDisplay implementation
    """
    from codeweaver.core.utils.environment import is_tty

    if is_tty():
        from codeweaver.core._logging import get_rich_console

        console = get_rich_console()

        return RichConsoleProgressReporter(console=console)

    # Default: no-op (e.g., testing)
    return NoOpProgressReporter()


type ProgressReporterDep = Annotated[ProgressReporter, depends(_create_progress_reporter)]


__all__ = ("ProgressReporterDep", "StatisticsDep", "TelemetryServiceDep")

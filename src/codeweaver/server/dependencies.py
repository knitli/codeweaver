# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dependency injection setup for server components.

This module provides DI factories for server-side services and state.
"""

from __future__ import annotations

import time

from typing import TYPE_CHECKING, Annotated

from codeweaver.core.dependencies import (
    ResolvedProjectNameDep,
    ResolvedProjectPathDep,
    SettingsDep,
    StatisticsDep,
    TelemetryServiceDep,
)
from codeweaver.core.di import INJECTED, dependency_provider, depends
from codeweaver.engine.dependencies import FailoverServiceDep, IndexingServiceDep
from codeweaver.providers import AllProviderSettingsDep

# Runtime imports needed for dependency_provider decorators
from codeweaver.server.health.health_service import HealthService
from codeweaver.server.management import ManagementServer
from codeweaver.server.server import CodeWeaverState


if TYPE_CHECKING:
    from codeweaver.server.management import ManagementServer


# ===========================================================================
# Service Factories
# ===========================================================================


@dependency_provider(HealthService, scope="singleton")
def _create_health_service(
    statistics: StatisticsDep = INJECTED,
    indexer: IndexingServiceDep = INJECTED,
    failover_manager: FailoverServiceDep = INJECTED,
    providers: AllProviderSettingsDep = INJECTED,
) -> HealthService:
    """Factory for health service."""
    return HealthService(
        statistics=statistics,
        indexer=indexer,
        failover_manager=failover_manager,
        providers=providers,
        startup_stopwatch=time.monotonic(),
    )


type HealthServiceDep = Annotated[
    "HealthService", depends(_create_health_service, scope="singleton")
]


@dependency_provider(CodeWeaverState, scope="singleton")  # ty:ignore[invalid-argument-type]
async def _create_cw_state(
    settings: SettingsDep = INJECTED,
    statistics: StatisticsDep = INJECTED,
    indexer: IndexingServiceDep = INJECTED,
    health_service: HealthServiceDep = INJECTED,
    failover_manager: FailoverServiceDep = INJECTED,
    project_path: ResolvedProjectPathDep = INJECTED,
    project_name: ResolvedProjectNameDep = INJECTED,
    telemetry: TelemetryServiceDep = INJECTED,
) -> CodeWeaverState:
    """Factory for application state."""
    return CodeWeaverState(
        initialized=False,
        project_path=project_path,
        config_path=settings.config_path,  # ty:ignore[unresolved-attribute]
        settings=settings,
        statistics=statistics,
        indexer=indexer,
        health_service=health_service,
        failover_manager=failover_manager,
        telemetry=telemetry,
    )


type CodeWeaverStateDep = Annotated[CodeWeaverState, depends(_create_cw_state, scope="singleton")]


@dependency_provider(ManagementServer, scope="singleton")
def _create_management_server(state: CodeWeaverStateDep = INJECTED) -> ManagementServer:
    """Factory for management server."""
    return ManagementServer(background_state=state)


type ManagementServerDep = Annotated[
    "ManagementServer", depends(_create_management_server, scope="singleton")
]

__all__ = ("CodeWeaverStateDep", "HealthServiceDep", "ManagementServerDep")

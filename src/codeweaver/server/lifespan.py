# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Lifespan management for CodeWeaver background services and servers.

This module provides lifespan context managers for different deployment modes:
- background_services_lifespan: Background services only (daemon mode)
- http_lifespan: Background services + HTTP MCP server integration
"""

from __future__ import annotations

import asyncio
import logging

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from codeweaver.server.server import CodeWeaverState


if TYPE_CHECKING:
    from codeweaver.cli.ui import StatusDisplay
    from codeweaver.common.statistics import SessionStatistics
    from codeweaver.config.settings import CodeWeaverSettings
    from codeweaver.mcp.state import CwMcpHttpState

logger = logging.getLogger(__name__)


@asynccontextmanager
async def background_services_lifespan(
    settings: CodeWeaverSettings | None = None,
    statistics: SessionStatistics | None = None,
    status_display: StatusDisplay | None = None,
    *,
    verbose: bool = False,
    debug: bool = False,
) -> AsyncIterator[CodeWeaverState]:
    """
    Lifespan context manager for background services only.

    This manages the lifecycle of CodeWeaver's background services without
    requiring an MCP server. Used for daemon mode (`codeweaver start`).

    Manages:
    - Background indexing task
    - File watcher
    - Health monitoring
    - Statistics and telemetry

    Args:
        settings: Configuration settings
        statistics: Session statistics instance
        status_display: StatusDisplay for user-facing output (created if None)
        verbose: Enable verbose logging
        debug: Enable debug logging

    Yields:
        CodeWeaverState instance for background services
    """
    from codeweaver.cli.ui import StatusDisplay
    from codeweaver.common.utils import get_project_path
    from codeweaver.config.settings import get_settings
    from codeweaver.core.types.sentinel import Unset

    # Create StatusDisplay if not provided
    if status_display is None:
        status_display = StatusDisplay()

    if verbose or debug:
        logger.info("Entering background services lifespan context manager...")

    # Load settings if not provided
    if settings is None:
        settings = get_settings()
    if isinstance(settings.project_path, Unset):
        settings.project_path = get_project_path()

    # Initialize CodeWeaverState
    from codeweaver.server.server import _initialize_cw_state

    background_state: CodeWeaverState = await _initialize_cw_state(settings, statistics)

    indexing_task = None

    try:
        if verbose or debug:
            logger.info("Initializing background services...")

        # Start background indexing task
        from codeweaver.server.background_services import run_background_indexing

        indexing_task = asyncio.create_task(
            run_background_indexing(background_state, status_display, verbose=verbose, debug=debug)
        )

        # Perform health checks and display results
        status_display.print_step("Health checks...")

        if background_state.health_service:
            health_response = await background_state.health_service.get_health_response()

            # Vector store health with degraded handling
            vs_status = health_response.services.vector_store.status
            status_display.print_health_check("Vector store (Qdrant)", vs_status)

            # Show helpful message for degraded/down vector store
            if vs_status in ("down", "degraded") and not verbose and not debug:
                status_display.console.print(
                    "  [dim]Unable to connect. Continuing with sparse-only search.[/dim]"
                )
                status_display.console.print(
                    "  [dim]To enable semantic search: docker run -p 6333:6333 qdrant/qdrant[/dim]"
                )

            # Embeddings health
            status_display.print_health_check(
                "Embeddings (Voyage AI)",
                health_response.services.embedding_provider.status,
                model=health_response.services.embedding_provider.model,
            )

            # Sparse embeddings health
            status_display.print_health_check(
                f"Sparse embeddings ({health_response.services.sparse_embedding.provider})",
                health_response.services.sparse_embedding.status,
            )

        status_display.print_ready()

        if verbose or debug:
            logger.info("Background services initialized successfully.")

        background_state.initialized = True

        # Background services run here
        yield background_state

    except Exception:
        background_state.initialized = False
        raise
    finally:
        # Cleanup
        from codeweaver.server.server import _cleanup_state

        await _cleanup_state(
            background_state, indexing_task, status_display, verbose=verbose or debug
        )


@asynccontextmanager
async def http_lifespan(
    mcp_state: CwMcpHttpState,
    settings: CodeWeaverSettings | None = None,
    statistics: SessionStatistics | None = None,
    status_display: StatusDisplay | None = None,
    *,
    verbose: bool = False,
    debug: bool = False,
) -> AsyncIterator[CodeWeaverState]:
    """
    Lifespan context manager for HTTP MCP server with background services.

    This manages both the MCP HTTP server lifecycle and background services
    together. Used when running `codeweaver server --transport streamable-http`.

    Args:
        mcp_state: MCP HTTP server state containing FastMCP app and config
        settings: Configuration settings
        statistics: Session statistics instance
        status_display: StatusDisplay for user-facing output (created if None)
        verbose: Enable verbose logging
        debug: Enable debug logging

    Yields:
        CodeWeaverState instance for background services
    """
    from codeweaver.cli.ui import StatusDisplay

    # Create StatusDisplay if not provided
    if status_display is None:
        status_display = StatusDisplay()

    # Print header with MCP server info
    status_display.print_header(host=mcp_state.host, port=mcp_state.port)

    if verbose or debug:
        logger.info("Entering HTTP server lifespan context manager...")

    # Use background services lifespan for all the heavy lifting
    async with background_services_lifespan(
        settings=settings,
        statistics=statistics,
        status_display=status_display,
        verbose=verbose,
        debug=debug,
    ) as background_state:
        if verbose or debug:
            logger.info("HTTP server lifespan initialized with background services.")

        yield background_state


# Backward compatibility alias (deprecated)
combined_lifespan = http_lifespan


__all__ = ("background_services_lifespan", "combined_lifespan", "http_lifespan")

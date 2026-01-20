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

from codeweaver.core import CodeWeaverSettingsType, get_container
from codeweaver.core.ui_protocol import ProgressReporter, RichConsoleProgressReporter
from codeweaver.server.server import CodeWeaverState


if TYPE_CHECKING:
    from codeweaver.core import SessionStatistics
    from codeweaver.server.mcp import CwMcpHttpState

logger = logging.getLogger(__name__)


@asynccontextmanager
async def background_services_lifespan(
    settings: CodeWeaverSettingsType,
    statistics: SessionStatistics,
    progress_reporter: ProgressReporter,
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
        progress_reporter: ProgressReporter for user-facing output (created if None)
        verbose: Enable verbose logging
        debug: Enable debug logging

    Yields:
        CodeWeaverState instance for background services
    """
    if verbose or debug:
        logger.info("Entering background services lifespan context manager...")

    # Initialize CodeWeaverState
    container = get_container()
    container.override(CodeWeaverSettingsType, settings)  # ty:ignore[invalid-argument-type]

    container.override(SessionStatistics, statistics)

    background_state: CodeWeaverState = await container.resolve(CodeWeaverState)

    indexing_task = None

    try:
        if verbose or debug:
            logger.info("Initializing background services...")

        # Start background indexing task
        from codeweaver.server.background_services import run_background_indexing

        indexing_task = asyncio.create_task(
            run_background_indexing(
                background_state, progress_reporter, verbose=verbose, debug=debug
            )
        )

        # Perform health checks and display results
        progress_reporter.report_status("Health checks...")

        if background_state.health_service:
            health_response = await background_state.health_service.get_health_response()

            # Vector store health with degraded handling
            vs_status = health_response.services.vector_store.status
            status_icon = {"up": "✅", "down": "❌", "degraded": "⚠️"}.get(vs_status, vs_status)
            progress_reporter.report_status(f"Vector store (Qdrant): {status_icon}")

            # Show helpful message for degraded/down vector store
            if vs_status in ("down", "degraded") and not verbose and not debug:
                progress_reporter.report_status(
                    "  Unable to connect. Continuing with sparse-only search.", level="warning"
                )
                progress_reporter.report_status(
                    "  To enable semantic search: docker run -p 6333:6333 qdrant/qdrant",
                    level="warning",
                )

            # Embeddings health
            emb_status = health_response.services.embedding_provider.status
            emb_model = health_response.services.embedding_provider.model
            status_icon = {"up": "✅", "down": "❌", "degraded": "⚠️"}.get(emb_status, emb_status)
            progress_reporter.report_status(f"Embeddings (Voyage AI): {status_icon} ({emb_model})")

            # Sparse embeddings health
            sparse_prov = health_response.services.sparse_embedding.provider
            sparse_status = health_response.services.sparse_embedding.status
            status_icon = {"up": "✅", "down": "❌", "degraded": "⚠️"}.get(
                sparse_status, sparse_status
            )
            progress_reporter.report_status(f"Sparse embeddings ({sparse_prov}): {status_icon}")

        progress_reporter.report_status("Ready for connections.")

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
            background_state, indexing_task, progress_reporter, verbose=verbose or debug
        )


@asynccontextmanager
async def http_lifespan(
    mcp_state: CwMcpHttpState,
    settings: CodeWeaverSettingsType | None = None,
    statistics: SessionStatistics | None = None,
    progress_reporter: ProgressReporter | None = None,
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
        progress_reporter: ProgressReporter for user-facing output (created if None)
        verbose: Enable verbose logging
        debug: Enable debug logging

    Yields:
        CodeWeaverState instance for background services
    """
    # Create ProgressReporter if not provided
    if progress_reporter is None:
        progress_reporter = RichConsoleProgressReporter()

    # Print header with MCP server info
    # status_display.print_header(host=mcp_state.host, port=mcp_state.port)
    progress_reporter.report_status(f"Server: http://{mcp_state.host}:{mcp_state.port}")
    progress_reporter.report_status("Built with FastMCP (https://gofastmcp.com)", level="debug")

    if verbose or debug:
        logger.info("Entering HTTP server lifespan context manager...")

    # Use background services lifespan for all the heavy lifting
    async with background_services_lifespan(
        settings=settings,  # ty:ignore[invalid-argument-type]
        statistics=statistics,  # ty:ignore[invalid-argument-type]
        progress_reporter=progress_reporter,
        verbose=verbose,
        debug=debug,
    ) as background_state:
        if verbose or debug:
            logger.info("HTTP server lifespan initialized with background services.")

        yield background_state


# Backward compatibility alias (deprecated)
combined_lifespan = http_lifespan


__all__ = ("background_services_lifespan", "combined_lifespan", "http_lifespan")

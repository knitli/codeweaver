# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Starlette lifespan integration for background services.

Manages startup/shutdown of background services using Starlette's
AsyncExitStack pattern.
"""

from __future__ import annotations

import asyncio
import logging

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from codeweaver.server.server import CodeWeaverState


if TYPE_CHECKING:
    from fastmcp import FastMCP

    from codeweaver.common.statistics import SessionStatistics
    from codeweaver.config.settings import CodeWeaverSettings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def combined_lifespan(
    app: FastMCP,  # type: ignore[type-arg]
    settings: CodeWeaverSettings | None = None,
    statistics: SessionStatistics | None = None,
    *,
    verbose: bool = False,
    debug: bool = False,
) -> AsyncIterator[None]:
    """
    Unified lifespan context manager for background services + MCP server.

    This replaces the old lifespan() function in server.py.
    Manages both background services and MCP server lifecycle.

    Args:
        app: FastMCP application instance
        settings: Configuration settings
        statistics: Session statistics instance
        verbose: Enable verbose logging
        debug: Enable debug logging
    """
    from codeweaver.cli.ui import StatusDisplay
    from codeweaver.common.utils import get_project_path
    from codeweaver.config.settings import get_settings
    from codeweaver.core.types.sentinel import Unset

    # Create StatusDisplay for clean user-facing output
    status_display = StatusDisplay()

    # Print clean header
    server_host = getattr(app, "host", "127.0.0.1") if hasattr(app, "host") else "127.0.0.1"
    server_port = getattr(app, "port", 9328) if hasattr(app, "port") else 9328
    status_display.print_header(host=server_host, port=server_port)

    if verbose or debug:
        logger.info("Entering combined lifespan context manager...")

    # Load settings if not provided
    if settings is None:
        settings = get_settings()
    if isinstance(settings.project_path, Unset):
        settings.project_path = get_project_path()

    # Initialize CodeWeaverState (formerly AppState)
    # This is the same initialization as before, just renamed
    from codeweaver.server.server import _initialize_app_state

    # _initialize_app_state returns CodeWeaverState now (will be updated during migration)
    background_state: CodeWeaverState = _initialize_app_state(app, settings, statistics)  # type: ignore[assignment]

    # Store in app.state for access via Context
    app.state.background = background_state

    indexing_task = None

    try:
        if verbose or debug:
            logger.info("Initializing background services...")

        # Initialize background services
        await background_state.initialize()

        # Start background indexing task
        from codeweaver.server.server import _run_background_indexing

        indexing_task = asyncio.create_task(
            _run_background_indexing(
                background_state,  # type: ignore[arg-type]
                settings,
                status_display,
                verbose=verbose,
                debug=debug,
            )
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
            logger.info("Lifespan start actions complete, server initialized.")

        background_state.initialized = True

        # Server runs here
        yield

    except Exception:
        background_state.initialized = False
        raise
    finally:
        # Cleanup
        from codeweaver.server.server import _cleanup_state

        await _cleanup_state(
            background_state, indexing_task, status_display, verbose=verbose or debug
        )  # type: ignore[arg-type]

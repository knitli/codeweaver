# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Management HTTP server for observability and monitoring.

Runs independently of MCP transport choice (stdio or HTTP).
Provides health, stats, metrics, and settings endpoints.
"""

from __future__ import annotations

import asyncio
import logging
import time

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import uvicorn

from pydantic_core import to_json
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route

from codeweaver.common.statistics import SessionStatistics, get_session_statistics, timed_http
from codeweaver.config.settings import get_settings_map
from codeweaver.config.types import CodeWeaverSettingsDict
from codeweaver.core.types import DictView


if TYPE_CHECKING:
    from codeweaver.server.server import CodeWeaverState


logger = logging.getLogger(__name__)


def statistics() -> SessionStatistics:
    """Get the current session statistics."""
    return get_session_statistics()


def settings() -> DictView[CodeWeaverSettingsDict]:
    """Get the current settings."""
    return get_settings_map()


# -------------------------
# Plain route handlers
# -------------------------
@timed_http("metrics")
async def stats_info(_request: Request) -> PlainTextResponse:
    """Return current session statistics as JSON."""
    global statistics
    if stats := statistics():
        try:
            return PlainTextResponse(content=stats.report(), media_type="application/json")
        except Exception as e:
            logger.exception("Failed to serialize session statistics")
            return PlainTextResponse(
                content=to_json({"error": f"Failed to serialize session statistics: {e}"}),
                status_code=500,
                media_type="application/json",
            )
    return PlainTextResponse(
        content=to_json({"error": "No metrics available"}),
        status_code=500,
        media_type="application/json",
    )


@timed_http("settings")
async def settings_info(_request: Request) -> PlainTextResponse:
    """Return current settings as JSON."""
    settings_view: DictView[CodeWeaverSettingsDict] = settings()
    try:
        return PlainTextResponse(
            content=to_json(dict(settings_view.items())), media_type="application/json"
        )
    except Exception as e:
        logger.exception("Failed to serialize settings")
        return PlainTextResponse(
            content=to_json({"error": f"Failed to serialize settings: {e}"}),
            status_code=500,
            media_type="application/json",
        )


@timed_http("version")
async def version_info(_request: Request) -> PlainTextResponse:
    """Return current version information as JSON."""
    from codeweaver import __version__

    try:
        return PlainTextResponse(
            content=to_json({"version": __version__}), media_type="application/json"
        )
    except Exception as e:
        logger.exception("Failed to serialize version information")
        return PlainTextResponse(
            content=to_json({"error": f"Failed to serialize version information: {e}"}),
            status_code=500,
            media_type="application/json",
        )


@timed_http("state")
async def state_info(_request: Request) -> PlainTextResponse:
    """Return the complete application state as JSON."""
    from codeweaver.server.server import get_state

    state = get_state()
    return PlainTextResponse(content=state.dump_json(), media_type="application/json")


@timed_http("health")
async def health(_request: Request) -> PlainTextResponse:
    """Return enhanced health information as JSON (FR-010-Enhanced).

    Provides comprehensive system health including:
    - Overall status (healthy/degraded/unhealthy)
    - Indexing progress and state
    - Service health for all providers
    - Statistics on indexed content and queries
    """
    from codeweaver.server.server import get_state

    try:
        state = get_state()
        if state.health_service is None:
            logger.warning("Health service not initialized, returning error response")
            # Health service not initialized - create error response
            from codeweaver.server.health.models import (
                EmbeddingProviderServiceInfo,
                HealthResponse,
                IndexingInfo,
                IndexingProgressInfo,
                RerankingServiceInfo,
                ServicesInfo,
                SparseEmbeddingServiceInfo,
                StatisticsInfo,
                VectorStoreServiceInfo,
            )

            error_response = HealthResponse.create_with_current_timestamp(
                status="unhealthy",
                uptime_seconds=0,
                indexing=IndexingInfo(
                    state="error",
                    last_indexed=None,
                    progress=IndexingProgressInfo(
                        files_discovered=0,
                        files_processed=0,
                        chunks_created=0,
                        errors=0,
                        current_file=None,
                        start_time=None,
                        estimated_completion=None,
                    ),
                ),
                services=ServicesInfo(
                    vector_store=VectorStoreServiceInfo(status="down", latency_ms=0),
                    embedding_provider=EmbeddingProviderServiceInfo(
                        status="down", model="unknown", latency_ms=0, circuit_breaker_state="open"
                    ),
                    sparse_embedding=SparseEmbeddingServiceInfo(status="down", provider="unknown"),
                    reranking=RerankingServiceInfo(status="down", model="unknown", latency_ms=0),
                ),
                statistics=StatisticsInfo(
                    total_chunks_indexed=0,
                    total_files_indexed=0,
                    languages_indexed=[],
                    index_size_mb=0,
                    queries_processed=0,
                    avg_query_latency_ms=0,
                    semantic_chunks=0,
                    delimiter_chunks=0,
                    file_chunks=0,
                    avg_chunk_size=0,
                ),
            )
            return PlainTextResponse(
                content=error_response.model_dump_json(),
                status_code=503,
                media_type="application/json",
            )

        # Get health response from health service
        health_response = await state.health_service.get_health_response()
        return PlainTextResponse(
            content=health_response.model_dump_json(), media_type="application/json"
        )
    except Exception:
        logger.exception("Failed to get health status")
        # Return unhealthy status on error

        from codeweaver.server.health.models import (
            EmbeddingProviderServiceInfo,
            HealthResponse,
            IndexingInfo,
            IndexingProgressInfo,
            RerankingServiceInfo,
            ServicesInfo,
            SparseEmbeddingServiceInfo,
            StatisticsInfo,
            VectorStoreServiceInfo,
        )

        error_response = HealthResponse.create_with_current_timestamp(
            status="unhealthy",
            uptime_seconds=0,
            indexing=IndexingInfo(
                state="error",
                last_indexed=None,
                progress=IndexingProgressInfo(
                    files_discovered=0,
                    files_processed=0,
                    chunks_created=0,
                    errors=0,
                    current_file=None,
                    start_time=None,
                    estimated_completion=None,
                ),
            ),
            services=ServicesInfo(
                vector_store=VectorStoreServiceInfo(status="down", latency_ms=0),
                embedding_provider=EmbeddingProviderServiceInfo(
                    status="down", model="unknown", latency_ms=0, circuit_breaker_state="open"
                ),
                sparse_embedding=SparseEmbeddingServiceInfo(status="down", provider="unknown"),
                reranking=RerankingServiceInfo(status="down", model="unknown", latency_ms=0),
            ),
            statistics=StatisticsInfo(
                total_chunks_indexed=0,
                total_files_indexed=0,
                languages_indexed=[],
                index_size_mb=0,
                queries_processed=0,
                avg_query_latency_ms=0,
                semantic_chunks=0,
                delimiter_chunks=0,
                file_chunks=0,
                avg_chunk_size=0,
            ),
        )
        return PlainTextResponse(
            content=error_response.model_dump_json(), status_code=503, media_type="application/json"
        )


async def favicon(_request: Request) -> Response:
    """Serve the CodeWeaver favicon (SVG format)."""
    import base64

    from codeweaver.server._assets import CODEWEAVER_SVG_ICON

    # Decode the base64 SVG data
    svg_data = base64.b64decode(CODEWEAVER_SVG_ICON.src.split(",")[1])

    return Response(
        content=svg_data,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=259200"  # Cache for 72 hours
        },
    )


@timed_http("status")
async def status_info(_request: Request) -> PlainTextResponse:
    """Return current operational status (progress, failover, runtime state).

    This endpoint provides real-time operational information:
    - Current indexing progress and phase
    - Failover status and backup operations
    - Active operations and their progress
    - Runtime state (different from health checks)
    """
    from codeweaver.server.server import get_state

    try:
        state = get_state()

        status_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "uptime_seconds": int(time.time() - state.startup_time)
            if hasattr(state, "startup_time")
            else 0,
        }

        # Indexing status
        if state.indexer:
            indexer_stats = state.indexer.stats
            status_data["indexing"] = {
                "active": state.indexer._running if hasattr(state.indexer, "_running") else False,
                **indexer_stats.dump_python(),
            }
        else:
            status_data["indexing"] = {"active": False}

        # Failover status
        if getattr(state, "failover_manager", None):
            failover_stats = statistics().failover_statistics
            if failover_stats:
                status_data["failover"] = failover_stats.dump_python()
            else:
                status_data["failover"] = {"enabled": True, "active": False}
        else:
            status_data["failover"] = {"enabled": False}

        if stats := statistics():
            status_data["statistics"] = {
                "total_requests": stats.total_requests,
                "successful_requests": stats.successful_requests,
                "failed_requests": stats.failed_requests,
            }

        return PlainTextResponse(content=to_json(status_data), media_type="application/json")

    except Exception:
        logger.exception("Failed to get status information")
        return PlainTextResponse(
            content=to_json({"error": "Failed to retrieve status information"}),
            status_code=500,
            media_type="application/json",
        )


@timed_http("shutdown")
async def shutdown_handler(request: Request) -> PlainTextResponse:
    """Request graceful shutdown of the daemon.

    This endpoint triggers an orderly shutdown of all daemon services.
    Returns 202 Accepted immediately while shutdown proceeds in background.
    """
    # Only allow POST requests for safety
    if request.method != "POST":
        return PlainTextResponse(
            content=to_json({"error": "Method not allowed. Use POST."}),
            status_code=405,
            media_type="application/json",
        )

    # Request shutdown
    if ManagementServer.request_shutdown():
        logger.info("Shutdown requested via management API")
        return PlainTextResponse(
            content=to_json({"status": "shutdown_initiated", "message": "Daemon shutdown initiated"}),
            status_code=202,
            media_type="application/json",
        )
    else:
        return PlainTextResponse(
            content=to_json({"error": "Shutdown could not be initiated"}),
            status_code=500,
            media_type="application/json",
        )


class ManagementServer:
    """
    HTTP server for management endpoints.

    Always runs on HTTP (port 9329 default), independent of MCP transport.
    Provides observability endpoints for monitoring and debugging.

    Reuses existing endpoint handlers from app_bindings.py.
    """

    # Class-level shutdown event for coordinating graceful shutdown
    _shutdown_event: asyncio.Event | None = None
    _instance: "ManagementServer | None" = None

    def __init__(self, background_state: CodeWeaverState) -> None:
        """
        Initialize management server.

        Args:
            background_state: CodeWeaverState instance for accessing services
        """
        self.background_state = background_state
        self.server: uvicorn.Server | None = None
        self.server_task: asyncio.Task | None = None
        ManagementServer._instance = self
        ManagementServer._shutdown_event = asyncio.Event()

    @classmethod
    def get_instance(cls) -> "ManagementServer | None":
        """Get the current management server instance."""
        return cls._instance

    @classmethod
    def request_shutdown(cls) -> bool:
        """Request graceful shutdown of the daemon."""
        if cls._shutdown_event:
            cls._shutdown_event.set()
            return True
        return False

    @classmethod
    def is_shutdown_requested(cls) -> bool:
        """Check if shutdown has been requested."""
        return cls._shutdown_event is not None and cls._shutdown_event.is_set()

    def create_app(self) -> Starlette:
        """
        Create Starlette app with management routes.

        Routes are conditionally registered based on endpoint_settings
        (matching pattern from app_bindings.py).

        IMPORTANT: Reuses existing handlers from app_bindings.py.
        """
        from codeweaver.config.settings import get_settings_map

        settings_map = get_settings_map()
        endpoint_settings = settings_map.get("endpoints", {})

        routes = [
            # Always register favicon (browsers always request it)
            Route("/favicon.ico", favicon, methods=["GET"], include_in_schema=False),
            # these are always enabled because we use them internally
            Route("/health", health, methods=["GET"]),
            Route("/status", status_info, methods=["GET"]),
            Route("/metrics", stats_info, methods=["GET"]),
            # Shutdown endpoint for graceful daemon termination
            Route("/shutdown", shutdown_handler, methods=["POST"]),
        ]

        if endpoint_settings.get("enable_version", True):
            routes.append(Route("/version", version_info, methods=["GET"]))

        if endpoint_settings.get("enable_settings", True):
            routes.append(Route("/settings", settings_info, methods=["GET"]))

        if endpoint_settings.get("enable_state", True):
            routes.append(Route("/state", state_info, methods=["GET"]))

        app = Starlette(routes=routes)

        # Attach background state to app for handlers to access
        # Handlers use get_state() global
        app.state.background = self.background_state

        return app

    async def start(self, host: str = "127.0.0.1", port: int = 9329) -> None:
        """
        Start management server.

        Args:
            host: Server host (default: 127.0.0.1)
            port: Server port (default: 9329)
        """
        logger.info("Starting management server on %s:%d", host, port)

        app = self.create_app()

        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="warning",  # Quiet logs for management server
            access_log=False,  # Use our own logging via @timed_http
        )

        self.server = uvicorn.Server(config)

        # Run in background task
        self.server_task = asyncio.create_task(self.server.serve())

        logger.info("Management server ready at http://%s:%d", host, port)

    async def stop(self) -> None:
        """Stop management server gracefully."""
        if self.server:
            logger.info("Stopping management server")
            self.server.should_exit = True

            if self.server_task:
                try:
                    await asyncio.wait_for(self.server_task, timeout=5.0)
                except TimeoutError:
                    logger.warning("Management server did not stop within 5 seconds")

            logger.info("Management server stopped")


__all__ = (ManagementServer,)

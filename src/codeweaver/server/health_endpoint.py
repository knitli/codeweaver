# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Health endpoint implementation for FastMCP server."""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING, Any

from codeweaver.server.health_models import (
    EmbeddingProviderServiceInfo,
    HealthResponse,
    RerankerServiceInfo,
    SparseEmbeddingServiceInfo,
    VectorStoreServiceInfo,
)


if TYPE_CHECKING:
    from codeweaver.server.health_service import HealthService
    from codeweaver.server.server import get_state


logger = logging.getLogger(__name__)


async def get_health() -> HealthResponse | Any:
    """Health check endpoint returning server status and metrics.

    This endpoint provides comprehensive health information including:
    - Overall system status (healthy/degraded/unhealthy)
    - Indexing progress and state
    - Service health for vector store, embedding providers, reranker
    - Statistics on indexed content and query performance

    Implements FR-010-Enhanced schema for operational visibility.

    Args:
        ctx: FastMCP context with AppState

    Returns:
        HealthResponse with complete system health information
    """
    try:
        ctx = get_state()
        # Get health service from app state
        health_service: HealthService = ctx.health_service

        # Collect health information from all components
        health_response = await health_service.get_health_response()

        logger.debug(
            "Health check completed: status=%s, uptime=%ds",
            health_response.status,
            health_response.uptime_seconds,
        )

    except Exception as e:
        logger.error("Health check failed with error: %s", e, exc_info=True)
        # Return unhealthy status on error

        from codeweaver.server.health_models import (
            IndexingInfo,
            IndexingProgressInfo,
            ServicesInfo,
            StatisticsInfo,
        )

        return HealthResponse.create_with_current_timestamp(
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
                reranker=RerankerServiceInfo(status="down", model="unknown", latency_ms=0),
            ),
            statistics=StatisticsInfo(
                total_chunks_indexed=0,
                total_files_indexed=0,
                languages_indexed=[],
                index_size_mb=0,
                queries_processed=0,
                avg_query_latency_ms=0,
            ),
        )
    else:
        return health_response


__all__ = ("get_health",)

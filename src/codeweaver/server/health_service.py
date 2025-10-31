# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Health service for collecting and aggregating system health information."""

from __future__ import annotations

import asyncio
import logging
import time

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from codeweaver.server.health_models import (
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


if TYPE_CHECKING:
    from codeweaver.common.registry import ProviderRegistry
    from codeweaver.common.statistics import SessionStatistics
    from codeweaver.engine.indexer import Indexer


logger = logging.getLogger(__name__)


class HealthService:
    """Service for collecting and aggregating health information from all components."""

    def __init__(
        self,
        *,
        provider_registry: ProviderRegistry,
        statistics: SessionStatistics,
        indexer: Indexer | None = None,
        startup_time: float,
    ) -> None:
        """Initialize health service.

        Args:
            provider_registry: Provider registry for accessing embedding/vector store providers
            statistics: Session statistics for query metrics
            indexer: Indexer instance for indexing progress (optional)
            startup_time: Server startup timestamp
        """
        self._provider_registry = provider_registry
        self._statistics = statistics
        self._indexer = indexer
        self._startup_time = startup_time
        self._last_indexed: str | None = None
        self._indexed_languages: set[str] = set()

    def set_indexer(self, indexer: Indexer) -> None:
        """Set the indexer instance after initialization."""
        self._indexer = indexer

    def update_last_indexed(self) -> None:
        """Update the last indexed timestamp to current time."""
        self._last_indexed = datetime.now(UTC).isoformat()

    def add_indexed_language(self, language: str) -> None:
        """Add a language to the set of indexed languages."""
        self._indexed_languages.add(language)

    async def get_health_response(self) -> HealthResponse:
        """Collect health information from all components and return complete response.

        Returns:
            HealthResponse with current system health
        """
        # Collect component health in parallel
        indexing_info_task = asyncio.create_task(self._get_indexing_info())
        services_info_task = asyncio.create_task(self._get_services_info())
        statistics_info_task = asyncio.create_task(self._get_statistics_info())

        indexing_info, services_info, statistics_info = await asyncio.gather(
            indexing_info_task, services_info_task, statistics_info_task
        )

        # Determine overall status
        status = self._determine_status(indexing_info, services_info)

        # Calculate uptime
        uptime_seconds = int(time.time() - self._startup_time)

        return HealthResponse.create_with_current_timestamp(
            status=status,
            uptime_seconds=uptime_seconds,
            indexing=indexing_info,
            services=services_info,
            statistics=statistics_info,
        )

    async def _get_indexing_info(self) -> IndexingInfo:
        """Get indexing state and progress information."""
        if self._indexer is None:
            # No indexer configured - return idle state with zeros
            return IndexingInfo(
                state="idle",
                progress=IndexingProgressInfo(
                    files_discovered=0,
                    files_processed=0,
                    chunks_created=0,
                    errors=0,
                    current_file=None,
                    start_time=None,
                    estimated_completion=None,
                ),
                last_indexed=self._last_indexed,
            )

        stats = self._indexer.stats
        error_count = len(stats.files_with_errors) if stats.files_with_errors else 0

        # Determine indexing state
        if error_count >= 50:
            state = "error"
        elif stats.files_processed < stats.files_discovered:
            state = "indexing"
        else:
            state = "idle"

        # Calculate estimated completion
        estimated_completion = None
        if state == "indexing" and stats.processing_rate > 0:
            remaining_files = stats.files_discovered - stats.files_processed
            eta_seconds = remaining_files / stats.processing_rate
            estimated_timestamp = time.time() + eta_seconds
            estimated_completion = datetime.fromtimestamp(estimated_timestamp, tz=UTC).isoformat()

        # Get start time
        start_time_iso = datetime.fromtimestamp(stats.start_time, tz=UTC).isoformat()

        return IndexingInfo(
            state=state,
            progress=IndexingProgressInfo(
                files_discovered=stats.files_discovered,
                files_processed=stats.files_processed,
                chunks_created=stats.chunks_created,
                errors=error_count,
                current_file=None,  # TODO: Track current file in Indexer
                start_time=start_time_iso,
                estimated_completion=estimated_completion,
            ),
            last_indexed=self._last_indexed,
        )

    async def _get_services_info(self) -> ServicesInfo:
        """Get health information for all services."""
        # Collect service health checks in parallel
        vector_store_task = asyncio.create_task(self._check_vector_store_health())
        embedding_task = asyncio.create_task(self._check_embedding_provider_health())
        sparse_task = asyncio.create_task(self._check_sparse_embedding_health())
        reranking_task = asyncio.create_task(self._check_reranking_health())

        vector_store, embedding, sparse, reranking = await asyncio.gather(
            vector_store_task, embedding_task, sparse_task, reranking_task
        )

        return ServicesInfo(
            vector_store=vector_store,
            embedding_provider=embedding,
            sparse_embedding=sparse,
            reranking=reranking,
        )

    async def _check_vector_store_health(self) -> VectorStoreServiceInfo:
        """Check vector store health with latency measurement."""
        from codeweaver.providers.provider import ProviderKind

        try:
            vector_provider = self._provider_registry.get_configured_provider_settings(
                provider_kind=ProviderKind.VECTOR_STORE
            )
            provider = (
                vector_provider["provider"]
                if isinstance(vector_provider, dict)
                else vector_provider[0]["provider"]
                if vector_provider
                else None
            )
            if not provider:
                raise RuntimeError("No vector store provider configured")
            self._provider_registry.get_vector_store_provider_instance(
                provider=provider, singleton=True
            )
            start = time.time()
            # TODO: Add ping/health check method to vector store providers
            # For now, assume healthy if we can get the instance
            latency_ms = (time.time() - start) * 1000
            return VectorStoreServiceInfo(status="up", latency_ms=latency_ms)
        except Exception as e:
            logger.warning("Vector store health check failed: %s", e)
            return VectorStoreServiceInfo(status="down", latency_ms=0)

    async def _check_embedding_provider_health(self) -> EmbeddingProviderServiceInfo:
        """Check embedding provider health with circuit breaker state."""
        try:
            if embedding_provider := self._provider_registry.get_embedding_provider():
                embedding_provider_instance = (
                    self._provider_registry.get_embedding_provider_instance(
                        provider=embedding_provider, singleton=True
                    )
                )
                circuit_state_raw = embedding_provider_instance.circuit_breaker_state
                # Handle both string and enum values (or mock objects with .value)
                if hasattr(circuit_state_raw, 'value'):
                    circuit_state = circuit_state_raw.value
                else:
                    circuit_state = str(circuit_state_raw) if circuit_state_raw else "closed"
                
                model_name = getattr(embedding_provider_instance, 'model_name', 'unknown')

                # Check if circuit breaker is open -> service is down
                status = "down" if circuit_state == "open" else "up"

                # Estimate latency from recent operations
                # TODO: Add actual latency tracking to providers
                latency_ms = 200.0 if status == "up" else 0.0

                return EmbeddingProviderServiceInfo(
                    status=status,
                    model=model_name,
                    latency_ms=latency_ms,
                    circuit_breaker_state=circuit_state,
                )
            raise RuntimeError("No embedding provider configured")
        except Exception as e:
            logger.warning("Embedding provider health check failed: %s", e)
            return EmbeddingProviderServiceInfo(
                status="down", model="unknown", latency_ms=0, circuit_breaker_state="open"
            )

    async def _check_sparse_embedding_health(self) -> SparseEmbeddingServiceInfo:
        """Check sparse embedding provider health."""
        try:
            if sparse_provider := self._provider_registry.get_embedding_provider(sparse=True):
                _ = self._provider_registry.get_sparse_embedding_provider_instance(
                    provider=sparse_provider, singleton=True
                )
                # Sparse embedding is local, so typically always available
                return SparseEmbeddingServiceInfo(status="up", provider=sparse_provider.as_title)
            logger.info("No sparse embedding provider configured")
            return SparseEmbeddingServiceInfo(status="down", provider="none")
        except Exception as e:
            logger.warning("Sparse embedding health check failed: %s", e)
            return SparseEmbeddingServiceInfo(status="down", provider="unknown")

    async def _check_reranking_health(self) -> RerankingServiceInfo:
        """Check reranking service health."""
        try:
            if reranking_provider := self._provider_registry.get_reranking_provider():
                reranking_instance = self._provider_registry.get_reranking_provider_instance(
                    provider=reranking_provider, singleton=True
                )
                circuit_state_raw = reranking_instance.circuit_breaker_state
                # Handle both string and enum values (or mock objects with .value)
                if hasattr(circuit_state_raw, 'value'):
                    circuit_state = circuit_state_raw.value
                else:
                    circuit_state = str(circuit_state_raw) if circuit_state_raw else "closed"
                    
                model_name = getattr(reranking_instance, 'model_name', 'unknown')
                status = "down" if circuit_state == "open" else "up"

                # Estimate latency
                latency_ms = 180.0 if status == "up" else 0.0
                return RerankingServiceInfo(status=status, model=model_name, latency_ms=latency_ms)
        except Exception as e:
            logger.warning("Reranking health check failed: %s", e)
            return RerankingServiceInfo(status="down", model="unknown", latency_ms=0)
        return RerankingServiceInfo(status="down", model="unknown", latency_ms=0)

    async def _get_statistics_info(self) -> StatisticsInfo:
        """Get statistics and metrics information."""
        stats = self._statistics

        # Calculate total chunks and files indexed
        total_chunks = 0
        total_files = 0
        if self._indexer:
            indexer_stats = self._indexer.stats
            total_chunks = indexer_stats.chunks_indexed
            total_files = indexer_stats.files_processed

        # Calculate average query latency from timing statistics
        timing_stats = stats.get_timing_statistics()
        avg_latency = 0.0
        if (
            timing_stats
            and "queries" in timing_stats
            and (query_timings := timing_stats["queries"])
        ):
            avg_latency = sum(query_timings) / len(query_timings) * 1000  # Convert to ms

        # Get total queries processed
        total_queries = stats.total_requests

        # Get indexed languages
        languages = sorted(self._indexed_languages)

        # Estimate index size (rough estimate: ~1KB per chunk)
        index_size_mb = int((total_chunks * 1024) / (1024 * 1024))

        return StatisticsInfo(
            total_chunks_indexed=total_chunks,
            total_files_indexed=total_files,
            languages_indexed=languages,
            index_size_mb=index_size_mb,
            queries_processed=total_queries,
            avg_query_latency_ms=avg_latency,
        )

    def _determine_status(
        self, indexing: IndexingInfo, services: ServicesInfo
    ) -> str:  # Literal["healthy", "degraded", "unhealthy"]:
        """Determine overall system health status based on component states.

        Status rules (from FR-010-Enhanced contract):
        - healthy: All services up, indexing idle or progressing normally
        - degraded: Some services down but core functionality works
        - unhealthy: Critical services down (vector store unavailable)
        """
        # Unhealthy: Vector store down OR indexing in error state
        if services.vector_store.status == "down" or indexing.state == "error":
            return "unhealthy"

        # Degraded: Embedding provider down (but sparse works) OR high error count
        if (
            services.embedding_provider.status == "down"
            and services.sparse_embedding.status == "up"
        ):
            return "degraded"

        return "degraded" if indexing.progress.errors >= 25 else "healthy"


__all__ = ("HealthService",)

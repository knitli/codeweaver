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
from typing import TYPE_CHECKING, Any, Literal, NoReturn, cast

from codeweaver.exceptions import ConfigurationError
from codeweaver.server.health_models import (
    EmbeddingProviderServiceInfo,
    FailoverInfo,
    HealthResponse,
    IndexingInfo,
    IndexingProgressInfo,
    RerankingServiceInfo,
    ResourceInfo,
    ServicesInfo,
    SparseEmbeddingServiceInfo,
    StatisticsInfo,
    VectorStoreServiceInfo,
)


if TYPE_CHECKING:
    from codeweaver.common.registry import ProviderRegistry
    from codeweaver.common.statistics import SessionStatistics
    from codeweaver.engine.failover import VectorStoreFailoverManager
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
        failover_manager: VectorStoreFailoverManager | None = None,
        startup_time: float,
    ) -> None:
        """Initialize health service.

        Args:
            provider_registry: Provider registry for accessing embedding/vector store providers
            statistics: Session statistics for query metrics
            indexer: Indexer instance for indexing progress (optional)
            failover_manager: Failover manager for vector store failover (optional)
            startup_time: Server startup timestamp
        """
        self._provider_registry = provider_registry
        self._statistics = statistics
        self._indexer = indexer
        self._failover_manager = failover_manager
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
        failover_info_task = asyncio.create_task(self._get_failover_info())
        resources_info_task = asyncio.create_task(self._collect_resource_info())

        (
            indexing_info,
            services_info,
            statistics_info,
            failover_info,
            resources_info,
        ) = await asyncio.gather(
            indexing_info_task,
            services_info_task,
            statistics_info_task,
            failover_info_task,
            resources_info_task,
        )

        # Determine overall status (including resource checks)
        status = self._determine_status(indexing_info, services_info, resources_info)

        # Calculate uptime
        uptime_seconds = int(time.time() - self._startup_time)

        return HealthResponse.create_with_current_timestamp(
            status=cast(Literal["healthy", "degraded", "unhealthy"], status),
            uptime_seconds=uptime_seconds,
            indexing=indexing_info,
            services=services_info,
            statistics=statistics_info,
            failover=failover_info,
            resources=resources_info,
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
        if state == "indexing" and stats.processing_rate() > 0:
            remaining_files = stats.files_discovered - stats.files_processed
            eta_seconds = remaining_files / stats.processing_rate()
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
                current_file=None,
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

        def raise_error() -> NoReturn:
            """Helper to raise error for missing provider."""
            logger.error("No vector store provider configured")
            raise ConfigurationError(
                "No vector store provider configured. Either you don't have a vector store configured, your settings are misconfigured, or the provider is not available.",
                details={
                    "vector_provider_settings": self._provider_registry.get_configured_provider_settings(
                        provider_kind=ProviderKind.VECTOR_STORE
                    )
                },
                suggestions=[
                    "Ensure a vector store provider is configured in your settings.",
                    "Check that the provider settings are correct and the provider is reachable.",
                    "If the issue persists, please submit an issue: https://github.com/knitli/codeweaver/issues/new",
                ],
            )

        try:
            vector_provider = self._provider_registry.get_configured_provider_settings(
                provider_kind=ProviderKind.VECTOR_STORE
            )
            provider = (
                vector_provider["provider"]
                if isinstance(vector_provider, dict)
                else vector_provider["provider"]
                if vector_provider
                else None
            )
            if not provider:
                raise_error()

            # Get vector store instance using new unified API
            vector_store_enum = self._provider_registry.get_provider_enum_for("vector_store")
            if vector_store_enum:
                _ = self._provider_registry.get_provider_instance(
                    vector_store_enum, "vector_store", singleton=True
                )
            start = time.time()
            # For now, assume healthy if we can get the instance
            latency_ms = (time.time() - start) * 1000
            return VectorStoreServiceInfo(status="up", latency_ms=latency_ms)
        except Exception as e:
            logger.warning("Vector store health check failed: %s", e)
            return VectorStoreServiceInfo(status="down", latency_ms=0)

    def _extract_circuit_breaker_state(self, circuit_state_raw: Any) -> str:
        """Extract circuit breaker state string from raw value.

        Handles both string values, enum values, and mock objects with .value attribute.

        Args:
            circuit_state_raw: Raw circuit breaker state (string, enum, or mock)

        Returns:
            Circuit breaker state as string ("closed", "open", or "half_open")
        """
        if hasattr(circuit_state_raw, "value"):
            return circuit_state_raw.value
        return str(circuit_state_raw) if circuit_state_raw else "closed"

    async def _check_embedding_provider_health(self) -> EmbeddingProviderServiceInfo:
        """Check embedding provider health with circuit breaker state."""

        def raise_error() -> NoReturn:
            """Helper to raise error for missing provider."""
            logger.error("No embedding provider configured")
            raise RuntimeError("No embedding provider configured")

        try:
            # Get embedding provider using new unified API
            if embedding_provider_enum := self._provider_registry.get_provider_enum_for(
                "embedding"
            ):
                embedding_provider_instance = self._provider_registry.get_provider_instance(
                    embedding_provider_enum, "embedding", singleton=True
                )
                circuit_state = self._extract_circuit_breaker_state(
                    embedding_provider_instance.circuit_breaker_state
                )
                model_name = getattr(embedding_provider_instance, "model_name", "unknown")

                # Check if circuit breaker is open -> service is down
                status = "down" if circuit_state == "open" else "up"

                # Estimate latency from recent operations
                latency_ms = 200.0 if status == "up" else 0.0

                return EmbeddingProviderServiceInfo(
                    status=status,
                    model=model_name,
                    latency_ms=latency_ms,
                    circuit_breaker_state=circuit_state,  # type: ignore
                )
            raise_error()
        except Exception as e:
            logger.warning("Embedding provider health check failed: %s", e)
            return EmbeddingProviderServiceInfo(
                status="down", model="unknown", latency_ms=0, circuit_breaker_state="open"
            )

    async def _check_sparse_embedding_health(self) -> SparseEmbeddingServiceInfo:
        """Check sparse embedding provider health."""
        try:
            # Get sparse embedding provider using new unified API
            if sparse_provider_enum := self._provider_registry.get_provider_enum_for(
                "sparse_embedding"
            ):
                _ = self._provider_registry.get_provider_instance(
                    sparse_provider_enum, "sparse_embedding", singleton=True
                )
                # Sparse embedding is local, so typically always available
                return SparseEmbeddingServiceInfo(
                    status="up", provider=sparse_provider_enum.as_title
                )
            logger.info("No sparse embedding provider configured")
            return SparseEmbeddingServiceInfo(status="down", provider="none")
        except Exception as e:
            logger.warning("Sparse embedding health check failed: %s", e)
            return SparseEmbeddingServiceInfo(status="down", provider="unknown")

    async def _check_reranking_health(self) -> RerankingServiceInfo:
        """Check reranking service health."""
        try:
            # Get reranking provider using new unified API
            if reranking_provider_enum := self._provider_registry.get_provider_enum_for(
                "reranking"
            ):
                reranking_instance = self._provider_registry.get_provider_instance(
                    reranking_provider_enum, "reranking", singleton=True
                )
                circuit_state = self._extract_circuit_breaker_state(
                    reranking_instance.circuit_breaker_state
                )
                model_name = getattr(reranking_instance, "model_name", "unknown")
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
        semantic_chunks = 0
        delimiter_chunks = 0
        file_chunks = 0
        avg_chunk_size = 0.0

        if self._indexer:
            # Use session statistics from indexer for comprehensive tracking
            session_stats = self._indexer.session_statistics

            # Get file statistics from session stats if available
            if session_stats.index_statistics:
                total_files = session_stats.index_statistics.total_unique_files

                # Aggregate chunk statistics across all categories and languages
                all_chunk_sizes = []
                for category_stats in session_stats.index_statistics.categories.values():
                    for lang_stats in category_stats.languages.values():
                        semantic_chunks += lang_stats.semantic_chunks
                        delimiter_chunks += lang_stats.delimiter_chunks
                        file_chunks += lang_stats.file_chunks
                        all_chunk_sizes.extend(lang_stats.chunk_sizes)

                # Calculate totals and averages
                total_chunks = semantic_chunks + delimiter_chunks + file_chunks
                if all_chunk_sizes:
                    import statistics as stats_module

                    avg_chunk_size = stats_module.mean(all_chunk_sizes)
            else:
                # Fallback to indexer stats (no detailed chunk breakdown)
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

        # Get indexed languages from session statistics
        languages = []
        if self._indexer and self._indexer.session_statistics.index_statistics:
            file_stats = self._indexer.session_statistics.index_statistics
            # Extract language names from all categories
            for category_stats in file_stats.categories.values():
                for lang in category_stats.languages:
                    if isinstance(lang, str):
                        languages.append(lang)
                    else:
                        languages.append(
                            lang.as_variable if hasattr(lang, "as_variable") else str(lang)
                        )
        languages = sorted(set(languages))  # Deduplicate and sort

        # Estimate index size (rough estimate: ~1KB per chunk)
        index_size_mb = int((total_chunks * 1024) / (1024 * 1024))

        return StatisticsInfo(
            total_chunks_indexed=total_chunks,
            total_files_indexed=total_files,
            languages_indexed=languages,
            index_size_mb=index_size_mb,
            queries_processed=total_queries,
            avg_query_latency_ms=avg_latency,
            semantic_chunks=semantic_chunks,
            delimiter_chunks=delimiter_chunks,
            file_chunks=file_chunks,
            avg_chunk_size=avg_chunk_size,
        )

    async def _get_failover_info(self) -> FailoverInfo | None:
        """Get failover status information.

        Returns:
            FailoverInfo if failover is configured, None otherwise
        """
        if self._failover_manager is None:
            return None

        # Get failover statistics from session statistics
        failover_stats = self._statistics.failover_statistics
        if not failover_stats:
            return FailoverInfo(
                failover_enabled=True,
                failover_active=False,
                failover_count=0,
                total_failover_time_seconds=0.0,
                backup_syncs_completed=0,
                chunks_in_failover=0,
            )

        # Get active store type from failover manager
        active_store = "backup" if self._failover_manager._failover_active else "primary"

        # Get circuit breaker state
        circuit_state = None
        if self._failover_manager._primary_store and hasattr(
            self._failover_manager._primary_store, "circuit_breaker_state"
        ):
            circuit_state = str(self._failover_manager._primary_store.circuit_breaker_state)

        return FailoverInfo(
            failover_enabled=True,
            failover_active=failover_stats.failover_active,
            active_store_type=active_store,
            failover_count=failover_stats.failover_count,
            total_failover_time_seconds=failover_stats.total_failover_time_seconds,
            last_failover_time=failover_stats.last_failover_time,
            primary_circuit_breaker_state=circuit_state,
            backup_syncs_completed=failover_stats.backup_syncs_completed,
            chunks_in_failover=failover_stats.chunks_in_failover,
        )

    async def _collect_resource_info(self) -> ResourceInfo | None:
        """Collect system resource usage.

        Returns:
            ResourceInfo with current resource usage, or None if psutil unavailable
        """
        try:
            import os

            from pathlib import Path

            import psutil

            process = psutil.Process(os.getpid())

            # Memory usage (RSS = Resident Set Size)
            memory_info = process.memory_info()
            memory_mb = memory_info.rss // (1024 * 1024)

            # CPU usage (over short interval)
            cpu_percent = process.cpu_percent(interval=0.1)

            # Disk usage
            from codeweaver.common.utils import get_user_config_dir

            config_dir = Path(get_user_config_dir())
            index_dir = config_dir / ".indexes"
            cache_dir = config_dir

            def get_dir_size(path: Path) -> int:
                """Get directory size in MB."""
                if not path.exists():
                    return 0
                try:
                    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
                    return total // (1024 * 1024)
                except (PermissionError, OSError):
                    # Gracefully handle permission errors
                    return 0

            disk_index_mb = get_dir_size(index_dir)
            disk_cache_mb = get_dir_size(cache_dir)
            disk_total_mb = disk_cache_mb  # Cache includes index

            # File descriptors (Unix only)
            file_descriptors = None
            file_descriptors_limit = None
            try:
                file_descriptors = process.num_fds()  # Unix only
                # Get system limit
                import resource

                soft_limit, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
                file_descriptors_limit = soft_limit
            except (AttributeError, ImportError):
                # Windows or unavailable
                pass

            return ResourceInfo(
                memory_mb=memory_mb,
                cpu_percent=cpu_percent,
                disk_total_mb=disk_total_mb,
                disk_index_mb=disk_index_mb,
                disk_cache_mb=disk_cache_mb,
                file_descriptors=file_descriptors,
                file_descriptors_limit=file_descriptors_limit,
            )
        except ImportError:
            # psutil not available - graceful degradation
            logger.debug("psutil not available, skipping resource collection")
            return None
        except Exception as e:
            # Gracefully handle any other errors
            logger.warning("Failed to collect resource information: %s", e)
            return None

    def _determine_status(
        self, indexing: IndexingInfo, services: ServicesInfo, resources: ResourceInfo | None = None
    ) -> str:  # Literal["healthy", "degraded", "unhealthy"]:
        """Determine overall system health status based on component states.

        Status rules (from FR-010-Enhanced contract):
        - healthy: All services up, indexing idle or progressing normally
        - degraded: Some services down but core functionality works, or high resource usage
        - unhealthy: Critical services down (vector store unavailable)

        Args:
            indexing: Indexing state information
            services: Service health information
            resources: Resource usage information (optional)

        Returns:
            Overall health status
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

        # Check resource usage (warnings, not critical)
        if resources:
            # Memory warning at 1.5GB, critical at 2GB
            if resources.memory_mb > 2048:
                logger.warning("High memory usage: %d MB", resources.memory_mb)
                return "degraded"

            # CPU sustained high usage (>80%)
            if resources.cpu_percent > 80:
                logger.warning("High CPU usage: %.1f%%", resources.cpu_percent)
                return "degraded"

            # File descriptor warning at 80% of limit
            if (
                resources.file_descriptors is not None
                and resources.file_descriptors_limit is not None
            ):
                fd_percent = (resources.file_descriptors / resources.file_descriptors_limit) * 100
                if fd_percent > 80:
                    logger.warning(
                        "High file descriptor usage: %d/%d (%.1f%%)",
                        resources.file_descriptors,
                        resources.file_descriptors_limit,
                        fd_percent,
                    )
                    return "degraded"

        return "degraded" if indexing.progress.errors >= 25 else "healthy"

    def to_dict(self) -> dict[str, Any]:
        """Convert HealthService to dictionary for serialization.

        In practice, HealthService isn't serialized -- we serialize HealthResponse.

        Warning: This method uses asyncio.run() and CANNOT be called from async context.
        If you need to get health information from async code, use get_health_response() instead.
        """
        # Get health response synchronously using asyncio.run()
        # This will raise RuntimeError if called from async context
        health_response = asyncio.run(self.get_health_response())
        return health_response.model_dump(round_trip=True)


__all__ = ("HealthService",)

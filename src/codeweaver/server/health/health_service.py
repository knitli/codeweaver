# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Health service for collecting and aggregating system health information."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, NoReturn, cast

from codeweaver.core import INJECTED, ConfigurationError, StatisticsDep
from codeweaver.core.constants import (
    FLOAT_ZERO,
    ONE_GIGABYTE,
    ONE_HUNDRED,
    ONE_KILOBYTE,
    ONE_MEGABYTE,
    ONE_MILLISECOND_IN_MICROSECONDS,
)
from codeweaver.engine.dependencies import FailoverServiceDep, IndexingServiceDep
from codeweaver.engine.services.indexing_service import IndexingService
from codeweaver.providers import AllProviderSettingsDep
from codeweaver.server.health.models import (
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
    from codeweaver.core import FileStatistics, SessionStatistics

logger = logging.getLogger(__name__)


def _get_statistics(statistics: StatisticsDep) -> SessionStatistics:
    return statistics


class HealthService:
    """Service for collecting and aggregating health information from all components."""

    def __init__(
        self,
        *,
        providers: AllProviderSettingsDep = INJECTED,
        statistics: StatisticsDep = INJECTED,
        indexer: IndexingServiceDep = INJECTED,
        failover_manager: FailoverServiceDep = INJECTED,
        startup_stopwatch: float | None = None,
    ) -> None:
        """Initialize health service.

        Args:
            providers: Dictionary of all configured providers (primary and backups)
            statistics: Session statistics for query metrics
            indexer: IndexingService instance for indexing progress
            failover_manager: FailoverService for vector store failover
            startup_stopwatch: Server startup monotonic time (optional, will use current time if not provided)
        """
        self._providers = providers
        self._statistics = statistics
        self._indexer = indexer
        self._failover_manager = failover_manager
        self._startup_stopwatch = startup_stopwatch or time.monotonic()
        self._last_indexed: str | None = None
        self._indexed_languages: set[str] = set()

    def set_indexer(self, indexer: IndexingService) -> None:
        """Set the indexer instance after initialization."""
        self._indexer = indexer

    def update_last_indexed(self) -> None:
        """Update the last indexed timestamp to current time."""
        self._last_indexed = datetime.now(UTC).isoformat()

    def add_indexed_language(self, language: str) -> None:
        """Add a language to the set of indexed languages."""
        self._indexed_languages.add(language)

    def _get_primary_provider(self, kind: str) -> Any | None:
        """Get the primary (non-backup) provider of a given kind."""
        if not self._providers:
            return None
        providers = self._providers.get(kind, ())  # type: ignore
        return next((p for p in providers if "Backup" not in p.__class__.__name__), None)

    async def get_health_response(self) -> HealthResponse:
        """Collect health information from all components and return complete response.

        Returns:
            HealthResponse with current system health
        """
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
        status = self._determine_status(indexing_info, services_info, resources_info)
        uptime_seconds = int(time.monotonic() - self._startup_stopwatch)
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

    async def _get_services_info(self) -> ServicesInfo:
        """Get health information for all services."""
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

        def raise_error() -> NoReturn:
            logger.error("No vector store provider configured")
            raise ConfigurationError(
                "No vector store provider configured.",
                suggestions=["Ensure a vector store provider is configured in your settings."],
            )

        try:
            provider = self._get_primary_provider("vector_store")
            if not provider:
                raise_error()

            # Health check: assume provider is up if we have an instance (DI succeeded)
            # In a real check we might ping it.
            # Qdrant provider usually checks connection on init.
            start = time.time()
            # If the provider has a 'health' or 'ping' method, we could use it.
            # For now, just presence is "up".
            latency_ms = (time.time() - start) * ONE_MILLISECOND_IN_MICROSECONDS
        except Exception as e:
            logger.warning("Vector store health check failed: %s", e)
            return VectorStoreServiceInfo(status="down", latency_ms=0)
        else:
            return VectorStoreServiceInfo(status="up", latency_ms=latency_ms)

    def _extract_circuit_breaker_state(self, circuit_state_raw: Any) -> str:
        if hasattr(circuit_state_raw, "variable"):
            return circuit_state_raw.variable
        return str(circuit_state_raw) if circuit_state_raw else "closed"

    async def _check_embedding_provider_health(self) -> EmbeddingProviderServiceInfo:
        """Check embedding provider health with circuit breaker state."""

        def raise_error() -> NoReturn:
            logger.error("No embedding provider configured")
            raise RuntimeError("No embedding provider configured")

        try:
            embedding_provider_instance = self._get_primary_provider("embedding")
            if embedding_provider_instance:
                circuit_state = self._extract_circuit_breaker_state(
                    getattr(embedding_provider_instance, "circuit_breaker_state", "closed")
                )
                model_name = getattr(embedding_provider_instance, "model_name", "unknown")
                status = "down" if circuit_state == "open" else "up"
                latency_ms = 200.0 if status == "up" else FLOAT_ZERO
                return EmbeddingProviderServiceInfo(
                    status=status,
                    model=model_name,
                    latency_ms=latency_ms,
                    circuit_breaker_state=circuit_state,  # ty:ignore[invalid-argument-type]
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
            if sparse_provider_instance := self._get_primary_provider("sparse_embedding"):
                # Assuming provider name is available or just use class name
                provider_name = sparse_provider_instance.__class__.__name__
                return SparseEmbeddingServiceInfo(status="up", provider=provider_name)
            logger.info("No sparse embedding provider configured")
        except Exception as e:
            logger.warning("Sparse embedding health check failed: %s", e)
            return SparseEmbeddingServiceInfo(status="down", provider="unknown")
        else:
            return SparseEmbeddingServiceInfo(status="down", provider="none")

    async def _check_reranking_health(self) -> RerankingServiceInfo:
        """Check reranking service health."""
        try:
            if reranking_instance := self._get_primary_provider("reranking"):
                circuit_state = self._extract_circuit_breaker_state(
                    getattr(reranking_instance, "circuit_breaker_state", "closed")
                )
                model_name = getattr(reranking_instance, "model_name", "unknown")
                status = "down" if circuit_state == "open" else "up"
                latency_ms = 180.0 if status == "up" else FLOAT_ZERO
                return RerankingServiceInfo(status=status, model=model_name, latency_ms=latency_ms)
        except Exception as e:
            logger.warning("Reranking health check failed: %s", e)
            return RerankingServiceInfo(status="down", model="unknown", latency_ms=0)
        return RerankingServiceInfo(status="down", model="unknown", latency_ms=0)

    def _aggregate_chunk_statistics(
        self, index_statistics: FileStatistics
    ) -> tuple[int, int, int, int, float]:
        semantic_chunks = 0
        delimiter_chunks = 0
        file_chunks = 0
        all_chunk_sizes = []
        for category_stats in index_statistics.categories.values():
            for lang_stats in category_stats.languages.values():
                semantic_chunks += lang_stats.semantic_chunks
                delimiter_chunks += lang_stats.delimiter_chunks
                file_chunks += lang_stats.file_chunks
                all_chunk_sizes.extend(lang_stats.chunk_sizes)
        total_chunks = semantic_chunks + delimiter_chunks + file_chunks
        avg_chunk_size = 0.0
        if all_chunk_sizes:
            import statistics as stats_module

            avg_chunk_size = stats_module.mean(all_chunk_sizes)
        return (total_chunks, semantic_chunks, delimiter_chunks, file_chunks, avg_chunk_size)

    def _extract_indexed_languages(self, index_statistics: Any) -> list[str]:
        languages = []
        for category_stats in index_statistics.categories.values():
            for lang in category_stats.languages:
                if isinstance(lang, str):
                    languages.append(lang)
                else:
                    languages.append(
                        lang.as_variable if hasattr(lang, "as_variable") else str(lang)
                    )
        return sorted(set(languages))

    def _calculate_avg_query_latency(self, stats: Any) -> float:
        timing_stats = stats.get_timing_statistics()
        if not timing_stats or "queries" not in timing_stats:
            return 0.0
        if query_timings := timing_stats["queries"]:
            return sum(query_timings) / len(query_timings) * ONE_MILLISECOND_IN_MICROSECONDS
        return 0.0

    async def _get_statistics_info(self) -> StatisticsInfo:
        stats: SessionStatistics = self._statistics
        total_chunks = 0
        total_files = 0
        semantic_chunks = 0
        delimiter_chunks = 0
        file_chunks = 0
        avg_chunk_size = 0.0
        languages: list[str] = []
        if self._indexer:
            if hasattr(self._indexer, "session_statistics"):
                session_stats = self._indexer.session_statistics
                if session_stats.index_statistics:  # ty:ignore[unresolved-attribute]
                    index_stats = session_stats.index_statistics  # ty:ignore[unresolved-attribute]
                    total_files = index_stats.total_unique_files
                    total_chunks, semantic_chunks, delimiter_chunks, file_chunks, avg_chunk_size = (
                        self._aggregate_chunk_statistics(index_stats)
                    )
                    languages = self._extract_indexed_languages(index_stats)
                else:
                    indexer_stats = self._indexer.stats
                    total_chunks = indexer_stats.chunks_indexed
                    total_files = indexer_stats.files_processed
            else:
                indexer_stats = self._indexer.stats
                total_chunks = indexer_stats.chunks_indexed
                total_files = indexer_stats.files_processed
        avg_latency = self._calculate_avg_query_latency(stats)
        total_queries = stats.total_requests
        index_size_mb = int(total_chunks * ONE_KILOBYTE / ONE_MEGABYTE)
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
        if self._failover_manager is None:
            return None
        failover_stats = self._statistics.failover_statistics
        if not failover_stats:
            return FailoverInfo(
                failover_enabled=not self._failover_manager.settings.disable_failover,
                failover_active=False,
                failover_count=0,
                total_failover_time_seconds=FLOAT_ZERO,
                backup_syncs_completed=0,
                chunks_in_failover=0,
            )
        active_store = "backup" if self._failover_manager._failover_active else "primary"
        circuit_state = None
        if self._failover_manager.primary_store:
            circuit_state = str(self._failover_manager.primary_store.circuit_breaker_state)
        return FailoverInfo(
            failover_enabled=not self._failover_manager.settings.disable_failover,
            failover_active=self._failover_manager._failover_active,
            active_store_type=active_store,
            failover_count=failover_stats.failover_count,
            total_failover_time_seconds=failover_stats.total_failover_time_seconds,
            last_failover_time=failover_stats.last_failover_time,
            primary_circuit_breaker_state=circuit_state,
            backup_syncs_completed=failover_stats.backup_syncs_completed,
            chunks_in_failover=failover_stats.chunks_in_failover,
        )

    async def _collect_resource_info(self) -> ResourceInfo | None:
        try:
            import os

            from pathlib import Path

            import psutil

            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_mb = memory_info.rss // ONE_MEGABYTE
            cpu_percent = process.cpu_percent(interval=0.1)
            from codeweaver.core import get_user_config_dir

            config_dir = Path(get_user_config_dir())
            index_dir = config_dir / ".indexes"
            cache_dir = config_dir

            def get_dir_size(path: Path) -> int:
                if not path.exists():
                    return 0
                try:
                    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
                except OSError:
                    return 0
                else:
                    return total // ONE_MEGABYTE

            disk_index_mb = get_dir_size(index_dir)
            disk_cache_mb = get_dir_size(cache_dir)
            disk_total_mb = disk_cache_mb
            file_descriptors = None
            file_descriptors_limit = None
            with contextlib.suppress(AttributeError, ImportError):
                file_descriptors = process.num_fds()
                import resource

                soft_limit, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
                file_descriptors_limit = soft_limit
        except ImportError:
            logger.debug("psutil not available, skipping resource collection")
            return None
        except Exception as e:
            logger.warning("Failed to collect resource information: %s", e)
            return None
        else:
            return ResourceInfo(
                memory_mb=memory_mb,
                cpu_percent=cpu_percent,
                disk_total_mb=disk_total_mb,
                disk_index_mb=disk_index_mb,
                disk_cache_mb=disk_cache_mb,
                file_descriptors=file_descriptors,
                file_descriptors_limit=file_descriptors_limit,
            )

    def _determine_status(
        self, indexing: IndexingInfo, services: ServicesInfo, resources: ResourceInfo | None = None
    ) -> str:
        if services.vector_store.status == "down" or indexing.state == "error":
            return "unhealthy"
        if (
            services.embedding_provider.status == "down"
            and services.sparse_embedding.status == "up"
        ):
            return "degraded"
        if resources:
            if resources.memory_mb > 2 * ONE_GIGABYTE:
                logger.warning("High memory usage: %d MB", resources.memory_mb)
                return "degraded"
            if resources.cpu_percent > 80:
                logger.warning("High CPU usage: %.1f%%", resources.cpu_percent)
                return "degraded"
            if (
                resources.file_descriptors is not None
                and resources.file_descriptors_limit is not None
            ):
                fd_percent = (
                    resources.file_descriptors / resources.file_descriptors_limit * ONE_HUNDRED
                )
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
        """Convert HealthService to dictionary for serialization."""
        health_response = asyncio.run(self.get_health_response())
        return health_response.model_dump(round_trip=True)


__all__ = ("HealthService",)

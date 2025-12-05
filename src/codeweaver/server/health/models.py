# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Data models for the enhanced health endpoint (FR-010-Enhanced)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import Field, NonNegativeInt
from pydantic.types import NonNegativeFloat

from codeweaver.core.types import BasedModel
from codeweaver.core.types.aliases import FilteredKey
from codeweaver.core.types.enum import AnonymityConversion


class IndexingProgressInfo(BasedModel):
    """Indexing progress details."""

    files_discovered: Annotated[NonNegativeInt, Field(description="Total files discovered")] = 0
    files_processed: Annotated[NonNegativeInt, Field(description="Files processed so far")] = 0
    chunks_created: Annotated[NonNegativeInt, Field(description="Total chunks created")] = 0
    errors: Annotated[NonNegativeInt, Field(description="Number of errors during indexing")] = 0
    current_file: Annotated[
        str | None, Field(description="Currently processing file (if indexing)")
    ] = None
    start_time: Annotated[str | None, Field(description="Indexing start timestamp (ISO8601)")] = (
        None
    )
    estimated_completion: Annotated[
        str | None, Field(description="Estimated completion time (ISO8601)")
    ] = None

    def _telemetry_keys(self) -> dict[FilteredKey, AnonymityConversion]:
        return {FilteredKey("current_file"): AnonymityConversion.HASH}


class IndexingInfo(BasedModel):
    """Indexing state and progress information."""

    state: Annotated[
        Literal["idle", "indexing", "error"], Field(description="Current indexing state")
    ]
    progress: Annotated[IndexingProgressInfo, Field(description="Indexing progress details")]
    last_indexed: Annotated[
        str | None, Field(description="Last successful indexing completion (ISO8601)")
    ] = None

    def _telemetry_keys(self) -> None:
        return None


class VectorStoreServiceInfo(BasedModel):
    """Vector store service health information."""

    status: Annotated[Literal["up", "down", "degraded"], Field(description="Vector store status")]
    latency_ms: Annotated[NonNegativeFloat, Field(ge=0, description="Latency in milliseconds")]

    def _telemetry_keys(self) -> None:
        return None


class EmbeddingProviderServiceInfo(BasedModel):
    """Embedding provider service health information."""

    status: Annotated[Literal["up", "down"], Field(description="Embedding provider status")]
    model: Annotated[str, Field(description="Embedding model name")]
    latency_ms: Annotated[float, Field(ge=0, description="Latency in milliseconds")]
    circuit_breaker_state: Annotated[
        Literal["closed", "open", "half_open"], Field(description="Circuit breaker state")
    ]

    def _telemetry_keys(self) -> None:
        return None


class SparseEmbeddingServiceInfo(BasedModel):
    """Sparse embedding service health information."""

    status: Annotated[Literal["up", "down"], Field(description="Sparse embedding status")]
    provider: Annotated[str, Field(description="Sparse embedding provider name")]

    def _telemetry_keys(self) -> None:
        return None


class RerankingServiceInfo(BasedModel):
    """Reranking service health information."""

    status: Annotated[Literal["up", "down"], Field(description="Reranking status")]
    model: Annotated[str, Field(description="Reranking model name")]
    latency_ms: Annotated[float, Field(ge=0, description="Latency in milliseconds")]

    def _telemetry_keys(self) -> None:
        return None


class ServicesInfo(BasedModel):
    """Health information for all services."""

    vector_store: Annotated[VectorStoreServiceInfo, Field(description="Vector store health")]
    embedding_provider: Annotated[
        EmbeddingProviderServiceInfo, Field(description="Embedding provider health")
    ]
    sparse_embedding: Annotated[
        SparseEmbeddingServiceInfo, Field(description="Sparse embedding health")
    ]
    reranking: Annotated[RerankingServiceInfo, Field(description="Reranking health")]

    def _telemetry_keys(self) -> None:
        return None


class StatisticsInfo(BasedModel):
    """Statistics and metrics information."""

    total_chunks_indexed: Annotated[NonNegativeInt, Field(description="Total chunks indexed")]
    total_files_indexed: Annotated[NonNegativeInt, Field(description="Total files indexed")]
    languages_indexed: Annotated[
        list[str], Field(default_factory=list, description="Languages indexed")
    ]
    index_size_mb: Annotated[
        NonNegativeInt, Field(default=0, description="Index size in megabytes")
    ]
    queries_processed: Annotated[NonNegativeInt, Field(description="Total queries processed")]
    avg_query_latency_ms: Annotated[
        float, Field(ge=0, description="Average query latency in milliseconds")
    ]

    # Chunk statistics
    semantic_chunks: Annotated[
        NonNegativeInt, Field(default=0, description="Number of AST/semantic chunks created")
    ]
    delimiter_chunks: Annotated[
        NonNegativeInt,
        Field(default=0, description="Number of delimiter/text-block chunks created"),
    ]
    file_chunks: Annotated[
        NonNegativeInt, Field(default=0, description="Number of whole-file chunks created")
    ]
    avg_chunk_size: Annotated[
        float, Field(ge=0, default=0.0, description="Average chunk size in characters")
    ]

    def _telemetry_keys(self) -> None:
        return None


class FailoverInfo(BasedModel):
    """Failover status and statistics information."""

    failover_enabled: Annotated[bool, Field(description="Whether failover is enabled")]
    failover_active: Annotated[bool, Field(description="Whether failover is currently active")]
    active_store_type: Annotated[
        str | None, Field(description="Currently active store type (primary/backup)")
    ] = None
    failover_count: Annotated[
        NonNegativeInt, Field(default=0, description="Total number of failover activations")
    ]
    total_failover_time_seconds: Annotated[
        NonNegativeFloat, Field(ge=0, default=0.0, description="Total time spent in failover")
    ]
    last_failover_time: Annotated[
        str | None, Field(description="Last failover activation time (ISO8601)")
    ] = None
    primary_circuit_breaker_state: Annotated[
        str | None, Field(description="Primary vector store circuit breaker state")
    ] = None
    backup_syncs_completed: Annotated[
        NonNegativeInt, Field(default=0, description="Number of backup syncs completed")
    ]
    chunks_in_failover: Annotated[
        NonNegativeInt, Field(default=0, description="Number of chunks currently in failover")
    ]

    def _telemetry_keys(self) -> None:
        return None


class ResourceInfo(BasedModel):
    """System resource usage information."""

    memory_mb: Annotated[NonNegativeInt, Field(description="Current memory usage in MB")]
    cpu_percent: Annotated[
        NonNegativeFloat, Field(ge=0, description="Current CPU usage percentage")
    ]
    disk_total_mb: Annotated[NonNegativeInt, Field(description="Total disk usage in MB")]
    disk_index_mb: Annotated[NonNegativeInt, Field(description="Disk usage for index in MB")]
    disk_cache_mb: Annotated[NonNegativeInt, Field(description="Disk usage for cache in MB")]
    file_descriptors: Annotated[
        int | None, Field(description="Open file descriptors (if available)")
    ] = None
    file_descriptors_limit: Annotated[
        int | None, Field(description="File descriptor limit (if available)")
    ] = None

    def _telemetry_keys(self) -> None:
        return None


class HealthResponse(BasedModel):
    """Represents the health of CodeWeaver and its components."""

    status: Annotated[
        Literal["healthy", "degraded", "unhealthy"], Field(description="Overall system health")
    ]

    indexing: Annotated[IndexingInfo, Field(description="Indexing state and progress")]
    services: Annotated[ServicesInfo, Field(description="Service health information")]
    statistics: Annotated[StatisticsInfo, Field(description="Statistics and metrics")]
    uptime_seconds: Annotated[NonNegativeInt, Field(description="Server uptime in seconds")] = 0
    failover: Annotated[
        FailoverInfo | None, Field(description="Failover status and statistics")
    ] = None
    resources: Annotated[
        ResourceInfo | None, Field(description="System resource usage information")
    ] = None
    timestamp: str = Field(
        description="Health check timestamp (ISO8601)",
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )

    @classmethod
    def create_with_current_timestamp(
        cls,
        status: Literal["healthy", "degraded", "unhealthy"],
        uptime_seconds: int,
        indexing: IndexingInfo,
        services: ServicesInfo,
        statistics: StatisticsInfo,
        failover: FailoverInfo | None = None,
        resources: ResourceInfo | None = None,
    ) -> HealthResponse:
        """Create health response with current timestamp."""
        return cls(
            status=status,
            uptime_seconds=uptime_seconds,
            indexing=indexing,
            services=services,
            statistics=statistics,
            failover=failover,
            resources=resources,
        )

    def _telemetry_keys(self) -> None:
        return None


__all__ = (
    "EmbeddingProviderServiceInfo",
    "FailoverInfo",
    "HealthResponse",
    "IndexingInfo",
    "IndexingProgressInfo",
    "RerankingServiceInfo",
    "ResourceInfo",
    "ServicesInfo",
    "SparseEmbeddingServiceInfo",
    "StatisticsInfo",
    "VectorStoreServiceInfo",
)

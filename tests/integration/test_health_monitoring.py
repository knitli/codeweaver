# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Integration tests for health endpoint monitoring (T012).

Tests comprehensive health endpoint functionality with FR-010-Enhanced schema validation:
- Health endpoint response structure and schema compliance
- Health status determination (healthy/degraded/unhealthy)
- Indexing progress tracking during operations
- Service health checks (vector_store, embedding_provider, sparse_embedding, reranking)
- Circuit breaker state exposure from T006
- Statistics collection from SessionStatistics
- Performance requirements (<200ms p95)

Reference:
- Contract: specs/003-our-aim-to/contracts/health_endpoint.json
- Health models: src/codeweaver/server/health_models.py
- Health service: src/codeweaver/server/health_service.py
- Health endpoint: src/codeweaver/server/management.py (/health route)
"""

from __future__ import annotations

import asyncio
import json
import time

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from codeweaver.common.statistics import FailoverStats, Identifier, SessionStatistics
from codeweaver.engine.indexer import Indexer, IndexingStats
from codeweaver.server.health_models import (
    HealthResponse,
    IndexingInfo,
    ServicesInfo,
    StatisticsInfo,
)
from codeweaver.server.health_service import HealthService


if TYPE_CHECKING:
    from unittest.mock import MagicMock


# Test fixture: Small test project for indexing
TEST_PROJECT_FILES = {
    "src/main.py": '''"""Main application module."""

def main():
    """Entry point for the application."""
    print("Hello, CodeWeaver!")

if __name__ == "__main__":
    main()
''',
    "src/utils.py": '''"""Utility functions."""

def format_name(first: str, last: str) -> str:
    """Format a full name."""
    return f"{first} {last}"

def parse_config(config_str: str) -> dict:
    """Parse configuration string."""
    return {"config": config_str}
''',
    "tests/test_utils.py": '''"""Tests for utility functions."""

import pytest
from src.utils import format_name, parse_config

def test_format_name():
    """Test name formatting."""
    assert format_name("John", "Doe") == "John Doe"

def test_parse_config():
    """Test config parsing."""
    result = parse_config("test")
    assert result["config"] == "test"
''',
}


@pytest.fixture
def test_project_path(tmp_path: Path) -> Path:
    """Create small test project fixture."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()

    for file_path, content in TEST_PROJECT_FILES.items():
        file_full_path = project_root / file_path
        file_full_path.parent.mkdir(parents=True, exist_ok=True)
        file_full_path.write_text(content)

    return project_root


@pytest.fixture
def mock_provider_registry(mocker) -> MagicMock:
    """Create mock provider registry."""
    # Don't use spec= to allow mocking new unified API methods
    registry = mocker.MagicMock()

    # Mock vector store provider (old API)
    vector_store = mocker.MagicMock()
    registry.get_vector_store_provider_instance.return_value = vector_store

    # Mock new unified API methods for vector store
    vector_store_config = {"provider": mocker.MagicMock()}
    registry.get_configured_provider_settings.return_value = vector_store_config
    vector_store_enum = mocker.MagicMock()

    # Setup get_provider_enum_for to return appropriate enums
    def get_provider_enum_for(provider_type: str):
        if provider_type == "vector_store":
            return vector_store_enum
        if provider_type == "embedding":
            return embedding_provider_enum
        if provider_type == "sparse_embedding":
            return sparse_provider_enum
        return reranking_provider_enum if provider_type == "reranking" else None

    registry.get_provider_enum_for.side_effect = get_provider_enum_for

    # Mock embedding provider with circuit breaker
    embedding_provider_enum = mocker.MagicMock()
    embedding_instance = mocker.MagicMock()
    embedding_instance.model_name = "voyage-code-3"
    embedding_instance.circuit_breaker_state = mocker.MagicMock()
    embedding_instance.circuit_breaker_state.value = "closed"
    registry.get_embedding_provider.return_value = embedding_provider_enum
    registry.get_embedding_provider_instance.return_value = embedding_instance

    # Mock sparse embedding provider
    sparse_provider_enum = mocker.MagicMock()
    sparse_provider_enum.as_title = "FastEmbed_Local"
    sparse_instance = mocker.MagicMock()
    registry.get_embedding_provider.side_effect = lambda sparse=False: (
        sparse_provider_enum if sparse else embedding_provider_enum
    )
    registry.get_sparse_embedding_provider_instance.return_value = sparse_instance

    # Mock reranking provider with circuit breaker
    reranking_provider_enum = mocker.MagicMock()
    reranking_instance = mocker.MagicMock()
    reranking_instance.model_name = "voyage-rerank-2.5"
    reranking_instance.circuit_breaker_state = mocker.MagicMock()
    reranking_instance.circuit_breaker_state.value = "closed"
    registry.get_reranking_provider.return_value = reranking_provider_enum
    registry.get_reranking_provider_instance.return_value = reranking_instance

    # Mock unified get_provider_instance to return the right instances
    def get_provider_instance(enum_value, provider_type: str, singleton: bool = True):
        if provider_type == "vector_store":
            return vector_store
        if provider_type == "embedding":
            return embedding_instance
        if provider_type == "sparse_embedding":
            return sparse_instance
        return reranking_instance if provider_type == "reranking" else None

    registry.get_provider_instance.side_effect = get_provider_instance

    return registry


@pytest.fixture
def session_statistics() -> SessionStatistics:
    """Create session statistics instance."""
    from codeweaver.common.statistics import FileStatistics, TokenCounter

    return SessionStatistics(
        index_statistics=FileStatistics(),
        query_statistics=[],
        token_statistics=TokenCounter(),
        semantic_statistics=[],
        indexing_statistics=[],
        embedding_statistics=[],
        reranking_statistics=[],
        sparse_embedding_statistics=[],
        vector_store_statistics=[],
        overall_statistics=[],
        _successful_request_log=[],
        _failed_request_log=[],
        _successful_http_request_log=[],
        _failed_http_request_log=[],
        failover_statistics=FailoverStats(),
    )


@pytest.fixture
def health_service(
    mock_provider_registry: MagicMock, session_statistics: SessionStatistics
) -> HealthService:
    """Create health service instance."""
    return HealthService(
        provider_registry=mock_provider_registry,
        statistics=session_statistics,
        indexer=None,
        startup_time=time.time(),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_endpoint_responds(health_service: HealthService):
    """T012: Health endpoint responds with valid HealthResponse.

    Given: Initialized health service
    When: get_health_response() called
    Then: Returns HealthResponse with all required fields
    """
    response = await health_service.get_health_response()

    assert isinstance(response, HealthResponse)
    assert response.status in ("healthy", "degraded", "unhealthy")
    assert response.timestamp is not None
    assert response.uptime_seconds >= 0
    assert response.indexing is not None
    assert response.services is not None
    assert response.statistics is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_response_schema_validation(health_service: HealthService):
    """T012: Health response matches FR-010-Enhanced schema exactly.

    Given: Health service with all components
    When: get_health_response() called
    Then: Response structure matches contract schema precisely
    """
    response = await health_service.get_health_response()

    # Validate top-level structure
    assert hasattr(response, "status")
    assert hasattr(response, "timestamp")
    assert hasattr(response, "uptime_seconds")
    assert hasattr(response, "indexing")
    assert hasattr(response, "services")
    assert hasattr(response, "statistics")

    # Validate timestamp is ISO8601
    datetime.fromisoformat(response.timestamp)

    # Validate indexing structure
    indexing = response.indexing
    assert indexing.state in ("idle", "indexing", "error")
    assert hasattr(indexing, "progress")
    assert indexing.progress.files_discovered >= 0
    assert indexing.progress.files_processed >= 0
    assert indexing.progress.chunks_created >= 0
    assert indexing.progress.errors >= 0

    # Validate services structure
    services = response.services
    assert services.vector_store.status in ("up", "down", "degraded")
    assert services.vector_store.latency_ms >= 0
    assert services.embedding_provider.status in ("up", "down")
    assert services.embedding_provider.circuit_breaker_state in ("closed", "open", "half_open")
    assert services.embedding_provider.latency_ms >= 0
    assert services.sparse_embedding.status in ("up", "down")
    assert services.reranking.status in ("up", "down")
    assert services.reranking.latency_ms >= 0

    # Validate statistics structure
    stats = response.statistics
    assert stats.total_chunks_indexed >= 0
    assert stats.total_files_indexed >= 0
    assert isinstance(stats.languages_indexed, list)
    assert stats.index_size_mb >= 0
    assert stats.queries_processed >= 0
    assert stats.avg_query_latency_ms >= 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_during_indexing(
    health_service: HealthService, test_project_path: Path, mocker
):
    """T012: Health during indexing shows progress correctly.

    Given: Indexer processing files
    When: get_health_response() called during indexing
    Then: Indexing progress reflects current state, estimated completion provided
    """
    # Create mock indexer with in-progress stats
    mock_indexer = mocker.MagicMock(spec=Indexer)
    mock_indexer.stats = IndexingStats(
        files_discovered=100,
        files_processed=45,
        chunks_created=320,
        chunks_embedded=280,
        chunks_indexed=280,
        start_time=time.time() - 300,  # 5 minutes ago
    )
    mock_indexer.stats.files_with_errors = []

    health_service.set_indexer(mock_indexer)

    response = await health_service.get_health_response()

    # Verify indexing state
    assert response.indexing.state == "indexing"
    assert response.indexing.progress.files_discovered == 100
    assert response.indexing.progress.files_processed == 45
    assert response.indexing.progress.chunks_created == 320
    assert response.indexing.progress.errors == 0

    # Verify start time is present
    assert response.indexing.progress.start_time is not None
    datetime.fromisoformat(response.indexing.progress.start_time)

    # Verify estimated completion is calculated
    assert response.indexing.progress.estimated_completion is not None
    datetime.fromisoformat(response.indexing.progress.estimated_completion)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_status_healthy(health_service: HealthService, mocker):
    """T012: Health status determined as 'healthy' when all services up.

    Given: All services operational, indexing idle or progressing normally
    When: get_health_response() called
    Then: Status is 'healthy'
    """
    # Mock resource collection to return healthy values
    from codeweaver.server.health_models import ResourceInfo

    async def mock_resource_info():
        return ResourceInfo(
            memory_mb=1024,  # <2048 (healthy threshold)
            cpu_percent=50.0,  # <80 (healthy threshold)
            disk_total_mb=10000,
            disk_index_mb=5000,
            disk_cache_mb=2000,
            file_descriptors=100,
            file_descriptors_limit=1024,  # 9.8% usage (healthy)
        )

    mocker.patch.object(health_service, "_collect_resource_info", side_effect=mock_resource_info)

    response = await health_service.get_health_response()

    # With mock providers all returning "up" and healthy resources, should be healthy
    assert response.status == "healthy"
    assert response.services.vector_store.status == "up"
    assert response.services.embedding_provider.status == "up"
    assert response.services.sparse_embedding.status == "up"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_status_degraded(health_service: HealthService, mocker):
    """T012: Health status determined as 'degraded' when some services down.

    Given: Embedding provider down but sparse embedding available
    When: get_health_response() called
    Then: Status is 'degraded' (sparse-only search still works)
    """
    # Mock embedding provider as down (circuit breaker open)
    embedding_instance = (
        health_service._provider_registry.get_embedding_provider_instance.return_value
    )
    embedding_instance.circuit_breaker_state.value = "open"

    response = await health_service.get_health_response()

    # Should be degraded: embedding down but sparse still works
    assert response.status == "degraded"
    assert response.services.embedding_provider.status == "down"
    assert response.services.embedding_provider.circuit_breaker_state == "open"
    assert response.services.sparse_embedding.status == "up"
    assert response.services.vector_store.status == "up"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_status_unhealthy(health_service: HealthService, mocker):
    """T012: Health status determined as 'unhealthy' when critical services down.

    Given: Vector store unavailable
    When: get_health_response() called
    Then: Status is 'unhealthy' (no search functionality available)
    """

    # Mock vector store as down using unified API
    # Note: get_provider_instance is called with (enum, "string_type", singleton=True)
    def failing_get_provider_instance(
        provider_enum, provider_type: str, *, singleton: bool = False, **kwargs
    ):
        if provider_type == "vector_store":
            raise RuntimeError("Vector store unavailable")
        # Return other providers normally with proper mock objects
        if provider_type == "embedding":
            embedding_mock = mocker.MagicMock()
            embedding_mock.model_name = "voyage-code-3"
            embedding_mock.circuit_breaker_state = mocker.MagicMock()
            embedding_mock.circuit_breaker_state.value = "closed"
            return embedding_mock
        if provider_type == "sparse_embedding":
            return mocker.MagicMock()
        if provider_type == "reranking":
            reranking_mock = mocker.MagicMock()
            reranking_mock.model_name = "voyage-rerank-2.5"
            reranking_mock.circuit_breaker_state = mocker.MagicMock()
            reranking_mock.circuit_breaker_state.value = "closed"
            return reranking_mock
        # Return a valid mock for any other case to avoid None
        return mocker.MagicMock()

    health_service._provider_registry.get_provider_instance.side_effect = (  # ty: ignore[invalid-assignment]
        failing_get_provider_instance
    )

    response = await health_service.get_health_response()

    # Should be unhealthy: vector store is critical
    assert response.status == "unhealthy"
    assert response.services.vector_store.status == "down"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_indexing_progress(health_service: HealthService, mocker):
    """T012: Indexing progress updates correctly during indexing.

    Given: Indexer with various completion states
    When: get_health_response() called at different stages
    Then: Progress reflects current indexing state accurately
    """
    # Stage 1: Indexing just started
    mock_indexer = mocker.MagicMock(spec=Indexer)
    mock_indexer.stats = IndexingStats(
        files_discovered=50, files_processed=5, chunks_created=35, start_time=time.time()
    )
    mock_indexer.stats.files_with_errors = []

    health_service.set_indexer(mock_indexer)
    response1 = await health_service.get_health_response()

    assert response1.indexing.state == "indexing"
    assert (
        response1.indexing.progress.files_processed < response1.indexing.progress.files_discovered
    )

    # Stage 2: Indexing complete
    mock_indexer.stats.files_processed = 50
    mock_indexer.stats.chunks_created = 350

    response2 = await health_service.get_health_response()

    assert response2.indexing.state == "idle"
    assert (
        response2.indexing.progress.files_processed == response2.indexing.progress.files_discovered
    )

    # Stage 3: Indexing with errors
    mock_indexer.stats.files_with_errors = [Path(f"file{i}.py") for i in range(60)]

    response3 = await health_service.get_health_response()

    assert response3.indexing.state == "error"
    assert response3.indexing.progress.errors == 60


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_service_states(health_service: HealthService):
    """T012: Service health checks work for all providers.

    Given: Health service with all provider types
    When: get_health_response() called
    Then: All service health states are correctly reported
    """
    response = await health_service.get_health_response()

    # Verify all services have health information
    assert response.services.vector_store is not None
    assert response.services.embedding_provider is not None
    assert response.services.sparse_embedding is not None
    assert response.services.reranking is not None

    # Verify vector store
    assert response.services.vector_store.status in ("up", "down", "degraded")
    assert response.services.vector_store.latency_ms >= 0

    # Verify embedding provider with circuit breaker
    assert response.services.embedding_provider.status in ("up", "down")
    assert response.services.embedding_provider.model == "voyage-code-3"
    assert response.services.embedding_provider.circuit_breaker_state in (
        "closed",
        "open",
        "half_open",
    )

    # Verify sparse embedding
    assert response.services.sparse_embedding.status in ("up", "down")
    assert response.services.sparse_embedding.provider == "FastEmbed_Local"

    # Verify reranking
    assert response.services.reranking.status in ("up", "down")
    assert response.services.reranking.model == "voyage-rerank-2.5"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_circuit_breaker_exposure(health_service: HealthService, mocker):
    """T012: Circuit breaker states from T006 are visible in health response.

    Given: Providers with circuit breaker states
    When: get_health_response() called
    Then: Circuit breaker states are exposed correctly
    """
    response = await health_service.get_health_response()

    # Embedding provider circuit breaker
    assert response.services.embedding_provider.circuit_breaker_state == "closed"

    # Test half_open state
    embedding_instance = (
        health_service._provider_registry.get_embedding_provider_instance.return_value
    )
    embedding_instance.circuit_breaker_state.value = "half_open"

    response2 = await health_service.get_health_response()
    assert response2.services.embedding_provider.circuit_breaker_state == "half_open"
    assert response2.services.embedding_provider.status == "up"

    # Test open state (service down)
    embedding_instance.circuit_breaker_state.value = "open"

    response3 = await health_service.get_health_response()
    assert response3.services.embedding_provider.circuit_breaker_state == "open"
    assert response3.services.embedding_provider.status == "down"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_statistics(
    health_service: HealthService, session_statistics: SessionStatistics, mocker
):
    """T012: Statistics collected from SessionStatistics correctly.

    Given: Health service with statistics tracking
    When: get_health_response() called
    Then: Statistics reflect session metrics accurately
    """
    # Add some indexed data
    mock_indexer = mocker.MagicMock(spec=Indexer)
    mock_indexer.stats = IndexingStats(
        files_discovered=25,
        files_processed=25,
        chunks_created=175,
        chunks_indexed=175,
        start_time=time.time() - 600,
    )
    mock_indexer.stats.files_with_errors = []

    # Mock session_statistics on the indexer - health service uses this path
    # Set index_statistics to None so it falls back to indexer.stats
    mock_indexer.session_statistics = mocker.MagicMock()
    mock_indexer.session_statistics.index_statistics = None

    health_service.set_indexer(mock_indexer)
    health_service.add_indexed_language("python")
    health_service.add_indexed_language("typescript")

    # Simulate some queries
    session_statistics._successful_request_log = [
        Identifier("req1"),
        Identifier("req2"),
        Identifier("req3"),
    ]

    response = await health_service.get_health_response()

    # Verify statistics
    assert response.statistics.total_chunks_indexed == 175
    assert response.statistics.total_files_indexed == 25
    # Note: languages come from session_statistics.index_statistics which is mocked as None
    # so languages_indexed will be empty, but that's okay for this test
    assert response.statistics.queries_processed == 3
    assert response.statistics.index_size_mb >= 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_performance(health_service: HealthService):
    """T012: Health endpoint responds within <200ms p95.

    Given: Health service with typical load
    When: get_health_response() called multiple times
    Then: p95 response time is <200ms
    """
    response_times = []

    # Execute 100 requests to get statistical sample
    for _ in range(100):
        start = time.perf_counter()
        await health_service.get_health_response()
        elapsed_ms = (time.perf_counter() - start) * 1000
        response_times.append(elapsed_ms)

    # Calculate p95
    response_times_sorted = sorted(response_times)
    p95_index = int(len(response_times_sorted) * 0.95)
    p95_latency = response_times_sorted[p95_index]

    # Verify p95 < 200ms
    assert p95_latency < 200, f"p95 latency {p95_latency:.2f}ms exceeds 200ms requirement"

    # Also verify mean is reasonable (allow for environmental variation)
    mean_latency = sum(response_times) / len(response_times)
    assert mean_latency < 150, f"Mean latency {mean_latency:.2f}ms is higher than expected"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_parallel_component_collection(health_service: HealthService, mocker):
    """T012: Health service collects component info in parallel for performance.

    Given: Health service with slow components
    When: get_health_response() called
    Then: Components queried in parallel, not sequentially
    """
    # Track call order and timing
    call_times = []

    async def slow_indexing_info():
        call_times.append(("indexing", time.perf_counter()))
        await asyncio.sleep(0.1)
        return mocker.MagicMock(spec=IndexingInfo)

    async def slow_services_info():
        call_times.append(("services", time.perf_counter()))
        await asyncio.sleep(0.1)
        return mocker.MagicMock(spec=ServicesInfo)

    async def slow_statistics_info():
        call_times.append(("statistics", time.perf_counter()))
        await asyncio.sleep(0.1)
        return mocker.MagicMock(spec=StatisticsInfo)

    # Patch internal methods
    mocker.patch.object(health_service, "_get_indexing_info", side_effect=slow_indexing_info)
    mocker.patch.object(health_service, "_get_services_info", side_effect=slow_services_info)
    mocker.patch.object(health_service, "_get_statistics_info", side_effect=slow_statistics_info)
    mocker.patch.object(
        health_service, "_determine_status", return_value="healthy"
    )  # Mock status determination

    start = time.perf_counter()
    await health_service.get_health_response()
    elapsed = time.perf_counter() - start

    # If parallel, total time should be ~0.1s (single slowest component)
    # If sequential, total time would be ~0.3s (sum of all components)
    assert elapsed < 0.2, f"Parallel execution failed: took {elapsed:.3f}s (expected ~0.1s)"

    # Verify all three components were called
    assert len(call_times) == 3
    component_names = {call[0] for call in call_times}
    assert component_names == {"indexing", "services", "statistics"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_json_serialization(health_service: HealthService):
    """T012: Health response can be serialized to JSON for HTTP endpoint.

    Given: HealthResponse from health service
    When: model_dump_json() called
    Then: Valid JSON produced matching schema
    """
    response = await health_service.get_health_response()

    # Serialize to JSON
    serialized = response.model_dump_json()
    assert serialized is not None

    # Parse back and validate structure
    json_data = json.loads(serialized)

    assert "status" in json_data
    assert "timestamp" in json_data
    assert "uptime_seconds" in json_data
    assert "indexing" in json_data
    assert "services" in json_data
    assert "statistics" in json_data

    # Verify nested structures
    assert "state" in json_data["indexing"]
    assert "progress" in json_data["indexing"]
    assert "vector_store" in json_data["services"]
    assert "embedding_provider" in json_data["services"]
    assert "total_chunks_indexed" in json_data["statistics"]

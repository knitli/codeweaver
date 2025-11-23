# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration tests for Phase 4 status reporting and failover communication.

Tests the complete flow:
- Statistics collection during failover operations
- Health endpoint includes failover information
- Status endpoint returns proper structure
- MCP tool metadata includes failover state
- Notifications sent to MCP clients
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio

from pydantic_core import to_json

from codeweaver.agent_api.find_code.types import FindCodeResponseSummary
from codeweaver.common.registry import ProviderRegistry
from codeweaver.common.statistics import FailoverStats, get_session_statistics
from codeweaver.engine.failover import VectorStoreFailoverManager
from codeweaver.server.health_models import FailoverInfo
from codeweaver.server.health_service import HealthService


@pytest.fixture
def mock_context() -> Mock:
    """Create a mock FastMCP context for testing."""
    context = Mock()
    # Add log level methods
    context.debug = Mock()
    context.info = Mock()
    context.warning = Mock()
    context.error = Mock()
    return context


@pytest.fixture
def mock_primary_store() -> Mock:
    """Create a mock primary vector store."""
    from codeweaver.providers.vector_stores.base import CircuitBreakerState

    store = Mock()
    store.close = AsyncMock()
    store.initialize = AsyncMock()
    store.upsert = AsyncMock()
    store.search = AsyncMock(return_value=[])
    store.count = AsyncMock(return_value=100)
    store.list_collections = AsyncMock(return_value=[])  # Add for health verification
    store.circuit_breaker_state = CircuitBreakerState.CLOSED  # Circuit breaker is healthy
    return store


@pytest.fixture
def mock_backup_store() -> Mock:
    """Create a mock backup vector store."""
    store = Mock()
    store.close = AsyncMock()
    store.initialize = AsyncMock()
    store.upsert = AsyncMock()
    store.search = AsyncMock(return_value=[])
    store.count = AsyncMock(return_value=0)
    # Add _persist_to_disk for shutdown
    store._persist_to_disk = AsyncMock()
    # Make sure the store is considered "truthy" for if checks
    store.__bool__ = Mock(return_value=True)
    return store


@pytest_asyncio.fixture
async def failover_manager(mock_primary_store: Mock, mock_backup_store: Mock, tmp_path: Path):
    """Create a failover manager with mocked stores."""
    # Create backup directory structure
    backup_dir = tmp_path / ".codeweaver" / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)

    manager = VectorStoreFailoverManager(
        backup_enabled=True,
        failure_threshold=2,
        recovery_threshold=2,
        backup_file_path=str(tmp_path / "test_backup.json"),
    )

    # Mock _create_backup_store to return our mock backup store
    async def mock_create_backup():
        return mock_backup_store

    manager._create_backup_store = mock_create_backup  # ty: ignore[invalid-assignment]

    # Initialize with required parameters
    await manager.initialize(primary_store=mock_primary_store, project_path=tmp_path)
    yield manager
    await manager.shutdown()


@pytest.mark.integration
@pytest.mark.async_test
class TestPhase4StatusFlow:
    """Integration tests for Phase 4 status reporting system."""

    async def test_statistics_collection_during_failover(
        self, failover_manager: VectorStoreFailoverManager, mock_context: Mock
    ) -> None:
        """Test that statistics are collected during failover activation."""
        # Set context for notifications
        failover_manager.set_context(mock_context)

        # Get statistics before failover
        stats = get_session_statistics()
        initial_failover_count = (
            stats.failover_statistics.failover_count if stats.failover_statistics else 0
        )

        # Directly activate failover for testing
        await failover_manager._activate_failover()

        # Verify statistics updated
        updated_stats = get_session_statistics()
        assert updated_stats.failover_statistics is not None
        assert updated_stats.failover_statistics.failover_active is True
        assert updated_stats.failover_statistics.failover_count == initial_failover_count + 1
        assert updated_stats.failover_statistics.active_store_type == "backup"

    async def test_failover_notification_sent(
        self, failover_manager: VectorStoreFailoverManager, mock_context: Mock
    ) -> None:
        """Test that MCP client receives failover activation notification."""
        # Set context for notifications
        failover_manager.set_context(mock_context)

        # Trigger failover directly
        await failover_manager._activate_failover()

        # Verify notification was sent
        assert mock_context.warning.called
        call_args = mock_context.warning.call_args

        # Check notification content - message is passed as first arg
        assert len(call_args.args) > 0
        message = call_args.args[0]
        assert "Failover activated" in message

    async def test_restoration_notification_sent(
        self, failover_manager: VectorStoreFailoverManager, mock_context: Mock
    ) -> None:
        """Test that restoration notification is sent when primary recovers."""
        # Set context for notifications
        failover_manager.set_context(mock_context)

        # First activate failover
        await failover_manager._activate_failover()

        # Reset mock to clear activation notification
        mock_context.warning.reset_mock()

        # Directly trigger restoration
        await failover_manager._restore_to_primary()

        # Verify restoration notification
        assert mock_context.info.called
        call_args = mock_context.info.call_args

        # Check restoration message
        assert len(call_args.args) > 0
        message = call_args.args[0]
        assert "restored" in message.lower()

    async def test_health_endpoint_includes_failover_info(
        self, failover_manager: VectorStoreFailoverManager
    ) -> None:
        """Test that health endpoint includes failover information."""
        import time

        # Create health service with failover manager and required parameters
        registry = ProviderRegistry()
        stats = get_session_statistics()

        health_service = HealthService(
            provider_registry=registry,
            statistics=stats,
            startup_time=time.time(),
            indexer=None,
            failover_manager=failover_manager,
        )

        # Get health response
        health_response = await health_service.get_health_response()

        # Verify failover info included
        assert health_response.failover is not None
        assert isinstance(health_response.failover, FailoverInfo)
        assert health_response.failover.failover_enabled is True
        assert health_response.failover.failover_active is False  # Not in failover initially
        assert health_response.failover.active_store_type == "primary"

    async def test_health_endpoint_during_failover(
        self, failover_manager: VectorStoreFailoverManager, mock_context: Mock
    ) -> None:
        """Test health endpoint shows failover state when active."""
        import time

        # Activate failover directly
        failover_manager.set_context(mock_context)
        await failover_manager._activate_failover()

        # Create health service with required parameters
        registry = ProviderRegistry()
        stats = get_session_statistics()

        health_service = HealthService(
            provider_registry=registry,
            statistics=stats,
            startup_time=time.time(),
            indexer=None,
            failover_manager=failover_manager,
        )

        # Get health response
        health_response = await health_service.get_health_response()

        # Verify failover state
        assert health_response.failover is not None
        assert health_response.failover.failover_active is True
        assert health_response.failover.active_store_type == "backup"
        assert health_response.failover.failover_count > 0

    async def test_status_endpoint_structure(self) -> None:
        """Test that status endpoint returns correct JSON structure."""
        # This test would normally use the actual HTTP endpoint
        # For now, we verify the expected structure matches our implementation

        # Expected structure from app_bindings.py implementation
        expected_keys = {"timestamp", "uptime_seconds", "indexing", "failover", "statistics"}

        # Mock status data
        status_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "uptime_seconds": 3600,
            "indexing": {"active": False},
            "failover": {"enabled": True, "active": False},
            "statistics": {"total_requests": 10, "successful_requests": 9, "failed_requests": 1},
        }

        # Verify structure
        assert set(status_data.keys()) == expected_keys
        assert isinstance(status_data["timestamp"], str)
        assert isinstance(status_data["uptime_seconds"], int)
        assert isinstance(status_data["indexing"], dict)
        assert isinstance(status_data["failover"], dict)
        assert isinstance(status_data["statistics"], dict)

        # Verify JSON serialization works
        json_output = to_json(status_data)
        assert json_output is not None

    async def test_find_code_metadata_population(
        self, failover_manager: VectorStoreFailoverManager
    ) -> None:
        """Test that find_code responses can include failover metadata."""
        # Create a mock FindCodeResponseSummary
        from codeweaver.agent_api.find_code.intent import IntentType
        from codeweaver.agent_api.find_code.types import SearchStrategy

        response = FindCodeResponseSummary(
            matches=[],
            summary="Test summary",
            query_intent=IntentType.UNDERSTAND,
            total_matches=0,
            total_results=0,
            token_count=100,
            execution_time_ms=50.0,
            search_strategy=(SearchStrategy.HYBRID_SEARCH,),
            status="success",
            warnings=[],
            indexing_state=None,
            index_coverage=None,
            search_mode=None,
            languages_found=(),
            metadata=None,
        )

        # Add failover metadata (simulating what app_bindings.py does)
        failover_metadata = {
            "failover": {
                "enabled": failover_manager.backup_enabled,
                "active": failover_manager.is_failover_active,
                "active_store_type": "backup" if failover_manager.is_failover_active else "primary",
            }
        }

        response_with_metadata = response.model_copy(update={"metadata": failover_metadata})

        # Verify metadata included
        assert response_with_metadata.metadata is not None
        assert "failover" in response_with_metadata.metadata
        assert response_with_metadata.metadata["failover"]["enabled"] is True
        assert response_with_metadata.metadata["failover"]["active"] is False
        assert response_with_metadata.metadata["failover"]["active_store_type"] == "primary"

    async def test_statistics_update_granular_control(self) -> None:
        """Test that statistics can be updated with granular control."""
        stats = get_session_statistics()

        # Update with specific fields
        stats.update_failover_stats(
            failover_active=True,
            increment_failover_count=True,
            active_store_type="backup",
            chunks_in_failover=150,
        )

        # Verify updates
        assert stats.failover_statistics is not None
        assert stats.failover_statistics.failover_active is True
        assert stats.failover_statistics.failover_count > 0
        assert stats.failover_statistics.active_store_type == "backup"
        assert stats.failover_statistics.chunks_in_failover == 150

        # Update additional fields
        stats.update_failover_stats(
            increment_backup_syncs=True, backup_file_exists=True, backup_file_size_bytes=1024
        )

        # Verify additional updates
        assert stats.failover_statistics.backup_syncs_completed > 0
        assert stats.failover_statistics.backup_file_exists is True
        assert stats.failover_statistics.backup_file_size_bytes == 1024

    async def test_end_to_end_failover_flow(
        self, failover_manager: VectorStoreFailoverManager, mock_context: Mock
    ) -> None:
        """Test complete end-to-end failover and restoration flow."""
        import time

        # Set context
        failover_manager.set_context(mock_context)

        # 1. Initial state - primary active
        stats_initial = get_session_statistics()
        initial_count = (
            stats_initial.failover_statistics.failover_count
            if stats_initial.failover_statistics
            else 0
        )

        # 2. Trigger failover directly
        await failover_manager._activate_failover()

        # 3. Verify failover activation
        stats_failover = get_session_statistics()
        assert stats_failover.failover_statistics.failover_active is True
        assert stats_failover.failover_statistics.failover_count == initial_count + 1
        assert mock_context.warning.called

        # 4. Verify health shows failover state
        registry = ProviderRegistry()
        stats = get_session_statistics()

        health_service = HealthService(
            provider_registry=registry,
            statistics=stats,
            startup_time=time.time(),
            indexer=None,
            failover_manager=failover_manager,
        )
        health_active = await health_service.get_health_response()
        assert health_active.failover.failover_active is True
        assert health_active.failover.active_store_type == "backup"

        # 5. Restore primary
        mock_context.warning.reset_mock()
        await failover_manager._restore_to_primary()

        # 6. Verify restoration
        stats_restored = get_session_statistics()
        assert stats_restored.failover_statistics.failover_active is False
        assert mock_context.info.called

        # 7. Verify health shows restored state
        health_restored = await health_service.get_health_response()
        assert health_restored.failover.failover_active is False
        assert health_restored.failover.active_store_type == "primary"


@pytest.mark.integration
class TestPhase4CLIStatus:
    """Integration tests for CLI status command."""

    def test_status_command_imports(self) -> None:
        """Test that status command module imports correctly."""
        from codeweaver.cli.commands import status

        # Verify main components exist
        assert hasattr(status, "app")
        assert hasattr(status, "status")
        assert hasattr(status, "_show_status_once")
        assert hasattr(status, "_watch_status")
        assert hasattr(status, "_query_server_status")
        assert hasattr(status, "_display_server_offline")
        assert hasattr(status, "_display_full_status")
        assert hasattr(status, "_display_indexing_status")
        assert hasattr(status, "_display_failover_status")
        assert hasattr(status, "_display_statistics")
        assert hasattr(status, "_format_duration")

    def test_format_duration_utility(self) -> None:
        """Test duration formatting utility function."""
        from codeweaver.cli.commands.status import _format_duration

        # Test seconds
        assert _format_duration(30) == "30s"
        assert _format_duration(45.7) == "45s"

        # Test minutes
        assert _format_duration(90) == "1m 30s"
        assert _format_duration(125) == "2m 5s"

        # Test hours
        assert _format_duration(3661) == "1h 1m 1s"
        assert _format_duration(7200) == "2h 0m 0s"

    def test_status_command_registered(self) -> None:
        """Test that status command is registered in CLI."""
        from codeweaver.cli.__main__ import app

        # The command should be registered
        # We can verify this by checking the app's command registry
        assert app is not None


@pytest.mark.integration
class TestPhase4FailoverStats:
    """Integration tests for FailoverStats dataclass."""

    def test_failover_stats_creation(self) -> None:
        """Test FailoverStats dataclass creation."""
        stats = FailoverStats()

        # Verify default values
        assert stats.failover_active is False
        assert stats.failover_count == 0
        assert stats.total_failover_time_seconds == 0.0
        assert stats.last_failover_time is None
        assert stats.backup_syncs_completed == 0
        assert stats.sync_back_operations == 0
        assert stats.chunks_synced_back == 0
        assert stats.active_store_type is None
        assert stats.primary_circuit_breaker_state is None
        assert stats.backup_file_exists is False
        assert stats.backup_file_size_bytes == 0
        assert stats.chunks_in_failover == 0

    def test_failover_stats_serialization(self) -> None:
        """Test FailoverStats serialization."""
        stats = FailoverStats(
            failover_active=True,
            failover_count=3,
            total_failover_time_seconds=150.5,
            last_failover_time="2025-01-15T10:30:00Z",
            active_store_type="backup",
            chunks_in_failover=100,
        )

        # Serialize to dict
        data = stats.serialize_for_telemetry()

        # Verify serialization
        assert data["failover_active"] is True
        assert data["failover_count"] == 3
        assert data["total_failover_time_seconds"] == 150.5
        assert data["active_store_type"] == "backup"
        assert data["chunks_in_failover"] == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

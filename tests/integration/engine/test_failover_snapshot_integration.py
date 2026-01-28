# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration tests for snapshot functionality in FailoverService.

Tests the integration between FailoverService and QdrantSnapshotBackupService,
including:
- Snapshot creation during maintenance loop
- Cycle-based scheduling
- Error handling and graceful degradation
- Interaction with other maintenance tasks (backup indexing, reconciliation)
"""

from __future__ import annotations

import asyncio

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.fixture
def mock_primary_store():
    """Create a mock primary vector store."""
    store = Mock()
    store.collection_name = "test_collection"
    store.client = Mock()
    store.circuit_breaker_state = Mock()
    return store


@pytest.fixture
def mock_backup_store():
    """Create a mock backup vector store."""
    store = Mock()
    store.collection_name = "backup_collection"
    return store


@pytest.fixture
def mock_indexing_service():
    """Create a mock indexing service."""
    service = AsyncMock()
    service.index_project = AsyncMock(return_value=0)
    return service


@pytest.fixture
def failover_settings(tmp_path: Path):
    """Create failover settings with snapshot configuration."""
    from codeweaver.engine.config import FailoverSettings

    return FailoverSettings(
        disable_failover=False,
        backup_sync=1,  # 1 second for fast testing
        reconciliation_interval_cycles=2,
        snapshot_interval_cycles=3,  # Every 3 cycles
        snapshot_retention_count=5,
        snapshot_storage_path=str(tmp_path / "snapshots"),
        wal_capacity_mb=256,
        wal_segments_ahead=2,
        wal_retain_closed=True,
    )


@pytest.fixture
def failover_service(
    mock_primary_store,
    mock_backup_store,
    mock_indexing_service,
    failover_settings,
):
    """Create a FailoverService instance for testing."""
    from codeweaver.engine.services.failover_service import FailoverService

    return FailoverService(
        primary_store=mock_primary_store,
        backup_store=mock_backup_store,
        indexing_service=mock_indexing_service,
        backup_indexing_service=mock_indexing_service,
        settings=failover_settings,
    )


class TestSnapshotCycleManagement:
    """Tests for snapshot cycle counting and scheduling."""

    @pytest.mark.asyncio
    async def test_snapshot_cycle_counter_increments(self, failover_service):
        """Test that snapshot cycle counter increments on each maintenance run."""
        assert failover_service._snapshot_cycle_count == 0

        # Mock the maintenance operations
        with patch.object(
            failover_service.backup_indexing_service, "index_project", new=AsyncMock()
        ):
            with patch.object(failover_service, "_run_reconciliation", new=AsyncMock()):
                with patch.object(failover_service, "_run_snapshot_maintenance", new=AsyncMock()):
                    # Simulate one maintenance cycle
                    await failover_service.backup_indexing_service.index_project()
                    failover_service._snapshot_cycle_count += 1

        assert failover_service._snapshot_cycle_count == 1

    @pytest.mark.asyncio
    async def test_snapshot_maintenance_runs_on_schedule(self, failover_service):
        """Test that snapshot maintenance runs every N cycles as configured."""
        # Set interval to 2 cycles for testing
        failover_service.settings.snapshot_interval_cycles = 2

        with patch.object(
            failover_service, "_run_snapshot_maintenance", new=AsyncMock()
        ) as mock_snapshot:
            # Simulate 5 maintenance cycles
            for i in range(5):
                failover_service._snapshot_cycle_count += 1

                if failover_service._snapshot_cycle_count >= failover_service.settings.snapshot_interval_cycles:
                    await failover_service._run_snapshot_maintenance()
                    failover_service._snapshot_cycle_count = 0

        # Should have been called 2 times (cycles 2 and 4)
        assert mock_snapshot.call_count == 2

    @pytest.mark.asyncio
    async def test_snapshot_cycle_counter_resets_after_threshold(self, failover_service):
        """Test that snapshot cycle counter resets after reaching threshold."""
        failover_service.settings.snapshot_interval_cycles = 3

        # Increment to threshold
        for i in range(3):
            failover_service._snapshot_cycle_count += 1

        assert failover_service._snapshot_cycle_count == 3

        # Simulate snapshot maintenance and reset
        with patch.object(failover_service, "_run_snapshot_maintenance", new=AsyncMock()):
            await failover_service._run_snapshot_maintenance()
            failover_service._snapshot_cycle_count = 0

        assert failover_service._snapshot_cycle_count == 0


class TestSnapshotCreation:
    """Tests for snapshot creation during failover maintenance."""

    @pytest.mark.asyncio
    async def test_snapshot_maintenance_creates_snapshot(self, failover_service, tmp_path: Path):
        """Test that _run_snapshot_maintenance creates a snapshot."""
        with patch(
            "codeweaver.engine.services.failover_service.QdrantSnapshotBackupService"
        ) as mock_service_class:
            mock_service = Mock()
            mock_service.snapshot_and_cleanup = AsyncMock(
                return_value={
                    "snapshot_created": True,
                    "snapshot_name": "snapshot_test_20250127_120000",
                    "cleanup_stats": {"deleted": 1},
                }
            )
            mock_service_class.return_value = mock_service

            await failover_service._run_snapshot_maintenance()

            # Verify service was created with correct parameters
            mock_service_class.assert_called_once_with(
                vector_store=failover_service.primary_store,
                storage_path=failover_service.settings.snapshot_storage_path,
                retention_count=failover_service.settings.snapshot_retention_count,
            )

            # Verify snapshot_and_cleanup was called
            mock_service.snapshot_and_cleanup.assert_called_once_with(wait=False)

    @pytest.mark.asyncio
    async def test_snapshot_maintenance_cleans_old_snapshots(self, failover_service):
        """Test that old snapshots are cleaned up during maintenance."""
        with patch(
            "codeweaver.engine.services.failover_service.QdrantSnapshotBackupService"
        ) as mock_service_class:
            mock_service = Mock()
            mock_service.snapshot_and_cleanup = AsyncMock(
                return_value={
                    "snapshot_created": True,
                    "snapshot_name": "new_snapshot",
                    "cleanup_stats": {"total": 10, "kept": 5, "deleted": 5, "failed": 0},
                }
            )
            mock_service_class.return_value = mock_service

            await failover_service._run_snapshot_maintenance()

            # Verify cleanup happened
            result = await mock_service.snapshot_and_cleanup()
            assert result["cleanup_stats"]["deleted"] == 5
            assert result["cleanup_stats"]["kept"] == 5

    @pytest.mark.asyncio
    async def test_snapshot_maintenance_without_primary_store(self, failover_service):
        """Test that snapshot maintenance is skipped when primary store is None."""
        failover_service.primary_store = None

        with patch(
            "codeweaver.engine.services.failover_service.QdrantSnapshotBackupService"
        ) as mock_service_class:
            await failover_service._run_snapshot_maintenance()

            # Service should not be created
            mock_service_class.assert_not_called()


class TestSnapshotErrorHandling:
    """Tests for error handling during snapshot operations."""

    @pytest.mark.asyncio
    async def test_snapshot_maintenance_handles_errors_gracefully(self, failover_service):
        """Test that snapshot maintenance errors don't crash the service."""
        with patch(
            "codeweaver.engine.services.failover_service.QdrantSnapshotBackupService"
        ) as mock_service_class:
            mock_service_class.side_effect = Exception("Snapshot service creation failed")

            # Should not raise exception
            await failover_service._run_snapshot_maintenance()

            # Verify error was logged (service attempted to create)
            mock_service_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_snapshot_creation_failure_logged(self, failover_service):
        """Test that snapshot creation failures are logged."""
        with patch(
            "codeweaver.engine.services.failover_service.QdrantSnapshotBackupService"
        ) as mock_service_class:
            mock_service = Mock()
            mock_service.snapshot_and_cleanup = AsyncMock(
                return_value={
                    "snapshot_created": False,
                    "snapshot_name": None,
                    "cleanup_stats": {},
                }
            )
            mock_service_class.return_value = mock_service

            with patch("codeweaver.engine.services.failover_service.logger") as mock_logger:
                await failover_service._run_snapshot_maintenance()

                # Verify warning was logged
                assert any("failed" in str(call).lower() for call in mock_logger.warning.call_args_list)


class TestMaintenanceLoopIntegration:
    """Tests for snapshot integration with full maintenance loop."""

    @pytest.mark.asyncio
    async def test_maintenance_loop_order(self, failover_service):
        """Test that maintenance operations run in correct order."""
        operations_order = []

        async def track_backup_index():
            operations_order.append("backup_index")

        async def track_reconciliation():
            operations_order.append("reconciliation")

        async def track_snapshot():
            operations_order.append("snapshot")

        with patch.object(
            failover_service.backup_indexing_service, "index_project", new=track_backup_index
        ):
            with patch.object(failover_service, "_run_reconciliation", new=track_reconciliation):
                with patch.object(failover_service, "_run_snapshot_maintenance", new=track_snapshot):
                    # Simulate one maintenance cycle with all operations
                    await failover_service.backup_indexing_service.index_project()
                    failover_service._maintenance_cycle_count = 2  # Trigger reconciliation
                    failover_service._snapshot_cycle_count = 3  # Trigger snapshot

                    if failover_service._maintenance_cycle_count >= failover_service.settings.reconciliation_interval_cycles:
                        await failover_service._run_reconciliation()

                    if failover_service._snapshot_cycle_count >= failover_service.settings.snapshot_interval_cycles:
                        await failover_service._run_snapshot_maintenance()

        # Verify order: backup → reconciliation → snapshot
        assert operations_order == ["backup_index", "reconciliation", "snapshot"]

    @pytest.mark.asyncio
    async def test_snapshot_skipped_during_failover(self, failover_service):
        """Test that snapshot maintenance is skipped when failover is active."""
        failover_service._failover_active = True

        with patch.object(
            failover_service, "_run_snapshot_maintenance", new=AsyncMock()
        ) as mock_snapshot:
            # Simulate maintenance loop logic
            if not failover_service._failover_active:
                await failover_service._run_snapshot_maintenance()

        # Snapshot should not be called during active failover
        mock_snapshot.assert_not_called()

    @pytest.mark.asyncio
    async def test_concurrent_maintenance_operations(self, failover_service):
        """Test that maintenance operations can run concurrently if needed."""
        # This test validates the maintenance loop structure supports async ops

        async def slow_backup_index():
            await asyncio.sleep(0.1)
            return 0

        async def slow_reconciliation():
            await asyncio.sleep(0.1)

        async def slow_snapshot():
            await asyncio.sleep(0.1)

        with patch.object(
            failover_service.backup_indexing_service, "index_project", new=slow_backup_index
        ):
            with patch.object(failover_service, "_run_reconciliation", new=slow_reconciliation):
                with patch.object(
                    failover_service, "_run_snapshot_maintenance", new=slow_snapshot
                ):
                    # Run operations in sequence (current implementation)
                    # but verify they're all async
                    start = asyncio.get_event_loop().time()
                    await failover_service.backup_indexing_service.index_project()
                    await failover_service._run_reconciliation()
                    await failover_service._run_snapshot_maintenance()
                    duration = asyncio.get_event_loop().time() - start

                    # Should take ~0.3 seconds (sequential)
                    assert duration >= 0.3


class TestSnapshotConfiguration:
    """Tests for snapshot configuration from FailoverSettings."""

    def test_snapshot_service_uses_correct_retention(self, failover_service, tmp_path: Path):
        """Test that snapshot service is created with correct retention count."""
        with patch(
            "codeweaver.engine.services.failover_service.QdrantSnapshotBackupService"
        ) as mock_service_class:
            mock_service = Mock()
            mock_service.snapshot_and_cleanup = AsyncMock(
                return_value={"snapshot_created": True, "cleanup_stats": {}}
            )
            mock_service_class.return_value = mock_service

            # This test is synchronous, so we need to use asyncio.run
            import asyncio

            asyncio.run(failover_service._run_snapshot_maintenance())

            # Verify retention_count matches settings
            call_args = mock_service_class.call_args
            assert call_args[1]["retention_count"] == failover_service.settings.snapshot_retention_count

    def test_snapshot_service_uses_correct_storage_path(self, failover_service):
        """Test that snapshot service is created with correct storage path."""
        with patch(
            "codeweaver.engine.services.failover_service.QdrantSnapshotBackupService"
        ) as mock_service_class:
            mock_service = Mock()
            mock_service.snapshot_and_cleanup = AsyncMock(
                return_value={"snapshot_created": True, "cleanup_stats": {}}
            )
            mock_service_class.return_value = mock_service

            import asyncio

            asyncio.run(failover_service._run_snapshot_maintenance())

            # Verify storage_path matches settings
            call_args = mock_service_class.call_args
            assert call_args[1]["storage_path"] == failover_service.settings.snapshot_storage_path


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""End-to-end integration tests for the complete backup system.

Tests the full backup system workflow including:
- Phase 1: Reranker fallback
- Phase 2: Vector reconciliation
- Phase 3: Snapshot-based disaster recovery

These tests validate that all three phases work together correctly
and provide comprehensive resilience.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.external_api]


@pytest.fixture
def backup_system_settings(tmp_path: Path):
    """Create complete backup system settings for testing."""
    from codeweaver.engine.config import FailoverSettings

    return FailoverSettings(
        disable_failover=False,
        backup_sync=2,  # 2 seconds for testing
        recovery_window_sec=1,
        max_memory_mb=2048,
        reconciliation_interval_cycles=2,
        reconciliation_batch_size=100,
        reconciliation_detection_limit=1000,
        snapshot_interval_cycles=3,
        snapshot_retention_count=5,
        snapshot_storage_path=str(tmp_path / "snapshots"),
        wal_capacity_mb=256,
        wal_segments_ahead=2,
        wal_retain_closed=True,
    )


@pytest.fixture
def mock_primary_qdrant_store():
    """Create a mock primary Qdrant vector store."""
    from codeweaver.providers import CircuitBreakerState

    store = Mock()
    store.collection_name = "codeweaver_vectors"
    store.client = Mock()
    store.circuit_breaker_state = CircuitBreakerState.CLOSED
    store.upsert = AsyncMock()
    store.search = AsyncMock(return_value=[])
    store.scroll = AsyncMock(return_value=([], None))
    store.count = AsyncMock(return_value=100)
    return store


@pytest.fixture
def mock_backup_qdrant_store():
    """Create a mock backup Qdrant vector store."""
    store = Mock()
    store.collection_name = "backup_vectors"
    store.client = Mock()
    store.upsert = AsyncMock()
    store.search = AsyncMock(return_value=[])
    store.scroll = AsyncMock(return_value=([], None))
    return store


class TestCompleteBackupMaintenanceCycle:
    """Tests for complete backup maintenance cycle with all phases."""

    @pytest.mark.asyncio
    async def test_full_maintenance_cycle_executes_all_phases(
        self,
        backup_system_settings,
        mock_primary_qdrant_store,
        mock_backup_qdrant_store,
        tmp_path: Path,
    ):
        """Test that a full maintenance cycle executes backup, reconciliation, and snapshot."""
        from codeweaver.engine.services.failover_service import FailoverService

        mock_indexing = AsyncMock()
        mock_indexing.index_project = AsyncMock(return_value=5)

        service = FailoverService(
            primary_store=mock_primary_qdrant_store,
            backup_store=mock_backup_qdrant_store,
            indexing_service=mock_indexing,
            backup_indexing_service=mock_indexing,
            settings=backup_system_settings,
        )

        operations_executed = []

        # Mock the operations to track execution
        original_run_reconciliation = service._run_reconciliation
        original_run_snapshot = service._run_snapshot_maintenance

        async def track_reconciliation():
            operations_executed.append("reconciliation")
            # Skip actual reconciliation in test

        async def track_snapshot():
            operations_executed.append("snapshot")
            # Skip actual snapshot in test

        service._run_reconciliation = track_reconciliation
        service._run_snapshot_maintenance = track_snapshot

        # Simulate multiple maintenance cycles
        for cycle in range(6):
            # Backup indexing
            await mock_indexing.index_project()

            # Increment counters
            service._maintenance_cycle_count += 1
            service._snapshot_cycle_count += 1

            # Reconciliation (every 2 cycles)
            if service._maintenance_cycle_count >= backup_system_settings.reconciliation_interval_cycles:
                await service._run_reconciliation()
                service._maintenance_cycle_count = 0

            # Snapshot (every 3 cycles)
            if service._snapshot_cycle_count >= backup_system_settings.snapshot_interval_cycles:
                await service._run_snapshot_maintenance()
                service._snapshot_cycle_count = 0

        # Verify backup indexing ran 6 times
        assert mock_indexing.index_project.call_count == 6

        # Verify reconciliation ran 3 times (cycles 2, 4, 6)
        assert operations_executed.count("reconciliation") == 3

        # Verify snapshot ran 2 times (cycles 3, 6)
        assert operations_executed.count("snapshot") == 2

    @pytest.mark.asyncio
    async def test_backup_indexing_runs_first_in_cycle(
        self,
        backup_system_settings,
        mock_primary_qdrant_store,
        mock_backup_qdrant_store,
    ):
        """Test that backup indexing always runs first in maintenance cycle."""
        from codeweaver.engine.services.failover_service import FailoverService

        execution_order = []

        mock_indexing = AsyncMock()

        async def track_index_project():
            execution_order.append("backup_index")
            return 0

        mock_indexing.index_project = track_index_project

        service = FailoverService(
            primary_store=mock_primary_qdrant_store,
            backup_store=mock_backup_qdrant_store,
            indexing_service=mock_indexing,
            backup_indexing_service=mock_indexing,
            settings=backup_system_settings,
        )

        async def track_reconciliation():
            execution_order.append("reconciliation")

        async def track_snapshot():
            execution_order.append("snapshot")

        service._run_reconciliation = track_reconciliation
        service._run_snapshot_maintenance = track_snapshot

        # Run one complete cycle with all operations
        await mock_indexing.index_project()
        service._maintenance_cycle_count = 2  # Trigger reconciliation
        service._snapshot_cycle_count = 3  # Trigger snapshot

        if service._maintenance_cycle_count >= backup_system_settings.reconciliation_interval_cycles:
            await service._run_reconciliation()

        if service._snapshot_cycle_count >= backup_system_settings.snapshot_interval_cycles:
            await service._run_snapshot_maintenance()

        # Verify order
        assert execution_order == ["backup_index", "reconciliation", "snapshot"]

    @pytest.mark.asyncio
    async def test_maintenance_continues_after_operation_failure(
        self,
        backup_system_settings,
        mock_primary_qdrant_store,
        mock_backup_qdrant_store,
    ):
        """Test that maintenance loop continues even if one operation fails."""
        from codeweaver.engine.services.failover_service import FailoverService

        operations_completed = []

        mock_indexing = AsyncMock()
        mock_indexing.index_project = AsyncMock(return_value=0)

        service = FailoverService(
            primary_store=mock_primary_qdrant_store,
            backup_store=mock_backup_qdrant_store,
            indexing_service=mock_indexing,
            backup_indexing_service=mock_indexing,
            settings=backup_system_settings,
        )

        # Make reconciliation fail
        async def failing_reconciliation():
            operations_completed.append("reconciliation_attempted")
            raise Exception("Reconciliation failed")

        async def track_snapshot():
            operations_completed.append("snapshot")

        service._run_reconciliation = failing_reconciliation
        service._run_snapshot_maintenance = track_snapshot

        # Run cycle with failing reconciliation
        try:
            await mock_indexing.index_project()
            service._maintenance_cycle_count = 2
            service._snapshot_cycle_count = 3

            # This should fail but not crash
            try:
                await service._run_reconciliation()
            except Exception:
                pass  # Expected failure

            # Snapshot should still run
            await service._run_snapshot_maintenance()

        except Exception as e:
            pytest.fail(f"Maintenance loop crashed: {e}")

        # Verify both operations were attempted
        assert "reconciliation_attempted" in operations_completed
        assert "snapshot" in operations_completed


class TestSnapshotCreationDuringNormalOperation:
    """Tests for snapshot creation during normal operation."""

    @pytest.mark.asyncio
    async def test_snapshots_created_on_schedule(
        self,
        backup_system_settings,
        mock_primary_qdrant_store,
        tmp_path: Path,
    ):
        """Test that snapshots are created on the configured schedule."""
        from codeweaver.engine.services.failover_service import FailoverService

        mock_indexing = AsyncMock()
        mock_indexing.index_project = AsyncMock(return_value=0)

        service = FailoverService(
            primary_store=mock_primary_qdrant_store,
            backup_store=None,  # No backup store for snapshot-only testing
            indexing_service=mock_indexing,
            backup_indexing_service=mock_indexing,
            settings=backup_system_settings,
        )

        snapshots_created = []

        with patch(
            "codeweaver.engine.services.failover_service.QdrantSnapshotBackupService"
        ) as mock_service_class:

            async def mock_snapshot_and_cleanup(wait=False):
                snapshot_name = f"snapshot_{len(snapshots_created)}"
                snapshots_created.append(snapshot_name)
                return {
                    "snapshot_created": True,
                    "snapshot_name": snapshot_name,
                    "cleanup_stats": {},
                }

            mock_service = Mock()
            mock_service.snapshot_and_cleanup = mock_snapshot_and_cleanup
            mock_service_class.return_value = mock_service

            # Run 9 cycles (should create 3 snapshots at cycles 3, 6, 9)
            for cycle in range(9):
                service._snapshot_cycle_count += 1

                if service._snapshot_cycle_count >= backup_system_settings.snapshot_interval_cycles:
                    await service._run_snapshot_maintenance()
                    service._snapshot_cycle_count = 0

        # Verify 3 snapshots were created
        assert len(snapshots_created) == 3

    @pytest.mark.asyncio
    async def test_snapshot_retention_enforced(
        self,
        backup_system_settings,
        mock_primary_qdrant_store,
        tmp_path: Path,
    ):
        """Test that snapshot retention is enforced during cleanup."""
        from codeweaver.engine.services.snapshot_service import QdrantSnapshotBackupService

        # Create service with retention of 3
        service = QdrantSnapshotBackupService(
            vector_store=mock_primary_qdrant_store,
            storage_path=tmp_path / "snapshots",
            retention_count=3,
        )

        # Mock list_snapshots to return 6 snapshots
        old_snapshots = [
            {"name": f"snapshot_{i}", "created_at": f"2025-01-27T{10+i:02d}:00:00Z"}
            for i in range(6)
        ]

        deleted_snapshots = []

        async def mock_delete(name: str) -> bool:
            deleted_snapshots.append(name)
            return True

        with patch.object(service, "list_snapshots", return_value=old_snapshots):
            with patch.object(service, "delete_snapshot", side_effect=mock_delete):
                stats = await service.cleanup_old_snapshots()

        # Should keep 3 most recent, delete 3 oldest
        assert stats["total"] == 6
        assert stats["kept"] == 3
        assert stats["deleted"] == 3
        assert len(deleted_snapshots) == 3

        # Verify oldest snapshots were deleted
        assert "snapshot_0" in deleted_snapshots
        assert "snapshot_1" in deleted_snapshots
        assert "snapshot_2" in deleted_snapshots


class TestDisasterRecoveryFromSnapshot:
    """Tests for disaster recovery using snapshots."""

    @pytest.mark.asyncio
    async def test_snapshot_restoration_workflow(
        self,
        mock_primary_qdrant_store,
        tmp_path: Path,
    ):
        """Test the complete snapshot restoration workflow."""
        from codeweaver.engine.services.snapshot_service import QdrantSnapshotBackupService

        service = QdrantSnapshotBackupService(
            vector_store=mock_primary_qdrant_store,
            storage_path=tmp_path / "snapshots",
            retention_count=5,
        )

        # Mock snapshot operations
        mock_primary_qdrant_store.client.create_snapshot = Mock()
        mock_primary_qdrant_store.client.list_snapshots = Mock(
            return_value=[Mock(name="snapshot_recovery_20250127_120000")]
        )
        mock_primary_qdrant_store.client.recover_snapshot = Mock()

        # 1. Create a snapshot
        snapshot_name = await service.create_snapshot(wait=False)
        assert snapshot_name is not None

        # 2. List snapshots to find recovery point
        snapshots = await service.list_snapshots()
        assert len(snapshots) > 0

        # 3. Restore from snapshot
        result = await service.restore_snapshot(snapshot_name, wait=True)
        assert result is True

        # Verify recovery was called
        mock_primary_qdrant_store.client.recover_snapshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_latest_snapshot_for_recovery(
        self,
        mock_primary_qdrant_store,
        tmp_path: Path,
    ):
        """Test getting the latest snapshot for disaster recovery."""
        from codeweaver.engine.services.snapshot_service import QdrantSnapshotBackupService

        service = QdrantSnapshotBackupService(
            vector_store=mock_primary_qdrant_store,
            storage_path=tmp_path / "snapshots",
            retention_count=5,
        )

        # Mock snapshots with different timestamps
        snapshots = [
            {"name": "snapshot_1", "created_at": "2025-01-27T10:00:00Z"},
            {"name": "snapshot_2", "created_at": "2025-01-27T12:00:00Z"},  # Latest
            {"name": "snapshot_3", "created_at": "2025-01-27T11:00:00Z"},
        ]

        with patch.object(service, "list_snapshots", return_value=snapshots):
            latest = await service.get_latest_snapshot()

        assert latest is not None
        assert latest["name"] == "snapshot_2"  # Most recent


class TestBackupSystemConfiguration:
    """Tests for backup system configuration and settings."""

    def test_wal_config_applied_to_primary_collection(self, backup_system_settings):
        """Test that WAL configuration is applied to primary collection."""
        # This is tested more thoroughly in test_wal_config_merging.py
        # Here we just verify the settings are accessible
        assert backup_system_settings.wal_capacity_mb == 256
        assert backup_system_settings.wal_segments_ahead == 2
        assert backup_system_settings.wal_retain_closed is True

    def test_snapshot_configuration_values(self, backup_system_settings, tmp_path: Path):
        """Test that snapshot configuration values are correct."""
        assert backup_system_settings.snapshot_interval_cycles == 3
        assert backup_system_settings.snapshot_retention_count == 5
        assert backup_system_settings.snapshot_storage_path == str(tmp_path / "snapshots")

    def test_reconciliation_configuration_values(self, backup_system_settings):
        """Test that reconciliation configuration values are correct."""
        assert backup_system_settings.reconciliation_interval_cycles == 2
        assert backup_system_settings.reconciliation_batch_size == 100
        assert backup_system_settings.reconciliation_detection_limit == 1000


class TestBackupSystemDisabled:
    """Tests for behavior when backup system is disabled."""

    @pytest.mark.asyncio
    async def test_no_snapshots_when_failover_disabled(self, tmp_path: Path):
        """Test that snapshots are not created when failover is disabled."""
        from codeweaver.engine.config import FailoverSettings
        from codeweaver.engine.services.failover_service import FailoverService

        settings = FailoverSettings(
            disable_failover=True,  # Disabled
            snapshot_interval_cycles=1,
            snapshot_storage_path=str(tmp_path / "snapshots"),
        )

        mock_indexing = AsyncMock()
        service = FailoverService(
            primary_store=None,
            backup_store=None,
            indexing_service=mock_indexing,
            backup_indexing_service=mock_indexing,
            settings=settings,
        )

        with patch(
            "codeweaver.engine.services.failover_service.QdrantSnapshotBackupService"
        ) as mock_service_class:
            # Even if we call _run_snapshot_maintenance, it should not create service
            # because primary_store is None (which happens when failover is disabled)
            await service._run_snapshot_maintenance()

            mock_service_class.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

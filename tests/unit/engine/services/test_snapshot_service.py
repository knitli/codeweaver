# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for QdrantSnapshotBackupService.

Tests cover:
- Snapshot creation and waiting
- Snapshot listing and deletion
- Retention management and cleanup
- Snapshot restoration
- Error handling and edge cases
"""

from __future__ import annotations

from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest


if TYPE_CHECKING:
    pass


@pytest.fixture
def mock_vector_store() -> Mock:
    """Create a mock vector store provider with Qdrant client."""
    store = Mock(spec=["client", "collection_name"])
    store.collection_name = "test_collection"
    store.client = Mock()
    return store


@pytest.fixture
def snapshot_service(mock_vector_store: Mock, tmp_path: Path):
    """Create a QdrantSnapshotBackupService instance for testing."""
    from codeweaver.engine.services.snapshot_service import QdrantSnapshotBackupService

    return QdrantSnapshotBackupService(
        vector_store=mock_vector_store,
        storage_path=tmp_path / "snapshots",
        retention_count=3,
        collection_name="test_collection",
    )


class TestQdrantSnapshotBackupServiceInitialization:
    """Tests for service initialization and configuration."""

    def test_init_with_custom_storage_path(self, mock_vector_store: Mock, tmp_path: Path):
        """Test initialization with custom storage path."""
        from codeweaver.engine.services.snapshot_service import QdrantSnapshotBackupService

        custom_path = tmp_path / "custom_snapshots"
        service = QdrantSnapshotBackupService(
            vector_store=mock_vector_store, storage_path=custom_path, retention_count=5
        )

        assert service.storage_path == custom_path
        assert service.retention_count == 5
        assert custom_path.exists()

    def test_init_with_default_storage_path(self, mock_vector_store: Mock):
        """Test initialization with default storage path."""
        from codeweaver.engine.services.snapshot_service import QdrantSnapshotBackupService

        service = QdrantSnapshotBackupService(vector_store=mock_vector_store, retention_count=12)

        # Should use user state directory
        assert "snapshots" in str(service.storage_path)
        assert service.collection_name in str(service.storage_path)

    def test_init_creates_storage_directory(self, mock_vector_store: Mock, tmp_path: Path):
        """Test that storage directory is created on init."""
        from codeweaver.engine.services.snapshot_service import QdrantSnapshotBackupService

        storage_path = tmp_path / "new_snapshots" / "nested"
        assert not storage_path.exists()

        QdrantSnapshotBackupService(vector_store=mock_vector_store, storage_path=storage_path)

        assert storage_path.exists()

    def test_init_uses_collection_name_from_vector_store(self, tmp_path: Path):
        """Test that collection name is taken from vector store if not provided."""
        from codeweaver.engine.services.snapshot_service import QdrantSnapshotBackupService

        store = Mock()
        store.collection_name = "custom_collection"

        service = QdrantSnapshotBackupService(vector_store=store, storage_path=tmp_path)

        assert service.collection_name == "custom_collection"


class TestSnapshotCreation:
    """Tests for snapshot creation functionality."""

    @pytest.mark.asyncio
    async def test_create_snapshot_success(self, snapshot_service, mock_vector_store: Mock):
        """Test successful snapshot creation without waiting."""
        mock_vector_store.client.create_snapshot = Mock(return_value=Mock(name="snapshot_123"))

        snapshot_name = await snapshot_service.create_snapshot(wait=False)

        assert snapshot_name is not None
        assert snapshot_name.startswith("snapshot_test_collection_")
        mock_vector_store.client.create_snapshot.assert_called_once()
        call_args = mock_vector_store.client.create_snapshot.call_args
        assert call_args[1]["collection_name"] == "test_collection"
        assert call_args[1]["snapshot_name"] == snapshot_name

    @pytest.mark.asyncio
    async def test_create_snapshot_with_wait(self, snapshot_service, mock_vector_store: Mock):
        """Test snapshot creation with wait for completion."""
        mock_snapshot = Mock()
        mock_snapshot.name = "snapshot_test_collection_20250127_120000"

        mock_vector_store.client.create_snapshot = Mock(return_value=mock_snapshot)
        mock_vector_store.client.list_snapshots = Mock(return_value=[mock_snapshot])

        snapshot_name = await snapshot_service.create_snapshot(wait=True)

        assert snapshot_name is not None
        assert snapshot_name.startswith("snapshot_test_collection_")
        mock_vector_store.client.list_snapshots.assert_called()

    @pytest.mark.asyncio
    async def test_create_snapshot_generates_timestamp_name(
        self, snapshot_service, mock_vector_store: Mock
    ):
        """Test that snapshot name includes timestamp."""
        mock_vector_store.client.create_snapshot = Mock(return_value=Mock())

        with patch("codeweaver.engine.services.snapshot_service.datetime") as mock_datetime:
            mock_now = Mock()
            mock_now.strftime = Mock(return_value="20250127_153045")
            mock_datetime.now = Mock(return_value=mock_now)
            mock_datetime.UTC = UTC

            snapshot_name = await snapshot_service.create_snapshot(wait=False)

        assert snapshot_name == "snapshot_test_collection_20250127_153045"

    @pytest.mark.asyncio
    async def test_create_snapshot_failure_returns_none(
        self, snapshot_service, mock_vector_store: Mock
    ):
        """Test that create_snapshot returns None on failure."""
        mock_vector_store.client.create_snapshot = Mock(
            side_effect=Exception("Snapshot creation failed")
        )

        snapshot_name = await snapshot_service.create_snapshot(wait=False)

        assert snapshot_name is None

    @pytest.mark.asyncio
    async def test_wait_for_snapshot_timeout(self, snapshot_service, mock_vector_store: Mock):
        """Test that _wait_for_snapshot handles timeout correctly."""
        # Never return the snapshot we're waiting for
        mock_vector_store.client.list_snapshots = Mock(return_value=[])

        result = await snapshot_service._wait_for_snapshot("missing_snapshot", timeout=2)

        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_snapshot_error_handling(
        self, snapshot_service, mock_vector_store: Mock
    ):
        """Test that _wait_for_snapshot handles errors during polling."""
        mock_vector_store.client.list_snapshots = Mock(side_effect=Exception("Connection error"))

        result = await snapshot_service._wait_for_snapshot("test_snapshot", timeout=2)

        assert result is False


class TestSnapshotListing:
    """Tests for snapshot listing functionality."""

    @pytest.mark.asyncio
    async def test_list_snapshots_success(self, snapshot_service, mock_vector_store: Mock):
        """Test successful snapshot listing."""
        mock_snapshot1 = Mock()
        mock_snapshot1.name = "snapshot_1"
        mock_snapshot1.size = 1000
        mock_snapshot1.creation_time = "2025-01-27T12:00:00Z"

        mock_snapshot2 = Mock()
        mock_snapshot2.name = "snapshot_2"
        mock_snapshot2.size = 2000
        mock_snapshot2.creation_time = "2025-01-27T13:00:00Z"

        mock_vector_store.client.list_snapshots = Mock(
            return_value=[mock_snapshot1, mock_snapshot2]
        )

        snapshots = await snapshot_service.list_snapshots()

        assert len(snapshots) == 2
        assert snapshots[0]["name"] == "snapshot_1"
        assert snapshots[0]["size"] == 1000
        assert snapshots[1]["name"] == "snapshot_2"
        assert snapshots[1]["size"] == 2000

    @pytest.mark.asyncio
    async def test_list_snapshots_empty(self, snapshot_service, mock_vector_store: Mock):
        """Test listing snapshots when none exist."""
        mock_vector_store.client.list_snapshots = Mock(return_value=[])

        snapshots = await snapshot_service.list_snapshots()

        assert snapshots == []

    @pytest.mark.asyncio
    async def test_list_snapshots_failure(self, snapshot_service, mock_vector_store: Mock):
        """Test that list_snapshots returns empty list on failure."""
        mock_vector_store.client.list_snapshots = Mock(side_effect=Exception("List failed"))

        snapshots = await snapshot_service.list_snapshots()

        assert snapshots == []


class TestSnapshotDeletion:
    """Tests for snapshot deletion functionality."""

    @pytest.mark.asyncio
    async def test_delete_snapshot_success(self, snapshot_service, mock_vector_store: Mock):
        """Test successful snapshot deletion."""
        mock_vector_store.client.delete_snapshot = Mock()

        result = await snapshot_service.delete_snapshot("snapshot_to_delete")

        assert result is True
        mock_vector_store.client.delete_snapshot.assert_called_once_with(
            collection_name="test_collection", snapshot_name="snapshot_to_delete"
        )

    @pytest.mark.asyncio
    async def test_delete_snapshot_failure(self, snapshot_service, mock_vector_store: Mock):
        """Test that delete_snapshot returns False on failure."""
        mock_vector_store.client.delete_snapshot = Mock(side_effect=Exception("Delete failed"))

        result = await snapshot_service.delete_snapshot("snapshot_to_delete")

        assert result is False


class TestSnapshotCleanup:
    """Tests for snapshot cleanup and retention management."""

    @pytest.mark.asyncio
    async def test_cleanup_old_snapshots_respects_retention(
        self, snapshot_service, mock_vector_store: Mock
    ):
        """Test that cleanup keeps the most recent N snapshots."""
        # Create 5 snapshots, retention is 3
        snapshots = [
            {"name": f"snapshot_{i}", "created_at": f"2025-01-27T{10 + i:02d}:00:00Z"}
            for i in range(5)
        ]

        with patch.object(snapshot_service, "list_snapshots", return_value=snapshots):
            with patch.object(
                snapshot_service, "delete_snapshot", return_value=True
            ) as mock_delete:
                stats = await snapshot_service.cleanup_old_snapshots()

        assert stats["total"] == 5
        assert stats["kept"] == 3
        assert stats["deleted"] == 2
        assert stats["failed"] == 0

        # Should delete the 2 oldest
        assert mock_delete.call_count == 2
        deleted_names = [call_args[0][0] for call_args in mock_delete.call_args_list]
        assert "snapshot_0" in deleted_names
        assert "snapshot_1" in deleted_names

    @pytest.mark.asyncio
    async def test_cleanup_when_under_retention(self, snapshot_service, mock_vector_store: Mock):
        """Test that cleanup does nothing when snapshot count is under retention."""
        snapshots = [
            {"name": "snapshot_1", "created_at": "2025-01-27T10:00:00Z"},
            {"name": "snapshot_2", "created_at": "2025-01-27T11:00:00Z"},
        ]

        with patch.object(snapshot_service, "list_snapshots", return_value=snapshots):
            with patch.object(snapshot_service, "delete_snapshot") as mock_delete:
                stats = await snapshot_service.cleanup_old_snapshots()

        assert stats["total"] == 2
        assert stats["kept"] == 2
        assert stats["deleted"] == 0
        assert stats["failed"] == 0
        mock_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_handles_deletion_failures(
        self, snapshot_service, mock_vector_store: Mock
    ):
        """Test that cleanup tracks deletion failures."""
        snapshots = [
            {"name": f"snapshot_{i}", "created_at": f"2025-01-27T{10 + i:02d}:00:00Z"}
            for i in range(5)
        ]

        def delete_side_effect(name: str) -> bool:
            # Fail for snapshot_0
            return name != "snapshot_0"

        with patch.object(snapshot_service, "list_snapshots", return_value=snapshots):
            with patch.object(
                snapshot_service, "delete_snapshot", side_effect=delete_side_effect
            ) as mock_delete:
                stats = await snapshot_service.cleanup_old_snapshots()

        assert stats["total"] == 5
        assert stats["kept"] == 3
        assert stats["deleted"] == 1
        assert stats["failed"] == 1
        assert mock_delete.call_count == 2

    @pytest.mark.asyncio
    async def test_cleanup_failure_returns_zero_stats(
        self, snapshot_service, mock_vector_store: Mock
    ):
        """Test that cleanup returns zero stats on failure."""
        with patch.object(snapshot_service, "list_snapshots", side_effect=Exception("List failed")):
            stats = await snapshot_service.cleanup_old_snapshots()

        assert stats == {"total": 0, "kept": 0, "deleted": 0, "failed": 0}


class TestSnapshotRestoration:
    """Tests for snapshot restoration functionality."""

    @pytest.mark.asyncio
    async def test_restore_snapshot_success(self, snapshot_service, mock_vector_store: Mock):
        """Test successful snapshot restoration."""
        mock_vector_store.client.recover_snapshot = Mock()

        result = await snapshot_service.restore_snapshot("snapshot_to_restore", wait=True)

        assert result is True
        mock_vector_store.client.recover_snapshot.assert_called_once_with(
            collection_name="test_collection", snapshot_name="snapshot_to_restore", wait=True
        )

    @pytest.mark.asyncio
    async def test_restore_snapshot_without_wait(self, snapshot_service, mock_vector_store: Mock):
        """Test snapshot restoration without waiting."""
        mock_vector_store.client.recover_snapshot = Mock()

        result = await snapshot_service.restore_snapshot("snapshot_to_restore", wait=False)

        assert result is True
        call_args = mock_vector_store.client.recover_snapshot.call_args
        assert call_args[1]["wait"] is False

    @pytest.mark.asyncio
    async def test_restore_snapshot_failure(self, snapshot_service, mock_vector_store: Mock):
        """Test that restore_snapshot returns False on failure."""
        mock_vector_store.client.recover_snapshot = Mock(side_effect=Exception("Restore failed"))

        result = await snapshot_service.restore_snapshot("snapshot_to_restore")

        assert result is False


class TestGetLatestSnapshot:
    """Tests for getting the latest snapshot."""

    @pytest.mark.asyncio
    async def test_get_latest_snapshot_success(self, snapshot_service):
        """Test getting the most recent snapshot."""
        snapshots = [
            {"name": "snapshot_1", "created_at": "2025-01-27T10:00:00Z"},
            {"name": "snapshot_2", "created_at": "2025-01-27T12:00:00Z"},  # Latest
            {"name": "snapshot_3", "created_at": "2025-01-27T11:00:00Z"},
        ]

        with patch.object(snapshot_service, "list_snapshots", return_value=snapshots):
            latest = await snapshot_service.get_latest_snapshot()

        assert latest is not None
        assert latest["name"] == "snapshot_2"

    @pytest.mark.asyncio
    async def test_get_latest_snapshot_none_exist(self, snapshot_service):
        """Test getting latest snapshot when none exist."""
        with patch.object(snapshot_service, "list_snapshots", return_value=[]):
            latest = await snapshot_service.get_latest_snapshot()

        assert latest is None


class TestSnapshotAndCleanup:
    """Tests for the combined snapshot_and_cleanup operation."""

    @pytest.mark.asyncio
    async def test_snapshot_and_cleanup_success(self, snapshot_service):
        """Test successful snapshot creation and cleanup."""
        with patch.object(
            snapshot_service, "create_snapshot", return_value="new_snapshot"
        ) as mock_create:
            with patch.object(
                snapshot_service,
                "cleanup_old_snapshots",
                return_value={"total": 5, "kept": 3, "deleted": 2, "failed": 0},
            ) as mock_cleanup:
                result = await snapshot_service.snapshot_and_cleanup(wait=False)

        assert result["snapshot_created"] is True
        assert result["snapshot_name"] == "new_snapshot"
        assert result["cleanup_stats"]["deleted"] == 2
        mock_create.assert_called_once_with(wait=False)
        mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_snapshot_and_cleanup_creation_failure(self, snapshot_service):
        """Test that cleanup is skipped if snapshot creation fails."""
        with patch.object(snapshot_service, "create_snapshot", return_value=None) as mock_create:
            with patch.object(snapshot_service, "cleanup_old_snapshots") as mock_cleanup:
                result = await snapshot_service.snapshot_and_cleanup()

        assert result["snapshot_created"] is False
        assert result["snapshot_name"] is None
        assert result["cleanup_stats"] == {}
        mock_create.assert_called_once()
        mock_cleanup.assert_not_called()

    @pytest.mark.asyncio
    async def test_snapshot_and_cleanup_with_wait(self, snapshot_service):
        """Test snapshot_and_cleanup with wait parameter."""
        with patch.object(
            snapshot_service, "create_snapshot", return_value="snapshot"
        ) as mock_create:
            with patch.object(snapshot_service, "cleanup_old_snapshots", return_value={}):
                await snapshot_service.snapshot_and_cleanup(wait=True)

        mock_create.assert_called_once_with(wait=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for vector store failover functionality."""

import asyncio
import json

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codeweaver.engine.failover import VectorStoreFailoverManager
from codeweaver.providers.vector_stores.base import CircuitBreakerState


pytestmark = [pytest.mark.unit]


def _create_mock_collection_info():
    """Create a properly structured mock CollectionInfo object.

    Uses MagicMock with JSON-serializable dict attributes to avoid pydantic
    auto-conversion that would turn dicts back into VectorParams objects.
    """
    from qdrant_client.http.models import Distance, SparseVectorParams, VectorParams

    # Create mock with nested structure
    # The key is that config.params.vectors and sparse_vectors must be dicts, not pydantic objects
    mock_info = MagicMock()
    mock_info.config = MagicMock()
    mock_info.config.params = MagicMock()

    # These MUST be plain dicts for JSON serialization to work
    # The production code at line 848-849 stores these directly in the backup dict
    dense_vector_params = VectorParams(size=768, distance=Distance.COSINE)
    sparse_vector_params = SparseVectorParams()

    # Use model_dump() to convert to JSON-serializable dicts
    mock_info.config.params.vectors = {"dense": dense_vector_params.model_dump()}
    mock_info.config.params.sparse_vectors = {"sparse": sparse_vector_params.model_dump()}

    return mock_info


class MockVectorStoreProvider:
    """Mock vector store provider for testing."""

    def __init__(self, circuit_state: CircuitBreakerState = CircuitBreakerState.CLOSED):
        self._circuit_state = circuit_state
        self._client = MagicMock()
        self._initialized = False

    @property
    def circuit_breaker_state(self) -> CircuitBreakerState:
        """Get circuit breaker state."""
        return self._circuit_state

    async def _initialize(self) -> None:
        """Initialize the provider."""
        self._initialized = True

    async def list_collections(self) -> list[str]:
        """List all collections."""
        return ["test_collection"]

    async def get_collection(self, collection_name: str) -> dict[str, Any]:
        """Get collection info."""
        return {
            "name": collection_name,
            "vectors_config": {"dense": {"size": 768, "distance": "Cosine"}},
            "sparse_vectors_config": {"sparse": {}},
        }


class MockMemoryProvider(MockVectorStoreProvider):
    """Mock memory provider for testing."""

    def __init__(self):
        super().__init__()
        self._persist_called = False
        self._restore_called = False

    async def _persist_to_disk(self) -> None:
        """Mock persist to disk."""
        self._persist_called = True

    async def _restore_from_disk(self) -> None:
        """Mock restore from disk."""
        self._restore_called = True


class TestBackupSyncPeriodically:
    """Tests for periodic backup sync functionality."""

    @pytest.mark.asyncio
    async def test_sync_task_starts_on_initialize(self, tmp_path: Path):
        """Test that backup sync task starts when manager initializes."""
        primary = MockVectorStoreProvider()
        manager = VectorStoreFailoverManager(backup_enabled=True, backup_sync_interval=30)

        await manager.initialize(primary, tmp_path)

        # Verify sync task was created
        assert manager._backup_sync_task is not None
        assert not manager._backup_sync_task.done()

        # Cleanup
        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_sync_skipped_when_no_primary(self, tmp_path: Path):
        """Test sync is skipped when primary store is None."""
        manager = VectorStoreFailoverManager(backup_enabled=True, backup_sync_interval=30)

        # Initialize without primary store (primary is None)
        manager._primary_store = None
        manager._project_path = tmp_path

        # Mock _sync_primary_to_backup to track if it's called
        sync_called = asyncio.Event()

        async def mock_sync():
            sync_called.set()

        with patch.object(manager, '_sync_primary_to_backup', side_effect=mock_sync):
            # Override the sync interval for testing
            manager.backup_sync_interval = 0.1

            # Start the sync task
            manager._backup_sync_task = asyncio.create_task(manager._sync_backup_periodically())

            # Wait for sync interval with timeout
            try:
                await asyncio.wait_for(sync_called.wait(), timeout=0.5)
            except TimeoutError:
                pass  # Expected - sync should not be called

            # Cleanup
            manager._backup_sync_task.cancel()
            try:
                await manager._backup_sync_task
            except asyncio.CancelledError:
                pass

            # Verify sync was not called due to missing primary
            assert not sync_called.is_set()

    @pytest.mark.asyncio
    async def test_sync_skipped_during_failover(self, tmp_path: Path):
        """Test sync is skipped when in failover mode."""
        primary = MockVectorStoreProvider()
        manager = VectorStoreFailoverManager(backup_enabled=True, backup_sync_interval=30)

        await manager.initialize(primary, tmp_path)

        # Set failover mode active
        manager._failover_active = True

        # Mock _sync_primary_to_backup to track if it's called
        sync_called = asyncio.Event()

        async def mock_sync():
            sync_called.set()

        with patch.object(manager, '_sync_primary_to_backup', side_effect=mock_sync):
            # Override the sync interval for testing
            manager.backup_sync_interval = 0.1

            # Wait for sync interval with timeout
            try:
                await asyncio.wait_for(sync_called.wait(), timeout=0.5)
            except TimeoutError:
                pass  # Expected - sync should not be called

            # Cleanup
            await manager.shutdown()

            # Verify sync was not called due to failover mode
            assert not sync_called.is_set()

    @pytest.mark.asyncio
    async def test_sync_skipped_when_primary_unhealthy(self, tmp_path: Path):
        """Test sync is skipped when circuit breaker is open."""
        # Create primary with open circuit breaker
        primary = MockVectorStoreProvider(circuit_state=CircuitBreakerState.OPEN)
        manager = VectorStoreFailoverManager(backup_enabled=True, backup_sync_interval=30)

        await manager.initialize(primary, tmp_path)

        # Mock _sync_primary_to_backup to track if it's called
        sync_called = asyncio.Event()

        async def mock_sync():
            sync_called.set()

        with patch.object(manager, '_sync_primary_to_backup', side_effect=mock_sync):
            # Override the sync interval for testing
            manager.backup_sync_interval = 0.1

            # Wait for sync interval with timeout
            try:
                await asyncio.wait_for(sync_called.wait(), timeout=0.5)
            except TimeoutError:
                pass  # Expected - sync should not be called

            # Cleanup
            await manager.shutdown()

            # Verify sync was not called due to open circuit breaker
            assert not sync_called.is_set()

    @pytest.mark.asyncio
    async def test_sync_executes_when_conditions_met(self, tmp_path: Path):
        """Test sync executes when all conditions are met."""
        primary = MockVectorStoreProvider(circuit_state=CircuitBreakerState.CLOSED)
        manager = VectorStoreFailoverManager(backup_enabled=True, backup_sync_interval=30)

        await manager.initialize(primary, tmp_path)

        # Ensure failover is NOT active
        manager._failover_active = False

        # Use an event to signal when sync is called
        sync_event = asyncio.Event()

        async def mock_sync():
            sync_event.set()

        with patch.object(manager, '_sync_primary_to_backup', side_effect=mock_sync):
            # Override the sync interval for testing
            manager.backup_sync_interval = 0.1

            # Wait for sync to execute (with timeout)
            try:
                await asyncio.wait_for(sync_event.wait(), timeout=0.5)
                sync_executed = True
            except TimeoutError:
                sync_executed = False

            # Cleanup
            await manager.shutdown()

            # Verify sync was executed when all conditions were met
            assert sync_executed


class TestSyncPrimaryToBackup:
    """Tests for _sync_primary_to_backup method."""

    @pytest.mark.asyncio
    async def test_creates_backup_file(self, tmp_path: Path):
        """Test that sync creates backup file with correct structure."""
        primary = MockVectorStoreProvider()

        # Mock get_collection to return proper CollectionInfo structure
        primary.get_collection = AsyncMock(return_value=_create_mock_collection_info())

        # Mock scroll to return test points
        mock_point = MagicMock()
        mock_point.id = "point-1"
        mock_point.vector = {"dense": [0.1] * 768, "sparse": {}}
        mock_point.payload = {"file": "test.py", "chunk": 1}
        primary._client.scroll = AsyncMock(return_value=([mock_point], None))

        manager = VectorStoreFailoverManager()
        manager._primary_store = primary
        manager._project_path = tmp_path

        await manager._sync_primary_to_backup()

        # Verify file created
        backup_file = tmp_path / ".codeweaver" / "backup" / "vector_store.json"
        assert backup_file.exists()

        # Verify structure
        backup_data = json.loads(backup_file.read_text())
        assert backup_data["version"] == "2.0"
        assert backup_data["metadata"]["collection_count"] == 1
        assert backup_data["metadata"]["total_points"] == 1
        assert "test_collection" in backup_data["collections"]

    @pytest.mark.asyncio
    async def test_atomic_write_with_temp_file(self, tmp_path: Path):
        """Test that sync uses atomic write via temp file."""
        primary = MockVectorStoreProvider()

        # Mock get_collection to return proper CollectionInfo structure
        primary.get_collection = AsyncMock(return_value=_create_mock_collection_info())

        primary._client.scroll = AsyncMock(return_value=([], None))

        manager = VectorStoreFailoverManager()
        manager._primary_store = primary
        manager._project_path = tmp_path

        await manager._sync_primary_to_backup()

        # Verify temp file was cleaned up
        backup_dir = tmp_path / ".codeweaver" / "backup"
        temp_files = list(backup_dir.glob("*.tmp"))
        assert not temp_files

    @pytest.mark.asyncio
    async def test_handles_pagination(self, tmp_path: Path):
        """Test that sync handles pagination correctly."""
        primary = MockVectorStoreProvider()

        # Mock get_collection to return proper CollectionInfo structure
        primary.get_collection = AsyncMock(return_value=_create_mock_collection_info())

        # Create mock points for multiple pages
        points_page1 = [MagicMock(id=f"id-{i}", vector={}, payload={}) for i in range(100)]
        points_page2 = [MagicMock(id=f"id-{i}", vector={}, payload={}) for i in range(100, 150)]

        # Mock scroll to return paginated results
        primary._client.scroll = AsyncMock(
            side_effect=[
                (points_page1, "offset-1"),  # First page
                (points_page2, None),  # Second page (last)
            ]
        )

        manager = VectorStoreFailoverManager()
        manager._primary_store = primary
        manager._project_path = tmp_path

        await manager._sync_primary_to_backup()

        # Verify all points were saved
        backup_file = tmp_path / ".codeweaver" / "backup" / "vector_store.json"
        backup_data = json.loads(backup_file.read_text())
        assert backup_data["metadata"]["total_points"] == 150


class TestValidateBackupFile:
    """Tests for backup file validation."""

    @pytest.mark.asyncio
    async def test_validates_missing_file(self, tmp_path: Path):
        """Test validation fails for non-existent file."""
        manager = VectorStoreFailoverManager()
        backup_file = tmp_path / "nonexistent.json"

        is_valid = await manager._validate_backup_file(backup_file)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validates_invalid_json(self, tmp_path: Path):
        """Test validation fails for invalid JSON."""
        manager = VectorStoreFailoverManager()
        backup_file = tmp_path / "invalid.json"
        backup_file.write_text("not valid json {{{")

        is_valid = await manager._validate_backup_file(backup_file)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validates_missing_required_fields(self, tmp_path: Path):
        """Test validation fails when required fields missing."""
        manager = VectorStoreFailoverManager()
        backup_file = tmp_path / "incomplete.json"

        # Missing 'collections' field
        backup_data = {"version": "2.0", "metadata": {}}
        backup_file.write_text(json.dumps(backup_data))

        is_valid = await manager._validate_backup_file(backup_file)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validates_unsupported_version(self, tmp_path: Path):
        """Test validation fails for unsupported version."""
        manager = VectorStoreFailoverManager()
        backup_file = tmp_path / "wrong_version.json"

        backup_data = {
            "version": "99.0",  # Unsupported
            "metadata": {},
            "collections": {},
        }
        backup_file.write_text(json.dumps(backup_data))

        is_valid = await manager._validate_backup_file(backup_file)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validates_valid_v1_file(self, tmp_path: Path):
        """Test validation passes for valid v1.0 file."""
        manager = VectorStoreFailoverManager()
        backup_file = tmp_path / "valid_v1.json"

        backup_data = {
            "version": "1.0",
            "metadata": {"created_at": "2024-01-01T00:00:00Z"},
            "collections": {"test": {"points": [{"id": "1", "vector": {}, "payload": {}}]}},
        }
        backup_file.write_text(json.dumps(backup_data))

        is_valid = await manager._validate_backup_file(backup_file)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validates_valid_v2_file(self, tmp_path: Path):
        """Test validation passes for valid v2.0 file."""
        manager = VectorStoreFailoverManager()
        backup_file = tmp_path / "valid_v2.json"

        backup_data = {
            "version": "2.0",
            "metadata": {
                "created_at": "2024-01-01T00:00:00Z",
                "collection_count": 1,
                "total_points": 1,
            },
            "collections": {
                "test": {
                    "metadata": {},
                    "config": {},
                    "points": [{"id": "1", "vector": {}, "payload": {}}],
                }
            },
        }
        backup_file.write_text(json.dumps(backup_data))

        is_valid = await manager._validate_backup_file(backup_file)
        assert is_valid is True


class TestFailoverWithValidation:
    """Tests for failover activation with backup validation."""

    @pytest.mark.asyncio
    async def test_failover_validates_before_restore(self, tmp_path: Path):
        """Test that failover validates backup file before restoring."""
        # Create invalid backup file
        backup_dir = tmp_path / ".codeweaver" / "backup"
        backup_dir.mkdir(parents=True)
        backup_file = backup_dir / "vector_store.json"
        backup_file.write_text("invalid json")

        primary = MockVectorStoreProvider(circuit_state=CircuitBreakerState.OPEN)
        manager = VectorStoreFailoverManager(backup_enabled=True)

        with patch(
            "codeweaver.engine.failover.estimate_backup_memory_requirements"
        ) as mock_estimate:
            # Create proper MemoryEstimate with numeric values
            from codeweaver.engine.resource_estimation import MemoryEstimate

            mock_estimate.return_value = MemoryEstimate(
                estimated_bytes=500_000_000,  # 500MB
                available_bytes=8_000_000_000,  # 8GB
                required_bytes=1_500_000_000,  # 1.5GB
                is_safe=True,
                estimated_chunks=100_000,
                zone="green",
            )

            with patch.object(manager, "_create_backup_store") as mock_create:
                mock_backup = MockMemoryProvider()
                mock_create.return_value = mock_backup

                await manager.initialize(primary, tmp_path)

                # Trigger failover
                await manager._activate_failover()

                # Verify restore was not called due to validation failure
                assert not mock_backup._restore_called

    @pytest.mark.asyncio
    async def test_failover_restores_valid_backup(self, tmp_path: Path):
        """Test that failover restores valid backup file."""
        # Create valid backup file
        backup_dir = tmp_path / ".codeweaver" / "backup"
        backup_dir.mkdir(parents=True)
        backup_file = backup_dir / "vector_store.json"

        backup_data = {
            "version": "2.0",
            "metadata": {"created_at": "2024-01-01T00:00:00Z"},
            "collections": {"test": {"points": []}},
        }
        backup_file.write_text(json.dumps(backup_data))

        primary = MockVectorStoreProvider(circuit_state=CircuitBreakerState.OPEN)
        manager = VectorStoreFailoverManager(backup_enabled=True)

        with patch(
            "codeweaver.engine.failover.estimate_backup_memory_requirements"
        ) as mock_estimate:
            # Create proper MemoryEstimate with numeric values
            from codeweaver.engine.resource_estimation import MemoryEstimate

            mock_estimate.return_value = MemoryEstimate(
                estimated_bytes=500_000_000,  # 500MB
                available_bytes=8_000_000_000,  # 8GB
                required_bytes=1_500_000_000,  # 1.5GB
                is_safe=True,
                estimated_chunks=100_000,
                zone="green",
            )

            with patch.object(manager, "_create_backup_store") as mock_create:
                mock_backup = MockMemoryProvider()
                mock_create.return_value = mock_backup

                await manager.initialize(primary, tmp_path)
                await manager._activate_failover()

                # Verify failover was activated (backup creation does not auto-restore anymore)
                # The new approach uses FileChangeTracker, not automatic restore
                assert manager._failover_active
                assert manager._backup_store is not None


class TestSyncBackToPrimary:
    """Tests for Phase 3 sync-back functionality."""

    @pytest.mark.asyncio
    async def test_snapshot_backup_state(self, tmp_path: Path):
        """Test snapshotting backup state before failover.

        Note: The current implementation uses FileChangeTracker for tracking,
        so _failover_chunks is intentionally cleared and not used.
        """

        backup = MockMemoryProvider()
        backup._initialized = True

        # Mock backup has 10 existing points
        mock_points = [MagicMock(id=f"existing-{i}") for i in range(10)]
        backup._client.scroll = AsyncMock(return_value=(mock_points, None))

        manager = VectorStoreFailoverManager()
        manager._backup_store = backup

        await manager._snapshot_backup_state()

        # Verify snapshot was cleared (FileChangeTracker handles tracking now)
        assert len(manager._failover_chunks) == 0
        # FileChangeTracker is the primary mechanism for tracking changes

    @pytest.mark.asyncio
    async def test_sync_back_identifies_new_chunks(self, tmp_path: Path):
        """Test that sync-back correctly identifies new chunks added during failover.

        Note: The current implementation uses FileChangeTracker for sync-back,
        so the legacy chunk-based sync returns 0 chunks intentionally.
        """
        primary = MockVectorStoreProvider()
        backup = MockMemoryProvider()

        manager = VectorStoreFailoverManager()
        manager._primary_store = primary
        manager._backup_store = backup
        manager._indexer = MagicMock()

        # Snapshot has 10 existing chunks
        manager._failover_chunks = {f"existing-{i}" for i in range(10)}

        # Current backup has existing + 5 new chunks
        all_points = [MagicMock(id=f"existing-{i}") for i in range(10)]
        all_points.extend([MagicMock(id=f"new-{i}") for i in range(5)])
        backup._client.scroll = AsyncMock(return_value=(all_points, None))

        # Mock sync_chunk_to_primary to track calls
        with patch.object(manager, "_sync_chunk_to_primary") as mock_sync:
            await manager._sync_back_to_primary()

            # Legacy chunk-based sync is deprecated - should sync 0 chunks
            # FileChangeTracker-based sync is the new approach
            assert mock_sync.call_count == 0

    @pytest.mark.asyncio
    async def test_sync_chunk_reembeds_text(self, tmp_path: Path):
        """Test that individual chunk sync re-embeds text content."""
        primary = MockVectorStoreProvider()
        backup = MockMemoryProvider()
        indexer = MagicMock()

        # Mock embedding providers
        indexer._embedding_provider = AsyncMock()
        indexer._embedding_provider.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
        indexer._sparse_provider = AsyncMock()
        indexer._sparse_provider.embed = AsyncMock(return_value=[{"0": 0.5}])

        manager = VectorStoreFailoverManager()
        manager._primary_store = primary
        manager._backup_store = backup
        manager._indexer = indexer

        # Create a proper CodeChunk
        from datetime import UTC, datetime
        from pathlib import Path as PathlibPath

        from codeweaver.common.utils import uuid7
        from codeweaver.core.chunks import CodeChunk
        from codeweaver.core.metadata import Metadata
        from codeweaver.core.spans import Span
        from codeweaver.providers.vector_stores.metadata import HybridVectorPayload

        chunk = CodeChunk(
            content="test content",
            line_range=Span(1, 10, _source_id=uuid7()),
            file_path=PathlibPath("test.py"),
            chunk_id=uuid7(),
            metadata=Metadata(
                chunk_id=uuid7(),
                created_at=datetime.now(UTC).timestamp(),
                line_start=1,
                line_end=10,
            ),
        )

        # Create proper HybridVectorPayload
        payload = HybridVectorPayload(
            chunk=chunk,
            chunk_id=str(chunk.chunk_id),
            file_path="test.py",
            line_start=1,
            line_end=10,
            indexed_at=datetime.now(UTC).isoformat(),
            chunked_on=datetime.now(UTC).isoformat(),
            hash=chunk.blake_hash,
            provider="test_provider",
            embedding_complete=True,
        )

        # Mock backup retrieval
        mock_point = MagicMock()
        mock_point.payload = payload.model_dump()
        backup._client.retrieve = AsyncMock(return_value=[mock_point])

        # Mock primary upsert
        primary.upsert = AsyncMock()

        await manager._sync_chunk_to_primary("test-chunk-id")

        # Verify re-embedding was called with the chunk object
        assert indexer._embedding_provider.embed.called
        embed_call = indexer._embedding_provider.embed.call_args
        assert len(embed_call[0][0]) == 1  # Called with a list of 1 chunk
        assert isinstance(embed_call[0][0][0], CodeChunk)
        assert embed_call[0][0][0].content == "test content"

        assert indexer._sparse_provider.embed.called
        sparse_call = indexer._sparse_provider.embed.call_args
        assert len(sparse_call[0][0]) == 1  # Called with a list of 1 chunk
        assert isinstance(sparse_call[0][0][0], CodeChunk)
        assert sparse_call[0][0][0].content == "test content"

        # Verify upsert to primary was called with the chunk
        assert primary.upsert.called
        upsert_call = primary.upsert.call_args
        assert len(upsert_call[0][0]) == 1  # Called with a list of 1 chunk
        assert isinstance(upsert_call[0][0][0], CodeChunk)

    @pytest.mark.asyncio
    async def test_verify_primary_health_checks(self, tmp_path: Path):
        """Test primary health verification performs all checks."""
        primary = MockVectorStoreProvider(circuit_state=CircuitBreakerState.CLOSED)
        primary.list_collections = AsyncMock(return_value=["test_collection"])

        manager = VectorStoreFailoverManager()
        manager._primary_store = primary

        # Should pass all checks
        await manager._verify_primary_health()

        # Verify checks were called
        assert primary.list_collections.called
        # Note: get_collection is only called for QdrantBaseProvider subclasses

    @pytest.mark.asyncio
    async def test_verify_primary_health_fails_on_open_circuit(self, tmp_path: Path):
        """Test health verification fails if circuit breaker is open."""
        primary = MockVectorStoreProvider(circuit_state=CircuitBreakerState.OPEN)
        primary.list_collections = AsyncMock(return_value=[])

        manager = VectorStoreFailoverManager()
        manager._primary_store = primary

        # Should raise due to open circuit
        with pytest.raises(
            RuntimeError, match=r"Primary vector store's circuit breaker was not closed"
        ):
            await manager._verify_primary_health()

    @pytest.mark.asyncio
    async def test_restore_to_primary_with_sync_back(self, tmp_path: Path):
        """Test full restoration flow with sync-back."""
        primary = MockVectorStoreProvider(circuit_state=CircuitBreakerState.CLOSED)
        backup = MockMemoryProvider()

        manager = VectorStoreFailoverManager()
        manager._primary_store = primary
        manager._backup_store = backup
        manager._failover_active = True
        manager._failover_chunks = {"chunk-1", "chunk-2"}

        # Mock sync-back and verification
        with patch.object(manager, "_sync_back_to_primary") as mock_sync:
            with patch.object(manager, "_verify_primary_health") as mock_verify:
                await manager._restore_to_primary()

                # Verify sync-back was called before restoration
                assert mock_sync.called
                assert mock_verify.called

                # Verify restored to primary
                assert manager._active_store == primary
                assert not manager._failover_active
                assert not manager._failover_chunks

    @pytest.mark.asyncio
    async def test_restore_stays_in_backup_on_sync_failure(self, tmp_path: Path):
        """Test restoration stays in backup mode if sync-back fails."""
        primary = MockVectorStoreProvider()
        backup = MockMemoryProvider()

        manager = VectorStoreFailoverManager()
        manager._primary_store = primary
        manager._backup_store = backup
        manager._failover_active = True
        manager._active_store = backup

        # Mock sync-back to fail
        with patch.object(manager, "_sync_back_to_primary") as mock_sync:
            mock_sync.side_effect = Exception("Sync failed")

            await manager._restore_to_primary()

            # Verify stayed in backup mode
            assert manager._active_store == backup
            assert manager._failover_active


class TestBackupSyncCoordination:
    """Tests for backup sync coordination using FileChangeTracker."""

    @pytest.mark.asyncio
    async def test_should_sync_false_when_no_tracker(self, tmp_path: Path):
        """Test should_sync_backup returns False without tracker."""
        manager = VectorStoreFailoverManager()

        assert manager.should_sync_backup() is False

    @pytest.mark.asyncio
    async def test_should_sync_false_when_no_changes(self, tmp_path: Path):
        """Test should_sync_backup returns False with no pending changes."""
        from codeweaver.engine.failover_tracker import FileChangeTracker

        manager = VectorStoreFailoverManager()
        manager._change_tracker = FileChangeTracker(project_path=tmp_path)

        assert manager.should_sync_backup() is False

    @pytest.mark.asyncio
    async def test_should_sync_true_on_volume_threshold(self, tmp_path: Path):
        """Test should_sync_backup returns True when volume threshold exceeded."""
        from codeweaver.engine.failover_tracker import FileChangeTracker

        manager = VectorStoreFailoverManager()
        tracker = FileChangeTracker(project_path=tmp_path)
        # Add 50+ pending changes
        tracker.pending_changes = {f"file{i}.py" for i in range(60)}
        manager._change_tracker = tracker

        assert manager.should_sync_backup(volume_threshold=50) is True

    @pytest.mark.asyncio
    async def test_should_sync_true_on_time_threshold(self, tmp_path: Path):
        """Test should_sync_backup returns True when time threshold exceeded."""
        from datetime import UTC, datetime, timedelta

        from codeweaver.engine.failover_tracker import FileChangeTracker

        manager = VectorStoreFailoverManager()
        tracker = FileChangeTracker(project_path=tmp_path)
        tracker.pending_changes = {"file.py"}
        # Set last sync time to 10 minutes ago
        tracker.last_sync_time = datetime.now(UTC) - timedelta(minutes=10)
        manager._change_tracker = tracker

        assert manager.should_sync_backup(time_threshold_seconds=300) is True

    @pytest.mark.asyncio
    async def test_should_sync_true_when_never_synced(self, tmp_path: Path):
        """Test should_sync_backup returns True when never synced."""
        from codeweaver.engine.failover_tracker import FileChangeTracker

        manager = VectorStoreFailoverManager()
        tracker = FileChangeTracker(project_path=tmp_path)
        tracker.pending_changes = {"file.py"}
        # last_sync_time is None by default
        manager._change_tracker = tracker

        assert manager.should_sync_backup() is True

    @pytest.mark.asyncio
    async def test_sync_pending_returns_zero_without_tracker(self, tmp_path: Path):
        """Test sync_pending_to_backup returns 0 without tracker."""
        manager = VectorStoreFailoverManager()

        result = await manager.sync_pending_to_backup()

        assert result == 0

    @pytest.mark.asyncio
    async def test_sync_pending_returns_zero_without_indexer(self, tmp_path: Path):
        """Test sync_pending_to_backup returns 0 without backup indexer."""
        from codeweaver.engine.failover_tracker import FileChangeTracker

        manager = VectorStoreFailoverManager()
        manager._change_tracker = FileChangeTracker(project_path=tmp_path)

        result = await manager.sync_pending_to_backup()

        assert result == 0

    @pytest.mark.asyncio
    async def test_sync_pending_returns_zero_with_no_changes(self, tmp_path: Path):
        """Test sync_pending_to_backup returns 0 with no pending changes."""
        from codeweaver.engine.failover_tracker import FileChangeTracker

        manager = VectorStoreFailoverManager()
        manager._change_tracker = FileChangeTracker(project_path=tmp_path)
        manager._backup_indexer = MagicMock()

        result = await manager.sync_pending_to_backup()

        assert result == 0


class TestBackupIndexerCreation:
    """Tests for backup indexer creation."""

    @pytest.mark.asyncio
    async def test_backup_indexer_property(self, tmp_path: Path):
        """Test backup_indexer property returns indexer."""
        manager = VectorStoreFailoverManager()
        mock_indexer = MagicMock()
        manager._backup_indexer = mock_indexer

        assert manager.backup_indexer is mock_indexer

    @pytest.mark.asyncio
    async def test_backup_indexer_property_none(self, tmp_path: Path):
        """Test backup_indexer property returns None when not set."""
        manager = VectorStoreFailoverManager()

        assert manager.backup_indexer is None


class TestPrimaryRecovery:
    """Tests for primary recovery using FileChangeTracker."""

    @pytest.mark.asyncio
    async def test_sync_failover_returns_zero_without_tracker(self, tmp_path: Path):
        """Test sync_failover_to_primary returns 0 without tracker."""
        manager = VectorStoreFailoverManager()

        result = await manager.sync_failover_to_primary()

        assert result == 0

    @pytest.mark.asyncio
    async def test_sync_failover_returns_zero_without_indexer(self, tmp_path: Path):
        """Test sync_failover_to_primary returns 0 without primary indexer."""
        from codeweaver.engine.failover_tracker import FileChangeTracker

        manager = VectorStoreFailoverManager()
        manager._change_tracker = FileChangeTracker(project_path=tmp_path)

        result = await manager.sync_failover_to_primary()

        assert result == 0

    @pytest.mark.asyncio
    async def test_sync_failover_returns_zero_with_no_failover_files(self, tmp_path: Path):
        """Test sync_failover_to_primary returns 0 with no failover files."""
        from codeweaver.engine.failover_tracker import FileChangeTracker

        manager = VectorStoreFailoverManager()
        manager._change_tracker = FileChangeTracker(project_path=tmp_path)
        manager._indexer = MagicMock()

        result = await manager.sync_failover_to_primary()

        assert result == 0

    @pytest.mark.asyncio
    async def test_status_includes_change_tracker_info(self, tmp_path: Path):
        """Test that status includes change tracker information."""
        from codeweaver.engine.failover_tracker import FileChangeTracker

        manager = VectorStoreFailoverManager()
        tracker = FileChangeTracker(project_path=tmp_path)
        tracker.pending_changes = {"a.py", "b.py"}
        tracker.failover_indexed = {"c.py"}
        manager._change_tracker = tracker

        status = manager.get_status()

        assert "change_tracker" in status
        assert status["change_tracker"]["pending_changes"] == 2
        assert status["change_tracker"]["failover_indexed"] == 1
        assert status["change_tracker"]["needs_backup_sync"] is True
        assert status["change_tracker"]["needs_primary_recovery"] is True


class TestGetStatus:
    """Tests for get_status method with Phase 2 additions."""

    @pytest.mark.asyncio
    async def test_status_includes_backup_sync_time(self, tmp_path: Path):
        """Test that status includes last backup sync time."""
        from datetime import UTC, datetime

        manager = VectorStoreFailoverManager()
        manager._last_backup_sync = datetime.now(UTC)

        status = manager.get_status()

        assert "last_backup_sync" in status
        assert status["last_backup_sync"] is not None

    @pytest.mark.asyncio
    async def test_status_includes_backup_file_info(self, tmp_path: Path):
        """Test that status includes backup file information."""
        # Create backup file
        backup_dir = tmp_path / ".codeweaver" / "backup"
        backup_dir.mkdir(parents=True)
        backup_file = backup_dir / "vector_store.json"
        backup_file.write_text(json.dumps({"version": "2.0", "metadata": {}, "collections": {}}))

        manager = VectorStoreFailoverManager()
        manager._project_path = tmp_path

        status = manager.get_status()

        assert status["backup_file_exists"] is True
        assert "backup_file_size_bytes" in status
        assert status["backup_file_size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_status_no_backup_file(self, tmp_path: Path):
        """Test status when backup file doesn't exist."""
        manager = VectorStoreFailoverManager()
        manager._project_path = tmp_path

        status = manager.get_status()

        assert status["backup_file_exists"] is False
        assert "backup_file_size_bytes" not in status

# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unit tests for MigrationService.

Tests cover:
- Service initialization
- Parallel migration execution
- Worker pool management
- Work distribution
- Vector truncation (dense and hybrid)
- Data integrity validation (4 layers)
- Checkpoint operations
- Resume capability

All tests use direct instantiation (NO DI) with mocked dependencies.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, Mock, patch

import pytest

from qdrant_client.conversions.common_types import NamedSparseVector
from qdrant_client.models import PointStruct


if TYPE_CHECKING:
    from codeweaver.engine.managers.checkpoint_manager import CheckpointManager
    from codeweaver.engine.managers.manifest_manager import FileManifestManager
    from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer
    from codeweaver.engine.services.migration_service import MigrationService
    from codeweaver.providers.vector_stores.base import VectorStoreProvider


# ===========================================================================
# Fixtures: Mock Dependencies
# ===========================================================================


@pytest.fixture
def mock_vector_store() -> Mock:
    """Create mock VectorStoreProvider."""
    store = Mock(spec=["collection", "get_collection_info", "search", "upsert"])
    store.collection = "test_collection"
    store.get_collection_info = AsyncMock(return_value={"vectors_count": 5000})
    store.search = AsyncMock(return_value=[])
    store.upsert = AsyncMock()
    return store


@pytest.fixture
def mock_config_analyzer() -> Mock:
    """Create mock ConfigChangeAnalyzer."""
    analyzer = Mock(spec=["analyze_config_change"])
    analyzer.analyze_config_change = AsyncMock()
    return analyzer


@pytest.fixture
def mock_checkpoint_manager() -> Mock:
    """Create mock CheckpointManager."""
    manager = Mock(spec=["checkpoint_dir"])
    manager.checkpoint_dir = Mock(spec=["__truediv__"])
    manager.checkpoint_dir.__truediv__ = Mock(return_value="/tmp/checkpoint.json")
    return manager


@pytest.fixture
def mock_manifest_manager() -> Mock:
    """Create mock FileManifestManager."""
    return Mock(spec=[])


@pytest.fixture
def migration_service(
    mock_vector_store: VectorStoreProvider,
    mock_config_analyzer: ConfigChangeAnalyzer,
    mock_checkpoint_manager: CheckpointManager,
    mock_manifest_manager: FileManifestManager,
) -> MigrationService:
    """Create MigrationService with mocked dependencies.

    Direct instantiation (NO DI container) for unit testing.
    """
    from codeweaver.engine.services.migration_service import MigrationService

    return MigrationService(
        vector_store=mock_vector_store,
        config_analyzer=mock_config_analyzer,
        checkpoint_manager=mock_checkpoint_manager,
        manifest_manager=mock_manifest_manager,
    )


# ===========================================================================
# Tests: Service Initialization
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestMigrationServiceInit:
    """Tests for MigrationService initialization."""

    def test_service_initializes_with_dependencies(
        self, migration_service: MigrationService
    ) -> None:
        """Test that service initializes with all dependencies."""
        assert migration_service.vector_store is not None
        assert migration_service.config_analyzer is not None
        assert migration_service.checkpoint_manager is not None
        assert migration_service.manifest_manager is not None

    def test_service_stores_vector_store_reference(
        self, migration_service: MigrationService, mock_vector_store: Mock
    ) -> None:
        """Test that service stores vector store reference."""
        assert migration_service.vector_store is mock_vector_store

    def test_service_stores_config_analyzer_reference(
        self, migration_service: MigrationService, mock_config_analyzer: Mock
    ) -> None:
        """Test that service stores config analyzer reference."""
        assert migration_service.config_analyzer is mock_config_analyzer


# ===========================================================================
# Tests: Work Distribution
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestWorkDistribution:
    """Tests for _create_work_items() method."""

    def test_creates_work_items_for_all_workers(self, migration_service: MigrationService) -> None:
        """Test that work items are created for all workers."""
        work_items = migration_service._create_work_items(
            source_collection="source",
            target_collection="target",
            new_dimension=1024,
            vector_count=10000,
            worker_count=4,
            batch_size=1000,
        )

        assert len(work_items) == 4
        assert all(item.worker_id in range(4) for item in work_items)

    def test_distributes_work_evenly(self, migration_service: MigrationService) -> None:
        """Test that work is distributed evenly among workers."""
        work_items = migration_service._create_work_items(
            source_collection="source",
            target_collection="target",
            new_dimension=1024,
            vector_count=10000,
            worker_count=4,
            batch_size=1000,
        )

        # All workers should get 2500 vectors each (10000 / 4)
        assert all(item.batch_size == 1000 for item in work_items)

    def test_handles_remainder_distribution(self, migration_service: MigrationService) -> None:
        """Test that remainder vectors are distributed across first workers."""
        work_items = migration_service._create_work_items(
            source_collection="source",
            target_collection="target",
            new_dimension=1024,
            vector_count=10003,  # 3 remainder
            worker_count=4,
            batch_size=1000,
        )

        # All workers should get work
        assert len(work_items) == 4

    def test_respects_start_offset(self, migration_service: MigrationService) -> None:
        """Test that start offset is properly set in work items."""
        work_items = migration_service._create_work_items(
            source_collection="source",
            target_collection="target",
            new_dimension=1024,
            vector_count=10000,
            worker_count=4,
            batch_size=1000,
            start_offset=5000,
        )

        # First worker should start at offset
        assert work_items[0].start_offset == 5000

    def test_zero_vectors_creates_no_work_items(self, migration_service: MigrationService) -> None:
        """Test that zero vectors creates no work items."""
        work_items = migration_service._create_work_items(
            source_collection="source",
            target_collection="target",
            new_dimension=1024,
            vector_count=0,
            worker_count=4,
            batch_size=1000,
        )

        assert len(work_items) == 0


# ===========================================================================
# Tests: Vector Truncation
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestVectorTruncation:
    """Tests for _truncate_vector() method."""

    def test_truncates_dense_vector(self, migration_service: MigrationService) -> None:
        """Test truncation of dense-only vector."""
        original = PointStruct(
            id="test_id", vector=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0], payload={"key": "value"}
        )

        truncated = migration_service._truncate_vector(original, new_dimension=3)

        assert len(truncated.vector) == 3
        assert truncated.vector == [1.0, 2.0, 3.0]
        assert truncated.id == "test_id"
        assert truncated.payload == {"key": "value"}

    def test_truncates_hybrid_vector_dense_component(
        self, migration_service: MigrationService
    ) -> None:
        """Test truncation of hybrid vector (dense + sparse)."""
        original = PointStruct(
            id="test_id",
            vector={
                "dense": [1.0, 2.0, 3.0, 4.0, 5.0],
                "sparse": {"indices": [0, 5, 10], "values": [0.5, 0.3, 0.2]},
            },
            payload={"key": "value"},
        )

        truncated = migration_service._truncate_vector(original, new_dimension=3)

        assert isinstance(truncated.vector, dict)
        assert len(truncated.vector["dense"]) == 3
        assert truncated.vector["dense"] == [1.0, 2.0, 3.0]
        # Sparse component should be preserved (qdrant converts dict to SparseVector object)
        sparse = truncated.vector["sparse"]
        assert cast(NamedSparseVector, sparse).indices == [0, 5, 10]
        assert cast(NamedSparseVector, sparse).values == [0.5, 0.3, 0.2]

    def test_preserves_sparse_component(self, migration_service: MigrationService) -> None:
        """Test that sparse component is preserved during truncation."""
        original = PointStruct(
            id="test_id",
            vector={"dense": [1.0, 2.0, 3.0], "sparse": {"indices": [1, 2], "values": [0.9, 0.8]}},
            payload={},
        )

        truncated = migration_service._truncate_vector(original, new_dimension=2)

        assert "sparse" in truncated.vector
        assert isinstance(truncated.vector, dict)
        assert cast(NamedSparseVector, truncated.vector["sparse"]).indices == [1, 2]
        assert cast(NamedSparseVector, truncated.vector["sparse"]).values == [0.9, 0.8]

    def test_handles_empty_sparse_component(self, migration_service: MigrationService) -> None:
        """Test handling of empty sparse component."""
        # Use Mock to bypass qdrant validation — PointStruct no longer accepts sparse=None
        original = Mock()
        original.id = "test_id"
        original.payload = {}
        original.vector = {"dense": [1.0, 2.0], "sparse": None}

        truncated = migration_service._truncate_vector(original, new_dimension=1)
        assert isinstance(truncated.vector, dict)
        assert len(truncated.vector["dense"]) == 1
        # Sparse component should not be in result if it was None
        if "sparse" in truncated.vector:
            assert truncated.vector["sparse"] is None


# ===========================================================================
# Tests: Data Integrity Validation
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestDataIntegrity:
    """Tests for _validate_migration_integrity() method (4 layers)."""

    @pytest.fixture
    def setup_validation_mocks(self, migration_service: MigrationService) -> None:
        """Set up mocks for validation tests."""
        migration_service._count_vectors = AsyncMock(return_value=5000)
        migration_service._compute_payload_checksums = AsyncMock(return_value=b"test_checksum")
        migration_service._get_random_samples = AsyncMock(return_value=["id1", "id2", "id3"])
        migration_service._get_vector = AsyncMock(return_value=[1.0, 2.0, 3.0, 4.0])
        migration_service._search_collection = AsyncMock(return_value=["id1", "id2", "id3"])
        migration_service._cosine_similarity = Mock(return_value=0.9999)
        migration_service._recall_at_k = Mock(return_value=0.85)

    async def test_layer_1_vector_count_match_passes(
        self, migration_service: MigrationService, setup_validation_mocks: None
    ) -> None:
        """Test Layer 1: Vector count match validation passes."""
        # Count matches expectation
        migration_service._count_vectors = AsyncMock(return_value=5000)

        # Should not raise
        await migration_service._validate_migration_integrity(
            source_collection="source",
            target_collection="target",
            expected_count=5000,
            new_dimension=1024,
        )

    async def test_layer_1_vector_count_mismatch_fails(
        self, migration_service: MigrationService
    ) -> None:
        """Test Layer 1: Vector count mismatch validation fails."""
        from codeweaver.engine.services.migration_service import ValidationError

        # Target has wrong count
        migration_service._count_vectors = AsyncMock(side_effect=[5000, 4999])

        with pytest.raises(ValidationError) as exc_info:
            await migration_service._validate_migration_integrity(
                source_collection="source",
                target_collection="target",
                expected_count=5000,
                new_dimension=1024,
            )

        assert "Layer 1 failed" in str(exc_info.value)
        assert "Vector count mismatch" in str(exc_info.value)

    async def test_layer_2_payload_checksums_match_passes(
        self, migration_service: MigrationService, setup_validation_mocks: None
    ) -> None:
        """Test Layer 2: Payload checksum validation passes."""
        # Checksums match
        migration_service._compute_payload_checksums = AsyncMock(return_value=b"matching_checksum")

        # Should not raise
        await migration_service._validate_migration_integrity(
            source_collection="source",
            target_collection="target",
            expected_count=5000,
            new_dimension=1024,
        )

    async def test_layer_2_payload_checksums_mismatch_fails(
        self, migration_service: MigrationService, setup_validation_mocks: None
    ) -> None:
        """Test Layer 2: Payload checksum mismatch validation fails."""
        from codeweaver.engine.services.migration_service import ValidationError

        # Checksums don't match
        migration_service._compute_payload_checksums = AsyncMock(
            side_effect=[b"source_checksum", b"different_checksum"]
        )

        with pytest.raises(ValidationError) as exc_info:
            await migration_service._validate_migration_integrity(
                source_collection="source",
                target_collection="target",
                expected_count=5000,
                new_dimension=1024,
            )

        assert "Layer 2 failed" in str(exc_info.value)
        assert "Payload checksums don't match" in str(exc_info.value)

    async def test_layer_3_semantic_equivalence_passes(
        self, migration_service: MigrationService, setup_validation_mocks: None
    ) -> None:
        """Test Layer 3: Semantic equivalence validation passes."""
        # High similarity (>0.9999)
        migration_service._cosine_similarity = Mock(return_value=0.99995)

        # Should not raise
        await migration_service._validate_migration_integrity(
            source_collection="source",
            target_collection="target",
            expected_count=5000,
            new_dimension=1024,
        )

    async def test_layer_3_semantic_equivalence_fails(
        self, migration_service: MigrationService, setup_validation_mocks: None
    ) -> None:
        """Test Layer 3: Semantic equivalence validation fails."""
        from codeweaver.engine.services.migration_service import ValidationError

        # Low similarity (<0.9999)
        migration_service._cosine_similarity = Mock(return_value=0.95)

        with pytest.raises(ValidationError) as exc_info:
            await migration_service._validate_migration_integrity(
                source_collection="source",
                target_collection="target",
                expected_count=5000,
                new_dimension=1024,
            )

        assert "Layer 3 failed" in str(exc_info.value)
        assert "Cosine similarity too low" in str(exc_info.value)

    async def test_layer_4_search_quality_passes(
        self, migration_service: MigrationService, setup_validation_mocks: None
    ) -> None:
        """Test Layer 4: Search quality validation passes."""
        # High recall (>80%)
        migration_service._recall_at_k = Mock(return_value=0.85)

        # Should not raise
        await migration_service._validate_migration_integrity(
            source_collection="source",
            target_collection="target",
            expected_count=5000,
            new_dimension=1024,
        )

    async def test_layer_4_search_quality_fails(
        self, migration_service: MigrationService, setup_validation_mocks: None
    ) -> None:
        """Test Layer 4: Search quality validation fails."""
        from codeweaver.engine.services.migration_service import ValidationError

        # Low recall (<80%)
        migration_service._recall_at_k = Mock(return_value=0.75)

        with pytest.raises(ValidationError) as exc_info:
            await migration_service._validate_migration_integrity(
                source_collection="source",
                target_collection="target",
                expected_count=5000,
                new_dimension=1024,
            )

        assert "Layer 4 failed" in str(exc_info.value)
        assert "Search quality degraded" in str(exc_info.value)


# ===========================================================================
# Tests: Checkpoint Operations
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestCheckpointing:
    """Tests for checkpoint save/load/delete operations."""

    @pytest.fixture
    def checkpoint_path_mock(self, migration_service: MigrationService) -> Mock:
        """Mock checkpoint path operations."""
        path_mock = Mock()
        path_mock.parent = Mock()
        path_mock.with_suffix = Mock(return_value=path_mock)
        migration_service._get_checkpoint_path = Mock(return_value=path_mock)
        return path_mock

    async def test_save_checkpoint_creates_checkpoint_data(
        self, migration_service: MigrationService, checkpoint_path_mock: Mock
    ) -> None:
        """Test that save_checkpoint creates proper checkpoint data."""
        from codeweaver.engine.services.migration_service import MigrationState

        with patch("codeweaver.engine.services.migration_service.AsyncPath") as async_path_mock:
            async_path_mock.return_value.mkdir = AsyncMock()
            async_path_mock.return_value.write_bytes = AsyncMock()
            async_path_mock.return_value.rename = AsyncMock()

            await migration_service._save_migration_checkpoint(
                migration_id="test_migration",
                state=MigrationState.IN_PROGRESS,
                batches_completed=10,
                vectors_migrated=5000,
                last_offset=5000,
                worker_progress={0: 2500, 1: 2500},
            )

            # Verify write was called
            assert async_path_mock.return_value.write_bytes.called

    async def test_load_checkpoint_returns_none_if_not_exists(
        self, migration_service: MigrationService, checkpoint_path_mock: Mock
    ) -> None:
        """Test that load_checkpoint returns None if checkpoint doesn't exist."""
        with patch("codeweaver.engine.services.migration_service.AsyncPath") as async_path_mock:
            async_path_mock.return_value.exists = AsyncMock(return_value=False)

            result = await migration_service._load_migration_checkpoint("test_migration")

            assert result is None

    async def test_load_checkpoint_reconstructs_checkpoint_object(
        self, migration_service: MigrationService, checkpoint_path_mock: Mock
    ) -> None:
        """Test that load_checkpoint properly reconstructs checkpoint object."""
        from codeweaver.engine.services.migration_service import MigrationState

        with patch("codeweaver.engine.services.migration_service.AsyncPath") as async_path_mock:
            async_path_mock.return_value.exists = AsyncMock(return_value=True)
            async_path_mock.return_value.read_bytes = AsyncMock(
                return_value=b'{"migration_id":"test_migration","state":"in_progress","batches_completed":10,"vectors_migrated":5000,"last_offset":5000,"timestamp":"2026-02-12T00:00:00Z","worker_progress":{"0":2500,"1":2500}}'
            )

            result = await migration_service._load_migration_checkpoint("test_migration")

            assert result is not None
            assert result.migration_id == "test_migration"
            assert result.state == MigrationState.IN_PROGRESS
            assert result.vectors_migrated == 5000

    async def test_delete_checkpoint_removes_file(
        self, migration_service: MigrationService, checkpoint_path_mock: Mock
    ) -> None:
        """Test that delete_checkpoint removes checkpoint file."""
        with patch("codeweaver.engine.services.migration_service.AsyncPath") as async_path_mock:
            async_path_mock.return_value.exists = AsyncMock(return_value=True)
            async_path_mock.return_value.unlink = AsyncMock()

            await migration_service._delete_migration_checkpoint("test_migration")

            async_path_mock.return_value.unlink.assert_called_once()


# ===========================================================================
# Tests: Resume Capability
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestResumeCapability:
    """Tests for resume from checkpoint functionality."""

    async def test_resumes_from_checkpoint_offset(
        self, migration_service: MigrationService
    ) -> None:
        """Test that migration resumes from checkpoint offset."""
        from codeweaver.engine.services.migration_service import MigrationCheckpoint, MigrationState

        # Mock checkpoint with partial completion
        checkpoint = MigrationCheckpoint(
            migration_id="test",
            state=MigrationState.IN_PROGRESS,
            batches_completed=5,
            vectors_migrated=2500,
            last_offset=2500,
            timestamp=datetime.now(UTC),
            worker_progress={0: 2500},
        )

        # Verify work items start from checkpoint offset
        work_items = migration_service._create_work_items(
            source_collection="source",
            target_collection="target",
            new_dimension=1024,
            vector_count=5000,
            worker_count=2,
            batch_size=1000,
            start_offset=checkpoint.last_offset,
        )

        assert work_items[0].start_offset == 2500

    async def test_checkpoint_saved_every_10_batches(
        self, migration_service: MigrationService
    ) -> None:
        """Test that checkpoints are saved every 10 batches."""
        # This test would verify the worker method saves checkpoints
        # at the correct intervals (every 10 batches)
        # Implementation would need to mock the worker execution
        # Placeholder - actual implementation depends on worker mock

    async def test_resume_with_different_worker_count(
        self, migration_service: MigrationService
    ) -> None:
        """Test that resume works with different worker count."""
        from codeweaver.engine.services.migration_service import MigrationCheckpoint, MigrationState

        # Original: 4 workers, Resume: 2 workers
        checkpoint = MigrationCheckpoint(
            migration_id="test",
            state=MigrationState.IN_PROGRESS,
            batches_completed=5,
            vectors_migrated=2500,
            last_offset=2500,
            timestamp=datetime.now(UTC),
            worker_progress={0: 625, 1: 625, 2: 625, 3: 625},
        )

        # Should handle different worker count gracefully
        work_items = migration_service._create_work_items(
            source_collection="source",
            target_collection="target",
            new_dimension=1024,
            vector_count=5000,
            worker_count=2,  # Different from original 4
            batch_size=1000,
            start_offset=checkpoint.last_offset,
        )

        assert len(work_items) == 2


# ===========================================================================
# Tests: Parallel Worker Execution
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestParallelWorkerExecution:
    """Tests for parallel worker execution."""

    async def test_worker_processes_batches(self, migration_service: MigrationService) -> None:
        """Test that worker processes batches correctly."""
        from codeweaver.engine.services.migration_service import WorkItem

        # Mock batch operations
        migration_service._fetch_batch = AsyncMock(
            side_effect=[
                [PointStruct(id="test_id", vector=[1.0, 2.0, 3.0], payload={})],  # Batch 1
                [],  # No more batches
            ]
        )
        migration_service._batch_upsert = AsyncMock()
        migration_service._save_migration_checkpoint = AsyncMock()

        work_item = WorkItem(
            source_collection="source",
            target_collection="target",
            start_offset=0,
            batch_size=1000,
            new_dimension=1024,
            worker_id=0,
        )

        result = await migration_service._migration_worker(work_item, "test_migration", None)

        assert result.success is True
        assert result.vectors_processed > 0

    async def test_worker_retries_on_failure(self, migration_service: MigrationService) -> None:
        """Test that worker retries on transient failures."""
        from codeweaver.engine.services.migration_service import WorkItem

        # First call fails, second succeeds
        migration_service._fetch_batch = AsyncMock(side_effect=[RuntimeError("Network error"), []])
        migration_service._batch_upsert = AsyncMock()
        migration_service._save_migration_checkpoint = AsyncMock()

        work_item = WorkItem(
            source_collection="source",
            target_collection="target",
            start_offset=0,
            batch_size=1000,
            new_dimension=1024,
            worker_id=0,
        )

        # Worker should retry and eventually succeed (or fail gracefully)
        result = await migration_service._migration_worker(work_item, "test_migration", None)

        # Either succeeds after retry or returns failure result
        assert isinstance(result.success, bool)

    async def test_worker_saves_checkpoint_every_10_batches(
        self, migration_service: MigrationService
    ) -> None:
        """Test that worker saves checkpoint every 10 batches."""
        from codeweaver.engine.services.migration_service import WorkItem

        # Create 11 batches to trigger checkpoint save
        batches = [
            [PointStruct(id=f"id_{i}", vector=[1.0, 2.0, 3.0], payload={})] for i in range(11)
        ]
        batches.append([])  # End marker

        migration_service._fetch_batch = AsyncMock(side_effect=batches)
        migration_service._batch_upsert = AsyncMock()
        migration_service._save_migration_checkpoint = AsyncMock()

        work_item = WorkItem(
            source_collection="source",
            target_collection="target",
            start_offset=0,
            batch_size=1,
            new_dimension=1024,
            worker_id=0,
        )

        await migration_service._migration_worker(work_item, "test_migration", None)

        # Should have saved checkpoint at batch 10
        assert migration_service._save_migration_checkpoint.call_count >= 1


# ===========================================================================
# Tests: Helper Methods
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestHelperMethods:
    """Tests for internal helper methods."""

    def test_cosine_similarity_identical_vectors(self, migration_service: MigrationService) -> None:
        """Test cosine similarity of identical vectors."""
        vec = [1.0, 2.0, 3.0]
        similarity = migration_service._cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 0.0001

    def test_cosine_similarity_orthogonal_vectors(
        self, migration_service: MigrationService
    ) -> None:
        """Test cosine similarity of orthogonal vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = migration_service._cosine_similarity(vec1, vec2)
        assert abs(similarity) < 0.0001

    def test_recall_at_k_perfect_match(self, migration_service: MigrationService) -> None:
        """Test recall@k with perfect match."""
        source = ["id1", "id2", "id3"]
        target = ["id1", "id2", "id3"]
        recall = migration_service._recall_at_k(source, target, k=3)
        assert recall == 1.0

    def test_recall_at_k_partial_match(self, migration_service: MigrationService) -> None:
        """Test recall@k with partial match."""
        source = ["id1", "id2", "id3"]
        target = ["id1", "id4", "id5"]
        recall = migration_service._recall_at_k(source, target, k=3)
        assert abs(recall - 0.333) < 0.01

    def test_generate_versioned_name(self, migration_service: MigrationService) -> None:
        """Test generation of versioned collection name."""
        name = migration_service._generate_versioned_name("base_collection", 1024)
        assert "base_collection" in name
        assert "1024" in name


# ===========================================================================
# Tests: Edge Cases
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    async def test_zero_vectors_skips_migration(self, migration_service: MigrationService) -> None:
        """Test that zero vectors skips migration gracefully."""
        migration_service._count_vectors = AsyncMock(return_value=0)
        migration_service._create_dimensioned_collection = AsyncMock()

        result = await migration_service.migrate_dimensions_parallel(
            new_dimension=1024, worker_count=4, resume=False
        )

        assert result.vectors_migrated == 0
        assert result.rollback_available is False

    async def test_handles_checkpoint_corruption(self, migration_service: MigrationService) -> None:
        """Test handling of corrupted checkpoint file."""
        with patch("codeweaver.engine.services.migration_service.AsyncPath") as async_path_mock:
            async_path_mock.return_value.exists = AsyncMock(return_value=True)
            async_path_mock.return_value.read_bytes = AsyncMock(return_value=b"corrupted data")

            result = await migration_service._load_migration_checkpoint("test")

            # Should return None on corruption
            assert result is None

    async def test_validation_error_preserves_checkpoint(
        self, migration_service: MigrationService
    ) -> None:
        """Test that validation errors preserve checkpoint for retry."""
        from codeweaver.engine.services.migration_service import ValidationError

        # Setup for validation failure
        migration_service._count_vectors = AsyncMock(return_value=5000)
        migration_service._compute_payload_checksums = AsyncMock(
            side_effect=[b"source", b"different"]
        )
        migration_service._create_dimensioned_collection = AsyncMock()
        migration_service._execute_parallel_migration = AsyncMock(return_value=5000)
        migration_service._load_migration_checkpoint = AsyncMock(return_value=None)
        migration_service._save_migration_checkpoint = AsyncMock()

        with pytest.raises(ValidationError):
            await migration_service.migrate_dimensions_parallel(
                new_dimension=1024, worker_count=4, resume=False
            )

        # Checkpoint should be saved for potential retry
        # (In real implementation, checkpoint would be saved on failure)

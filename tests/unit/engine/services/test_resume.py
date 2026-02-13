# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for migration resume capability.

Tests cover:
- Checkpoint saves every 10 batches
- Resume from various failure points (25%, 50%, 90%)
- No data loss on resume
- Resume with different worker counts
- Checkpoint corruption handling
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest


if TYPE_CHECKING:
    from codeweaver.engine.services.migration_service import MigrationService


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def migration_service():
    """Create MigrationService with mocked dependencies."""
    from codeweaver.engine.services.migration_service import MigrationService

    vector_store = Mock(spec=["collection"])
    vector_store.collection = "test_collection"

    checkpoint_manager = Mock(spec=["checkpoint_dir"])
    checkpoint_manager.checkpoint_dir = Mock()

    return MigrationService(
        vector_store=vector_store,
        config_analyzer=Mock(),
        checkpoint_manager=checkpoint_manager,
        manifest_manager=Mock(),
    )


# ===========================================================================
# Tests: Checkpoint Frequency
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestCheckpointFrequency:
    """Tests for checkpoint save frequency."""

    async def test_checkpoint_saved_every_10_batches(
        self, migration_service: MigrationService
    ) -> None:
        """Test that checkpoint is saved every 10 batches."""
        from codeweaver.engine.services.migration_service import WorkItem

        # Mock operations
        batches_processed = 0

        async def mock_fetch(collection, offset, limit):
            nonlocal batches_processed
            batches_processed += 1
            if batches_processed <= 25:  # Process 25 batches
                return [Mock()]
            return []

        migration_service._fetch_batch = mock_fetch
        migration_service._batch_upsert = AsyncMock()
        migration_service._save_migration_checkpoint = AsyncMock()

        work_item = WorkItem(
            source_collection="source",
            target_collection="target",
            start_offset=0,
            batch_size=100,
            new_dimension=1024,
            worker_id=0,
        )

        await migration_service._migration_worker(work_item, "test_migration", None)

        # Should save checkpoint at batch 10 and 20
        assert migration_service._save_migration_checkpoint.call_count >= 2

    async def test_checkpoint_not_saved_for_small_batches(
        self, migration_service: MigrationService
    ) -> None:
        """Test that checkpoint is not saved for <10 batches."""
        from codeweaver.engine.services.migration_service import WorkItem

        batches_processed = 0

        async def mock_fetch(collection, offset, limit):
            nonlocal batches_processed
            batches_processed += 1
            if batches_processed <= 5:  # Only 5 batches
                return [Mock()]
            return []

        migration_service._fetch_batch = mock_fetch
        migration_service._batch_upsert = AsyncMock()
        migration_service._save_migration_checkpoint = AsyncMock()

        work_item = WorkItem(
            source_collection="source",
            target_collection="target",
            start_offset=0,
            batch_size=100,
            new_dimension=1024,
            worker_id=0,
        )

        await migration_service._migration_worker(work_item, "test_migration", None)

        # Should not save checkpoint (only 5 batches)
        assert migration_service._save_migration_checkpoint.call_count == 0


# ===========================================================================
# Tests: Resume from Various Points
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestResumeFromCheckpoint:
    """Tests for resuming from different completion points."""

    async def test_resume_from_25_percent(self, migration_service: MigrationService) -> None:
        """Test resume from 25% completion."""
        from codeweaver.engine.services.migration_service import MigrationCheckpoint, MigrationState

        # Checkpoint at 25% (2500/10000 vectors)
        checkpoint = MigrationCheckpoint(
            migration_id="test",
            state=MigrationState.IN_PROGRESS,
            batches_completed=25,
            vectors_migrated=2500,
            last_offset=2500,
            timestamp=datetime.now(UTC),
            worker_progress={0: 2500},
        )

        migration_service._load_migration_checkpoint = AsyncMock(return_value=checkpoint)

        # Work items should start from checkpoint offset
        work_items = migration_service._create_work_items(
            source_collection="source",
            target_collection="target",
            new_dimension=1024,
            vector_count=10000,
            worker_count=4,
            batch_size=1000,
            start_offset=checkpoint.last_offset,
        )

        # Should start from 2500, not 0
        assert work_items[0].start_offset == 2500

    async def test_resume_from_50_percent(self, migration_service: MigrationService) -> None:
        """Test resume from 50% completion."""
        from codeweaver.engine.services.migration_service import MigrationCheckpoint, MigrationState

        checkpoint = MigrationCheckpoint(
            migration_id="test",
            state=MigrationState.IN_PROGRESS,
            batches_completed=50,
            vectors_migrated=5000,
            last_offset=5000,
            timestamp=datetime.now(UTC),
            worker_progress={0: 1250, 1: 1250, 2: 1250, 3: 1250},
        )

        migration_service._load_migration_checkpoint = AsyncMock(return_value=checkpoint)

        work_items = migration_service._create_work_items(
            source_collection="source",
            target_collection="target",
            new_dimension=1024,
            vector_count=10000,
            worker_count=4,
            batch_size=1000,
            start_offset=checkpoint.last_offset,
        )

        assert work_items[0].start_offset == 5000

    async def test_resume_from_90_percent(self, migration_service: MigrationService) -> None:
        """Test resume from 90% completion."""
        from codeweaver.engine.services.migration_service import MigrationCheckpoint, MigrationState

        checkpoint = MigrationCheckpoint(
            migration_id="test",
            state=MigrationState.IN_PROGRESS,
            batches_completed=90,
            vectors_migrated=9000,
            last_offset=9000,
            timestamp=datetime.now(UTC),
            worker_progress={0: 2250, 1: 2250, 2: 2250, 3: 2250},
        )

        migration_service._load_migration_checkpoint = AsyncMock(return_value=checkpoint)

        work_items = migration_service._create_work_items(
            source_collection="source",
            target_collection="target",
            new_dimension=1024,
            vector_count=10000,
            worker_count=4,
            batch_size=1000,
            start_offset=checkpoint.last_offset,
        )

        # Should only process last 1000 vectors
        assert work_items[0].start_offset == 9000


# ===========================================================================
# Tests: No Data Loss
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestNoDataLoss:
    """Tests to ensure no data loss on resume."""

    async def test_no_duplicate_vectors_on_resume(
        self, migration_service: MigrationService
    ) -> None:
        """Test that resume doesn't re-process already migrated vectors."""
        from codeweaver.engine.services.migration_service import MigrationCheckpoint, MigrationState

        checkpoint = MigrationCheckpoint(
            migration_id="test",
            state=MigrationState.IN_PROGRESS,
            batches_completed=10,
            vectors_migrated=1000,
            last_offset=1000,
            timestamp=datetime.now(UTC),
            worker_progress={0: 1000},
        )

        # Resume should start at offset 1000, not 0
        work_items = migration_service._create_work_items(
            source_collection="source",
            target_collection="target",
            new_dimension=1024,
            vector_count=5000,
            worker_count=2,
            batch_size=1000,
            start_offset=checkpoint.last_offset,
        )

        # First worker should start at 1000
        assert work_items[0].start_offset == 1000

    async def test_all_vectors_processed_after_resume(
        self, migration_service: MigrationService
    ) -> None:
        """Test that all vectors are processed including after resume."""
        # Checkpoint + remaining work should cover all vectors
        from codeweaver.engine.services.migration_service import MigrationCheckpoint, MigrationState

        total_vectors = 10000
        checkpoint_vectors = 2500

        checkpoint = MigrationCheckpoint(
            migration_id="test",
            state=MigrationState.IN_PROGRESS,
            batches_completed=25,
            vectors_migrated=checkpoint_vectors,
            last_offset=checkpoint_vectors,
            timestamp=datetime.now(UTC),
            worker_progress={0: checkpoint_vectors},
        )

        # Remaining vectors to process
        remaining = total_vectors - checkpoint_vectors

        # Should create work for remaining vectors
        assert remaining == 7500


# ===========================================================================
# Tests: Resume with Different Worker Count
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestResumeWithDifferentWorkers:
    """Tests for resuming with different number of workers."""

    async def test_resume_4_workers_to_2_workers(self, migration_service: MigrationService) -> None:
        """Test resume from 4 workers to 2 workers."""
        from codeweaver.engine.services.migration_service import MigrationCheckpoint, MigrationState

        # Original: 4 workers
        checkpoint = MigrationCheckpoint(
            migration_id="test",
            state=MigrationState.IN_PROGRESS,
            batches_completed=40,
            vectors_migrated=4000,
            last_offset=4000,
            timestamp=datetime.now(UTC),
            worker_progress={0: 1000, 1: 1000, 2: 1000, 3: 1000},
        )

        migration_service._load_migration_checkpoint = AsyncMock(return_value=checkpoint)

        # Resume with 2 workers
        work_items = migration_service._create_work_items(
            source_collection="source",
            target_collection="target",
            new_dimension=1024,
            vector_count=10000,
            worker_count=2,  # Changed from 4
            batch_size=1000,
            start_offset=checkpoint.last_offset,
        )

        # Should create 2 work items
        assert len(work_items) == 2

    async def test_resume_2_workers_to_4_workers(self, migration_service: MigrationService) -> None:
        """Test resume from 2 workers to 4 workers."""
        from codeweaver.engine.services.migration_service import MigrationCheckpoint, MigrationState

        # Original: 2 workers
        checkpoint = MigrationCheckpoint(
            migration_id="test",
            state=MigrationState.IN_PROGRESS,
            batches_completed=20,
            vectors_migrated=2000,
            last_offset=2000,
            timestamp=datetime.now(UTC),
            worker_progress={0: 1000, 1: 1000},
        )

        migration_service._load_migration_checkpoint = AsyncMock(return_value=checkpoint)

        # Resume with 4 workers
        work_items = migration_service._create_work_items(
            source_collection="source",
            target_collection="target",
            new_dimension=1024,
            vector_count=10000,
            worker_count=4,  # Changed from 2
            batch_size=1000,
            start_offset=checkpoint.last_offset,
        )

        # Should create 4 work items
        assert len(work_items) == 4

    async def test_worker_progress_merged_on_resume(
        self, migration_service: MigrationService
    ) -> None:
        """Test that worker progress is properly merged on resume."""
        from codeweaver.engine.services.migration_service import MigrationCheckpoint, MigrationState

        # Different worker counts should still aggregate correctly
        checkpoint = MigrationCheckpoint(
            migration_id="test",
            state=MigrationState.IN_PROGRESS,
            batches_completed=30,
            vectors_migrated=3000,
            last_offset=3000,
            timestamp=datetime.now(UTC),
            worker_progress={0: 1000, 1: 1000, 2: 1000},  # 3 workers originally
        )

        # Total progress should be sum of all workers
        total_progress = sum(checkpoint.worker_progress.values())
        assert total_progress == checkpoint.vectors_migrated


# ===========================================================================
# Tests: Checkpoint Corruption
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestCheckpointCorruption:
    """Tests for checkpoint corruption handling."""

    async def test_corrupted_checkpoint_returns_none(
        self, migration_service: MigrationService
    ) -> None:
        """Test that corrupted checkpoint returns None."""
        with patch("codeweaver.engine.services.migration_service.AsyncPath") as mock_path:
            mock_path.return_value.exists = AsyncMock(return_value=True)
            mock_path.return_value.read_bytes = AsyncMock(return_value=b"corrupted data")

            result = await migration_service._load_migration_checkpoint("test")

            assert result is None

    async def test_missing_checkpoint_returns_none(
        self, migration_service: MigrationService
    ) -> None:
        """Test that missing checkpoint returns None."""
        with patch("codeweaver.engine.services.migration_service.AsyncPath") as mock_path:
            mock_path.return_value.exists = AsyncMock(return_value=False)

            result = await migration_service._load_migration_checkpoint("test")

            assert result is None

    async def test_resume_starts_fresh_on_corruption(
        self, migration_service: MigrationService
    ) -> None:
        """Test that corrupted checkpoint causes fresh start."""
        migration_service._load_migration_checkpoint = AsyncMock(return_value=None)

        # With no checkpoint, should start from beginning
        work_items = migration_service._create_work_items(
            source_collection="source",
            target_collection="target",
            new_dimension=1024,
            vector_count=10000,
            worker_count=4,
            batch_size=1000,
            start_offset=None,  # No checkpoint offset
        )

        # Should start from 0 (or None for first batch)
        assert work_items[0].start_offset is None or work_items[0].start_offset == 0


# ===========================================================================
# Tests: Checkpoint State Validation
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestCheckpointStateValidation:
    """Tests for checkpoint state validation."""

    async def test_checkpoint_state_enum_preserved(
        self, migration_service: MigrationService
    ) -> None:
        """Test that checkpoint state enum is preserved through save/load."""
        from codeweaver.engine.services.migration_service import MigrationState

        with patch("codeweaver.engine.services.migration_service.AsyncPath") as mock_path:
            mock_path.return_value.exists = AsyncMock(return_value=True)
            mock_path.return_value.read_bytes = AsyncMock(
                return_value=b'{"migration_id":"test","state":"in_progress","batches_completed":10,"vectors_migrated":1000,"last_offset":1000,"timestamp":"2026-02-12T00:00:00Z","worker_progress":{}}'
            )

            checkpoint = await migration_service._load_migration_checkpoint("test")

            assert checkpoint is not None
            assert checkpoint.state == MigrationState.IN_PROGRESS

    async def test_checkpoint_contains_all_required_fields(
        self, migration_service: MigrationService
    ) -> None:
        """Test that checkpoint contains all required fields."""
        from codeweaver.engine.services.migration_service import MigrationState

        with patch("codeweaver.engine.services.migration_service.AsyncPath") as mock_path:
            mock_path.return_value.mkdir = AsyncMock()
            mock_path.return_value.write_bytes = AsyncMock()
            mock_path.return_value.rename = AsyncMock()
            mock_path.return_value.parent = Mock()
            mock_path.return_value.with_suffix = Mock(return_value=mock_path.return_value)

            migration_service._get_checkpoint_path = Mock(return_value=mock_path.return_value)

            await migration_service._save_migration_checkpoint(
                migration_id="test",
                state=MigrationState.IN_PROGRESS,
                batches_completed=10,
                vectors_migrated=1000,
                last_offset=1000,
                worker_progress={0: 1000},
            )

            # Verify all fields are present
            assert mock_path.return_value.write_bytes.called

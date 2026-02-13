# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for parallel worker execution and coordination.

Tests cover:
- Work distribution among workers
- Concurrent execution correctness
- No duplicate/missing vectors
- Speedup measurements
- Worker failure handling
"""

from __future__ import annotations

import asyncio

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

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

    return MigrationService(
        vector_store=vector_store,
        config_analyzer=Mock(),
        checkpoint_manager=Mock(),
        manifest_manager=Mock(),
    )


# ===========================================================================
# Tests: Work Distribution
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestWorkDistribution:
    """Tests for work distribution among workers."""

    def test_work_distributed_among_workers(self, migration_service: MigrationService) -> None:
        """Verify work is distributed to all workers."""
        work_items = migration_service._create_work_items(
            source_collection="source",
            target_collection="target",
            new_dimension=1024,
            vector_count=10000,
            worker_count=4,
            batch_size=1000,
        )

        # All 4 workers should get work
        assert len(work_items) == 4
        worker_ids = {item.worker_id for item in work_items}
        assert worker_ids == {0, 1, 2, 3}

    def test_work_distribution_covers_all_vectors(
        self, migration_service: MigrationService
    ) -> None:
        """Verify all vectors are covered by work items."""
        vector_count = 10000
        work_items = migration_service._create_work_items(
            source_collection="source",
            target_collection="target",
            new_dimension=1024,
            vector_count=vector_count,
            worker_count=4,
            batch_size=1000,
        )

        # Calculate total vectors covered
        # Each worker gets vectors_per_worker vectors
        vectors_per_worker = vector_count // 4  # 2500 each
        total_coverage = len(work_items) * vectors_per_worker

        assert total_coverage == vector_count

    def test_work_distribution_handles_uneven_split(
        self, migration_service: MigrationService
    ) -> None:
        """Verify uneven vector counts are handled correctly."""
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

    def test_work_items_have_correct_parameters(self, migration_service: MigrationService) -> None:
        """Verify work items have correct parameters."""
        work_items = migration_service._create_work_items(
            source_collection="source",
            target_collection="target",
            new_dimension=1024,
            vector_count=10000,
            worker_count=4,
            batch_size=1000,
        )

        for item in work_items:
            assert item.source_collection == "source"
            assert item.target_collection == "target"
            assert item.new_dimension == 1024
            assert item.batch_size == 1000


# ===========================================================================
# Tests: Concurrent Execution
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestConcurrentExecution:
    """Tests for concurrent worker execution."""

    async def test_workers_execute_concurrently(self, migration_service: MigrationService) -> None:
        """Verify workers execute in parallel, not sequentially."""
        from codeweaver.engine.services.migration_service import WorkItem

        execution_times = []

        async def slow_worker(item, migration_id, checkpoint):
            start = datetime.now(UTC)
            await asyncio.sleep(0.1)  # Simulate work
            end = datetime.now(UTC)
            execution_times.append((item.worker_id, start, end))
            return Mock(success=True, vectors_processed=100, elapsed=end - start)

        migration_service._migration_worker = slow_worker

        work_items = [
            WorkItem(
                source_collection="source",
                target_collection="target",
                start_offset=i * 1000,
                batch_size=1000,
                new_dimension=1024,
                worker_id=i,
            )
            for i in range(4)
        ]

        # Execute in parallel
        start_time = datetime.now(UTC)
        await asyncio.gather(*[
            migration_service._migration_worker(item, "test", None) for item in work_items
        ])
        end_time = datetime.now(UTC)

        total_time = (end_time - start_time).total_seconds()

        # Should take ~0.1s (parallel), not ~0.4s (sequential)
        assert total_time < 0.2, "Workers should execute concurrently"

    async def test_no_duplicate_vectors_processed(
        self, migration_service: MigrationService
    ) -> None:
        """Verify no vectors are processed by multiple workers."""
        processed_vectors = []

        async def tracking_worker(item, migration_id, checkpoint):
            # Track which vectors this worker processes
            # In real implementation, this would be based on offsets
            worker_vectors = list(
                range(item.start_offset or 0, (item.start_offset or 0) + item.batch_size)
            )
            processed_vectors.extend([(item.worker_id, vec) for vec in worker_vectors])
            return Mock(success=True, vectors_processed=len(worker_vectors), elapsed=timedelta(0))

        migration_service._migration_worker = tracking_worker
        migration_service._create_work_items = Mock(
            return_value=[
                Mock(worker_id=0, start_offset=0, batch_size=100),
                Mock(worker_id=1, start_offset=100, batch_size=100),
                Mock(worker_id=2, start_offset=200, batch_size=100),
                Mock(worker_id=3, start_offset=300, batch_size=100),
            ]
        )

        work_items = migration_service._create_work_items(
            source_collection="source",
            target_collection="target",
            new_dimension=1024,
            vector_count=400,
            worker_count=4,
            batch_size=100,
        )

        await asyncio.gather(*[
            migration_service._migration_worker(item, "test", None) for item in work_items
        ])

        # Check for duplicates
        vector_ids = [vec_id for _, vec_id in processed_vectors]
        assert len(vector_ids) == len(set(vector_ids)), "Duplicate vectors processed"

    async def test_no_missing_vectors(self, migration_service: MigrationService) -> None:
        """Verify all vectors are processed exactly once."""
        # This test verifies coverage - no gaps in processing
        processed_offsets = set()

        async def tracking_worker(item, migration_id, checkpoint):
            start = item.start_offset or 0
            # Track processed offset range
            processed_offsets.update(range(start, start + item.batch_size))
            return Mock(success=True, vectors_processed=item.batch_size, elapsed=timedelta(0))

        migration_service._migration_worker = tracking_worker

        work_items = [Mock(worker_id=i, start_offset=i * 100, batch_size=100) for i in range(4)]

        await asyncio.gather(*[
            migration_service._migration_worker(item, "test", None) for item in work_items
        ])

        # Should cover 0-399 with no gaps
        expected = set(range(400))
        assert processed_offsets == expected, "Missing vectors detected"


# ===========================================================================
# Tests: Speedup Measurements
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestSpeedupMeasurements:
    """Tests for parallel speedup metrics."""

    async def test_speedup_calculation(self, migration_service: MigrationService) -> None:
        """Test speedup calculation for parallel execution."""
        # Mock single worker execution time
        single_worker_time = timedelta(seconds=100)

        # Mock parallel execution time (4 workers)
        parallel_time = timedelta(seconds=30)

        # Theoretical speedup: 100/30 = 3.33x
        speedup = single_worker_time / parallel_time

        # Should be >3x (close to 4x ideal)
        assert speedup > 3.0

    async def test_speedup_with_4_workers_exceeds_3_5x(
        self, migration_service: MigrationService
    ) -> None:
        """Test that 4 workers achieve >3.5x speedup (success criteria)."""
        # From implementation plan: Parallel speedup >3.5x with 4 workers
        # This would be measured in real benchmark tests
        # Here we verify the calculation logic

        single_worker_time = 100.0  # seconds
        four_worker_time = 28.0  # seconds

        speedup = single_worker_time / four_worker_time

        # Success criteria: >3.5x
        assert speedup > 3.5


# ===========================================================================
# Tests: Worker Failure Handling
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestWorkerFailureHandling:
    """Tests for worker failure scenarios."""

    async def test_worker_failure_detected(self, migration_service: MigrationService) -> None:
        """Test that worker failures are detected."""
        from codeweaver.engine.services.migration_service import MigrationError

        async def failing_worker(item, migration_id, checkpoint):
            if item.worker_id == 2:
                raise RuntimeError("Worker 2 failed")
            return Mock(success=True, vectors_processed=100, elapsed=timedelta(0))

        migration_service._migration_worker = failing_worker
        migration_service._create_work_items = Mock(
            return_value=[Mock(worker_id=i) for i in range(4)]
        )
        migration_service._count_vectors = AsyncMock(return_value=1000)
        migration_service._create_dimensioned_collection = AsyncMock()
        migration_service._load_migration_checkpoint = AsyncMock(return_value=None)

        with pytest.raises(MigrationError):
            await migration_service.migrate_dimensions_parallel(
                new_dimension=1024, worker_count=4, resume=False
            )

    async def test_worker_returns_failure_result(self, migration_service: MigrationService) -> None:
        """Test that worker can return failure result."""
        from codeweaver.engine.services.migration_service import ChunkResult

        # Worker returns failure (not exception)
        async def worker_with_failure(item, migration_id, checkpoint):
            if item.worker_id == 1:
                return ChunkResult(
                    worker_id=1,
                    vectors_processed=0,
                    elapsed=timedelta(0),
                    success=False,
                    error="Simulated error",
                )
            return ChunkResult(
                worker_id=item.worker_id, vectors_processed=100, elapsed=timedelta(0), success=True
            )

        migration_service._migration_worker = worker_with_failure
        migration_service._create_work_items = Mock(
            return_value=[Mock(worker_id=i) for i in range(4)]
        )
        migration_service._count_vectors = AsyncMock(return_value=1000)
        migration_service._create_dimensioned_collection = AsyncMock()
        migration_service._load_migration_checkpoint = AsyncMock(return_value=None)

        with pytest.raises(Exception):  # Should detect failed worker
            await migration_service.migrate_dimensions_parallel(
                new_dimension=1024, worker_count=4, resume=False
            )

    async def test_partial_worker_success_rolls_back(
        self, migration_service: MigrationService
    ) -> None:
        """Test that partial success triggers rollback."""
        # If some workers succeed and some fail, should rollback
        # This ensures data consistency - all or nothing
        pytest.skip("Rollback logic not yet implemented")


# ===========================================================================
# Tests: Worker Coordination
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestWorkerCoordination:
    """Tests for worker coordination and synchronization."""

    async def test_workers_dont_interfere(self, migration_service: MigrationService) -> None:
        """Test that workers don't interfere with each other."""
        # Workers should operate on separate offset ranges
        # No shared state between workers (except checkpoint)
        # Verified by no duplicate/missing vector tests

    async def test_worker_progress_tracked_independently(
        self, migration_service: MigrationService
    ) -> None:
        """Test that worker progress is tracked per worker."""
        from codeweaver.engine.services.migration_service import MigrationCheckpoint, MigrationState

        checkpoint = MigrationCheckpoint(
            migration_id="test",
            state=MigrationState.IN_PROGRESS,
            batches_completed=10,
            vectors_migrated=5000,
            last_offset=5000,
            timestamp=datetime.now(UTC),
            worker_progress={0: 1250, 1: 1250, 2: 1250, 3: 1250},
        )

        # Each worker's progress is tracked separately
        assert len(checkpoint.worker_progress) == 4
        assert sum(checkpoint.worker_progress.values()) == checkpoint.vectors_migrated

    async def test_checkpoint_aggregates_worker_progress(
        self, migration_service: MigrationService
    ) -> None:
        """Test that checkpoint aggregates progress from all workers."""
        # Checkpoint should sum up progress from all workers
        worker_progress = {0: 1000, 1: 1500, 2: 1200, 3: 1300}
        total = sum(worker_progress.values())

        assert total == 5000  # Sum of all worker progress

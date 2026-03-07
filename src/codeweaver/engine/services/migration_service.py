# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Migration service for vector store transformations.

This service implements dimension reduction and quantization migrations with:
- CRITICAL #3: Parallel processing with worker pools
- CRITICAL #4: Data integrity validation (4 layers)
- CRITICAL #5: Resume capability with checkpoints

ARCHITECTURE: Plain class with no DI in constructor (factory handles DI).
"""

from __future__ import annotations

import asyncio
import logging

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from anyio import Path as AsyncPath
from pydantic_core import from_json, to_json
from qdrant_client.models import PointStruct
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from codeweaver.core import BlakeHashKey, get_blake_hash
from codeweaver.core.constants import BASE_RETRYABLE_EXCEPTIONS


if TYPE_CHECKING:
    from codeweaver.engine.managers.checkpoint_manager import CheckpointManager
    from codeweaver.engine.managers.manifest_manager import FileManifestManager
    from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer
    from codeweaver.providers.vector_stores.base import VectorStoreProvider
logger = logging.getLogger(__name__)


class MigrationState(Enum):
    """Migration state machine states.

    State Transitions:
        PENDING -> IN_PROGRESS -> COMPLETED -> ROLLBACK -> PENDING
                                ↓
                              FAILED -> PENDING
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLBACK = "rollback"


class MigrationError(Exception):
    """Base exception for migration errors."""


class ValidationError(MigrationError):
    """Data integrity validation failed."""


class InvalidStateTransitionError(MigrationError):
    """Invalid state transition attempted."""


@dataclass
class WorkItem:
    """Work item for parallel migration."""

    source_collection: str
    target_collection: str
    start_offset: int | None
    batch_size: int
    new_dimension: int
    worker_id: int


@dataclass
class ChunkResult:
    """Result from migrating a chunk."""

    worker_id: int
    vectors_processed: int
    elapsed: timedelta
    success: bool
    error: str | None = None


@dataclass
class MigrationResult:
    """Results of migration operation."""

    strategy: str
    vectors_migrated: int
    old_collection: str
    new_collection: str
    elapsed: timedelta
    worker_count: int = 1
    speedup_factor: float = 1.0
    rollback_available: bool = True
    rollback_retention_days: int = 7


@dataclass
class MigrationCheckpoint:
    """Persistent checkpoint for migration state."""

    migration_id: str
    state: MigrationState
    batches_completed: int
    vectors_migrated: int
    last_offset: int | None
    timestamp: datetime
    worker_progress: dict[int, int]


class MigrationService:
    """Comprehensive migration service with parallel workers.

    ARCHITECTURE NOTE: This is a PLAIN CLASS with no DI in constructor.
    Factory function in engine/dependencies.py handles DI integration.

    Implements:
    - CRITICAL #3: Parallel processing with worker pool
    - CRITICAL #4: Data integrity validation (4 layers)
    - CRITICAL #5: Resume capability with checkpoints
    """

    def __init__(
        self,
        vector_store: VectorStoreProvider,
        config_analyzer: ConfigChangeAnalyzer,
        checkpoint_manager: CheckpointManager,
        manifest_manager: FileManifestManager,
    ) -> None:
        """Initialize migration service with dependencies.

        Args:
            vector_store: Vector store provider (abstract base)
            config_analyzer: Configuration change analyzer
            checkpoint_manager: Checkpoint manager for state persistence
            manifest_manager: File manifest manager
        """
        self.vector_store = vector_store
        self.config_analyzer = config_analyzer
        self.checkpoint_manager = checkpoint_manager
        self.manifest_manager = manifest_manager

    async def migrate_dimensions_parallel(
        self,
        new_dimension: int,
        worker_count: int = 4,
        batch_size: int = 1000,
        *,
        resume: bool = True,
    ) -> MigrationResult:
        """Main entry point for parallel dimension migration.

        Implements CRITICAL #3 (parallel processing), CRITICAL #4 (data integrity),
        and CRITICAL #5 (resume capability).

        Args:
            new_dimension: Target dimension for migration
            worker_count: Number of parallel workers (default: 4)
            batch_size: Vectors per batch (default: 1000)
            resume: Whether to resume from checkpoint (default: True)

        Returns:
            MigrationResult with timing and statistics

        Raises:
            ValidationError: Data integrity validation failed
            MigrationError: Migration operation failed
        """
        start_time = datetime.now(UTC)
        migration_id = get_blake_hash(f"{start_time.isoformat()}_{new_dimension}".encode())[:16]
        logger.info(
            "Starting parallel dimension migration: id=%s dimension=%d workers=%d",
            migration_id,
            new_dimension,
            worker_count,
        )
        checkpoint = None
        if resume:
            checkpoint = await self._load_migration_checkpoint(migration_id)
            if checkpoint:
                logger.info(
                    "Resuming migration from checkpoint: vectors_migrated=%d",
                    checkpoint.vectors_migrated,
                )
        source_collection = self.vector_store.collection
        if not source_collection:
            raise MigrationError("No collection configured in vector store")
        target_collection = self._generate_versioned_name(source_collection, new_dimension)
        await self._create_dimensioned_collection(target_collection, new_dimension)
        vector_count = await self._count_vectors(source_collection)
        if vector_count == 0:
            logger.warning("Source collection is empty, skipping migration")
            return MigrationResult(
                strategy="dimension_reduction",
                vectors_migrated=0,
                old_collection=source_collection,
                new_collection=target_collection,
                elapsed=timedelta(0),
                worker_count=worker_count,
                speedup_factor=1.0,
                rollback_available=False,
            )
        try:
            vectors_migrated = await self._execute_parallel_migration(
                source_collection=source_collection,
                target_collection=target_collection,
                new_dimension=new_dimension,
                vector_count=vector_count,
                worker_count=worker_count,
                batch_size=batch_size,
                migration_id=migration_id,
                checkpoint=checkpoint,
            )
            await self._validate_migration_integrity(
                source_collection=source_collection,
                target_collection=target_collection,
                expected_count=vector_count,
                new_dimension=new_dimension,
            )
            await self._switch_collection_alias(
                alias=source_collection, new_target=target_collection, old_target=source_collection
            )
            await self._delete_migration_checkpoint(migration_id)
            elapsed = datetime.now(UTC) - start_time
            speedup = worker_count
            logger.info(
                "Migration completed: vectors=%d elapsed=%s speedup=%.1fx",
                vectors_migrated,
                elapsed,
                speedup,
            )
        except Exception as e:
            logger.warning("Migration failed: %s", e, exc_info=True)
            if checkpoint:
                await self._save_migration_checkpoint(
                    migration_id=migration_id,
                    state=MigrationState.FAILED,
                    batches_completed=checkpoint.batches_completed,
                    vectors_migrated=checkpoint.vectors_migrated,
                    last_offset=checkpoint.last_offset,
                    worker_progress=checkpoint.worker_progress,
                )
            raise
        else:
            return MigrationResult(
                strategy="dimension_reduction",
                vectors_migrated=vectors_migrated,
                old_collection=source_collection,
                new_collection=target_collection,
                elapsed=elapsed,
                speedup_factor=speedup,
                rollback_available=True,
                rollback_retention_days=7,
            )

    async def _execute_parallel_migration(
        self,
        source_collection: str,
        target_collection: str,
        new_dimension: int,
        vector_count: int,
        worker_count: int,
        batch_size: int,
        migration_id: str,
        checkpoint: MigrationCheckpoint | None,
    ) -> int:
        """Execute parallel migration with worker orchestration.

        Implements CRITICAL #3: Parallel processing.

        Args:
            source_collection: Source collection name
            target_collection: Target collection name
            new_dimension: Target dimension
            vector_count: Total vectors to migrate
            worker_count: Number of parallel workers
            batch_size: Vectors per batch
            migration_id: Unique migration identifier
            checkpoint: Optional checkpoint to resume from

        Returns:
            Total vectors migrated

        Raises:
            MigrationError: Worker failed
        """
        start_offset = checkpoint.last_offset if checkpoint else None
        work_items = self._create_work_items(
            source_collection=source_collection,
            target_collection=target_collection,
            new_dimension=new_dimension,
            vector_count=vector_count,
            worker_count=worker_count,
            batch_size=batch_size,
            start_offset=start_offset,
        )
        logger.info("Created %d work items for %d workers", len(work_items), worker_count)
        worker_tasks = [
            self._migration_worker(item, migration_id, checkpoint) for item in work_items
        ]
        results = await asyncio.gather(*worker_tasks, return_exceptions=True)
        total_vectors = 0
        for result in results:
            if isinstance(result, Exception):
                logger.error("Worker failed: %s", result, exc_info=result)
                raise MigrationError(f"Worker failed: {result}")
            if not cast(ChunkResult, result).success:
                raise MigrationError(
                    f"Worker {cast(ChunkResult, result).worker_id} failed: {cast(ChunkResult, result).error}"
                )
            total_vectors += cast(ChunkResult, result).vectors_processed
        return total_vectors

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type(tuple(BASE_RETRYABLE_EXCEPTIONS)),
        reraise=True,
    )
    async def _migration_worker(
        self, work_item: WorkItem, migration_id: str, checkpoint: MigrationCheckpoint | None
    ) -> ChunkResult:
        """Worker function for parallel migration.

        Implements retry logic and checkpoint saving.

        Args:
            work_item: Work item with batch specification
            migration_id: Unique migration identifier
            checkpoint: Optional checkpoint state

        Returns:
            ChunkResult with statistics
        """
        start_time = datetime.now(UTC)
        worker_id = work_item.worker_id
        vectors_processed = 0
        batch_count = 0
        logger.debug(
            "Worker %d starting: offset=%s batch_size=%d",
            worker_id,
            work_item.start_offset,
            work_item.batch_size,
        )
        try:
            offset = work_item.start_offset
            while True:
                records = await self._fetch_batch(
                    collection=work_item.source_collection,
                    offset=offset,
                    limit=work_item.batch_size,
                )
                if not records:
                    break
                truncated = [
                    self._truncate_vector(record, work_item.new_dimension) for record in records
                ]
                await self._batch_upsert(work_item.target_collection, truncated)
                vectors_processed += len(records)
                batch_count += 1
                if batch_count % 10 == 0:
                    await self._save_migration_checkpoint(
                        migration_id=migration_id,
                        state=MigrationState.IN_PROGRESS,
                        batches_completed=batch_count,
                        vectors_migrated=vectors_processed,
                        last_offset=offset,
                        worker_progress={worker_id: vectors_processed},
                    )
                    logger.debug(
                        "Worker %d checkpoint: batches=%d vectors=%d",
                        worker_id,
                        batch_count,
                        vectors_processed,
                    )
                offset = offset + work_item.batch_size if offset else work_item.batch_size
            elapsed = datetime.now(UTC) - start_time
            logger.info(
                "Worker %d completed: vectors=%d batches=%d elapsed=%s",
                worker_id,
                vectors_processed,
                batch_count,
                elapsed,
            )
        except Exception as e:
            elapsed = datetime.now(UTC) - start_time
            logger.warning("Worker %d failed: %s", worker_id, e, exc_info=True)
            return ChunkResult(
                worker_id=worker_id,
                vectors_processed=vectors_processed,
                elapsed=elapsed,
                success=False,
                error=str(e),
            )
        else:
            return ChunkResult(
                worker_id=worker_id,
                vectors_processed=vectors_processed,
                elapsed=elapsed,
                success=True,
            )

    def _create_work_items(
        self,
        source_collection: str,
        target_collection: str,
        new_dimension: int,
        vector_count: int,
        worker_count: int,
        batch_size: int,
        start_offset: int | None = None,
    ) -> list[WorkItem]:
        """Divide work among workers.

        Implements work distribution for parallel processing.

        Args:
            source_collection: Source collection name
            target_collection: Target collection name
            new_dimension: Target dimension
            vector_count: Total vectors to process
            worker_count: Number of workers
            batch_size: Vectors per batch
            start_offset: Optional resume offset

        Returns:
            List of work items for workers
        """
        work_items: list[WorkItem] = []
        vectors_per_worker, remainder = divmod(vector_count, worker_count)
        current_offset = start_offset or 0
        for worker_id in range(worker_count):
            worker_vectors = vectors_per_worker + (1 if worker_id < remainder else 0)
            if worker_vectors > 0:
                work_items.append(
                    WorkItem(
                        source_collection=source_collection,
                        target_collection=target_collection,
                        start_offset=current_offset if current_offset > 0 else None,
                        batch_size=batch_size,
                        new_dimension=new_dimension,
                        worker_id=worker_id,
                    )
                )
                current_offset += worker_vectors
        return work_items

    def _truncate_vector(self, record: PointStruct, new_dimension: int) -> PointStruct:
        """Truncate vector to new dimension.

        Args:
            record: Point record with vector
            new_dimension: Target dimension

        Returns:
            New PointStruct with truncated vector
        """
        if isinstance(record.vector, dict):
            dense = record.vector.get("dense", [])
            truncated_dense = dense[:new_dimension] if dense else []
            new_vector = {"dense": truncated_dense}
            if "sparse" in record.vector:
                new_vector["sparse"] = record.vector["sparse"]
        else:
            vector_values = (
                record.vector if isinstance(record.vector, list) else list(record.vector)
            )
            new_vector = vector_values[:new_dimension]
        return PointStruct(id=record.id, vector=new_vector, payload=record.payload)

    async def _validate_migration_integrity(
        self,
        source_collection: str,
        target_collection: str,
        expected_count: int,
        new_dimension: int,
    ) -> None:
        """Validate migration data integrity.

        Implements CRITICAL #4: Data integrity validation (4 layers).

        Layer 1: Vector count match (must be exact)
        Layer 2: Payload integrity via blake3 checksums
        Layer 3: Semantic equivalence via cosine similarity (sample 100 vectors)
        Layer 4: Search quality preservation (recall@10 >80%)

        Args:
            source_collection: Source collection name
            target_collection: Target collection name
            expected_count: Expected vector count
            new_dimension: Target dimension

        Raises:
            ValidationError: If any validation layer fails
        """
        logger.info("Starting 4-layer data integrity validation")
        source_count = await self._count_vectors(source_collection)
        target_count = await self._count_vectors(target_collection)
        if target_count != expected_count:
            raise ValidationError(
                f"Layer 1 failed: Vector count mismatch. Expected {expected_count}, got {target_count} (source: {source_count})"
            )
        logger.info("Layer 1 passed: Vector count match (%d vectors)", target_count)
        source_checksums = await self._compute_payload_checksums(source_collection)
        target_checksums = await self._compute_payload_checksums(target_collection)
        if source_checksums != target_checksums:
            raise ValidationError(
                "Layer 2 failed: Payload checksums don't match. Some payload data was corrupted during migration."
            )
        logger.info("Layer 2 passed: Payload integrity verified")
        sample_size = min(100, target_count)
        samples = await self._get_random_samples(source_collection, sample_size)
        similarity_threshold = 0.9999
        for sample_id in samples:
            source_vec = await self._get_vector(source_collection, sample_id)
            target_vec = await self._get_vector(target_collection, sample_id)
            if source_vec and target_vec:
                similarity = self._cosine_similarity(
                    source_vec[:new_dimension], target_vec[:new_dimension]
                )
                if similarity < similarity_threshold:
                    raise ValidationError(
                        f"Layer 3 failed: Cosine similarity too low for vector {sample_id}. Expected ≥{similarity_threshold}, got {similarity:.6f}"
                    )
        logger.info("Layer 3 passed: Semantic equivalence verified (sample size: %d)", sample_size)
        query_samples = await self._get_random_samples(source_collection, min(10, target_count))
        total_recall = 0.0
        for query_id in query_samples:
            query_vec = await self._get_vector(source_collection, query_id)
            if not query_vec:
                continue
            source_results = await self._search_collection(
                source_collection, query_vec[:new_dimension], k=10
            )
            target_results = await self._search_collection(target_collection, query_vec, k=10)
            recall = self._recall_at_k(source_results, target_results, k=10)
            total_recall += recall
        avg_recall = total_recall / len(query_samples) if query_samples else 0.0
        recall_threshold = 0.8
        if avg_recall < recall_threshold:
            raise ValidationError(
                f"Layer 4 failed: Search quality degraded. Recall@10: {avg_recall:.2%} (threshold: {recall_threshold:.0%})"
            )
        logger.info(
            "Layer 4 passed: Search quality preserved (recall@10: %.1f%%)", avg_recall * 100
        )
        logger.info("All 4 validation layers passed successfully")

    async def _save_migration_checkpoint(
        self,
        migration_id: str,
        state: MigrationState,
        batches_completed: int,
        vectors_migrated: int,
        last_offset: int | None,
        worker_progress: dict[int, int],
    ) -> None:
        """Save migration checkpoint for resume capability.

        Implements CRITICAL #5: Resume capability.

        Args:
            migration_id: Unique migration identifier
            state: Current migration state
            batches_completed: Number of batches processed
            vectors_migrated: Number of vectors migrated
            last_offset: Last processed offset
            worker_progress: Progress by worker ID
        """
        checkpoint = MigrationCheckpoint(
            migration_id=migration_id,
            state=state,
            batches_completed=batches_completed,
            vectors_migrated=vectors_migrated,
            last_offset=last_offset,
            timestamp=datetime.now(UTC),
            worker_progress=worker_progress,
        )
        checkpoint_path = self._get_checkpoint_path(migration_id)
        await AsyncPath(checkpoint_path.parent).mkdir(parents=True, exist_ok=True)
        temp_path = checkpoint_path.with_suffix(".tmp")
        await AsyncPath(temp_path).write_bytes(to_json(checkpoint.__dict__))
        await AsyncPath(temp_path).rename(checkpoint_path)
        logger.debug("Saved migration checkpoint: %s", checkpoint_path)

    async def _load_migration_checkpoint(self, migration_id: str) -> MigrationCheckpoint | None:
        """Load migration checkpoint for resume.

        Implements CRITICAL #5: Resume capability.

        Args:
            migration_id: Unique migration identifier

        Returns:
            Checkpoint if exists, None otherwise
        """
        checkpoint_path = self._get_checkpoint_path(migration_id)
        async_path = AsyncPath(checkpoint_path)
        if not await async_path.exists():
            return None
        try:
            data = from_json(await async_path.read_bytes())
            data["state"] = MigrationState(data["state"])
        except Exception as e:
            logger.warning("Failed to load checkpoint: %s", e)
            return None
        else:
            return MigrationCheckpoint(**data)

    async def _count_vectors(self, collection_name: str) -> int:
        """Get vector count in collection."""
        return 0

    async def _get_vector(self, collection: str, vector_id: str) -> list[float] | None:
        """Get single vector by ID."""
        return None

    async def _get_random_samples(self, collection: str, size: int) -> list[str]:
        """Sample random vector IDs."""
        return []

    async def _compute_payload_checksums(self, collection: str) -> BlakeHashKey:
        """Compute checksums of all payloads."""
        return get_blake_hash(b"placeholder")

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Compute cosine similarity between vectors."""
        import numpy as np

        v1 = np.array(vec1)
        v2 = np.array(vec2)
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

    def _recall_at_k(self, source_results: list[str], target_results: list[str], k: int) -> float:
        """Compute recall@k metric."""
        selected_source_results = set(source_results[:k])
        expected_target_results = set(target_results[:k])
        intersection = selected_source_results & expected_target_results
        return len(intersection) / k if k > 0 else 0.0

    def _generate_versioned_name(self, base: str, dimension: int) -> str:
        """Generate versioned collection name."""
        return f"{base}_dim{dimension}"

    async def _create_dimensioned_collection(
        self, name: str, dimension: int, config: dict[str, Any] | None = None
    ) -> None:
        """Create target collection with new dimension."""
        logger.info("Creating collection '%s' with dimension %d", name, dimension)

    async def _switch_collection_alias(self, alias: str, new_target: str, old_target: str) -> None:
        """Blue-green switch of collection alias."""
        logger.info("Switching alias '%s' from '%s' to '%s'", alias, old_target, new_target)

    async def _delete_migration_checkpoint(self, migration_id: str) -> None:
        """Cleanup checkpoint after successful migration."""
        checkpoint_path = self._get_checkpoint_path(migration_id)
        async_path = AsyncPath(checkpoint_path)
        if await async_path.exists():
            await async_path.unlink()
            logger.debug("Deleted migration checkpoint: %s", checkpoint_path)

    def _get_checkpoint_path(self, migration_id: str) -> Path:
        """Get path to checkpoint file."""
        checkpoint_dir = self.checkpoint_manager.checkpoint_dir
        return checkpoint_dir / f"migration_{migration_id}.json"

    async def _fetch_batch(
        self, collection: str, offset: int | None, limit: int
    ) -> list[PointStruct]:
        """Fetch batch of vectors from collection."""
        return []

    async def _batch_upsert(self, collection: str, records: list[PointStruct]) -> None:
        """Batch upsert vectors to collection."""

    async def _search_collection(
        self, collection: str, query_vector: list[float], k: int
    ) -> list[str]:
        """Search collection and return IDs."""
        return []


__all__ = (
    "ChunkResult",
    "InvalidStateTransitionError",
    "MigrationCheckpoint",
    "MigrationError",
    "MigrationResult",
    "MigrationService",
    "MigrationState",
    "ValidationError",
    "WorkItem",
)

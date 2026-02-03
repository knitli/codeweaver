# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Vector reconciliation service for backup vector validation and repair.

This service ensures that all points in the vector store have the required backup
vectors. It operates in a lazy repair mode, only fixing points that are missing
backup vectors rather than proactively checking everything.

The service integrates with the failover maintenance loop and runs periodically
to ensure backup vector coverage for disaster recovery scenarios.
"""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING, TypedDict

from codeweaver.core import CodeChunk
from codeweaver.core.constants import (
    BACKUP_DENSE_VECTOR_NAME,
    DEFAULT_RECONCILIATION_SERVICE_BATCH_SIZE,
)
from codeweaver.providers.config.backup_models import get_backup_embedding_provider


if TYPE_CHECKING:
    from qdrant_client import models as qmodels

    from codeweaver.providers.embedding.providers.base import EmbeddingProvider
    from codeweaver.providers.vector_stores.base import VectorStoreProvider

logger = logging.getLogger(__name__)


class RepairStats(TypedDict):
    """Statistics for repair operations."""

    repaired: int
    failed: int
    errors: list[str]


class ReconciliationResult(TypedDict):
    """Results from reconciliation operations."""

    detected: int
    repaired: int
    failed: int
    errors: list[str]


class VectorReconciliationService:
    """Service for reconciling backup vectors in the vector store.

    This service ensures that all points have the required backup vectors for
    failover scenarios. It operates in two modes:

    1. Detection: Identify points missing backup vectors
    2. Repair: Generate and add missing backup vectors

    The service uses batch processing for efficiency and integrates with
    the failover maintenance loop for periodic execution.
    """

    def __init__(
        self,
        vector_store: VectorStoreProvider,
        backup_vector_name: str = BACKUP_DENSE_VECTOR_NAME,
        batch_size: int = DEFAULT_RECONCILIATION_SERVICE_BATCH_SIZE,
    ) -> None:
        """Initialize the reconciliation service.

        Args:
            vector_store: Vector store provider to reconcile
            backup_vector_name: Name of the backup vector field
            batch_size: Number of points to process per batch
        """
        self.vector_store = vector_store
        self.backup_vector_name = backup_vector_name
        self.batch_size = batch_size
        self._backup_provider: EmbeddingProvider | None = None

    async def _get_backup_provider(self) -> EmbeddingProvider | None:
        """Get or create backup embedding provider.

        Returns:
            Backup embedding provider instance, or None if unavailable
        """
        if self._backup_provider is None:
            self._backup_provider = await get_backup_embedding_provider()

        return self._backup_provider

    async def detect_missing_vectors(
        self, collection_name: str, limit: int | None = None
    ) -> list[str]:
        """Detect points missing backup vectors.

        This method scrolls through the collection and identifies points that
        don't have the backup vector field populated.

        Args:
            collection_name: Name of collection to check
            limit: Maximum number of missing points to detect (None = all)

        Returns:
            List of point IDs missing backup vectors

        Example:
            >>> service = VectorReconciliationService(vector_store)
            >>> missing = await service.detect_missing_vectors("my_collection")
            >>> print(f"Found {len(missing)} points missing backup vectors")
        """
        missing_ids: list[str] = []
        offset: str | None = None

        logger.info(
            "Starting detection of missing backup vectors in collection: %s", collection_name
        )

        try:
            while True:
                # Scroll through collection in batches
                points, next_offset = await self.vector_store.scroll(
                    collection_name=collection_name,
                    limit=self.batch_size,
                    offset=offset,
                    with_vectors=True,  # Need vectors to check for backup
                )

                if not points:
                    break

                # Check each point for backup vector
                for point in points:
                    # Check if backup vector exists and is populated
                    if not self._has_backup_vector(point):
                        missing_ids.append(str(point.id))

                        # Stop if we've hit the limit
                        if limit and len(missing_ids) >= limit:
                            logger.info("Reached detection limit of %d missing points", limit)
                            return missing_ids

                # Update offset for next batch
                offset = next_offset
                if offset is None:
                    break

            logger.info(
                "Detection complete: found %d points missing backup vectors", len(missing_ids)
            )

        except Exception as e:
            logger.warning("Error detecting missing vectors: %s", e)
            raise
        else:
            return missing_ids

    def _has_backup_vector(self, point: qmodels.Record) -> bool:
        """Check if a point has a backup vector.

        Args:
            point: Qdrant point record to check

        Returns:
            True if point has backup vector, False otherwise
        """
        # Check if point has vectors
        if not hasattr(point, "vector") or point.vector is None:
            return False

        # Handle different vector formats
        vectors = point.vector

        # Single vector (not multi-vector)
        if isinstance(vectors, list):
            return False  # Single vector = no backup

        # Multi-vector format (dict of vectors)
        if isinstance(vectors, dict):
            backup_vector = vectors.get(self.backup_vector_name)
            # Check if backup vector exists and is non-empty
            if backup_vector is None:
                return False
            # Handle both list and SparseVector types
            return len(backup_vector) > 0 if isinstance(backup_vector, list) else True
        return False

    async def repair_missing_vectors(
        self, collection_name: str, point_ids: list[str]
    ) -> RepairStats:
        """Repair points by generating and adding missing backup vectors.

        This method retrieves the points, generates backup embeddings from their
        content, and updates the vector store with the new backup vectors.

        Args:
            collection_name: Name of collection containing points
            point_ids: List of point IDs to repair

        Returns:
            Dictionary with repair statistics:
            - repaired: Number of successfully repaired points
            - failed: Number of points that failed to repair
            - errors: List of error messages encountered

        Example:
            >>> missing = await service.detect_missing_vectors("collection")
            >>> stats = await service.repair_missing_vectors("collection", missing)
            >>> print(f"Repaired: {stats['repaired']}, Failed: {stats['failed']}")
        """
        if not point_ids:
            logger.info("No points to repair")
            return RepairStats(repaired=0, failed=0, errors=[])

        logger.info("Starting repair of %d points", len(point_ids))

        # Get backup embedding provider
        backup_provider = await self._get_backup_provider()
        if backup_provider is None:
            error_msg = "No backup embedding provider available"
            logger.error(error_msg)
            return RepairStats(repaired=0, failed=len(point_ids), errors=[error_msg])

        stats: RepairStats = RepairStats(repaired=0, failed=0, errors=[])

        # Process in batches
        for i in range(0, len(point_ids), self.batch_size):
            batch_ids = point_ids[i : i + self.batch_size]
            batch_result = await self._repair_batch(
                collection_name=collection_name,
                point_ids=batch_ids,
                backup_provider=backup_provider,
            )

            # Update statistics
            stats["repaired"] += batch_result["repaired"]
            stats["failed"] += batch_result["failed"]
            stats["errors"].extend(batch_result["errors"])

        logger.info(
            "Repair complete: repaired=%d, failed=%d, errors=%d",
            stats["repaired"],
            stats["failed"],
            len(stats["errors"]),
        )

        return stats

    async def _repair_batch(
        self, collection_name: str, point_ids: list[str], backup_provider: EmbeddingProvider
    ) -> RepairStats:
        """Repair a batch of points.

        Args:
            collection_name: Collection name
            point_ids: Batch of point IDs to repair
            backup_provider: Provider for generating backup embeddings

        Returns:
            Batch repair statistics
        """
        batch_stats: RepairStats = RepairStats(repaired=0, failed=0, errors=[])

        try:
            # Retrieve points with payload
            points = await self.vector_store.retrieve(
                collection_name=collection_name,
                ids=point_ids,
                with_vectors=False,  # Don't need existing vectors
                with_payload=True,  # Need content for embedding
            )

            if not points:
                error_msg = f"Failed to retrieve batch: {point_ids}"
                logger.warning(error_msg)
                batch_stats["failed"] = len(point_ids)
                batch_stats["errors"].append(error_msg)
                return batch_stats

            # Extract CodeChunk objects from payloads
            chunks: list[CodeChunk] = []
            point_map: dict[int, str] = {}  # index -> point_id

            for idx, point in enumerate(points):
                try:
                    # Reconstruct CodeChunk from payload
                    # CodeChunk is a pydantic model, use model_validate instead of from_dict
                    chunk = CodeChunk.model_validate(point.payload)
                    chunks.append(chunk)
                    point_map[idx] = str(point.id)
                except Exception as e:
                    error_msg = f"Failed to extract content from point {point.id}: {e}"
                    logger.warning(error_msg)
                    batch_stats["failed"] += 1
                    batch_stats["errors"].append(error_msg)

            if not chunks:
                return batch_stats

            # Generate backup embeddings
            try:
                # EmbeddingProvider.embed_documents expects Sequence[CodeChunk]
                embedding_result = await backup_provider.embed_documents(chunks)
                # Handle potential error result
                if isinstance(embedding_result, dict):
                    # EmbeddingErrorInfo case - treat as failure
                    error_msg = (
                        f"Embedding failed: {embedding_result.get('error', 'Unknown error')}"
                    )
                    logger.exception(error_msg)
                    batch_stats["failed"] += len(chunks)
                    batch_stats["errors"].append(error_msg)
                    return batch_stats
                backup_embeddings = embedding_result
            except Exception as e:
                error_msg = f"Failed to generate backup embeddings: {e}"
                logger.exception(error_msg)
                batch_stats["failed"] += len(chunks)
                batch_stats["errors"].append(error_msg)
                return batch_stats

            # Update points with backup vectors
            for idx, embedding in enumerate(backup_embeddings):
                point_id = point_map[idx]
                try:
                    await self.vector_store.update_vectors(
                        collection_name=collection_name,
                        points=[{"id": point_id, "vector": {self.backup_vector_name: embedding}}],
                    )
                    batch_stats["repaired"] += 1

                except Exception as e:
                    error_msg = f"Failed to update point {point_id}: {e}"
                    logger.warning(error_msg)
                    batch_stats["failed"] += 1
                    batch_stats["errors"].append(error_msg)

        except Exception as e:
            error_msg = f"Batch repair failed: {e}"
            logger.exception(error_msg)
            batch_stats["failed"] = len(point_ids)
            batch_stats["errors"].append(error_msg)

        return batch_stats

    async def reconcile(
        self, collection_name: str, *, auto_repair: bool = True, detection_limit: int | None = None
    ) -> ReconciliationResult:
        """Perform full reconciliation: detect and optionally repair missing vectors.

        This is the main entry point for the reconciliation service. It detects
        points missing backup vectors and optionally repairs them.

        Args:
            collection_name: Collection to reconcile
            auto_repair: Whether to automatically repair detected issues
            detection_limit: Maximum points to detect (None = all)

        Returns:
            Dictionary with reconciliation results:
            - detected: Number of points missing backup vectors
            - repaired: Number of successfully repaired points
            - failed: Number of points that failed to repair
            - errors: List of error messages

        Example:
            >>> service = VectorReconciliationService(vector_store)
            >>> result = await service.reconcile("my_collection", auto_repair=True)
            >>> print(f"Detected: {result['detected']}, Repaired: {result['repaired']}")
        """
        logger.info(
            "Starting reconciliation for collection: %s (auto_repair=%s)",
            collection_name,
            auto_repair,
        )

        # Detect missing vectors
        missing_ids = await self.detect_missing_vectors(
            collection_name=collection_name, limit=detection_limit
        )

        result: ReconciliationResult = ReconciliationResult(
            detected=len(missing_ids), repaired=0, failed=0, errors=[]
        )

        # Repair if enabled
        if auto_repair and missing_ids:
            repair_stats = await self.repair_missing_vectors(
                collection_name=collection_name, point_ids=missing_ids
            )
            result["repaired"] = repair_stats["repaired"]
            result["failed"] = repair_stats["failed"]
            result["errors"] = repair_stats["errors"]

        logger.info(
            "Reconciliation complete: detected=%d, repaired=%d, failed=%d",
            result["detected"],
            result["repaired"],
            result["failed"],
        )

        return result

    async def cleanup(self) -> None:
        """Cleanup service resources."""
        if self._backup_provider is not None:
            # Check if cleanup method exists and is callable
            cleanup_method = getattr(self._backup_provider, "cleanup", None)
            if cleanup_method is not None and callable(cleanup_method):
                await cleanup_method()
            self._backup_provider = None


__all__ = ("VectorReconciliationService",)

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Snapshot backup service for Qdrant vector store disaster recovery.

This service creates and manages periodic snapshots of the vector store for
point-in-time recovery scenarios. It integrates with the failover maintenance
loop and handles snapshot retention, cleanup, and storage management.
"""

from __future__ import annotations

import asyncio
import logging

from datetime import UTC, datetime
from inspect import isawaitable
from pathlib import Path
from types import CoroutineType
from typing import TYPE_CHECKING, Any, TypedDict, cast

from pydantic import NonNegativeInt

from codeweaver import QdrantBaseProvider
from codeweaver.core import get_user_state_dir
from codeweaver.core.constants import DEFAULT_SNAPSHOT_RETENTION_COUNT, ONE_MINUTE
from codeweaver.core.utils.general import generate_collection_name


if TYPE_CHECKING:
    from qdrant_client.http.models import SnapshotDescription
else:
    SnapshotDescription = dict[str, Any]


logger = logging.getLogger(__name__)


class CleanupStatsDict(TypedDict):
    """Dictionary for snapshot cleanup statistics."""

    total: NonNegativeInt
    kept: NonNegativeInt
    deleted: NonNegativeInt
    failed: NonNegativeInt


class SnapshotMetaDict(TypedDict):
    """Metadata dictionary for snapshot operations results."""

    snapshot_name: str | None
    snapshot_created: bool
    cleanup_stats: CleanupStatsDict


class QdrantSnapshotBackupService:
    """Service for creating and managing Qdrant vector store snapshots.

    This service provides periodic snapshot creation for disaster recovery,
    with automatic retention management and support for local/cloud storage.

    Features:
    - Periodic snapshot creation
    - Automatic retention management (keep N most recent snapshots)
    - Local and cloud storage support
    - Graceful error handling
    - Integration with failover maintenance loop
    """

    def __init__(
        self,
        vector_store: QdrantBaseProvider,
        storage_path: Path | str | None = None,
        retention_count: int = DEFAULT_SNAPSHOT_RETENTION_COUNT,
        collection_name: str | None = None,
    ) -> None:
        """Initialize the snapshot backup service.

        Args:
            vector_store: Vector store provider to snapshot
            storage_path: Path for local snapshot storage (None = default path)
            retention_count: Number of snapshots to retain (default: 12)
            collection_name: Collection name (None = use vector_store default)
        """
        self.vector_store = vector_store
        self.retention_count = retention_count
        self.collection_name = (
            collection_name
            or cast(QdrantBaseProvider, vector_store).collection_name
            or generate_collection_name()
        )
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            state_dir = get_user_state_dir()
            self.storage_path = Path(state_dir) / "snapshots" / self.collection_name
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def create_snapshot(self, *, wait: bool = True) -> str | None:
        """Create a new snapshot of the collection.

        Args:
            wait: Whether to wait for snapshot creation to complete

        Returns:
            Snapshot name if successful, None otherwise

        Example:
            >>> service = QdrantSnapshotBackupService(vector_store)
            >>> snapshot_name = await service.create_snapshot()
            >>> print(f"Created snapshot: {snapshot_name}")
        """
        try:
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            snapshot_name = f"snapshot_{self.collection_name}_{timestamp}"
            logger.info("Creating snapshot: %s", snapshot_name)
            await asyncio.to_thread(
                self.vector_store.client.create_snapshot,
                collection_name=self.collection_name,
                snapshot_name=snapshot_name,
            )
            if wait:
                await self._wait_for_snapshot(snapshot_name)
            logger.info("Successfully created snapshot: %s", snapshot_name)
        except Exception as e:
            logger.warning(
                "Failed to create snapshot for collection %s: %s", self.collection_name, e
            )
            return None
        else:
            return snapshot_name

    async def _wait_for_snapshot(
        self, snapshot_name: str, snapshot_timeout: int = ONE_MINUTE
    ) -> bool:
        """Wait for snapshot creation to complete.

        Args:
            snapshot_name: Name of the snapshot to wait for
            snapshot_timeout: Maximum wait time in seconds

        Returns:
            True if snapshot is ready, False if timeout or error
        """
        try:
            async with asyncio.timeout(snapshot_timeout):
                while True:
                    try:
                        snapshots = await asyncio.to_thread(
                            self.vector_store.client.list_snapshots,
                            collection_name=self.collection_name,
                        )
                        if any(
                            s.name == snapshot_name
                            for s in (await snapshots if isawaitable(snapshots) else snapshots)
                        ):
                            return True
                        await asyncio.sleep(1)
                    except Exception as e:
                        logger.warning("Error checking snapshot status: %s", e)
                        await asyncio.sleep(1)
        except TimeoutError:
            logger.warning("Snapshot creation timeout for: %s", snapshot_name)
            return False

    @staticmethod
    def _normalize_snapshot(snapshot: Any) -> SnapshotDescription:
        """Normalize a snapshot object or dict to a consistent dict format.

        Args:
            snapshot: A snapshot object or dict from the Qdrant client.

        Returns:
            A normalized dict with name, size, and created_at keys.
        """
        if isinstance(snapshot, dict):
            return cast(SnapshotDescription, snapshot)
        # Qdrant SnapshotDescription uses "creation_time"; older versions may use "created_at"
        return cast(
            SnapshotDescription,
            {
                "name": getattr(snapshot, "name", None),
                "size": getattr(snapshot, "size", None),
                "created_at": (
                    getattr(snapshot, "creation_time", None)
                    or getattr(snapshot, "created_at", None)
                ),
            },
        )

    async def list_snapshots(self) -> list[SnapshotDescription]:
        """List all available snapshots for the collection.

        Returns:
            List of snapshot metadata dictionaries

        Example:
            >>> snapshots = await service.list_snapshots()
            >>> for snapshot in snapshots:
            ...     print(f"{snapshot['name']}: {snapshot['size']} bytes")
        """
        try:
            snapshots: CoroutineType[Any, Any, list[Any]] = await asyncio.to_thread(
                self.vector_store.client.list_snapshots, collection_name=self.collection_name
            )
        except Exception as e:
            logger.warning("Failed to list snapshots: %s", e)
            return []
        else:
            raw = await snapshots if isawaitable(snapshots) else snapshots
            return [self._normalize_snapshot(s) for s in raw]

    async def delete_snapshot(self, snapshot_name: str) -> bool:
        """Delete a specific snapshot.

        Args:
            snapshot_name: Name of the snapshot to delete

        Returns:
            True if successfully deleted, False otherwise
        """
        try:
            await asyncio.to_thread(
                self.vector_store.client.delete_snapshot,
                collection_name=self.collection_name,
                snapshot_name=snapshot_name,
            )
            logger.info("Deleted snapshot: %s", snapshot_name)
        except Exception as e:
            logger.warning("Failed to delete snapshot %s: %s", snapshot_name, e)
            return False
        else:
            return True

    async def cleanup_old_snapshots(self) -> CleanupStatsDict:
        """Delete old snapshots beyond retention count.

        Keeps the N most recent snapshots (configured by retention_count).

        Returns:
            Dictionary with cleanup statistics:
            - total: Total snapshots found
            - kept: Number of snapshots retained
            - deleted: Number of snapshots deleted
            - failed: Number of deletion failures

        Example:
            >>> stats = await service.cleanup_old_snapshots()
            >>> print(f"Deleted {stats['deleted']} old snapshots")
        """
        try:
            snapshots = await self.list_snapshots()
            stats = {"total": len(snapshots), "kept": 0, "deleted": 0, "failed": 0}
            if len(snapshots) <= self.retention_count:
                stats["kept"] = len(snapshots)
                logger.debug(
                    "No cleanup needed: %d snapshots (limit: %d)",
                    len(snapshots),
                    self.retention_count,
                )
                return CleanupStatsDict(**stats)  # ty:ignore[missing-typed-dict-key]
            snapshots_sorted = sorted(
                snapshots,
                key=lambda s: s.get("created_at") or "",
                reverse=True,
            )
            to_keep = snapshots_sorted[: self.retention_count]
            to_delete = snapshots_sorted[self.retention_count :]
            stats["kept"] = len(to_keep)
            logger.info(
                "Cleaning up snapshots: keeping %d, deleting %d", len(to_keep), len(to_delete)
            )
            for snapshot in to_delete:
                snapshot_name = snapshot.get("name")
                if not snapshot_name:
                    logger.warning("Skipping snapshot without name during cleanup: %r", snapshot)
                    stats["failed"] += 1
                    continue
                if await self.delete_snapshot(snapshot_name):
                    stats["deleted"] += 1
                else:
                    stats["failed"] += 1
            logger.info(
                "Snapshot cleanup complete: deleted=%d, failed=%d",
                stats["deleted"],
                stats["failed"],
            )
        except Exception as e:
            logger.warning("Snapshot cleanup failed: %s", e, exc_info=True)
            return CleanupStatsDict(total=0, kept=0, deleted=0, failed=0)
        else:
            return CleanupStatsDict(**stats)  # ty:ignore[missing-typed-dict-key]

    async def restore_snapshot(self, snapshot_name: str, *, wait: bool = True) -> bool:
        """Restore the collection from a snapshot.

        WARNING: This operation replaces the entire collection with the snapshot state.

        Args:
            snapshot_name: Name of the snapshot to restore
            wait: Whether to wait for restore operation to complete

        Returns:
            True if restore initiated successfully, False otherwise

        Example:
            >>> success = await service.restore_snapshot("snapshot_20250127_120000")
            >>> if success:
            ...     print("Restore completed successfully")
        """
        try:
            logger.warning(
                "Restoring collection %s from snapshot: %s", self.collection_name, snapshot_name
            )
            await asyncio.to_thread(
                self.vector_store.client.recover_snapshot,
                collection_name=self.collection_name,
                snapshot_name=snapshot_name,
                wait=wait,
            )
            logger.info(
                "Successfully restored collection %s from snapshot: %s",
                self.collection_name,
                snapshot_name,
            )
        except Exception as e:
            logger.warning(
                "Failed to restore snapshot %s for collection %s: %s",
                snapshot_name,
                self.collection_name,
                e,
                exc_info=True,
            )
            return False
        else:
            return True

    async def get_latest_snapshot(self) -> SnapshotDescription | None:
        """Get metadata for the most recent snapshot.

        Returns:
            Snapshot metadata dictionary, or None if no snapshots exist
        """
        snapshots = await self.list_snapshots()
        if not snapshots:
            return None
        return max(
            snapshots,
            key=lambda s: s.get("created_at") or "",
        )

    async def snapshot_and_cleanup(self, *, wait: bool = False) -> SnapshotMetaDict:
        """Create a new snapshot and clean up old ones.

        This is the main method for periodic snapshot maintenance.
        It combines snapshot creation and retention management.

        Args:
            wait: Whether to wait for snapshot creation to complete

        Returns:
            Dictionary with operation results:
            - snapshot_created: Whether new snapshot was created successfully
            - snapshot_name: Name of new snapshot (None if failed)
            - cleanup_stats: Statistics from cleanup operation

        Example:
            >>> result = await service.snapshot_and_cleanup()
            >>> if result["snapshot_created"]:
            ...     print(f"Created: {result['snapshot_name']}")
            ...     print(f"Cleaned up: {result['cleanup_stats']['deleted']} old snapshots")
        """
        if snapshot_name := await self.create_snapshot(wait=wait):
            return SnapshotMetaDict(
                snapshot_created=True,
                snapshot_name=snapshot_name,
                cleanup_stats=await self.cleanup_old_snapshots(),
            )
        logger.error("Failed to create snapshot, skipping cleanup")
        return SnapshotMetaDict(
            snapshot_created=False,
            snapshot_name=None,
            cleanup_stats=CleanupStatsDict(total=0, kept=0, deleted=0, failed=0),
        )


__all__ = ("QdrantSnapshotBackupService",)

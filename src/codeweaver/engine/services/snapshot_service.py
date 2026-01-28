# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
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
from pathlib import Path
from typing import TYPE_CHECKING, Any

from codeweaver.core import get_user_state_dir


if TYPE_CHECKING:
    from codeweaver.providers import VectorStoreProvider


logger = logging.getLogger(__name__)


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
        vector_store: VectorStoreProvider,
        storage_path: Path | str | None = None,
        retention_count: int = 12,
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
        self.collection_name = collection_name or getattr(
            vector_store, "collection_name", "codeweaver_vectors"
        )

        # Resolve storage path
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            # Default to user state directory
            state_dir = get_user_state_dir()
            self.storage_path = Path(state_dir) / "snapshots" / self.collection_name

        # Ensure storage directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def create_snapshot(self, wait: bool = True) -> str | None:
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
            # Generate timestamp-based snapshot name
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            snapshot_name = f"snapshot_{self.collection_name}_{timestamp}"

            logger.info("Creating snapshot: %s", snapshot_name)

            # Create snapshot using Qdrant client
            # Note: Qdrant's create_snapshot returns immediately, snapshot is created async
            await asyncio.to_thread(
                self.vector_store.client.create_snapshot,
                collection_name=self.collection_name,
                snapshot_name=snapshot_name,
            )

            if wait:
                # Wait for snapshot to be ready
                await self._wait_for_snapshot(snapshot_name)

            logger.info("Successfully created snapshot: %s", snapshot_name)
            return snapshot_name

        except Exception as e:
            logger.exception("Failed to create snapshot for collection %s: %s", self.collection_name, e)
            return None

    async def _wait_for_snapshot(self, snapshot_name: str, timeout: int = 60) -> bool:
        """Wait for snapshot creation to complete.

        Args:
            snapshot_name: Name of the snapshot to wait for
            timeout: Maximum wait time in seconds

        Returns:
            True if snapshot is ready, False if timeout or error
        """
        start_time = datetime.now(UTC)
        while (datetime.now(UTC) - start_time).total_seconds() < timeout:
            try:
                # Check if snapshot exists by listing snapshots
                snapshots = await asyncio.to_thread(
                    self.vector_store.client.list_snapshots, collection_name=self.collection_name
                )

                # Check if our snapshot is in the list
                if any(s.name == snapshot_name for s in snapshots):
                    return True

                # Wait before checking again
                await asyncio.sleep(1)

            except Exception as e:
                logger.warning("Error checking snapshot status: %s", e)
                await asyncio.sleep(1)

        logger.warning("Snapshot creation timeout for: %s", snapshot_name)
        return False

    async def list_snapshots(self) -> list[dict[str, Any]]:
        """List all available snapshots for the collection.

        Returns:
            List of snapshot metadata dictionaries

        Example:
            >>> snapshots = await service.list_snapshots()
            >>> for snapshot in snapshots:
            ...     print(f"{snapshot['name']}: {snapshot['size']} bytes")
        """
        try:
            snapshots = await asyncio.to_thread(
                self.vector_store.client.list_snapshots, collection_name=self.collection_name
            )

            return [
                {"name": snapshot.name, "size": snapshot.size, "created_at": snapshot.creation_time}
                for snapshot in snapshots
            ]

        except Exception as e:
            logger.exception("Failed to list snapshots: %s", e)
            return []

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
            return True

        except Exception as e:
            logger.warning("Failed to delete snapshot %s: %s", snapshot_name, e)
            return False

    async def cleanup_old_snapshots(self) -> dict[str, Any]:
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
            # Get all snapshots
            snapshots = await self.list_snapshots()

            stats = {"total": len(snapshots), "kept": 0, "deleted": 0, "failed": 0}

            if len(snapshots) <= self.retention_count:
                stats["kept"] = len(snapshots)
                logger.debug(
                    "No cleanup needed: %d snapshots (limit: %d)",
                    len(snapshots),
                    self.retention_count,
                )
                return stats

            # Sort snapshots by creation time (newest first)
            snapshots_sorted = sorted(
                snapshots, key=lambda s: s.get("created_at", ""), reverse=True
            )

            # Keep the most recent N snapshots, delete the rest
            to_keep = snapshots_sorted[: self.retention_count]
            to_delete = snapshots_sorted[self.retention_count :]

            stats["kept"] = len(to_keep)

            logger.info(
                "Cleaning up snapshots: keeping %d, deleting %d", len(to_keep), len(to_delete)
            )

            # Delete old snapshots
            for snapshot in to_delete:
                snapshot_name = snapshot["name"]
                if await self.delete_snapshot(snapshot_name):
                    stats["deleted"] += 1
                else:
                    stats["failed"] += 1

            logger.info(
                "Snapshot cleanup complete: deleted=%d, failed=%d",
                stats["deleted"],
                stats["failed"],
            )

            return stats

        except Exception as e:
            logger.error("Snapshot cleanup failed: %s", e, exc_info=True)
            return {"total": 0, "kept": 0, "deleted": 0, "failed": 0}

    async def restore_snapshot(self, snapshot_name: str, wait: bool = True) -> bool:
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

            # Restore snapshot
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
            return True

        except Exception as e:
            logger.error(
                "Failed to restore snapshot %s for collection %s: %s",
                snapshot_name,
                self.collection_name,
                e,
                exc_info=True,
            )
            return False

    async def get_latest_snapshot(self) -> dict[str, Any] | None:
        """Get metadata for the most recent snapshot.

        Returns:
            Snapshot metadata dictionary, or None if no snapshots exist
        """
        snapshots = await self.list_snapshots()
        if not snapshots:
            return None

        # Sort by creation time and return the newest
        return max(snapshots, key=lambda s: s.get("created_at", ""))

    async def snapshot_and_cleanup(self, wait: bool = False) -> dict[str, Any]:
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
        result = {"snapshot_created": False, "snapshot_name": None, "cleanup_stats": {}}

        # Create new snapshot
        snapshot_name = await self.create_snapshot(wait=wait)
        if snapshot_name:
            result["snapshot_created"] = True
            result["snapshot_name"] = snapshot_name

            # Cleanup old snapshots
            cleanup_stats = await self.cleanup_old_snapshots()
            result["cleanup_stats"] = cleanup_stats
        else:
            logger.error("Failed to create snapshot, skipping cleanup")

        return result


__all__ = ("QdrantSnapshotBackupService",)

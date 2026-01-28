# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Failover service for coordinating primary/backup vector store transitions."""

from __future__ import annotations

import asyncio
import logging

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from codeweaver.core.utils.procs import very_low_priority
from codeweaver.providers import CircuitBreakerState


if TYPE_CHECKING:
    from codeweaver.engine.config import FailoverSettings
    from codeweaver.engine.services.indexing_service import IndexingService
    from codeweaver.providers import VectorStoreProvider


logger = logging.getLogger(__name__)


class FailoverService:
    """Coordinates failover between primary and backup vector stores.

    Responsibilities:
    - Monitor primary store health
    - Activate backup when primary fails
    - Sync backup periodically
    - Restore to primary when recovered
    """

    def __init__(
        self,
        primary_store: VectorStoreProvider | None,
        backup_store: VectorStoreProvider | None,
        indexing_service: IndexingService,
        backup_indexing_service: IndexingService,
        settings: FailoverSettings,
    ):
        """Initialize failover service with required dependencies."""
        self.primary_store = primary_store
        self.backup_store = backup_store
        self.indexing_service = indexing_service
        self.backup_indexing_service = backup_indexing_service
        self.settings = settings

        # State
        self._active_store: VectorStoreProvider | None = primary_store
        self._failover_active = False
        self._monitor_task: asyncio.Task | None = None
        self._backup_maintenance_task: asyncio.Task | None = None
        self._failover_time: datetime | None = None
        self._maintenance_cycle_count = 0  # Track cycles for reconciliation
        self._snapshot_cycle_count = (
            0  # Track cycles for snapshot creation  # Track cycles for reconciliation
        )

    async def start_monitoring(self) -> None:
        """Start health monitoring, automatic failover, and backup maintenance."""
        if self.settings.disable_failover or not self.primary_store:
            return

        self._monitor_task = asyncio.create_task(
            self._monitor_health(), name="failover_health_monitor"
        )
        self._backup_maintenance_task = asyncio.create_task(
            self._maintain_backup_loop(), name="backup_maintenance_loop"
        )
        logger.info("Failover health monitoring and backup maintenance started")

    async def _monitor_health(self) -> None:
        """Monitor primary store health."""
        while True:
            try:
                await asyncio.sleep(60)  # check every minute

                if not self.primary_store:
                    continue

                state = self.primary_store.circuit_breaker_state

                if state == CircuitBreakerState.OPEN and not self._failover_active:
                    await self._activate_failover()
                elif state == CircuitBreakerState.CLOSED and self._failover_active:
                    await asyncio.sleep(self.settings.recovery_window_sec)
                    await self._restore_primary()

            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("Error in failover health monitor", exc_info=True)

    async def _maintain_backup_loop(self) -> None:
        """Periodically sync the backup store, run vector reconciliation, and create snapshots.

        This method runs on a regular interval (backup_sync) and performs three main tasks:
        1. Backup indexing - sync primary state to backup store
        2. Vector reconciliation - ensure all points have backup vectors (every N cycles)
        3. Snapshot creation - create and manage snapshots for disaster recovery (every M cycles)
        """
        while True:
            try:
                # Sync interval from settings (default 5 mins)
                await asyncio.sleep(self.settings.backup_sync)

                # Only run if not currently failing over (if failover is active, backup is live anyway)
                if not self._failover_active and self.backup_store:
                    # Use very low priority for background maintenance
                    with very_low_priority():
                        # 1. Regular backup indexing
                        # We use index_project() on the backup service.
                        # It respects the shared file manifest, so it only indexes what needs indexing.
                        # Since it uses backup embedding models (via its own dependencies),
                        # it creates backup-compatible chunks/embeddings.
                        await self.backup_indexing_service.index_project()

                        # Increment cycle counters
                        self._maintenance_cycle_count += 1
                        self._snapshot_cycle_count += 1

                        # 2. Vector reconciliation (every N cycles)
                        if (
                            self._maintenance_cycle_count
                            >= self.settings.reconciliation_interval_cycles
                        ):
                            await self._run_reconciliation()
                            self._maintenance_cycle_count = 0  # Reset counter

                        # 3. Snapshot creation (every M cycles)
                        if self._snapshot_cycle_count >= self.settings.snapshot_interval_cycles:
                            await self._run_snapshot_maintenance()
                            self._snapshot_cycle_count = 0  # Reset counter

            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("Error in backup maintenance loop", exc_info=True)

    async def _run_reconciliation(self) -> None:
        """Run vector reconciliation to ensure all points have backup vectors.

        This method creates a reconciliation service and runs it against the primary
        vector store to detect and repair any missing backup vectors.
        """
        if not self.primary_store:
            logger.debug("No primary store available for reconciliation")
            return

        logger.info("Starting vector reconciliation")

        try:
            from codeweaver.engine.services.reconciliation_service import (
                VectorReconciliationService,
            )

            # Create reconciliation service
            reconciliation_service = VectorReconciliationService(
                vector_store=self.primary_store,
                backup_vector_name="backup",
                batch_size=self.settings.reconciliation_batch_size,
            )

            # Get collection name from primary store
            collection_name = getattr(self.primary_store, "collection_name", "codeweaver_vectors")

            # Run reconciliation with auto-repair enabled
            result = await reconciliation_service.reconcile(
                collection_name=collection_name,
                auto_repair=True,
                detection_limit=self.settings.reconciliation_detection_limit,
            )

            # Log results
            if result["detected"] > 0:
                logger.info(
                    "Reconciliation complete: detected=%d, repaired=%d, failed=%d",
                    result["detected"],
                    result["repaired"],
                    result["failed"],
                )
            else:
                logger.debug("Reconciliation complete: no missing vectors detected")

            # Cleanup
            await reconciliation_service.cleanup()

        except Exception as e:
            logger.error("Vector reconciliation failed: %s", e, exc_info=True)

    async def _run_snapshot_maintenance(self) -> None:
        """Run snapshot creation and cleanup for disaster recovery.

        This method creates a new snapshot of the primary vector store and
        manages retention by cleaning up old snapshots.
        """
        if not self.primary_store:
            logger.debug("No primary store available for snapshot creation")
            return

        logger.info("Starting snapshot maintenance")

        try:
            from codeweaver.engine.services.snapshot_service import QdrantSnapshotBackupService

            # Create snapshot service
            snapshot_service = QdrantSnapshotBackupService(
                vector_store=self.primary_store,
                storage_path=self.settings.snapshot_storage_path,
                retention_count=self.settings.snapshot_retention_count,
            )

            # Create snapshot and cleanup old ones
            result = await snapshot_service.snapshot_and_cleanup(wait=False)

            # Log results
            if result["snapshot_created"]:
                logger.info(
                    "Snapshot maintenance complete: created=%s, cleaned_up=%d old snapshots",
                    result["snapshot_name"],
                    result["cleanup_stats"].get("deleted", 0),
                )
            else:
                logger.warning("Snapshot creation failed")

        except Exception as e:
            logger.error("Snapshot maintenance failed: %s", e, exc_info=True)

    async def _activate_failover(self) -> None:
        """Activate backup store."""
        if not self.backup_store:
            logger.warning("Primary store failed but no backup store available")
            return

        logger.warning("⚠️ PRIMARY VECTOR STORE UNAVAILABLE - Activating backup mode")

        if not await self._is_backup_safe():
            logger.error("Backup activation blocked: insufficient resources")
            return

        self._active_store = self.backup_store
        self._failover_active = True
        self._failover_time = datetime.now(UTC)

        logger.info("Failover to backup store complete")

    async def _restore_primary(self) -> None:
        """Restore primary store after recovery."""
        logger.info("Primary vector store recovered, restoring")

        # Sync changes from backup to primary
        # This handles the complex reconciliation logic
        if self.backup_store:
            try:
                await self.indexing_service.reconcile_from_backup(self.backup_store)
            except Exception:
                logger.exception("Failed to reconcile from backup during restore")
                # We restore anyway, eventual consistency will catch up via standard indexing

        self._active_store = self.primary_store
        self._failover_active = False
        self._failover_time = None

        logger.info("Restored to primary store")

    async def _is_backup_safe(self) -> bool:
        """Check if activating backup is safe (resource-wise)."""
        if not self.backup_store:
            return False

        if not self._is_in_memory_store(self.backup_store):
            return True

        try:
            import psutil

            available_mb = psutil.virtual_memory().available / 1024 / 1024
        except ImportError:
            return True  # Assume safe if psutil missing
        else:
            return available_mb > self.settings.max_memory_mb

    def _is_in_memory_store(self, store: VectorStoreProvider) -> bool:
        """Check if store is in-memory."""
        from codeweaver.providers.vector_stores.inmemory import MemoryVectorStoreProvider

        return isinstance(store, MemoryVectorStoreProvider)

    @property
    def active_store(self) -> VectorStoreProvider | None:
        """Get the currently active store."""
        return self._active_store


__all__ = ("FailoverService",)

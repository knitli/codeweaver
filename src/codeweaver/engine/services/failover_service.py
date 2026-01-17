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
        settings: FailoverSettings,
    ):
        """Initialize failover service with required dependencies."""
        self.primary_store = primary_store
        self.backup_store = backup_store
        self.indexing_service = indexing_service
        self.settings = settings

        # State
        self._active_store: VectorStoreProvider | None = primary_store
        self._failover_active = False
        self._monitor_task: asyncio.Task | None = None
        self._failover_time: datetime | None = None

    async def start_monitoring(self) -> None:
        """Start health monitoring and automatic failover."""
        if self.settings.disable_failover or not self.primary_store:
            return

        self._monitor_task = asyncio.create_task(
            self._monitor_health(), name="failover_health_monitor"
        )
        logger.info("Failover health monitoring started")

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
                elif (
                    state == CircuitBreakerState.CLOSED
                    and self._failover_active
                    and self.settings.auto_restore
                ):
                    await asyncio.sleep(self.settings.restore_delay)
                    await self._restore_primary()

            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("Error in failover health monitor", exc_info=True)

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

        # In a real implementation, we would sync changes here

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

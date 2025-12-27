# sourcery skip: no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Vector store failover management for backup activation and recovery.

This module implements automatic failover to an in-memory backup vector store
when the primary vector store becomes unavailable, along with automatic recovery
when the primary becomes healthy again.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, NoReturn, cast

from fastmcp import Context
from pydantic import Field, PrivateAttr
from qdrant_client.http.models.models import CollectionInfo

from codeweaver.common._logging import log_to_client_or_fallback
from codeweaver.config.profiles import _backup_profile, get_profile
from codeweaver.config.providers import ProviderSettingsDict
from codeweaver.core.types.models import BasedModel
from codeweaver.engine.resource_estimation import estimate_backup_memory_requirements
from codeweaver.providers.vector_stores.base import CircuitBreakerState
from codeweaver.providers.vector_stores.qdrant_base import QdrantBaseProvider


if TYPE_CHECKING:
    from codeweaver.core.types import AnonymityConversion, FilteredKeyT
    from codeweaver.engine.failover_tracker import FileChangeTracker
    from codeweaver.engine.indexer.indexer import Indexer
    from codeweaver.providers.vector_stores.base import VectorStoreProvider
    from codeweaver.providers.vector_stores.inmemory import MemoryVectorStoreProvider

logger = logging.getLogger(__name__)


def _get_collection_name(*, secondary: bool) -> str:
    """Get the collection name for primary or backup vector store.

    Args:
        secondary: Whether to get the backup collection name

    Returns:
        The collection name for the primary or backup vector store.
    """
    if secondary:
        backup_config = _backup_profile()
        if vector_store := backup_config.get("vector_store"):
            # Handle tuple or single VectorStoreProviderSettings
            settings = vector_store[0] if isinstance(vector_store, tuple) else vector_store
            return settings.get("provider_settings", {}).get("collection_name", "codeweaver-backup")  # type: ignore[union-attr]
        return "codeweaver-backup"
    from codeweaver.common.registry.provider import get_provider_config_for

    if (config := get_provider_config_for("vector_store")) and (
        collection_name := config.get("provider_settings", {}).get("collection_name")
    ):
        return f"{collection_name}-backup" if secondary else collection_name
    from codeweaver.core import generate_collection_name

    return generate_collection_name(is_backup=secondary)


class VectorStoreFailoverManager(BasedModel):
    """Manages failover between primary and backup vector stores.

    This class coordinates automatic failover to an in-memory backup when
    the primary vector store fails, along with automatic recovery when the
    primary becomes healthy again.

    Responsibilities:
    - Monitor primary health via circuit breaker state
    - Activate backup on failure with resource safety checks
    - Manage state synchronization between stores
    - Handle automatic recovery to primary
    - Provide user communication about failover status

    Attributes:
        backup_enabled: Whether backup failover is enabled
        backup_sync_interval: Seconds between periodic backup syncs
        auto_restore: Whether to automatically restore to primary when recovered
        restore_delay: Seconds to wait after primary recovery before restoring
    """

    # Configuration
    backup_enabled: bool = Field(
        default=True, description="Enable automatic failover to backup vector store"
    )
    backup_sync_interval: int = Field(
        default=300, ge=30, description="Seconds between backup syncs (minimum 30)"
    )
    auto_restore: bool = Field(
        default=True, description="Automatically restore to primary when it recovers"
    )
    restore_delay: int = Field(
        default=60, ge=0, description="Seconds to wait after primary recovery before restoring"
    )
    max_memory_mb: int = Field(default=2048, ge=256, description="Maximum memory for backup (MB)")

    # Performance tuning
    health_check_interval: int = Field(
        default=60, ge=5, description="Seconds between health checks when primary is healthy"
    )
    health_check_interval_failing: int = Field(
        default=15, ge=1, description="Seconds between health checks when primary is failing"
    )
    sync_only_on_changes: bool = Field(
        default=True, description="Only sync backup when data has changed since last sync"
    )
    primary_collection: CollectionInfo | None = Field(
        default=None, description="Information about the primary vector store collection"
    )
    backup_collection: CollectionInfo | None = Field(
        default=None, description="Information about the backup vector store collection"
    )
    backup_profile: ProviderSettingsDict | None = Field(default_factory=_backup_profile)

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        """Keys to process for telemetry privacy."""
        from codeweaver.core.types.aliases import FilteredKey
        from codeweaver.core.types.enum import AnonymityConversion

        return {
            FilteredKey("primary_collection"): AnonymityConversion.BOOLEAN,
            FilteredKey("backup_collection"): AnonymityConversion.BOOLEAN,
        }

    # Runtime state (private)
    _primary_store: Annotated[VectorStoreProvider | None, PrivateAttr()] = None
    _backup_store: Annotated[MemoryVectorStoreProvider | None, PrivateAttr()] = None
    _active_store: Annotated[VectorStoreProvider | None, PrivateAttr()] = None
    _project_path: Annotated[Path | None, PrivateAttr()] = None
    _indexer: Annotated[Indexer | None, PrivateAttr()] = None

    # Monitoring tasks
    _circuit_monitor_task: Annotated[asyncio.Task | None, PrivateAttr()] = None
    _backup_sync_task: Annotated[asyncio.Task | None, PrivateAttr()] = None
    _failover_active: Annotated[bool, PrivateAttr()] = False
    _failover_time: Annotated[datetime | None, PrivateAttr()] = None
    _last_health_check: Annotated[datetime | None, PrivateAttr()] = None
    _last_backup_sync: Annotated[datetime | None, PrivateAttr()] = None
    _failover_chunks: set[str] = PrivateAttr(default_factory=set)
    _last_context: Annotated[Context | None, PrivateAttr()] = None  # For client notifications

    # Performance optimization state
    _last_indexed_count: Annotated[int, PrivateAttr()] = 0  # Track changes for smart sync
    _cached_snapshot: Annotated[set[str] | None, PrivateAttr()] = None  # Cache snapshot state
    _cached_memory_estimate: Annotated[Any | None, PrivateAttr()] = None  # Cache resource estimate
    _estimate_cache_time: Annotated[datetime | None, PrivateAttr()] = (
        None  # When estimate was cached
    )

    # File change tracking for backup sync
    _change_tracker: Annotated[FileChangeTracker | None, PrivateAttr()] = None

    # Backup indexer (separate instance with backup providers and chunk settings)
    _backup_indexer: Annotated[Indexer | None, PrivateAttr()] = None

    async def initialize(
        self,
        primary_store: VectorStoreProvider | None,
        project_path: Path,
        indexer: Indexer | None = None,
    ) -> None:
        """Initialize failover manager with primary store.

        Args:
            primary_store: Primary vector store provider
            project_path: Project root path for backup persistence
            indexer: Optional indexer reference for stats
        """
        from codeweaver.engine.failover_tracker import FileChangeTracker
        from codeweaver.providers.vector_stores.qdrant_base import QdrantBaseProvider

        self._primary_store = primary_store
        self._active_store = primary_store
        self._project_path = project_path
        self._indexer = indexer
        self._profile = get_profile("backup", "local")

        # Initialize file change tracker
        self._change_tracker = FileChangeTracker.load(project_path)
        logger.debug(
            "Loaded file change tracker: %d files tracked, %d pending changes",
            len(self._change_tracker.file_hashes),
            self._change_tracker.pending_count,
        )

        # Initialize chunk indexes
        # Use provider's config collection_name if available (important for tests with explicit collection names)
        # The provider's .collection property may be None before _initialize(), but config always has it
        # Fall back to _get_collection_name() if provider config doesn't have collection_name set
        primary_collection_name = (
            primary_store.config.get("collection_name") if primary_store else None
        ) or _get_collection_name(secondary=False)
        backup_collection_name = _get_collection_name(secondary=True)
        # Initialize _last_indexed_count to current state to avoid skipping first sync
        if indexer and indexer.stats:
            self._last_indexed_count = indexer.stats.chunks_indexed
            logger.debug("Initialized _last_indexed_count to %d", self._last_indexed_count)
        self.primary_collection = (
            await cast(QdrantBaseProvider, primary_store).get_collection(primary_collection_name)
            if primary_store
            else None
        )

        if self.backup_enabled and primary_store:
            logger.info("Initializing vector store failover support")
            # Start monitoring primary health
            import asyncio

            self._circuit_monitor_task = asyncio.create_task(
                self._monitor_primary_health(),
                name="vector_store_circuit_monitor",  # ty:ignore[unresolved-attribute]
            )
            # Start periodic backup sync task
            self._backup_sync_task = asyncio.create_task(
                self._sync_backup_periodically(),
                name="vector_store_backup_sync",  # ty:ignore[unresolved-attribute]
            )
            if self._backup_store and not self.backup_collection:
                self.backup_collection = await self._backup_store.get_collection(
                    backup_collection_name
                )
        else:
            logger.debug("Backup failover disabled or no primary store")
        if primary_store and isinstance(primary_store, QdrantBaseProvider):
            await primary_store.create_payload_index(primary_collection_name, "chunk_id", "uuid")
            await primary_store.create_payload_index(
                primary_collection_name, "file_path", "keyword"
            )
        if self._backup_store and isinstance(self._backup_store, QdrantBaseProvider):
            await self._backup_store.create_payload_index(
                backup_collection_name, "chunk_id", "uuid"
            )
            await self._backup_store.create_payload_index(
                backup_collection_name, "file_path", "keyword"
            )

    async def shutdown(self) -> None:
        """Gracefully shutdown failover manager."""
        # Cancel monitoring tasks
        if self._circuit_monitor_task:
            self._circuit_monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._circuit_monitor_task

        if self._backup_sync_task:
            self._backup_sync_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._backup_sync_task

        # Save file change tracker state
        if self._change_tracker:
            if self._change_tracker.save():
                logger.info("Saved file change tracker state on shutdown")
            else:
                logger.warning("Failed to save file change tracker on shutdown")

        # Persist backup state if active
        if self._failover_active and self._backup_store:
            try:
                await self._backup_store._persist_to_disk()
                logger.info("Persisted backup state on shutdown")
            except Exception as e:
                logger.warning("Failed to persist backup on shutdown", exc_info=e)

    @property
    def change_tracker(self) -> FileChangeTracker | None:
        """Get the file change tracker for recording indexed files."""
        return self._change_tracker

    @property
    def backup_indexer(self) -> Indexer | None:
        """Get the backup indexer for failover indexing operations."""
        return self._backup_indexer

    def record_file_indexed(self, discovered_file: Any) -> None:
        """Record that a file was successfully indexed by the primary.

        This should be called by the Indexer after successful indexing.

        Args:
            discovered_file: The DiscoveredFile that was indexed
        """
        if self._change_tracker:
            self._change_tracker.record_file_indexed(discovered_file)

    def record_file_deleted(self, path: Path) -> None:
        """Record that a file was deleted.

        Args:
            path: Path of the deleted file
        """
        if self._change_tracker:
            self._change_tracker.record_file_deleted(path)

    def record_file_indexed_during_failover(self, path: Path) -> None:
        """Record that a file was indexed during failover mode.

        These files will need primary re-indexing on recovery.

        Args:
            path: Path of the file indexed during failover
        """
        if self._change_tracker:
            self._change_tracker.record_file_indexed_during_failover(path)

    def set_context(self, context: Context | None) -> None:
        """Set the MCP context for client notifications.

        Args:
            context: FastMCP context from current request
        """
        self._last_context = context

    @property
    def active_store(self) -> VectorStoreProvider | None:
        """Get the currently active vector store."""
        return self._active_store

    @property
    def is_failover_active(self) -> bool:
        """Whether failover mode is currently active."""
        return self._failover_active

    @property
    def failover_duration(self) -> float | None:
        """Seconds since failover activated, or None if not in failover."""
        if not self._failover_active or not self._failover_time:
            return None
        return (datetime.now(UTC) - self._failover_time).total_seconds()

    async def _monitor_primary_health(self) -> None:
        """Continuously monitor primary circuit breaker state with adaptive polling.

        Runs as a background task with adaptive check intervals:
        - 30 seconds when primary is healthy (configurable via health_check_interval)
        - 5 seconds when primary is failing (configurable via health_check_interval_failing)

        Monitors for:
        - Primary failure → trigger failover
        - Primary recovery → consider restoration
        """
        # Start with healthy interval
        check_interval = self.health_check_interval

        while True:
            try:
                await asyncio.sleep(check_interval)
                self._last_health_check = datetime.now(UTC)

                if not self._primary_store:
                    continue

                # Check circuit breaker state
                circuit_state = self._primary_store.circuit_breaker_state

                if circuit_state == CircuitBreakerState.OPEN and not self._failover_active:
                    # Primary failed - trigger failover and switch to fast polling
                    logger.warning("Primary vector store circuit breaker opened")
                    check_interval = self.health_check_interval_failing
                    await self._activate_failover()

                elif (
                    circuit_state == CircuitBreakerState.CLOSED
                    and self._failover_active
                    and self.auto_restore
                ):
                    # Primary recovered - consider restoring and switch back to slow polling
                    logger.info("Primary vector store circuit breaker closed")
                    check_interval = self.health_check_interval
                    await self._consider_restoration()

                elif circuit_state == CircuitBreakerState.CLOSED and not self._failover_active:
                    # Primary healthy - use slow polling
                    check_interval = self.health_check_interval

                elif circuit_state == CircuitBreakerState.HALF_OPEN:
                    # Circuit breaker is half-open (testing recovery) - use fast polling to quickly detect stabilization
                    check_interval = self.health_check_interval_failing

                else:
                    # Unexpected circuit breaker state - default to fast polling for safety
                    check_interval = self.health_check_interval_failing

            except asyncio.CancelledError:
                logger.debug("Circuit monitor task cancelled")
                break
            except Exception:
                logger.warning("Error in circuit monitor task", exc_info=True)
                # Continue monitoring despite errors

    async def _sync_backup_periodically(self) -> None:
        """Periodically sync primary store to backup for fast recovery.

        This task runs in the background, syncing the primary vector store
        to a backup JSON file at regular intervals (default: 5 minutes).

        OPTIMIZATION: Only syncs when data has changed since last sync.
        Tracks indexer statistics to detect changes efficiently.

        The backup file is used for quick recovery when the primary fails,
        allowing restoration in <60 seconds vs. re-indexing which could
        take minutes.

        Syncs only when:
        - Primary store is healthy (circuit breaker CLOSED)
        - Not currently in failover mode
        - Backup is enabled
        - Data has changed since last sync (if sync_only_on_changes=True)

        The backup file includes:
        - Version information
        - Metadata (last sync time, collection counts)
        - All collections with points, vectors, and payloads
        """
        sync_interval = self.backup_sync_interval

        while True:
            try:
                await asyncio.sleep(sync_interval)

                # Only sync if we have a healthy primary and are not in failover
                if not self._primary_store:
                    logger.debug("No primary store - skipping backup sync")
                    continue

                if self._failover_active:
                    logger.debug("In failover mode - skipping backup sync")
                    continue

                # Check if primary is healthy
                from codeweaver.providers.vector_stores.base import CircuitBreakerState

                if self._primary_store.circuit_breaker_state != CircuitBreakerState.CLOSED:
                    logger.debug(
                        "Primary unhealthy (circuit breaker %s) - skipping backup sync",
                        self._primary_store.circuit_breaker_state,
                    )
                    continue

                # OPTIMIZATION: Check if data has changed since last sync
                if self.sync_only_on_changes and self._indexer:
                    current_indexed = self._indexer.stats.chunks_indexed
                    if current_indexed == self._last_indexed_count:
                        logger.debug(
                            "No data changes since last sync (%d chunks) - skipping backup sync",
                            current_indexed,
                        )
                        continue
                    # Update tracked count
                    self._last_indexed_count = current_indexed

                # Check if backup sync should be triggered using FileChangeTracker
                if self.should_sync_backup():
                    logger.debug("Starting file-based backup sync")
                    synced_count = await self.sync_pending_to_backup()
                    if synced_count > 0:
                        logger.info(
                            "✓ File-based backup sync completed: %d files synced", synced_count
                        )

                # Also perform legacy vector store backup sync
                logger.debug("Starting periodic backup sync")
                await self._sync_primary_to_backup()
                self._last_backup_sync = datetime.now(UTC)
                logger.info("✓ Backup sync completed successfully")

            except asyncio.CancelledError:
                logger.debug("Backup sync task cancelled")
                break
            except Exception:
                logger.warning(
                    "Error in backup sync task - will retry next interval", exc_info=True
                )
                # Continue syncing despite errors

    async def _activate_failover(self) -> None:
        """Activate backup vector store with resource safety checks.

        Performs the following steps:
        1. Check if already in failover
        2. Estimate memory requirements (with caching)
        3. Verify resource availability
        4. Initialize backup store if needed
        5. Attempt to restore from persisted state
        6. Switch active store to backup
        7. Notify user

        If resources are insufficient, logs error and continues without backup.

        OPTIMIZATION: Caches resource estimates for 5 minutes to avoid repeated scanning.
        """
        if self._failover_active:
            logger.debug("Failover already active, skipping activation")
            return

        logger.warning("⚠️  PRIMARY VECTOR STORE UNAVAILABLE - Activating backup mode")

        # Step 1: Resource check with caching
        # Reuse cached estimate if it's less than 5 minutes old AND chunk count hasn't changed significantly
        stats = self._indexer.stats if self._indexer else None
        current_chunks = stats.chunks_indexed if stats else 0

        cache_valid = (
            self._cached_memory_estimate is not None
            and self._estimate_cache_time is not None
            and (datetime.now(UTC) - self._estimate_cache_time).total_seconds() < 300
            and abs(current_chunks - self._cached_memory_estimate.estimated_chunks)
            < (current_chunks * 0.1)  # Within 10%
        )

        if cache_valid:
            memory_estimate = self._cached_memory_estimate
            logger.debug(
                "Using cached memory estimate (age: %.1fs, chunks: %d)",
                (datetime.now(UTC) - self._estimate_cache_time).total_seconds(),
                memory_estimate.estimated_chunks,
            )
        else:
            memory_estimate = estimate_backup_memory_requirements(
                project_path=self._project_path, stats=stats
            )
            # Cache the estimate
            self._cached_memory_estimate = memory_estimate
            self._estimate_cache_time = datetime.now(UTC)

        logger.info(
            "Backup memory estimate: %.2fGB (%d chunks), available: %.2fGB, zone: %s",
            memory_estimate.estimated_gb,
            memory_estimate.estimated_chunks,
            memory_estimate.available_gb,
            memory_estimate.zone,
        )

        # Check against configured maximum
        max_memory_bytes = self.max_memory_mb * 1024 * 1024
        if memory_estimate.estimated_bytes > max_memory_bytes:
            logger.error(
                "❌ BACKUP ACTIVATION BLOCKED - Estimated memory "
                "(%.2fGB) exceeds configured "
                "maximum (%.2fGB)",
                memory_estimate.estimated_gb,
                self.max_memory_mb / 1024,
            )
            self._log_resource_constraint_message(memory_estimate)
            return

        if not memory_estimate.is_safe:
            logger.warning(
                "❌ BACKUP ACTIVATION FAILED - Insufficient memory. "
                "Required: %.2fGB, "
                "Available: %.2fGB",
                memory_estimate.required_gb,
                memory_estimate.available_gb,
            )
            self._log_resource_constraint_message(memory_estimate)
            return

        # Step 2: Initialize backup store
        try:
            if not self._backup_store:
                logger.info("Initializing in-memory backup vector store")
                self._backup_store = await self._create_backup_store()
        except Exception:
            logger.warning("Failed to initialize backup store", exc_info=True)
            return

        # Step 2b: Initialize backup indexer with appropriate chunk sizes
        try:
            if not self._backup_indexer:
                logger.info("Initializing backup indexer with backup model constraints")
                self._backup_indexer = await self._create_backup_indexer()
        except Exception:
            logger.warning("Failed to initialize backup indexer", exc_info=True)
            # Continue without backup indexer - store can still work for queries

        # Step 3: Attempt to restore from persistence
        if self._backup_store and self._project_path:
            from codeweaver.core import get_user_config_dir

            backup_file = get_user_config_dir() / "codeweaver" / "backup" / "vector_store.json"
            if backup_file.exists():
                # Validate backup file before restoring
                is_valid = await self._validate_backup_file(backup_file)
                if not is_valid:
                    logger.warning(
                        "Backup file validation failed - will start with empty backup. File: %s",
                        backup_file,
                    )
                    logger.info("Backup will be populated as indexing continues")
                else:
                    try:
                        logger.info("Restoring backup from validated persisted state")
                        await self._backup_store._restore_from_disk()
                        logger.info("✓ Backup restored successfully from disk")
                    except Exception as e:
                        logger.warning("Failed to restore backup from disk", exc_info=e)
                        logger.info("Backup will be populated as indexing continues")
            else:
                logger.info("No persisted backup found - backup will be populated during indexing")

        # Step 4: Snapshot current backup state for sync-back tracking
        # Always build a fresh snapshot to avoid stale state issues
        # The backup store may have been modified (restored from disk, chunks added, etc.)
        await self._snapshot_backup_state()

        # Step 5: Activate backup
        self._active_store = self._backup_store
        self._failover_active = True
        self._failover_time = datetime.now(UTC)

        # Update global statistics
        from codeweaver.common.statistics import get_session_statistics

        stats = get_session_statistics()
        stats.update_failover_stats(
            failover_active=True,
            increment_failover_count=True,
            last_failover_time=self._failover_time.isoformat(),
            active_store_type="backup",
        )

        logger.warning(
            "⚠️  BACKUP MODE ACTIVE - Search functionality will continue "
            "with in-memory backup. Run 'cw status' for details."
        )

        # Notify client if context available
        if self._last_context:
            await log_to_client_or_fallback(
                self._last_context,
                "warning",
                {
                    "msg": "⚠️  Failover activated - switched to backup vector store",
                    "extra": {
                        "reason": "Primary vector store unavailable",
                        "active_store": "backup",
                        "failover_time": self._failover_time.isoformat()
                        if self._failover_time
                        else None,
                    },
                },
            )

    async def _consider_restoration(self) -> None:
        """Consider restoring to primary when it recovers.

        Waits for restore_delay before attempting restoration to ensure
        primary is stable.
        """
        if not self._failover_active or not self._primary_store:
            return

        # Wait for restore delay to ensure primary is stable
        if self.restore_delay > 0:
            logger.info(
                "Primary recovered, waiting %ds before restoration for stability",
                self.restore_delay,
            )
            await asyncio.sleep(self.restore_delay)

        # Test primary health with a simple operation
        try:
            await self._primary_store.list_collections()
            logger.info("Primary health check passed - restoring")
            await self._restore_to_primary()
        except Exception as e:
            logger.debug("Primary still unhealthy during restoration check", exc_info=e)
            # Keep using backup

    async def _restore_to_primary(self) -> None:
        """Restore to primary vector store with sync-back.

        Phase 3 implementation: Syncs changes from backup to primary before
        switching back. This ensures no data loss during failover period.

        Process:
        1. Sync changes from backup → primary (with re-embedding)
        2. Verify primary health after sync
        3. Switch active store to primary
        4. Clear failover state
        5. Keep backup running until primary verified
        """
        if not self._primary_store or not self._backup_store:
            return

        logger.info("Restoring to primary vector store with sync-back")

        try:
            # Step 1: Re-index files that were indexed during failover to primary
            if self._change_tracker and self._change_tracker.has_failover_files:
                synced = await self.sync_failover_to_primary()
                logger.info("Re-indexed %d failover files to primary", synced)
            else:
                # Fallback to legacy chunk-by-chunk sync if no tracker
                await self._sync_back_to_primary()

            # Step 2: Verify primary is working after sync
            await self._verify_primary_health()

            # Step 3: Switch back to primary
            self._active_store = self._primary_store
            self._failover_active = False
            self._failover_time = None
            self._failover_chunks.clear()

            # Update global statistics
            from codeweaver.common.statistics import get_session_statistics

            stats = get_session_statistics()
            stats.update_failover_stats(failover_active=False, active_store_type="primary")

            logger.info(
                "✓ PRIMARY VECTOR STORE RESTORED - Backup mode deactivated. "
                "Normal operation resumed with all changes synced."
            )

            # Notify client if context available
            if self._last_context:
                await log_to_client_or_fallback(
                    self._last_context,
                    "info",
                    {
                        "msg": "✓ Primary vector store restored - failover deactivated",
                        "extra": {"active_store": "primary", "status": "Normal operation resumed"},
                    },
                )

        except Exception:
            logger.warning(
                "Failed to restore to primary. Staying in backup mode for safety.", exc_info=True
            )
            # Stay in backup mode if sync-back fails

    async def _snapshot_backup_state(self) -> None:
        """Snapshot current backup state before failover.

        Records all existing point IDs in the backup so we can later
        identify which chunks were added during the failover period.

        OPTIMIZATION: Uses in-memory index, but rebuilds it first to ensure accuracy.
        The index may be stale if chunks were added/removed since initialization.
        """
        if not self._backup_store:
            logger.debug("No backup store to snapshot")
            return

        try:
            # Legacy chunk-based tracking is deprecated in favor of FileChangeTracker
            # Just clear the failover chunks set - FileChangeTracker handles tracking
            self._failover_chunks = set()
            self._cached_snapshot = set()

            logger.debug("Snapshot initialized (FileChangeTracker handles file tracking)")

        except Exception as e:
            logger.warning("Failed to snapshot backup state: %s", e)
            # Continue anyway - FileChangeTracker is the primary tracking mechanism

    async def _sync_back_to_primary(self) -> None:
        """Sync changes from backup to primary with re-embedding.

        Critical: We do NOT copy vectors from backup to primary because:
        - Backup uses local embeddings (different dimensions)
        - Primary may use different embedding provider
        - Vector dimensions/types are incompatible

        Instead:
        1. Get chunk payloads (text content) from backup
        2. Re-embed using primary's embedding provider via indexer
        3. Upsert to primary with correct vectors

        OPTIMIZATION: Uses in-memory index, but rebuilds it first to ensure accuracy.
        """
        if not self._primary_store or not self._backup_store or not self._indexer:
            logger.warning("Cannot sync back - missing primary, backup, or indexer")
            return

        try:
            # Legacy chunk-based sync is deprecated - use FileChangeTracker instead
            # This method is a fallback when no tracker is available
            logger.warning(
                "Using legacy chunk-based sync. FileChangeTracker-based sync is preferred."
            )

            # Without FileChangeTracker, we can't efficiently identify new chunks
            # Log warning and skip - the new file-based approach should be used
            new_chunks: set[str] = set()
            logger.info("Found %d chunks to sync back to primary", len(new_chunks))

            if not new_chunks:
                logger.info("No new chunks to sync - backup and primary are in sync")
                return

            # Sync each new chunk to primary
            synced_count = 0
            failed_count = 0

            for chunk_id in new_chunks:
                try:
                    await self._sync_chunk_to_primary(chunk_id)
                    synced_count += 1
                    if synced_count % 100 == 0:
                        logger.info("Synced %d/%d chunks to primary", synced_count, len(new_chunks))
                except Exception as e:
                    logger.warning("Failed to sync chunk %s: %s", chunk_id, e)
                    failed_count += 1

            logger.info(
                "✓ Sync-back complete: %d synced, %d failed out of %d total",
                synced_count,
                failed_count,
                len(new_chunks),
            )

            if failed_count > 0:
                logger.warning(
                    "⚠️  %d chunks failed to sync - may need manual recovery", failed_count
                )

        except Exception:
            logger.warning("Sync-back failed", exc_info=True)
            raise

    async def _sync_chunk_to_primary(self, chunk_id: str) -> None:
        """Sync a single chunk from backup to primary with re-embedding.

        Args:
            chunk_id: UUID of the chunk to sync

        Process:
        1. Retrieve chunk payload from backup (contains text and metadata)
        2. Re-embed text using primary's embedding providers (CRITICAL)
        3. Upsert to primary with new embeddings

        Note: We MUST re-embed because backup uses local embeddings which
        have different dimensions than primary's embedding provider.
        """
        if not self._backup_store or not self._indexer or not self._primary_store:
            return
        from codeweaver.providers.vector_stores.metadata import HybridVectorPayload

        try:
            # Get chunk from backup (need payload for re-embedding)
            if not (collections := await self._backup_store.list_collections()):
                logger.warning("No collections in backup store to find chunk %s", chunk_id)
                return
            for collection_name in collections:
                points = await self._backup_store._client.retrieve(
                    collection_name=collection_name,
                    ids=[chunk_id],
                    with_payload=True,
                    with_vectors=False,  # Don't copy incompatible vectors
                )

                if not points:
                    continue

                point = points[0]
                raw_payload = point.payload
                payload = HybridVectorPayload.model_validate(raw_payload)
                chunk = payload.chunk

                # Re-embed using primary's embedding providers
                dense_vector = None
                sparse_vector = None

                if (
                    hasattr(self._indexer, "_embedding_provider")
                    and self._indexer._embedding_provider
                ):  # type: ignore[attr-defined]
                    dense_embeddings = await self._indexer._embedding_provider.embed([chunk])  # type: ignore[attr-defined]
                    if dense_embeddings:
                        dense_vector = dense_embeddings[0]

                if hasattr(self._indexer, "_sparse_provider") and self._indexer._sparse_provider:  # type: ignore[attr-defined]
                    sparse_embeddings = await self._indexer._sparse_provider.embed([chunk])  # type: ignore[attr-defined]
                    if sparse_embeddings:
                        sparse_vector = sparse_embeddings[0]

                # Construct vectors dict
                vectors: dict[str, Any] = {}
                if dense_vector is not None:
                    vectors["dense"] = dense_vector
                if sparse_vector is not None:
                    vectors["sparse"] = sparse_vector

                if not vectors:
                    logger.warning("Failed to generate embeddings for chunk %s", chunk_id)
                    return

                # Upsert to primary with new embeddings
                await self._primary_store.upsert([chunk], for_backup=False)

                logger.debug("✓ Synced chunk %s to primary with re-embedding", chunk_id)
                return

            logger.warning("Chunk %s not found in any backup collection", chunk_id)

        except Exception:
            logger.warning("Failed to sync chunk %s", chunk_id, exc_info=True)
            raise

    async def _verify_primary_health(self) -> None:
        """Verify primary is healthy before completing restoration.

        Performs health checks to ensure primary can handle traffic:
        1. List collections (basic connectivity)
        2. Simple query operation (read capability)
        3. Circuit breaker state (no failures)

        Raises:
            Exception: If primary fails health checks
        """

        def _raise_if_closedcircuit() -> NoReturn:
            raise RuntimeError(
                f"Primary vector store's circuit breaker was not closed: {self._primary_store.circuit_breaker_state}"
            )

        if not self._primary_store:
            raise ValueError("No primary store to verify")

        try:
            # Check 1: Can list collections
            collections = await self._primary_store.list_collections()
            if collections:
                logger.debug("Primary health check: listed %d collections", len(collections))
            else:
                logger.debug("Primary health check: no collections found")

            # Check 2: Circuit breaker is closed
            from codeweaver.providers.vector_stores.base import CircuitBreakerState

            if (
                self._primary_store.circuit_breaker_state != CircuitBreakerState.CLOSED
                or not self._primary_store
            ):
                _raise_if_closedcircuit()

            # Check 3: Can get collection info (if collections exist)
            if (
                collections
                and self._primary_store
                and issubclass(type(self._primary_store), QdrantBaseProvider)
            ):
                await cast(QdrantBaseProvider, self._primary_store).list_collections()
                logger.debug("Primary health check: retrieved collection info")

            logger.info("✓ Primary health verification passed")

        except Exception:
            logger.warning("Primary health verification failed", exc_info=True)
            raise

    async def _create_backup_store(self) -> MemoryVectorStoreProvider:
        """Create and initialize in-memory backup vector store.

        Uses the backup profile configuration to create a memory provider
        instance with local embeddings.

        Returns:
            Initialized MemoryVectorStoreProvider

        Raises:
            Exception: If backup store creation fails
        """
        from codeweaver.providers.vector_stores.inmemory import MemoryVectorStoreProvider

        # Get backup configuration
        backup_config = _backup_profile()

        # Extract memory provider settings
        vector_store_settings = backup_config.get("vector_store")
        if not vector_store_settings:
            raise ValueError("Backup profile missing vector_store configuration")

        # Create memory provider
        memory_provider = MemoryVectorStoreProvider(config=vector_store_settings.provider_settings)  # type: ignore[attr-defined]

        # Initialize the provider
        await memory_provider._initialize()

        logger.debug("Created in-memory backup vector store")
        return memory_provider

    async def _create_backup_indexer(self) -> Indexer:
        """Create a separate Indexer instance for backup indexing.

        Creates an Indexer with:
        - Fresh BlakeStore to avoid dedup conflicts with primary
        - ChunkGovernor configured for backup model constraints
        - Backup embedding/reranking providers (from backup profile)

        This indexer operates independently of the primary indexer,
        using smaller chunk sizes appropriate for the backup models.

        Returns:
            Initialized Indexer configured for backup operations

        Raises:
            Exception: If backup indexer creation fails
        """
        from codeweaver.common.registry import get_provider_registry
        from codeweaver.core.discovery import DiscoveredFile
        from codeweaver.core.stores import make_blake_store
        from codeweaver.engine.chunker.base import ChunkGovernor
        from codeweaver.engine.chunking_service import ChunkingService
        from codeweaver.engine.indexer.indexer import Indexer

        # Get backup configuration
        backup_config = _backup_profile()

        # Create ChunkGovernor with backup model constraints
        # This ensures chunks are sized for the backup models (e.g., 512 tokens)
        backup_governor = ChunkGovernor.from_backup_profile(backup_config)
        logger.info(
            "Backup indexer chunk limit: %d tokens (vs primary which may be much larger)",
            backup_governor.chunk_limit,
        )

        # Create chunking service with backup governor
        backup_chunking_service = ChunkingService(backup_governor)

        # Create fresh BlakeStore to avoid dedup conflicts with primary
        backup_store = make_blake_store(value_type=DiscoveredFile)

        # Create the backup indexer
        backup_indexer = Indexer(
            walker=None,  # Files will be provided directly
            store=backup_store,
            chunking_service=backup_chunking_service,
            auto_initialize_providers=False,  # We'll initialize manually
            project_path=self._project_path,
        )

        # Initialize backup providers from profile
        # Get provider registry and create instances for backup
        registry = get_provider_registry()

        # Initialize embedding provider from backup profile
        embedding_settings = backup_config.get("embedding")
        if (
            embedding_settings
            and isinstance(embedding_settings, tuple)
            and len(embedding_settings) > 0
        ):
            first_setting = embedding_settings[0]
            provider_enum = first_setting.provider
            model_name = getattr(first_setting.model_settings, "model", None)
            try:
                embedding_provider = registry.create_provider(
                    provider_enum, "embedding", model=model_name
                )
                backup_indexer._embedding_provider = embedding_provider
                logger.debug(
                    "Initialized backup embedding provider: %s (%s)", provider_enum, model_name
                )
            except Exception as e:
                logger.warning("Failed to create backup embedding provider: %s", e)

        # Initialize sparse embedding provider from backup profile
        sparse_settings = backup_config.get("sparse_embedding")
        if sparse_settings and isinstance(sparse_settings, tuple) and len(sparse_settings) > 0:
            first_setting = sparse_settings[0]
            provider_enum = first_setting.provider
            model_name = getattr(first_setting.model_settings, "model", None)
            try:
                sparse_provider = registry.create_provider(
                    provider_enum, "sparse_embedding", model=model_name
                )
                backup_indexer._sparse_provider = sparse_provider
                logger.debug(
                    "Initialized backup sparse embedding provider: %s (%s)",
                    provider_enum,
                    model_name,
                )
            except Exception as e:
                logger.warning("Failed to create backup sparse provider: %s", e)

        # Set the backup vector store
        backup_indexer._vector_store = self._backup_store
        backup_indexer._providers_initialized = True

        logger.info(
            "Created backup indexer with chunk limit %d tokens", backup_governor.chunk_limit
        )
        return backup_indexer

    async def sync_pending_to_backup(self) -> int:
        """Sync pending file changes to the backup store using the backup indexer.

        Uses the FileChangeTracker to identify files that have changed since
        the last backup sync, then re-indexes them with the backup indexer
        (which uses smaller chunk sizes appropriate for backup models).

        Returns:
            Number of files synced to backup.
        """
        if not self._change_tracker:
            logger.debug("No change tracker available for backup sync")
            return 0

        if not self._backup_indexer:
            logger.debug("No backup indexer available for backup sync")
            return 0

        if not self._change_tracker.has_pending_changes:
            logger.debug("No pending changes to sync to backup")
            return 0

        files_to_index, files_to_delete = self._change_tracker.get_files_needing_backup()
        total_operations = len(files_to_index) + len(files_to_delete)

        if total_operations == 0:
            return 0

        logger.info(
            "Syncing %d files to backup (%d to index, %d to delete)",
            total_operations,
            len(files_to_index),
            len(files_to_delete),
        )

        synced_count = 0

        # Index changed files with backup indexer
        for file_path in files_to_index:
            if not file_path.exists():
                logger.debug("Skipping non-existent file: %s", file_path)
                continue

            try:
                # Use the backup indexer to index the file
                await self._backup_indexer._index_file(file_path)
                synced_count += 1
                logger.debug("Synced file to backup: %s", file_path)
            except Exception as e:
                logger.warning("Failed to sync file to backup: %s - %s", file_path, e)

        # Handle deletions
        for file_path in files_to_delete:
            try:
                await self._backup_indexer._delete_file(file_path)
                synced_count += 1
                logger.debug("Deleted file from backup: %s", file_path)
            except Exception as e:
                logger.warning("Failed to delete file from backup: %s - %s", file_path, e)

        # Mark backup sync complete
        self._change_tracker.mark_backup_complete()

        # Save tracker state
        self._change_tracker.save()

        logger.info(
            "Backup sync complete: %d/%d operations successful", synced_count, total_operations
        )
        return synced_count

    def should_sync_backup(
        self, *, time_threshold_seconds: float = 300, volume_threshold: int = 50
    ) -> bool:
        """Check if backup sync should be triggered based on thresholds.

        Args:
            time_threshold_seconds: Minimum seconds since last sync (default 5 minutes)
            volume_threshold: Minimum pending changes to trigger sync (default 50)

        Returns:
            True if sync should be triggered.
        """
        if not self._change_tracker:
            return False

        if not self._change_tracker.has_pending_changes:
            return False

        # Check volume threshold
        if self._change_tracker.pending_count >= volume_threshold:
            logger.debug(
                "Backup sync triggered by volume: %d pending >= %d threshold",
                self._change_tracker.pending_count,
                volume_threshold,
            )
            return True

        # Check time threshold
        time_since_sync = self._change_tracker.time_since_last_sync()
        if time_since_sync is None or time_since_sync >= time_threshold_seconds:
            logger.debug(
                "Backup sync triggered by time: %.1fs since last sync >= %.1fs threshold",
                time_since_sync or 0,
                time_threshold_seconds,
            )
            return True

        return False

    async def sync_failover_to_primary(self) -> int:
        """Re-index files that were indexed during failover to the primary.

        Uses the primary indexer to re-index files that were only indexed
        to the backup during failover. This ensures the primary has all
        content with proper embeddings.

        Returns:
            Number of files successfully re-indexed to primary.
        """
        if not self._change_tracker:
            logger.debug("No change tracker available for primary recovery")
            return 0

        if not self._indexer:
            logger.debug("No primary indexer available for primary recovery")
            return 0

        if not self._change_tracker.has_failover_files:
            logger.debug("No failover files to sync to primary")
            return 0

        failover_files = self._change_tracker.get_failover_indexed_files()

        if not failover_files:
            return 0

        logger.info(
            "Re-indexing %d files to primary that were indexed during failover", len(failover_files)
        )

        synced_count = 0

        for file_path in failover_files:
            if not file_path.exists():
                logger.debug("Skipping non-existent failover file: %s", file_path)
                continue

            try:
                # Use the primary indexer to re-index the file
                await self._indexer._index_file(file_path)
                synced_count += 1
                logger.debug("Re-indexed failover file to primary: %s", file_path)
            except Exception as e:
                logger.warning("Failed to re-index failover file to primary: %s - %s", file_path, e)

        # Mark primary recovery complete
        self._change_tracker.mark_primary_recovery_complete()

        # Save tracker state
        self._change_tracker.save()

        logger.info(
            "Primary recovery complete: %d/%d files re-indexed", synced_count, len(failover_files)
        )
        return synced_count

    async def _sync_primary_to_backup(self) -> None:
        """Sync primary vector store to backup JSON file.

        Creates a versioned backup file containing all collections,
        points, vectors, and payloads from the primary store.

        The backup file uses the following structure:
        - version: Backup file format version
        - metadata: Sync time, collection count, point count
        - collections: Full collection data with points

        This allows quick restoration if primary fails.

        Raises:
            Exception: If sync fails (logged but doesn't stop periodic sync)
        """
        import json

        if not self._primary_store or not self._project_path:
            logger.warning("Cannot sync backup - missing primary store or project path")
            return

        backup_dir = self._project_path / ".codeweaver" / "backup"
        backup_file = backup_dir / "vector_store.json"
        backup_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Get all collections from primary
            collections_response = await self._primary_store.list_collections()
            collections_data = {}
            total_points = 0
            if not collections_response:
                logger.debug("No collections in primary store to back up")
                collections_response = []

            for collection_name in collections_response:
                # Get collection info
                collection_info = await cast(
                    QdrantBaseProvider, self._primary_store
                ).get_collection(collection_name)

                # Scroll all points from the collection
                points = []
                offset = None
                while True:
                    result = await self._primary_store._client.scroll(
                        collection_name=collection_name,
                        limit=100,
                        offset=offset,
                        with_payload=True,
                        with_vectors=True,
                    )
                    if not result[0]:  # No more points
                        break
                    points.extend(result[0])
                    offset = result[1]  # next offset
                    if offset is None:  # Reached end
                        break

                total_points += len(points)

                # Serialize collection data
                collections_data[collection_name] = {
                    "metadata": {
                        "provider": "backup",
                        "created_at": datetime.now(UTC).isoformat(),
                        "point_count": len(points),
                    },
                    "config": {
                        "vectors_config": collection_info.config.params.vectors,
                        "sparse_vectors_config": collection_info.config.params.sparse_vectors,
                    },
                    "points": [
                        {"id": str(point.id), "vector": point.vector, "payload": point.payload}  # type: ignore[attr-defined]
                        for point in points
                    ],
                }

            # Create backup file with versioning
            backup_data = {
                "version": "2.0",  # Phase 2 version with metadata
                "metadata": {
                    "created_at": datetime.now(UTC).isoformat(),
                    "last_modified": datetime.now(UTC).isoformat(),
                    "collection_count": len(collections_data),
                    "total_points": total_points,
                    "source": "primary_sync",
                },
                "collections": collections_data,
            }

            # Write to temporary file first (atomic write)
            temp_file = backup_file.with_suffix(".tmp")
            temp_file.write_text(json.dumps(backup_data, indent=2))

            # Atomic rename
            temp_file.replace(backup_file)

            logger.debug(
                "Synced backup: %d collections, %d points to %s",
                len(collections_data),
                total_points,
                backup_file,
            )

        except Exception:
            logger.warning("Failed to sync primary to backup", exc_info=True)
            raise

    async def _validate_backup_file(self, backup_file: Path) -> bool:
        """Validate backup file structure and version.

        Checks:
        - File exists and is readable
        - JSON is valid
        - Required fields are present
        - Version is compatible

        Args:
            backup_file: Path to backup file

        Returns:
            True if valid, False otherwise
        """
        import json

        try:
            if not backup_file.exists():
                logger.debug("Backup file does not exist: %s", backup_file)
                return False

            # Read and parse JSON
            backup_data = json.loads(backup_file.read_text())

            # Check required fields
            required_fields = ["version", "metadata", "collections"]
            for field in required_fields:
                if field not in backup_data:
                    logger.warning("Backup file missing required field: %s", field)
                    return False

            # Check version compatibility
            version = backup_data.get("version", "1.0")
            if version not in ["1.0", "2.0"]:
                logger.warning("Unsupported backup file version: %s", version)
                return False

            # Validate metadata structure
            metadata = backup_data.get("metadata", {})
            if not isinstance(metadata, dict):
                logger.warning("Invalid metadata structure in backup file")
                return False

            # Validate collections structure
            collections = backup_data.get("collections", {})
            if not isinstance(collections, dict):
                logger.warning("Invalid collections structure in backup file")
                return False

            # Check each collection has required fields
            for col_name, col_data in collections.items():
                if "points" not in col_data:
                    logger.warning("Collection %s missing points field", col_name)
                    return False

        except json.JSONDecodeError as e:
            logger.warning("Backup file contains invalid JSON: %s", e)
            return False
        except Exception as e:
            logger.warning("Error validating backup file: %s", e)
            return False
        else:
            logger.debug("Backup file %s validated successfully", backup_file)
            return True

    def _log_resource_constraint_message(self, memory_estimate: Any) -> None:
        """Log detailed resource constraint message for user.

        Args:
            memory_estimate: MemoryEstimate with resource details
        """
        logger.error(
            "Continuing without vector store (embeddings only). "
            "To enable backup mode, try one of the following:\n"
            "  - Free up memory (need %.2fGB, "
            "have %.2fGB)\n"
            "  - Use a remote vector store (Qdrant Cloud, Pinecone, etc.)\n"
            "  - Index a subset of your codebase\n"
            "  - Increase max_memory_mb setting (current: %dMB)",
            memory_estimate.required_gb,
            memory_estimate.available_gb,
            self.max_memory_mb,
        )

    def get_status(self) -> dict[str, Any]:
        """Get current failover status for reporting.

        Returns:
            Dictionary with failover status information
        """
        status: dict[str, Any] = {
            "backup_enabled": self.backup_enabled,
            "failover_active": self._failover_active,
            "active_store_type": type(self._active_store).__name__ if self._active_store else None,
        }

        if self._failover_active and self._failover_time:
            status |= {
                "failover_since": self._failover_time.isoformat(),
                "failover_duration_seconds": self.failover_duration,
                "primary_state": (
                    self._primary_store.circuit_breaker_state if self._primary_store else "unknown"
                ),
            }

        if self._last_health_check:
            status["last_health_check"] = self._last_health_check.isoformat()

        if self._last_backup_sync:
            status["last_backup_sync"] = self._last_backup_sync.isoformat()

        # Add backup file status
        if self._project_path:
            backup_file = self._project_path / ".codeweaver" / "backup" / "vector_store.json"
            status["backup_file_exists"] = backup_file.exists()
            if backup_file.exists():
                status["backup_file_size_bytes"] = backup_file.stat().st_size

        # Add change tracker status
        if self._change_tracker:
            tracker_status = self._change_tracker.get_status()
            status["change_tracker"] = {
                "pending_changes": tracker_status["pending_changes"],
                "pending_deletions": tracker_status["pending_deletions"],
                "failover_indexed": tracker_status["failover_indexed"],
                "needs_backup_sync": tracker_status["needs_sync"],
                "needs_primary_recovery": tracker_status["needs_primary_recovery"],
            }
            if tracker_status["last_sync_time"]:
                status["change_tracker"]["last_sync_time"] = tracker_status["last_sync_time"]

        return status

    async def delete_and_clear(self) -> None:
        """Delete all data from both primary and backup vector stores."""
        from codeweaver.providers.vector_stores.qdrant_base import QdrantBaseProvider

        try:
            if self._primary_store:
                await cast(QdrantBaseProvider, self._primary_store).delete_collection(
                    self._primary_store.collection
                )
                logger.info("Deleted all data from primary vector store")
        except Exception:
            logger.warning("Failed to delete data from primary vector store", exc_info=True)

        try:
            if self._backup_store:
                await cast(QdrantBaseProvider, self._backup_store).delete_collection(
                    self._backup_store.collection
                )

            logger.info("Deleted all data from backup vector store")
        except Exception:
            logger.warning("Failed to delete data from backup vector store", exc_info=True)


__all__ = ["VectorStoreFailoverManager"]

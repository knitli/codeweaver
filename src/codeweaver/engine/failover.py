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
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field, PrivateAttr

from codeweaver.core.types.models import BasedModel
from codeweaver.engine.resource_estimation import estimate_backup_memory_requirements
from codeweaver.providers.vector_stores.base import CircuitBreakerState


if TYPE_CHECKING:
    from codeweaver.engine.indexer.indexer import Indexer
    from codeweaver.providers.vector_stores.base import VectorStoreProvider
    from codeweaver.providers.vector_stores.inmemory import MemoryVectorStoreProvider

logger = logging.getLogger(__name__)


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

    def _telemetry_keys(self) -> dict[str, str] | None:
        """Telemetry keys for privacy-preserving data collection.

        Returns:
            None - no sensitive data to filter in this model
        """
        return None

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
    _failover_chunks: Annotated[set[str], PrivateAttr()] = set()  # Chunk IDs indexed during failover

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
        self._primary_store = primary_store
        self._active_store = primary_store
        self._project_path = project_path
        self._indexer = indexer

        if self.backup_enabled and primary_store:
            logger.info("Initializing vector store failover support")
            # Start monitoring primary health
            self._circuit_monitor_task = asyncio.create_task(
                self._monitor_primary_health(), name="vector_store_circuit_monitor"
            )
            # Start periodic backup sync task
            self._backup_sync_task = asyncio.create_task(
                self._sync_backup_periodically(), name="vector_store_backup_sync"
            )
        else:
            logger.debug("Backup failover disabled or no primary store")

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

        # Persist backup state if active
        if self._failover_active and self._backup_store:
            try:
                await self._backup_store._persist_to_disk()
                logger.info("Persisted backup state on shutdown")
            except Exception as e:
                logger.warning("Failed to persist backup on shutdown", exc_info=e)

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
        """Continuously monitor primary circuit breaker state.

        Runs as a background task checking every 5 seconds for:
        - Primary failure → trigger failover
        - Primary recovery → consider restoration
        """
        check_interval = 5  # seconds

        while True:
            try:
                await asyncio.sleep(check_interval)
                self._last_health_check = datetime.now(UTC)

                if not self._primary_store:
                    continue

                # Check circuit breaker state
                circuit_state = self._primary_store.circuit_breaker_state

                if circuit_state == CircuitBreakerState.OPEN and not self._failover_active:
                    # Primary failed - trigger failover
                    logger.warning("Primary vector store circuit breaker opened")
                    await self._activate_failover()

                elif (
                    circuit_state == CircuitBreakerState.CLOSED
                    and self._failover_active
                    and self.auto_restore
                ):
                    # Primary recovered - consider restoring
                    logger.info("Primary vector store circuit breaker closed")
                    await self._consider_restoration()

            except asyncio.CancelledError:
                logger.debug("Circuit monitor task cancelled")
                break
            except Exception:
                logger.exception("Error in circuit monitor task")
                # Continue monitoring despite errors

    async def _sync_backup_periodically(self) -> None:
        """Periodically sync primary store to backup for fast recovery.

        This task runs in the background, syncing the primary vector store
        to a backup JSON file at regular intervals (default: 5 minutes).

        The backup file is used for quick recovery when the primary fails,
        allowing restoration in <60 seconds vs. re-indexing which could
        take minutes.

        Syncs only when:
        - Primary store is healthy (circuit breaker CLOSED)
        - Not currently in failover mode
        - Backup is enabled

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

                # Perform backup sync
                logger.debug("Starting periodic backup sync")
                await self._sync_primary_to_backup()
                self._last_backup_sync = datetime.now(UTC)
                logger.info("✓ Backup sync completed successfully")

            except asyncio.CancelledError:
                logger.debug("Backup sync task cancelled")
                break
            except Exception:
                logger.exception("Error in backup sync task - will retry next interval")
                # Continue syncing despite errors

    async def _activate_failover(self) -> None:
        """Activate backup vector store with resource safety checks.

        Performs the following steps:
        1. Check if already in failover
        2. Estimate memory requirements
        3. Verify resource availability
        4. Initialize backup store if needed
        5. Attempt to restore from persisted state
        6. Switch active store to backup
        7. Notify user

        If resources are insufficient, logs error and continues without backup.
        """
        if self._failover_active:
            logger.debug("Failover already active, skipping activation")
            return

        logger.warning("⚠️  PRIMARY VECTOR STORE UNAVAILABLE - Activating backup mode")

        # Step 1: Resource check
        stats = self._indexer.stats if self._indexer else None
        memory_estimate = estimate_backup_memory_requirements(
            project_path=self._project_path, stats=stats
        )

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
            logger.exception(
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
            logger.exception("Failed to initialize backup store")
            return

        # Step 3: Attempt to restore from persistence
        if self._backup_store and self._project_path:
            backup_file = self._project_path / ".codeweaver" / "backup" / "vector_store.json"
            if backup_file.exists():
                # Validate backup file before restoring
                is_valid = await self._validate_backup_file(backup_file)
                if not is_valid:
                    logger.warning(
                        "Backup file validation failed - will start with empty backup. "
                        "File: %s",
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
        await self._snapshot_backup_state()

        # Step 5: Activate backup
        self._active_store = self._backup_store
        self._failover_active = True
        self._failover_time = datetime.now(UTC)

        logger.warning(
            "⚠️  BACKUP MODE ACTIVE - Search functionality will continue "
            "with in-memory backup. Run 'codeweaver status' for details."
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
            # Step 1: Sync changes from backup to primary
            await self._sync_back_to_primary()

            # Step 2: Verify primary is working after sync
            await self._verify_primary_health()

            # Step 3: Switch back to primary
            self._active_store = self._primary_store
            self._failover_active = False
            self._failover_time = None
            self._failover_chunks.clear()

            logger.info(
                "✓ PRIMARY VECTOR STORE RESTORED - Backup mode deactivated. "
                "Normal operation resumed with all changes synced."
            )

        except Exception as e:
            logger.error(
                "Failed to restore to primary: %s. Staying in backup mode for safety.",
                e,
                exc_info=True,
            )
            # Stay in backup mode if sync-back fails

    async def _snapshot_backup_state(self) -> None:
        """Snapshot current backup state before failover.

        Records all existing point IDs in the backup so we can later
        identify which chunks were added during the failover period.
        """
        if not self._backup_store:
            logger.debug("No backup store to snapshot")
            return

        try:
            # Get all collections
            collections = await self._backup_store.list_collections()

            # Track existing point IDs
            for collection_name in collections:
                # Scroll all points
                offset = None
                while True:
                    result = await self._backup_store._client.scroll(  # type: ignore[union-attr]
                        collection_name=collection_name,
                        limit=100,
                        offset=offset,
                        with_payload=False,  # Only need IDs
                        with_vectors=False,
                    )
                    if not result[0]:
                        break

                    # Record IDs
                    for point in result[0]:
                        self._failover_chunks.add(str(point.id))  # type: ignore[attr-defined]

                    offset = result[1]
                    if offset is None:
                        break

            logger.debug("Snapshotted %d existing chunks before failover", len(self._failover_chunks))

        except Exception as e:
            logger.warning("Failed to snapshot backup state: %s", e)
            # Continue anyway - worst case we re-embed some existing chunks

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
        """
        if not self._primary_store or not self._backup_store or not self._indexer:
            logger.warning("Cannot sync back - missing primary, backup, or indexer")
            return

        try:
            # Get all current point IDs from backup
            current_chunks: set[str] = set()
            collections = await self._backup_store.list_collections()

            for collection_name in collections:
                offset = None
                while True:
                    result = await self._backup_store._client.scroll(  # type: ignore[union-attr]
                        collection_name=collection_name,
                        limit=100,
                        offset=offset,
                        with_payload=False,
                        with_vectors=False,
                    )
                    if not result[0]:
                        break

                    for point in result[0]:
                        current_chunks.add(str(point.id))  # type: ignore[attr-defined]

                    offset = result[1]
                    if offset is None:
                        break

            # Find chunks added during failover (diff against snapshot)
            new_chunks = current_chunks - self._failover_chunks
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
                    "⚠️  %d chunks failed to sync - may need manual recovery",
                    failed_count,
                )

        except Exception as e:
            logger.exception("Sync-back failed: %s", e)
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

        try:
            # Get chunk from backup (need payload for re-embedding)
            collections = await self._backup_store.list_collections()

            for collection_name in collections:
                points = await self._backup_store._client.retrieve(  # type: ignore[union-attr]
                    collection_name=collection_name,
                    ids=[chunk_id],
                    with_payload=True,
                    with_vectors=False,  # Don't copy incompatible vectors
                )

                if not points:
                    continue

                point = points[0]
                payload = point.payload  # type: ignore[attr-defined]

                # Extract text content from payload
                chunk_text = payload.get("chunk_text", "") or payload.get("text", "")
                if not chunk_text:
                    logger.warning("Chunk %s has no text content to re-embed", chunk_id)
                    return

                # Re-embed using primary's embedding providers
                dense_vector = None
                sparse_vector = None

                if hasattr(self._indexer, "_embedding_provider") and self._indexer._embedding_provider:  # type: ignore[attr-defined]
                    dense_embeddings = await self._indexer._embedding_provider.embed([chunk_text])  # type: ignore[attr-defined]
                    if dense_embeddings:
                        dense_vector = dense_embeddings[0]

                if hasattr(self._indexer, "_sparse_provider") and self._indexer._sparse_provider:  # type: ignore[attr-defined]
                    sparse_embeddings = await self._indexer._sparse_provider.embed([chunk_text])  # type: ignore[attr-defined]
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
                await self._primary_store.upsert(
                    collection_name=collection_name,
                    points=[{
                        "id": chunk_id,
                        "vector": vectors,
                        "payload": payload,
                    }],
                )

                logger.debug("✓ Synced chunk %s to primary with re-embedding", chunk_id)
                return

            logger.warning("Chunk %s not found in any backup collection", chunk_id)

        except Exception as e:
            logger.exception("Failed to sync chunk %s: %s", chunk_id, e)
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
        if not self._primary_store:
            raise ValueError("No primary store to verify")

        try:
            # Check 1: Can list collections
            collections = await self._primary_store.list_collections()
            logger.debug("Primary health check: listed %d collections", len(collections))

            # Check 2: Circuit breaker is closed
            from codeweaver.providers.vector_stores.base import CircuitBreakerState

            if self._primary_store.circuit_breaker_state != CircuitBreakerState.CLOSED:
                raise RuntimeError(
                    f"Primary circuit breaker not closed: {self._primary_store.circuit_breaker_state}"
                )

            # Check 3: Can get collection info (if collections exist)
            if collections:
                collection_info = await self._primary_store.get_collection(collections[0])
                logger.debug("Primary health check: retrieved collection info")

            logger.info("✓ Primary health verification passed")

        except Exception as e:
            logger.error("Primary health verification failed: %s", e)
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
        from codeweaver.config.profiles import _backup_profile
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

            for collection_name in collections_response:
                # Get collection info
                collection_info = await self._primary_store.get_collection(collection_name)

                # Scroll all points from the collection
                points = []
                offset = None
                while True:
                    result = await self._primary_store._client.scroll(  # type: ignore[union-attr]
                        collection_name=collection_name,
                        limit=100,
                        offset=offset,
                        with_payload=True,
                        with_vectors=True,  # type: ignore[arg-type]
                    )
                    if not result[0]:  # No more points
                        break
                    points.extend(result[0])  # type: ignore[arg-type]
                    offset = result[1]  # Next offset
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
                        "vectors_config": collection_info.get("vectors_config", {}),
                        "sparse_vectors_config": collection_info.get("sparse_vectors_config", {}),
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

        except Exception as e:
            logger.exception("Failed to sync primary to backup: %s", e)
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

            logger.debug("Backup file validation passed: %s", backup_file)
            return True

        except json.JSONDecodeError as e:
            logger.warning("Backup file contains invalid JSON: %s", e)
            return False
        except Exception as e:
            logger.warning("Error validating backup file: %s", e)
            return False

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

        return status


__all__ = ["VectorStoreFailoverManager"]

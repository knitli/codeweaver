# Engine Package DI Refactoring Design

**Date**: 2026-01-16
**Status**: Design Phase
**Context**: 75% through codebase-wide DI rearchitecting; `core` and `providers` complete

## Executive Summary

This document outlines the refactoring strategy for the `engine` package to align with the new dependency injection architecture established in `core` and `providers`. The refactoring will dramatically simplify state management, eliminate configuration branching logic, and establish a clean separation between primary and backup components while maintaining architectural flexibility for future engine swaps (e.g., CocoIndex).

**Key Decision**: We will **NOT** migrate to CocoIndex at this time, but will refactor the current engine to be more modular and maintainable, following proven DI patterns.

## Background Context

### Completed Work (`core` and `providers`)

1. **Configuration System Refactored**:
   - Types directly map to constructors: `SomeConstructor(**type.as_settings())`
   - Clean separation of configuration from construction

2. **DI Factory Pattern**:
   - All construction moved to `providers/dependencies.py`
   - Providers receive complete configuration + instantiated clients
   - No multi-config logic in providers themselves

3. **Backup Strategy**:
   - Separate classes for backup components (`BackupEmbeddingProvider`, etc.)
   - Created via `backup_factory.py` (moving to `core/backup_factory.py`) with `is_provider_backup` property
   - Mirrored dependency markers (`BackupVectorStoreProviderDep`)
   - Each backup component owns its own configuration and state

4. **State Management**:
   - Eliminated ClassVar deduplication mechanisms
   - Per-instance stores with locks for thread safety
   - Each provider owns single config

### Problems in Current Engine

1. **Complex Failover Logic**:
   - `failover.py` (150+ lines): Handles both failover orchestration AND construction
   - `failover_tracker.py`: Complex state tracking
   - `resource_estimation.py`: Over-engineered for current needs

2. **State Management Issues**:
   - Similar ClassVar issues to what providers had
   - Shared mutable state across components
   - Difficult-to-test code

3. **Construction Responsibilities**:
   - Indexer, ChunkingService, Checkpoint, Manifest all have complex init logic
   - Configuration validation mixed with business logic
   - Hard to create test doubles

4. **Tight Coupling**:
   - Components directly instantiate dependencies
   - Difficult to swap implementations
   - Hard to test in isolation

## Design Principles

### 1. Follow Provider Pattern

**Apply lessons from provider refactoring**:

- ✅ Construction external to business logic (in `engine/dependencies.py`)
- ✅ Single responsibility: each service owns ONE configuration
- ✅ Dependency injection via markers (from `core` and `providers`)
- ✅ Backup components as separate instances
- ✅ Per-instance stores (no mutable ClassVars)

### 2. Separation of Concerns

**Clear boundaries**:

```
engine/
├── dependencies.py          # ⭐ Construction and wiring (NEW)
├── config/                  # Configuration types only
├── services/                # Business logic services (REFACTORED)
│   ├── indexing_service.py  # Orchestrates indexing workflow
│   ├── chunking_service.py  # Refactored with smart chunk reuse
│   └── failover_service.py  # Simplified failover orchestration
├── managers/                # State management (REFACTORED)
│   ├── checkpoint_manager.py   # Checkpoint persistence
│   ├── manifest_manager.py     # File manifest tracking
│   └── progress_tracker.py     # Progress reporting
├── chunker/                 # Existing, mostly unchanged
├── watcher/                 # Existing, minimal changes
└── search/                  # Existing, minimal changes
```

### 3. Dependency Flow

```
User/CLI
   ↓
engine/dependencies.py
   ↓ constructs
Services (Indexer, ChunkingService, FailoverService)
   ↓ injects
Managers (Checkpoint, Manifest, Progress)
   ↓ uses
core/providers dependencies (INJECTED markers)
```

**Key insight**: Services coordinate workflows; managers handle state; dependencies.py handles all construction.

### 4. Configuration Strategy

**Per-component configuration** (not global mega-config):

```python
# engine/config/__init__.py

class IndexingServiceSettings(BasedModel):
    """Settings for the indexing service."""
    checkpoint_interval: int = 100  # files
    checkpoint_time_interval: int = 300  # seconds
    enable_failover: bool = True
    batch_size: int = 50

class ChunkingServiceSettings(BasedModel):
    """Settings for chunking service."""
    enable_parallel: bool = True
    parallel_threshold: int = 3
    # ... existing settings

class FailoverServiceSettings(BasedModel):
    """Settings for failover orchestration."""
    backup_sync_interval: int = 300
    auto_restore: bool = True
    restore_delay: int = 60
    max_memory_mb: int = 2048

# Aggregated for convenience
class EngineSettings(BasedModel):
    indexing: IndexingServiceSettings = Field(default_factory=IndexingServiceSettings)
    chunking: ChunkingServiceSettings = Field(default_factory=ChunkingServiceSettings)
    failover: FailoverServiceSettings = Field(default_factory=FailoverServiceSettings)
```

## Detailed Component Design

### 1. Dependency Injection Setup (`engine/dependencies.py`)

**Purpose**: Central construction and wiring for all engine components.

```python
# engine/dependencies.py

"""Dependency injection setup for engine components.

This module provides DI factories for engine services and managers.
All construction logic lives here, keeping business logic clean.

Architecture:
- Services receive dependencies from other codeweaver packages via INJECTED markers
- Inter-dependencies from within the engine package handled in dependencies.py
- Managers are constructed here and injected into services
- Configuration flows: Settings → Config → Dependencies → Services
"""

from typing import Annotated
from codeweaver.core import (
    INJECTED,
    ChunkingServiceDep,
    EmbeddingDep,
    SparseEmbeddingDep,
    VectorStoreDep,
    BackupVectorStoreDep,
    BackupEmbeddingDep,
    BackupSparseEmbeddingDep,
    GovernorDep,
    BackupGovernorDep,
    TokenizerDep,
    SettingsDep,
    dependency_provider,
    depends,
    create_backup_class,
)

# ===========================================================================
# Configuration Providers
# ===========================================================================

@dependency_provider(IndexingServiceSettings, scope="singleton")
def _get_indexing_service_settings(
    settings: SettingsDep = INJECTED
) -> IndexingServiceSettings:
    """Factory for indexing service settings."""
    return settings.engine.indexing

@dependency_provider(ChunkingServiceSettings, scope="singleton")
def _get_chunking_service_settings(
    settings: SettingsDep = INJECTED
) -> ChunkingServiceSettings:
    """Factory for chunking service settings."""
    return settings.engine.chunking

@dependency_provider(FailoverServiceSettings, scope="singleton")
def _get_failover_service_settings(
    settings: SettingsDep = INJECTED
) -> FailoverServiceSettings:
    """Factory for failover service settings."""
    return settings.engine.failover

# ===========================================================================
# Manager Factories
# ===========================================================================

@dependency_provider(CheckpointManager, scope="singleton")
def _create_checkpoint_manager(
    settings: SettingsDep = INJECTED
) -> CheckpointManager:
    """Factory for checkpoint manager."""
    return CheckpointManager(
        project_path=settings.project_path,
        checkpoint_dir=settings.user_config_dir / "checkpoints"
    )

@dependency_provider(FileManifestManager, scope="singleton")
def _create_manifest_manager(
    settings: SettingsDep = INJECTED
) -> FileManifestManager:
    """Factory for file manifest manager."""
    return FileManifestManager(
        project_path=settings.project_path,
        manifest_dir=settings.user_config_dir / "manifests"
    )

@dependency_provider(IndexingProgressTracker, scope="function")
def _create_progress_tracker() -> IndexingProgressTracker:
    """Factory for progress tracker (function-scoped for per-operation tracking)."""
    return IndexingProgressTracker()

# ===========================================================================
# Service Factories
# ===========================================================================

@dependency_provider(ChunkingService, scope="singleton")
def _create_chunking_service(
    governor: GovernorDep = INJECTED,
    tokenizer: TokenizerDep = INJECTED,
    settings: Annotated[ChunkingServiceSettings, depends(_get_chunking_service_settings)] = INJECTED,
) -> ChunkingService:
    """Factory for primary chunking service."""
    return ChunkingService(
        governor=governor,
        tokenizer=tokenizer,
        settings=settings,
    )

@dependency_provider(BackupChunkingService, scope="singleton")
def _create_backup_chunking_service(
    backup_governor: BackupGovernorDep = INJECTED,
    tokenizer: TokenizerDep = INJECTED,
    settings: Annotated[ChunkingServiceSettings, depends(_get_chunking_service_settings)] = INJECTED,
) -> BackupChunkingService:
    """Factory for backup chunking service with smart chunk reuse."""
    BackupChunkingService = create_backup_class(ChunkingService)
    return BackupChunkingService(
        governor=backup_governor,
        tokenizer=tokenizer,
        settings=settings,
    )

@dependency_provider(IndexingService, scope="singleton")
def _create_indexing_service(
    chunking_service: ChunkingServiceDep = INJECTED,
    embedding_provider: EmbeddingDep = INJECTED,
    sparse_embedding_provider: SparseEmbeddingDep = INJECTED,
    vector_store: VectorStoreDep = INJECTED,
    checkpoint_manager: Annotated[CheckpointManager, depends(_create_checkpoint_manager)] = INJECTED,
    manifest_manager: Annotated[FileManifestManager, depends(_create_manifest_manager)] = INJECTED,
    settings: Annotated[IndexingServiceSettings, depends(_get_indexing_service_settings)] = INJECTED,
) -> IndexingService:
    """Factory for indexing service."""
    return IndexingService(
        chunking_service=chunking_service,
        embedding_provider=embedding_provider,
        sparse_embedding_provider=sparse_embedding_provider,
        vector_store=vector_store,
        checkpoint_manager=checkpoint_manager,
        manifest_manager=manifest_manager,
        settings=settings,
    )

@dependency_provider(FailoverService, scope="singleton")
def _create_failover_service(
    primary_vector_store: VectorStoreDep = INJECTED,
    backup_vector_store: BackupVectorStoreDep = INJECTED,
    indexing_service: Annotated[IndexingService, depends(_create_indexing_service)] = INJECTED,
    settings: Annotated[FailoverServiceSettings, depends(_get_failover_service_settings)] = INJECTED,
) -> FailoverService:
    """Factory for failover service."""
    return FailoverService(
        primary_store=primary_vector_store,
        backup_store=backup_vector_store,
        indexing_service=indexing_service,
        settings=settings,
    )

# ===========================================================================
# Backup Service Factories
# ===========================================================================

@dependency_provider(BackupIndexingService, scope="singleton")
def _create_backup_indexing_service(
    backup_chunking_service: Annotated[BackupChunkingService, depends(_create_backup_chunking_service)] = INJECTED,
    backup_embedding_provider: BackupEmbeddingDep = INJECTED,
    backup_sparse_embedding_provider: BackupSparseEmbeddingDep = INJECTED,
    backup_vector_store: BackupVectorStoreDep = INJECTED,
    checkpoint_manager: Annotated[CheckpointManager, depends(_create_checkpoint_manager)] = INJECTED,
    manifest_manager: Annotated[FileManifestManager, depends(_create_manifest_manager)] = INJECTED,
    settings: Annotated[IndexingServiceSettings, depends(_get_indexing_service_settings)] = INJECTED,
) -> BackupIndexingService:
    """Factory for backup indexing service."""
    # Create backup variant
    BackupIndexingService = create_backup_class(IndexingService)
    return BackupIndexingService(
        chunking_service=backup_chunking_service,
        embedding_provider=backup_embedding_provider,
        sparse_embedding_provider=backup_sparse_embedding_provider,
        vector_store=backup_vector_store,
        checkpoint_manager=checkpoint_manager,
        manifest_manager=manifest_manager,
        settings=settings,
    )

# ===========================================================================
# Dependency Markers (exported for use in rest of codebase)
# ===========================================================================

type ChunkingServiceDep = Annotated[ChunkingService, depends(_create_chunking_service)]
type BackupChunkingServiceDep = Annotated[BackupChunkingService, depends(_create_backup_chunking_service)]
type IndexingServiceDep = Annotated[IndexingService, depends(_create_indexing_service)]
type BackupIndexingServiceDep = Annotated[BackupIndexingService, depends(_create_backup_indexing_service)]
type FailoverServiceDep = Annotated[FailoverService, depends(_create_failover_service)]
type CheckpointManagerDep = Annotated[CheckpointManager, depends(_create_checkpoint_manager)]
type ManifestManagerDep = Annotated[FileManifestManager, depends(_create_manifest_manager)]
type ProgressTrackerDep = Annotated[IndexingProgressTracker, depends(_create_progress_tracker)]

__all__ = [
    "ChunkingServiceDep",
    "BackupChunkingServiceDep",
    "IndexingServiceDep",
    "BackupIndexingServiceDep",
    "FailoverServiceDep",
    "CheckpointManagerDep",
    "ManifestManagerDep",
    "ProgressTrackerDep",
]
```

### 2. ChunkingService (Enhanced with Smart Reuse)

**Purpose**: Chunk files with intelligent reuse for backup scenarios.

```python
# engine/services/chunking_service.py

"""Chunking service with smart chunk reuse for backup operations."""

from pathlib import Path
from typing import TYPE_CHECKING

from codeweaver.core import INJECTED, GovernorDep, TokenizerDep

if TYPE_CHECKING:
    from collections.abc import Iterator
    from codeweaver.core import DiscoveredFile, CodeChunk
    from codeweaver.engine.config import ChunkingServiceSettings

class ChunkingService:
    """Chunks files with optional smart reuse for backup scenarios.

    Responsibilities:
    - Chunk files based on language and model constraints
    - Provide both parallel and sequential chunking
    - Support smart reuse of existing chunks when compatible

    Does NOT:
    - Generate embeddings (that's providers)
    - Store chunks (that's vector stores)
    - Manage backup state (that's FailoverService)
    """

    def __init__(
        self,
        governor: GovernorDep,
        tokenizer: TokenizerDep,
        settings: ChunkingServiceSettings,
    ):
        """Initialize chunking service with injected dependencies."""
        self.governor = governor
        self.tokenizer = tokenizer
        self.settings = settings
        self._selector = ChunkerSelector(governor, tokenizer)

    def chunk_files(
        self,
        files: list[DiscoveredFile],
        *,
        source_chunks: dict[Path, list[CodeChunk]] | None = None,
    ) -> Iterator[tuple[Path, list[CodeChunk]]]:
        """Chunk files with optional reuse of source chunks.

        Args:
            files: Files to chunk
            source_chunks: Optional pre-existing chunks (e.g., from primary)

        Yields:
            (file_path, chunks) tuples

        Notes:
            When source_chunks provided, checks compatibility before reusing.
            Backup service uses this to avoid re-chunking when primary chunks fit.
        """
        # If backup and source chunks provided, attempt smart reuse
        if source_chunks and self._is_backup_service():
            yield from self._chunk_with_reuse(files, source_chunks)
        else:
            # Normal chunking (primary or no source chunks)
            yield from self._chunk_normal(files)

    def _chunk_with_reuse(
        self,
        files: list[DiscoveredFile],
        source_chunks: dict[Path, list[CodeChunk]],
    ) -> Iterator[tuple[Path, list[CodeChunk]]]:
        """Chunk files, reusing source chunks when compatible.

        Checks if source chunks fit within backup model constraints.
        Only re-chunks when necessary.
        """
        for file in files:
            if self._can_reuse_chunks(source_chunks.get(file.path)):
                # Reuse primary chunks (they fit in backup model)
                logger.debug("Reusing chunks for %s (compatible with backup model)", file.path)
                yield (file.path, source_chunks[file.path])
            else:
                # Re-chunk with backup constraints
                logger.debug("Re-chunking %s (primary chunks incompatible)", file.path)
                yield from self._chunk_normal([file])

    def _can_reuse_chunks(self, chunks: list[CodeChunk] | None) -> bool:
        """Check if chunks are compatible with current model.

        Returns True if:
        - Chunks exist
        - All chunk sizes <= model context window
        - Chunking strategy compatible

        This enables backup to reuse primary chunks when models have
        similar context windows.
        """
        if not chunks:
            return False

        max_tokens = self.governor.max_chunk_tokens

        # Check if all chunks fit
        for chunk in chunks:
            chunk_tokens = self.tokenizer.count_tokens(chunk.text)
            if chunk_tokens > max_tokens:
                return False

        return True

    def _is_backup_service(self) -> bool:
        """Check if this is a backup service instance."""
        return getattr(self, 'is_provider_backup', False)

    def _chunk_normal(
        self, files: list[DiscoveredFile]
    ) -> Iterator[tuple[Path, list[CodeChunk]]]:
        """Normal chunking without reuse."""
        # Existing implementation (parallel/sequential logic)
        if self.settings.enable_parallel and len(files) >= self.settings.parallel_threshold:
            yield from chunk_files_parallel(files, self.governor, tokenizer=self.tokenizer)
        else:
            yield from self._chunk_sequential(files)

    # ... rest of existing implementation ...
```

**Key Features**:
- **Smart Reuse**: Checks if primary chunks fit backup model constraints
- **Lazy Re-chunking**: Only re-chunks when necessary
- **Transparent**: Primary service behavior unchanged
- **Testable**: Easy to test reuse logic in isolation

**Performance Impact**:
- Best case (reuse): Skip chunking entirely (~100ms saved per file)
- Worst case (re-chunk): ~100ms overhead per file (~2% total time)
- Embedding generation still bottleneck (~1-5s per file)

### 3. IndexingService (Refactored)

**Purpose**: Orchestrate the indexing workflow WITHOUT managing construction.

```python
# engine/services/indexing_service.py

"""Indexing service for orchestrating file discovery, chunking, embedding, and storage."""

from pathlib import Path
from typing import TYPE_CHECKING

from codeweaver.core import INJECTED, ChunkingServiceDep, EmbeddingDep, VectorStoreDep

if TYPE_CHECKING:
    from codeweaver.engine.managers import CheckpointManager, FileManifestManager
    from codeweaver.engine.config import IndexingServiceSettings

class IndexingService:
    """Orchestrates the indexing workflow.

    Responsibilities:
    - Coordinate file discovery → chunking → embedding → storage
    - Manage checkpointing at intervals
    - Update file manifest
    - Report progress
    - Handle graceful interruption

    Does NOT:
    - Construct dependencies (that's dependencies.py)
    - Manage failover (that's FailoverService)
    - Implement chunking/embedding (delegates to providers)
    """

    def __init__(
        self,
        chunking_service: ChunkingServiceDep,
        embedding_provider: EmbeddingDep,
        sparse_embedding_provider: SparseEmbeddingDep | None,
        vector_store: VectorStoreDep,
        checkpoint_manager: CheckpointManager,
        manifest_manager: FileManifestManager,
        settings: IndexingServiceSettings,
    ):
        """Initialize indexing service with injected dependencies."""
        self.chunking_service = chunking_service
        self.embedding_provider = embedding_provider
        self.sparse_embedding_provider = sparse_embedding_provider
        self.vector_store = vector_store
        self.checkpoint_manager = checkpoint_manager
        self.manifest_manager = manifest_manager
        self.settings = settings

        # Per-instance state (not ClassVars)
        self._current_checkpoint: IndexingCheckpoint | None = None
        self._files_since_checkpoint = 0
        self._time_since_checkpoint = 0

    async def index_project(
        self,
        project_path: Path,
        *,
        progress_callback: ProgressCallback | None = None,
        resume: bool = True,
    ) -> IndexingStats:
        """Index a project with checkpoint support.

        Args:
            project_path: Root path to index
            progress_callback: Optional callback for progress updates
            resume: Whether to resume from checkpoint if available

        Returns:
            Statistics about the indexing operation
        """
        # 1. Load checkpoint if resuming
        if resume and (checkpoint := await self.checkpoint_manager.load()):
            self._current_checkpoint = checkpoint
            logger.info("Resuming from checkpoint: %d files processed", checkpoint.files_processed)

        # 2. Discover files
        discovered_files = await self._discover_files(project_path)
        if progress_callback:
            progress_callback("discovery", len(discovered_files), len(discovered_files))

        # 3. Filter unchanged files using manifest
        files_to_process = await self.manifest_manager.filter_unchanged(discovered_files)
        if progress_callback:
            progress_callback("filtering", len(files_to_process), len(discovered_files))

        # 4. Process files in batches
        stats = IndexingStats()
        for batch in self._batch_files(files_to_process):
            # Chunk files
            chunked = list(self.chunking_service.chunk_files(batch))
            stats.chunks_created += sum(len(chunks) for _, chunks in chunked)

            # Generate embeddings
            embeddings = await self._generate_embeddings(chunked)

            # Store in vector database
            await self._store_chunks(embeddings)
            stats.files_processed += len(batch)

            # Checkpoint if needed
            self._files_since_checkpoint += len(batch)
            if self._files_since_checkpoint >= self.settings.checkpoint_interval:
                await self._save_checkpoint(stats)
                self._files_since_checkpoint = 0

            # Update progress
            if progress_callback:
                progress_callback("indexing", stats.files_processed, len(files_to_process))

        # 5. Update manifest
        await self.manifest_manager.update_from_stats(stats)

        # 6. Clean up checkpoint
        if self._current_checkpoint:
            await self.checkpoint_manager.clear()

        return stats

    # ... private helper methods ...
```

**Key Changes**:
- Dependencies injected via constructor
- No construction logic
- Clear, focused responsibilities
- Per-instance state (no ClassVars)
- Testable interface

### 4. FailoverService (Simplified with Backup Chunking)



**Purpose**: Coordinate failover between primary and backup stores WITHOUT construction complexity.

```python
# engine/services/failover_service.py

"""Failover service for coordinating primary/backup vector store transitions."""

from typing import TYPE_CHECKING

from codeweaver.core import INJECTED, VectorStoreDep, BackupVectorStoreDep

if TYPE_CHECKING:
    from codeweaver.engine.services import IndexingService
    from codeweaver.engine.config import FailoverServiceSettings

class FailoverService:
    """Coordinates failover between primary and backup vector stores.

    Responsibilities:
    - Monitor primary store health
    - Activate backup when primary fails
    - Sync backup periodically
    - Restore to primary when recovered

    Does NOT:
    - Construct stores (that's dependencies.py)
    - Estimate resources (simple checks only)
    - Implement indexing (delegates to IndexingService)
    """

    def __init__(
        self,
        primary_store: VectorStoreDep,
        backup_store: BackupVectorStoreDep,
        indexing_service: IndexingService,
        settings: FailoverServiceSettings,
    ):
        """Initialize failover service with injected dependencies."""
        self.primary_store = primary_store
        self.backup_store = backup_store
        self.indexing_service = indexing_service
        self.settings = settings

        # State
        self._active_store: VectorStoreProvider = primary_store
        self._failover_active = False
        self._monitor_task: asyncio.Task | None = None

    async def start_monitoring(self) -> None:
        """Start health monitoring and automatic failover."""
        if not self.settings.enable_failover:
            return

        self._monitor_task = asyncio.create_task(self._monitor_health())

    async def _monitor_health(self) -> None:
        """Monitor primary store health and trigger failover if needed."""
        while True:
            await asyncio.sleep(self.settings.health_check_interval)

            # Check primary health via circuit breaker
            if self.primary_store.circuit_breaker.state == CircuitBreakerState.OPEN:
                if not self._failover_active:
                    await self._activate_failover()
            elif self._failover_active and self.settings.auto_restore:
                # Primary recovered, restore after delay
                await asyncio.sleep(self.settings.restore_delay)
                await self._restore_primary()

    async def _activate_failover(self) -> None:
        """Activate backup store."""
        logger.warning("Primary vector store unhealthy, activating backup")

        # Simple safety check (not over-engineered)
        if not await self._is_backup_safe():
            logger.error("Cannot activate backup: insufficient resources")
            return

        # Sync current state to backup
        await self._sync_to_backup()

        # Switch active store
        self._active_store = self.backup_store
        self._failover_active = True

        logger.info("Failover to backup complete")

    async def _restore_primary(self) -> None:
        """Restore primary store after recovery."""
        logger.info("Primary vector store recovered, restoring")

        # Sync backup changes back to primary
        await self._sync_from_backup()

        # Switch back
        self._active_store = self.primary_store
        self._failover_active = False

        logger.info("Restored to primary store")

    async def _is_backup_safe(self) -> bool:
        """Simple safety check for backup activation."""
        # Just check available memory vs configured max
        import psutil
        available_mb = psutil.virtual_memory().available / 1024 / 1024
        return available_mb > self.settings.max_memory_mb

    async def _sync_to_backup(self) -> None:
        """Sync primary state to backup with smart re-chunking.

        Uses BackupIndexingService which has BackupChunkingService that
        can intelligently reuse primary chunks when compatible.
        """
        # Get files that need syncing
        files = await self._get_changed_files()

        # Get primary chunks (for reuse optimization)
        primary_chunks_by_file = await self.primary_store.get_chunks_by_files(files)

        # Re-index using backup service (which will reuse chunks if compatible)
        await self.backup_indexing_service.index_files(
            files,
            source_chunks=primary_chunks_by_file,  # Passed to BackupChunkingService
        )

    async def _sync_from_backup(self) -> None:
        """Sync backup state back to primary."""
        # Get all chunks from backup
        chunks = await self.backup_store.get_all_chunks()

        # Store in primary
        await self.primary_store.upsert_chunks(chunks)

    def get_active_store(self) -> VectorStoreProvider:
        """Get the currently active store (primary or backup)."""
        return self._active_store
```

**Key Changes**:
- **80% simpler** than current `failover.py`
- No construction logic
- No complex resource estimation (simple checks only)
- Clear delegation to IndexingService
- Easy to test
- Smart chunk reuse for efficient failover

### 5. Managers (Checkpoint, Manifest, Progress)

**Purpose**: Pure state management WITHOUT business logic.

```python
# engine/managers/checkpoint_manager.py

"""Checkpoint persistence manager."""

from pathlib import Path
from typing import TYPE_CHECKING

from codeweaver.core import BasedModel

if TYPE_CHECKING:
    from codeweaver.engine.indexer import IndexingCheckpoint

class CheckpointManager:
    """Manages checkpoint persistence.

    Responsibilities:
    - Save/load checkpoint files
    - Validate checkpoint compatibility
    - Clear completed checkpoints

    Does NOT:
    - Implement indexing logic
    - Decide when to checkpoint (that's IndexingService)
    - Construct dependencies
    """

    def __init__(self, project_path: Path, checkpoint_dir: Path):
        """Initialize checkpoint manager."""
        self.project_path = project_path
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, checkpoint: IndexingCheckpoint) -> None:
        """Save checkpoint to disk."""
        checkpoint_file = self._get_checkpoint_path()
        checkpoint_file.write_text(checkpoint.model_dump_json())
        logger.debug("Saved checkpoint: %s", checkpoint_file)

    async def load(self) -> IndexingCheckpoint | None:
        """Load checkpoint from disk if available."""
        checkpoint_file = self._get_checkpoint_path()
        if not checkpoint_file.exists():
            return None

        try:
            data = checkpoint_file.read_text()
            checkpoint = IndexingCheckpoint.model_validate_json(data)

            # Validate compatibility
            if not self._is_compatible(checkpoint):
                logger.warning("Checkpoint incompatible, ignoring")
                return None

            return checkpoint
        except Exception:
            logger.exception("Failed to load checkpoint")
            return None

    async def clear(self) -> None:
        """Remove checkpoint file."""
        checkpoint_file = self._get_checkpoint_path()
        if checkpoint_file.exists():
            checkpoint_file.unlink()
            logger.debug("Cleared checkpoint: %s", checkpoint_file)

    def _get_checkpoint_path(self) -> Path:
        """Get path to checkpoint file for this project."""
        project_hash = get_blake_hash(str(self.project_path))
        return self.checkpoint_dir / f"checkpoint_{project_hash}.json"

    def _is_compatible(self, checkpoint: IndexingCheckpoint) -> bool:
        """Check if checkpoint is compatible with current settings."""
        # Simple version check (details omitted)
        return checkpoint.manifest_version == "1.1.0"
```

**Similar patterns for**:
- `FileManifestManager`: Pure manifest CRUD
- `IndexingProgressTracker`: Pure progress reporting

## Migration Strategy

### Phase 1: Setup (1-2 days)

1. **Create new structure**:
   ```bash
   mkdir -p src/codeweaver/engine/services
   mkdir -p src/codeweaver/engine/managers
   ```

2. **Create `engine/dependencies.py`**:
   - Start with configuration providers
   - Add manager factories
   - Add service factories (empty stubs initially)

3. **Create `engine/config/__init__.py`**:
   - Define per-service settings classes
   - Create aggregated `EngineSettings`

### Phase 2: Extract Managers (2-3 days)

1. **Refactor CheckpointManager**:
   - Extract from current `checkpoint.py`
   - Move to `managers/checkpoint_manager.py`
   - Pure state management only
   - Add to `dependencies.py`

2. **Refactor FileManifestManager**:
   - Extract from current `manifest.py`
   - Move to `managers/manifest_manager.py`
   - Remove business logic
   - Add to `dependencies.py`

3. **Refactor ProgressTracker**:
   - Extract from current `progress.py`
   - Move to `managers/progress_tracker.py`
   - Pure reporting only
   - Add to `dependencies.py`

### Phase 3: Refactor Services (3-4 days)

1. **Refactor IndexingService**:
   - Currently `indexer/indexer.py`
   - Move to `services/indexing_service.py`
   - Remove construction logic
   - Inject managers via dependencies
   - Update tests

2. **Create FailoverService**:
   - Simplify current `failover.py`
   - Move to `services/failover_service.py`
   - Remove resource estimation complexity
   - Inject stores and indexing service
   - Update tests

3. **Refactor ChunkingService**:
   - Move to `services/chunking_service.py`
   - Add smart chunk reuse logic
   - Create BackupChunkingService variant
   - Add to `dependencies.py`
   - Update tests for reuse scenarios

### Phase 4: Remove Legacy (1-2 days)

1. **Delete obsolete files**:
   - `failover_tracker.py` (absorbed into FailoverService)
   - `resource_estimation.py` (simplified away)
   - Old `indexer/indexer.py` (replaced by IndexingService)

2. **Update imports throughout codebase**:
   - `from codeweaver.engine.services import IndexingService`
   - `from codeweaver.engine import IndexingServiceDep`

3. **Update `engine/__init__.py`**:
   - Export new public API

### Phase 5: Testing & Validation (2-3 days)

1. **Unit tests**:
   - Test each manager in isolation
   - Test each service with mocked dependencies
   - Verify DI wiring

2. **Integration tests**:
   - Test full indexing workflow
   - Test failover scenarios
   - Test checkpoint/resume

3. **End-to-end tests**:
   - Real projects
   - Failover under load
   - Performance validation

## Benefits

### Immediate Benefits

1. **Simpler Code**:
   - FailoverService: ~100 lines vs 400+ (75% reduction)
   - No complex construction in business logic
   - Clear separation of concerns

2. **Better Testability**:
   - Easy to mock dependencies
   - Services testable in isolation
   - Managers testable independently

3. **Maintainability**:
   - Changes localized to appropriate files
   - Dependencies explicit via types
   - Configuration changes don't ripple

4. **Consistency**:
   - Matches `core` and `providers` patterns
   - Same DI approach everywhere
   - Backup strategy unified

### Long-term Benefits

1. **Flexibility**:
   - Easy to swap indexing implementations
   - CocoIndex integration feasible later
   - Alternative storage backends simple

2. **Performance**:
   - No redundant construction
   - Better resource utilization
   - Parallelization opportunities

3. **Observability**:
   - Clear component boundaries
   - Easy to add monitoring
   - Telemetry integration straightforward

## CocoIndex Decision

### Why NOT Migrate Now

1. **Constitutional**: Principle IV requires "Proven Patterns". CocoIndex is ~1 year old, not proven at scale.

2. **Architectural Mismatch**: CodeWeaver is an MCP server (tool for AI agents), CocoIndex is an ETL framework (data transformation pipeline). Different domains.

3. **Dependencies**: PostgreSQL requirement conflicts with lightweight deployment model.

4. **Provider Ecosystem**: Would sacrifice current provider flexibility.

### What We Learn From CocoIndex

1. **Content Fingerprinting**: Adopt for better change detection
2. **Row-Level Tracking**: Improve manifest granularity
3. **Declarative Flows**: Consider for complex pipelines (optional mode)
4. **Incremental Processing**: Enhance current approach

### Future Reconsideration

**Revisit CocoIndex in 2-3 years if**:
- It achieves enterprise adoption
- Incremental processing becomes critical user need
- Can be integrated as **optional backend** (not replacement)

## Risks & Mitigation

### Risk 1: Breaking Changes

**Mitigation**:
- Maintain compatibility layer in `engine/__init__.py`
- Deprecation warnings for old imports
- Update all internal usage before removing old code
- Comprehensive test coverage

### Risk 2: Performance Regression

**Mitigation**:
- Benchmark before/after
- DI overhead is minimal (resolved at construction time)
- Parallel processing unchanged
- Memory usage should improve (no ClassVars)

### Risk 3: Incomplete Refactoring

**Mitigation**:
- Work in phases with clear milestones
- Each phase independently testable
- Can pause between phases if needed
- Tests validate each step

### Risk 4: Testing Complexity

**Mitigation**:
- DI actually simplifies testing (easy mocks)
- Start with unit tests for managers
- Add integration tests incrementally
- E2E tests validate full system

## Success Criteria

### Must Have

- ✅ All construction moved to `dependencies.py`
- ✅ Services use injected dependencies only
- ✅ Managers pure state management
- ✅ No ClassVars in services/managers
- ✅ Backup services work via backup_factory
- ✅ All tests passing
- ✅ No performance regression

### Nice to Have

- 📊 Improved performance (memory, speed)
- 📝 Better documentation
- 🧪 Higher test coverage
- 🎯 Clearer component boundaries

## Timeline Estimate

**Total**: 10-15 days (adjusted for BackupChunkingService)

- Phase 1 (Setup): 1-2 days
- Phase 2 (Managers): 2-3 days
- Phase 3 (Services): 4-5 days (includes BackupChunkingService refactor)
- Phase 4 (Cleanup): 1-2 days
- Phase 5 (Testing): 2-3 days

**Assumptions**:
- 1 developer full-time
- Minimal interruptions
- Tests written alongside code
- No major surprises in legacy code
- `backup_factory.py` moved to `core` (prerequisite)

**Note**: Phase 3 extended by 1 day to include BackupChunkingService smart reuse logic

## Open Questions

1. **Should we keep `engine/indexer/` package or flatten to `engine/services/`?**
   - Recommendation: Flatten for simplicity

   **DECISION**: Flatten.

2. **How to handle FileWatcher integration?**
   - Keep in `engine/watcher/` but inject IndexingService

   **DECISION**: Keep separate and inject. FileWatcher is a wrapper around watchfiles and rignore and both are reliable and clean.

3. **Should progress reporting be separate manager or part of IndexingService?**
   - Recommendation: Separate manager for reusability

   **DECISION**: Separate manager

4. **Do we need BackupChunkingService?**
   - Recommendation: No, chunking is deterministic, only backup stores/providers

   **DECISION**: **YES, create BackupChunkingService with smart chunk reuse.**

   **Rationale**:
   - Backup models often have different context windows (e.g., 512 tokens vs 16K tokens)
   - Architectural consistency: matches provider pattern (each component owns ONE config)
   - Optimization opportunity: reuse primary chunks when compatible (avoids redundant chunking)
   - Implementation flexibility: start simple, add reuse logic incrementally
   - Performance: chunking overhead ~2% of total (embedding generation is bottleneck)

   **Implementation Strategy**:
   - Phase 3: Create BackupChunkingService (inherits from ChunkingService)
   - Phase 6 (future): Add smart chunk reuse optimization
   - Backup service checks chunk compatibility before reusing
   - Only re-chunks when primary chunks exceed backup model constraints

## Next Steps

1. **Review this design** with team
2. **Approve or adjust** approach
3. **Create implementation tickets** for each phase
4. **Begin Phase 1** (Setup)
5. **Daily check-ins** during implementation

## Appendix: Example Test

```python
# tests/engine/services/test_indexing_service.py

import pytest
from unittest.mock import Mock, AsyncMock
from codeweaver.engine.services import IndexingService
from codeweaver.engine.managers import CheckpointManager, FileManifestManager
from codeweaver.engine.config import IndexingServiceSettings

@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for IndexingService."""
    return {
        "chunking_service": Mock(),
        "embedding_provider": AsyncMock(),
        "sparse_embedding_provider": None,
        "vector_store": AsyncMock(),
        "checkpoint_manager": Mock(spec=CheckpointManager),
        "manifest_manager": AsyncMock(spec=FileManifestManager),
        "settings": IndexingServiceSettings(),
    }

async def test_index_project_basic(mock_dependencies, tmp_path):
    """Test basic indexing workflow."""
    # Arrange
    service = IndexingService(**mock_dependencies)
    mock_dependencies["manifest_manager"].filter_unchanged.return_value = []

    # Act
    stats = await service.index_project(tmp_path)

    # Assert
    assert stats.files_processed == 0
    mock_dependencies["checkpoint_manager"].clear.assert_called_once()

async def test_index_project_with_checkpoint(mock_dependencies, tmp_path):
    """Test checkpoint resume."""
    # Arrange
    service = IndexingService(**mock_dependencies)
    checkpoint = Mock(files_processed=50)
    mock_dependencies["checkpoint_manager"].load.return_value = checkpoint

    # Act
    stats = await service.index_project(tmp_path, resume=True)

    # Assert
    mock_dependencies["checkpoint_manager"].load.assert_called_once()
```

---

**Document Version**: 1.1
**Last Updated**: 2026-01-16
**Authors**: Claude Sonnet 4.5 + User
**Status**: Ready for Implementation

**Changelog**:
- v1.1: Added BackupChunkingService with smart chunk reuse
- v1.1: Updated dependencies.py to include ChunkingService factories
- v1.1: Enhanced FailoverService with backup chunking integration
- v1.1: Noted backup_factory moving to core package
- v1.1: Adjusted timeline (+1 day for BackupChunkingService)
- v1.0: Initial design

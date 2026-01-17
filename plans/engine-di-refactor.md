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
   - Factories call other factories directly for internal wiring (reducing DI abstraction overhead)
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
   - Shared mutable state across components
   - Difficult-to-test code

3. **Construction Responsibilities**:
   - Indexer, ChunkingService, Checkpoint, Manifest all have complex init logic
   - Configuration validation mixed with business logic
   - Hard to create test doubles

4. **Tight Coupling**:
   - Components directly instantiate dependencies using `INJECTED` defaults in `__init__`
   - Difficult to swap implementations
   - Hard to test in isolation without DI overrides

## Design Principles

### 1. Follow Provider Pattern

**Apply lessons from provider refactoring**:

- ✅ Construction external to business logic (in `engine/dependencies.py`)
- ✅ **Factory Injection**: Factories accept dependencies as arguments (`= INJECTED`), allowing the Container to manage resolution and overrides.
- ✅ **Clean Constructors**: Service `__init__` methods take required dependencies (no `INJECTED`, no `None` defaults).
- ✅ Dependency injection via markers (from `core` and `providers`) for external deps.
- ✅ Backup components as separate instances.

### 2. Separation of Concerns

**Clear boundaries**:

```
engine/
├── dependencies.py          # ⭐ Construction and wiring (NEW)
├── config/                  # Configuration types (IndexerSettings, ChunkerSettings, FailoverSettings)
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
engine/dependencies.py (Factories) --[Container Resolves]--> Dependencies
   ↓ constructs
Services (Indexer, ChunkingService) --[via clean __init__]--> Managers & Core/Providers
   ↓ uses
Business Logic
```

**Key insight**: Services become "dumb" containers of logic; `dependencies.py` handles the "smart" wiring via the Container.

### 4. Configuration Strategy

**Reuse Existing Config Types**:
We will reuse the existing configuration types in `codeweaver.engine.config`. They are sufficient and do not require the massive overhaul seen in providers.

- **`IndexerSettings`** (`engine/config/indexer.py`): Covers indexing, file filtering, and general engine options.
- **`ChunkerSettings`** (`engine/config/chunker.py`): Covers chunking strategies and overlap.
- **`FailoverSettings`** (`engine/config/failover.py`): Covers backup sync intervals, auto-restore logic, and memory limits.

## Detailed Component Design

### 1. Dependency Injection Setup (`engine/dependencies.py`)

**Purpose**: Central construction and wiring for all engine components.

**Pattern**: Factories request dependencies via `INJECTED` arguments. This ensures that if a dependency is overridden in the Container (e.g., for testing), the factory receives the overridden instance.

```python
# engine/dependencies.py

"""Dependency injection setup for engine components.

This module provides DI factories for engine services and managers.
All construction logic lives here, keeping business logic clean.
"""

from typing import Annotated
from codeweaver.core import (
    INJECTED,
    depends,
    dependency_provider,
    create_backup_class,
    SettingsDep,
)
from codeweaver.engine.config import IndexerSettings, ChunkerSettings, FailoverSettings
# ... provider imports ...

# ===========================================================================
# Configuration Factories
# ===========================================================================

@dependency_provider(IndexerSettings, scope="singleton")
def _get_indexer_settings(
    settings: SettingsDep = INJECTED
) -> IndexerSettings:
    """Factory for indexer settings."""
    # Logic to extract/validate indexer settings from root settings
    return settings.indexer

@dependency_provider(ChunkerSettings, scope="singleton")
def _get_chunker_settings(
    settings: SettingsDep = INJECTED
) -> ChunkerSettings:
    """Factory for chunker settings."""
    return settings.chunker

@dependency_provider(FailoverSettings, scope="singleton")
def _get_failover_settings(
    settings: SettingsDep = INJECTED
) -> FailoverSettings:
    """Factory for failover settings."""
    return settings.failover

# ===========================================================================
# Manager Factories
# ===========================================================================

@dependency_provider(CheckpointManager, scope="singleton")
def _create_checkpoint_manager(
    settings: Annotated[IndexerSettings, depends(_get_indexer_settings)] = INJECTED,
) -> CheckpointManager:
    """Factory for checkpoint manager."""
    # Settings are injected by the container, allowing for overrides
    return CheckpointManager(
        project_path=settings.project_path, # derived or from core settings
        checkpoint_dir=settings.cache_dir / "checkpoints"
    )

# ... similar for ManifestManager ...

# ===========================================================================
# Service Factories
# ===========================================================================

@dependency_provider(ChunkingService, scope="singleton")
def _create_chunking_service(
    governor: GovernorDep = INJECTED,
    tokenizer: TokenizerDep = INJECTED,
    settings: Annotated[ChunkerSettings, depends(_get_chunker_settings)] = INJECTED,
) -> ChunkingService:
    """Factory for primary chunking service."""
    return ChunkingService(
        governor=governor,
        tokenizer=tokenizer,
        settings=settings,
    )

@dependency_provider(IndexingService, scope="singleton")
def _create_indexing_service(
    embedding_provider: EmbeddingDep = INJECTED,
    sparse_embedding_provider: SparseEmbeddingDep = INJECTED,
    vector_store: VectorStoreDep = INJECTED,
    chunking_service: Annotated[ChunkingService, depends(_create_chunking_service)] = INJECTED,
    checkpoint_manager: Annotated[CheckpointManager, depends(_create_checkpoint_manager)] = INJECTED,
    manifest_manager: Annotated[FileManifestManager, depends(_create_manifest_manager)] = INJECTED,
    settings: Annotated[IndexerSettings, depends(_get_indexer_settings)] = INJECTED,
) -> IndexingService:
    """Factory for indexing service.
    
    All dependencies are injected by the container.
    """
    return IndexingService(
        chunking_service=chunking_service,
        embedding_provider=embedding_provider,
        sparse_embedding_provider=sparse_embedding_provider,
        vector_store=vector_store,
        checkpoint_manager=checkpoint_manager,
        manifest_manager=manifest_manager,
        settings=settings,
    )

# ... similar for FailoverService and BackupIndexingService ...
```

### 2. Service Refactoring (Clean Constructors)

**Purpose**: Services should not know about `INJECTED` or default values. They expect ready-to-use objects.

```python
# engine/services/indexing_service.py

class IndexingService:
    """Orchestrates the indexing workflow."""

    def __init__(
        self,
        chunking_service: ChunkingService,
        embedding_provider: EmbeddingProvider,
        sparse_embedding_provider: SparseEmbeddingProvider | None,
        vector_store: VectorStoreProvider,
        checkpoint_manager: CheckpointManager,
        manifest_manager: FileManifestManager,
        settings: IndexerSettings,
    ):
        """Initialize indexing service. 
        
        NO default values, NO INJECTED markers. 
        Dependencies must be provided by the factory.
        """
        self.chunking_service = chunking_service
        self.embedding_provider = embedding_provider
        self.sparse_embedding_provider = sparse_embedding_provider
        self.vector_store = vector_store
        self.checkpoint_manager = checkpoint_manager
        self.manifest_manager = manifest_manager
        self.settings = settings
```

## Migration Strategy

### Phase 1: Setup & Dependencies (1-2 days)

1. **Extend Config**: Create `engine/config/failover.py` and integrate into root settings. (Completed)
2. **Verify Config**: Ensure `IndexerSettings` and `ChunkerSettings` are ready.
3. **Create `engine/dependencies.py`**:
   - Implement configuration factories (`_get_indexer_settings`, `_get_failover_settings`, etc.).
   - Implement manager factories.
   - Implement service factories (stubs initially).
   - Use `INJECTED` arguments to wire dependencies via the Container.

### Phase 2: Extract Managers (2-3 days)

1. **Refactor CheckpointManager**:
   - Move to `managers/checkpoint_manager.py`.
   - Update `__init__` to be clean (no defaults).
   - Update `dependencies.py` factory to construct it.

2. **Refactor FileManifestManager** & **ProgressTracker**:
   - Similar move and cleanup.

### Phase 3: Refactor Services (3-4 days)

1. **Refactor IndexingService**:
   - Move `indexer/indexer.py` logic to `services/indexing_service.py`.
   - **Crucial**: Strip `__init__` of all `INJECTED` markers and `None` handling.
   - Inject managers via `dependencies.py` factory.

2. **Refactor ChunkingService**:
   - Move to `services/chunking_service.py`.
   - Clean `__init__`.
   - Add backup variant logic (smart reuse).

3. **Create FailoverService**:
   - Extract from `failover.py`.
   - Clean `__init__`.
   - **Update**: Check if backup store is in-memory before applying memory limits.

### Phase 4: Remove Legacy (1-2 days)

1. **Delete obsolete files** (`failover.py`, `failover_tracker.py`, etc.).
2. **Update imports**.
3. **Verify via tests**.

## Benefits (Refined)

- **Simplicity**: Service initialization becomes trivial assignment.
- **Traceability**: `dependencies.py` provides a single view of how the system is wired.
- **Testability**: Every dependency in `dependencies.py` can be overridden in the container without modifying service code.
- **Flexibility**: Backup components are just instances created with different configs/factories.

## Success Criteria

- ✅ `engine/dependencies.py` contains all construction logic.
- ✅ Service constructors have no `INJECTED` markers or `None` defaults for required deps.
- ✅ Existing config types (`IndexerSettings`, `ChunkerSettings`) reused and new `FailoverSettings` added.
- ✅ Tests pass with explicit dependency injection (mocks).

## Appendix: FailoverService Design Update

```python
    async def _is_backup_safe(self) -> bool:
        """Check if activating backup is safe (resource-wise)."""
        # If backup is NOT in-memory (e.g., local Qdrant collection), 
        # process memory limits are less critical.
        if not self._is_in_memory_store(self.backup_store):
            return True

        # For in-memory stores, check available RAM
        import psutil
        available_mb = psutil.virtual_memory().available / 1024 / 1024
        return available_mb > self.settings.max_memory_mb

    def _is_in_memory_store(self, store: VectorStoreProvider) -> bool:
        """Check if store is in-memory."""
        # Check type or config
        from codeweaver.providers.vector_stores.inmemory import MemoryVectorStoreProvider
        return isinstance(store, MemoryVectorStoreProvider)
```

---

**Document Version**: 1.5
**Last Updated**: 2026-01-16
**Authors**: Claude Sonnet 4.5 + User
**Status**: Ready for Implementation

**Changelog**:
- v1.5: Updated FailoverService design to only check memory for in-memory backup stores.
- v1.4: Added FailoverSettings creation and integration.
- v1.3: Updated dependencies.py pattern to use "Factory Injection" (INJECTED args) to support container overrides.
- v1.2: Refined Phase 1 to reuse existing config types (IndexerSettings, ChunkerSettings)
- v1.2: Clarified that Service constructors will be stripped of INJECTED markers and defaults
- v1.1: Added BackupChunkingService with smart chunk reuse
- v1.1: Updated dependencies.py to include ChunkingService factories
- v1.1: Enhanced FailoverService with backup chunking integration
- v1.1: Noted backup_factory moving to core package
- v1.1: Adjusted timeline (+1 day for BackupChunkingService)
- v1.0: Initial design

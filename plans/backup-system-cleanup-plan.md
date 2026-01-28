<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Old Backup System Cleanup Plan

**Date**: 2026-01-28
**Status**: Ready for Execution
**Approach**: Direct removal (no deprecation warnings)

## Understanding: New vs Old System

### NEW SYSTEM (Already Working ✅ - KEEP)
- **Multi-vector backup**: Additional vectors on same points via `VectorRole` enum
- **Three-phase loop**: Vector reconciliation + snapshot management
- **Priority system**: `very_low_priority()` for backup, `low_priority()` for primary
- **Smart failover**: Only runs for cloud embedding providers OR cloud vector stores
- **Single indexing service**: Generates all embeddings (primary + backup vectors)
- **Hardcoded backup models**: `backup_models.py` - Models with large context windows that handle any chunk size

### OLD SYSTEM (Deprecated ❌ - REMOVE)
- **Backup class factories**: `create_backup_class()` - ALREADY REMOVED (commit cd45eeb9)
- **Backup DI injectors**: `BackupEmbeddingProviderDep`, etc. - ALREADY REMOVED
- **BackupEmbeddingRegistry**: Separate registry subclass - NEEDS REMOVAL
- **Dual chunking**: `ChunkGovernor.from_backup_profile()` - NEEDS REMOVAL (no longer needed with hardcoded backup models)
- **Separate backup indexing service**: Extra `IndexingService` instance - NEEDS REMOVAL
- **Old backup profile**: Testing profile aliased as backup - NEEDS REMOVAL

---

## Critical Bug to Fix First

### 1. Missing `_create_failover_service()` Factory ⚠️ BLOCKING

**File**: `src/codeweaver/engine/dependencies.py`

**Issue**: Line 243 references undefined factory function

**Fix**: Add this function
```python
@dependency_provider(FailoverService, scope="singleton")
def _create_failover_service(
    primary_store: VectorStoreProviderDep = INJECTED,
    backup_store: VectorStoreProviderDep | None = None,
    indexing_service: IndexingServiceDep = INJECTED,
    settings: FailoverSettingsDep = INJECTED,
) -> FailoverService:
    """Create FailoverService with dependencies."""
    return FailoverService(
        primary_store=primary_store,
        backup_store=backup_store,
        indexing_service=indexing_service,
        settings=settings,
    )
```

**Note**: This factory should NOT include `backup_indexing_service` parameter (new system doesn't need it)

---

## Cleanup Tasks

### ~~Task 1: Remove Hardcoded Backup Models~~ ❌ KEEP THIS FILE

**File**: `src/codeweaver/providers/config/backup_models.py` (208 lines)

**Action**: **KEEP** - This is part of the NEW system

**Rationale**:
- Hardcodes backup models with LARGE context windows (minishlab/potion-base-8M, jinaai/jina-embeddings-v2-small-en)
- This is the **solution** that eliminated dual chunking complexity
- Chunks sized for primary model, backup models guaranteed to handle them
- **KEY INSIGHT**: Large context windows mean no need for backup-specific chunk sizing

**Status**: ✅ Part of new architecture, no changes needed

---

### Task 1: Remove BackupEmbeddingRegistry

**File**: `src/codeweaver/providers/embedding/registry.py`

**Lines to Remove**:
- **146-156**: `BackupEmbeddingRegistry` class definition
- **192-195**: `_get_backup_registry()` factory function
- **46**: `is_backup_provider: bool = False` attribute in `EmbeddingRegistry`
- **49**: `is_backup_provider` parameter in `__init__()`
- **62**: `self.is_backup_provider = is_backup_provider` assignment

**After Cleanup**: Single `EmbeddingRegistry` class without backup variants

---

#### Task 2.2: Remove Dual Chunking Logic

**File**: `src/codeweaver/engine/chunker/base.py`

**Lines to Remove**:
- **284-366**: `ChunkGovernor.from_backup_profile()` method (~82 lines)

**File**: `src/codeweaver/engine/services/chunking_service.py`

**Lines to Remove**:
- **59**: Conditional check `if source_chunks and self._is_backup_service():`
- **77-87**: `_chunk_with_reuse()` method
- **93-99**: `_can_reuse_chunks()` and `can_reuse_chunks()` methods

**Bug Fix**: Remove undefined reference to `_is_backup_service()` method

---

#### Task 2.3: Remove backup_indexing_service Parameter

**File**: `src/codeweaver/engine/services/failover_service.py`

**Changes**:
1. **Line 44**: Remove `backup_indexing_service: IndexingService` parameter from `__init__()`
2. **Line 51**: Remove `self.backup_indexing_service = backup_indexing_service` assignment
3. **Lines 100-144**: REMOVE ENTIRE `_maintain_backup_loop()` method
4. **Lines 73-75**: Remove task registration in `start_monitoring()`:
   ```python
   # Remove this:
   self._backup_maintenance_task = asyncio.create_task(
       self._maintain_backup_loop(), name="backup_maintenance_loop"
   )
   ```
5. **Lines 60-62** (OPTIONAL): Remove cycle counter fields if not repurposing:
   ```python
   # _maintenance_cycle_count: int = 0
   # _snapshot_cycle_count: int = 0
   ```

**Result**: FailoverService now only does health monitoring + failover activation/restoration

**Keep**:
- `_monitor_health()` - Circuit breaker health checks
- `_activate_failover()` - Switch to backup vector store
- `_restore_primary()` - Restore to primary vector store
- `_run_reconciliation()` - Optional repurpose for vector reconciliation
- `_run_snapshot_maintenance()` - Snapshot management for cloud stores

---

#### Task 2.4: Remove is_provider_backup Property

**File**: `src/codeweaver/providers/embedding/providers/base.py`

**Lines to Remove**:
- **738-740**: `is_provider_backup` property (stub, always returns False)

---

#### Task 2.5: Remove Old Backup Profile

**File**: `src/codeweaver/providers/config/profiles.py`

**Lines to Remove**:
- **465-469**: `BACKUP` profile definition

---

### Phase 3 Tasks: Update Test Files

#### File: `tests/integration/engine/test_failover_snapshot_integration.py`

**Changes**:
- **Line 83**: Remove `backup_indexing_service` parameter from fixture
- **Lines 98, 273, 322**: Remove mock patches for `backup_indexing_service.index_project`
- **Lines 103, 278, 331**: Remove or update direct calls to `backup_indexing_service.index_project()`

#### File: `tests/integration/workflows/test_backup_system_e2e.py`

**Changes**:
- **Lines 98, 171, 217, 275, 467**: Remove `backup_indexing_service` parameter from 5 constructor calls

#### File: `tests/integration/providers/test_embedding_failover.py`

**Action**: DELETE ENTIRE FILE (345 lines)

**Rationale**: Tests reproduce bugs in deprecated backup system

#### Other Test Files

- **`tests/unit/core/types/test_chunk_embeddings_properties.py`**: Remove 2 backup-specific tests
- **`tests/unit/providers/types/test_vectors.py`**: Remove 2 backup-specific tests
- **`tests/unit/providers/test_wal_config_integration.py`**: Remove 3 of 6 tests (failover-specific)

---

### Phase 4 Tasks: Registry Migration to Cache Manager Pattern

#### Task 4.1: Implement EmbeddingCacheManager

**New File**: `src/codeweaver/providers/embedding/cache_manager.py`

**Purpose**: Centralized cache with namespace isolation replacing per-instance stores

**Implementation**:
```python
"""Centralized embedding cache manager with namespace isolation."""
from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from pydantic import Field

from codeweaver.core.chunks import CodeChunk
from codeweaver.core.stores import UUIDStore, BlakeStore
from codeweaver.core.types import UUID7, BlakeHashKey
from codeweaver.core.types.models import BasedModel
from codeweaver.providers.embedding.registry import EmbeddingRegistry


class EmbeddingCacheManager(BasedModel):
    """Centralized cache manager with namespace isolation.

    Replaces per-instance provider stores with a shared singleton
    that provides namespace-based isolation for different providers
    and embedding kinds (dense vs sparse).

    Benefits:
    - True cross-instance deduplication
    - Namespace isolation prevents collisions
    - Simpler provider code (3 method calls vs managing stores)
    - Async-safe with per-namespace locks
    - Better observability (cache hit rates)
    """

    # Internal stores organized by namespace
    _batch_stores: dict[str, UUIDStore[list]] = Field(default_factory=dict)
    _hash_stores: dict[str, BlakeStore[UUID7]] = Field(default_factory=dict)
    _locks: dict[str, asyncio.Lock] = Field(default_factory=dict)

    # Global registry (unchanged)
    registry: EmbeddingRegistry

    def _get_namespace(self, provider_id: str, embedding_kind: str) -> str:
        """Generate namespace: 'voyage-code-2.dense' or 'voyage-code-2.sparse'"""
        return f"{provider_id}.{embedding_kind}"

    def _ensure_namespace(self, namespace: str) -> None:
        """Lazily initialize stores for namespace."""
        if namespace not in self._batch_stores:
            from codeweaver.core.stores import make_uuid_store, make_blake_store

            self._batch_stores[namespace] = make_uuid_store(
                value_type=list, size_limit=3 * 1024 * 1024  # 3 MB
            )
            self._hash_stores[namespace] = make_blake_store(
                value_type=UUID7, size_limit=256 * 1024  # 256 KB
            )
            self._locks[namespace] = asyncio.Lock()

    async def deduplicate(
        self,
        chunks: list[CodeChunk],
        namespace: str,
        batch_id: UUID7,
    ) -> tuple[list[CodeChunk], dict[int, BlakeHashKey]]:
        """Deduplicate chunks and return unique ones with hash mapping.

        Args:
            chunks: Input chunks to deduplicate
            namespace: Provider namespace (e.g., 'voyage-code-2.dense')
            batch_id: UUID7 for this batch

        Returns:
            (unique_chunks, hash_mapping)
            - unique_chunks: Chunks not yet embedded
            - hash_mapping: {original_idx: hash} for all chunks
        """
        self._ensure_namespace(namespace)

        async with self._locks[namespace]:
            from codeweaver.core.utils import get_blake_hash

            # Compute hashes
            hashes = {
                i: get_blake_hash(chunk.content.encode("utf-8"))
                for i, chunk in enumerate(chunks)
            }

            # Find unique chunks
            hash_store = self._hash_stores[namespace]
            unique_chunks = [
                chunk for i, chunk in enumerate(chunks)
                if hashes[i] not in hash_store
            ]

            # Register hashes
            for i, chunk in enumerate(unique_chunks):
                hash_store[hashes[i]] = batch_id

            return unique_chunks, hashes

    async def store_batch(
        self,
        chunks: list[CodeChunk],
        batch_id: UUID7,
        namespace: str,
    ) -> None:
        """Store batch for potential reprocessing."""
        self._ensure_namespace(namespace)

        async with self._locks[namespace]:
            self._batch_stores[namespace][batch_id] = chunks

    async def get_batch(
        self,
        batch_id: UUID7,
        namespace: str,
    ) -> list[CodeChunk] | None:
        """Retrieve batch by ID."""
        self._ensure_namespace(namespace)

        async with self._locks[namespace]:
            return self._batch_stores[namespace].get(batch_id)

    async def register_embeddings(
        self,
        chunk_id: UUID7,
        embedding_info: "EmbeddingBatchInfo",
    ) -> None:
        """Register embeddings in global registry.

        Note: This does NOT need namespace locking as the registry
        is keyed by chunk_id, not namespace.
        """
        self.registry[chunk_id].add(embedding_info)

    def get_stats(self, namespace: str) -> dict:
        """Get cache statistics for namespace."""
        if namespace not in self._batch_stores:
            return {"exists": False}

        return {
            "exists": True,
            "batch_store_size": len(self._batch_stores[namespace]),
            "hash_store_size": len(self._hash_stores[namespace]),
            "batch_store_bytes": self._batch_stores[namespace].total_size,
            "hash_store_bytes": self._hash_stores[namespace].total_size,
        }
```

---

#### Task 4.2: Add FastAPI Lifespan Management

**File**: `src/codeweaver/server/server.py` or similar

**Changes**: Add singleton cache manager via lifespan

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Initialize cache manager
    from codeweaver.providers.embedding.cache_manager import EmbeddingCacheManager
    from codeweaver.providers.embedding.registry import get_embedding_registry

    cache_manager = EmbeddingCacheManager(
        registry=get_embedding_registry()
    )

    # Store in app state
    app.state.cache_manager = cache_manager

    yield

    # Cleanup (if needed)
    # cache_manager.cleanup()

app = FastAPI(lifespan=lifespan)
```

---

#### Task 4.3: Add DI Provider for Cache Manager

**File**: `src/codeweaver/providers/dependencies.py`

**Add**:
```python
from codeweaver.providers.embedding.cache_manager import EmbeddingCacheManager

@dependency_provider(EmbeddingCacheManager, scope="singleton")
def _get_cache_manager(registry: EmbeddingRegistryDep = INJECTED) -> EmbeddingCacheManager:
    """Get or create singleton cache manager."""
    return EmbeddingCacheManager(registry=registry)

# Type alias for DI
type CacheManagerDep = Annotated[
    EmbeddingCacheManager, depends(_get_cache_manager, scope="singleton")
]
```

---

#### Task 4.4: Refactor Providers to Use Cache Manager

**File**: `src/codeweaver/providers/embedding/providers/base.py`

**Changes**:

1. **Remove per-instance stores from `__init__`**:
```python
def __init__(
    self,
    client: EmbeddingClient,
    config: EmbeddingProviderSettings,
    registry: EmbeddingRegistry,
    cache_manager: CacheManagerDep,  # NEW: injected cache manager
    caps: EmbeddingCapabilityGroup,
    # REMOVE: store_kwargs, hash_store_kwargs
    ...
):
    # REMOVE these lines:
    # object.__setattr__(self, "_store", make_uuid_store(**store_kwargs))
    # object.__setattr__(self, "_hash_store", make_blake_store(**hash_store_kwargs))

    # ADD this:
    self._cache_manager = cache_manager
    self._namespace = cache_manager._get_namespace(
        provider_id=self.provider_id,
        embedding_kind=self.caps.embedding_kind.value
    )
```

2. **Refactor `_process_input()` to use cache manager**:
```python
async def _process_input(
    self,
    chunk_list: Sequence[CodeChunk],
    key: UUID7,
    skip_deduplication: bool = False,
) -> list[CodeChunk]:
    """Process input chunks with deduplication."""

    if skip_deduplication:
        starter_chunks = list(chunk_list)
        await self._cache_manager.store_batch(starter_chunks, key, self._namespace)
        return starter_chunks

    # Deduplicate via cache manager
    unique_chunks, hash_mapping = await self._cache_manager.deduplicate(
        chunks=list(chunk_list),
        namespace=self._namespace,
        batch_id=key,
    )

    # Store batch
    await self._cache_manager.store_batch(unique_chunks, key, self._namespace)

    return unique_chunks
```

3. **Update `_register_chunks()` to use cache manager**:
```python
async def _register_chunks(
    self,
    batch_id: UUID7,
    chunks: Sequence[CodeChunk],
    embeddings: Sequence[list[float] | SparseEmbedding],
) -> None:
    """Register embeddings via cache manager."""

    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_info = EmbeddingBatchInfo.create_dense(
            batch_id=batch_id,
            batch_index=i,
            chunk_id=chunk.chunk_id,
            model=self.model_name,
            embeddings=embedding,
            dtype=self.get_datatype()
        )

        # Use cache manager instead of direct registry access
        await self._cache_manager.register_embeddings(chunk.chunk_id, chunk_info)
```

---

#### Task 4.5: Replace threading.Lock with asyncio.Lock

**Already handled** by EmbeddingCacheManager which uses `asyncio.Lock` per namespace.

**Benefit**: Async-safe locking without blocking event loop.

---

#### Task 4.6: Update Tests

**Changes Needed**:

1. **Test fixtures**: Inject cache manager instead of mocking stores
2. **Namespace isolation**: Each test gets unique namespace
3. **Async context**: Ensure tests use `asyncio.run()` or pytest-asyncio

**Example**:
```python
@pytest.fixture
def cache_manager():
    """Provide cache manager with test registry."""
    registry = get_embedding_registry()
    return EmbeddingCacheManager(registry=registry)

@pytest.mark.asyncio
async def test_deduplication(cache_manager):
    """Test deduplication across providers."""
    namespace = "test-provider.dense"

    chunks = [CodeChunk(...), CodeChunk(...)]
    batch_id = uuid7()

    # First call: All unique
    unique1, _ = await cache_manager.deduplicate(chunks, namespace, batch_id)
    assert len(unique1) == 2

    # Second call: All duplicates
    unique2, _ = await cache_manager.deduplicate(chunks, namespace, batch_id)
    assert len(unique2) == 0
```

---

## Execution Plan

### Phase 1: Critical Bug Fix (15 minutes)
1. ✅ Define `_create_failover_service()` factory in `engine/dependencies.py`
2. ✅ Verify FailoverService can be instantiated via DI

### Phase 2: Remove Old System Code (1 hour)
3. ✅ Remove `BackupEmbeddingRegistry` from `registry.py` (~50 lines)
4. ✅ Remove dual chunking logic from `base.py` and `chunking_service.py` (~150 lines)
5. ✅ Remove `backup_indexing_service` from `failover_service.py` (~50 lines)
6. ✅ Remove `is_provider_backup` property from `base.py` (3 lines)
7. ✅ Remove old backup profile from `profiles.py` (5 lines)

### Phase 3: Update Tests (30 minutes)
9. ✅ Delete `test_embedding_failover.py`
10. ✅ Update `test_failover_snapshot_integration.py` (7 changes)
11. ✅ Update `test_backup_system_e2e.py` (5 changes)
12. ✅ Remove backup-specific tests in type test files (4 tests)
13. ✅ Update WAL config tests (remove 3 tests)

### Phase 4: Validation (15 minutes)
14. ✅ Run full test suite: `mise run test`
15. ✅ Run linting: `mise run lint`
16. ✅ Verify no imports of removed code
17. ✅ Verify FailoverService still works for vector store failover

---

## Code Removal Summary

### Production Code
| File | Lines to Remove | Action |
|------|----------------|--------|
| ~~`backup_models.py`~~ | ~~208~~ | **KEEP** (part of new system) |
| `registry.py` | 50 | Remove BackupEmbeddingRegistry |
| `base.py` (chunker) | 82 | Remove from_backup_profile() |
| `chunking_service.py` | 50 | Remove chunk reuse logic |
| `failover_service.py` | 50 | Remove backup_indexing_service |
| `base.py` (providers) | 3 | Remove is_provider_backup |
| `profiles.py` | 5 | Remove BACKUP profile |
| `dependencies.py` | 0 | ADD factory (net positive) |
| **TOTAL** | **~240 lines removed** | |

### Test Code
| File | Lines to Remove | Action |
|------|----------------|--------|
| `test_embedding_failover.py` | 345 | DELETE FILE |
| `test_failover_snapshot_integration.py` | 20 | Update 7 locations |
| `test_backup_system_e2e.py` | 10 | Update 5 locations |
| `test_chunk_embeddings_properties.py` | 10 | Remove 2 tests |
| `test_vectors.py` | 10 | Remove 2 tests |
| `test_wal_config_integration.py` | 60 | Remove 3 tests |
| **TOTAL** | **~455 lines removed** | |

**Grand Total**: ~695 lines of old backup system code removed

---

## Risk Assessment

### Low Risk ✅
- ~~`backup_models.py` deletion~~ - **KEEPING** (part of new system)
- `BackupEmbeddingRegistry` removal - not used in production
- Dual chunking removal - `_is_backup_service()` undefined anyway
- Test file deletion - tests deprecated functionality
- O(n) store write fix - simple move outside loop
- O(n²) lookup fix - straightforward dict pre-build

### Medium Risk ⚠️
- `backup_indexing_service` removal from FailoverService
  - **Mitigation**: New system uses single indexing service with multi-vector
  - **Validation**: Test that vector reconciliation still works
- Cache manager migration
  - **Mitigation**: Phased rollout, keep old code until tests pass
  - **Validation**: Comprehensive test suite for namespace isolation

### High Risk 🔴
- Missing factory definition
  - **Mitigation**: Add factory FIRST before any other changes
  - **Validation**: Verify FailoverService DI resolution works
- Async safety (threading.Lock → asyncio.Lock)
  - **Mitigation**: Cache manager handles all locking correctly
  - **Validation**: Concurrent embedding test with multiple providers

---

## Success Criteria

### Code Quality
- ✅ `backup_models.py` kept (part of new system)
- ✅ No `BackupEmbeddingRegistry` class
- ✅ No `backup_indexing_service` parameter
- ✅ No dual chunking logic
- ✅ All imports resolve
- ✅ All tests pass
- ✅ Cache manager with namespace isolation
- ✅ Async-safe with `asyncio.Lock`
- ✅ DI-based singleton pattern

### Functionality
- ✅ FailoverService health monitoring works
- ✅ Vector store failover works
- ✅ Multi-vector backup works
- ✅ Snapshot creation works
- ✅ Vector reconciliation works
- ✅ True cross-instance deduplication
- ✅ Namespace-isolated caches

### Performance
- ✅ Indexing uses single service
- ✅ No separate backup maintenance loop
- ✅ Priority system intact
- ✅ 10-20x speedup from O(n) fix
- ✅ O(n²) → O(n) for index lookups
- ✅ Async-native locking (no event loop blocking)

---

## Post-Cleanup Verification

### Manual Checks
```bash
# 1. Verify no imports of removed code (backup_models.py should still exist)
grep -r "BackupEmbeddingRegistry" src/
grep -r "backup_indexing_service" src/
grep -r "from_backup_profile" src/

# 2. Run tests
mise run test

# 3. Run linting
mise run lint

# 4. Check for undefined references
mise run check
```

### Expected Results
- No grep matches for removed code
- All tests pass
- No linting errors
- No type checking errors

---

## Implementation Notes

### Order Matters
1. **FIRST**: Add `_create_failover_service()` factory
2. **SECOND**: Remove production code
3. **THIRD**: Update tests
4. **LAST**: Validate

### Be Careful With
- ~~Imports from `backup_models.py`~~ - This file is KEPT (part of new system)
- Conditional checks for `is_backup_provider` attribute
- Test fixtures that create FailoverService
- Any code using `backup=True` parameter (this is NEW system, keep it)

### Don't Remove
- `backup_models.py` - **Core of new system** (hardcoded models with large context windows)
- `VectorRole.BACKUP` enum value (used by new system)
- `backup` parameter in `get_provider_settings()` (new system)
- Three-phase loop architecture (new system)
- Priority context managers in `procs.py` (new system)
- Snapshot service (new system)
- Vector reconciliation (new system)

---

## Estimated Timeline

| Phase | Duration | Complexity |
|-------|----------|-----------|
| Phase 1: Critical Fixes | 30 mins | Low |
| Phase 2: Remove Old System | 1 hour | Low |
| Phase 3: Update Tests | 30 mins | Low |
| Phase 4: Registry Migration | 4-6 hours | Medium |
| Phase 5: Final Validation | 30 mins | Low |
| **TOTAL** | **7-8.5 hours** | **Medium** |

**Suggested Approach**: Can be done in two sessions:
- **Session 1** (2 hours): Phases 1-3 (quick wins, old system removal)
- **Session 2** (5-6 hours): Phase 4-5 (registry migration, testing)

---

## Next Steps

1. **Review this plan** with team
2. **Create feature branch**: `git checkout -b feat/backup-cleanup-and-registry-migration`
3. **Execute Phase 1**: Critical performance fixes (30 mins)
4. **Execute Phase 2-3**: Remove old backup system (1.5 hours)
5. **Commit checkpoint**: "refactor: remove old backup system artifacts"
6. **Execute Phase 4**: Migrate to cache manager (4-6 hours)
7. **Execute Phase 5**: Final validation (30 mins)
8. **Create PR** with comprehensive testing
9. **Document** architectural improvements in ARCHITECTURE.md

---

## Documentation Updates Needed

After completion, update these files:

1. **ARCHITECTURE.md**: Document cache manager pattern
2. **Embedding provider README**: Update usage examples
3. **Migration guide**: Document breaking changes (if any)
4. **Performance benchmarks**: Document 10-20x speedup

---

**Ready to proceed with execution**

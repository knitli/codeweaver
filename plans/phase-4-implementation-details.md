<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Phase 4: Registry Migration Implementation Details

**Status**: In Progress
**Date Started**: 2026-01-28
**Estimated Completion**: 4-6 hours

## Overview

Phase 4 migrates from per-instance `_store` and `_hash_store` ClassVar registries to a centralized `EmbeddingCacheManager` singleton with namespace isolation. This enables true cross-instance deduplication while maintaining async safety.

## Completed Work

### 1. Created EmbeddingCacheManager ✅
**File**: `src/codeweaver/providers/embedding/cache_manager.py` (NEW, ~220 lines)

Features implemented:
- Namespace isolation via `_get_namespace(provider_id, embedding_kind)`
- Async-safe locking with `asyncio.Lock` per namespace
- Lazy namespace initialization for batch/hash stores
- Three core async methods:
  - `deduplicate()`: Identifies unique chunks, returns hash mapping
  - `store_batch()`: Stores processed batch
  - `register_embeddings()`: Delegates to global registry
- Statistics tracking per namespace
- `clear_namespace()` for testing

### 2. Added DI Provider for Cache Manager ✅
**File**: `src/codeweaver/providers/dependencies.py`

Added:
```python
@dependency_provider(scope="singleton")
def _get_cache_manager(registry: EmbeddingRegistryDep = INJECTED):
    from codeweaver.providers.embedding.cache_manager import EmbeddingCacheManager
    return EmbeddingCacheManager(registry=registry)

type CacheManagerDep = Annotated[
    "EmbeddingCacheManager", depends(_get_cache_manager, use_cache=True, scope="singleton")
]
```

Updated `__all__` exports to include `CacheManagerDep`.

## In Progress: Refactoring BaseEmbeddingProvider

### Current Architecture Problems

**Per-Instance Stores (WRONG)**:
```python
# Lines 209-220 in base.py
_store: UUIDStore[list] = make_uuid_store(value_type=list, size_limit=ONE_MB * 3)
_hash_store: BlakeStore[UUID7] = make_blake_store(value_type=UUID, size_limit=ONE_KB * 256)

# Lines 255-260 in __init__
store_kwargs = kwargs.get("store_kwargs", {"value_type": list, "size_limit": ONE_MB * 3})
object.__setattr__(self, "_store", make_uuid_store(**store_kwargs))
hash_store_kwargs = kwargs.get("hash_store_kwargs", {"value_type": UUID, "size_limit": ONE_KB * 256})
object.__setattr__(self, "_hash_store", make_blake_store(**hash_store_kwargs))
```

**Issues**:
1. Each provider instance creates own stores → NO cross-instance deduplication
2. ClassVar pattern causes state issues with multiple instances
3. Threading locks in stores → blocks async event loop
4. No namespace isolation → dense/sparse collisions possible

### Required Changes

#### Task 1: Update __init__ Signature ⏳

**File**: `src/codeweaver/providers/embedding/providers/base.py`
**Method**: `EmbeddingProvider.__init__` (lines 227-264)

**Current**:
```python
def __init__(
    self,
    client: EmbeddingClient,
    config: EmbeddingProviderSettings,
    registry: EmbeddingRegistry,
    caps: EmbeddingModelCapabilities | None = None,
    impl_deps: EmbeddingImplementationDeps = None,
    custom_deps: EmbeddingCustomDeps = None,
    **kwargs: Any,
) -> None:
```

**New**:
```python
def __init__(
    self,
    client: EmbeddingClient,
    config: EmbeddingProviderSettings,
    registry: EmbeddingRegistry,
    cache_manager: CacheManagerDep,  # NEW
    caps: EmbeddingModelCapabilities | None = None,
    impl_deps: EmbeddingImplementationDeps = None,
    custom_deps: EmbeddingCustomDeps = None,
    **kwargs: Any,
) -> None:
```

**Implementation**:
```python
def __init__(
    self,
    client: EmbeddingClient,
    config: EmbeddingProviderSettings,
    registry: EmbeddingRegistry,
    cache_manager: CacheManagerDep,  # ADD
    caps: EmbeddingModelCapabilities | None = None,
    impl_deps: EmbeddingImplementationDeps = None,
    custom_deps: EmbeddingCustomDeps = None,
    **kwargs: Any,
) -> None:
    """Initialize the embedding provider."""
    defaults = getattr(self, "_defaults", {})
    object.__setattr__(self, "_model_dump_json", super().model_dump_json)
    object.__setattr__(self, "_circuit_state", CircuitBreakerState.CLOSED)
    object.__setattr__(self, "_failure_count", kwargs.get("failure_count", 0))
    object.__setattr__(self, "_last_failure_time", kwargs.get("last_failure_time"))
    object.__setattr__(
        self,
        "_circuit_open_duration",
        kwargs.get("circuit_open_duration", OPEN_CIRCUIT_DURATION),
    )
    object.__setattr__(self, "client", client)
    object.__setattr__(self, "config", config)
    object.__setattr__(self, "query_options", config.query if config and config.query else {})
    object.__setattr__(
        self, "embed_options", config.embedding if config and config.embedding else {}
    )
    object.__setattr__(self, "model_options", config.model if config and config.model else {})

    # REMOVE lines 255-260 (per-instance store initialization)
    # ADD cache manager setup
    object.__setattr__(self, "_cache_manager", cache_manager)

    # Compute namespace from provider ID + embedding kind
    provider_id = self.config.provider.variable if self.config.provider else "unknown"
    embedding_kind = "sparse" if isinstance(self, SparseEmbeddingProvider) else "dense"
    object.__setattr__(self, "_namespace", cache_manager._get_namespace(provider_id, embedding_kind))

    self._initialize(impl_deps, custom_deps)
    object.__setattr__(self, "caps", caps)
    object.__setattr__(self, "registry", registry)
    super().__init__(
        client=client,
        config=config,
        caps=caps,
        cache_manager=cache_manager,  # ADD
        **defaults
    )
```

**Also add field declarations** (after line 200):
```python
cache_manager: Annotated[
    "EmbeddingCacheManager",
    Field(
        description="Centralized cache manager for deduplication and batch storage",
        exclude=True,
    ),
]

_namespace: str = Field(
    description="Namespace for cache isolation (computed from provider_id.embedding_kind)",
    exclude=True,
)
```

**Remove** (lines 209-220):
```python
# DELETE these ClassVar fields:
_store: UUIDStore[list] = make_uuid_store(...)
_hash_store: BlakeStore[UUID7] = make_blake_store(...)
```

#### Task 2: Refactor _process_input to Use Cache Manager ⏳

**File**: `src/codeweaver/providers/embedding/providers/base.py`
**Method**: `_process_input` (lines 983-1033)

**Strategy**: Convert to async method, delegate deduplication to cache_manager

**Current Signature**:
```python
def _process_input(
    self,
    input_data: StructuredDataInput,
    *,
    is_old_batch: bool = False,
    skip_deduplication: bool = False,
) -> tuple[Iterator[CodeChunk], UUID7 | None]:
```

**New Signature**:
```python
async def _process_input(  # MAKE ASYNC
    self,
    input_data: StructuredDataInput,
    *,
    is_old_batch: bool = False,
    skip_deduplication: bool = False,
) -> tuple[list[CodeChunk], UUID7 | None]:  # Return list, not Iterator
```

**Implementation**:
```python
async def _process_input(
    self,
    input_data: StructuredDataInput,
    *,
    is_old_batch: bool = False,
    skip_deduplication: bool = False,
) -> tuple[list[CodeChunk], UUID7 | None]:
    """Process input data for embedding with cache manager deduplication."""
    processed_chunks = default_input_transformer(input_data)
    if is_old_batch:
        return list(processed_chunks), None

    batch_id = uuid7()
    chunk_list = list(processed_chunks)

    if skip_deduplication:
        # No deduplication - store all chunks directly
        await self._cache_manager.store_batch(
            chunks=chunk_list,
            batch_id=batch_id,
            namespace=self._namespace,
        )
        return chunk_list, batch_id

    # Deduplicate via cache manager
    unique_chunks, hash_mapping = await self._cache_manager.deduplicate(
        chunks=chunk_list,
        namespace=self._namespace,
        batch_id=batch_id,
    )

    # Add batch keys to unique chunks
    is_sparse_provider = isinstance(self, SparseEmbeddingProvider)
    final_chunks = [
        chunk.set_batch_keys(BatchKeys(id=batch_id, idx=i, sparse=is_sparse_provider))
        for i, chunk in enumerate(unique_chunks)
    ]

    # Store batch via cache manager
    await self._cache_manager.store_batch(
        chunks=final_chunks,
        batch_id=batch_id,
        namespace=self._namespace,
    )

    return final_chunks, batch_id
```

**Cascade Changes**: All callers of `_process_input` must now be async or await the call:
- `embed_documents()` (already async) - add `await`
- Any other internal methods calling `_process_input`

#### Task 3: Update _register_chunks ⏳

**File**: `src/codeweaver/providers/embedding/providers/base.py`
**Method**: `_register_chunks`

**Find the method** (search for `def _register_chunks`):
```python
def _register_chunks(
    self,
    chunks: Sequence[CodeChunk],
    batch_id: UUID7,
    embeddings: Sequence[list[float] | SparseEmbedding],
) -> None:
    """Register chunks with embeddings in the registry."""
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_info = EmbeddingBatchInfo.create_dense(
            batch_id=batch_id,
            batch_index=i,
            chunk_id=chunk.chunk_id,
            model=self.model_name,
            embeddings=embedding,
            dtype=self.get_datatype()
        )
        # OLD: self.registry.register_chunk_embedding(chunk.chunk_id, chunk_info)
        # NEW: Use cache manager
```

**Make it async**:
```python
async def _register_chunks(
    self,
    chunks: Sequence[CodeChunk],
    batch_id: UUID7,
    embeddings: Sequence[list[float] | SparseEmbedding],
) -> None:
    """Register chunks with embeddings via cache manager."""
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
        await self._cache_manager.register_embeddings(
            chunk_id=chunk.chunk_id,
            embedding_info=chunk_info,
        )
```

**Update all callers** to await this method (likely in `embed_documents`).

#### Task 4: Update clear_deduplication_stores ⏳

**File**: `src/codeweaver/providers/embedding/providers/base.py`
**Method**: `clear_deduplication_stores` (lines 281-287)

**Current**:
```python
def clear_deduplication_stores(self) -> None:
    """Clear class-level deduplication stores."""
    self._store = make_uuid_store(value_type=list, size_limit=ONE_MB * 3)
    self._hash_store = make_blake_store(value_type=UUID, size_limit=ONE_KB * 256)
```

**New**:
```python
def clear_deduplication_stores(self) -> None:
    """Clear namespace-isolated deduplication stores."""
    self._cache_manager.clear_namespace(self._namespace)
```

#### Task 5: Update Provider Factory Functions ⏳

**File**: `src/codeweaver/providers/dependencies.py`
**Functions**: `_get_embedding_provider_for_config`, `_get_sparse_embedding_provider_for_config`

**Current** (`_get_embedding_provider_for_config`, line ~600):
```python
def _get_embedding_provider_for_config(
    config: EmbeddingProviderSettings, registry: EmbeddingRegistryDep = INJECTED
) -> EmbeddingProvider:
    """Helper to get the embedding provider settings from config."""
    capabilities = config.embedding_config.capabilities
    provider = config.client.embedding_provider
    # ... provider resolution ...
    client = config.get_client()
    return resolved_provider(client=client, registry=registry, caps=capabilities, config=config)
```

**New**:
```python
def _get_embedding_provider_for_config(
    config: EmbeddingProviderSettings,
    registry: EmbeddingRegistryDep = INJECTED,
    cache_manager: CacheManagerDep = INJECTED,  # ADD
) -> EmbeddingProvider:
    """Helper to get the embedding provider settings from config."""
    capabilities = config.embedding_config.capabilities
    provider = config.client.embedding_provider
    # ... provider resolution ...
    client = config.get_client()
    return resolved_provider(
        client=client,
        registry=registry,
        cache_manager=cache_manager,  # ADD
        caps=capabilities,
        config=config
    )
```

**Same for `_get_sparse_embedding_provider_for_config`**.

Also update the signature for `_create_embedding_provider` and `_create_sparse_embedding_provider`:
```python
@dependency_provider(EmbeddingProvider, scope="singleton")
def _create_embedding_provider(
    config: EmbeddingProviderSettingsDep = INJECTED,
    registry: EmbeddingRegistryDep = INJECTED,
    cache_manager: CacheManagerDep = INJECTED,  # ADD
) -> EmbeddingProvider:
    return _get_embedding_provider_for_config(config, registry, cache_manager)  # PASS
```

### SparseEmbeddingProvider Updates

**File**: Same file, `SparseEmbeddingProvider` class (lines 1099-1156)

**Problem**: SparseEmbeddingProvider has its own `_batch_and_key` override that directly accesses `self._hash_store` and `self._store`.

**Solution**: This method will be **REMOVED** entirely. The base class `_process_input` (now async) handles everything via cache manager with namespace isolation. The `is_sparse_provider` check ensures sparse providers get `sparse=True` in their BatchKeys.

**Delete** lines 1111-1143:
```python
# DELETE THIS ENTIRE METHOD
def _batch_and_key(...):
    ...
```

The SparseEmbeddingProvider will automatically use the base `_process_input` which now handles namespace isolation correctly.

## Testing Plan

### Unit Tests for EmbeddingCacheManager
**File**: `tests/unit/providers/embedding/test_cache_manager.py` (NEW)

Tests to write:
1. `test_namespace_generation()`: Verify namespace format
2. `test_deduplication_basic()`: Unique chunks identified correctly
3. `test_deduplication_duplicates()`: Duplicates filtered
4. `test_namespace_isolation()`: Dense and sparse don't collide
5. `test_cross_instance_deduplication()`: Same namespace, different instances
6. `test_async_safety()`: Concurrent operations don't race
7. `test_statistics_tracking()`: Hits/misses tracked correctly
8. `test_clear_namespace()`: Namespace clearing works

### Integration Test Updates
**Files**: Various test files using embedding providers

Update fixtures:
```python
# OLD
@pytest.fixture
def embedding_provider(registry):
    return VoyageEmbeddingProvider(
        client=...,
        registry=registry,
        caps=...,
        config=...,
    )

# NEW
@pytest.fixture
def cache_manager(registry):
    from codeweaver.providers.embedding.cache_manager import EmbeddingCacheManager
    return EmbeddingCacheManager(registry=registry)

@pytest.fixture
def embedding_provider(registry, cache_manager):
    return VoyageEmbeddingProvider(
        client=...,
        registry=registry,
        cache_manager=cache_manager,  # ADD
        caps=...,
        config=...,
    )
```

## Validation Checklist

- [ ] All provider __init__ signatures updated
- [ ] Cache manager injected via DI
- [ ] _process_input converted to async
- [ ] _register_chunks converted to async
- [ ] All callers of async methods updated with await
- [ ] SparseEmbeddingProvider._batch_and_key deleted
- [ ] clear_deduplication_stores uses cache_manager
- [ ] Provider factories inject cache_manager
- [ ] Unit tests for cache manager written
- [ ] Integration test fixtures updated
- [ ] All tests pass
- [ ] Type checking passes (mise run check)
- [ ] Linting passes (mise run lint)
- [ ] Performance benchmark shows 10-20x improvement

## Expected Outcomes

**Performance**:
- 10-20x speedup from Phase 1 O(n) and O(n²) fixes
- No additional overhead from async locking (asyncio.Lock is efficient)

**Architecture**:
- True cross-instance deduplication
- Namespace isolation prevents collisions
- Async-safe operations (no event loop blocking)
- Simplified provider code (delegates to cache manager)

**Code Quality**:
- Removed ~80 lines from base.py (_process_input simplified)
- Removed ~30 lines from sparse provider
- Added ~200 lines (cache_manager.py)
- Net: -20 lines in production code
- Cleaner separation of concerns

## Rollback Plan

If issues arise:
1. Revert to commit before Phase 4
2. All Phase 1-3 changes are safe (already committed)
3. Cache manager is additive (can be disabled)

**Feature flag approach** (if needed):
```python
USE_CACHE_MANAGER = os.getenv("CODEWEAVER_USE_CACHE_MANAGER", "true").lower() == "true"

if USE_CACHE_MANAGER:
    # New cache manager path
else:
    # Old per-instance stores path
```

## Next Steps

1. Complete Task 1: Update __init__ signature ⏳
2. Complete Task 2: Refactor _process_input ⏳
3. Complete Task 3: Update _register_chunks ⏳
4. Complete Task 4: Update clear_deduplication_stores ⏳
5. Complete Task 5: Update provider factories ⏳
6. Complete Task 6: Write unit tests ⏳
7. Complete Task 7: Update test fixtures ⏳
8. Run validation suite
9. Performance benchmark
10. Commit Phase 4 changes

## Time Estimate

- Tasks 1-5: 2-3 hours (core implementation)
- Tasks 6-7: 1-2 hours (testing)
- Validation: 30 minutes
- Buffer: 30 minutes
- **Total**: 4-6 hours

**Status**: Started 2026-01-28, Task 1 in progress

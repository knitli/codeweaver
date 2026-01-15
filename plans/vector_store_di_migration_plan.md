<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Vector Store Provider DI Migration Plan

## Executive Summary

This migration applies the same DI patterns from reranking/embedding providers to vector store providers, but requires careful handling of several complex areas:

1. **Backup Logic Removal**: Currently extensive `for_backup` parameters and branching - needs elimination
2. **Collection Construction**: Currently in providers, may need architectural rethinking for multi-vector future
3. **Config Overlap**: `_BaseQdrantVectorStoreProviderSettings` + `CollectionMetadata` both generate collection configs
4. **Multiple Embedding Support**: `EmbeddingCapabilityGroup` exists but may not be flexible enough for future multi-vector
5. **Broken References**: `_embedding_caps` and `embedding_caps` references need updating

## Current State Analysis

### 1. Constructor Pattern

**Current** (`VectorStoreProvider` base class):
```python
def __init__(
    self,
    client: VectorStoreClient,
    config: VectorStoreProviderSettings,
    capabilities: EmbeddingCapabilityGroup,  # Note: NOT caps!
    **kwargs: Any,
) -> None:
```

**Issues**:
- Uses `capabilities` instead of `caps` (inconsistent with other providers)
- Has `embedding_caps` parameter handling after `super().__init__()` with complex lock logic
- Comments about PrivateAttr factory behavior suggest fragile initialization

### 2. Backup Logic Distribution

**Found `for_backup` usage in**:
- `base.py`: `_upsert_with_retry`, `upsert` signature
- `qdrant_base.py`: `_generate_metadata`, `_ensure_collection`, `_create_payload`, `_chunks_to_points`, `upsert`
- `inmemory.py`: `upsert` override

**Pattern**: Throughout the codebase, `for_backup` parameter threads through:
- Metadata generation (changes dense model, sparse model, dimension, collection name)
- Collection creation
- Payload creation
- Upsert operations

**Current backup differentiation**:
- Different embedding models (`backup_dense`, `backup_sparse` from `_embedding_caps`)
- Different collection names (`.endswith("backup")`)
- Different dimensions (256 for backup vs config dimension for primary)
- Payload flag: `is_backup: bool` field

### 3. Collection Construction Location

**Currently** in `QdrantBaseProvider._ensure_collection()`:
```python
await self._client.create_collection(
    **self._generate_metadata(for_backup=for_backup, collection_name=collection_name).to_collection()
)
```

**Two paths for collection config**:
1. **`_generate_metadata()` → `CollectionMetadata`** (lines 108-183 in qdrant_base.py)
   - Uses provider settings + `_embedding_caps`
   - Generates `vector_config` and `sparse_config`
   - Has `for_backup` branching logic

2. **`CollectionMetadata.to_collection()`** (metadata.py lines 84-98)
   - Converts metadata to collection creation args
   - Excludes metadata fields, returns just config dicts

**Overlap concerns**:
- `_BaseQdrantVectorStoreProviderSettings` (in config/kinds.py)
- `CollectionMetadata` both have logic for generating vector configs

### 4. EmbeddingCapabilityGroup Structure

**Definition** (providers/types.py lines 239-276):
```python
class EmbeddingCapabilityGroup(NamedTuple):
    dense: ConfiguredCapability | None = None
    sparse: ConfiguredCapability | None = None
    idf: ConfiguredCapability | None = None
    late_interaction: None = None  # Placeholder for future
```

**Current usage**:
- Passed to vector store provider constructor
- Stored in `_embedding_caps` (which has broken references)
- Used in `_generate_metadata` for backup logic: `self._embedding_caps["backup_dense"]`, `self._embedding_caps["backup_sparse"]`

**Problems**:
- Designed for current sparse+dense hybrid search
- Not flexible for future multi-vector scenarios (multiple dense, multiple sparse, ColBERT, etc.)
- Hardcoded backup access patterns suggest tight coupling

### 5. Dependencies.py Factory Structure

**Current vector store factories** (lines 935-1008):
```python
def _get_vector_store_provider_for_config(
    config: QdrantVectorStoreProviderSettings | MemoryVectorStoreProviderSettings,
) -> QdrantVectorStoreProvider | MemoryVectorStoreProvider:
    client = _resolve_client(config.client)
    provider = config.client.vector_store_provider
    resolved_provider = provider._resolve()
    client = _instantiate_client(client, config.client_options)
    return resolved_provider(client=client, config=config)  # Missing capabilities!
```

**Issues**:
- No `caps` parameter passed (unlike embedding/reranking)
- No `EmbeddingCapabilityGroup` construction
- Backup factory follows same pattern

## Migration Challenges

### Challenge 1: Backup Logic Removal

**Current approach**: Single provider class with `for_backup` parameter controlling behavior

**Target approach**: Multiple provider instances, no backup differentiation logic

**Decision needed**:
- Keep collection name differentiation? (YES - still useful for organization)
- Keep dimension differentiation? (MAYBE - depends on whether backup uses same models)
- Keep `is_backup` payload field? (MAYBE - useful for debugging/filtering)

**Recommendation**:
- Remove `for_backup` parameter entirely
- Each provider instance has ONE collection, ONE set of embeddings
- Collection names determined by config, not by backup flag
- Payload `is_backup` field removed (no longer meaningful)

### Challenge 2: Collection Construction Architecture

**Current**: Provider constructs collections on-demand in `_ensure_collection()`

**Future need**: Multiple collections per provider for advanced search

**Options**:

**Option A: Keep construction in provider** (Current)
- ✅ Encapsulation: Provider owns its storage
- ✅ Simplicity: Works with current code
- ❌ Flexibility: Hard to add multiple collections
- ❌ Separation: Mixes storage management with search logic

**Option B: Extract to CollectionManager**
- ✅ Flexibility: Easy to manage multiple collections
- ✅ Separation: Clean boundaries
- ❌ Complexity: New abstraction layer
- ❌ Migration: More code to refactor

**Option C: Config-driven collection specification**
- ✅ Flexibility: Config lists multiple collections
- ✅ DI-friendly: Collections specified at config time
- ❌ Rigidity: Harder to create collections dynamically
- ❌ Config complexity: More complex config structure

**Recommendation**: **Option A for now, prepare for Option C**
- Keep construction in provider for Alpha 2
- Remove backup-specific logic
- Add `collections: dict[str, CollectionMetadata]` property to prepare for multiple collections
- Future work: Add collection management to config

### Challenge 3: Config Overlap Resolution

**Two sources of collection config**:
1. Provider settings → `_generate_metadata()` → `CollectionMetadata`
2. `CollectionMetadata.to_collection()` → dict for Qdrant

**Overlap analysis needed**:
- Find `_BaseQdrantVectorStoreProviderSettings` (in config/kinds.py)
- Compare what it generates vs `_generate_metadata()`
- Determine canonical source

**Recommendation**:
- **Investigate**: Search for vector store config generation methods
- **Consolidate**: Choose `CollectionMetadata` as canonical (it already exists)
- **Simplify**: Remove redundant generation in settings if it exists
- **Document**: Clear API for creating `CollectionMetadata` from config

### Challenge 4: EmbeddingCapabilityGroup Redesign

**Current limitations**:
- Fixed structure (dense, sparse, idf, late_interaction)
- Assumes one-of-each
- Backup logic hardcoded (`_embedding_caps["backup_dense"]`)

**Future needs**:
- Multiple dense embeddings (different dimensions, models)
- Multiple sparse embeddings
- ColBERT late interaction
- IDF/BM25 alongside others
- Dynamic composition

**Design options**:

**Option A: Extend current NamedTuple**
```python
class EmbeddingCapabilityGroup(NamedTuple):
    dense: Sequence[ConfiguredCapability] = ()  # Multiple dense
    sparse: Sequence[ConfiguredCapability] = ()  # Multiple sparse
    late_interaction: Sequence[ConfiguredCapability] = ()
    idf: ConfiguredCapability | None = None  # Still singleton
```

**Option B: Generic capability list**
```python
class EmbeddingCapabilityGroup(NamedTuple):
    capabilities: Sequence[ConfiguredCapability]

    def by_type(self, type: Literal["dense", "sparse", "idf", "late"]) -> Sequence[ConfiguredCapability]:
        ...

    def primary_dense(self) -> ConfiguredCapability: ...
    def primary_sparse(self) -> ConfiguredCapability: ...
```

**Option C: Strategy-based**
```python
class VectorSearchStrategy(NamedTuple):
    dense: Sequence[ConfiguredCapability]
    sparse: Sequence[ConfiguredCapability] | None
    late_interaction: ConfiguredCapability | None
    idf: ConfiguredCapability | None

    # Different strategies: DENSE_ONLY, HYBRID, MULTIVECTOR, etc.
```

**Recommendation**: **Option A for Alpha 2, Plan Option C for Alpha 3**
- Extend current structure to support sequences
- Maintain backward compatibility with single-element sequences
- Add `primary_dense()`, `primary_sparse()` helper methods
- Plan strategy-based redesign for when multi-vector is implemented

### Challenge 5: Reference Updates

**Broken references found**:
- `self._embedding_caps["backup_dense"]` (qdrant_base.py:153)
- `self._embedding_caps["backup_sparse"]` (qdrant_base.py:142)
- `self._embedding_caps.get("dense")` (qdrant_base.py:158)
- `embedding_caps` parameter (base.py:104)

**Required changes**:
1. Update `EmbeddingCapabilityGroup` to support the new access patterns
2. Remove backup-specific access (`backup_dense`, `backup_sparse`)
3. Change `embedding_caps` parameter to `caps` for consistency
4. Update all access patterns to use `caps.dense`, `caps.sparse`, etc.

## Implementation Plan

### Phase 1: Investigate & Document (Required Before Implementation)

#### 1.1 Find Vector Store Config Generation
- [ ] Search for `_BaseQdrantVectorStoreProviderSettings` or similar
- [ ] Search for `VectorConfig`, `SparseConfig` generation in config files
- [ ] Document all collection config generation paths

#### 1.2 Analyze Config Overlap
- [ ] Compare settings-based vs metadata-based config generation
- [ ] Identify redundant code
- [ ] Design consolidation approach

#### 1.3 Multi-Vector Architecture Design
- [ ] Review current search pipeline for multi-vector readiness
- [ ] Design collection-per-vector-type approach OR shared collection approach
- [ ] Document search strategy implications

### Phase 2: EmbeddingCapabilityGroup Enhancement

#### 2.1 Extend EmbeddingCapabilityGroup
- [ ] Change `dense` to `Sequence[ConfiguredCapability]`
- [ ] Change `sparse` to `Sequence[ConfiguredCapability]`
- [ ] Add `primary_dense()` helper method
- [ ] Add `primary_sparse()` helper method
- [ ] Add `all_dense()` method
- [ ] Add `all_sparse()` method

#### 2.2 Update Factory in dependencies.py
- [ ] Add `_create_embedding_capability_group()` factory function
- [ ] Construct group from all embedding configs (not just primary)
- [ ] Handle backward compatibility (single-element sequences)

#### 2.3 Update Type Annotations
- [ ] Fix `capabilities` → `caps` in base class
- [ ] Update all type hints
- [ ] Add `EmbeddingCapabilityGroupDep` type alias

### Phase 3: Remove Backup Logic

#### 3.1 Update Base Class (base.py)
- [ ] Remove `for_backup` parameter from `_upsert_with_retry`
- [ ] Remove `for_backup` parameter from `upsert` signature
- [ ] Update docstrings

#### 3.2 Update QdrantBaseProvider (qdrant_base.py)
- [ ] Remove `for_backup` parameter from `_generate_metadata`
- [ ] Remove backup-specific model selection logic
- [ ] Remove backup-specific dimension logic
- [ ] Remove `for_backup` parameter from `_ensure_collection`
- [ ] Remove `collection_name.endswith("backup")` check
- [ ] Remove `for_backup` parameter from `_create_payload`
- [ ] Remove `is_backup` field from `HybridVectorPayload`
- [ ] Remove `for_backup` parameter from `_chunks_to_points`
- [ ] Remove `for_backup` parameter from `upsert`

#### 3.3 Update MemoryVectorStoreProvider (inmemory.py)
- [ ] Remove `for_backup` parameter from `upsert` override

#### 3.4 Update CollectionMetadata (metadata.py)
- [ ] Remove `is_backup` field
- [ ] Remove backup-related validation logic
- [ ] Update docstrings

### Phase 4: Refactor Constructors

#### 4.1 Update VectorStoreProvider Base
```python
def __init__(
    self,
    client: VectorStoreClient,
    config: VectorStoreProviderSettings,
    caps: EmbeddingCapabilityGroup,  # Changed from capabilities
    **kwargs: Any,
) -> None:
    """Initialize the vector store provider."""
    # Simplified initialization, no embedding_caps override logic
    super().__init__(client=client, config=config, caps=caps, **kwargs)
```

#### 4.2 Update QdrantBaseProvider
- [ ] Update `__init__` if overridden
- [ ] Update `_generate_metadata` to use `self.caps` instead of `self._embedding_caps`
- [ ] Update dense/sparse model access patterns

#### 4.3 Update Concrete Implementations
- [ ] `QdrantVectorStoreProvider`: Simplify constructor
- [ ] `MemoryVectorStoreProvider`: Simplify constructor

### Phase 5: Update Factories in dependencies.py

#### 5.1 Add Capability Group Factory
```python
@dependency_provider(EmbeddingCapabilityGroup, scope="singleton")
def _create_embedding_capability_group(
    embedding_configs: AllEmbeddingConfigsDep = INJECTED,
    sparse_configs: AllSparseEmbeddingConfigsDep = INJECTED,
) -> EmbeddingCapabilityGroup:
    """Factory for creating embedding capability group from all configs."""
    # Construct ConfiguredCapability for each config
    # Build EmbeddingCapabilityGroup with sequences
    ...
```

#### 5.2 Update Vector Store Factories
```python
def _get_vector_store_provider_for_config(
    config: VectorStoreProviderSettings,
    caps: EmbeddingCapabilityGroupDep = INJECTED,  # NEW
) -> VectorStoreProvider:
    client = _resolve_client(config.client)
    provider = config.client.vector_store_provider
    resolved_provider = provider._resolve()
    client = _instantiate_client(client, config.client_options)
    return resolved_provider(client=client, config=config, caps=caps)  # Added caps
```

#### 5.3 Remove Backup Factory Differentiation
- [ ] Keep backup config factory for DI type system
- [ ] Remove any backup-specific provider construction logic
- [ ] Both primary and backup use same provider class, different configs

### Phase 6: Config Consolidation

#### 6.1 Consolidate Collection Config Generation
- [ ] Make `CollectionMetadata` the canonical source
- [ ] Remove redundant generation from settings (if it exists)
- [ ] Add factory method: `CollectionMetadata.from_config(config, caps)`

#### 6.2 Simplify _generate_metadata
- [ ] Reduce to simple delegation to `CollectionMetadata.from_config`
- [ ] Or move logic directly into config if appropriate

### Phase 7: Update Tests

#### 7.1 Unit Tests
- [ ] Update all vector store provider tests
- [ ] Add mock `caps` fixture
- [ ] Remove `for_backup` test cases
- [ ] Update constructor call patterns

#### 7.2 Integration Tests
- [ ] Update vector store integration tests
- [ ] Test multiple provider instances
- [ ] Test collection management

### Phase 8: Documentation & Cleanup

#### 8.1 Update Documentation
- [ ] Update provider initialization docs
- [ ] Document multi-provider pattern
- [ ] Update collection management docs

#### 8.2 Progress Tracking
- [ ] Create `vector_store_di_migration_progress.md`
- [ ] Track completed phases

## Open Questions

### Q1: Collection Config Source of Truth
**Question**: Should collection configuration live in:
- A) Settings (`VectorStoreProviderSettings`)
- B) Provider logic (`_generate_metadata`)
- C) Separate metadata class (`CollectionMetadata`)

**Impact**: Affects where users specify dimensions, distance metrics, etc.

**Recommendation**: **C** - `CollectionMetadata` as canonical, generated from settings+caps

### Q2: Multiple Collections Architecture
**Question**: How should multiple collections be managed?
- A) Single provider, multiple methods (`.collection("name")`)
- B) Multiple provider instances (current approach scaled)
- C) Separate CollectionManager class

**Impact**: Affects future multi-vector search implementation

**Recommendation**: **B for now** - Multiple providers (via DI). Plan **A** for future when multi-vector is implemented.

### Q3: EmbeddingCapabilityGroup Backward Compatibility
**Question**: Should we maintain exact backward compatibility with single-element access?
- A) Yes - keep `caps.dense` returning single capability, add `caps.all_dense()` for sequence
- B) No - breaking change, `caps.dense` returns sequence, add `caps.primary_dense()` for single

**Impact**: Affects existing code that accesses `caps.dense`

**Recommendation**: **B** - Accept breaking change for cleaner future API

### Q4: Payload is_backup Field
**Question**: Should we keep `is_backup: bool` field in `HybridVectorPayload`?
- A) Remove - no longer meaningful without backup differentiation
- B) Keep - useful for debugging/filtering

**Impact**: Affects stored data structure and queries

**Recommendation**: **A** - Remove for simplicity. Collection name provides sufficient differentiation if needed.

### Q5: Collection Metadata Validation
**Question**: Should `CollectionMetadata.validate_compatibility()` be:
- A) Removed - not needed without backup switching
- B) Kept - still useful for detecting config drift
- C) Enhanced - add more validation checks

**Impact**: Affects error detection and user experience

**Recommendation**: **B** - Keep for config drift detection (model changes, dimension changes, etc.)

## Risk Assessment

### High Risk
1. **Collection Config Consolidation**: May reveal hidden dependencies
2. **EmbeddingCapabilityGroup Redesign**: Breaking change affecting search pipeline

### Medium Risk
1. **Backup Logic Removal**: Extensive but straightforward refactoring
2. **Constructor Changes**: Well-established pattern from reranking/embedding

### Low Risk
1. **Factory Updates**: Proven pattern, clear implementation
2. **Test Updates**: Mechanical changes following provider patterns

## Success Criteria

- [ ] All vector store providers follow same DI pattern as reranking/embedding
- [ ] No `for_backup` parameters anywhere in vector store code
- [ ] `EmbeddingCapabilityGroup` supports multiple embeddings per type
- [ ] Collection configuration has single source of truth
- [ ] All tests pass with new patterns
- [ ] Documentation updated
- [ ] No broken references to `embedding_caps` or `_embedding_caps`

## Timeline Estimate

**Phase 1-2 (Investigation + Design)**: 1-2 sessions
**Phase 3-5 (Implementation)**: 2-3 sessions
**Phase 6-8 (Testing + Documentation)**: 1-2 sessions

**Total**: 4-7 working sessions

## Notes for Implementation

1. **Start with Phase 1**: DO NOT skip investigation - we need to find config generation code
2. **Phase 2 before Phase 3**: Fix `EmbeddingCapabilityGroup` before removing backup logic
3. **Test after each phase**: Don't batch all changes
4. **Keep migration log**: Document decisions and issues in progress file

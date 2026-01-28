<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Embedding Types Strategic Analysis

**Date**: 2026-01-23
**Purpose**: Strategic analysis of embedding-related types and vector handling architecture
**Status**: Analysis Complete - Recommendations Ready

---

## Executive Summary

The CodeWeaver embedding architecture has **already been partially refactored** to support dynamic, intent-driven embeddings. The core types (`ChunkEmbeddings`, `CodeChunk`) use `dict[str, ...]` structures as specified in the failover plan. However, **key coordination components are missing**:

1. ✅ **Core Types Refactored** - Dynamic dictionaries implemented
2. ❌ **VectorNames Missing** - No intent → physical name resolution
3. ❌ **EmbeddingStrategy Missing** - No unified configuration for what to generate
4. ✅ **Failover Service Exists** - But operates at service level, not data level
5. ⚠️ **Provider Updates Needed** - Hardcoded "dense"/"sparse" names in `_prepare_vectors`

**Key Insight**: This isn't primarily a type problem - it's a **configuration and coordination problem**. The types support the architecture, but the orchestration layer is incomplete.

---

## Current Type Architecture

### Core Embedding Types (Already Refactored ✅)

```python
# src/codeweaver/core/types/embeddings.py

class ChunkEmbeddings(BasedModel):
    """Dynamic dictionary supporting arbitrary intents."""
    embeddings: dict[str, EmbeddingBatchInfo]  # ✅ Already dynamic
    chunk: CodeChunk

class EmbeddingBatchInfo(BasedModel):
    """Embedding metadata + actual vectors."""
    batch_id: UUID7
    batch_index: int
    kind: EmbeddingKind  # DENSE or SPARSE
    chunk_id: UUID7
    model: ModelNameT
    embeddings: StoredEmbeddingVectors | SparseEmbedding
    dimension: int
    dtype: Literal["float32", "float16", "int8", "binary"]
```

### CodeChunk Structure (Already Refactored ✅)

```python
# src/codeweaver/core/chunks.py

class CodeChunk(BasedModel):
    # ... core fields ...
    _embeddings: dict[str, BatchKeys]  # ✅ Already dynamic

    @property
    def embeddings(self) -> dict[str, BatchKeys]:
        return self._embeddings

    @property
    def dense_batch_key(self) -> BatchKeys | None:
        return self._embeddings.get("primary")  # Still uses "primary" convention
```

### Reference Type (Lightweight, Good Design ✅)

```python
class BatchKeys(NamedTuple):
    """Lightweight reference to batch embeddings."""
    id: UUID7  # batch ID
    idx: int   # index within batch
    sparse: bool = False
```

### Supporting Types (Domain Models ✅)

```python
class EmbeddingKind(BaseEnum):
    DENSE = "dense"
    SPARSE = "sparse"

class SparseEmbedding(NamedTuple):
    indices: Sequence[int]
    values: Sequence[float]

class EmbeddingModelInfo(NamedTuple):
    """Configuration-level model info."""
    dense: ModelNameT | None
    sparse: ModelNameT | None
    backup_dense: ModelNameT | None
    backup_sparse: ModelNameT | None
```

---

## Critical Missing Components

### 1. VectorNames Resolution (High Priority ❌)

**Purpose**: Map logical intents to physical Qdrant vector names

**Required Implementation**:
```python
# NEW FILE: src/codeweaver/providers/vector_stores/vector_names.py

class VectorNames(BasedModel):
    """Maps intent keys to physical vector names in Qdrant.

    Example:
        "primary" → "voyage_large_2" (physical vector name in Qdrant)
        "backup" → "jina_embed_v3"
        "sparse" → "bm25_sparse"
    """
    mapping: dict[str, str]

    def resolve(self, intent: str) -> str:
        """Get physical vector name for intent."""
        return self.mapping.get(intent, intent)

    @classmethod
    def from_config(cls, embedding_config: EmbeddingStrategy) -> VectorNames:
        """Generate mapping from embedding strategy."""
        mapping = {}
        if embedding_config.primary_dense:
            # Convert model name to vector name convention
            mapping["primary"] = _model_to_vector_name(embedding_config.primary_dense)
        if embedding_config.sparse:
            mapping["sparse"] = _model_to_vector_name(embedding_config.sparse)
        if embedding_config.backup_dense:
            mapping["backup"] = _model_to_vector_name(embedding_config.backup_dense)
        return cls(mapping=mapping)
```

**Used By**:
- `QdrantBaseProvider._prepare_vectors()` - to construct named vector dict
- `QdrantBaseProvider._validate_collection_config()` - to check schema consistency
- Search logic - to select which vectors to query

### 2. EmbeddingStrategy Configuration (High Priority ❌)

**Purpose**: Declare which embeddings to generate (replaces hardcoded logic)

**Required Implementation**:
```python
# NEW FILE: src/codeweaver/engine/config/embedding_strategy.py

class EmbeddingStrategy(BasedModel):
    """Configuration for which embeddings to generate.

    Determines:
    1. Which intents are active
    2. Which models to use for each intent
    3. When to enable backup embeddings
    """
    primary_dense: ModelNameT
    sparse: ModelNameT
    backup_dense: ModelNameT | None = None
    backup_sparse: ModelNameT | None = None

    def enabled_intents(self) -> set[str]:
        """Return active intent keys."""
        intents = {"primary", "sparse"}
        if self.backup_dense:
            intents.add("backup")
        if self.backup_sparse:
            intents.add("backup_sparse")
        return intents

    def requires_backup(self) -> bool:
        """Check if backup embeddings should be generated."""
        return self.backup_dense is not None
```

**Used By**:
- `EmbeddingService` - to know which embedding passes to run
- `VectorNames.from_config()` - to build intent → name mapping
- Validation logic - to ensure consistency

### 3. VectorIntent Enum (Medium Priority ⚠️)

**Purpose**: Standardize intent naming (prevent typos, enable validation)

**Required Implementation**:
```python
# MODIFY: src/codeweaver/core/types/embeddings.py

class VectorIntent(BaseEnum):
    """Standard intent names for embeddings."""
    PRIMARY = "primary"
    SPARSE = "sparse"
    BACKUP = "backup"
    BACKUP_SPARSE = "backup_sparse"
    # Future extensibility:
    SUMMARY = "summary"
    AST = "ast"
    CUSTOM = "custom"
```

**Benefits**:
- Type-safe intent names
- IDE autocomplete
- Validation at ChunkEmbeddings.add()
- Clear documentation

---

## Provider Implementation Issues

### Current QdrantBaseProvider._prepare_vectors() (❌ Hardcoded)

```python
# src/codeweaver/providers/vector_stores/qdrant_base.py:492

def _prepare_vectors(self, chunk: CodeChunk) -> dict[str, Any]:
    vectors: dict[str, Any] = {}
    if chunk.dense_embeddings:
        vectors["dense"] = list(dense_info.embeddings)  # ❌ Hardcoded "dense"
    if sparse_info := chunk.sparse_embeddings:
        # ... sparse handling ...
        pass
    if not sparse_info:
        vectors["sparse"] = Document(text=chunk.content, model="qdrant/bm25")  # ❌ Hardcoded "sparse"
    return vectors
```

### Required Refactor (✅ Dynamic)

```python
def _prepare_vectors(self, chunk: CodeChunk) -> dict[str, Any]:
    """Prepare vectors dynamically from chunk embeddings."""
    from codeweaver.providers.embedding.registry import embedding_registry

    vectors: dict[str, Any] = {}

    # Iterate over all embeddings in chunk
    for intent, batch_key in chunk.embeddings.items():
        # Get physical vector name for this intent
        vector_name = self.vector_names.resolve(intent)

        # Retrieve actual embedding data from registry
        embedding_info = embedding_registry.get(batch_key)

        if embedding_info.is_dense:
            vectors[vector_name] = list(embedding_info.embeddings)
        elif embedding_info.is_sparse:
            # Handle sparse vector conversion
            vectors[vector_name] = self._prepare_sparse_vector_data(
                embedding_info.embeddings
            )

    # BM25 fallback only if no sparse embeddings at all
    if not any(info.is_sparse for info in vectors.values()):
        vectors["sparse"] = Document(text=chunk.content, model="qdrant/bm25")

    return vectors
```

---

## Data Flow Analysis

### Current Flow (Partially Dynamic ⚠️)

```
1. Chunking → CodeChunk created
2. EmbeddingService → Generates embeddings
   └─ Creates EmbeddingBatchInfo for each intent
   └─ Stores in ChunkEmbeddings registry
   └─ Stores BatchKeys in CodeChunk._embeddings dict ✅
3. VectorStoreProvider.upsert()
   └─ Calls _prepare_vectors(chunk)
   └─ ❌ Uses hardcoded "dense"/"sparse" names
   └─ Creates Qdrant PointStruct
4. Qdrant Collection
   └─ Stores named vectors {"dense": [...], "sparse": {...}}
```

### Target Flow (Fully Dynamic ✅)

```
1. Configuration → EmbeddingStrategy defines intents
2. Initialization → VectorNames mapping created
3. Chunking → CodeChunk created
4. EmbeddingService → Reads EmbeddingStrategy
   └─ Generates embeddings for each enabled intent
   └─ Intent keys: "primary", "sparse", "backup" (from strategy)
5. VectorStoreProvider.upsert()
   └─ Calls _prepare_vectors(chunk)
   └─ ✅ Iterates chunk.embeddings dynamically
   └─ ✅ Maps intents → physical names via VectorNames
   └─ Creates Qdrant PointStruct
6. Qdrant Collection
   └─ Stores named vectors {"voyage_large_2": [...], "bm25_sparse": {...}, "jina_embed_v3": [...]}
```

---

## Hardcoded References Audit

**Found 68 occurrences** of "primary"/"backup"/"sparse" across 24 files.

### High Priority Files (Need Updates)

1. **`src/codeweaver/providers/vector_stores/qdrant_base.py`** (5 occurrences)
   - `_prepare_vectors()` - hardcoded "dense"/"sparse"
   - `_validate_collection_config()` - checks for "dense" vector
   - Need: VectorNames integration

2. **`src/codeweaver/core/chunks.py`** (6 occurrences)
   - Property accessors use "primary"/"sparse" literals
   - `set_batch_keys()` infers intent from sparse flag
   - Keep: Backward compat properties OK if dynamic dict is primary API

3. **`src/codeweaver/core/types/embeddings.py`** (11 occurrences)
   - Property accessors for models (dense_model, backup_dense_model, etc.)
   - Intent inference in add()/update()
   - Keep: These are convenience accessors, dynamic dict is source of truth

4. **`src/codeweaver/engine/services/indexing_service.py`**
   - Likely orchestrates embedding generation
   - Need: Update to use EmbeddingStrategy

5. **`src/codeweaver/engine/config/failover.py`**
   - Failover config (already reviewed)
   - Keep: Service-level failover, not data-level

### Low Priority (Configuration/Documentation)

- Config files, defaults, profiles - reference backup/primary conceptually
- These are OK - they define user-facing configuration

---

## Implementation Roadmap

### Phase 1: Foundational Types (Week 1)

**Priority**: High
**Dependencies**: None
**Breaking**: No (additive)

1. Create `VectorIntent` enum in `core/types/embeddings.py`
2. Create `VectorNames` class in `providers/vector_stores/vector_names.py`
3. Create `EmbeddingStrategy` in `engine/config/embedding_strategy.py`
4. Add validation in `ChunkEmbeddings.add()` using `VectorIntent`

**Deliverables**:
- New files with complete type definitions
- Unit tests for each new type
- Integration with existing config system

### Phase 2: Provider Updates (Week 2)

**Priority**: High
**Dependencies**: Phase 1
**Breaking**: No (internal implementation)

1. Add `vector_names: VectorNames` field to `QdrantBaseProvider`
2. Refactor `_prepare_vectors()` to use dynamic iteration
3. Update `_validate_collection_config()` to use `VectorNames`
4. Add `VectorNames.from_config()` factory method

**Deliverables**:
- Updated `QdrantBaseProvider` implementation
- Tests for dynamic vector construction
- Collection validation tests

### Phase 3: Service Layer (Week 3)

**Priority**: High
**Dependencies**: Phase 1, 2
**Breaking**: No (orchestration layer)

1. Update `EmbeddingService` to read `EmbeddingStrategy`
2. Modify embedding generation to iterate over enabled intents
3. Update `FailoverService` coordination (if needed)
4. Add reconciliation for arbitrary missing vectors

**Deliverables**:
- Updated embedding service
- Multi-intent embedding tests
- Failover integration tests

### Phase 4: Search & Retrieval (Week 4)

**Priority**: Medium
**Dependencies**: Phase 2
**Breaking**: No (enhancement)

1. Update search logic to use `VectorNames` for query construction
2. Implement multi-vector fallback (primary → backup → sparse)
3. Add hybrid search composition across multiple dense vectors
4. Update result scoring for multi-vector scenarios

**Deliverables**:
- Enhanced search capabilities
- Fallback logic tests
- Performance benchmarks

---

## Type Organization Strategy

### Current Structure
```
src/codeweaver/core/types/embeddings.py  (375 lines, all types)
```

### Recommended Structure
```
src/codeweaver/core/types/embeddings/
    __init__.py          # Re-exports for backward compatibility
    vectors.py           # RawEmbeddingVectors, StoredEmbeddingVectors, SparseEmbedding
    metadata.py          # EmbeddingBatchInfo, EmbeddingModelInfo
    references.py        # BatchKeys, ChunkEmbeddings
    kinds.py             # EmbeddingKind, DataType
    resolution.py        # VectorIntent (NEW)

src/codeweaver/providers/vector_stores/
    vector_names.py      # VectorNames (NEW)

src/codeweaver/engine/config/
    embedding_strategy.py # EmbeddingStrategy (NEW)
```

**Benefits**:
- Clear separation of concerns
- Easier to navigate and understand
- Logical grouping by purpose
- No breaking changes (re-export from `__init__.py`)

---

## Testing Strategy

### Unit Tests

1. **Type Tests**
   - `test_vector_intent_enum.py` - VectorIntent values and validation
   - `test_vector_names.py` - Mapping and resolution logic
   - `test_embedding_strategy.py` - Intent enablement, validation

2. **Provider Tests**
   - `test_qdrant_dynamic_vectors.py` - Dynamic vector construction
   - `test_vector_name_resolution.py` - Intent → name mapping in provider

3. **Service Tests**
   - `test_multi_intent_embedding.py` - Generate multiple intents
   - `test_strategy_driven_embedding.py` - Strategy configuration

### Integration Tests

1. **End-to-End Flow**
   - `test_dynamic_failover_flow.py` - Complete failover with dynamic vectors
   - `test_multi_vector_search.py` - Search across multiple vector types
   - `test_backup_reconciliation.py` - Sync backup with missing intents

2. **Configuration Tests**
   - `test_strategy_validation.py` - Config consistency checks
   - `test_vector_name_generation.py` - Auto-generation from models

---

## Risks & Mitigations

### Risk 1: Backward Compatibility

**Issue**: Existing code uses `chunk.dense_batch_key` accessors
**Mitigation**: Keep property accessors as convenience API over dynamic dict
**Status**: Low risk - accessors are thin wrappers

### Risk 2: Collection Schema Mismatch

**Issue**: Existing Qdrant collections use "dense"/"sparse" names
**Mitigation**: `_validate_collection_config()` auto-updates mapping OR requires reindex
**Status**: Medium risk - needs migration path

### Risk 3: Performance Impact

**Issue**: Dynamic iteration vs. direct access
**Mitigation**: Dictionary lookup is O(1), minimal overhead; batch operations unchanged
**Status**: Low risk - negligible performance impact

### Risk 4: Type Proliferation

**Issue**: Adding more types increases complexity
**Mitigation**: Organize into logical modules, clear naming, comprehensive docs
**Status**: Low risk - improves architecture clarity

---

## Recommendations

### Immediate Actions (This Week)

1. ✅ **Complete This Analysis** - Document current state
2. 🔴 **Create VectorNames type** - Highest priority missing piece
3. 🔴 **Create EmbeddingStrategy type** - Configuration foundation
4. 🟡 **Audit QdrantBaseProvider** - Identify all hardcoded references

### Short-Term (Next 2 Weeks)

1. **Refactor `_prepare_vectors()`** - Dynamic vector construction
2. **Update EmbeddingService** - Strategy-driven generation
3. **Add VectorIntent enum** - Standardize naming
4. **Write integration tests** - Multi-intent flow coverage

### Long-Term (4+ Weeks)

1. **Enhance search logic** - Multi-vector fallback
2. **Optimize reconciliation** - Arbitrary intent sync
3. **Add telemetry** - Track vector usage patterns
4. **Documentation** - User guide for intent configuration

---

## Success Criteria

### Phase 1 Complete When:
- [ ] VectorIntent, VectorNames, EmbeddingStrategy types implemented
- [ ] Unit tests passing (90%+ coverage)
- [ ] Integration with config system working
- [ ] No breaking changes to existing APIs

### Phase 2 Complete When:
- [ ] `QdrantBaseProvider` uses dynamic vector construction
- [ ] No hardcoded "dense"/"sparse" in vector operations
- [ ] Collection validation works with arbitrary vector names
- [ ] Tests verify dynamic behavior

### Phase 3 Complete When:
- [ ] EmbeddingService generates intents from strategy
- [ ] Failover works with dynamic embeddings
- [ ] Reconciliation handles arbitrary missing vectors
- [ ] End-to-end tests passing

### Full Implementation Complete When:
- [ ] Search supports multi-vector fallback
- [ ] All 68 hardcoded references reviewed/updated
- [ ] Performance benchmarks show <5% overhead
- [ ] Documentation updated
- [ ] User stories validated

---

## Appendices

### A. Type Dependency Graph

```
VectorIntent (enum)
    ↓
EmbeddingKind (enum) → EmbeddingBatchInfo → ChunkEmbeddings
    ↓                          ↓                  ↓
BatchKeys ←─────────────────────────────── CodeChunk
    ↑
SparseEmbedding

EmbeddingStrategy → VectorNames → QdrantBaseProvider
```

### B. Configuration Example

```toml
# codeweaver.toml

[embedding.strategy]
primary_dense = "voyage-large-2-instruct"
sparse = "Alibaba-NLP/gte-multilingual-mlm-base"
backup_dense = "jinaai/jina-embeddings-v3"
# backup_sparse not typically needed

[vector_store.vector_names]
# Auto-generated from strategy, can override:
# primary = "voyage_large_2"
# sparse = "bm25_sparse"
# backup = "jina_embed_v3"
```

### C. Key Files Reference

| Component | File Path | Status |
|-----------|-----------|--------|
| ChunkEmbeddings | `core/types/embeddings.py:257` | ✅ Refactored |
| EmbeddingBatchInfo | `core/types/embeddings.py:100` | ✅ Complete |
| CodeChunk | `core/chunks.py:140` | ✅ Refactored |
| BatchKeys | `core/chunks.py:87` | ✅ Complete |
| QdrantBaseProvider | `providers/vector_stores/qdrant_base.py:60` | ⚠️ Needs Update |
| FailoverService | `engine/services/failover_service.py:29` | ✅ Service Level |
| VectorNames | **(NEW)** `providers/vector_stores/vector_names.py` | ❌ Missing |
| EmbeddingStrategy | **(NEW)** `engine/config/embedding_strategy.py` | ❌ Missing |
| VectorIntent | **(NEW)** `core/types/embeddings.py` | ❌ Missing |

---

**Analysis Complete** - Ready for implementation planning and prioritization.

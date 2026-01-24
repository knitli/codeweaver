# CodeWeaver Failover Architecture - Revised Implementation Plan

**Date**: 2026-01-19
**Last Updated**: 2026-01-23 (Minimal Type Changes for Breaking Release)
**Status**: Design Complete - Implementation Ready
**Priority**: High - Alpha Release 3 Target
**Replaces**: Previous failover plan (2026-01-18)

> **Breaking Changes Notice:**
> This is a breaking release. We're implementing minimal type changes now with
> extensibility for future multi-vector strategies (binary prefilter, function signatures,
> AST-based search, etc.). No backward compatibility - design it right from the start.

> **⚠️ API Compatibility Note:**  
> All query examples have been updated to use the modern `qdrant_client 1.16+` API:
> - `query_points()` instead of deprecated `search()`
> - Proper `Filter`, `FieldCondition`, `Range` objects instead of plain dicts
> - `with_vectors=["name"]` (list) instead of set notation
> - `prefetch` pattern for hybrid search with named vectors

---

## Changelog

### 2026-01-23 - Minimal Breaking Changes for Clean Slate
**Updated by:** Type architecture strategic analysis

**Key Decisions:**
1. ✅ **Breaking changes accepted** - No users yet, design it right
2. ✅ **Minimal implementation** - Only what's needed for failover + future extensibility
3. ✅ **Delete, don't deprecate** - `EmbeddingModelInfo` deleted entirely
4. ✅ **Required fields** - `intent` is mandatory in `EmbeddingBatchInfo`
5. ✅ **Simple types** - No over-engineering (ttl, quantization, priority deferred)

**Type Changes:**
- **DELETE**: `EmbeddingModelInfo` (replaced by `EmbeddingStrategy`)
- **DELETE**: Old `QueryResult` NamedTuple (replaced with dict-based version, same name)
- **ADD**: `VectorStrategy` - minimal vector configuration (model, kind, lazy)
- **ADD**: `EmbeddingStrategy` - multi-vector strategy definition
- **MODIFY**: `EmbeddingBatchInfo` - add required `intent: str` field
- **MODIFY**: `QueryResult` - new dict-based multi-vector result type

### 2026-01-22 - Initial Architecture Review
**Status:** ✅ **Already Complete** - CodeChunk and ChunkEmbeddings already use dynamic dicts

**Findings:**
1. `CodeChunk._embeddings: dict[str, BatchKeys]` ✅ Already implemented
2. `ChunkEmbeddings.embeddings: dict[str, EmbeddingBatchInfo]` ✅ Already implemented
3. Dynamic intent support ✅ Already in place
4. Missing: VectorNames, EmbeddingStrategy, required intent field

---

## Executive Summary

This plan details a **failover implementation** that not only solves the immediate availability problem but refactors the core embedding architecture to support **future intent-driven search** (arbitrary named vectors).

**Key Architectural Shifts:**
- **From:** Rigid "Primary vs. Backup" binary in code structures.
- **To:** Dynamic dictionary of named embeddings (`"primary"`, `"backup"`, `"summary"`, `"ast"`).
- **Benefit:** Immediate failover support now; rich multi-modal/intent search support later without re-architecture.

**Implementation Effort:** 4 weeks

---

## Table of Contents

1. [Architectural Overview](#architectural-overview)
2. [Core Design Decisions](#core-design-decisions)
3. [Required Changes](#required-changes)
4. [Implementation Phases](#implementation-phases)
5. [Testing Strategy](#testing-strategy)

---

## Architectural Overview

### **System Context**

**Current Reality:**
- CodeWeaver runs as a **continuously-running daemon**.
- `CodeChunk` and `ChunkEmbeddings` ✅ **already use dynamic dicts** (`dict[str, BatchKeys]`)
- Missing: Intent field in `EmbeddingBatchInfo`, `VectorNames`, `EmbeddingStrategy`
- Provider failures impact indexing, not just search.

**Design Insight:**
- **All sparse embedders are local** (fastembed, sentence-transformers).
- **Backup embedding + reranking models** now have 8192 token context windows, eliminating scenarios where the lower limit would require two chunk sizes.
- **Chunk size cap** of ~7500 tokens works for all providers as top limit. However, chunkers are functionally capped at no more than ~1000 tokens to keep chunk sizes within optimal size to match training corpora (already implemented in chunkers)
- **Preemptive turn off:** If dense embedding provider is local, turn off backup system.

### **High-Level Architecture**

```
┌─────────────────────────────────────────────────────────┐
│              Daemon Startup / File Change               │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              ChunkingService (Single Granularity)       │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│         EmbeddingService (Conditional Intent/Backup)    │
│                                                         │
│  Generates dict of embeddings:                          │
│  {                                                      │
│    "primary": <Voyage Embeddings>,                      │
│    "backup": <Jina Embeddings>, (if configured)         │
│    "sparse": <SPLADE Embeddings>                        │
│  }                                                      │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│   Qdrant Collection (Named Vectors - Single Collection) │
│                                                         │
│   Point Structure:                                      │
│   {                                                     │
│     "id": "chunk-uuid",                                 │
│     "vector": {                                         │
│       "voyage_embed": [0.1, ...],   // Mapped from "primary"
│       "jina_embed": [...],          // Mapped from "backup"
│       "bm25_sparse": {...}          // Mapped from "sparse"
│     },                                                  │
│     "payload": { chunk metadata }                       │
│   }                                                     │
└──────────────────────┬──────────────────────────────────┘
```

---

## Core Design Decisions

### **Decision 1: Dynamic Embedding Storage**

**Status:** ✅ **Already Complete**

**Current State:**
- `CodeChunk._embeddings: dict[str, BatchKeys]` ✅ Implemented
- `ChunkEmbeddings.embeddings: dict[str, EmbeddingBatchInfo]` ✅ Implemented
- Intent-based keys ("primary", "sparse", "backup") ✅ Supported

**Required Change:**
- Add `intent: str` field to `EmbeddingBatchInfo` (currently intent is only the dict key)
- This makes embeddings self-describing for logging, debugging, validation

### **Decision 2: Single Collection with Named Vectors**

**Rationale:** Qdrant supports multiple named vectors per point. This eliminates the need for separate collections and complex reconciliation logic. 

**Implementation:**
```python
# Collection configuration
vectors_config = {
    "dense": VectorParams(size=1024, distance=Distance.COSINE),
    "dense_backup": VectorParams(size=512, distance=Distance.COSINE), # Optional
    "sparse": SparseVectorParams(),
}
```

### **Decision 3: Vector Name Resolution (NEW)**

**Rationale:** Decouple logical intents ("primary", "backup") from physical Qdrant vector names.

**Implementation:**
```python
class VectorNames(BasedModel):
    """Maps intent → physical Qdrant vector name."""
    mapping: dict[str, str]

    def resolve(self, intent: str) -> str:
        """Get physical name, fallback to intent."""
        return self.mapping.get(intent, intent)

    @classmethod
    def from_strategy(cls, strategy: EmbeddingStrategy) -> VectorNames:
        """Auto-generate from embedding strategy."""
        mapping = {}
        for intent, vec_strategy in strategy.vectors.items():
            # Simple derivation: "voyage-large-2" → "voyage_large_2"
            model_name = str(vec_strategy.model).split("/")[-1]
            vector_name = model_name.replace("-", "_").lower()
            mapping[intent] = vector_name
        return cls(mapping=mapping)
```

### **Decision 4: Embedding Strategy Configuration (NEW)**

**Rationale:** Need unified configuration for which vectors to generate, replacing hardcoded logic.

**Implementation:**
```python
class VectorStrategy(BasedModel):
    """Configuration for a single vector type."""
    model: ModelNameT
    kind: EmbeddingKind  # Reuse existing DENSE/SPARSE enum
    lazy: bool = False   # Generate on-demand vs upfront

    @classmethod
    def dense(cls, model: str, *, lazy: bool = False) -> VectorStrategy:
        return cls(model=ModelName(model), kind=EmbeddingKind.DENSE, lazy=lazy)

    @classmethod
    def sparse(cls, model: str, *, lazy: bool = False) -> VectorStrategy:
        return cls(model=ModelName(model), kind=EmbeddingKind.SPARSE, lazy=lazy)


class EmbeddingStrategy(BasedModel):
    """Multi-vector embedding strategy."""
    vectors: dict[str, VectorStrategy]

    @classmethod
    def default(cls) -> EmbeddingStrategy:
        """Default: primary + sparse."""
        return cls(vectors={
            "primary": VectorStrategy.dense("voyage-large-2-instruct"),
            "sparse": VectorStrategy.sparse("Alibaba-NLP/gte-multilingual-mlm-base"),
        })

    @classmethod
    def with_backup(cls) -> EmbeddingStrategy:
        """With failover backup."""
        return cls(vectors={
            "primary": VectorStrategy.dense("voyage-large-2-instruct"),
            "sparse": VectorStrategy.sparse("Alibaba-NLP/gte-multilingual-mlm-base"),
            "backup": VectorStrategy.dense("jinaai/jina-embeddings-v3", lazy=True),
        })

    @property
    def intents(self) -> set[str]:
        """All configured intents."""
        return set(self.vectors.keys())
```

### **Decision 5: Generic Point Construction**

**Rationale:** Provider iterates over chunk embeddings dynamically using `VectorNames`.

**Implementation:**
```python
def _prepare_vectors(self, chunk: CodeChunk) -> dict[str, Any]:
    """Prepare vectors dynamically from chunk."""
    from codeweaver.providers.embedding.registry import embedding_registry

    vectors = {}
    for intent, batch_key in chunk.embeddings.items():
        # Get physical vector name
        vector_name = self.vector_names.resolve(intent)

        # Get actual embedding data from registry
        embedding_info = embedding_registry.get(batch_key)

        if embedding_info.is_dense:
            vectors[vector_name] = list(embedding_info.embeddings)
        elif embedding_info.is_sparse:
            vectors[vector_name] = self._prepare_sparse_vector_data(...)

    return vectors
```

---

## Required Changes

### **Phase 1: Core Type Changes** (Week 1)

#### 1.1 DELETE Old Types
**File:** `src/codeweaver/core/types/embeddings.py`

**DELETE entirely:**
```python
# ❌ REMOVE - Replaced by EmbeddingStrategy
class EmbeddingModelInfo(NamedTuple):
    dense: ModelNameT | None
    sparse: ModelNameT | None
    backup_dense: ModelNameT | None
    backup_sparse: ModelNameT | None

# ❌ REMOVE - Replaced by new QueryResult (same name)
class QueryResult(NamedTuple):
    dense: RawEmbeddingVectors | None
    sparse: SparseEmbedding | None
```

#### 1.2 ADD New QueryResult (Breaking Change)
**File:** `src/codeweaver/core/types/embeddings.py`

**Replace with dict-based version (same name):**
```python
class QueryResult(BasedModel):
    """Multi-vector embedding result (replaces old NamedTuple)."""
    vectors: dict[str, RawEmbeddingVectors | SparseEmbedding]

    def __getitem__(self, intent: str) -> RawEmbeddingVectors | SparseEmbedding:
        """Dict-like access."""
        return self.vectors[intent]

    def get(self, intent: str, default=None) -> RawEmbeddingVectors | SparseEmbedding | None:
        """Safe access with default."""
        return self.vectors.get(intent, default)

    @property
    def intents(self) -> set[str]:
        """Available intent names."""
        return set(self.vectors.keys())
```

#### 1.3 UPDATE EmbeddingBatchInfo (Breaking Change)
**File:** `src/codeweaver/core/types/embeddings.py`

**Add required intent field:**
```python
class EmbeddingBatchInfo(BasedModel):
    # ... existing fields ...
    kind: EmbeddingKind  # Already exists

    # NEW: Required intent field
    intent: Annotated[
        str,
        Field(description="Vector intent: 'primary', 'sparse', 'backup', etc.")
    ]

    @classmethod
    def create_dense(
        cls,
        # ... existing params ...
        intent: str,  # NEW: required parameter
        *,
        # ... existing kwargs ...
    ) -> EmbeddingBatchInfo:
        return cls(..., intent=intent)

    @classmethod
    def create_sparse(
        cls,
        # ... existing params ...
        intent: str,  # NEW: required parameter
        *,
        # ... existing kwargs ...
    ) -> EmbeddingBatchInfo:
        return cls(..., intent=intent)
```

#### 1.4 UPDATE ChunkEmbeddings
**File:** `src/codeweaver/core/types/embeddings.py`

**Update add() method:**
```python
class ChunkEmbeddings(BasedModel):
    embeddings: dict[str, EmbeddingBatchInfo]  # ✅ Already exists
    chunk: CodeChunk

    def add(self, embedding_info: EmbeddingBatchInfo) -> ChunkEmbeddings:
        """Add embedding (intent from embedding_info.intent).

        BREAKING: No longer accepts optional intent parameter.
        """
        if self.chunk.chunk_id != embedding_info.chunk_id:
            raise ValueError(f"Chunk ID mismatch")

        # Intent comes from embedding_info (required field)
        intent = embedding_info.intent

        if intent in self.embeddings:
            raise ValueError(f"Intent '{intent}' already exists")

        new_embeddings = dict(self.embeddings)
        new_embeddings[intent] = embedding_info
        return self.model_copy(update={"embeddings": new_embeddings})
```

---

### **Phase 2: New Configuration Types** (Week 1-2)

#### 2.1 ADD VectorStrategy
**New File:** `src/codeweaver/core/types/strategy.py`

```python
class VectorStrategy(BasedModel):
    """Configuration for a single vector type."""
    model: ModelNameT
    kind: EmbeddingKind  # Reuse existing enum
    lazy: bool = False   # Generate on-demand vs upfront

    @classmethod
    def dense(cls, model: str | ModelNameT, *, lazy: bool = False) -> VectorStrategy:
        return cls(model=ModelName(model), kind=EmbeddingKind.DENSE, lazy=lazy)

    @classmethod
    def sparse(cls, model: str | ModelNameT, *, lazy: bool = False) -> VectorStrategy:
        return cls(model=ModelName(model), kind=EmbeddingKind.SPARSE, lazy=lazy)
```

#### 2.2 ADD EmbeddingStrategy
**New File:** `src/codeweaver/core/types/strategy.py`

```python
class EmbeddingStrategy(BasedModel):
    """Multi-vector embedding strategy configuration."""
    vectors: dict[str, VectorStrategy]

    @classmethod
    def default(cls) -> EmbeddingStrategy:
        """Default: primary dense + sparse."""
        return cls(vectors={
            "primary": VectorStrategy.dense("voyage-large-2-instruct"),
            "sparse": VectorStrategy.sparse("Alibaba-NLP/gte-multilingual-mlm-base"),
        })

    @classmethod
    def with_backup(cls) -> EmbeddingStrategy:
        """With failover backup."""
        return cls(vectors={
            "primary": VectorStrategy.dense("voyage-large-2-instruct"),
            "sparse": VectorStrategy.sparse("Alibaba-NLP/gte-multilingual-mlm-base"),
            "backup": VectorStrategy.dense("jinaai/jina-embeddings-v3", lazy=True),
        })

    @property
    def intents(self) -> set[str]:
        return set(self.vectors.keys())

    def get_strategy(self, intent: str) -> VectorStrategy:
        return self.vectors[intent]
```

#### 2.3 ADD VectorNames
**New File:** `src/codeweaver/providers/vector_stores/vector_names.py`

```python
class VectorNames(BasedModel):
    """Maps intent → physical Qdrant vector name."""
    mapping: dict[str, str]

    def resolve(self, intent: str) -> str:
        """Get physical name, fallback to intent."""
        return self.mapping.get(intent, intent)

    @classmethod
    def from_strategy(cls, strategy: EmbeddingStrategy) -> VectorNames:
        """Auto-generate mapping from strategy."""
        mapping = {}
        for intent, vec_strategy in strategy.vectors.items():
            # "voyage-large-2-instruct" → "voyage_large_2"
            model_name = str(vec_strategy.model).split("/")[-1]
            vector_name = model_name.replace("-", "_").lower()
            mapping[intent] = vector_name
        return cls(mapping=mapping)
```

### **Phase 3: Provider Updates** (Week 2)

#### 3.1 Update `QdrantBaseProvider`
**File:** `src/codeweaver/providers/vector_stores/qdrant_base.py`

**Add VectorNames field:**
```python
class QdrantBaseProvider:
    vector_names: VectorNames  # NEW field
```

**Refactor `_prepare_vectors()` to iterate dynamically:**
```python
def _prepare_vectors(self, chunk: CodeChunk) -> dict[str, Any]:
    """Prepare vectors dynamically."""
    from codeweaver.providers.embedding.registry import embedding_registry

    vectors = {}
    for intent, batch_key in chunk.embeddings.items():
        # Map intent → physical name
        vector_name = self.vector_names.resolve(intent)

        # Get embedding data
        embedding_info = embedding_registry.get(batch_key)

        if embedding_info.is_dense:
            vectors[vector_name] = list(embedding_info.embeddings)
        elif embedding_info.is_sparse:
            vectors[vector_name] = self._prepare_sparse_vector_data(...)

    return vectors
```

**Update `_validate_collection_config()`:**
- Check all vectors in `VectorNames.mapping` exist in collection schema
- Validate dimensions match for each named vector

---

### **Phase 4: Service Layer Updates** (Week 3)

#### 4.1 Update `EmbeddingService`
**File:** `src/codeweaver/engine/services/embedding_service.py`

**Changes:**
- Read `EmbeddingStrategy` from config
- Generate embeddings for each intent in `strategy.intents`
- Pass `intent` to `EmbeddingBatchInfo.create_*()` methods
- Handle lazy vs eager generation

**Example:**
```python
async def embed_chunks(self, chunks: list[CodeChunk]) -> None:
    strategy = self.config.embedding_strategy

    # Generate eager embeddings
    for intent in strategy.intents:
        vec_strategy = strategy.get_strategy(intent)

        if vec_strategy.lazy:
            continue  # Skip lazy embeddings

        # Generate embedding with this model
        provider = self._get_provider(vec_strategy.model)
        results = await provider.embed_batch([c.content for c in chunks])

        # Create batch info with intent
        for i, chunk in enumerate(chunks):
            batch_info = EmbeddingBatchInfo.create_dense(
                ...,
                intent=intent,  # NEW: required
            )
```

#### 4.2 Update Provider `embed()` Methods
**Files:** Various provider implementations

**Change return type:**
```python
# OLD
def embed(self, text: str) -> QueryResult:  # Old NamedTuple
    return QueryResult(dense=[...], sparse=None)

# NEW
def embed(self, text: str) -> QueryResult:  # New dict-based
    return QueryResult(vectors={
        "primary": [...],  # or whatever intent
    })
```

---

## Implementation Phases

### **Phase 1: Type Changes (Breaking - Week 1)**
**Goal:** Implement minimal type changes for intent-driven architecture.

**Tasks:**
1. DELETE `EmbeddingModelInfo` type
2. DELETE old `QueryResult` NamedTuple
3. ADD new `QueryResult` (dict-based, same name)
4. ADD `intent: str` field to `EmbeddingBatchInfo` (required)
5. UPDATE `ChunkEmbeddings.add()` to use `embedding_info.intent`
6. ADD `VectorStrategy` type
7. ADD `EmbeddingStrategy` type
8. ADD `VectorNames` type

**Deliverables:**
- Updated `core/types/embeddings.py`
- New `core/types/strategy.py`
- New `providers/vector_stores/vector_names.py`
- All tests updated for new signatures

### **Phase 2: Provider Updates (Week 2)**
**Goal:** Make providers use dynamic vector construction.

**Tasks:**
1. Add `vector_names: VectorNames` to `QdrantBaseProvider`
2. Refactor `_prepare_vectors()` to iterate dynamically
3. Update `_validate_collection_config()` for named vectors
4. Update all embedding providers to return new `QueryResult`
5. Update provider `embed()` methods to pass intent

**Deliverables:**
- Updated `QdrantBaseProvider`
- Updated embedding provider implementations
- Integration tests for dynamic vectors

### **Phase 3: Service & Configuration (Week 3)**
**Goal:** Integrate new types into service layer.

**Tasks:**
1. Update `EmbeddingService` to read `EmbeddingStrategy`
2. Generate embeddings for each configured intent
3. Pass intent to `EmbeddingBatchInfo` creation
4. Update configuration system for `EmbeddingStrategy`
5. Update failover service if needed

**Deliverables:**
- Updated embedding service
- Updated configuration
- End-to-end tests

---

## Testing Strategy

### **Unit Tests**

**Type Tests:**
- `test_query_result.py` - New dict-based QueryResult
- `test_embedding_batch_info.py` - Required intent field
- `test_vector_strategy.py` - VectorStrategy creation and validation
- `test_embedding_strategy.py` - Strategy presets and intents
- `test_vector_names.py` - Mapping and resolution

**Provider Tests:**
- `test_qdrant_dynamic_vectors.py` - Dynamic vector construction
- `test_vector_name_resolution.py` - Intent → physical name mapping
- `test_provider_query_result.py` - Providers return new QueryResult

### **Integration Tests**

**End-to-End Flow:**
- `test_multi_intent_embedding.py` - Generate primary + sparse + backup
- `test_strategy_driven_indexing.py` - Full indexing with EmbeddingStrategy
- `test_dynamic_failover.py` - Failover using dynamic vectors
- `test_vector_name_generation.py` - Auto-generation from strategy

**Provider Integration:**
- `test_qdrant_named_vectors.py` - Qdrant point structure with multiple vectors
- `test_collection_validation.py` - Schema validation with VectorNames

---

## Configuration Schema

### Embedding Strategy Configuration

```python
# Configuration
class EmbeddingConfig(BasedModel):
    """Embedding configuration."""
    strategy: EmbeddingStrategy = Field(default_factory=EmbeddingStrategy.default)

    # Optional: Override vector names
    vector_names: dict[str, str] | None = None

# Example: Default strategy
config = EmbeddingConfig(
    strategy=EmbeddingStrategy.default()
)

# Example: With failover
config = EmbeddingConfig(
    strategy=EmbeddingStrategy.with_backup()
)

# Example: Custom strategy
config = EmbeddingConfig(
    strategy=EmbeddingStrategy(vectors={
        "primary": VectorStrategy.dense("voyage-large-2-instruct"),
        "sparse": VectorStrategy.sparse("Alibaba-NLP/gte-multilingual-mlm-base"),
        "backup": VectorStrategy.dense("jinaai/jina-embeddings-v3", lazy=True),
    })
)
```

### Failover Settings (Unchanged)

```python
class FailoverSettings(BasedModel):
    """Failover behavior configuration."""
    disable_failover: bool = False
    backup_sync: int = 300  # 5 minutes
    recovery_window_sec: int = 300
    max_memory_mb: int = 2048
```

---

## Migration Checklist

**Breaking Changes:**
- [ ] DELETE `EmbeddingModelInfo` - find all usages, replace with `EmbeddingStrategy`
- [ ] DELETE old `QueryResult` NamedTuple
- [ ] UPDATE all `EmbeddingBatchInfo.create_*()` calls to include `intent` parameter
- [ ] UPDATE all provider `embed()` methods to return new `QueryResult`
- [ ] UPDATE `ChunkEmbeddings.add()` calls to remove optional intent parameter

**New Implementations:**
- [ ] CREATE `VectorStrategy` type
- [ ] CREATE `EmbeddingStrategy` type
- [ ] CREATE `VectorNames` type
- [ ] IMPLEMENT new `QueryResult` (dict-based)
- [ ] ADD `intent` field to `EmbeddingBatchInfo`

**Provider Updates:**
- [ ] UPDATE `QdrantBaseProvider._prepare_vectors()` for dynamic iteration
- [ ] UPDATE `QdrantBaseProvider._validate_collection_config()` for named vectors
- [ ] UPDATE all embedding provider implementations

**Service Updates:**
- [ ] UPDATE `EmbeddingService` to read `EmbeddingStrategy`
- [ ] UPDATE embedding generation to iterate over intents
- [ ] UPDATE configuration system for new types

**Testing:**
- [ ] Unit tests for all new types
- [ ] Integration tests for dynamic vectors
- [ ] End-to-end tests for failover scenarios
- [ ] Migration tests for old → new QueryResult

---

## Future Extensibility

**Ready for (but not implementing now):**
- Binary quantized vectors for fast pre-filtering
- Function signature IDF sparse vectors
- AST-aware embeddings
- Summary-only embeddings
- Comment/documentation-specific vectors

**How to add new vector types:**
```python
# Just add to strategy!
strategy = EmbeddingStrategy(vectors={
    "primary": VectorStrategy.dense("voyage-large-2"),
    "sparse": VectorStrategy.sparse("splade"),
    "binary": VectorStrategy.dense("voyage-large-2", lazy=False),  # Future
    "function_sig": VectorStrategy.sparse("code-sig-idf", lazy=True),  # Future
})
```

No type changes needed - architecture is extensible by design.

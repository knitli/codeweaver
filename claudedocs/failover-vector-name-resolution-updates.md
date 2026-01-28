<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Failover Architecture Plan - Vector Name Resolution Updates

**Date**: 2026-01-22
**Purpose**: Document required updates to failover architecture plan for vector name resolution support

## Summary of Changes

The failover architecture plan needs to be updated to support user-configurable vector names and enable future extensibility for intent-based search strategies. This addresses the architectural concern that hardcoded vector names ("dense", "dense_backup", "sparse") would:

1. Break user-configured collection names
2. Make intent-based search strategies harder to implement
3. Block cross-collection and multi-vector search features

## Solution: Convention-Based Vector Name Resolution

### Core Approach

**Alpha 3 Implementation**: Convention-based resolution with auto-detection
- Respects user configuration from `CollectionConfig.vectors_config`
- Uses naming conventions (`_backup` suffix) for auto-detection
- Defaults to "dense", "dense_backup", "sparse" for backward compatibility

**Future Evolution**: Full VectorRegistry with VectorPurpose enum
- Arbitrary purpose → name mappings
- Support for specialized vectors (CODE_STRUCTURE, SEMANTIC, etc.)
- Intent-based search strategy integration

## Required Code Changes

### 1. New File: `src/codeweaver/providers/vector_stores/vector_names.py`

```python
"""Vector name resolution for user-configurable collection names."""

from dataclasses import dataclass
from qdrant_client.models import VectorParams, SparseVectorParams
from codeweaver.providers.config.kinds import CollectionConfig


@dataclass(frozen=True)
class VectorNames:
    """Resolved vector names for a collection."""
    primary_dense: str
    backup_dense: str
    sparse: str


def get_vector_names(config: CollectionConfig) -> VectorNames:
    """Extract vector names from collection configuration.

    Auto-detects based on conventions:
    - Primary: any VectorParams without "_backup" suffix
    - Backup: any with "_backup" suffix or derived (primary + "_backup")
    - Sparse: any SparseVectorParams
    """
    # Find primary dense
    dense_vectors = {
        k: v for k, v in (config.vectors_config or {}).items()
        if isinstance(v, VectorParams) and not k.endswith("_backup")
    }
    primary_dense = next(iter(dense_vectors.keys()), "dense")

    # Find backup (explicit or derived)
    backup_vectors = {
        k for k in (config.vectors_config or {}).keys()
        if k.endswith("_backup")
    }
    backup_dense = (
        next(iter(backup_vectors))
        if backup_vectors
        else f"{primary_dense}_backup"
    )

    # Find sparse
    sparse_vectors = {
        k: v for k, v in (config.sparse_vectors_config or {}).items()
        if isinstance(v, SparseVectorParams)
    }
    sparse = next(iter(sparse_vectors.keys()), "sparse")

    return VectorNames(
        primary_dense=primary_dense,
        backup_dense=backup_dense,
        sparse=sparse,
    )
```

### 2. Update `CollectionMetadata` (`src/codeweaver/providers/vector_stores/metadata.py`)

Add vector name mappings:

```python
class CollectionMetadata(BasedModel):
    # ... existing fields ...

    version: str = "1.3.0"  # Bump version for vector_names field

    # NEW: Vector name mappings
    vector_names: dict[str, str] = Field(
        default_factory=lambda: {
            "primary_dense": "dense",
            "backup_dense": "dense_backup",
            "sparse": "sparse",
        },
        description="Mapping of vector purposes to actual names"
    )

    def get_vector_names(self) -> VectorNames:
        """Get VectorNames from metadata."""
        from codeweaver.providers.vector_stores.vector_names import VectorNames

        return VectorNames(
            primary_dense=self.vector_names["primary_dense"],
            backup_dense=self.vector_names["backup_dense"],
            sparse=self.vector_names["sparse"],
        )
```

### 3. Update `QdrantBaseProvider` (`src/codeweaver/providers/vector_stores/qdrant_base.py`)

Add vector name resolution:

```python
from codeweaver.providers.vector_stores.vector_names import VectorNames, get_vector_names

class QdrantBaseProvider(VectorStoreProvider[AsyncQdrantClient], ABC):
    # ... existing fields ...

    _vector_names: VectorNames | None = None

    @property
    def vector_names(self) -> VectorNames:
        """Get resolved vector names for this collection."""
        if self._vector_names is None:
            metadata = await self.collection_info()
            if metadata and metadata.vector_names:
                self._vector_names = metadata.get_vector_names()
            else:
                self._vector_names = get_vector_names(self.config.collection)
        return self._vector_names

    async def _initialize(self) -> None:
        """Initialize with vector name resolution."""
        await self._init_provider()

        # Initialize vector names
        metadata = await self.collection_info()
        if metadata:
            self._vector_names = metadata.get_vector_names()
        else:
            self._vector_names = get_vector_names(self.config.collection)
```

### 4. Update All Code Examples

Replace all hardcoded vector names with VectorNames resolution:

**Before**:
```python
vectors = {
    "dense": dense_vector,
    "dense_backup": backup_vector,
    "sparse": sparse_vector,
}

using="dense"  # or "dense_backup"
```

**After**:
```python
vector_names = self.vector_names  # or get_vector_names(config)

vectors = {
    vector_names.primary_dense: dense_vector,
    vector_names.backup_dense: backup_vector,
    vector_names.sparse: sparse_vector,
}

using=vector_names.primary_dense  # or vector_names.backup_dense
```

## Implementation Phases Update

### NEW Phase 0: Vector Name Resolution Foundation (Week 1, Part 1)

**Tasks**:
1. Create `VectorNames` dataclass and `get_vector_names()` helper
2. Update `CollectionMetadata` with `vector_names` field
3. Update `QdrantBaseProvider` to initialize `_vector_names`
4. Add tests for vector name resolution logic

**Testing**:
- Test default resolution ("dense", "dense_backup", "sparse")
- Test custom names from user config
- Test backup name derivation
- Test persistence and retrieval from CollectionMetadata

**Deliverable**: Vector name resolution infrastructure operational

### Updated Phase 1: Named Vectors Foundation (Week 1, Part 2)

Now uses `VectorNames` throughout instead of hardcoded strings.

### Updated Phase 2: Conditional Backup Creation (Week 2)

`EmbeddingService` and `IndexingService` use `VectorNames` for all vector operations.

### Updated Phase 3: Reconciliation Service (Week 3)

`VectorReconciliationService` uses `VectorNames` to find and fill missing vectors.

## Testing Strategy Updates

### New Unit Tests

```python
# tests/providers/vector_stores/test_vector_names.py

def test_get_vector_names_defaults():
    """Test vector name resolution with default configuration."""
    config = CollectionConfig(
        vectors_config={"dense": VectorParams(size=1024)},
        sparse_vectors_config={"sparse": SparseVectorParams()},
    )

    names = get_vector_names(config)

    assert names.primary_dense == "dense"
    assert names.backup_dense == "dense_backup"
    assert names.sparse == "sparse"

def test_get_vector_names_custom():
    """Test with custom names."""
    config = CollectionConfig(
        vectors_config={
            "my_embeddings": VectorParams(size=1024),
            "my_embeddings_backup": VectorParams(size=512),
        },
        sparse_vectors_config={"my_sparse": SparseVectorParams()},
    )

    names = get_vector_names(config)

    assert names.primary_dense == "my_embeddings"
    assert names.backup_dense == "my_embeddings_backup"
    assert names.sparse == "my_sparse"
```

### Integration Test Updates

All failover tests should verify custom vector names work:

```python
@pytest.mark.integration
async def test_failover_with_custom_vector_names():
    """Test failover with user-configured vector names."""

    collection_config = CollectionConfig(
        vectors_config={
            "voyage_embeddings": VectorParams(size=1024),
            "voyage_embeddings_backup": VectorParams(size=512),
        },
        sparse_vectors_config={"bm25_sparse": SparseVectorParams()},
    )

    vector_store = QdrantVectorStoreProvider(collection=collection_config)
    vector_names = vector_store.vector_names

    assert vector_names.primary_dense == "voyage_embeddings"
    # ... rest of test using custom names
```

## User Configuration Examples

### Default (Implicit)

```toml
# codeweaver.toml
[provider.vector_store.collection]
# Uses defaults: dense, dense_backup, sparse
```

### Custom Names

```toml
# codeweaver.toml
[provider.vector_store.collection]
vectors_config.voyage_embeddings = { size = 1024, distance = "Cosine" }
vectors_config.voyage_embeddings_backup = { size = 512, distance = "Cosine" }
sparse_vectors_config.bm25_sparse = {}

# Auto-detected:
# primary_dense = "voyage_embeddings"
# backup_dense = "voyage_embeddings_backup"
# sparse = "bm25_sparse"
```

## Future Migration Path

### Phase: Intent-Based Search (Post-Alpha 3)

```python
# Future: src/codeweaver/providers/vector_stores/registry.py

class VectorPurpose(Enum):
    """Logical purposes for vectors."""
    PRIMARY_DENSE = "primary_dense"
    BACKUP_DENSE = "backup_dense"
    SPARSE = "sparse"
    CODE_STRUCTURE = "code_structure"  # Future
    SEMANTIC_CONCEPTS = "semantic_concepts"  # Future

class VectorRegistry:
    """Maps purposes to actual vector names."""

    def __init__(self, config: CollectionConfig, metadata: CollectionMetadata):
        self._mapping = metadata.vector_names or self._auto_discover(config)

    def resolve(self, purpose: VectorPurpose) -> str:
        """Get actual vector name for a purpose."""
        return self._mapping[purpose.value]
```

This provides a clear evolution path from VectorNames → VectorRegistry without breaking changes.

## Benefits

✅ **User customization** - Respects custom vector names
✅ **Backward compatible** - Defaults work with existing code
✅ **Future extensible** - Clear path to VectorRegistry
✅ **No hardcoding** - All references use VectorNames
✅ **Type-safe** - Compile-time guarantees
✅ **Observable** - Names persisted in metadata
✅ **Testable** - Easy to test custom configurations

## Implementation Checklist

- [ ] Create `vector_names.py` with `VectorNames` and `get_vector_names()`
- [ ] Update `CollectionMetadata` with `vector_names` field
- [ ] Update `QdrantBaseProvider._initialize()` for name resolution
- [ ] Update collection creation to use `VectorNames`
- [ ] Update point construction to use `VectorNames`
- [ ] Update search methods to use `VectorNames`
- [ ] Update `EmbeddingService` to use `VectorNames`
- [ ] Update `ReconciliationService` to use `VectorNames`
- [ ] Add unit tests for vector name resolution
- [ ] Add integration tests with custom names
- [ ] Update all plan documentation with `VectorNames` examples
- [ ] Document user configuration options

## Success Metrics (Additional)

- ✅ **User can customize all vector names via config**
- ✅ **Custom vector names preserve across restarts**
- ✅ **Vector name migration works for existing collections**
- ✅ **Clear migration path to VectorRegistry**
- ✅ **No breaking changes for default configurations**

---

**Next Steps**: Integrate these changes into the main failover architecture plan document.

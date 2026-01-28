<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Vector Types Phase 2 - Consumer Migration TODO

## Status
**Phase 1**: ✅ Complete - New types implemented, old types removed (breaking release)
**Phase 2**: 🔄 In Progress - Consumer migration needed

## Files Requiring Updates

### 1. Vector Store Providers

#### `src/codeweaver/providers/vector_stores/qdrant_base.py`
**Current State**: Still imports and uses `VectorNames` (line 46, 69-78)

**Changes Needed**:
```python
# Remove import (line 46)
- from codeweaver.providers.types import EmbeddingCapabilityGroup, VectorNames
+ from codeweaver.providers.types import EmbeddingCapabilityGroup

# Remove vector_names field (lines 69-78) from QdrantBaseProvider class
- vector_names: VectorNames = Field(...)

# Update logic that resolves intent -> physical vector names
# Use VectorSet.by_role() or VectorSet.by_name() instead of VectorNames.resolve()
```

**Where `vector_names` is used**: Search for `vector_names` or `VectorNames` in this file to find all usages

### 2. Tests to Delete

#### `tests/unit/core/types/test_embedding_strategy.py`
- Tests deprecated `VectorStrategy` and `EmbeddingStrategy` classes
- **Action**: Delete file entirely

#### `tests/unit/providers/vector_stores/test_vector_names.py`
- Tests deprecated `VectorNames` class
- **Action**: Delete file entirely

### 3. Other Potential Consumers

**Search for**:
- `VectorStrategy` - No remaining references after removal
- `EmbeddingStrategy` - No remaining references after removal
- `VectorNames` - Only in `qdrant_base.py`
- `vector_names` (lowercase) - Only in `qdrant_base.py`

## Implementation Strategy

### Step 1: Remove VectorNames from QdrantBaseProvider

The `vector_names` field was used to map intent names to physical Qdrant vector names. With the new system:

**Old approach**:
```python
# Old: VectorNames mapping
vector_names = VectorNames(mapping={
    "primary": "dense",
    "sparse": "sparse",
    "backup": "backup_dense"
})
physical_name = vector_names.resolve("primary")  # "dense"
```

**New approach**:
```python
# New: VectorSet with role-based names
vector_set = VectorSet(vectors={
    "primary": VectorConfig(name="primary", role=VectorRole.PRIMARY, ...),
    "sparse": VectorConfig(name="sparse", role=VectorRole.SPARSE, ...)
})

# Query by role
primary_vector = vector_set.by_role(VectorRole.PRIMARY)[0]
physical_name = primary_vector.name  # "primary"
```

**Key difference**: Physical vector names now directly reflect their role. No mapping needed.

### Step 2: Update Collection Configuration

The `QdrantBaseProvider` needs to use `VectorSet` instead of `VectorNames` for collection configuration:

**Current**: Provider likely has logic to generate Qdrant collection config from `VectorNames`

**New**: Use `VectorSet` methods:
```python
# For collection creation
vectors_config = vector_set.to_qdrant_vectors_config()  # dict[str, VectorParams]
sparse_config = vector_set.to_qdrant_sparse_vectors_config()  # dict[str, SparseVectorParams]

# Create collection with both
collection_config = CollectionParams(
    vectors_config=vectors_config,
    sparse_vectors_config=sparse_config
)
```

### Step 3: Update Search/Query Logic

Any code that resolves intent names to physical vector names needs updating:

**Old pattern**:
```python
intent = "primary"
vector_name = self.vector_names.resolve(intent)  # "dense"
# Use vector_name in query
```

**New pattern**:
```python
role = VectorRole.PRIMARY  # or string "primary"
vectors = self.vector_set.by_role(role)
if vectors:
    vector_name = vectors[0].name  # "primary"
    # Use vector_name in query
```

## Testing Strategy

1. **Unit Tests**: Update tests for `QdrantBaseProvider` to use `VectorSet`
2. **Integration Tests**: Verify collection creation works with new types
3. **Backward Compatibility**: None needed (breaking release)

## Migration Checklist

- [ ] Remove `VectorNames` import from `qdrant_base.py`
- [ ] Remove `vector_names` field from `QdrantBaseProvider`
- [ ] Add `vector_set: VectorSet` field to `QdrantBaseProvider`
- [ ] Update collection configuration logic
- [ ] Update intent->physical name resolution logic
- [ ] Delete `tests/unit/core/types/test_embedding_strategy.py`
- [ ] Delete `tests/unit/providers/vector_stores/test_vector_names.py`
- [ ] Update any tests that reference old types
- [ ] Verify all imports work correctly
- [ ] Run full test suite

## Notes

- **Breaking Release**: No backward compatibility needed
- **Physical Vector Names**: Now role-based (`"primary"`, `"backup"`, `"sparse"`) instead of model-based
- **No Mapping Layer**: VectorSet eliminates the need for VectorNames entirely
- **Cleaner Architecture**: Direct alignment with Qdrant's vector configuration

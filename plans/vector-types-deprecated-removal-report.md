<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Vector Types - Deprecated Types Removal Report

**Date**: 2026-01-27
**Status**: ✅ **COMPLETE**
**Release Type**: **BREAKING** (types were never deployed in production)

## Summary

Successfully removed all deprecated vector type classes from the codebase as part of the clean break for the vector types refactor. The old types (`VectorStrategy`, `EmbeddingStrategy`, `VectorNames`) have been completely removed and replaced with the new role-based architecture.

## Files Modified

### 1. `src/codeweaver/providers/types/vectors.py`
**Changes**:
- ✅ Removed `VectorStrategy` class (lines 24-101)
- ✅ Removed `EmbeddingStrategy` class (lines 104-225)
- ✅ Removed `VectorNames` class (lines 235-283)
- ✅ Removed `importlib` import (no longer needed)
- ✅ Removed `HAS_ST` constant (no longer needed)
- ✅ Updated `__all__` to only export new types: `VectorRole`, `VectorConfig`, `VectorSet`
- ✅ Updated header comments to reflect clean architecture (removed "Phase 1" language)

**Before**:
```python
__all__ = ("EmbeddingStrategy", "VectorNames", "VectorStrategy")

# Phase 1: New Vector Types
# They will eventually replace VectorStrategy, EmbeddingStrategy, and VectorNames.
```

**After**:
```python
__all__ = ("VectorRole", "VectorConfig", "VectorSet")

# ============================================================================
# Vector Types (Role-Based Architecture)
# ============================================================================
# Role-based vector configuration system with direct Qdrant alignment.
```

### 2. `src/codeweaver/providers/types/__init__.py`
**Changes**:
- ✅ Updated TYPE_CHECKING imports: `VectorConfig`, `VectorRole`, `VectorSet` (replaced old types)
- ✅ Updated `_dynamic_imports` mapping: Added new types, removed old types
- ✅ Updated `__all__` tuple: Exported new types, removed old types

**Removed from `__all__`**:
- `"EmbeddingStrategy"`
- `"VectorNames"`
- `"VectorStrategy"`

**Added to `__all__`**:
- `"VectorConfig"`
- `"VectorRole"`
- `"VectorSet"`

### 3. `src/codeweaver/providers/__init__.py`
**Changes**: Same pattern as `types/__init__.py`
- ✅ Updated TYPE_CHECKING imports
- ✅ Updated `_dynamic_imports` mapping (3 locations)
- ✅ Updated `__all__` tuple (3 locations)

All references to old types replaced with new types throughout the lazy import system.

### 4. Test Files Deleted
- ✅ Deleted `tests/unit/core/types/test_embedding_strategy.py`
- ✅ Deleted `tests/unit/providers/vector_stores/test_vector_names.py`

These test files only tested the deprecated types and are no longer relevant.

## Verification

### Import Testing
```bash
✅ from codeweaver.providers.types import VectorRole, VectorConfig, VectorSet  # Works
✅ from codeweaver.providers import VectorRole, VectorConfig, VectorSet        # Works
✅ VectorRole.PRIMARY.variable == "primary"                                    # Correct
```

### No Remaining References
Searched entire codebase for old type usage:
- ✅ `VectorStrategy` - No references except in `qdrant_base.py` (Phase 2 work)
- ✅ `EmbeddingStrategy` - No references
- ✅ `VectorNames` - Only in `qdrant_base.py` (Phase 2 work)

## Remaining Work (Phase 2)

### Known Consumer: `src/codeweaver/providers/vector_stores/qdrant_base.py`

**Current State**: Still has `VectorNames` usage:
```python
from codeweaver.providers.types import EmbeddingCapabilityGroup, VectorNames

class QdrantBaseProvider:
    vector_names: VectorNames = Field(...)
```

**Action Required**: See `plans/vector-types-phase2-todo.md` for migration plan

This is the only remaining consumer of the old types. Will be addressed in Phase 2 consumer migration.

## Breaking Changes

### For External Users (if any existed)

**Removed APIs**:
- `VectorStrategy.dense(model_name)` → Use `VectorConfig(name="primary", ...)`
- `VectorStrategy.sparse(model_name)` → Use `VectorConfig(name="sparse", ...)`
- `EmbeddingStrategy.default()` → Use `VectorSet.default()`
- `EmbeddingStrategy.with_backup()` → Create custom `VectorSet`
- `VectorNames.resolve(intent)` → Use `VectorSet.by_role(role)`
- `VectorNames.from_strategy(strategy)` → No longer needed (VectorSet uses role-based naming)

**Migration Path**:
```python
# Old
strategy = EmbeddingStrategy(vectors={
    "primary": VectorStrategy.dense("voyage-large-2"),
    "sparse": VectorStrategy.sparse("opensearch/sparse")
})
vector_names = VectorNames.from_strategy(strategy)
physical_name = vector_names.resolve("primary")

# New
vector_set = VectorSet(vectors={
    "primary": VectorConfig(
        name="primary",  # Physical name is role-based
        model_name=ModelName("voyage-large-2"),
        params=VectorParams(...),
        role=VectorRole.PRIMARY
    ),
    "sparse": VectorConfig(
        name="sparse",
        model_name=ModelName("opensearch/sparse"),
        params=SparseVectorParams(...),
        role=VectorRole.SPARSE
    )
})
physical_name = vector_set.by_role(VectorRole.PRIMARY)[0].name
```

## Benefits Achieved

✅ **Cleaner Architecture**: Removed mapping layer (VectorNames)
✅ **Qdrant Alignment**: Direct use of VectorParams/SparseVectorParams
✅ **Role-Based Naming**: Physical names reflect purpose ("primary", "backup", "sparse")
✅ **Future-Proof**: Supports multiple vectors per role via dict keying
✅ **Type Safety**: Immutable frozen BaseModels
✅ **Simpler API**: Fewer classes, clearer responsibilities

## No Backward Compatibility

This is a **breaking release**. No backward compatibility layer was created because:
1. Types were never deployed in production
2. Clean break is better than maintenance burden
3. New architecture is fundamentally different (no clean conversion)

## Next Steps

**Phase 2**: Consumer Migration
- Update `qdrant_base.py` to use `VectorSet` instead of `VectorNames`
- Update collection configuration logic
- Update search/query intent resolution
- Run full test suite
- See `plans/vector-types-phase2-todo.md` for detailed plan

## Conclusion

Successfully removed all deprecated vector types from the codebase. The new role-based architecture is now the only vector type system, providing a cleaner and more maintainable foundation for future development.

**Status**: ✅ Ready for Phase 2 consumer migration

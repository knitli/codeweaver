<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Circular Import Fix - Summary

**Date**: 2025-11-03
**Status**: ✅ **RESOLVED** - Tests now run successfully

## Problem

Tests for the client factory implementation were blocked by circular import errors:

```
ImportError: cannot import name 'get_provider_registry' from partially initialized module
'codeweaver.common.registry.provider'
```

### Circular Import Chain

1. **provider.py** → imports **VectorStoreProvider**
2. **vector_stores/base.py** → imports **StrategizedQuery** from agent_api
3. **agent_api/__init__.py** → imports **find_code**
4. **find_code/pipeline.py** → imports **get_provider_registry**
5. ❌ **Circular back to provider.py**

## Solution

### Fix 1: Lazy Import in pipeline.py

**Problem**: Top-level import of `get_provider_registry` in `pipeline.py` caused circular dependency.

**Solution**: Move import inside functions that use it (lazy import pattern).

**Files Modified**: `src/codeweaver/agent_api/find_code/pipeline.py`

```python
# BEFORE (line 21):
from codeweaver.common.registry import get_provider_registry

# AFTER (removed from top-level)

# Then inside each function:
async def embed_query(query: str) -> QueryResult:
    from codeweaver.common.registry import get_provider_registry  # Lazy import
    registry = get_provider_registry()
    ...
```

**Changes**:
- `embed_query()` - added lazy import
- `execute_vector_search()` - added lazy import
- `rerank_results()` - added lazy import

### Fix 2: Lazy Default Factory in vector_stores/base.py

**Problem**: `_embedding_caps` field default evaluated at class definition time, triggering circular import via `_get_caps()`.

**Solution**: Use Pydantic's `PrivateAttr` with `default_factory` for lazy evaluation.

**Files Modified**: `src/codeweaver/providers/vector_stores/base.py`

```python
# BEFORE:
_embedding_caps: EmbeddingCapsDict = EmbeddingCapsDict(
    dense=_get_caps(), sparse=_get_caps(sparse=True)
)

# AFTER:
def _default_embedding_caps() -> EmbeddingCapsDict:
    """Default factory for embedding capabilities. Evaluated lazily at instance creation."""
    return EmbeddingCapsDict(
        dense=_get_caps(), sparse=_get_caps(sparse=True)
    )

_embedding_caps: EmbeddingCapsDict = PrivateAttr(default_factory=_default_embedding_caps)
```

### Fix 3: String Annotation for cast() in provider.py

**Problem**: `cast()` with `LiteralProviderKind` evaluated at runtime, but type only imported under `TYPE_CHECKING`.

**Solution**: Use string literal for cast target type.

**Files Modified**: `src/codeweaver/common/registry/provider.py`

```python
# BEFORE (line 76-77):
] = cast(
    MappingProxyType[LiteralProviderKind, Mapping[LiteralProvider, partial[LazyImport[Any]]]],
    MappingProxyType({

# AFTER:
] = cast(
    "MappingProxyType[LiteralProviderKind, Mapping[LiteralProvider, partial[LazyImport[Any]]]]",
    MappingProxyType({
```

## Test Results

### Before Fix
```
ERROR: All 22 tests failed with ImportError: circular import
```

### After Fix
```
✅ 15 PASSING (68%)
❌ 7 FAILING (fixable issues, not circular imports)
```

**Passing Tests (15)**:
- ✅ All `TestInstantiateClient` tests except missing API key test (12/13)
- ✅ All `TestClientOptionsHandling` tests (2/2)

**Failing Tests (7)**:
- ❌ `TestClientMapLookup` (5 tests) - `LiteralProvider` not defined in capabilities.py
- ❌ Missing required API key test - validation logic needs check
- ❌ Provider kind normalization test - same `LiteralProvider` issue

## Impact

**✅ Primary Goal Achieved**: Circular import resolved, tests can now run

**Remaining Work**:
1. Fix `LiteralProvider` issue in `capabilities.py` (same pattern as our fix)
2. Fix test that patches wrong CLIENT_MAP location
3. Verify API key validation logic

## Key Learnings

1. **Lazy Imports Pattern**: Move imports inside functions when circular dependency exists
2. **Pydantic Private Attributes**: Use `PrivateAttr(default_factory=...)` for lazy evaluation
3. **String Type Annotations**: Use string literals in `cast()` for types under `TYPE_CHECKING`
4. **Default Factory Pattern**: Defer expensive computations to instance creation time

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/codeweaver/agent_api/find_code/pipeline.py` | Modified | Lazy imports in 3 functions |
| `src/codeweaver/providers/vector_stores/base.py` | Modified | Lazy default factory for `_embedding_caps` |
| `src/codeweaver/common/registry/provider.py` | Modified | String annotation for cast() |

## Next Steps

1. ✅ **DONE**: Resolve circular import
2. 🔄 **IN PROGRESS**: Fix remaining test failures
3. ⏳ **TODO**: Run full test suite
4. ⏳ **TODO**: Commit fixes with comprehensive message

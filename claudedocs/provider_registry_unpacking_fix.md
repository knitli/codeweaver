<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Provider Registry Unpacking Error - Fix Summary

**Date**: 2025-11-04
**Issue**: BLOCKER #3 from integration test assessment
**Status**: ✅ FIXED

## Problem Statement

**Error Location**: `src/codeweaver/common/registry/provider.py:814` (now line 859)

**Error Type**:
```python
ValueError: too many values to unpack (expected 2)
```

**Root Cause**:
Code attempted to unpack `self._provider_map[provider_kind]` into `(registry, kind_name)` tuple, but `_provider_map` only contains lazy import mappings, not runtime registry references.

## Data Structure Mismatch

### What Was Expected
```python
# Line 814 tried to do:
registry, kind_name = self._provider_map[provider_kind]
```

### What Actually Existed
```python
# _provider_map structure (line 74-148):
_provider_map: ClassVar[
    MappingProxyType[LiteralProviderKind, Mapping[LiteralProvider, partial[LazyImport[Any]]]]
] = MappingProxyType({
    ProviderKind.EMBEDDING: {
        Provider.VOYAGE: partial(lazy_import, "...voyage"),
        # ... more providers
    },
    # ... more kinds
})
```

**Analysis**: `_provider_map[provider_kind]` returns a single `Mapping` object, not a 2-tuple.

## Root Cause Analysis

The issue was introduced in commit `90dd6699` which removed the `_registry_map` property during a refactoring but failed to update the unpacking code that depended on it.

**Before removal** (commit `90dd669^`):
```python
@property
def _registry_map(self) -> dict[ProviderKind | str, tuple[MutableMapping[...], str]]:
    """Get the registry map for provider classes."""
    return {
        ProviderKind.EMBEDDING: (self._embedding_providers, "Embedding"),
        "embedding": (self._embedding_providers, "Embedding"),
        # ... more mappings
    }

def get_provider_class(...):
    registry, kind_name = self._registry_map[provider_kind]  # This worked!
```

**After removal** (commit `90dd6699`):
```python
# _registry_map property was completely removed
# But line 814 still tried to use it, causing the error
def get_provider_class(...):
    registry, kind_name = self._provider_map[provider_kind]  # ERROR!
```

## Solution Implemented

**Approach**: Restore the `_registry_map` property with proper mapping from provider kinds to runtime registries.

### Change 1: Add `_registry_map` Property

**File**: `src/codeweaver/common/registry/provider.py`
**Location**: After line 190 (after `get_instance()` method)

```python
@property
def _registry_map(
    self,
) -> dict[
    ProviderKind | str,
    tuple[
        MutableMapping[
            Provider,
            LazyImport[type[EmbeddingProvider[Any]]]
            | type[EmbeddingProvider[Any]]
            | LazyImport[type[SparseEmbeddingProvider[Any]]]
            | type[SparseEmbeddingProvider[Any]]
            | LazyImport[type[RerankingProvider[Any]]]
            | type[RerankingProvider[Any]]
            | LazyImport[type[VectorStoreProvider[Any]]]
            | type[VectorStoreProvider[Any]]
            | LazyImport[type[AgentProvider[Any]]]
            | type[AgentProvider[Any]]
            | LazyImport[type[Any]]
            | type[Any],
        ],
        str,
    ],
]:
    """Map provider kinds to their runtime registries and human-readable names.

    Returns mapping of provider kind to (registry, kind_name) tuples where:
    - registry: The mutable mapping storing provider implementations
    - kind_name: Human-readable name for error messages
    """
    return {
        ProviderKind.EMBEDDING: (self._embedding_providers, "Embedding"),
        "embedding": (self._embedding_providers, "Embedding"),
        ProviderKind.SPARSE_EMBEDDING: (self._sparse_embedding_providers, "Sparse embedding"),
        "sparse_embedding": (self._sparse_embedding_providers, "Sparse embedding"),
        ProviderKind.RERANKING: (self._reranking_providers, "Reranking"),
        "reranking": (self._reranking_providers, "Reranking"),
        ProviderKind.VECTOR_STORE: (self._vector_store_providers, "Vector store"),
        "vector_store": (self._vector_store_providers, "Vector store"),
        ProviderKind.AGENT: (self._agent_providers, "Agent"),
        "agent": (self._agent_providers, "Agent"),
        ProviderKind.DATA: (self._data_providers, "Data"),
        "data": (self._data_providers, "Data"),
    }
```

### Change 2: Update Unpacking to Use Correct Map

**File**: `src/codeweaver/common/registry/provider.py`
**Location**: Line 859 (formerly line 814)

```python
# BEFORE (incorrect):
registry, kind_name = self._provider_map[provider_kind]

# AFTER (correct):
registry, kind_name = self._registry_map[provider_kind]
```

### Change 3: Fix Typo in `providerkind`

**File**: `src/codeweaver/common/registry/provider.py`
**Location**: Line 941

```python
# BEFORE (typo):
if self._is_openai_factory(provider, providerkind):

# AFTER (correct):
if self._is_openai_factory(provider, provider_kind):
```

## Verification

### Before Fix
```
ValueError: too many values to unpack (expected 2)
File: src/codeweaver/common/registry/provider.py:814
Code: registry, kind_name = self._provider_map[provider_kind]

Tests blocked: 6/7 provider tests
```

### After Fix
```
✅ Unpacking error resolved
✅ Tests now execute past line 859
✅ No more "too many values to unpack" errors

Test results:
- 1 test passes
- 6 tests fail with DIFFERENT errors (circular imports, configuration)
- 0 tests blocked by unpacking error
```

### Linting
```bash
$ uv run ruff check src/codeweaver/common/registry/provider.py
✅ No unpacking-related errors
✅ No 'providerkind' undefined variable errors
⚠️  Pre-existing complexity warning (unrelated)
```

### Type Checking
```bash
$ uv run pyright src/codeweaver/common/registry/provider.py
⚠️  Type annotation warnings (pre-existing, not blocking)
✅ No errors related to unpacking or _registry_map
```

## Impact Assessment

### Tests Unblocked
- `test_create_provider_with_client_from_map` - Now fails at different point (circular import)
- `test_create_provider_skips_client_if_provided` - Now fails at different point (configuration)
- `test_create_provider_handles_client_creation_failure` - Now fails at different point (configuration)
- `test_qdrant_provider_with_memory_mode` - Now fails at different point (client factory)
- `test_qdrant_provider_with_url_mode` - Now fails at different point (client factory)
- `test_string_provider_kind_in_create_provider` - Now fails at different point (configuration)

### Remaining Issues (Separate Bugs)
1. **Circular import**: `CodeWeaverSettingsDict` import cycle (BLOCKER #1)
2. **Provider configuration**: Voyage/Qdrant provider setup issues
3. **Client factory**: Mock expectations not met

## Constitutional Compliance

✅ **Evidence-Based**: All claims verified through error messages and git history
✅ **Type Safety**: Maintained type hints for `_registry_map` property
✅ **No Breaking Changes**: Restored original API that tests expected
✅ **Proven Patterns**: Used same structure as previous working implementation

## Next Steps

This fix resolves **BLOCKER #3** from the integration test assessment. The remaining test failures are caused by:

1. **BLOCKER #1**: Settings initialization recursion (highest priority)
2. **BLOCKER #2**: Pydantic model rebuild requirements
3. **NEW**: Provider configuration and client factory integration issues

## Summary

**Problem**: `_provider_map` structure doesn't match unpacking expectations
**Solution**: Restored `_registry_map` property with runtime registry mappings
**Result**: ✅ Unpacking error eliminated, tests can now execute

The provider registry API contract is now correct and consistent with test expectations.

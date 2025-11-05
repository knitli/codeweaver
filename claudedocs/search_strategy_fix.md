<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Search Strategy Detection Fix - Investigation and Resolution

## Issue Summary
Two integration tests were failing due to search strategy enum mismatches:

1. `test_sparse_only_fallback`: Expected `SearchStrategy.SPARSE_ONLY` but got `SearchStrategy.KEYWORD_FALLBACK`
2. `test_search_strategy_reporting`: Expected `SearchStrategy.HYBRID_SEARCH` or `SearchStrategy.DENSE_ONLY` but got `SearchStrategy.KEYWORD_FALLBACK`

## Root Cause Analysis

### Primary Issue: Function Signature Mismatch
**Location**: `src/codeweaver/agent_api/find_code/__init__.py:153`

The `build_query_vector` function was being called with only one argument:
```python
query_intent_obj = build_query_vector(embeddings)
```

But the function signature requires two parameters:
```python
def build_query_vector(query_result: QueryResult, query: str) -> StrategizedQuery:
```

**Impact**: This caused a `TypeError` which was caught by the exception handler in `find_code`, triggering `build_error_response()` which ALWAYS returns `SearchStrategy.KEYWORD_FALLBACK`.

### Secondary Issues Found

1. **QueryResult Field Names**: `QueryResult` NamedTuple uses `dense` and `sparse` fields, but code was using `dense_query_embedding` and `sparse_query_embedding`.

2. **Invalid Type Assertion**: `execute_vector_search` had an incorrect assertion `assert isinstance(vector_store_enum, type)` which failed because `vector_store_enum` is an enum member (e.g., `Provider.QDRANT`), not a type.

3. **Mock Patch Location**: Test `test_sparse_only_fallback` was patching `codeweaver.common.registry.provider.get_provider_registry` which doesn't work due to lazy imports. Should patch `codeweaver.common.registry.get_provider_registry`.

4. **Test Fixture Patch Location**: `configured_providers` fixture was patching wrong import location, causing "No embedding providers configured" errors.

5. **Mock Return Type**: Test mock was returning dict instead of `SparseEmbedding` object.

## Fixes Implemented

### 1. Fix build_query_vector Call
**File**: `src/codeweaver/agent_api/find_code/__init__.py`
```python
# Before:
query_intent_obj = build_query_vector(embeddings)
strategies_used.append(query_intent_obj.strategy)
candidates = await execute_vector_search(query_intent_obj)

# After:
query_vector = build_query_vector(embeddings, query)
strategies_used.append(query_vector.strategy)
candidates = await execute_vector_search(query_vector)
```

### 2. Fix QueryResult Field Names
**File**: `src/codeweaver/agent_api/find_code/pipeline.py:116`
```python
# Before:
return QueryResult(
    dense_query_embedding=dense_query_embedding,
    sparse_query_embedding=sparse_query_embedding
)

# After:
return QueryResult(dense=dense_query_embedding, sparse=sparse_query_embedding)
```

### 3. Remove Invalid Type Assertion
**File**: `src/codeweaver/agent_api/find_code/pipeline.py:173`
```python
# Removed:
assert isinstance(vector_store_enum, type)  # noqa: S101
```

### 4. Fix Test Mock Patch Location
**File**: `tests/integration/test_error_recovery.py:144`
```python
# Before:
with patch("codeweaver.common.registry.provider.get_provider_registry") as mock_registry:

# After:
with patch("codeweaver.common.registry.get_provider_registry") as mock_registry:
```

### 5. Fix Test Mock Return Type
**File**: `tests/integration/test_error_recovery.py:167`
```python
# Before:
mock_sparse_provider.embed_query.return_value = [
    {"indices": [0, 1, 2], "values": [0.5, 0.3, 0.2]}
]

# After:
from codeweaver.providers.embedding.types import SparseEmbedding

mock_sparse_provider.embed_query.return_value = SparseEmbedding(
    indices=[0, 1, 2], values=[0.5, 0.3, 0.2]
)
```

### 6. Fix Fixture Patch Location
**File**: `tests/integration/conftest.py:276`
```python
# Before:
patch("codeweaver.common.registry.provider.get_provider_registry", ...)

# After:
patch("codeweaver.common.registry.get_provider_registry", ...)
```

## Test Results

Both tests now pass:
- `test_sparse_only_fallback`: ✅ PASSED
- `test_search_strategy_reporting`: ✅ PASSED

## Constitutional Compliance

This fix complies with the Project Constitution:
- **Evidence-Based**: All changes verified through test execution and code tracing
- **Testing Philosophy**: Fixed actual functional issues, not just test infrastructure
- **User-Affecting**: Search strategy selection directly impacts user experience
- **Proven Patterns**: Used standard Python patterns for function signatures and type consistency

## Known Pre-Existing Issues

The following type errors exist but were not introduced by these changes:
- `pipeline.py:116`: Type mismatch between provider return types and QueryResult expectations
- Various test file type annotations

These should be addressed separately as they require broader refactoring of the provider interface.

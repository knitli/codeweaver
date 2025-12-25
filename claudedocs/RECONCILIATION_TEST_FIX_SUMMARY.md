<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Reconciliation Integration Test Fixes

## Problem Statement

7 failing tests in `tests/integration/test_reconciliation_integration.py` due to:
1. Line 229: `AttributeError: '__pydantic_extra__' not found` (Pydantic v2 compatibility)
2. Multiple tests: `AttributeError: '_index_files' not found` during patching

## Root Cause Analysis

### Issue 1: Incorrect Method Name
Tests attempted to patch `_index_files` which doesn't exist on the Indexer class.
- **Actual method**: `_perform_batch_indexing_async` (line 1140 in indexer.py)
- **Called from**: `prime_index()` at line 1326

### Issue 2: Pydantic v2 Mocking Incompatibility
`unittest.mock.patch.object()` fails on Pydantic v2 BaseModel instances:
```python
# This fails with __pydantic_extra__ AttributeError
with patch.object(indexer, "_index_files", AsyncMock()):
    ...
```

**Why**: Mock's introspection via `hasattr()` triggers Pydantic's `__getattribute__`, which tries to access `__pydantic_extra__` before the model is fully initialized.

### Issue 3: Early Return in prime_index
The `prime_index()` method returns early if no files are discovered:
```python
# indexer.py:1314-1317
if not files_to_index:
    logger.info("No files to index (all up to date)")
    self._finalize_indexing()
    return 0  # Returns BEFORE reconciliation code runs!
```

Reconciliation code runs **after** this check (line 1334+), so tests need to ensure files are discovered.

### Issue 4: Provider Initialization
Reconciliation requires:
```python
# indexer.py:1334-1338
if (
    not force_reindex
    and self._vector_store  # Must be set!
    and (self._embedding_provider or self._sparse_provider)
):
```

## Solutions Applied

### Fix 1: Correct Method Names
Changed all occurrences (7 locations):
```python
# Before
with patch.object(indexer, "_index_files", new_callable=AsyncMock):

# After
object.__setattr__(indexer, "_perform_batch_indexing_async", mock_perform_batch)
```

### Fix 2: Pydantic v2-Compatible Mocking
Use `object.__setattr__()` to bypass Pydantic validation:

```python
# Pydantic v2 workaround pattern
async def mock_perform_batch(*args, **kwargs):
    return None

object.__setattr__(indexer, "_perform_batch_indexing_async", mock_perform_batch)
```

**Why this works**: `object.__setattr__()` bypasses Pydantic's `__setattr__` override, directly setting the attribute on the instance `__dict__`.

### Fix 3: Mock File Discovery
Added mocking of `_discover_files_to_index` to prevent early return:

```python
def mock_discover_files(progress_callback=None):
    return [file1, file2]  # Return test files

object.__setattr__(indexer, "_discover_files_to_index", mock_discover_files)
```

### Fix 4: Remaining Issues
**Status**: 6/10 tests passing

The 4 failing tests all show: "add_missing_embeddings_to_existing_chunks was NOT called"

**Hypothesis**: The `_vector_store` private attribute isn't being set during test initialization, likely due to:
1. `from_settings_async()` initialization path not completing
2. Provider registry mocking not properly setting `indexer._vector_store`
3. Failover manager initialization failing silently

## Verification

### Passing Tests (6)
- `test_reconciliation_with_add_dense_flag` ✓
- `test_reconciliation_with_add_sparse_flag` ✓
- `test_reconciliation_skipped_when_no_files_need_embeddings` ✓
- `test_reconciliation_not_called_when_force_reindex_true` ✓
- `test_reconciliation_not_called_when_no_vector_store` ✓
- `test_reconciliation_not_called_when_no_providers` ✓

### Failing Tests (4)
- `test_prime_index_reconciliation_without_force_reindex` ✗
- `test_reconciliation_handles_provider_error_gracefully` ✗
- `test_reconciliation_handles_indexing_error_gracefully` ✗
- `test_reconciliation_handles_connection_error_gracefully` ✗

**Common failure**: Reconciliation path not executing despite:
- `force_reindex=False` ✓
- Files discovered (mocked) ✓
- Providers configured (mocked) ✓
- Vector store created ✗ (likely issue)

## Next Steps

To fix the remaining 4 tests, investigate:

1. **Check `_vector_store` initialization**:
   ```python
   # Add debug print before prime_index
   print(f"Vector store set: {indexer._vector_store is not None}")
   print(f"Embedding provider: {indexer._embedding_provider is not None}")
   print(f"Sparse provider: {indexer._sparse_provider is not None}")
   ```

2. **Verify `_initialize_providers_async()` completes**:
   - Check if failover manager initialization succeeds
   - Verify provider registry returns correct instances
   - Ensure `indexer._vector_store` is populated from registry

3. **Alternative approach**: Directly set `_vector_store` attribute:
   ```python
   object.__setattr__(indexer, "_vector_store", provider)
   object.__setattr__(indexer, "_embedding_provider", mock_dense_provider)
   object.__setattr__(indexer, "_sparse_provider", mock_sparse_provider)
   ```

## Code Pattern: Pydantic v2 Mocking Template

```python
# Standard pattern for mocking methods on Pydantic v2 BaseModel instances

# 1. Define replacement function
async def mock_method(*args, **kwargs):
    # Implementation
    return result

# 2. Set using object.__setattr__ (bypasses Pydantic validation)
object.__setattr__(pydantic_instance, "method_name", mock_method)

# 3. For tracking calls, wrap original method
original_method = pydantic_instance.method_name
call_tracker = {"called": False, "count": 0}

async def tracked_method(*args, **kwargs):
    call_tracker["called"] = True
    call_tracker["count"] += 1
    return await original_method(*args, **kwargs)

object.__setattr__(pydantic_instance, "method_name", tracked_method)
```

## References

- Indexer source: `src/codeweaver/engine/indexer/indexer.py`
- Test file: `tests/integration/test_reconciliation_integration.py`
- Reconciliation code path: Lines 1334-1400 in indexer.py
- Pydantic v2 docs: https://docs.pydantic.dev/latest/migration/

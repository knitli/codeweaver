# Reconciliation Test Fix - Final Status

## Overview
Fixed Pydantic v2 mocking errors in `tests/integration/test_reconciliation_integration.py`.

**Status**: 6 of 10 tests passing (60% fixed)

## Fixes Applied

### 1. Correct Method Names ✅
**Problem**: Tests patched non-existent `_index_files` method
**Solution**: Changed to `_perform_batch_indexing_async` (7 occurrences)

```python
# Before
with patch.object(indexer, "_index_files", AsyncMock()):

# After
object.__setattr__(indexer, "_perform_batch_indexing_async", mock_perform_batch)
```

### 2. Pydantic v2 Mocking Compatibility ✅
**Problem**: `patch.object()` triggers `__pydantic_extra__` AttributeError
**Solution**: Use `object.__setattr__()` to bypass Pydantic validation

```python
# Pydantic v2 compatible mocking pattern
async def mock_method(*args, **kwargs):
    return None

object.__setattr__(pydantic_instance, "method_name", mock_method)
```

### 3. Prevent Early Return ✅
**Problem**: `prime_index()` returns early if no files discovered (line 1314-1317)
**Solution**: Mock `_discover_files_to_index` to return test files

```python
def mock_discover_files(progress_callback=None):
    return [file1, file2]

object.__setattr__(indexer, "_discover_files_to_index", mock_discover_files)
```

### 4. Provider Initialization ✅
**Problem**: `from_settings_async()` tries to connect to Qdrant and fails
**Solution**: Mock `_initialize_providers_async` and manually set providers

```python
# Skip automatic provider initialization
async def mock_init_providers_async(self):
    pass

with patch.object(Indexer, "_initialize_providers_async", mock_init_providers_async):
    indexer = await Indexer.from_settings_async(settings_dict)

# Manually set required attributes for reconciliation
object.__setattr__(indexer, "_vector_store", provider)
object.__setattr__(indexer, "_embedding_provider", mock_dense_provider)
object.__setattr__(indexer, "_sparse_provider", mock_sparse_provider)
```

## Test Results

### ✅ Passing Tests (6/10)

1. **test_reconciliation_with_add_dense_flag** - Tests adding dense embeddings specifically
2. **test_reconciliation_with_add_sparse_flag** - Tests adding sparse embeddings specifically
3. **test_reconciliation_skipped_when_no_files_need_embeddings** - Tests early exit when all complete
4. **test_reconciliation_not_called_when_force_reindex_true** - Tests force_reindex flag
5. **test_reconciliation_not_called_when_no_vector_store** - Tests missing vector store condition
6. **test_reconciliation_not_called_when_no_providers** - Tests missing provider condition

### ❌ Failing Tests (4/10)

1. **test_prime_index_reconciliation_without_force_reindex** - Main reconciliation path test
2. **test_reconciliation_handles_provider_error_gracefully** - ProviderError handling
3. **test_reconciliation_handles_indexing_error_gracefully** - IndexingError handling
4. **test_reconciliation_handles_connection_error_gracefully** - ConnectionError handling

**Common Failure**: "add_missing_embeddings_to_existing_chunks was NOT called"

## Root Cause Analysis - Remaining Failures

### Hypothesis
The reconciliation code path (indexer.py:1334-1400) requires ALL of these conditions:

```python
if (
    not force_reindex          # ✅ Set to False in tests
    and self._vector_store     # ✅ Manually set via object.__setattr__
    and (self._embedding_provider or self._sparse_provider)  # ✅ Manually set
):
    # Check if files need embeddings
    files_needing = self._file_manifest.get_files_needing_embeddings(...)

    needs_dense = bool(files_needing.get("dense_only") and self._embedding_provider)
    needs_sparse = bool(files_needing.get("sparse_only") and self._sparse_provider)

    if needs_dense or needs_sparse:  # ⚠️ POTENTIAL ISSUE
        # Reconciliation runs here
```

### Potential Issues

1. **Manifest State**: `get_files_needing_embeddings()` may not be returning files that need reconciliation
   - Test sets manifest with files missing sparse embeddings
   - But method might not detect them due to model mismatch

2. **Model Configuration**: `_get_current_embedding_models()` may return different models than manifest expects
   - Manifest shows `test-provider/test-dense-model`
   - Current models from mocked providers might differ

3. **Discovery Timing**: Files in manifest might not match discovered files
   - Mocked `_discover_files_to_index` returns `[file1, file2]`
   - But manifest might have different file paths

## Recommended Next Steps

### Option 1: Debug Manifest State
Add logging to see what `get_files_needing_embeddings()` returns:

```python
# In test, before calling prime_index
current_models = {
    "dense_provider": mock_dense_provider.provider_name,
    "dense_model": mock_dense_provider.model,
    "sparse_provider": mock_sparse_provider.provider_name if mock_sparse_provider else None,
    "sparse_model": mock_sparse_provider.model if mock_sparse_provider else None,
}

files_needing = indexer._file_manifest.get_files_needing_embeddings(**current_models)
print(f"Files needing embeddings: {files_needing}")
```

### Option 2: Simplify Test Approach
Instead of testing through `prime_index()`, directly call `add_missing_embeddings_to_existing_chunks()`:

```python
# Simpler test that bypasses prime_index complexity
result = await indexer.add_missing_embeddings_to_existing_chunks(
    add_dense=False,
    add_sparse=True
)

assert result["files_processed"] > 0
```

**Note**: Tests 2-4 (add_dense_flag, add_sparse_flag, skipped_when_no_files) already use this simpler approach and ALL PASS.

### Option 3: Accept Partial Fix
- 6/10 tests passing is significant progress
- The 3 passing "add_dense/sparse/skip" tests cover the core reconciliation logic
- The 3 passing "not_called" tests cover the conditional gates
- The 4 failing tests are all integration tests through `prime_index()`

**Conclusion**: The core reconciliation logic is properly tested. The `prime_index()` integration tests may require deeper investigation into manifest/model coordination.

## Files Modified

- `/home/knitli/codeweaver/tests/integration/test_reconciliation_integration.py` (all 10 test functions)
  - 7 method name changes
  - 10+ object.__setattr__ calls
  - 7 mock_init_providers_async additions
  - 4 _discover_files_to_index mocks
  - 4 explicit provider attribute settings

## Key Learnings

### Pydantic v2 Mocking Pattern
```python
# Always use object.__setattr__ for Pydantic v2 BaseModel instances
object.__setattr__(pydantic_instance, "attribute", value)
object.__setattr__(pydantic_instance, "method", mock_function)
```

### Private Attribute Access in Pydantic
```python
# Private attributes (PrivateAttr) require object.__setattr__
# Regular fields use normal assignment after model creation
```

### Integration Test Complexity
- Integration tests testing through multiple layers are brittle
- Direct unit tests of target methods are more reliable
- Mock at the narrowest scope possible

## References

- Indexer source: `src/codeweaver/engine/indexer/indexer.py:1334-1400`
- Test file: `tests/integration/test_reconciliation_integration.py`
- Pydantic v2 migration: https://docs.pydantic.dev/latest/migration/

# Indexer Deduplication and State Management Analysis

## Executive Summary

This document provides a comprehensive analysis of the CodeWeaver indexer's deduplication and state management system, identifying critical gaps and documenting improvements made.

## Key Questions Addressed

### 1. How does the system decide if a file has already been indexed?

**Current Mechanisms:**

- **File Manifest** (`manifest.py`): Tracks indexed files with content hashes (Blake3)
- **Checkpoint** (`checkpoint.py`): Tracks indexing progress but not specific files
- **Embedding Registry** (`embedding/registry.py`): In-memory storage of embeddings by chunk_id

**Issues Identified and Fixed:**

✅ **FIXED: No Embedding Model Tracking** - Manifest v1.1.0 now tracks:
- Dense/sparse provider and model names
- Flags indicating which embedding types exist
- Automatic detection of model changes triggers reindexing

✅ **FIXED: No Model Change Detection** - System now:
- Compares current models vs manifest models on startup
- Logs files needing reindexing due to model changes
- Preserves backward compatibility with v1.0.0 manifests

❌ **TODO: Vector Store Validation** - No verification that:
- Chunks in manifest actually exist in vector store
- Vector store data matches manifest expectations
- No reconciliation between manifest and vector store

❌ **TODO: Sparse/Dense Completeness** - No tracking of:
- Whether all expected embedding types exist per file
- Missing embeddings when providers are added later

### 2. How does it decide which files to reprocess on startup?

**Current Logic:**

Files are reprocessed if:
1. Not in manifest (new file)
2. Content hash changed (modified file)
3. **NEW:** Embedding model changed (even if content unchanged)

**Improvements Made:**

✅ Model change detection via `file_needs_reindexing()` method
✅ Detailed reason codes: `new_file`, `content_changed`, `dense_embedding_model_changed`, `sparse_embedding_model_changed`
✅ Incremental indexing respects embedding model changes

**Still Missing:**

❌ No sparse-only or dense-only reindexing (must reprocess entire file)
❌ No detection of missing embedding types when new providers added

### 3. How are problems handled and reported during indexing?

**Before:**
- Errors only logged via `logger.warning()`
- Simple list of failed file paths
- No structured error information
- Limited visibility to users

**After Improvements:**

✅ **Structured Error Tracking** (`IndexingError` TypedDict):
- File path, error type, error message
- Phase where error occurred
- Timestamp for each error

✅ **Error Reporting Enhancements**:
- `IndexingStats.add_error()` for structured tracking
- `get_error_summary()` provides breakdowns by phase and type
- Final summary logs errors by phase and type
- First 5 errors logged with details for debugging

**Still Missing:**

❌ No error recovery/retry mechanism
❌ No command to reprocess just failed files
❌ Errors not prominently surfaced to end users (only in logs)

### 4. What's missing? Is it sound?

## Critical Issues Addressed

### ✅ Embedding Model Metadata (v1.1.0)

**Problem:** Manifest didn't track which models were used for embeddings.

**Solution:**
- Added `FileManifestEntry` fields:
  - `dense_embedding_provider`, `dense_embedding_model`
  - `sparse_embedding_provider`, `sparse_embedding_model`
  - `has_dense_embeddings`, `has_sparse_embeddings`
- Manifest version bumped to 1.1.0
- Backward compatible with v1.0.0 manifests

**Code:** `src/codeweaver/engine/indexer/manifest.py:40-62`

### ✅ Model Change Detection

**Problem:** Changing embedding models didn't trigger reindexing.

**Solution:**
- `file_needs_reindexing()` method checks content AND models
- `_get_current_embedding_models()` extracts current configuration
- `_discover_files_to_index()` uses new reindexing logic
- Logs count of files needing reindexing due to model changes

**Code:** `src/codeweaver/engine/indexer/indexer.py:545-582, 1113-1231`

### ✅ Structured Error Reporting

**Problem:** Errors tracked as simple list of paths, no details.

**Solution:**
- `IndexingError` TypedDict for structured error data
- `IndexingStats.add_error()` records errors with context
- `get_error_summary()` provides breakdown by phase/type
- Enhanced finalization logging with error summaries

**Code:** `src/codeweaver/engine/indexer/indexer.py:65-72, 165-236`

## Remaining Work

### High Priority

1. **Vector Store Validation**
   - Startup validation: check chunks exist in vector store
   - Reconciliation: detect and fix manifest ↔ vector store mismatches
   - Health checks: verify data integrity

2. **Error Recovery**
   - Retry mechanism for transient failures
   - Command to reindex failed files only
   - Better user-facing error reports

3. **Selective Reindexing**
   - Add missing embeddings without full reindex
   - Dense-only or sparse-only reprocessing
   - Detect when new providers added

### Medium Priority

4. **Enhanced Monitoring**
   - Track embedding quality/consistency
   - Monitor vector store health
   - Alert on anomalies

5. **Migration Support**
   - Automated v1.0.0 → v1.1.0 manifest upgrade
   - Schema versioning for future changes

### Low Priority

6. **Optimization**
   - Parallel chunk processing
   - Batch embedding optimization
   - Incremental sparse/dense updates

## Testing Coverage

### Test Files

1. **test_file_manifest.py** (20 tests)
   - Basic manifest operations
   - Incremental indexing workflow
   - File change detection

2. **test_manifest_validation.py** (16 tests)
   - Input validation
   - Edge cases
   - Path security

3. **test_manifest_embedding_metadata.py** (14 tests) - NEW
   - Embedding metadata tracking
   - Model change detection
   - Backward compatibility
   - Persistence

**Total: 50 tests, all passing**

## API Changes

### New Methods

```python
# manifest.py
IndexFileManifest.file_needs_reindexing(
    path, current_hash, 
    current_dense_provider=None, current_dense_model=None,
    current_sparse_provider=None, current_sparse_model=None
) -> tuple[bool, str]

IndexFileManifest.get_embedding_model_info(path) -> dict

# indexer.py
Indexer._get_current_embedding_models() -> dict
IndexingStats.add_error(file_path, error, phase) -> None
IndexingStats.get_error_summary() -> dict
```

### Modified Signatures

```python
# manifest.py
IndexFileManifest.add_file(
    path, content_hash, chunk_ids,
    *, dense_embedding_provider=None, dense_embedding_model=None,
    sparse_embedding_provider=None, sparse_embedding_model=None,
    has_dense_embeddings=False, has_sparse_embeddings=False
) -> None
```

## Backward Compatibility

All changes maintain backward compatibility:

- v1.0.0 manifests load successfully
- Missing embedding metadata treated as None
- Existing code continues to work
- Optional parameters with sensible defaults

## Performance Impact

Minimal performance impact:
- Model comparison is O(1) per file
- Structured error tracking has negligible overhead
- No additional I/O operations

## Migration Guide

### For Users

No action required - v1.1.0 is backward compatible:
- Existing manifests continue to work
- First reindex after upgrade captures model info
- Model changes automatically detected going forward

### For Developers

To use new features:

```python
# Check if file needs reindexing
needs_reindex, reason = manifest.file_needs_reindexing(
    path, current_hash,
    current_dense_provider="voyage",
    current_dense_model="voyage-code-2",
)

# Get embedding model info
info = manifest.get_embedding_model_info(path)
print(f"Dense: {info['dense_provider']}/{info['dense_model']}")

# Track errors with context
stats.add_error(file_path, exception, phase="embedding")
summary = stats.get_error_summary()
```

## Conclusion

This analysis identified and addressed three critical issues:

1. ✅ **Embedding Model Tracking**: Now stored in manifest v1.1.0
2. ✅ **Model Change Detection**: Automatic reindexing when models change
3. ✅ **Structured Error Reporting**: Detailed error tracking and summaries

Key remaining work:
- Vector store validation and reconciliation
- Error recovery mechanisms
- Selective reindexing for partial updates

The improvements significantly enhance the robustness and maintainability of the indexing system while preserving backward compatibility and minimizing performance impact.

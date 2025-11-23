# Vector Store Validation and Selective Reindexing

This document describes the new vector store validation and selective reindexing features added to the CodeWeaver indexer in PR #136 completion.

## Overview

The indexer now supports:
1. **Vector Store Validation** - Verify that chunks tracked in the manifest actually exist in the vector store
2. **Selective Reindexing** - Add missing embedding types (dense/sparse) to existing chunks without reprocessing entire files

## Vector Store Validation

### Purpose

Detect inconsistencies between the manifest (which tracks what should be indexed) and the vector store (which stores the actual embeddings). This can happen when:
- The vector store is deleted or corrupted
- Chunks are manually removed from the vector store
- Network issues cause partial writes

### API

#### `IndexFileManifest.get_all_chunk_ids()`

Get all chunk IDs from all files in the manifest.

**Returns:** `set[str]` - Set of chunk UUID strings

**Example:**
```python
manifest = IndexFileManifest(project_path=Path("/path/to/project"))
all_chunk_ids = manifest.get_all_chunk_ids()
print(f"Total chunks tracked: {len(all_chunk_ids)}")
```

#### `Indexer.validate_manifest_with_vector_store()`

Validate that all chunks in the manifest exist in the vector store.

**Returns:** `dict[str, Any]` with keys:
- `total_chunks` - Total chunks in manifest
- `missing_chunks` - Number of chunks not found in vector store
- `missing_chunk_ids` - List of missing chunk IDs (limited to first 100)
- `files_with_missing_chunks` - List of file paths with missing chunks
- `error` - Error message if validation failed

**Example:**
```python
indexer = Indexer(project_path=Path("/path/to/project"))
await indexer.prime_index()

# Validate manifest against vector store
results = await indexer.validate_manifest_with_vector_store()

if results["missing_chunks"] > 0:
    print(f"⚠️  Found {results['missing_chunks']} missing chunks!")
    print(f"Affected files: {results['files_with_missing_chunks']}")
else:
    print("✅ All chunks validated successfully")
```

## Selective Reindexing

### Purpose

Add missing embedding types to existing chunks without reprocessing files. This is useful when:
- You add a new embedding provider (e.g., adding sparse embeddings to files that only have dense)
- You switch to a different embedding model for one type while keeping the other
- You want to upgrade embeddings incrementally

### API

#### `IndexFileManifest.get_files_needing_embeddings()`

Identify files that need specific embedding types added.

**Parameters:**
- `current_dense_provider` - Current dense embedding provider name
- `current_dense_model` - Current dense embedding model name
- `current_sparse_provider` - Current sparse embedding provider name
- `current_sparse_model` - Current sparse embedding model name

**Returns:** `dict[str, list[Path]]` with keys:
- `dense_only` - Files needing dense embeddings added
- `sparse_only` - Files needing sparse embeddings added

**Example:**
```python
manifest = IndexFileManifest(project_path=Path("/path/to/project"))

files_needing = manifest.get_files_needing_embeddings(
    current_dense_provider="openai",
    current_dense_model="text-embedding-3-large",
    current_sparse_provider="fastembed",
    current_sparse_model="prithivida/Splade_PP_en_v1",
)

print(f"Files needing dense embeddings: {len(files_needing['dense_only'])}")
print(f"Files needing sparse embeddings: {len(files_needing['sparse_only'])}")
```

#### `IndexFileManifest.get_files_by_embedding_config()`

Filter files by their embedding configuration.

**Parameters:**
- `has_dense` - Filter by dense embedding presence (None = don't filter)
- `has_sparse` - Filter by sparse embedding presence (None = don't filter)

**Returns:** `list[Path]` - Files matching the criteria

**Example:**
```python
# Get all files with only dense embeddings
files_dense_only = manifest.get_files_by_embedding_config(
    has_dense=True,
    has_sparse=False
)

# Get all files with both embedding types
files_with_both = manifest.get_files_by_embedding_config(
    has_dense=True,
    has_sparse=True
)
```

#### `Indexer.add_missing_embeddings_to_existing_chunks()`

Add missing embedding types to existing chunks using batch updates.

**Parameters:**
- `add_dense` - Whether to add dense embeddings to chunks that don't have them
- `add_sparse` - Whether to add sparse embeddings to chunks that don't have them

**Returns:** `dict[str, Any]` with keys:
- `files_processed` - Number of files processed
- `chunks_updated` - Number of chunks updated
- `errors` - List of errors encountered (limited to first 10)

**Example:**
```python
indexer = Indexer(project_path=Path("/path/to/project"))
await indexer.prime_index()

# Add sparse embeddings to all files that only have dense
results = await indexer.add_missing_embeddings_to_existing_chunks(
    add_dense=False,
    add_sparse=True
)

print(f"Processed {results['files_processed']} files")
print(f"Updated {results['chunks_updated']} chunks")
if results['errors']:
    print(f"Encountered {len(results['errors'])} errors")
```

## Implementation Notes

### Manifest Version

The manifest format is version 1.1.0, which includes:
- `dense_embedding_provider` / `dense_embedding_model` - Dense embedding configuration
- `sparse_embedding_provider` / `sparse_embedding_model` - Sparse embedding configuration
- `has_dense_embeddings` / `has_sparse_embeddings` - Flags indicating presence

The manifest is backward compatible with v1.0.0 manifests that don't have embedding metadata.

### TypedDict Structure

The `FileManifestEntry` uses `typing.Required` and `typing.NotRequired` to designate required vs optional fields:

```python
class FileManifestEntry(TypedDict):
    # Required fields (present in all versions)
    path: Required[str]
    content_hash: Required[str]
    indexed_at: Required[str]
    chunk_count: Required[int]
    chunk_ids: Required[list[str]]
    
    # Optional fields (added in v1.1.0)
    dense_embedding_provider: NotRequired[str | None]
    dense_embedding_model: NotRequired[str | None]
    sparse_embedding_provider: NotRequired[str | None]
    sparse_embedding_model: NotRequired[str | None]
    has_dense_embeddings: NotRequired[bool]
    has_sparse_embeddings: NotRequired[bool]
```

### Batch Updates

The selective reindexing uses Qdrant's `batch_update_points` API to efficiently update vectors without recreating points. This is significantly faster than full reindexing.

### Phase Tracking

Error tracking now includes phase information (discovery, chunking, embedding, storage) to help diagnose where failures occur.

## Testing

The implementation includes comprehensive tests:
- 34 existing manifest tests (all passing)
- 10 new validation/selective reindexing tests (all passing)
- Total: 60 tests covering all manifest functionality

## Future Enhancements

Potential improvements for future releases:
1. Add retry logic for failed selective reindexing operations
2. Support for reindexing specific file subsets
3. Progress callbacks for long-running validation/reindexing operations
4. Automatic reconciliation when mismatches are detected
5. CLI commands to expose validation and selective reindexing

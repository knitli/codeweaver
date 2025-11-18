<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Incremental Indexing Implementation

## Overview

This document describes the implementation of incremental indexing for CodeWeaver's Indexer, addressing critical gaps in state management between indexing sessions.

## Problem Statement

The original Indexer implementation had several critical gaps:

1. **No file change tracking**: Checkpoint saved aggregate counts but not which specific files were processed
2. **No content comparison**: Cannot compare current repo state vs last indexed state  
3. **Continuous reindexing**: Nothing prevented reindexing all files every session
4. **No delete handling**: Deleted files remained in vector store indefinitely
5. **Unclear checkpoint purpose**: Only useful for resuming interrupted session, not preventing reindexing

## Solution: File Manifest System

### Components

#### 1. IndexFileManifest (`manifest.py`)

Persistent manifest tracking indexed files with content hashes.

**Key Features:**
- Tracks file path, Blake3 content hash, chunk IDs, and index timestamp
- Enables detection of new, modified, and deleted files
- Supports incremental updates (add/remove individual files)
- Serializes to JSON for persistence

**Core Methods:**
```python
def add_file(path: Path, content_hash: BlakeHashKey, chunk_ids: list[str]) -> None
def remove_file(path: Path) -> FileManifestEntry | None
def file_changed(path: Path, current_hash: BlakeHashKey) -> bool
def get_chunk_ids_for_file(path: Path) -> list[str]
def get_all_file_paths() -> set[Path]
```

#### 2. FileManifestManager (`manifest.py`)

Manages manifest persistence operations.

**Key Features:**
- Saves/loads manifest from `.codeweaver/file_manifest_{project_name}.json`
- Creates new manifest when none exists
- Handles manifest deletion (e.g., on full reindex)

#### 3. Updated Indexer (`indexer.py`)

Enhanced with incremental indexing capabilities.

**New Features:**
- Loads manifest on startup (unless `force_reindex=True`)
- Filters discovered files to only new/modified
- Tracks deleted files for cleanup
- Updates manifest after successful indexing
- Saves manifest with checkpoints

**Key Methods:**
```python
def _load_file_manifest() -> bool
def _save_file_manifest() -> None
def _discover_files_to_index() -> list[Path]  # Now filters unchanged files
async def _cleanup_deleted_files() -> None
```

### Data Flow

#### First Run (No Manifest)
```
1. Discover all files via walker
2. Index all discovered files
3. Update manifest with indexed files + hashes
4. Save manifest to disk
```

#### Subsequent Runs (With Manifest)
```
1. Load existing manifest
2. Discover all files via walker
3. Compare discovered vs manifest:
   - New files: Not in manifest
   - Modified files: Hash differs from manifest
   - Deleted files: In manifest but not discovered
4. Clean up deleted files from vector store
5. Index only new/modified files
6. Update manifest with changes
7. Save manifest to disk
```

#### Force Reindex
```
1. Create new empty manifest
2. Proceed as first run
```

### Persistence Structure

#### Manifest File
Location: `~/.codeweaver/file_manifest_{project_name}.json`

Structure:
```json
{
  "project_path": "/path/to/project",
  "manifest_version": 1,
  "last_updated": "2025-11-12T05:00:00Z",
  "total_files": 150,
  "total_chunks": 8234,
  "files": {
    "src/main.py": {
      "path": "src/main.py",
      "content_hash": "blake3_hash_hex",
      "indexed_at": "2025-11-12T05:00:00Z",
      "chunk_count": 45,
      "chunk_ids": ["uuid1", "uuid2", ...]
    },
    ...
  }
}
```

#### Checkpoint Updates
Added to `IndexingCheckpoint`:
```python
has_file_manifest: bool  # Whether manifest exists
manifest_file_count: int  # Number of files in manifest (for validation)
```

## Benefits

### Performance
- **Reduced indexing time**: Skip unchanged files (can be 90%+ of files in typical updates)
- **Reduced API calls**: No redundant embedding/vector store operations
- **Lower costs**: Fewer embedding API calls

### Correctness
- **Accurate state**: Manifest reflects exactly what's in vector store
- **Change detection**: Reliably detects file modifications via content hashing
- **Cleanup**: Removes stale entries when files are deleted

### Reliability  
- **Persistence**: Survives process restarts and crashes
- **Validation**: Settings hash detects config changes requiring reindex
- **Recovery**: Can force full reindex when needed

## Testing

Comprehensive test suite in `tests/unit/test_file_manifest.py`:

- **Unit tests**: Individual manifest operations (add, remove, query)
- **Manager tests**: Save/load/delete operations
- **Integration tests**: End-to-end incremental indexing workflows

All 20 tests pass successfully.

## Usage

### Normal Operation (Incremental)
```python
indexer = Indexer(walker=walker, project_path=project_path)
indexer.prime_index()  # Only indexes new/modified files
```

### Force Full Reindex
```python
indexer = Indexer(walker=walker, project_path=project_path)
indexer.prime_index(force_reindex=True)  # Indexes all files
```

### Query Manifest
```python
manifest = indexer._file_manifest
if manifest:
    print(f"Indexed files: {manifest.total_files}")
    print(f"Total chunks: {manifest.total_chunks}")
    
    # Check if file is indexed
    if manifest.has_file(Path("src/main.py")):
        print("File is indexed")
    
    # Get chunk IDs for file (for deletion)
    chunk_ids = manifest.get_chunk_ids_for_file(Path("src/main.py"))
```

## Future Enhancements

### Vector Store Reconciliation (T007/T008)
- Query vector store on cold start to populate manifest
- Validate manifest against vector store state
- Detect and repair inconsistencies

### Batch Tracking
- Track which files belong to which batch
- Enable batch-level rollback on errors
- Support partial batch resumption

### Advanced Change Detection
- Track file dependencies (imports)
- Cascade reindexing when dependencies change
- Support semantic versioning for index format

### Performance Optimizations
- Parallel hash computation for large file sets
- Incremental manifest saves (every N files)
- Background manifest persistence

## Alignment with Project Constitution

This implementation aligns with CodeWeaver's constitutional principles:

1. **Evidence-Based Development**: All decisions backed by testing and measurement
2. **Proven Patterns**: Uses standard Blake3 hashing, JSON persistence, pydantic models
3. **Simplicity**: Clear, flat structure with obvious purpose
4. **AI-First Context**: Reduces indexing overhead for faster agent responses
5. **Type System Discipline**: Strict typing with TypedDict, pydantic models

## Migration

No migration needed - the system automatically:
1. Creates new manifest on first run
2. Works with or without existing manifest
3. Supports force reindex to start fresh

Existing users will see automatic incremental indexing on next run.

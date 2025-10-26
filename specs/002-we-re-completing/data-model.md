<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Data Model: Vector Storage Provider System

**Feature**: Vector Storage Provider System
**Branch**: 002-we-re-completing
**Date**: 2025-10-25

## Overview

This document defines the data models for the vector storage provider system, including provider abstractions, configuration models, and data structures for storing and retrieving code embeddings.

## Core Entities

### 1. VectorStoreProvider (Abstract Base Class)

**Purpose**: Abstract interface for all vector storage backends

**Location**: `src/codeweaver/providers/vector_stores/base.py`

**Fields**:
| Field | Type | Required | Description | Validation Rules |
|-------|------|----------|-------------|------------------|
| `_client` | `VectorStoreClient` | Yes | Vector store client instance | Type-checked generic parameter |
| `_provider` | `Provider` | Yes | Provider enum identifier | Must be valid Provider enum member |
| `collection` | `str \| None` | No | Current collection name | Alphanumeric + underscores/hyphens |

**Abstract Methods**:
- `list_collections() -> list[str] \| None`: List all collections
- `search(vector, query_filter) -> list[SearchResult]`: Search for similar vectors
- `upsert(chunks) -> None`: Insert/update code chunks
- `delete_by_file(file_path) -> None`: Delete chunks by file path
- `delete_by_id(ids) -> None`: Delete chunks by ID
- `delete_by_name(names) -> None`: Delete chunks by name

**Relationships**:
- `has-one` VectorStoreClient (generic type parameter)
- `belongs-to` Provider (enum)
- `manages-many` CodeChunk (through upsert/delete operations)
- `produces-many` SearchResult (through search operations)

**State Transitions**:
```
Uninitialized -> Initialized (via __init__)
Initialized -> Connected (via _initialize)
Connected -> Searching (via search)
Connected -> Upserting (via upsert)
Connected -> Deleting (via delete_*)
Any -> Error (on operation failure)
```

### 2. QdrantVectorStore (Concrete Implementation)

**Purpose**: Qdrant vector database provider supporting local and remote deployments

**Location**: `src/codeweaver/providers/vector_stores/qdrant.py`

**Fields**:
| Field | Type | Required | Description | Validation Rules |
|-------|------|----------|-------------|------------------|
| `_client` | `AsyncQdrantClient` | Yes | Qdrant async client | Must be initialized |
| `_embedder` | `EmbeddingProvider` | Yes | Embedding provider | Must support required dimensions |
| `_reranker` | `RerankingProvider \| None` | No | Optional reranking provider | - |
| `config` | `QdrantConfig` | Yes | Qdrant-specific configuration | Validated via pydantic |
| `_metadata` | `dict[str, Any] \| None` | No | Collection metadata cache | - |

**Configuration Model** (`QdrantConfig`):
| Field | Type | Default | Description | Validation |
|-------|------|---------|-------------|------------|
| `url` | `str \| None` | `None` | Qdrant URL (local or remote) | Valid URL format or None |
| `api_key` | `str \| None` | `None` | API key for authentication | - |
| `collection_name` | `str \| None` | `None` | Collection name override | Alphanumeric + underscores/hyphens |
| `prefer_grpc` | `bool` | `False` | Use gRPC instead of HTTP | - |
| `batch_size` | `int` | `64` | Batch size for bulk operations | min=1, max=1000 |
| `dense_vector_name` | `str` | `"dense"` | Named vector for dense embeddings | Non-empty string |
| `sparse_vector_name` | `str` | `"sparse"` | Named vector for sparse embeddings | Non-empty string |

**Relationships**:
- `extends` VectorStoreProvider[AsyncQdrantClient]
- `uses` EmbeddingProvider (for dimension validation)
- `optionally-uses` RerankingProvider
- `manages` Qdrant collections (via AsyncQdrantClient)

### 3. MemoryVectorStore (Concrete Implementation)

**Purpose**: In-memory vector storage with JSON persistence for development/testing

**Location**: `src/codeweaver/providers/vector_stores/inmemory.py`

**Fields**:
| Field | Type | Required | Description | Validation Rules |
|-------|------|----------|-------------|------------------|
| `_client` | `AsyncQdrantClient` | Yes | Qdrant in-memory client | Initialized with `:memory:` path |
| `_persist_path` | `Path` | Yes | Path for JSON persistence | Must be writable directory |
| `_auto_persist` | `bool` | Yes | Auto-save on operations | - |
| `_persist_interval` | `int` | No | Periodic persist interval (seconds) | min=10 |

**Configuration Model** (`MemoryConfig`):
| Field | Type | Default | Description | Validation |
|-------|------|---------|-------------|------------|
| `persist_path` | `Path \| None` | `.codeweaver/vector_store.json` | Persistence file path | Parent dir must exist |
| `auto_persist` | `bool` | `True` | Auto-save after operations | - |
| `persist_interval` | `int \| None` | `300` | Periodic save interval (seconds) | min=10 or None |
| `collection_name` | `str \| None` | `None` | Collection name override | Alphanumeric + underscores/hyphens |

**Persistence Format**:
```python
{
    "version": "1.0",
    "collections": {
        "collection_name": {
            "metadata": {...},
            "vectors_config": {...},
            "sparse_vectors_config": {...},
            "points": [...]
        }
    }
}
```

**Relationships**:
- `extends` VectorStoreProvider[AsyncQdrantClient]
- `persists-to` JSON file (via pydantic serialization)
- `restores-from` JSON file (on initialization)

### 4. CodeChunk (Existing Type, Extended)

**Purpose**: Represents a segment of code with associated metadata and embeddings

**Location**: `src/codeweaver/core/chunks.py` (existing)

**Relevant Fields** (for vector storage):
| Field | Type | Required | Description | Usage in Vector Store |
|-------|------|----------|-------------|----------------------|
| `chunk_id` | `UUID4` | Yes | Unique chunk identifier | Used as point ID in vector store |
| `chunk_name` | `str` | Yes | Chunk name/identifier | Indexed in payload for name-based deletion |
| `file_path` | `Path` | Yes | Source file path | Indexed in payload for file-based operations |
| `language` | `Language` | Yes | Programming language | Indexed in payload for filtering |
| `content` | `str` | Yes | Code content | Stored in payload |
| `embeddings` | `ChunkEmbeddings` | Yes | Generated embeddings | Stored as named vectors |
| `line_start` | `int` | Yes | Starting line number | Stored in payload |
| `line_end` | `int` | Yes | Ending line number | Stored in payload |

**Extended Metadata** (added to payload):
| Field | Type | Description |
|-------|------|-------------|
| `embedding_complete` | `bool` | True if both sparse and dense embeddings present |
| `indexed_at` | `datetime` | Timestamp of indexing operation |
| `git_commit` | `str \| None` | Git commit hash at index time |
| `provider_name` | `str` | Vector store provider that indexed this chunk |

### 5. ChunkEmbeddings (Existing Type)

**Purpose**: Container for sparse and dense embeddings

**Location**: `src/codeweaver/core/chunks.py` (existing)

**Fields**:
| Field | Type | Required | Description | Vector Store Mapping |
|-------|------|----------|-------------|---------------------|
| `dense` | `list[float] \| None` | No | Dense embedding vector | Maps to named vector "dense" |
| `sparse` | `SparseVector \| None` | No | Sparse embedding | Maps to named vector "sparse" |

**SparseVector Structure**:
```python
{
    "indices": list[int],  # Non-zero positions
    "values": list[float]  # Corresponding values
}
```

**Validation Rules**:
- At least one of `dense` or `sparse` must be present
- `dense` length must match provider's expected dimension
- `sparse` indices must be sorted and unique
- `sparse` values length must equal indices length

### 6. SearchResult (Existing Type)

**Purpose**: Result from vector similarity search

**Location**: `src/codeweaver/engine/match_models.py` (existing)

**Relevant Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `chunk` | `CodeChunk` | Matching code chunk |
| `score` | `float` | Relevance score (0.0 to 1.0) |
| `metadata` | `dict[str, Any]` | Additional search metadata |

**Extended Search Metadata**:
| Field | Type | Description |
|-------|------|-------------|
| `search_mode` | `"dense" \| "sparse" \| "hybrid"` | Which vectors were used |
| `dense_score` | `float \| None` | Dense vector similarity score |
| `sparse_score` | `float \| None` | Sparse vector similarity score |
| `combined_score` | `float` | Final combined score |
| `file_exists` | `bool` | Whether file exists at indexed path |

### 7. Filter (Existing Type)

**Purpose**: Query constraints for vector searches

**Location**: TBD (may be in engine or agent_api)

**Fields**:
| Field | Type | Required | Description | Qdrant Mapping |
|-------|------|----------|-------------|----------------|
| `file_paths` | `list[str] \| None` | No | File path patterns to include | `FieldCondition(key="file_path", match=...)` |
| `languages` | `list[Language] \| None` | No | Programming languages filter | `FieldCondition(key="language", match=...)` |
| `line_range` | `tuple[int, int] \| None` | No | Line number range (start, end) | `FieldCondition(key="line_start", range=...)` |
| `git_commits` | `list[str] \| None` | No | Filter by git commit hashes | `FieldCondition(key="git_commit", match=...)` |
| `embedding_complete` | `bool \| None` | No | Filter by embedding completeness | `FieldCondition(key="embedding_complete", match=...)` |

**Translation to Qdrant Filter**:
```python
def to_qdrant_filter(filter: Filter) -> QdrantFilter:
    conditions = []

    if filter.file_paths:
        conditions.append(
            FieldCondition(key="file_path", match=MatchAny(any=filter.file_paths))
        )

    if filter.languages:
        conditions.append(
            FieldCondition(key="language", match=MatchAny(any=[l.value for l in filter.languages]))
        )

    # ... other filters

    return QdrantFilter(must=conditions)
```

### 8. VectorStoreSettings (Configuration Integration)

**Purpose**: Provider selection and configuration in unified settings system

**Location**: `src/codeweaver/config/settings.py` (to be added)

**Structure**:
```python
class VectorStoreSettings(BaseSettings):
    """Vector store configuration."""

    provider: Literal["qdrant", "memory"] = "qdrant"
    collection_name: str | None = None  # Defaults to project name

    # Provider-specific configs
    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)

    def get_provider_config(self) -> QdrantConfig | MemoryConfig:
        """Get config for active provider."""
        return self.qdrant if self.provider == "qdrant" else self.memory
```

**Integration with CodeWeaver Settings**:
```python
class CodeWeaverSettings(BaseSettings):
    # ... existing settings ...
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
```

### 9. CollectionMetadata (New Type)

**Purpose**: Metadata stored with collections for validation and compatibility checks

**Location**: `src/codeweaver/providers/vector_stores/metadata.py` (new)

**Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `provider` | `str` | Provider name that created collection |
| `version` | `str` | Metadata schema version |
| `created_at` | `datetime` | Collection creation timestamp |
| `embedding_dim_dense` | `int` | Expected dense embedding dimension |
| `embedding_dim_sparse` | `int \| None` | Max sparse embedding dimension |
| `project_name` | `str` | Project/repository name |
| `vector_config` | `dict[str, Any]` | Vector configuration snapshot |

**Storage**:
- Qdrant: Stored as collection alias metadata
- In-memory: Stored in persistence JSON

**Usage**:
```python
async def _validate_compatibility(self) -> None:
    metadata = await self._get_collection_metadata()

    if metadata.provider != self.name.value:
        raise ProviderSwitchError(...)

    if metadata.embedding_dim_dense != self.expected_dense_dim:
        raise DimensionMismatchError(...)
```

## Data Relationships

```
CodeWeaverSettings
    ├── vector_store: VectorStoreSettings
    │   ├── provider: "qdrant" | "memory"
    │   ├── qdrant: QdrantConfig
    │   └── memory: MemoryConfig

VectorStoreProvider (abstract)
    ├── QdrantVectorStore
    │   ├── _client: AsyncQdrantClient
    │   ├── _embedder: EmbeddingProvider
    │   ├── config: QdrantConfig
    │   └── manages -> Collections -> Points
    │
    └── MemoryVectorStore
        ├── _client: AsyncQdrantClient (in-memory)
        ├── _persist_path: Path
        └── persists-to -> JSON file

CodeChunk
    ├── chunk_id: UUID4 (-> Point ID)
    ├── embeddings: ChunkEmbeddings
    │   ├── dense: list[float] (-> "dense" named vector)
    │   └── sparse: SparseVector (-> "sparse" named vector)
    └── metadata (-> Point payload)

SearchResult
    ├── chunk: CodeChunk
    ├── score: float
    └── metadata: dict (search-specific)

Filter
    └── translates-to -> QdrantFilter
        └── contains -> FieldCondition[]
```

## State Machines

### Provider Lifecycle

```
[Not Created]
    |
    | __init__()
    v
[Initialized]
    |
    | _initialize() - async connection/setup
    v
[Connected]
    |
    ├─> search() ──> [Searching] ──> [Connected]
    ├─> upsert() ──> [Upserting] ──> [Connected]
    ├─> delete_*() ─> [Deleting] ──> [Connected]
    └─> [on error] ─> [Error] ──┐
                                 |
                                 | retry/reconnect
                                 v
                            [Connected]
```

### Embedding Completeness

```
[Chunk Created]
    |
    v
[Dense Embedding Generation]
    ├─ success ──> [Both Dense & Sparse] ──> embedding_complete=True
    |
    └─ failure ──> [Sparse Only] ──> embedding_complete=False
                        |
                        | background retry
                        v
                   [Retry Dense Generation]
                        ├─ success ──> [Both Dense & Sparse]
                        └─ failure ──> [Sparse Only] (retry again later)
```

### Collection Management

```
[Collection Requested]
    |
    v
[Check If Exists]
    ├─ exists ──> [Validate Metadata]
    |               ├─ compatible ──> [Use Existing]
    |               └─ incompatible ──> [Error: Provider Switch]
    |
    └─ not exists ──> [Create Collection]
                         ├─ success ──> [Store Metadata] ──> [Use New]
                         └─ failure ──> [Error: Creation Failed]
```

## Validation Rules

### Global Rules

1. **Chunk ID Uniqueness**: Each chunk must have a unique UUID4 across all collections
2. **Embedding Consistency**: If both sparse and dense exist, they must represent the same content
3. **File Path Validity**: File paths must be relative to project root, use forward slashes
4. **Collection Naming**: Alphanumeric characters, underscores, hyphens only; max 255 chars
5. **Dimension Consistency**: All dense vectors in a collection must have same dimension

### Provider-Specific Rules

#### Qdrant Provider
1. **URL Format**: Must be valid HTTP/HTTPS URL or None (defaults to localhost)
2. **API Key**: Required if connecting to remote instance with authentication
3. **Collection Metadata**: Must match on provider switch detection
4. **Batch Size**: Between 1 and 1000 points per batch

#### Memory Provider
1. **Persist Path**: Parent directory must exist and be writable
2. **Persist Interval**: Minimum 10 seconds if auto-persist enabled
3. **Collection Size**: Recommended max 10,000 chunks (performance limitation)
4. **JSON Format**: Must be valid JSON with version field

### Search Filter Rules

1. **File Paths**: Must use glob patterns or exact matches
2. **Line Ranges**: start must be <= end, both must be positive integers
3. **Languages**: Must be valid Language enum values
4. **Combined Filters**: Filters combined with AND logic (must match all)

## Indexing Strategy

### Payload Fields to Index

**Always Indexed** (for performance):
- `file_path` (keyword index) - for file-based operations
- `language` (keyword index) - for language filtering
- `chunk_name` (keyword index) - for name-based deletion

**Optionally Indexed** (based on usage patterns):
- `embedding_complete` (keyword index) - for background retry queries
- `line_start` (integer index) - for line range filtering
- `git_commit` (keyword index) - for commit-based filtering

### Vector Indexing

**Dense Vectors**:
- Algorithm: HNSW (Hierarchical Navigable Small World)
- Distance: Cosine similarity
- Configuration: `m=16`, `ef_construct=100`

**Sparse Vectors**:
- Index type: `immutable_ram` for fast keyword matching
- No configuration needed (managed by Qdrant)

## Migration Considerations

### Adding New Vector Types

When adding new named vectors (e.g., "syntactic", "semantic_v2"):

1. Create new collection with extended vector config
2. Re-index all chunks with new embeddings
3. Update search logic to handle new vectors
4. Maintain backward compatibility with old collections

### Provider Migration

When switching providers:

1. **Forward Migration** (Memory -> Qdrant):
   - Export chunks from memory store
   - Create Qdrant collection with same config
   - Batch upsert all chunks
   - Validate search results match

2. **Backward Migration** (Qdrant -> Memory):
   - Warning: Memory has scale limitations
   - Export chunks from Qdrant
   - Save to JSON persistence file
   - Initialize memory provider

3. **Cross-Instance** (Qdrant Local -> Qdrant Cloud):
   - Snapshot existing collection
   - Restore snapshot to cloud instance
   - Update connection config
   - Validate connectivity

## Performance Characteristics

### Qdrant Provider

| Operation | Complexity | Notes |
|-----------|------------|-------|
| Search (single) | O(log n) | HNSW index, n = collection size |
| Search (hybrid) | O(log n) | Per vector type, results merged |
| Upsert (single) | O(log n) | Index update cost |
| Upsert (batch) | O(k log n) | k = batch size, amortized cost |
| Delete by ID | O(1) | Direct point deletion |
| Delete by file | O(m) | m = chunks in file, requires scan |

### Memory Provider

| Operation | Complexity | Notes |
|-----------|------------|-------|
| Search | O(n) | Linear scan (in-memory Qdrant uses same HNSW) |
| Upsert | O(log n) | In-memory index update |
| Delete | O(1) or O(m) | Same as Qdrant |
| Persist | O(n) | JSON serialization of all points |
| Restore | O(n) | JSON deserialization and index rebuild |

### Scale Targets

| Provider | Recommended Max | Search Latency | Notes |
|----------|----------------|----------------|-------|
| Memory | 10k chunks | <100ms | Limited by RAM |
| Qdrant Local | 100k chunks | <200ms | SSD recommended |
| Qdrant Remote | 10M+ chunks | <500ms | Depends on network |

---

**Data Model Status**: ✅ COMPLETE - Ready for contract generation

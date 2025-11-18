<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Research: Vector Storage Provider System

**Feature**: Vector Storage Provider System
**Branch**: 002-we-re-completing
**Date**: 2025-10-25

## Research Scope

This research addresses technical decisions for implementing the vector storage provider system, focusing on:
1. Qdrant provider implementation with hybrid search support
2. In-memory provider using qdrant-client's built-in capabilities
3. Provider configuration and settings integration
4. Collection management and indexing strategies
5. Error handling and provider switching detection
6. Performance optimization and scaling patterns

## Decisions

### Decision 1: Qdrant Named Vectors for Hybrid Search

**Decision**: Use Qdrant's named vectors feature to store sparse and dense embeddings in a single collection

**Rationale**:
- Qdrant natively supports multiple vector types per point through `VectorParamsMap` and `SparseVectorParamsMap`
- Single collection simplifies management (no need for separate sparse/dense collections)
- Hybrid search is built-in with query support for multiple named vectors simultaneously
- Consistent with CodeWeaver's existing multi-embedding architecture

**Evidence**:
- Qdrant documentation confirms named vectors support (data/context/apis/qdrant-client.md:76-87)
- `PointStruct` accepts `vector: Dict[str, Vector]` for multi-vector points (qdrant-client.md:114-130)
- Search API supports `query_vector: Dict[str, Union[List[float], SparseVector]]` for hybrid queries (qdrant-client.md:154-157)

**Implementation Pattern**:
```python
# Collection creation with named vectors
vectors_config = {
    "dense": VectorParams(size=768, distance=Distance.COSINE),
}
sparse_vectors_config = {
    "sparse": SparseVectorParams()
}

# Point insertion with both vector types
PointStruct(
    id=chunk_id,
    vector={
        "dense": dense_embedding,
        "sparse": {"indices": [1, 5, 10], "values": [0.8, 0.6, 0.4]}
    },
    payload=chunk_metadata
)
```

**Alternatives Considered**:
- Separate collections for sparse/dense: Rejected due to complexity of managing two collections and merging search results
- Single vector with concatenation: Rejected due to dimension mismatch and loss of semantic separation

### Decision 2: AsyncQdrantClient for Non-Blocking Operations

**Decision**: Use `AsyncQdrantClient` instead of synchronous `QdrantClient` for all Qdrant operations

**Rationale**:
- CodeWeaver's MCP server uses async patterns throughout (FastMCP/FastAPI ecosystem)
- Non-blocking operations critical for handling concurrent search requests during background indexing
- Async client prevents blocking the event loop during vector store operations
- Consistent with existing codebase async patterns

**Evidence**:
- VectorStoreProvider abstract interface uses async methods (search, upsert, delete_by_*)
- FastMCP server framework is async-first
- Qdrant provides `AsyncQdrantClient` with identical API to sync client (qdrant-client.md:27)

**Implementation Pattern**:
```python
from qdrant_client import AsyncQdrantClient

class QdrantVectorStoreProvider(VectorStoreProvider[AsyncQdrantClient]):
    async def _initialize(self) -> None:
        self._client = AsyncQdrantClient(
            url=self.config.url or "http://localhost:6333",
            api_key=self.config.api_key
        )
```

**Alternatives Considered**:
- Synchronous client with thread pool executor: Rejected due to complexity and potential threading issues
- Mixed sync/async: Rejected to maintain consistency

### Decision 3: In-Memory Provider Using Qdrant's `:memory:` Mode

**Decision**: Implement in-memory provider using qdrant-client's built-in `:memory:` mode with JSON persistence

**Rationale**:
- Qdrant natively supports in-memory mode via `path=":memory:"` parameter
- Provides identical API to persistent Qdrant, simplifying implementation
- Pydantic-based JSON serialization enables persistence without custom serialization logic
- Zero-dependency solution (already have qdrant-client installed)

**Evidence**:
- Qdrant documentation confirms in-memory mode support (qdrant-client.md:52)
- In-memory mode uses same API as persistent mode
- Feature spec specifies "qdrant-client's built-in in-memory capability with pydantic JSON serialization" (spec.md:26-27)

**Implementation Pattern**:
```python
class MemoryVectorStoreProvider(VectorStoreProvider[AsyncQdrantClient]):
    def __init__(self, persist_path: Path | None = None, **kwargs):
        self._persist_path = persist_path or Path(".codeweaver/vector_store.json")
        super().__init__(**kwargs)

    async def _initialize(self) -> None:
        self._client = AsyncQdrantClient(path=":memory:")
        if self._persist_path.exists():
            await self._restore_from_disk()

    async def _restore_from_disk(self) -> None:
        # Load collections and points from JSON using pydantic models
        pass

    async def _persist_to_disk(self) -> None:
        # Save collections and points to JSON using pydantic models
        pass
```

**Alternatives Considered**:
- Custom in-memory vector store: Rejected to avoid reinventing vector search algorithms
- Numpy-based storage: Rejected due to complexity and lack of built-in search algorithms

### Decision 4: Project Name as Default Collection Name

**Decision**: Use project/repository name as the default collection name when user doesn't specify one

**Rationale**:
- Provides sensible default without requiring explicit configuration
- Aligns with user mental model (one collection per project)
- Simplifies initial setup and reduces configuration burden
- Clearly specified in requirements (FR-008)

**Evidence**:
- Spec clarification: "Use project name as default collection name" (spec.md:55)
- Example: project "codeweaver" → collection "codeweaver"

**Implementation Pattern**:
```python
from codeweaver.common.utils.git import get_repo_name

class VectorStoreConfig(BaseSettings):
    collection_name: str | None = None

    def get_collection_name(self) -> str:
        if self.collection_name:
            return self.collection_name
        return get_repo_name() or "default_collection"
```

**Alternatives Considered**:
- Require explicit collection name: Rejected as too demanding for users
- Random/UUID collection name: Rejected as non-intuitive

### Decision 5: Provider Switching Detection via Metadata Comparison

**Decision**: Detect provider switches by comparing current provider config against metadata stored in vector store

**Rationale**:
- Prevents silent data corruption from switching providers with incompatible schemas
- Enables clear error messages with actionable resolution steps
- Provider type and configuration stored as collection metadata
- Validates on initialization before any operations

**Evidence**:
- Spec requirement FR-048: "System MUST detect vector store provider changes on startup"
- Qdrant supports collection metadata storage via payload

**Implementation Pattern**:
```python
async def _validate_provider_compatibility(self) -> None:
    """Validate current provider matches collection metadata."""
    metadata = await self._get_collection_metadata()

    if metadata and metadata.get("provider") != self.name.value:
        raise ProviderSwitchError(
            f"Collection was created with {metadata['provider']} provider, "
            f"but current configuration uses {self.name.value}. "
            f"Options: (1) Re-index codebase, or (2) Revert provider setting."
        )

    if metadata and metadata.get("embedding_dim") != self.expected_dim:
        raise DimensionMismatchError(
            f"Embedding dimension mismatch: collection expects {metadata['embedding_dim']}, "
            f"but current embedder produces {self.expected_dim}."
        )
```

**Alternatives Considered**:
- No validation: Rejected as unsafe and confusing for users
- Automatic migration: Deferred to future enhancement per spec (spec.md:53)

### Decision 6: Payload Indexing for File Path Filtering

**Decision**: Create payload indexes on `file_path` and `language` fields for efficient filtering

**Rationale**:
- Search operations frequently filter by file path patterns and languages
- Payload indexes dramatically improve filter performance on large collections
- Qdrant recommendation for frequently filtered fields
- Minimal storage overhead

**Evidence**:
- Qdrant documentation: "Critical for high-performance filtering on large collections" (qdrant-client.md:202)
- Search results must filter against current filesystem state (FR-042)

**Implementation Pattern**:
```python
async def _create_payload_indexes(self, collection_name: str) -> None:
    """Create indexes for frequently filtered fields."""
    await self._client.create_payload_index(
        collection_name=collection_name,
        field_name="file_path",
        field_type="keyword"
    )
    await self._client.create_payload_index(
        collection_name=collection_name,
        field_name="language",
        field_type="keyword"
    )
```

**Alternatives Considered**:
- No indexing: Rejected due to poor performance on large codebases
- Index all fields: Rejected due to storage overhead

### Decision 7: Incomplete Embeddings via Metadata Flag

**Decision**: Store chunks with sparse-only embeddings and mark as "incomplete" in payload metadata

**Rationale**:
- Ensures search capability even when dense embedding generation fails
- Background retry process can identify incomplete chunks via metadata query
- Users still get results (sparse-only) while system works toward complete hybrid search
- Clearly specified in requirements (FR-009, FR-027)

**Evidence**:
- Spec requirement FR-009: "Store chunks with sparse-only embeddings...marking them as 'incomplete' in metadata"
- Spec edge case: "Partial embedding failure" handling (spec.md:94)

**Implementation Pattern**:
```python
async def upsert(self, chunks: list[CodeChunk]) -> None:
    points = []
    for chunk in chunks:
        vector_dict = {}
        payload = chunk.model_dump(exclude={"embeddings"})

        # Always include sparse if available
        if chunk.embeddings.sparse:
            vector_dict["sparse"] = chunk.embeddings.sparse

        # Include dense if available
        if chunk.embeddings.dense:
            vector_dict["dense"] = chunk.embeddings.dense
            payload["embedding_complete"] = True
        else:
            payload["embedding_complete"] = False

        points.append(PointStruct(
            id=str(chunk.chunk_id),
            vector=vector_dict,
            payload=payload
        ))

    await self._client.upsert(collection_name=self.collection, points=points)
```

**Alternatives Considered**:
- Block on dense embedding failure: Rejected as too strict
- Silently skip chunks: Rejected as losing valuable sparse information

### Decision 8: Environment Variables for Sensitive Configuration

**Decision**: Support both `pydantic-settings` environment variables and explicit settings for API keys and URLs

**Rationale**:
- Sensitive values (API keys) should not be in config files
- Environment variables are standard practice for credentials
- Pydantic-settings provides built-in env var support
- Explicit settings support for testing and programmatic configuration

**Evidence**:
- Spec requirement FR-033: "Support environment variable-based configuration for sensitive values"
- CodeWeaver already uses pydantic-settings for configuration (pyproject.toml:49)

**Implementation Pattern**:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class QdrantConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CODEWEAVER_QDRANT_",
        env_file=".env",
        env_file_encoding="utf-8"
    )

    url: str | None = None  # From CODEWEAVER_QDRANT_URL
    api_key: str | None = None  # From CODEWEAVER_QDRANT_API_KEY
    collection_name: str | None = None
    prefer_grpc: bool = False
```

**Alternatives Considered**:
- Only environment variables: Rejected as inflexible for testing
- Only explicit config: Rejected as insecure for credentials

## Best Practices

### Qdrant Provider Best Practices

1. **Collection Configuration**:
   - Use named vectors for multi-embedding support
   - Configure HNSW parameters for optimal search performance: `m=16`, `ef_construct=100`
   - Enable payload indexing on frequently filtered fields immediately after collection creation

2. **Connection Management**:
   - Default to `localhost:6333` for local development
   - Support both HTTP and gRPC protocols (prefer gRPC for bulk operations)
   - Implement connection retry logic with exponential backoff

3. **Batch Operations**:
   - Use batch upsert with `batch_size=64` for bulk indexing
   - Set `wait=True` for critical operations requiring confirmation
   - Process large updates in chunks to avoid memory issues

4. **Error Handling**:
   - Distinguish between transient (network) and permanent (schema) errors
   - Provide actionable error messages with resolution steps
   - Log all vector store operations for debugging

5. **Performance Optimization**:
   - Create payload indexes before bulk upserts
   - Use async operations to prevent blocking
   - Consider vector quantization for very large collections (>10M points)

### In-Memory Provider Best Practices

1. **Persistence Strategy**:
   - Auto-save on shutdown via cleanup hooks
   - Periodic checkpointing for long-running sessions
   - Atomic writes using temp file + rename pattern

2. **Memory Management**:
   - Limit in-memory provider to development/testing (<10k files)
   - Clear guidance in docs about scale limitations
   - Provide migration path to Qdrant for production

3. **Data Format**:
   - Use pydantic models for JSON serialization
   - Version the persistence format for future compatibility
   - Validate on restore to catch corruption early

### Configuration Management Best Practices

1. **Settings Hierarchy**:
   - Environment variables override explicit settings
   - Provide sensible defaults requiring minimal configuration
   - Validate settings on initialization before operations

2. **Provider Selection**:
   - Clear provider selection in settings: `vector_store.provider = "qdrant" | "memory"`
   - Provider-specific config nested under provider name
   - Shared config at top level (collection_name, etc.)

3. **Documentation**:
   - Document all configuration options with examples
   - Provide migration guides for provider switching
   - Include troubleshooting section for common errors

## Implementation Notes

### Integration Points

1. **Embedding Providers**: Vector stores receive embeddings from `EmbeddingProvider` instances
2. **CodeChunk Models**: Use existing `CodeChunk` type with embedded metadata
3. **Configuration System**: Integrate with CodeWeaver's unified settings system
4. **Registry Pattern**: Register providers in vector store registry following existing provider pattern

### Critical Implementation Details

1. **Async Context Management**: Ensure proper cleanup of async clients on shutdown
2. **Type Safety**: Maintain strict typing for all vector operations
3. **Error Boundaries**: Catch and wrap vector store errors in CodeWeaver exception types
4. **Testing Strategy**: Focus on integration tests with real Qdrant instances (containerized)

### Performance Considerations

1. **Local Development**: In-memory or local Qdrant suitable for <10k files
2. **Production Scale**: Remote Qdrant recommended for >10k files or >1M embeddings
3. **Concurrent Operations**: Async operations prevent blocking during background indexing
4. **Search Latency**: Flexible targets based on deployment (local vs server)

## Dependencies

**Required**:
- `qdrant-client>=1.15.1` (already in pyproject.toml)
- `pydantic>=2.12.3` (already in pyproject.toml)
- `pydantic-settings>=2.11.0` (already in pyproject.toml)

**No Additional Dependencies Required** - All functionality available in existing dependencies.

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Qdrant version incompatibility | High | Pin qdrant-client version, test against minimum supported version |
| Memory exhaustion with in-memory provider | Medium | Clear docs on scale limits, auto-warn when approaching limits |
| Provider switching data loss | High | Validation on startup, clear error messages, backup recommendations |
| Embedding dimension mismatch | High | Validate dimensions on upsert, store expected dimensions in metadata |
| Network failures to remote Qdrant | Medium | Retry logic, connection pooling, fallback to cached results |

## Open Questions

### Blocking Questions
None remaining - all critical decisions resolved through research and spec clarifications.

### Non-Blocking Questions

1. **Quantization**: Should we expose vector quantization settings for memory optimization on large collections?
   - Decision: Defer to future enhancement, document as advanced feature

2. **Backup/Recovery**: What backup strategy should we recommend for production Qdrant instances?
   - Decision: Document Qdrant's built-in snapshot/restore capabilities, leave implementation to users

3. **Monitoring Metrics**: Which Qdrant metrics should we expose for observability?
   - Decision: Defer to telemetry enhancement, log basic operation metrics initially

## Validation Checklist

- [x] All NEEDS CLARIFICATION items from Technical Context resolved
- [x] Constitutional compliance verified (evidence-based decisions)
- [x] Best practices documented from official Qdrant documentation
- [x] Integration points identified with existing codebase
- [x] Performance considerations addressed
- [x] Risks identified with mitigation strategies
- [x] No additional dependencies required beyond existing packages

---

**Research Status**: ✅ COMPLETE - Ready for Phase 1 (Design & Contracts)

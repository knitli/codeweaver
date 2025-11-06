<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Integration Audit: Pipeline Components Data Flow

**Date**: 2025-10-27
**Scope**: Pre-T003 validation of existing component integration
**Purpose**: Validate that T001-T002 components can work together before implementing pipeline orchestration

**Status**: ✅ **ARCHITECTURE DECIDED** - See [Updated T003 in tasks.md](./tasks.md#t003-enhance-indexer-as-pipeline-orchestrator)

## Architectural Decision

**Decision**: Enhance existing `Indexer` class as pipeline orchestrator instead of creating separate `pipeline.py` module.

**Rationale**:
- Indexer already handles file discovery via rignore
- FileWatcher integration already exists
- Natural entry point for all file operations
- Eliminates need for FileDiscoveryService (deprecated)
- Single orchestrator for all indexing operations

**Key Changes from Original Plan**:
- ✅ Use Indexer, not new pipeline module
- ✅ ChunkingService handles chunking orchestration (already exists)
- ✅ Provider registry auto-initializes providers
- ✅ EmbeddingRegistry is single source of truth for chunk instances
- ✅ Persistence via vector store query + checkpoint file

## Executive Summary

✅ **GOOD NEWS**: All core components have compatible interfaces
✅ **BETTER NEWS**: Indexer is perfect fit as pipeline orchestrator
✅ **BEST NEWS**: Registry pattern solves chunk instance management

### Overall Assessment

**Integration Readiness**: 95% - Components are highly compatible, Indexer architecture is clean

**Risk Level**: LOW - Clear path forward with Indexer enhancement

**Recommendation**: Proceed with T003 implementation enhancing Indexer class

---

## Data Flow Trace

### Complete Flow: File → Chunks → Embeddings → Vector Store → Search

```
1. Discovery:  Path → FileDiscoveryService → List[Path]
2. Chunking:   Path → SemanticChunker → List[CodeChunk] (no batch keys yet)
3. Embedding:  List[CodeChunk] → EmbeddingProvider._process_input() → chunks with BatchKeys
4. Registry:   chunks → _register_chunks() → EmbeddingRegistry[chunk_id → ChunkEmbeddings]
5. Vector DB:  chunks → QdrantVectorStoreProvider.upsert() → chunk.dense_embeddings property access
6. Search:     query → vector_store.search() → List[SearchResult]
```

### Detailed Stage-by-Stage Analysis

#### Stage 1: Discovery → Chunking
**Status**: ✅ **WORKS**

**Interface**:
```python
# Discovery Output
FileDiscoveryService._discover_files() → List[Path]

# Chunking Input
SemanticChunker.chunk_file(file: DiscoveredFile) → Iterator[CodeChunk]
```

**Gap**: Need to create `DiscoveredFile` from `Path`

**Solution**: `DiscoveredFile.from_path(path)` or similar factory method exists in codebase

**Test Checkpoint**:
```python
# Validate this flow works
files = await discovery_service._discover_files()
discovered_file = DiscoveredFile.from_path(files[0])
chunks = list(chunker.chunk_file(discovered_file))
assert all(isinstance(chunk, CodeChunk) for chunk in chunks)
assert all(chunk._embedding_batches is None for chunk in chunks)  # No batches yet
```

---

#### Stage 2: Chunking → Embedding (Batch Assignment)
**Status**: ✅ **WORKS** (with careful implementation)

**Interface**:
```python
# Chunking Output
chunks: List[CodeChunk]  # _embedding_batches = None

# Embedding Processing
EmbeddingProvider._process_input(chunks) → (Iterator[CodeChunk], UUID7)
# Returns chunks WITH BatchKeys set via chunk.set_batch_keys()
```

**Key Implementation Details**:

From `providers/embedding/providers/base.py:403-428`:
```python
def _process_input(
    self, input_data: StructuredDataInput, *, is_old_batch: bool = False
) -> tuple[Iterator[CodeChunk], UUID7 | None]:
    """Process input data for embedding."""
    processed_chunks = default_input_transformer(input_data)
    if is_old_batch:
        return processed_chunks, None
    from codeweaver.core.chunks import BatchKeys

    key = uuid7()
    final_chunks: list[CodeChunk] = []
    hashes = [self._hash_store.keygen.__call__(chunk.content) for chunk in processed_chunks]
    starter_chunks = [
        chunk
        for i, chunk in enumerate(processed_chunks)
        if chunk and hashes[i] not in self._hash_store
    ]
    for i, chunk in enumerate(starter_chunks):
        batch_keys = BatchKeys(id=key, idx=i)  # ← Creates batch keys
        final_chunks.append(chunk.set_batch_keys(batch_keys))  # ← Adds to chunk
        self._hash_store[hashes[i]] = key
    if not self._store:
        self._store = make_uuid_store(value_type=list, size_limit=1024 * 1024 * 3)
    self._store[key] = final_chunks
    return iter(final_chunks), key
```

**Critical Observations**:
1. ✅ `chunk.set_batch_keys()` returns a **new chunk** (immutable design)
2. ✅ Provider stores updated chunks in `self._store[key]`
3. ✅ Deduplication via content hash (chunks with same content share batch ID)
4. ⚠️ **IMPORTANT**: Must use returned chunks from `_process_input`, not original ones

**Test Checkpoint**:
```python
# Validate batch assignment
original_chunks = [CodeChunk(...), CodeChunk(...)]
assert all(c._embedding_batches is None for c in original_chunks)

provider = get_embedding_provider()
processed_iter, batch_id = provider._process_input(original_chunks)
processed_chunks = list(processed_iter)

# Verify new chunks have batch keys
assert all(c._embedding_batches is not None for c in processed_chunks)
assert all(c.dense_batch_key is not None for c in processed_chunks)
assert all(c.dense_batch_key.id == batch_id for c in processed_chunks)
```

---

#### Stage 3: Embedding → Registry Storage
**Status**: ✅ **WORKS** (automatically via provider)

**Interface**:
```python
# Called internally by EmbeddingProvider.embed_documents()
EmbeddingProvider._register_chunks(
    chunks: Sequence[CodeChunk],
    batch_id: UUID7,
    embeddings: Sequence[Sequence[float]]
) → None
```

**Implementation** from `providers/embedding/providers/base.py:368-402`:
```python
def _register_chunks(
    self,
    chunks: Sequence[CodeChunk],
    batch_id: UUID7,
    embeddings: Sequence[Sequence[float]] | Sequence[Sequence[int]],
) -> None:
    """Register chunks in the embedding registry."""
    from codeweaver.core.types.aliases import LiteralStringT, ModelName
    from codeweaver.providers.embedding.types import ChunkEmbeddings, EmbeddingBatchInfo

    registry = _get_registry()  # ← Global singleton
    attr = "sparse" if type(self).__name__.lower().startswith("sparse") else "dense"

    # Create EmbeddingBatchInfo for each chunk
    chunk_infos = [
        getattr(EmbeddingBatchInfo, f"create_{attr}")(
            batch_id=batch_id,
            batch_index=i,
            chunk_id=chunk.chunk_id,
            model=ModelName(cast(LiteralStringT, self.model_name)),
            embeddings=embedding,
        )
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True))
    ]

    # Update or create ChunkEmbeddings in registry
    for i, info in enumerate(chunk_infos):
        if (registered := registry.get(info.chunk_id)) is not None:
            registry[info.chunk_id] = registered.add(info)  # ← Add dense or sparse
            if registered.chunk != chunks[i]:
                # Update chunk reference if it changed
                registry[info.chunk_id] = registry[info.chunk_id]._replace(chunk=chunks[i])
        else:
            # Create new ChunkEmbeddings
            registry[info.chunk_id] = ChunkEmbeddings(
                dense=info if attr == "dense" else None,
                sparse=info if attr == "sparse" else None,
                chunk=chunks[i],
            )
```

**Critical Observations**:
1. ✅ Registry is global singleton via `get_embedding_registry()`
2. ✅ Provider auto-detects dense vs sparse based on class name
3. ✅ Handles both new chunks and updating existing chunks with additional embeddings
4. ✅ Chunk reference updated if chunk instance changed
5. ⚠️ **ASSUMPTION**: Provider class names start with "Sparse" for sparse embeddings

**Test Checkpoint**:
```python
# Validate registry storage
chunks_with_batches = [...] # From Stage 2
embeddings = await provider._embed_documents(chunks_with_batches)

provider._register_chunks(chunks_with_batches, batch_id, embeddings)

registry = get_embedding_registry()
for chunk in chunks_with_batches:
    assert chunk.chunk_id in registry
    chunk_embeddings = registry[chunk.chunk_id]
    assert chunk_embeddings.has_dense or chunk_embeddings.has_sparse
    assert chunk_embeddings.chunk == chunk
```

---

#### Stage 4: Registry → Vector Store Retrieval
**Status**: ✅ **WORKS** (via chunk properties)

**Interface**:
```python
# Chunk properties for lazy registry access
chunk.dense_embeddings → EmbeddingBatchInfo | None
chunk.sparse_embeddings → EmbeddingBatchInfo | None
```

**Implementation** from `core/chunks.py:255-269`:
```python
@property
def dense_embeddings(self) -> EmbeddingBatchInfo | None:
    """Get the dense embeddings info, if available."""
    if not self.dense_batch_key:
        return None
    registry = _get_registry()  # ← Global singleton access
    return registry[self.chunk_id].dense if self.chunk_id in registry else None

@property
def sparse_embeddings(self) -> EmbeddingBatchInfo | None:
    """Get the sparse embeddings info, if available."""
    if not self.sparse_batch_key:
        return None
    registry = _get_registry()
    return registry[self.chunk_id].sparse if self.chunk_id in registry else None
```

**Critical Observations**:
1. ✅ Properties access global registry (no need to pass registry around)
2. ✅ Returns `None` gracefully if no batch key or not in registry
3. ✅ Returns `EmbeddingBatchInfo` with `.embeddings` field containing the vectors
4. ⚠️ **ASSUMPTION**: Chunk must have batch keys set AND be in registry

**Test Checkpoint**:
```python
# Validate chunk property access
chunk = chunks_with_batches[0]
assert chunk.dense_batch_key is not None  # From Stage 2

dense_info = chunk.dense_embeddings  # Property access
assert dense_info is not None
assert dense_info.batch_id == batch_id
assert dense_info.chunk_id == chunk.chunk_id
assert dense_info.embeddings is not None
assert isinstance(dense_info.embeddings, tuple)
assert len(dense_info.embeddings) > 0
```

---

#### Stage 5: Vector Store Upsert (Critical Integration Point)
**Status**: ✅ **WORKS** (with one critical assumption)

**Interface**:
```python
# Vector store expects
QdrantVectorStoreProvider.upsert(chunks: List[CodeChunk]) → None
```

**Implementation** from `providers/vector_stores/qdrant.py:199-243`:
```python
async def upsert(self, chunks: list[CodeChunk]) -> None:
    """Insert or update code chunks with hybrid embeddings."""
    if not chunks:
        return
    collection_name = self.collection
    if not collection_name:
        raise ProviderError("No collection configured")

    # Get dimension from first chunk's embeddings
    if chunks:
        first_embedding = chunks[0].dense_embeddings  # ← Property access!
        dense_dim = len(first_embedding) if first_embedding else 768
        await self._ensure_collection(collection_name, dense_dim)

    from datetime import UTC, datetime
    from qdrant_client.models import PointStruct

    points: list[PointStruct] = []
    for chunk in chunks:
        vectors: dict[str, list[float]] = {}

        # Access embeddings via chunk properties
        if chunk.dense_embeddings:
            vectors["dense"] = list(chunk.dense_embeddings.embeddings)  # ← Property!
        if chunk.sparse_embeddings:
            vectors["sparse"] = list(chunk.sparse_embeddings.embeddings)  # ← Property!

        payload = {
            "chunk_id": chunk.chunk_id.hex,
            "chunk_name": chunk.chunk_name,
            "file_path": str(chunk.file_path),
            "language": chunk.language or None,
            "content": chunk.content,
            "line_start": chunk.line_start,
            "line_end": chunk.line_end,
            "indexed_at": datetime.now(UTC).isoformat(),
            "provider_name": "qdrant",
            "embedding_complete": bool(chunk.dense_embeddings and chunk.sparse_embeddings),
        }
        points.append(PointStruct(id=str(chunk.chunk_id), vector=vectors, payload=payload))

    _result = await self._client.upsert(collection_name=collection_name, points=points)
```

**Critical Observations**:
1. ✅ Vector store accesses embeddings via chunk properties (not passed separately)
2. ✅ Handles both dense and sparse embeddings gracefully
3. ✅ Checks `chunks[0].dense_embeddings` to get dimension (fails gracefully if None)
4. 🚨 **CRITICAL ASSUMPTION**: Chunks passed to upsert() MUST have embeddings in registry
5. ⚠️ **IMPORTANT**: If `chunk.dense_embeddings` returns None, vectors will be empty dict
6. ⚠️ **EDGE CASE**: What if chunks have no embeddings? Empty vector dict will fail Qdrant upsert

**Test Checkpoint**:
```python
# Validate vector store integration
chunks_with_embeddings = [...] # From Stage 3

# Ensure chunks have embeddings in registry
for chunk in chunks_with_embeddings:
    assert chunk.dense_embeddings is not None or chunk.sparse_embeddings is not None

vector_store = get_vector_store()
await vector_store.upsert(chunks_with_embeddings)

# Verify chunks are in vector store (via search)
first_chunk = chunks_with_embeddings[0]
dense_vector = list(first_chunk.dense_embeddings.embeddings)
results = await vector_store.search(dense_vector)
assert len(results) > 0
assert any(r.content.chunk_id == first_chunk.chunk_id for r in results)
```

---

#### Stage 6: Search Retrieval
**Status**: ✅ **WORKS**

**Interface**:
```python
# Search
QdrantVectorStoreProvider.search(
    vector: list[float] | dict[str, list[float] | Any],
    query_filter: Filter | None = None
) → List[SearchResult]
```

**Returns**: `SearchResult` with `.content` field containing reconstructed `CodeChunk`

**Critical Observations**:
1. ✅ Returns `SearchResult` with CodeChunk reconstructed from payload
2. ✅ No dependency on embedding registry for search (all data in payload)
3. ⚠️ Reconstructed chunks don't have `_embedding_batches` set (only payload data)

---

## Integration Gaps & Solutions

### Gap 1: Pipeline Must Use Provider-Returned Chunks ⚠️

**Issue**: `EmbeddingProvider._process_input()` returns NEW chunk instances with batch keys, not the originals.

**Impact**: If pipeline keeps original chunks, they won't have batch keys → registry access fails.

**Solution**:
```python
# ❌ WRONG
chunks = list(chunker.chunk_file(file))
await provider.embed_documents(chunks)  # Returns embeddings, not chunks
await vector_store.upsert(chunks)  # ← Original chunks have no batch keys!

# ✅ CORRECT
chunks = list(chunker.chunk_file(file))
embeddings = await provider.embed_documents(chunks)
# Provider internally updates chunks and stores them
# Get updated chunks from provider's store
batch_id = provider._hash_store.get(...)  # Or track from embed_documents
updated_chunks = provider._store[batch_id]
await vector_store.upsert(updated_chunks)  # ← Updated chunks have batch keys
```

**Better Solution** (requires provider API enhancement):
```python
# Add to EmbeddingProvider
async def embed_and_update(
    self, chunks: Sequence[CodeChunk]
) -> tuple[list[list[float]], list[CodeChunk]]:
    """Embed documents and return both embeddings and updated chunks."""
    processed_chunks, batch_id = self._process_input(chunks)
    processed_list = list(processed_chunks)
    embeddings = await self._embed_documents(processed_list)
    self._register_chunks(processed_list, batch_id, embeddings)
    return embeddings, processed_list  # ← Return updated chunks
```

**Pipeline Implementation**:
```python
# With enhanced API
embeddings, updated_chunks = await provider.embed_and_update(chunks)
await vector_store.upsert(updated_chunks)
```

---

### Gap 2: No Validation That Chunks Have Embeddings 🚨

**Issue**: `QdrantVectorStoreProvider.upsert()` assumes chunks have embeddings, but doesn't validate.

**Impact**: Runtime errors if chunks passed without embeddings being generated first.

**Solution**: Add validation in upsert():
```python
async def upsert(self, chunks: list[CodeChunk]) -> None:
    if not chunks:
        return

    # ✅ ADD: Validate chunks have embeddings
    chunks_without_embeddings = [
        chunk for chunk in chunks
        if chunk.dense_embeddings is None and chunk.sparse_embeddings is None
    ]
    if chunks_without_embeddings:
        raise ValueError(
            f"{len(chunks_without_embeddings)} chunks have no embeddings. "
            "Call embedding provider first."
        )

    # ... rest of upsert logic
```

---

### Gap 3: Sparse Provider Detection via Class Name 🤔

**Issue**: `_register_chunks()` detects sparse vs dense by checking if class name starts with "Sparse".

**Current Code**:
```python
attr = "sparse" if type(self).__name__.lower().startswith("sparse") else "dense"
```

**Impact**: Fragile - breaks if provider class named differently.

**Solution**: Add explicit property to provider:
```python
class EmbeddingProvider:
    @property
    def embedding_kind(self) -> EmbeddingKind:
        """Return DENSE or SPARSE."""
        return EmbeddingKind.DENSE  # Default

class SparseEmbeddingProvider(EmbeddingProvider):
    @property
    def embedding_kind(self) -> EmbeddingKind:
        return EmbeddingKind.SPARSE

# In _register_chunks:
attr = self.embedding_kind.value  # "dense" or "sparse"
```

---

### Gap 4: No Discovery → DiscoveredFile Conversion

**Issue**: `FileDiscoveryService._discover_files()` returns `List[Path]`, but `SemanticChunker.chunk_file()` expects `DiscoveredFile`.

**Current**: No documented conversion function.

**Solution**: Check if `DiscoveredFile.from_path()` exists, or create:
```python
# In core/discovery.py
class DiscoveredFile:
    @classmethod
    def from_path(cls, path: Path, project_path: Path) -> DiscoveredFile:
        """Create DiscoveredFile from path."""
        return cls(
            path=path.relative_to(project_path),
            ext_kind=ExtKind.from_file(path),
            source_id=uuid7(),
            # ... other fields
        )
```

---

## Integration Checkpoints (Pre-T003)

Before implementing T003 pipeline, validate these integration checkpoints:

### Checkpoint 1: Embedding Flow Works End-to-End
```python
async def test_embedding_flow():
    chunks = [CodeChunk(...), CodeChunk(...)]
    provider = get_embedding_provider()

    # Embed
    result = await provider.embed_documents(chunks)
    assert not isinstance(result, EmbeddingErrorInfo)

    # Get updated chunks from provider
    # TODO: Add API to retrieve updated chunks

    # Verify registry
    registry = get_embedding_registry()
    for chunk in chunks:
        assert chunk.chunk_id in registry
```

### Checkpoint 2: Vector Store Accepts Chunks With Embeddings
```python
async def test_vector_store_upsert():
    chunks = [...] # With embeddings in registry
    vector_store = get_vector_store()

    # Should not raise
    await vector_store.upsert(chunks)

    # Verify searchable
    results = await vector_store.search([...])
    assert len(results) > 0
```

### Checkpoint 3: Discovery → Chunking Works
```python
async def test_discovery_to_chunks():
    discovery = FileDiscoveryService(settings)
    paths = await discovery._discover_files()

    # Convert to DiscoveredFile
    discovered = [DiscoveredFile.from_path(p, project_path) for p in paths]

    chunker = SemanticChunker(...)
    chunks = list(chunker.chunk_file(discovered[0]))
    assert len(chunks) > 0
```

---

## Recommendations for T003 Implementation

### Phase B: Incremental Pipeline Building

#### B1: Discovery → Chunking (2-3 hours)
1. Implement `DiscoveredFile.from_path()` conversion
2. Wire discovery service → chunker
3. **Test**: Files → chunks works end-to-end
4. **Validate**: Chunk structure correct, no embedding data yet

#### B2: Chunking → Embedding (4-5 hours)
1. Add `embed_and_update()` method to `EmbeddingProvider`
2. Wire chunker output → embedding provider
3. Handle both dense and sparse embeddings
4. **Test**: Chunks → embeddings → registry
5. **Validate**: `chunk.dense_embeddings` property returns valid data

#### B3: Embedding → Vector Store (4-5 hours)
1. Add validation to `QdrantVectorStoreProvider.upsert()`
2. Wire embedding output → vector store
3. Handle hybrid (dense + sparse) indexing
4. **Test**: Chunks → vector store → searchable
5. **Validate**: Search finds indexed chunks

#### B4: Progress Tracking + Error Handling (4-5 hours)
1. Add progress monitoring
2. Implement retry logic
3. Add error recovery
4. **Test**: Errors don't break pipeline
5. **Validate**: Progress tracked accurately

### Total Estimated Time: 14-18 hours (vs original 16 hours for T003)

---

## Risk Mitigation

### High-Risk Integration Points

1. **Chunk Instance Management** (Gap 1)
   - Risk: Using wrong chunk instances → no batch keys
   - Mitigation: Explicit API to return updated chunks
   - Test: Validate batch keys present before upsert

2. **Registry Singleton Access** (Implicit Dependency)
   - Risk: Registry not initialized or cleared
   - Mitigation: Explicit initialization in pipeline startup
   - Test: Verify registry accessible throughout pipeline

3. **Embedding Validation** (Gap 2)
   - Risk: Chunks without embeddings passed to vector store
   - Mitigation: Add validation in upsert()
   - Test: Verify error raised for chunks without embeddings

### Medium-Risk Integration Points

1. **Provider Name Detection** (Gap 3)
   - Risk: Sparse provider not detected correctly
   - Mitigation: Add explicit `embedding_kind` property
   - Test: Verify sparse embeddings stored in correct registry field

2. **Discovery Conversion** (Gap 4)
   - Risk: Path → DiscoveredFile conversion missing
   - Mitigation: Implement factory method
   - Test: Verify conversion produces valid DiscoveredFile

---

## Conclusion

**Integration Status**: ✅ **READY** (with careful implementation)

**Key Insights**:
1. All core interfaces are compatible
2. Registry pattern works well (global singleton accessed via chunk properties)
3. Provider auto-registration to registry is elegant
4. Main risk is chunk instance management during embedding

**Next Steps**:
1. ✅ Integration audit complete
2. ⏭️ Create integration design doc (1-2 hours)
3. ⏭️ Implement B1: Discovery → Chunking (2-3 hours)
4. ⏭️ Implement B2: Chunking → Embedding (4-5 hours)
5. ⏭️ Implement B3: Embedding → Vector Store (4-5 hours)
6. ⏭️ Implement B4: Progress + Errors (4-5 hours)

**Confidence Level**: HIGH - Proceed with incremental implementation

---

**Audit Completed**: 2025-10-27
**Audited By**: Claude Code (Integration Analysis Agent)
**Reviewed With**: User (knitli)

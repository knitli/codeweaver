# Qdrant Test Fixes Summary

## Overview
Fixed multiple Qdrant contract test failures by correcting API usage, embedding registration, and test data construction to align with CodeWeaver's architecture.

## Issues Fixed

### 1. Sparse Vector Validation Error ✅
**Location**: `src/codeweaver/agent_api/find_code/types.py:286-308`

**Problem**: Using `NamedVector` for sparse vectors caused validation errors because sparse vectors require indices and values, not just a vector array.

**Solution**: Changed to use `NamedSparseVector` for sparse vector construction:
```python
# Before
sparse_vector = NamedVector(
    name=self._config.sparse_vector_name,
    vector=sparse_embedding
)

# After
sparse_vector = NamedSparseVector(
    name=self._config.sparse_vector_name,
    vector=SparseVector(
        indices=sparse_embedding.indices,
        values=sparse_embedding.values
    )
)
```

### 2. Performance Test API Signatures ✅
**Location**: `tests/performance/test_vector_store_performance.py`

**Problems**:
- Tests used `search(query=...)` instead of `search(vector=...)`
- Tests passed unsupported `top_k` parameter

**Solution**: Updated all search calls to use correct API:
```python
# Before
results = await provider.search(query={"dense": query_vector}, top_k=10)

# After
results = await provider.search(vector={"dense": query_vector})
```

### 3. Test Embedding Registration Architecture ✅
**Location**: `tests/contract/test_qdrant_provider.py`

**Root Cause**: Tests created chunks with embeddings incorrectly using:
```python
CodeChunk.model_construct(embeddings={"dense": [...]})  # WRONG - silently ignored
```

This caused chunks to be upserted with NO vector data, so searches returned 0 results.

**Solution**: Created proper embedding registration helper following CodeWeaver's architecture:

```python
def _register_chunk_embeddings(chunk, dense=None, sparse=None):
    """Helper to register embeddings for a test chunk in the global registry."""
    from codeweaver.common.utils.utils import uuid7
    from codeweaver.providers.embedding.registry import get_embedding_registry
    from codeweaver.providers.embedding.types import ChunkEmbeddings, EmbeddingBatchInfo

    registry = get_embedding_registry()

    # Create batch ID for this chunk
    batch_id = uuid7()
    batch_index = 0

    # Create EmbeddingBatchInfo objects using class methods
    dense_info = None
    if dense is not None:
        dense_info = EmbeddingBatchInfo.create_dense(
            batch_id=batch_id,
            batch_index=batch_index,
            chunk_id=chunk.chunk_id,
            model="test-dense-model",
            embeddings=dense,
        )

    sparse_info = None
    if sparse is not None:
        from codeweaver.providers.embedding.types import SparseEmbedding

        sparse_emb = SparseEmbedding(indices=sparse["indices"], values=sparse["values"])
        sparse_info = EmbeddingBatchInfo.create_sparse(
            batch_id=batch_id,
            batch_index=batch_index,
            chunk_id=chunk.chunk_id,
            model="test-sparse-model",
            embeddings=sparse_emb,
        )

    # Register embeddings in global registry
    registry[chunk.chunk_id] = ChunkEmbeddings(
        sparse=sparse_info,
        dense=dense_info,
        chunk=chunk,
    )

    # Create immutable chunk with batch keys
    from codeweaver.core.chunks import BatchKeys
    batch_keys = BatchKeys(id=batch_id, idx=batch_index)
    return chunk.set_batch_keys(batch_keys)
```

### 4. Incorrect Language Import ✅
**Location**: `tests/contract/test_qdrant_provider.py`

**Problem**: Tests imported non-existent `Language` from `codeweaver.core.language` (remnant from old langchain dependency).

**Solution**: Removed `Language` import entirely and omitted the `language` parameter from `CodeChunk.model_construct()` calls.

### 5. UUID Version Mismatch ✅
**Location**: `tests/contract/test_qdrant_provider.py`

**Problem**: Tests used `uuid4()` for chunk IDs, but CodeWeaver expects UUID v7 throughout.

**Solution**: Changed all `uuid4()` calls to `uuid7()` for chunk ID generation.

## CodeWeaver Embedding Architecture

The correct flow for chunks with embeddings:

```python
# 1. Create chunk with uuid7() IDs
chunk = CodeChunk.model_construct(
    chunk_id=uuid7(),
    chunk_name="test.py:func",
    file_path=Path("test.py"),
    content="def func(): pass",
    line_range=Span(start=1, end=1, _source_id=uuid7()),
)

# 2. Register embeddings in global EmbeddingRegistry
registry = get_embedding_registry()
registry[chunk.chunk_id] = ChunkEmbeddings(
    sparse=sparse_batch_info,  # or None
    dense=dense_batch_info,     # or None
    chunk=chunk,
)

# 3. Create immutable chunk with batch keys
batch_keys = BatchKeys(id=batch_id, idx=batch_index)
chunk_with_embeddings = chunk.set_batch_keys(batch_keys)

# 4. Now chunk.dense_embedding and chunk.sparse_embedding properties work
```

**Key Points**:
- Chunks are immutable - `set_batch_keys()` returns a NEW chunk instance
- Embeddings are NOT stored in chunks - they're retrieved from the registry via properties
- `BatchKeys` is a NamedTuple: `(id: UUID7, idx: int, sparse: bool = False)`
- `ChunkEmbeddings` is a NamedTuple: `(sparse, dense, chunk)`

## Additional Fixes ✅

### 6. Sparse Vector BatchKeys Configuration ✅
**Location**: `tests/contract/test_qdrant_provider.py:65-125`

**Problem**: Chunks with sparse embeddings weren't retrievable because `BatchKeys(sparse=False)` by default - sparse embeddings need `sparse=True` flag set.

**Solution**: Updated `_register_chunk_embeddings()` helper to create separate batch keys for dense and sparse:

```python
# Create separate batch IDs for dense and sparse
dense_batch_id = uuid7() if dense is not None else None
sparse_batch_id = uuid7() if sparse is not None else None

# Add dense batch key if we have dense embeddings
if dense is not None:
    dense_batch_keys = BatchKeys(id=dense_batch_id, idx=batch_index, sparse=False)
    result_chunk = result_chunk.set_batch_keys(dense_batch_keys)

# Add sparse batch key if we have sparse embeddings
if sparse is not None:
    sparse_batch_keys = BatchKeys(id=sparse_batch_id, idx=batch_index, sparse=True)
    result_chunk = result_chunk.set_batch_keys(sparse_batch_keys)
```

### 7. Sparse Vector Upsert Bug ✅
**Location**: `src/codeweaver/providers/vector_stores/qdrant.py:292-306`

**Problem**: Code attempted to unpack `SparseEmbedding` as tuple but it's a NamedTuple with `.indices` and `.values` fields.

**Solution**: Access fields directly instead of unpacking:

```python
# Before (incorrect - trying to unpack NamedTuple):
indices, values = sparse.embeddings

# After (correct - accessing NamedTuple fields):
vectors["sparse"] = SparseVector(
    indices=list(sparse.embeddings.indices),
    values=list(sparse.embeddings.values)
)
```

### 8. Strengthened Test Assertions ✅
**Location**: `tests/contract/test_qdrant_provider.py` (lines 165-220)

**Problem**: Weak `if results:` assertions that pass even when search returns empty results.

**Solution**: Replaced with strong assertions that actually validate functionality:

```python
# Dense vector search (normalized scores):
assert len(results) > 0, "Search returned no results after upserting chunk with dense embeddings"
assert all(hasattr(r, "chunk") and hasattr(r, "score") for r in results), "Search results missing chunk or score attributes"
assert all(0.0 <= r.score <= 1.0 for r in results), "Search result scores out of valid range [0.0, 1.0]"

# Sparse/hybrid vector search (unbounded scores):
assert len(results) > 0, "Search returned no results after upserting chunk with sparse embeddings"
assert all(hasattr(r, "chunk") and hasattr(r, "score") for r in results), "Search results missing chunk or score attributes"
# Sparse vector scores can be unbounded (SPLADE/BM25), so we just check they're valid numbers
assert all(isinstance(r.score, (int, float)) and not isinstance(r.score, bool) for r in results), "Search result scores should be numeric"
```

**Note**: Sparse and hybrid vector search scores are not normalized to [0, 1] range - they use SPLADE/BM25-style unbounded scores.

## Test Results

**Before fixes**: Multiple failures with 0 search results, weak assertions, sparse vector bugs
**After all fixes**: All tests PASSED ✅

- `test_search_with_dense_vector` ✅
- `test_search_with_sparse_vector` ✅
- `test_search_with_hybrid_vectors` ✅
- `test_upsert_batch_of_chunks` ✅

The test now properly:
1. Creates chunks with uuid7() IDs
2. Registers embeddings in the global registry
3. Creates immutable chunks with batch keys
4. Upserts to Qdrant successfully
5. Retrieves results via search

## Files Modified

1. `src/codeweaver/agent_api/find_code/types.py` - Fixed sparse vector construction (NamedSparseVector)
2. `src/codeweaver/providers/vector_stores/qdrant.py` - Fixed sparse embedding field access bug
3. `tests/performance/test_vector_store_performance.py` - Fixed search API calls (vector= not query=)
4. `tests/contract/test_qdrant_provider.py` - Added embedding registration helper, fixed imports, fixed UUID versions, strengthened assertions, fixed sparse BatchKeys

## Lessons Learned

1. **CodeChunk.model_construct()** bypasses pydantic validation, so incorrect fields are silently ignored
2. **Embeddings live in a global registry**, not in chunks themselves
3. **Chunks are immutable** - must use `set_batch_keys()` to create new instances
4. **Test quality matters** - weak assertions (`if results:`) hide bugs
5. **Architecture documentation is critical** - the embedding flow was complex and undocumented

## Recommendations

1. ✅ ~~**Improve test assertions**~~ - COMPLETED: Replaced weak `if results:` checks with strong assertions
2. **Document embedding architecture** - Add architecture docs explaining the chunk → embedder → registry → vector store flow
3. **Create test fixtures** - Consider making `_register_chunk_embeddings()` a shared fixture across all test files
4. **Add validation** - Consider adding runtime checks that chunks have embeddings before upsert
5. **Sparse vector scoring** - Document that sparse/hybrid vector scores are unbounded (not normalized to [0,1])

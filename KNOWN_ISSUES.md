# Known Issues

## Sparse-Only Vector Search Not Finding Results (ISSUE-001)

**Status**: Known issue, requires investigation
**Severity**: Medium
**Created**: 2025-11-17
**Tests Affected**:
- `tests/integration/test_hybrid_storage.py::test_store_hybrid_embeddings` (sparse search assertion)
- `tests/integration/test_partial_embeddings.py::test_partial_embeddings`

### Description

Sparse-only vector searches using Qdrant are returning 0 results even when matching sparse embeddings have been stored. Dense-only and hybrid searches work correctly.

### Symptoms

1. Chunks with sparse embeddings upsert successfully to Qdrant
2. Dense-only searches find the chunks correctly
3. Hybrid searches (dense + sparse) work correctly
4. Sparse-only searches return empty results `[]` even with identical sparse vectors

### Investigation Findings

1. **Sparse embeddings are stored correctly**:
   - `SparseEmbedding` objects are properly created and registered
   - Qdrant collection includes sparse vector configuration with index
   - No errors during upsert operations

2. **Query generation appears correct**:
   - `StrategizedQuery.to_query()` generates proper `NamedSparseVector`
   - Query structure: `NamedSparseVector(name='sparse', vector=SparseVector(...))`
   - Uses `client.search()` API (not `query_points()`)

3. **Potential causes**:
   - Qdrant sparse vector search API compatibility issue
   - Sparse index configuration mismatch
   - Different API requirements for sparse-only vs hybrid searches
   - Possible issue with `NamedSparseVector` in search context vs storage

### Code Locations

- **Search implementation**: `/home/knitli/codeweaver-mcp/src/codeweaver/providers/vector_stores/qdrant_base.py`
  - Query generation: `StrategizedQuery.to_query()` (lines 400-434)
  - Search execution: `_execute_search_query()` (lines 354-393)
  - Sparse vector preparation: `_prepare_vectors()` (lines 475-513)

- **Test files**:
  - `/home/knitli/codeweaver-mcp/tests/integration/test_hybrid_storage.py` (line 91)
  - `/home/knitli/codeweaver-mcp/tests/integration/test_partial_embeddings.py` (line 76)

### Workarounds

1. **For users**: Use hybrid search (dense + sparse) instead of sparse-only
2. **For testing**: Tests marked with `@pytest.mark.xfail(reason="ISSUE-001")`

### Next Steps for Resolution

1. **Review Qdrant documentation** for sparse vector search API requirements
2. **Compare API calls** between hybrid (working) and sparse-only (failing) searches
3. **Test with Qdrant client directly** to isolate issue from CodeWeaver logic
4. **Check Qdrant version compatibility** - may need specific version for sparse search
5. **Consider alternative**: Implement sparse search via `query_points()` API like hybrid

### Related Code

```python
# Current sparse-only query generation (types.py:427-434)
if self.has_dense():
    assert self.dense is not None
    dense_vector = NamedVector(name="dense", vector=list(self.dense))
    return {"query_vector": dense_vector, **kwargs}
# Sparse-only path
assert self.sparse is not None
sparse_vector = SparseVector(
    indices=list(self.sparse.indices), values=list(self.sparse.values)
)
named_sparse = NamedSparseVector(name="sparse", vector=sparse_vector)
return {"query_vector": named_sparse, **kwargs}
```

### Test Results

```bash
# Dense search: ✅ PASSES - Returns results
# Hybrid search: ✅ PASSES - Returns results
# Sparse search: ❌ FAILS - Returns empty array []
```

### Dependencies

- `qdrant-client`: Check if version supports sparse-only searches with named vectors
- Collection configuration: Verify sparse index parameters are optimal

### Impact

- **Low user impact**: Hybrid search (the default) works correctly
- **Medium development impact**: Cannot test sparse-only fallback scenarios
- **No blocking issues**: Core functionality (hybrid search) is operational

# Real Provider Integration Tests (Tier 2)

## Overview

This directory contains **Tier 2 integration tests** that validate actual search behavior using real embedding providers, real vector storage, and real search operations.

### Two-Tier Testing Strategy

CodeWeaver uses a two-tier integration testing strategy:

| Tier | Purpose | Providers | Speed | Use Case |
|------|---------|-----------|-------|----------|
| **Tier 1** | Structure validation | Mock providers | Fast (<1s) | Response structure, error paths, API contracts |
| **Tier 2** | Behavior validation | **Real providers** | Slow (2-15s) | Search quality, end-to-end pipelines, actual behavior |

### Why Two Tiers?

**Tier 1 (Mock-based tests)** validate:
- ✅ "Does my code call the right methods?"
- ✅ Response structure and type constraints
- ✅ Error handling and edge cases
- ✅ Fast feedback for development

**BUT** they **cannot** validate:
- ❌ Does search actually find relevant code?
- ❌ Do embeddings capture semantic meaning?
- ❌ Can vector store perform similarity search?
- ❌ Does ranking prioritize best matches?

**Tier 2 (Real provider tests)** validate:
- ✅ Search actually works end-to-end
- ✅ Embeddings capture semantic meaning
- ✅ Vector search finds relevant results
- ✅ Performance meets SLA requirements

## Running Tests

### Quick Tier 1 Tests (Development)
```bash
# Fast tests with mocks - run during development
pytest -m "integration and not real_providers" tests/integration/
```

### Full Tier 2 Tests (Pre-commit/CI)
```bash
# Real provider tests - run before committing
pytest -m "integration and real_providers" tests/integration/real/
```

### Performance Benchmarks Only
```bash
# Just performance validation (slower)
pytest -m "integration and real_providers and benchmark" tests/integration/real/
```

### Run Everything
```bash
# All integration tests (both tiers)
pytest -m integration tests/integration/
```

## Test Files

### `test_search_behavior.py`
Validates search quality and semantic understanding:
- **Search finds authentication code** - validates embeddings capture auth concepts
- **Search finds database code** - validates SQL/database terminology
- **Search finds API endpoints** - validates REST API understanding
- **Search distinguishes concepts** - validates embeddings are semantically distinct
- **Search returns actual code** - validates chunking and content storage

**What these tests catch:**
- Embeddings don't capture semantic meaning
- Vector search returns irrelevant results
- Ranking algorithm broken
- Chunking produces unusable segments

### `test_full_pipeline.py`
Validates complete index → search workflows:
- **Full pipeline index then search** - most important test, validates entire system
- **Incremental indexing updates** - validates new files appear in search
- **Large codebase handling** - validates scale (20+ files)
- **File update handling** - validates re-indexing updates vectors
- **Error resilience** - validates partial failures don't break everything
- **Performance benchmarks** - validates SLA compliance (FR-037)

**What these tests catch:**
- Indexing doesn't actually store vectors
- Embedding dimensions incompatible with vector store
- Search can't find freshly indexed content
- Performance doesn't meet requirements

## Fixtures

### Provider Fixtures (`tests/integration/conftest.py`)

**Real Provider Fixtures:**
- `real_embedding_provider` - IBM Granite English R2 (lightweight, local, fast)
- `real_sparse_provider` - OpenSearch neural sparse encoding
- `real_reranking_provider` - MS MARCO MiniLM
- `real_vector_store` - Qdrant in-memory mode
- `real_provider_registry` - Complete provider ecosystem
- `real_providers` - **Main fixture** - patches registry with real providers

**Test Data Fixtures:**
- `known_test_codebase` - 5-file Python codebase with distinct semantic content
  - `auth.py` - Authentication and session management
  - `database.py` - Database connections and queries
  - `api.py` - REST API endpoints and routing
  - `config.py` - Configuration loading and validation
  - `utils.py` - Utility functions and helpers

### Using Real Providers in Tests

```python
@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_my_search_behavior(real_providers, known_test_codebase):
    """Test actual search behavior with real embeddings."""
    from codeweaver.agent_api.find_code import find_code

    # This uses REAL embeddings, REAL vector store, REAL search
    response = await find_code(
        query="authentication logic",
        cwd=str(known_test_codebase),
        index_if_needed=True,
    )

    # Validate actual behavior
    result_files = [r.file_path.name for r in response.results[:3]]
    assert "auth.py" in result_files, "Should actually find auth code"
```

## Model Selection

**Why these models?**

All models are **lightweight, local, and require no API keys**:

1. **IBM Granite English R2** (dense embeddings)
   - Fast CPU inference
   - Good semantic understanding for code
   - ~100MB model size
   - No API key required

2. **OpenSearch Neural Sparse** (sparse embeddings)
   - Lightweight sparse encoder
   - Good for hybrid search
   - Fast inference
   - No API key required

3. **MS MARCO MiniLM** (reranking)
   - Fast cross-encoder
   - Good relevance scoring
   - Works offline
   - No API key required

4. **Qdrant In-Memory** (vector storage)
   - No Docker required
   - Perfect for CI
   - Cleans up automatically
   - No external dependencies

## Performance Expectations

### Tier 1 (Mock) Tests
- **Duration:** <1 second per test
- **Use:** Development, fast feedback

### Tier 2 (Real Provider) Tests

**Search behavior tests:**
- **Duration:** 2-5 seconds per test
- **Why:** Real embedding generation (CPU intensive)

**Full pipeline tests:**
- **Duration:** 5-15 seconds per test
- **Why:** Indexing + embedding generation + search

**Performance benchmarks:**
- **Duration:** 10-60 seconds per test
- **Why:** Testing with larger codebases (20-50 files)

## Test Quality Principles

### What Makes a Good Tier 2 Test?

1. **Tests actual behavior, not structure**
   ```python
   # ✅ Good - validates search quality
   assert "auth.py" in top_results

   # ❌ Bad - just validates structure (use Tier 1)
   assert isinstance(response, FindCodeResponse)
   ```

2. **Clear production failure modes**
   ```python
   # ✅ Good - documents what could break
   """
   **Production failure modes this catches:**
   - Embeddings don't capture auth semantics
   - Vector search prioritizes wrong files
   - Ranking algorithm broken
   """
   ```

3. **Small but realistic test data**
   ```python
   # ✅ Good - 5 files, fast but validates quality
   known_test_codebase  # auth.py, database.py, api.py, etc.

   # ❌ Bad - 10,000 files, too slow for tests
   ```

4. **Validates semantic understanding**
   ```python
   # ✅ Good - tests embeddings understand concepts
   assert search("authentication") finds auth.py
   assert search("database") finds database.py
   assert results_differ_by_query()
   ```

### What to Test in Tier 2

**DO test:**
- ✅ Search finds semantically relevant code
- ✅ Different queries return different results
- ✅ Index → search pipeline works end-to-end
- ✅ Performance meets SLA requirements
- ✅ Quality doesn't degrade with scale

**DON'T test (use Tier 1):**
- ❌ Response structure validation
- ❌ Error message formats
- ❌ Type constraints
- ❌ API contracts
- ❌ Configuration validation

## CI Integration

### GitHub Actions

```yaml
- name: Run Fast Tests (Tier 1)
  run: pytest -m "integration and not real_providers"

- name: Run Quality Tests (Tier 2)
  run: pytest -m "integration and real_providers and not slow"

- name: Run Performance Benchmarks (Tier 2)
  run: pytest -m "integration and real_providers and benchmark"
  # Only on main branch or release
```

### Local Development

```bash
# Fast feedback during development
mise run test  # Runs Tier 1 only by default

# Before committing - validate search quality
pytest -m "integration and real_providers and not benchmark"

# Before release - full validation
pytest -m "integration and real_providers"
```

## Troubleshooting

### Tests are slow
- ✅ **Expected:** Real provider tests are 10-50x slower than mocks
- ✅ **By design:** Generating real embeddings is CPU intensive
- ✅ **Solution:** Use Tier 1 (mocks) for development, Tier 2 for validation

### Tests fail with "Model not found"
```bash
# Download models manually
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('ibm-granite/granite-embedding-english-r2')"
```

### Tests fail with dimension mismatch
- Check embedding model outputs correct dimensions
- Verify vector store configured for model dimensions
- This is exactly the kind of bug Tier 2 tests catch!

### Search doesn't find expected files
- ✅ **This is a real quality issue** - don't change the test!
- Investigate:
  - Are embeddings capturing semantic meaning?
  - Is chunking producing good segments?
  - Is ranking algorithm working?
  - This is precisely what these tests are designed to catch

## Contributing

### Adding New Tier 2 Tests

1. **Mark with `@pytest.mark.real_providers`**
   ```python
   @pytest.mark.integration
   @pytest.mark.real_providers
   @pytest.mark.asyncio
   async def test_new_behavior(real_providers, known_test_codebase):
   ```

2. **Document what could break**
   ```python
   """
   **Production failure modes this catches:**
   - [Specific embedding issue]
   - [Specific search issue]
   - [Specific quality issue]
   """
   ```

3. **Use small but realistic data**
   - Prefer `known_test_codebase` (5 files, fast)
   - Create larger datasets only for scale tests
   - Mark slow tests: `@pytest.mark.slow`

4. **Validate behavior, not structure**
   - Focus on search quality
   - Validate semantic understanding
   - Check actual functionality

### When to Add Tier 2 vs Tier 1

**Add Tier 2 test if:**
- Testing search quality or relevance
- Validating embeddings capture semantics
- Testing full pipeline coordination
- Benchmarking performance

**Add Tier 1 test if:**
- Testing error handling
- Validating response structure
- Testing configuration
- Need fast feedback

## FAQ

**Q: Why do we need both tiers?**
A: Mocks validate structure (fast feedback), real providers validate behavior (quality assurance). Both are essential.

**Q: Can I use API-based providers (Voyage, OpenAI)?**
A: For local development, yes. But CI uses local models for speed and reliability. Configure via environment variables.

**Q: How do I debug failing Tier 2 tests?**
A: These tests catch real quality issues. Don't disable them - investigate the root cause in embeddings, chunking, or search logic.

**Q: Are Tier 2 tests required for all PRs?**
A: Yes, but only non-benchmark tests. Benchmark tests run on main/release only.

**Q: How do I make Tier 2 tests faster?**
A: You don't - they validate real behavior which is inherently slower. Use Tier 1 for development speed.

## References

- [Project Constitution](../../../.specify/memory/constitution.md) - Testing philosophy
- [CODE_STYLE.md](../../../CODE_STYLE.md) - Code quality standards
- [ARCHITECTURE.md](../../../ARCHITECTURE.md) - System design
- [Pytest markers](../../../pyproject.toml#L576) - Available test markers

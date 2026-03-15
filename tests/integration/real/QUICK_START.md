<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Quick Start: Real Provider Tests

## TL;DR

```bash
# Development (fast mocks)
pytest -m "integration and not real_providers"

# Pre-commit (quality validation)
pytest -m "integration and real_providers and not benchmark"

# Full validation (CI)
pytest -m integration
```

## What's Different?

### Tier 1 (Existing - Mock-based)
```python
# Tests structure - FAST (<1s)
@pytest.mark.integration
async def test_structure(configured_providers):
    response = await find_code("query")
    assert isinstance(response, FindCodeResponse)  # ✅ Structure
```

### Tier 2 (NEW - Real providers)
```python
# Tests behavior - SLOW (2-10s)
@pytest.mark.integration
@pytest.mark.real_providers
async def test_behavior(real_providers, known_test_codebase):
    response = await find_code("authentication", cwd=str(known_test_codebase))
    assert "auth.py" in [r.file_path.name for r in response.results]  # ✅ Quality
```

## When to Use Which?

| Scenario | Use | Why |
|----------|-----|-----|
| Writing new feature | Tier 1 (mocks) | Fast feedback |
| Before committing | Tier 2 (real) | Validate quality |
| Debugging search issue | Tier 2 (real) | See actual behavior |
| CI pipeline | Both tiers | Complete validation |

## Writing a New Real Provider Test

```python
@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_my_search_quality(real_providers, known_test_codebase):
    """Brief description of what quality aspect this tests.

    **Production failure modes this catches:**
    - Specific bug type 1
    - Specific bug type 2
    """
    response = await find_code(
        query="your semantic query",
        cwd=str(known_test_codebase),
        index_if_needed=True,
    )

    # Validate actual behavior, not just structure
    result_files = [r.file_path.name for r in response.results[:3]]
    assert "expected_file.py" in result_files, "Should find relevant code"
```

## Common Issues

### "Tests are slow"
✅ **Expected** - Real embeddings are CPU intensive. Use Tier 1 for development.

### "Can't find model"
```bash
# Download models manually
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('ibm-granite/granite-embedding-30m-english')"
```

### "Test fails - auth.py not found"
✅ **This is a real quality bug** - Don't disable the test, investigate the issue!

## Available Fixtures

- `real_providers` - Complete real provider ecosystem (main fixture)
- `known_test_codebase` - 5-file Python codebase (auth, database, api, config, utils)
- `real_embedding_provider` - IBM Granite English R2
- `real_sparse_provider` - OpenSearch neural sparse
- `real_reranking_provider` - MS MARCO MiniLM
- `real_vector_store` - Qdrant in-memory

## Test Markers

```bash
# Filter by marker
pytest -m real_providers          # All real provider tests
pytest -m benchmark               # Performance tests only
pytest -m "real_providers and not slow"  # Fast real tests
```

## Full Documentation

See [README.md](README.md) for comprehensive documentation including:
- Detailed architecture explanation
- Model selection rationale
- Performance expectations
- Troubleshooting guide
- Contributing guidelines

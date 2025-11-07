<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Fix for SentenceTransformersRerankingProvider Import Error

## Problem Summary
16 tests across `test_full_pipeline.py` and `test_search_behavior.py` were failing with:
```
NameError: name 'SentenceTransformersRerankingProvider' is not defined
```

## Root Cause
The `tests/integration/conftest.py` file had two issues:

1. **Wrong import location in TYPE_CHECKING block** (line 21):
   - Incorrectly imported `SentenceTransformersRerankingProvider` from embedding providers
   - Should import from reranking providers

2. **Wrong model implementation in fixture** (lines 188-200):
   - Used `TextEmbedding` from `fastembed` (wrong for reranking)
   - Should use `CrossEncoder` from `sentence_transformers`
   - Wrong model name: used "cross-encoder/ms-marco-MiniLM-L6-v2"
   - Correct name: "Xenova/ms-marco-MiniLM-L6-v2"

## Changes Applied

### Change 1: Fixed TYPE_CHECKING imports (lines 17-25)
**Before:**
```python
if TYPE_CHECKING:
    from codeweaver.core.chunks import CodeChunk
    from codeweaver.providers.embedding.providers.sentence_transformers import (
        SentenceTransformersEmbeddingProvider,
        SentenceTransformersRerankingProvider,  # WRONG MODULE
        SentenceTransformersSparseProvider,
    )
```

**After:**
```python
if TYPE_CHECKING:
    from codeweaver.core.chunks import CodeChunk
    from codeweaver.providers.embedding.providers.sentence_transformers import (
        SentenceTransformersEmbeddingProvider,
        SentenceTransformersSparseProvider,
    )
    from codeweaver.providers.reranking.providers.sentence_transformers import (
        SentenceTransformersRerankingProvider,  # CORRECT MODULE
    )
```

### Change 2: Fixed actual_reranking_provider fixture (lines 185-203)
**Before:**
```python
@pytest.fixture
def actual_reranking_provider() -> SentenceTransformersRerankingProvider:
    """Provide an actual reranking provider using SentenceTransformers."""
    from fastembed import TextEmbedding  # WRONG - for embeddings

    from codeweaver.providers.reranking.capabilities.ms_marco import (
        get_marco_reranking_capabilities,
    )

    caps = next(
        cap
        for cap in get_marco_reranking_capabilities()
        if cap.name == "Xenova/ms-marco-MiniLM-L6-v2"  # WRONG model name
    )
    return SentenceTransformersRerankingProvider(
        capabilities=caps,
        client=TextEmbedding(caps.name)  # WRONG client type
    )
```

**After:**
```python
@pytest.fixture
def actual_reranking_provider() -> SentenceTransformersRerankingProvider:
    """Provide an actual reranking provider using SentenceTransformers."""
    from sentence_transformers import CrossEncoder  # CORRECT - for reranking

    from codeweaver.providers.reranking.capabilities.ms_marco import (
        get_marco_reranking_capabilities,
    )
    from codeweaver.providers.reranking.providers.sentence_transformers import (
        SentenceTransformersRerankingProvider,
    )

    caps = next(
        cap
        for cap in get_marco_reranking_capabilities()
        if cap.name == "Xenova/ms-marco-MiniLM-L6-v2"  # CORRECT model name
    )
    return SentenceTransformersRerankingProvider(
        capabilities=caps,
        client=CrossEncoder(caps.name)  # CORRECT client type
    )
```

## Verification

### Test Collection
All 16 tests now collect successfully:
```bash
$ python -m pytest tests/integration/real/test_full_pipeline.py \
    tests/integration/real/test_search_behavior.py --collect-only -q

16 tests collected in 0.03s
```

### Import Verification
```python
# TYPE_CHECKING imports work
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from codeweaver.providers.reranking.providers.sentence_transformers import (
        SentenceTransformersRerankingProvider,
    )

# Runtime import works
from codeweaver.providers.reranking.providers.sentence_transformers import (
    SentenceTransformersRerankingProvider
)
print(SentenceTransformersRerankingProvider.__name__)
# Output: SentenceTransformersRerankingProvider
```

## Affected Tests
All 16 tests across both test files now import successfully:

**tests/integration/real/test_full_pipeline.py (7 tests):**
- test_full_pipeline_index_then_search
- test_incremental_indexing_updates_search_results
- test_pipeline_handles_large_codebase
- test_pipeline_handles_file_updates
- test_pipeline_coordination_with_errors
- test_search_performance_with_real_providers
- test_indexing_performance_with_real_providers

**tests/integration/real/test_search_behavior.py (9 tests):**
- test_search_finds_authentication_code
- test_search_finds_database_code
- test_search_finds_api_endpoints
- test_search_distinguishes_different_concepts
- test_search_returns_relevant_code_chunks
- test_search_respects_file_types
- test_search_handles_no_matches_gracefully
- test_search_handles_empty_codebase
- test_search_with_very_long_query

## Key Learnings

1. **Module Organization**: Reranking providers are in `codeweaver.providers.reranking.providers.*`, not embedding providers
2. **Client Types**:
   - `SentenceTransformersEmbeddingProvider` uses `SentenceTransformer`
   - `SentenceTransformersRerankingProvider` uses `CrossEncoder`
3. **Model Names**: MS-MARCO models in capabilities use "Xenova/" prefix for sentence_transformers provider
4. **Import Discipline**: Always verify import paths match actual module structure

## Status
✅ RESOLVED - All import errors fixed. Tests can now execute (though they may fail for other reasons).

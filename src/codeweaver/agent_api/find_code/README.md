<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# find_code Package

The `find_code` package provides CodeWeaver's semantic code search functionality. It has been designed as a modular, extensible package with clear separation of concerns.

## Quick Start

```python
from codeweaver.agent_api.find_code import find_code

# Basic usage
response = await find_code("how does authentication work")

# With options
response = await find_code(
    "find login bugs",
    intent=IntentType.DEBUG,
    include_tests=True,
    focus_languages=("python", "javascript"),
    max_results=20
)
```

## Package Structure

```
find_code/
├── __init__.py       # Main entry point (find_code function)
├── conversion.py     # SearchResult → CodeMatch conversion
├── filters.py        # Post-search filtering
├── pipeline.py       # Search pipeline (embedding, vector search)
├── response.py       # Response building and metadata
├── scoring.py        # Score calculation and reranking
└── ARCHITECTURE.md   # Detailed architecture documentation
```

## Modules

### Core Function (`__init__.py`)
- **`find_code()`** - Main async function for semantic code search
- **`MatchedSection`** - NamedTuple representing matched code sections

### Utilities

#### `conversion.py`
Converts between different result formats:
- `convert_search_result_to_code_match()` - Vector store → API format
- `create_code_chunk_from_result()` - String content → CodeChunk

#### `filters.py`
Post-search filtering:
- `filter_test_files()` - Filter by test/non-test
- `filter_by_languages()` - Filter by programming language
- `apply_filters()` - Apply all filters

#### `pipeline.py`
Search pipeline orchestration:
- `embed_query()` - Generate embeddings
- `build_query_vector()` - Construct search vector
- `execute_vector_search()` - Query vector store
- `rerank_results()` - Optional reranking

#### `response.py`
Response building:
- `build_success_response()` - Successful search response
- `build_error_response()` - Error response
- `calculate_token_count()` - Token estimation
- `generate_summary()` - Human-readable summary
- `extract_languages()` - Unique languages in results

#### `scoring.py`
Score calculations:
- `apply_hybrid_weights()` - Combine dense/sparse scores
- `apply_semantic_weighting()` - Intent-based boosting
- `process_reranked_results()` - Process reranked results
- `process_unranked_results()` - Process without reranking

## Extension Points

### Adding a New Filter

```python
# In filters.py
def filter_by_size(candidates, max_size):
    """Filter by maximum file size."""
    return [c for c in candidates if c.size <= max_size]
```

### Adding a New Scoring Strategy

```python
# In scoring.py
def apply_recency_boost(score, modified_date):
    """Boost recently modified files."""
    age_days = (datetime.now() - modified_date).days
    return score * (1 + max(0, 1 - age_days/365) * 0.1)
```

### Adding a New Pipeline Step

```python
# In pipeline.py
async def expand_query(query):
    """Expand query with synonyms."""
    # Implementation
    return expanded_query
```

## Design Principles

1. **Single Responsibility** - Each module has one clear purpose
2. **Composability** - Functions can be composed and reused
3. **Testability** - Components can be tested in isolation
4. **Extensibility** - New functionality can be added without modifying core logic
5. **Backward Compatibility** - All existing imports continue to work

## Testing

```python
# Test individual components
from codeweaver.agent_api.find_code.filters import filter_by_languages

candidates = [...]  # SearchResult objects
filtered = filter_by_languages(candidates, ("python", "javascript"))
```

## See Also

- [ARCHITECTURE.md](./ARCHITECTURE.md) - Detailed architecture documentation
- [Contract Tests](../../../tests/contract/test_find_code_contract.py) - API contract tests
- [Integration Tests](../../../tests/integration/) - End-to-end tests

<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# find_code Package Architecture

## Overview

The `find_code` package has been refactored into a modular structure to improve maintainability, extensibility, and testability. Previously a single 529-line module, it's now organized into focused components with clear responsibilities.

## Package Structure

```
codeweaver/agent_api/find_code/
├── __init__.py       # Main entry point and orchestration
├── conversion.py     # Result format conversions
├── filters.py        # Post-search filtering logic
├── intent.py         # Intent types and resolution
├── pipeline.py       # Search pipeline orchestration
├── response.py       # Response building and metadata
├── types.py          # Shared types
├── results.py        # result object (isolated to avoid circular imports)
└── scoring.py        # Scoring and reranking logic

```

## Module Responsibilities

### `__init__.py` - Main Entry Point
The main `find_code()` function that orchestrates the entire search pipeline:
1. Intent detection
2. Query embedding
3. Vector search execution
4. Filtering
5. Scoring and reranking
6. Response building

**Exports:**
- `find_code()` - Async function for semantic code search
- `MatchedSection` - NamedTuple for matched code sections

### `conversion.py` - Result Conversions
Handles conversion between different result formats.

**Key Functions:**
- `convert_search_result_to_code_match()` - Converts SearchResult to CodeMatch
- `create_code_chunk_from_result()` - Creates CodeChunk from string content

**Purpose:** Isolates the complexity of mapping between vector store results and API response formats.

### `filters.py` - Post-Search Filtering
Applies various filters to search results.

**Key Functions:**
- `filter_test_files()` - Filters out test files based on path heuristics
- `filter_by_languages()` - Filters results by programming language
- `apply_filters()` - Unified interface for applying all filters

**Purpose:** Makes it easy to add new filtering strategies without modifying core search logic.

### `intent.py` - Intent Identification and Weighting

### `pipeline.py` - Search Pipeline
Orchestrates the search pipeline components.

**Key Functions:**
- `embed_query()` - Generates dense and sparse embeddings
- `build_query_vector()` - Constructs query vector for search
- `execute_vector_search()` - Executes search against vector store
- `rerank_results()` - Optional reranking step

**Purpose:** Separates provider interactions from business logic, making it easier to swap or extend providers.

### `response.py` - Response Building
Constructs FindCodeResponseSummary objects and calculates metadata.

**Key Functions:**
- `calculate_token_count()` - Estimates token count from matches
- `generate_summary()` - Creates human-readable summary
- `extract_languages()` - Extracts unique languages from results
- `build_success_response()` - Builds successful response
- `build_error_response()` - Builds error response with graceful degradation

**Purpose:** Centralizes response building logic, making it easier to customize output formatting.

### `scoring.py` - Scoring and Reranking
Handles all score calculations and adjustments.

**Key Functions:**
- `apply_hybrid_weights()` - Combines dense and sparse scores
- `apply_semantic_weighting()` - Applies intent-based semantic boosts
- `process_reranked_results()` - Processes results with reranking scores
- `process_unranked_results()` - Processes results without reranking

**Purpose:** Centralizes scoring logic, making it easier to tune and extend scoring strategies.

## Benefits of This Architecture

### 1. Modularity
Each module has a single, well-defined responsibility. This makes the code easier to understand and modify.

### 2. Extensibility
New features can be added by extending individual modules:
- Add new filters in `filters.py`
- Add new intent approaches in `intent.py`
- Add new scoring strategies in `scoring.py`
- Add new pipeline steps in `pipeline.py`
- Add new result formats in `conversion.py`

### 3. Testability
Components can be tested in isolation:
- Unit test filters without setting up embeddings
- Test scoring logic without running searches
- Mock individual pipeline steps

### 4. Maintainability
Clear separation of concerns makes it easier to:
- Locate bugs
- Understand code flow
- Make surgical changes
- Review code

### 5. Backward Compatibility
All existing imports continue to work:
```python
# Still works exactly as before
from codeweaver.agent_api.find_code import find_code, MatchedSection
from codeweaver.agent_api import find_code
```

### 6. Improved Code Size
The original 529-line monolithic module has been broken down into 6 focused modules:
- `__init__.py`: 220 lines (main orchestration)
- `pipeline.py`: 215 lines (search pipeline)
- `response.py`: 151 lines (response building)
- `scoring.py`: 167 lines (scoring logic)
- `conversion.py`: 131 lines (format conversions)
- `filters.py`: 87 lines (filtering logic)

Each module is now under 250 lines and has a single, clear responsibility.

## Future Extensions

The modular structure makes it straightforward to add:

### New Filters
```python
# In filters.py
def filter_by_size(candidates, max_size):
    """Filter by file size."""
    return [c for c in candidates if c.size <= max_size]
```

### New Scoring Strategies
```python
# In scoring.py
def apply_recency_boost(score, file_modified_date):
    """Boost score for recently modified files."""
    age_days = (datetime.now() - file_modified_date).days
    boost = max(0, 1 - (age_days / 365))
    return score * (1 + boost * 0.1)
```

### New Pipeline Steps
```python
# In pipeline.py
async def apply_query_expansion(query):
    """Expand query with synonyms."""
    # Implementation here
    pass
```

## Migration Notes

No changes are required for existing code. The refactoring:
- Preserves the exact same public API
- Maintains all function signatures
- Keeps all type hints and defaults
- Retains all docstrings

All imports and function calls work identically to before.

# find_code Refactoring Examples

This document provides practical examples of how the new modular structure makes it easier to extend and maintain the find_code functionality.

## Example 1: Adding a New Filter

**Before** (monolithic structure):
- Had to modify the large find_code.py file
- Filter logic mixed with search logic
- Hard to test in isolation

**After** (modular structure):

```python
# In src/codeweaver/agent_api/find_code/filters.py

def filter_by_file_size(
    candidates: list[SearchResult],
    max_size_kb: int = 100
) -> list[SearchResult]:
    """Filter out files larger than max_size_kb.
    
    Args:
        candidates: List of search results to filter
        max_size_kb: Maximum file size in kilobytes
        
    Returns:
        Filtered list of search results
    """
    max_bytes = max_size_kb * 1024
    return [
        c for c in candidates 
        if c.file_path and c.file_path.stat().st_size <= max_bytes
    ]

# Update apply_filters to use the new filter
def apply_filters(
    candidates: list[SearchResult],
    *,
    include_tests: bool = False,
    focus_languages: tuple[str, ...] | None = None,
    max_file_size_kb: int | None = None,  # New parameter
) -> list[SearchResult]:
    """Apply all configured filters to search results."""
    filtered = filter_test_files(candidates, include_tests)
    filtered = filter_by_languages(filtered, focus_languages)
    if max_file_size_kb:
        filtered = filter_by_file_size(filtered, max_file_size_kb)
    return filtered
```

## Example 2: Adding a Custom Scoring Strategy

**Before**: Scoring logic buried in the main function

**After**: Clean, composable scoring functions

```python
# In src/codeweaver/agent_api/find_code/scoring.py

def apply_recency_boost(
    score: float,
    file_modified_date: datetime,
    max_boost: float = 0.15
) -> float:
    """Boost scores for recently modified files.
    
    Args:
        score: Base relevance score
        file_modified_date: When the file was last modified
        max_boost: Maximum boost percentage (default: 15%)
        
    Returns:
        Adjusted score with recency boost
    """
    age_days = (datetime.now() - file_modified_date).days
    # Linear decay over 365 days
    recency_factor = max(0, 1 - (age_days / 365))
    return score * (1 + recency_factor * max_boost)

# Use it in process_unranked_results or process_reranked_results
def process_unranked_results_with_recency(
    candidates: list[SearchResult],
    intent_type: IntentType,
    agent_task: AgentTask,
    apply_recency: bool = False,
) -> list[SearchResult]:
    """Process results with optional recency boosting."""
    scored_candidates: list[SearchResult] = []
    
    for candidate in candidates:
        base_score = candidate.score
        chunk_obj = candidate.content if isinstance(candidate.content, CodeChunk) else None
        
        # Apply semantic weighting
        final_score = apply_semantic_weighting(base_score, chunk_obj, intent_type, agent_task)
        
        # Apply recency boost if enabled
        if apply_recency and candidate.file_path:
            modified_date = datetime.fromtimestamp(candidate.file_path.stat().st_mtime)
            final_score = apply_recency_boost(final_score, modified_date)
        
        scored_candidate = candidate.model_copy(update={"relevance_score": final_score})
        scored_candidates.append(scored_candidate)
    
    return scored_candidates
```

## Example 3: Adding Query Preprocessing

**Before**: Would require modifying the main find_code function

**After**: Add a clean pipeline step

```python
# In src/codeweaver/agent_api/find_code/pipeline.py

async def expand_query_with_synonyms(
    query: str,
    synonym_service: SynonymService
) -> str:
    """Expand query with relevant synonyms.
    
    Args:
        query: Original query string
        synonym_service: Service for finding synonyms
        
    Returns:
        Expanded query with synonyms
    """
    # Extract key terms
    terms = extract_key_terms(query)
    
    # Find synonyms for each term
    expanded_terms = []
    for term in terms:
        synonyms = await synonym_service.get_synonyms(term)
        expanded_terms.extend([term] + synonyms[:2])  # Original + top 2 synonyms
    
    # Reconstruct query
    return " ".join(expanded_terms)

# Then use it in the main pipeline
async def find_code(...):
    # ... existing code ...
    
    # NEW: Query expansion step (optional)
    if enable_query_expansion:
        query = await expand_query_with_synonyms(query, synonym_service)
    
    # Step 2: Embed query (dense + sparse)
    dense_embedding, sparse_embedding = await embed_query(query)
    # ... rest of the pipeline ...
```

## Example 4: Custom Response Formatting

**Before**: Response building logic mixed with search logic

**After**: Clean response builder functions

```python
# In src/codeweaver/agent_api/find_code/response.py

def build_detailed_response(
    code_matches: list[CodeMatch],
    query: str,
    intent_type: IntentType,
    total_candidates: int,
    token_limit: int,
    execution_time_ms: float,
    strategies_used: list[SearchStrategy],
    include_snippets: bool = True,
) -> FindCodeResponseSummary:
    """Build response with detailed code snippets.
    
    Same as build_success_response but includes code snippets in summary.
    """
    base_summary = generate_summary(code_matches, intent_type, query)
    
    if include_snippets and code_matches:
        # Add snippets from top 3 matches
        snippets = []
        for match in code_matches[:3]:
            snippet = match.content.content[:100] + "..."  # First 100 chars
            snippets.append(f"  {match.file.path.name}: {snippet}")
        
        detailed_summary = f"{base_summary}\n\nTop snippets:\n" + "\n".join(snippets)
    else:
        detailed_summary = base_summary
    
    return FindCodeResponseSummary(
        matches=code_matches,
        summary=detailed_summary[:1000],
        query_intent=intent_type,
        total_matches=total_candidates,
        total_results=len(code_matches),
        token_count=calculate_token_count(code_matches, token_limit),
        execution_time_ms=execution_time_ms,
        search_strategy=tuple(strategies_used),
        languages_found=extract_languages(code_matches),
    )
```

## Example 5: Testing Individual Components

**Before**: Hard to test components in isolation

**After**: Easy to write focused unit tests

```python
# tests/unit/agent_api/find_code/test_filters.py

import pytest
from codeweaver.agent_api.find_code.filters import (
    filter_by_languages,
    filter_test_files,
)

class TestFilters:
    def test_filter_test_files_excludes_tests(self):
        """Test that test files are filtered out."""
        # Create mock candidates
        candidates = [
            SearchResult(content="code", file_path=Path("src/main.py")),
            SearchResult(content="test", file_path=Path("tests/test_main.py")),
        ]
        
        # Filter
        filtered = filter_test_files(candidates, include_tests=False)
        
        # Verify
        assert len(filtered) == 1
        assert "test" not in str(filtered[0].file_path)
    
    def test_filter_by_languages_python_only(self):
        """Test language filtering."""
        candidates = [
            create_candidate_with_language("python"),
            create_candidate_with_language("javascript"),
        ]
        
        filtered = filter_by_languages(candidates, ("python",))
        
        assert len(filtered) == 1
        assert filtered[0].content.language == "python"

# tests/unit/agent_api/find_code/test_scoring.py

from codeweaver.agent_api.find_code.scoring import apply_semantic_weighting

class TestScoring:
    def test_semantic_weighting_debug_intent(self):
        """Test semantic weighting for debug intent."""
        chunk = create_mock_chunk_with_debug_importance(0.8)
        
        score = apply_semantic_weighting(
            base_score=0.5,
            chunk=chunk,
            intent_type=IntentType.DEBUG,
            agent_task=AgentTask.DEBUG,
        )
        
        # Should be boosted
        assert score > 0.5
        # Boost should be reasonable (not more than 20%)
        assert score <= 0.5 * 1.2
```

## Benefits Summary

### Modularity
- Each example shows focused changes to a single module
- No need to understand the entire 529-line file
- Changes are localized and predictable

### Extensibility
- New features added as new functions
- Existing code mostly unchanged
- Clear extension points

### Testability
- Each component can be tested independently
- Mock only what you need
- Fast, focused unit tests

### Maintainability
- Easy to find where to make changes
- Clear module responsibilities
- Self-documenting structure

## Migration Path

For teams adopting this structure:

1. **Start Simple**: Use the existing `find_code()` function as-is
2. **Extend Gradually**: Add custom filters or scoring as needed
3. **Test Components**: Write unit tests for new components
4. **Compose**: Combine components to create custom search flows
5. **Share**: Package custom components as reusable modules

## Future Enhancements

The modular structure makes it easy to add:

- **Multi-stage filtering**: Apply filters at different pipeline stages
- **Pluggable embeddings**: Swap embedding providers dynamically
- **A/B testing**: Compare different scoring strategies
- **Custom pipelines**: Create domain-specific search pipelines
- **Metrics collection**: Track performance of individual components

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Response building utilities for find_code.

This module handles the construction of FindCodeResponseSummary objects
from search results, including summary generation and metadata calculation.
"""

from __future__ import annotations

from codeweaver.agent_api.find_code.intent import IntentType
from codeweaver.agent_api.find_code.types import CodeMatch, FindCodeResponseSummary, SearchStrategy
from codeweaver.core.language import ConfigLanguage, SemanticSearchLanguage
from codeweaver.core.types import LanguageName


def calculate_token_count(code_matches: list[CodeMatch], token_limit: int) -> int:
    """Calculate approximate token count from code matches.

    Args:
        code_matches: List of code matches to count tokens for
        token_limit: Maximum token limit to enforce

    Returns:
        Estimated token count, capped at token_limit
    """
    total_tokens_raw = sum(
        len(m.content.content.split()) * 1.3  # Rough token estimate
        for m in code_matches
        if hasattr(m.content, "content") and m.content.content
    )
    return min(int(total_tokens_raw), token_limit)


def generate_summary(code_matches: list[CodeMatch], intent_type: IntentType, query: str) -> str:
    """Generate a human-readable summary of search results.

    Args:
        code_matches: List of code matches
        intent_type: Detected query intent
        query: Original search query

    Returns:
        Summary string (max 1000 characters)
    """
    if code_matches:
        # Extract top file names
        top_unique_files: set[str] = {m.file.path.name for m in code_matches[:3]}
        top_files: list[str] = list(top_unique_files)
        summary = (
            f"Found {len(code_matches)} relevant matches "
            f"for {intent_type.value} query. "
            f"Top results in: {', '.join(top_files[:3])}"
        )
    else:
        summary = f"No matches found for query: '{query}'"

    return summary[:1000]  # Enforce max_length


def extract_languages(
    code_matches: list[CodeMatch],
) -> tuple[SemanticSearchLanguage | LanguageName, ...]:
    """Extract unique programming languages from code matches.

    Args:
        code_matches: List of code matches

    Returns:
        Tuple of unique languages found (excludes ConfigLanguage)
    """
    languages: set[SemanticSearchLanguage | LanguageName | ConfigLanguage] = {
        m.file.ext_kind.language for m in code_matches if m.file.ext_kind is not None
    }
    return tuple(lang for lang in languages if not isinstance(lang, ConfigLanguage))


def build_success_response(
    code_matches: list[CodeMatch],
    query: str,
    intent_type: IntentType,
    total_candidates: int,
    token_limit: int,
    execution_time_ms: float,
    strategies_used: list[SearchStrategy],
) -> FindCodeResponseSummary:
    """Build a successful FindCodeResponseSummary.

    Args:
        code_matches: List of code matches to include
        query: Original search query
        intent_type: Detected query intent
        total_candidates: Total number of candidates before limiting
        token_limit: Maximum token limit
        execution_time_ms: Execution time in milliseconds
        strategies_used: List of search strategies used

    Returns:
        FindCodeResponseSummary with all fields populated
    """
    # Determine search mode from strategies
    search_mode = None
    if SearchStrategy.HYBRID_SEARCH in strategies_used:
        search_mode = "hybrid"
    elif SearchStrategy.DENSE_ONLY in strategies_used:
        search_mode = "dense_only"
    elif SearchStrategy.SPARSE_ONLY in strategies_used:
        search_mode = "sparse_only"
    elif SearchStrategy.KEYWORD_FALLBACK in strategies_used:
        search_mode = "keyword"

    # Get indexing state from indexer if available
    indexing_state = None
    index_coverage = None
    warnings = []
    status = "success"

    # NOTE: Indexer state tracking not yet implemented
    # When implemented, this will check global indexer instance
    # For now, we mark state as unknown
    indexing_state = "unknown"

    # Add warnings for degraded search modes
    if search_mode == "sparse_only":
        warnings.append("Dense embeddings unavailable - using sparse search only (degraded mode)")
        status = "partial"
    elif search_mode == "dense_only":
        warnings.append("Sparse embeddings unavailable - using dense search only")
    elif search_mode == "keyword":
        warnings.append("Embedding providers unavailable - using keyword fallback")
        status = "partial"

    return FindCodeResponseSummary(
        matches=code_matches,
        summary=generate_summary(code_matches, intent_type, query),
        query_intent=intent_type,
        total_matches=total_candidates,
        total_results=len(code_matches),
        token_count=calculate_token_count(code_matches, token_limit),
        execution_time_ms=execution_time_ms,
        search_strategy=tuple(strategies_used),
        languages_found=extract_languages(code_matches),
        status=status,
        warnings=warnings,
        indexing_state=indexing_state,
        index_coverage=index_coverage,
        search_mode=search_mode,
        metadata={},
    )


def build_error_response(
    error: Exception, query_intent: IntentType | None, execution_time_ms: float
) -> FindCodeResponseSummary:
    """Build an error response with graceful degradation.

    Args:
        error: Exception that occurred
        query_intent: Optional detected query intent
        execution_time_ms: Execution time in milliseconds

    Returns:
        FindCodeResponseSummary indicating failure
    """
    # Get indexing state even in error case
    # NOTE: Indexer state tracking not yet implemented
    # When implemented, this will check global indexer instance
    # For now, we mark state as unknown
    indexing_state = "unknown"
    index_coverage = None

    return FindCodeResponseSummary(
        matches=[],
        summary=f"Search failed: {str(error)[:500]}",
        query_intent=query_intent,
        total_matches=0,
        total_results=0,
        token_count=0,
        execution_time_ms=execution_time_ms,
        search_strategy=(SearchStrategy.KEYWORD_FALLBACK,),
        languages_found=(),
        status="error",
        warnings=[f"Critical error: {type(error).__name__}: {str(error)[:200]}"],
        indexing_state=indexing_state,
        index_coverage=index_coverage,
        search_mode="keyword",
        metadata={},
    )


__all__ = (
    "build_error_response",
    "build_success_response",
    "calculate_token_count",
    "extract_languages",
    "generate_summary",
)

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Response building utilities for find_code.

This module handles the construction of FindCodeResponseSummary objects
from search results, including summary generation and metadata calculation.
"""

from __future__ import annotations

import contextlib

from typing import Literal

from codeweaver.agent_api.find_code.intent import IntentType
from codeweaver.agent_api.find_code.types import CodeMatch, FindCodeResponseSummary, SearchStrategy
from codeweaver.core.language import ConfigLanguage, SemanticSearchLanguage
from codeweaver.core.types import LanguageName


def get_indexer_state_info() -> tuple[
    Literal["complete", "in_progress", "not_started", "unknown"], float | None
]:
    """Get indexing state and coverage from global application state.

    Returns:
        Tuple of (indexing_state, index_coverage):
        - indexing_state: "complete", "in_progress", "not_started", or "unknown"
        - index_coverage: Percentage of files indexed (0-100), or None if unavailable
    """
    try:
        from codeweaver.server.server import get_state

        state = get_state()

        if state.indexer is None:
            return ("not_started", None)

        stats = state.indexer.stats
        files_discovered = stats.files_discovered
        files_processed = stats.files_processed

        # Calculate coverage
        coverage = files_processed / files_discovered * 100 if files_discovered > 0 else None

        # Determine state
        if files_discovered == 0:
            indexing_state = "not_started"
        elif files_processed >= files_discovered:
            indexing_state = "complete"
        else:
            indexing_state = "in_progress"

    except Exception:
        # If state is not initialized or any error occurs, return unknown
        return ("unknown", None)
    else:
        return (indexing_state, coverage)


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
            f"for {intent_type.variable} query. "
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
    elif (
        SearchStrategy.SPARSE_ONLY in strategies_used
        or SearchStrategy.KEYWORD_FALLBACK in strategies_used
    ):
        search_mode = "sparse_only"

    # Get indexing state from global application state
    indexing_state, index_coverage = get_indexer_state_info()

    warnings = []
    status = "success"

    # Add warnings for degraded search modes
    if search_mode == "sparse_only":
        warnings.append("Dense embeddings unavailable - using sparse search only (degraded mode)")
        status = "partial"
    elif search_mode == "dense_only":
        warnings.append("Sparse embeddings unavailable - using dense search only")

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
    # Get indexing state from global application state
    indexing_state, index_coverage = get_indexer_state_info()
    from codeweaver.common.registry.provider import get_provider_registry
    from codeweaver.providers.vector_stores.base import VectorStoreProvider

    mode = "unknown"
    with contextlib.suppress(Exception):
        registry = get_provider_registry()
        provider = registry.get_provider_enum_for("vector_store")
        vector_store: VectorStoreProvider = registry.get_provider_instance(
            provider, "vector_store", singleton=True
        )  # ty: ignore[no-matching-overload]
        capabilities = vector_store.embedding_capabilities
        mode = (
            "hybrid"
            if ((dense := capabilities.get("dense")) and (sparse := capabilities.get("sparse")))
            else ("dense_only" if dense else "sparse_only" if sparse else "unknown")
        )
    error_message = f"Critical error: {type(error).__name__}: {str(error)!s}"
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
        warnings=[(error_message if len(error_message) <= 200 else f"{error_message[:200]}...")],
        indexing_state=indexing_state,
        index_coverage=index_coverage,
        search_mode=mode,
        metadata={},
    )


__all__ = (
    "build_error_response",
    "build_success_response",
    "calculate_token_count",
    "extract_languages",
    "generate_summary",
    "get_indexer_state_info",
)

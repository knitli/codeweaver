# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""# Implementation of the find_code tool.

CodeWeaver differentiates between *internal* and *external* tools. External tools -- and there is only one, this one, the **`find_code`** tool -- are exposed to the user and user's AI agents. `find_code` is intentionally very simple. This module contains the back-end, execution-side, of the `find_code` tool. The entry-point exposed to users and agents is in `codeweaver.server.app_bindings`.

## How it Works

You, or your AI agents, simply ask a question, explain what you are trying to do or what you need information for, and CodeWeaver will answer it.

For example, your agent might say:
    > Note: The main parameters for `find_code` that are exposed to users and agents are `query`, `intent`, and `focus_languages`. There are also `token_limit` and `include_tests`, but those are fairly self-explanatory.
    ```
    ```

`find_code` is different from other MCP tools in that it:
    1) Is intentionally designed to reduce "*cognitive load*"[^1] on *agents*. Put simply, AI agents have "great minds and terrible hands." `find_code` aims to bridge that gap between intellect and action. The explosion of MCP tools has also increased the cognitive load on agents -- when there are 100 tools, which one do you use? It's a hard task for a human, and harder for an AI. `find_code` aims to be a simple, universal tool that can be used in many situations.
    2) `find_code`, and all of CodeWeaver, is entirely designed to *narrow context*. AI agents are very prone to "*context poisoning*" and "*context overload*". In even small codebases, this can happen very quickly -- often before the agent even gets to the point of using a tool. `find_code` intentionally filters and shields the user's agent from unnecessary context, and only provides the context that is relevant to the query. This is a key part of CodeWeaver's design philosophy.
    3) It's context-aware. `find_code` understands the context of your project, the files, the languages, and the structure. It uses this context to provide relevant results.

    [^1]: AI agents don't experience 'cognitive load' in the human sense, but we use the term here metaphorically. Practically speaking, two things actually happen: 1) Context 'poisoning' -- the agent's context gets filled with irrelevant information that steers it away from the results you want, 2) The agent, which really doesn't 'think' in the human sense, can't tell what tool to use, so it often picks the wrong one -- tool use is more of a side effect of their training to generate language.
"""

from __future__ import annotations

import logging
import time

from pathlib import Path
from typing import NamedTuple

from pydantic import NonNegativeInt, PositiveInt

from codeweaver.agent_api.intent import INTENT_TO_AGENT_TASK, IntentType, detect_intent
from codeweaver.agent_api.models import (
    CodeMatch,
    CodeMatchType,
    FindCodeResponseSummary,
    SearchStrategy,
)
from codeweaver.common.registry import get_provider_registry
from codeweaver.common.utils import uuid7
from codeweaver.core.chunks import CodeChunk, SearchResult
from codeweaver.core.discovery import DiscoveredFile
from codeweaver.core.spans import Span
from codeweaver.semantic.classifications import AgentTask


logger = logging.getLogger(__name__)


class MatchedSection(NamedTuple):
    """Represents a matched section within a file."""

    content: str
    span: Span
    score: NonNegativeInt
    filename: str | None = None
    file_path: Path | None = None
    chunk_number: PositiveInt | None = None


def _convert_search_result_to_code_match(result: SearchResult) -> CodeMatch:
    """Convert SearchResult from vector store to CodeMatch for response.

    Args:
        result: SearchResult from vector store search

    Returns:
        CodeMatch with all required fields populated
    """
    # Extract CodeChunk (SearchResult.content can be str or CodeChunk)
    if isinstance(result.content, str):
        # Create minimal CodeChunk from string
        chunk = CodeChunk(
            content=result.content,
            line_range=(1, result.content.count("\n") + 1),
            file_path=result.file_path,
            language=None,
            source="TEXT_BLOCK",
            chunk_id=uuid7(),
        )
    else:
        chunk = result.content

    # Get file info (prefer from chunk, fallback to result.file_path)
    if hasattr(chunk, "file_path") and chunk.file_path:
        file = DiscoveredFile.from_path(chunk.file_path)
    elif result.file_path:
        file = DiscoveredFile.from_path(result.file_path)
    else:
        # Create minimal DiscoveredFile
        file = DiscoveredFile.from_path(Path("unknown"))

    # Extract span (line range)
    if hasattr(chunk, "line_range"):
        span = chunk.line_range
    else:
        span = (1, chunk.content.count("\n") + 1 if hasattr(chunk, "content") else 1)

    # Use relevance_score if set, otherwise use base score
    relevance = getattr(result, "relevance_score", result.score)

    # Extract related symbols from chunk metadata if available
    related_symbols = ()
    if hasattr(chunk, "metadata") and chunk.metadata:
        meta = chunk.metadata
        if hasattr(meta, "related_symbols"):
            related_symbols = tuple(meta.related_symbols)

    return CodeMatch(
        file=file,
        content=chunk,
        span=span,
        relevance_score=relevance,
        match_type=CodeMatchType.SEMANTIC,  # Vector search is always semantic
        related_symbols=related_symbols,
    )


async def find_code(
    query: str,
    *,
    intent: IntentType | None = None,
    token_limit: int = 10000,
    include_tests: bool = False,
    focus_languages: tuple[str, ...] | None = None,
    max_results: int = 50,
) -> FindCodeResponseSummary:
    """Find relevant code based on semantic search with intent-driven ranking.

    This is the main entry point for the CodeWeaver search pipeline:
    1. Intent detection (keyword-based for v0.1)
    2. Query embedding (dense + sparse)
    3. Hybrid vector search
    4. Apply static dense/sparse weights
    5. Rerank (if provider available)
    6. Rescore with semantic importance weights
    7. Sort, limit, and build response

    Args:
        query: Natural language search query
        intent: Optional explicit intent (if None, will be detected)
        token_limit: Maximum tokens to return (default: 10000)
        include_tests: Whether to include test files in results
        focus_languages: Optional language filter
        max_results: Maximum number of results to return (default: 50)

    Returns:
        FindCodeResponseSummary with ranked matches and metadata

    Examples:
        >>> response = await find_code("how does authentication work")
        >>> response.query_intent
        IntentType.UNDERSTAND

        >>> response = await find_code("fix login bug", intent=IntentType.DEBUG)
        >>> response.search_strategy
        (SearchStrategy.HYBRID_SEARCH, SearchStrategy.SEMANTIC_RERANK)
    """
    start_time = time.time()
    strategies_used: list[SearchStrategy] = []

    try:
        # Step 1: Intent detection
        if intent is not None:
            query_intent_obj = None
            intent_type = intent
            confidence = 1.0
        else:
            query_intent_obj = detect_intent(query)
            intent_type = query_intent_obj.intent_type
            confidence = query_intent_obj.confidence

        agent_task_str = INTENT_TO_AGENT_TASK.get(intent_type, "DEFAULT")
        agent_task = AgentTask[agent_task_str]

        logger.info("Query intent detected: %s (confidence: %.2f)", intent_type, confidence)

        # Get provider registry
        registry = get_provider_registry()

        # Step 2: Embed query (dense + sparse)
        dense_provider_enum = registry.get_embedding_provider(sparse=False)
        sparse_provider_enum = registry.get_embedding_provider(sparse=True)

        # Get provider instances (both optional individually for graceful degradation,
        # but at least one must be available - validated below)
        dense_provider = (
            registry.get_embedding_provider_instance(dense_provider_enum, singleton=True)
            if dense_provider_enum
            else None
        )
        sparse_provider = (
            registry.get_embedding_provider_instance(sparse_provider_enum, singleton=True)
            if sparse_provider_enum
            else None
        )

        if not dense_provider and not sparse_provider:
            raise ValueError("No embedding providers configured (neither dense nor sparse)")

        # Embed query (with fallback to sparse-only if dense fails)
        dense_query_embedding = None
        if dense_provider:
            try:
                dense_query_embedding = await dense_provider.embed_query(query)
            except Exception as e:
                logger.warning("Dense embedding failed: %s", e)
                if not sparse_provider:
                    # No fallback available - must fail
                    raise ValueError("Dense embedding failed and no sparse provider available") from e

        sparse_query_embedding = None
        if sparse_provider:
            try:
                sparse_query_embedding = await sparse_provider.embed_query(query)
            except Exception as e:
                logger.warning("Sparse embedding failed, continuing with dense only: %s", e)

        # Step 3: Hybrid search
        vector_store_enum = registry.get_vector_store_provider()
        if not vector_store_enum:
            raise ValueError("No vector store provider configured")

        vector_store = registry.get_vector_store_provider_instance(
            vector_store_enum, singleton=True
        )

        # Build query vector (unified search API) with graceful degradation
        if dense_query_embedding and sparse_query_embedding:
            strategies_used.append(SearchStrategy.HYBRID_SEARCH)
            query_vector = {"dense": dense_query_embedding, "sparse": sparse_query_embedding}
        elif dense_query_embedding and not sparse_query_embedding:
            strategies_used.append(SearchStrategy.DENSE_ONLY)
            logger.warning("Using dense-only search (sparse embeddings unavailable)")
            query_vector = dense_query_embedding
        elif not dense_query_embedding and sparse_query_embedding:
            strategies_used.append(SearchStrategy.SPARSE_ONLY)
            logger.warning("Using sparse-only search (dense embeddings unavailable - degraded mode)")
            query_vector = {"sparse": sparse_query_embedding}
        else:
            # Both failed - should not reach here due to earlier validation
            raise ValueError("No embeddings available (both dense and sparse failed)")

        # Execute search (returns max 100 results)
        # Note: Filter support deferred to v0.2 - we over-fetch and filter post-search
        candidates = await vector_store.search(vector=query_vector, query_filter=None)

        # Post-search filtering (v0.1 simple approach)
        if not include_tests:
            candidates = [c for c in candidates if not getattr(c.chunk.file, "is_test", False)]
        if focus_languages:
            lang_set = set(focus_languages)
            candidates = [
                c for c in candidates if getattr(c.chunk.file, "language", None) in lang_set
            ]

        logger.info("Vector search returned %d candidates", len(candidates))

        # Step 4: Apply static dense/sparse weights (v0.1)
        if SearchStrategy.HYBRID_SEARCH in strategies_used:
            for candidate in candidates:
                # Static weights for v0.1: dense=0.65, sparse=0.35
                candidate.score = (
                    getattr(candidate, "dense_score", candidate.score) * 0.65
                    + getattr(candidate, "sparse_score", 0.0) * 0.35
                )
        # For sparse-only, scores are already set by vector store

        # Step 5: Rerank (optional, if provider configured)
        reranking_enum = registry.get_reranking_provider()
        if reranking_enum and len(candidates) > 0:
            try:
                reranking = registry.get_reranking_provider_instance(reranking_enum, singleton=True)
                candidates = await reranking.rerank(query, candidates, top_k=max_results * 2)
                strategies_used.append(SearchStrategy.SEMANTIC_RERANK)
                logger.info("Reranked to %d candidates", len(candidates))
            except Exception as e:
                logger.warning("Reranking failed, continuing without: %s", e)

        # Step 6: Rescore with semantic weights
        for candidate in candidates:
            base_score = getattr(candidate, "rerank_score", candidate.score)

            # Apply semantic weighting if semantic class available
            semantic_class = getattr(candidate.chunk, "semantic_class", None)
            if semantic_class and hasattr(semantic_class, "importance_scores"):
                importance = semantic_class.importance_scores.for_task(agent_task)

                # Use appropriate importance dimension based on intent
                if intent_type == IntentType.DEBUG:
                    semantic_boost = importance.debugging
                elif intent_type == IntentType.IMPLEMENT:
                    semantic_boost = (importance.discovery + importance.modification) / 2
                elif intent_type == IntentType.UNDERSTAND:
                    semantic_boost = importance.comprehension
                else:
                    semantic_boost = importance.discovery

                # Apply semantic boost (20% adjustment)
                candidate.relevance_score = base_score * (1 + semantic_boost * 0.2)
            else:
                candidate.relevance_score = base_score

        # Step 7: Sort and limit
        candidates.sort(key=lambda x: x.relevance_score if hasattr(x, 'relevance_score') and x.relevance_score is not None else x.score, reverse=True)
        search_results = candidates[:max_results]

        # Convert SearchResult objects to CodeMatch objects for response
        code_matches = []
        for result in search_results:
            try:
                match = _convert_search_result_to_code_match(result)
                code_matches.append(match)
            except Exception as e:
                logger.warning("Failed to convert search result to code match: %s", e)
                continue

        # Build response
        execution_time_ms = (time.time() - start_time) * 1000

        # Calculate token count from code matches
        total_tokens = sum(
            len(match.content.content.split()) * 1.3  # Rough token estimate
            for match in code_matches
            if match.content and hasattr(match.content, 'content')
        )
        total_tokens = min(int(total_tokens), token_limit)

        # Generate summary
        if code_matches:
            top_files = list({m.file.path.name for m in code_matches[:3] if m.file and m.file.path})
            summary = (
                f"Found {len(code_matches)} relevant matches "
                f"for {intent_type.value} query. "
                f"Top results in: {', '.join(top_files[:3])}"
            )
        else:
            summary = f"No matches found for query: '{query}'"

        # Extract languages from code matches
        languages_found = tuple({
            m.file.ext_kind.language
            for m in code_matches
            if m.file and hasattr(m.file, 'ext_kind') and m.file.ext_kind
        })

        return FindCodeResponseSummary(
            matches=code_matches,
            summary=summary[:1000],  # Enforce max_length
            query_intent=intent_type,
            total_matches=len(candidates),
            total_results=len(code_matches),
            token_count=total_tokens,
            execution_time_ms=execution_time_ms,
            search_strategy=tuple(strategies_used),
            languages_found=languages_found,
        )

    except Exception as e:
        logger.exception("find_code failed")
        # Return empty response on failure (graceful degradation)
        execution_time_ms = (time.time() - start_time) * 1000
        return FindCodeResponseSummary(
            matches=[],
            summary=f"Search failed: {str(e)[:500]}",
            query_intent=intent,
            total_matches=0,
            total_results=0,
            token_count=0,
            execution_time_ms=execution_time_ms,
            search_strategy=(SearchStrategy.KEYWORD_FALLBACK,),
            languages_found=(),
        )


__all__ = ("MatchedSection", "find_code")

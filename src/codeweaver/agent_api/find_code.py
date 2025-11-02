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
from typing import TYPE_CHECKING, Any, NamedTuple

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
from codeweaver.core.chunks import ChunkSource, CodeChunk, SearchResult
from codeweaver.core.discovery import DiscoveredFile
from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.core.spans import Span
from codeweaver.core.types import LanguageName
from codeweaver.semantic.classifications import AgentTask


if TYPE_CHECKING:
    from codeweaver.providers.vector_stores.base import VectorStoreProvider


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
        chunk = _create_code_chunk_from_result(result)
    else:
        chunk = result.content

    # Get file info (prefer from chunk, fallback to result.file_path, then create fallback)
    file: DiscoveredFile | None = None
    if hasattr(chunk, "file_path") and chunk.file_path:
        file = DiscoveredFile.from_path(chunk.file_path)
    elif result.file_path:
        file = DiscoveredFile.from_path(result.file_path)

    # Ensure we always have a DiscoveredFile (CodeMatch requires non-None)
    if file is None:
        # Create fallback DiscoveredFile with unknown path
        from codeweaver.core.metadata import ExtKind

        unknown_path = Path("unknown")
        ext_kind = ExtKind.from_language("text", "other")
        # DiscoveredFile constructor accepts path and ext_kind directly
        file = DiscoveredFile(path=unknown_path, ext_kind=ext_kind)

    # Extract span (line range) - ensure it's a Span object
    if hasattr(chunk, "line_range"):
        span = chunk.line_range
    else:
        # Fallback span - positional args: start, end, source_id
        span = Span(
            1, chunk.content.count("\n") + 1 if hasattr(chunk, "content") else 1, file.source_id
        )

    # Use relevance_score if set, otherwise use base score
    relevance = getattr(result, "relevance_score", result.score)

    # Extract related symbols from chunk metadata if available
    # Metadata is a TypedDict, check for semantic_meta which may contain symbols
    related_symbols = ()
    if hasattr(chunk, "metadata") and chunk.metadata:
        meta = chunk.metadata
        # Check if semantic_meta exists and has symbol information
        semantic_meta = meta.get("semantic_meta")
        if (
            semantic_meta is not None
            and hasattr(semantic_meta, "symbol")
            and (symbol := getattr(semantic_meta, "symbol", None))
        ):
            related_symbols = (symbol,)

    return CodeMatch(
        file=file,
        content=chunk,
        span=span,
        relevance_score=relevance,
        match_type=CodeMatchType.SEMANTIC,  # Vector search is always semantic
        related_symbols=related_symbols,
    )


def _create_code_chunk_from_result(result: SearchResult) -> CodeChunk:
    # Create minimal CodeChunk from string
    from codeweaver.core.metadata import ExtKind

    if isinstance(result.content, CodeChunk):
        return result.content

    # Determine ext_kind from file_path or use default
    ext_kind = (
        ExtKind.from_file(result.file_path)
        if result.file_path
        else ExtKind.from_language("text", "other")
    )

    # Create Span for line_range with proper UUID7 source_id
    source_id = uuid7()
    line_count = (result.content.count("\n") + 1) if result.content else 1
    line_span = Span(1, line_count, source_id)  # Positional args: start, end, source_id

    return CodeChunk(
        content=result.content,
        line_range=line_span,
        file_path=result.file_path,
        language=None,
        ext_kind=ext_kind,
        source=ChunkSource.TEXT_BLOCK,
        chunk_id=uuid7(),
    )


def raise_value_error(message: str) -> None:
    """Helper function to raise ValueError with a message."""
    raise ValueError(message)


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

        raw_agent_task = INTENT_TO_AGENT_TASK.get(intent_type, "DEFAULT")
        agent_task = AgentTask[raw_agent_task]

        logger.info("Query intent detected: %s (confidence: %.2f)", intent_type, confidence)

        # Get provider registry
        registry = get_provider_registry()

        # Step 2: Embed query (dense + sparse)
        dense_provider_enum = registry.get_provider_enum_for("embedding")
        sparse_provider_enum = registry.get_provider_enum_for("sparse_embedding")

        if not dense_provider_enum and not sparse_provider_enum:
            raise_value_error("No embedding providers configured (neither dense nor sparse)")

        # Embed query (with fallback to sparse-only if dense fails)

        dense_query_embedding = None
        if dense_provider_enum:
            try:
                dense_provider = registry.get_provider_instance(
                    dense_provider_enum, "embedding", singleton=True
                )
                result = await dense_provider.embed_query(query)
                # Check for embedding error
                if isinstance(result, dict) and "error" in result:
                    logger.warning("Dense embedding returned error: %s", result.get("error"))
                    if not sparse_provider_enum:
                        raise_value_error(
                            f"Dense embedding failed: {result.get('error')} (no sparse fallback)"
                        )
                else:
                    dense_query_embedding = result
            except Exception as e:
                logger.warning("Dense embedding failed: %s", e)
                if not sparse_provider_enum:
                    # No fallback available - must fail
                    raise ValueError(
                        "Dense embedding failed and no sparse provider available"
                    ) from e

        sparse_query_embedding = None
        if sparse_provider_enum:
            try:
                sparse_provider = registry.get_provider_instance(
                    sparse_provider_enum, "sparse_embedding", singleton=True
                )
                result = await sparse_provider.embed_query(query)
                # Check for embedding error
                if isinstance(result, dict) and "error" in result:
                    logger.warning("Sparse embedding returned error: %s", result.get("error"))
                else:
                    sparse_query_embedding = result
            except Exception as e:
                logger.warning("Sparse embedding failed, continuing with dense only: %s", e)

        # Step 3: Hybrid search
        vector_store_enum = registry.get_provider_enum_for("vector_store")
        if not vector_store_enum:
            raise_value_error("No vector store provider configured")
        assert isinstance(vector_store_enum, type)  # noqa: S101
        vector_store: VectorStoreProvider[Any] = registry.get_provider_instance(
            vector_store_enum, "vector_store", singleton=True
        )  # type: ignore

        # Build query vector (unified search API) with graceful degradation
        # Note: embed_query returns list[list[float|int]] (batch results), unwrap to list[float]
        query_vector: list[float] | dict[str, list[float] | Any]
        if dense_query_embedding and sparse_query_embedding:
            strategies_used.append(SearchStrategy.HYBRID_SEARCH)
            # Unwrap batch results (take first element) and ensure float type
            dense_vec: list[float] = [float(x) for x in dense_query_embedding[0]]
            sparse_vec: list[float] = [float(x) for x in sparse_query_embedding[0]]
            query_vector = {"dense": dense_vec, "sparse": sparse_vec}
        elif dense_query_embedding:
            strategies_used.append(SearchStrategy.DENSE_ONLY)
            logger.warning("Using dense-only search (sparse embeddings unavailable)")
            # Unwrap batch results (take first element) and ensure float type
            query_vector = [float(x) for x in dense_query_embedding[0]]
        elif sparse_query_embedding:
            strategies_used.append(SearchStrategy.SPARSE_ONLY)
            logger.warning(
                "Using sparse-only search (dense embeddings unavailable - degraded mode)"
            )
            # Unwrap batch results (take first element) and ensure float type
            sparse_vec_unwrapped: list[float] = [float(x) for x in sparse_query_embedding[0]]
            query_vector = {"sparse": sparse_vec_unwrapped}
        else:
            # Both failed - should not reach here due to earlier validation
            query_vector = {"dense": [], "sparse": []}
            raise_value_error("Both dense and sparse embeddings failed")

        # Execute search (returns max 100 results)
        # Note: Filter support deferred to v0.2 - we over-fetch and filter post-search
        candidates: list[SearchResult] = await vector_store.search(
            vector=query_vector, query_filter=None
        )

        # Post-search filtering (v0.1 simple approach)
        # Access file info from SearchResult.file_path, not chunk.file (which doesn't exist)
        # TODO: This is a basic implementation of test filtering.
        # Going forward, we'll use our repo metadata collection to tag files as test or non-test among other attributes.
        if not include_tests:
            candidates = [
                c for c in candidates if not (c.file_path and "test" in str(c.file_path).lower())
            ]
        if focus_languages:
            langs = set(focus_languages)
            candidates = [
                c
                for c in candidates
                if (
                    isinstance(c.content, CodeChunk)
                    and c.content.language
                    and str(c.content.language) in langs
                )
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
        reranking_enum = registry.get_provider_enum_for("reranking")
        reranked_results = None
        if reranking_enum and candidates:
            try:
                reranking = registry.get_provider_instance(
                    reranking_enum, "reranking", singleton=True
                )
                if chunks_for_reranking := [
                    c.content for c in candidates if isinstance(c.content, CodeChunk)
                ]:
                    reranked_results = await reranking.rerank(query, chunks_for_reranking)
                    strategies_used.append(SearchStrategy.SEMANTIC_RERANK)
                    logger.info("Reranked to %d candidates", len(reranked_results))
                else:
                    logger.warning("No CodeChunk objects available for reranking, skipping")
            except Exception as e:
                logger.warning("Reranking failed, continuing without: %s", e)

        # Step 6: Rescore with semantic weights
        # Build final candidate list with relevance scores
        scored_candidates: list[SearchResult] = []

        if reranked_results:
            # Map reranked results back to SearchResult objects with rerank_score
            for rerank_result in reranked_results:
                # Find original candidate by matching chunk
                original_candidate = candidates[rerank_result.original_index]
                base_score = rerank_result.score

                # Apply semantic weighting if semantic class available
                semantic_class = getattr(rerank_result.chunk, "semantic_class", None)
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
                    final_score = base_score * (1 + semantic_boost * 0.2)
                else:
                    final_score = base_score

                # Create updated SearchResult with new scores
                scored_candidate = original_candidate.model_copy(
                    update={"rerank_score": base_score, "relevance_score": final_score}
                )
                scored_candidates.append(scored_candidate)
        else:
            # No reranking - use original scores with semantic weighting
            for candidate in candidates:
                base_score = candidate.score

                # Apply semantic weighting if semantic class available
                chunk_obj = candidate.content if isinstance(candidate.content, CodeChunk) else None
                semantic_class = getattr(chunk_obj, "semantic_class", None) if chunk_obj else None

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
                    final_score = base_score * (1 + semantic_boost * 0.2)
                else:
                    final_score = base_score

                # Create updated SearchResult with relevance score
                scored_candidate = candidate.model_copy(update={"relevance_score": final_score})
                scored_candidates.append(scored_candidate)

        # Step 7: Sort and limit
        scored_candidates.sort(
            key=lambda x: (x.relevance_score if x.relevance_score is not None else x.score),
            reverse=True,
        )
        search_results = scored_candidates[:max_results]

        # Convert SearchResult objects to CodeMatch objects for response
        code_matches: list[CodeMatch] = []
        for result in search_results:
            try:
                match: CodeMatch = _convert_search_result_to_code_match(result)
                code_matches.append(match)
            except Exception as e:
                logger.warning("Failed to convert search result to code match: %s", e)
                continue

        # Build response
        execution_time_ms = (time.time() - start_time) * 1000

        # Calculate token count from code matches
        # Extract content string and calculate tokens
        total_tokens_raw = sum(
            len(m.content.content.split()) * 1.3  # Rough token estimate
            for m in code_matches
            if hasattr(m.content, "content") and m.content.content
        )
        total_tokens: int = min(int(total_tokens_raw), token_limit)

        # Generate summary
        if code_matches:
            # Extract top file names (file and file.path are non-nullable in CodeMatch)
            # Build set of filenames, convert to list for slicing
            top_unique_files: set[str] = {m.file.path.name for m in code_matches[:3]}
            top_files: list[str] = list(top_unique_files)
            summary: str = (
                f"Found {len(code_matches)} relevant matches "
                f"for {intent_type.value} query. "
                f"Top results in: {', '.join(top_files[:3])}"
            )
        else:
            summary: str = f"No matches found for query: '{query}'"

        # Extract languages from code matches
        # Build set of languages (including ConfigLanguage), then convert to tuple
        from codeweaver.core.language import ConfigLanguage

        languages: set[SemanticSearchLanguage | LanguageName | ConfigLanguage] = {
            m.file.ext_kind.language for m in code_matches if m.file.ext_kind is not None
        }
        languages_found: tuple[SemanticSearchLanguage | LanguageName, ...] = tuple(
            lang for lang in languages if not isinstance(lang, ConfigLanguage)
        )

        return FindCodeResponseSummary(
            matches=code_matches,
            summary=summary[:1000],  # Enforce max_length
            query_intent=intent_type,
            total_matches=len(scored_candidates),
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

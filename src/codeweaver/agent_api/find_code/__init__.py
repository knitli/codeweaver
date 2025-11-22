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

## Architecture

The find_code package is organized into focused modules:

- **conversion.py**: Converts SearchResult objects to CodeMatch responses
- **filters.py**: Post-search filtering (test files, language focus)
- **pipeline.py**: Query embedding and vector search orchestration
- **scoring.py**: Score calculation, reranking, and semantic weighting

This modular structure makes it easy to:
- Add new filtering strategies
- Extend scoring mechanisms
- Integrate new search providers
- Test individual components in isolation

## Philosophy: Agent UX

The design of `find_code` is heavily influenced by the concept of *Agent User Experience (Agent UX)*. Just as traditional UX focuses on making software intuitive and efficient for human users, Agent UX aims to optimize how AI agents interact with tools and systems. When we ask agents to use a tool with a human API, we need to consider how the agent will perceive and utilize that tool. `find_code` is designed to be as straightforward and effective as possible for AI agents, minimizing the complexity they have to deal with.
"""

from __future__ import annotations

import logging
import time

from pathlib import Path
from typing import Any, NamedTuple

from pydantic import NonNegativeInt, PositiveInt

from codeweaver.agent_api.find_code.conversion import convert_search_result_to_code_match
from codeweaver.agent_api.find_code.filters import apply_filters
from codeweaver.agent_api.find_code.intent import INTENT_TO_AGENT_TASK, IntentType, detect_intent
from codeweaver.agent_api.find_code.pipeline import (
    build_query_vector,
    embed_query,
    execute_vector_search,
    rerank_results,
)
from codeweaver.agent_api.find_code.response import build_error_response, build_success_response
from codeweaver.agent_api.find_code.scoring import (
    apply_hybrid_weights,
    process_reranked_results,
    process_unranked_results,
)
from codeweaver.agent_api.find_code.types import CodeMatch, FindCodeResponseSummary, SearchStrategy
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


def _get_settings(context: Any | None) -> Any:
    """Get settings from MCP context or load fresh.

    Args:
        context: Optional MCP context containing settings

    Returns:
        CodeWeaverSettings instance
    """
    if context and hasattr(context, "settings"):
        return context.settings

    # Load fresh (CLI usage)
    from codeweaver.config.settings import get_settings

    return get_settings()


async def _check_index_status(context: Any | None) -> tuple[bool, int]:
    """Check if index exists and get chunk count.

    Args:
        context: Optional MCP context

    Returns:
        Tuple of (index_exists, chunk_count) where:
        - index_exists: True if collection exists in vector store
        - chunk_count: Number of chunks in collection (0 if doesn't exist)
    """
    from codeweaver.common.registry import get_provider_registry

    try:
        _ = _get_settings(context)  # Ensure settings loaded
        registry = get_provider_registry()

        # Get vector store provider
        provider_enum = registry.get_provider_enum_for("vector_store")
        if not provider_enum:
            logger.warning("No vector store provider configured")
            return False, 0

        vector_store = registry.get_provider_instance(provider_enum, "vector_store", singleton=True)
        if not vector_store:
            logger.warning("Could not get vector store instance")
            return False, 0

        # Initialize vector store if needed
        await vector_store._initialize()

        # Check if collection exists
        collection_name = vector_store.collection
        if not collection_name:
            logger.warning("No collection name configured")
            return False, 0

        # Use qdrant client directly to check existence and count
        client = vector_store.client
        collection_exists = await client.collection_exists(collection_name)

        if not collection_exists:
            logger.info("Collection %s does not exist", collection_name)
            return False, 0

        # Get count
        count_result = await client.count(collection_name)
        chunk_count = count_result.count if hasattr(count_result, "count") else 0

        logger.info("Collection %s exists with %d chunks", collection_name, chunk_count)
    except Exception as e:
        logger.warning("Failed to check index status: %s", e)
        return False, 0
    else:
        return True, chunk_count


async def _ensure_index_ready(context: Any | None) -> None:
    """Ensure index is ready by running indexer if needed.

    This function blocks until initial indexing is complete. It uses the
    direct Indexer pattern from cli.commands.index (no server needed).

    Args:
        context: Optional MCP context

    Raises:
        Does not raise - logs warnings and continues on failure
    """
    from codeweaver.core.types.dictview import DictView
    from codeweaver.engine.indexer import Indexer

    try:
        logger.info("Auto-indexing: Starting initial indexing...")

        # Get settings (from context or load)
        settings = _get_settings(context)

        # Create indexer (pattern from cli.commands.index)
        settings_dict = settings.model_dump() if hasattr(settings, "model_dump") else settings
        indexer = await Indexer.from_settings_async(DictView(settings_dict))

        # Run initial indexing (blocks until complete)
        await indexer.prime_index()

        # Log success
        stats = indexer.stats
        logger.info(
            "Auto-indexing complete: %d files, %d chunks in %.2fs",
            stats.files_processed,
            stats.chunks_indexed,
            stats.elapsed_time(),
        )

    except Exception as e:
        logger.warning("Auto-indexing failed: %s", e)
        # Don't fail find_code - let it try to search anyway


async def find_code(
    query: str,
    *,
    intent: IntentType | None = None,
    token_limit: int = 10000,
    include_tests: bool = False,
    focus_languages: tuple[str, ...] | None = None,
    max_results: int = 50,
    context: Any | None = None,  # ADD THIS for MCP communication
) -> FindCodeResponseSummary:
    """Find relevant code based on semantic search with intent-driven ranking.

    This is the main entry point for the CodeWeaver search pipeline:
    0. Auto-index if needed (blocks if empty, background if incremental)
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
        context: Optional FastMCP Context for client communication

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
        # Step 0: Auto-index if needed
        index_exists, chunk_count = await _check_index_status(context)

        if not index_exists or chunk_count == 0:
            # Full indexing needed - BLOCK and wait
            logger.info("Index not ready, triggering auto-indexing...")
            await _ensure_index_ready(context)
        # If index exists with chunks, proceed to search
        # (incremental updates handled by background watcher if server running)

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

        # Step 2: Embed query (dense + sparse)
        embeddings = await embed_query(query, context=context)  # THREAD CONTEXT

        # Step 3: Build query vector and determine strategy
        query_vector = build_query_vector(embeddings, query)
        strategies_used.append(query_vector.strategy)

        # Step 4: Execute vector search
        candidates = await execute_vector_search(query_vector, context=context)  # THREAD CONTEXT

        # Step 5: Post-search filtering (v0.1 simple approach)
        candidates = apply_filters(
            candidates, include_tests=include_tests, focus_languages=focus_languages
        )

        logger.info("Vector search returned %d candidates after filtering", len(candidates))

        # Step 6: Apply static dense/sparse weights (v0.1)
        if SearchStrategy.HYBRID_SEARCH in strategies_used:
            apply_hybrid_weights(candidates)

        # Step 7: Rerank (optional, if provider configured)
        reranked_results, rerank_strategy = await rerank_results(
            query, candidates, context=context
        )  # THREAD CONTEXT
        if rerank_strategy:
            strategies_used.append(rerank_strategy)

        # Step 8: Rescore with semantic weights
        if reranked_results:
            scored_candidates = process_reranked_results(
                reranked_results, candidates, intent_type, agent_task
            )
        else:
            scored_candidates = process_unranked_results(candidates, intent_type, agent_task)

        # Step 9: Sort and limit
        scored_candidates.sort(
            key=lambda x: (x.relevance_score if x.relevance_score is not None else x.score),
            reverse=True,
        )
        search_results = scored_candidates[:max_results]

        # Step 10: Convert to CodeMatch objects for response
        code_matches: list[CodeMatch] = []
        for result in search_results:
            try:
                match: CodeMatch = convert_search_result_to_code_match(result)
                code_matches.append(match)
            except Exception as e:
                logger.warning("Failed to convert search result to code match: %s", e)
                continue

        # Step 11: Build response
        execution_time_ms = (time.time() - start_time) * 1000

        return build_success_response(
            code_matches=code_matches,
            query=query,
            intent_type=intent_type,
            total_candidates=len(scored_candidates),
            token_limit=token_limit,
            execution_time_ms=execution_time_ms,
            strategies_used=strategies_used,
        )

    except Exception as e:
        logger.warning("find_code failed")
        # Return empty response on failure (graceful degradation)
        execution_time_ms = (time.time() - start_time) * 1000
        return build_error_response(e, intent, execution_time_ms)


__all__ = ("MatchedSection", "find_code")

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""# Implementation of the find_code tool.

CodeWeaver differentiates between *internal* and *external* tools. External tools -- and there is only one, this one, the **`find_code`** tool -- are exposed to the user and user's AI agents. `find_code` is intentionally very simple. This module contains the back-end, execution-side, of the `find_code` tool. The entry-point exposed to users and agents is in `codeweaver.mcp.user_agent`.

## How it Works

You, or your AI agents, simply ask a question, explain what you are trying to do or what you need information for, and CodeWeaver will answer it.

For example, your agent might say:
    > Note: The main parameters for `find_code` that are exposed to users and agents are `query`, `intent`, and `focus_languages`. There's also `token_limit`, but that's self-explanatory.
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
from typing import TYPE_CHECKING, NamedTuple

from fastmcp.server.context import Context
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
    process_reranked_results,
    process_unranked_results,
)
from codeweaver.common._logging import log_to_client_or_fallback
from codeweaver.common.telemetry.events import capture_search_event
from codeweaver.core.spans import Span
from codeweaver.core.types.search import SearchStrategy
from codeweaver.di import INJECTED
from codeweaver.di.providers import EmbeddingDep, RerankingDep, SparseEmbeddingDep, VectorStoreDep
from codeweaver.semantic.classifications import AgentTask


if TYPE_CHECKING:
    from codeweaver.agent_api.find_code.types import CodeMatch, FindCodeResponseSummary
    from codeweaver.config.types import CodeWeaverSettingsDict
    from codeweaver.core.types.dictview import DictView


logger = logging.getLogger(__name__)


class MatchedSection(NamedTuple):
    """Represents a matched section within a file."""

    content: str
    span: Span
    score: NonNegativeInt
    filename: str | None = None
    file_path: Path | None = None
    chunk_number: PositiveInt | None = None


def get_max_tokens() -> int:
    """Get maximum tokens allowed in find_code response."""
    settings = _get_settings()
    return settings["token_limit"]


def get_max_results() -> int:
    """Get maximum results allowed in find_code response."""
    settings = _get_settings()
    return settings["max_results"]


def _get_settings() -> DictView[CodeWeaverSettingsDict]:
    """Get settings view from codeweaver settings."""
    from codeweaver.config.settings import get_settings_map

    return get_settings_map()


async def _check_index_status(
    context: Context | None, vector_store: VectorStoreDep = INJECTED
) -> tuple[bool, int]:
    """Check if index exists and get chunk count.

    Args:
        context: Optional MCP context
        vector_store: Optional pre-initialized vector store instance

    Returns:
        Tuple of (index_exists, chunk_count) where:
        - index_exists: True if collection exists in vector store
        - chunk_count: Number of chunks in collection (0 if doesn't exist)
    """
    if vector_store is None:
        logger.warning("No vector store provider provided")
        return False, 0

    try:
        # Initialize if needed
        if hasattr(vector_store, "_initialize"):
            await vector_store._initialize()

        # Check collection
        collection_name = vector_store.collection
        if not collection_name:
            return False, 0

        exists = await vector_store.client.collection_exists(collection_name)
        if not exists:
            return False, 0

        info = await vector_store.client.get_collection(collection_name)
    except Exception as e:
        logger.warning("Failed to check index status: %s", e)
        return False, 0
    else:
        return True, info.points_count or 0


async def _ensure_index_ready(
    context: Context | None, vector_store: VectorStoreDep | None = None
) -> None:
    """Ensure index is ready by running indexer if needed.

    This function blocks until initial indexing is complete.

    Args:
        context: Optional MCP context
        vector_store: Optional pre-initialized vector store instance to use
    """
    from codeweaver.di import get_container
    from codeweaver.engine.indexer import Indexer

    try:
        logger.info("Auto-indexing: Starting initial indexing...")

        container = get_container()
        if vector_store:
            from codeweaver.providers.vector_stores.base import VectorStoreProvider
            container.override(VectorStoreProvider, vector_store)

        indexer = await container.resolve(Indexer)

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


_set_max = get_max_tokens()
_set_max_results = get_max_results()


async def find_code(  # noqa: C901
    query: str,
    *,
    intent: IntentType | None = None,
    token_limit: int = _set_max,
    focus_languages: tuple[str, ...] | None = None,
    max_results: int = _set_max_results,
    context: Context | None = None,
    vector_store: VectorStoreDep = INJECTED,
    embedding_provider: EmbeddingDep = INJECTED,
    sparse_provider: SparseEmbeddingDep = INJECTED,
    reranking_provider: RerankingDep = INJECTED,
) -> FindCodeResponseSummary:
    """Find relevant code based on semantic search with intent-driven ranking.

    This is the main entry point for the CodeWeaver search pipeline.

    Args:
        query: Natural language query
        intent: Optional IntentType to override detection
        token_limit: Maximum tokens to return (default: 30000)
        focus_languages: Optional language filter
        max_results: Maximum number of results to return (default: 30)
        context: Optional FastMCP Context for client communication
        vector_store: Injected vector store instance
        embedding_provider: Injected dense embedding provider
        sparse_provider: Injected sparse embedding provider
        reranking_provider: Injected reranking provider

    Returns:
        FindCodeResponseSummary with ranked matches and metadata
    """
    from codeweaver.di import DependsPlaceholder, get_container
    from codeweaver.providers.embedding.providers.base import EmbeddingProvider
    from codeweaver.providers.reranking.providers.base import RerankingProvider
    from codeweaver.providers.vector_stores.base import VectorStoreProvider

    container = get_container()

    if isinstance(vector_store, DependsPlaceholder):
        vector_store = await container.resolve(VectorStoreProvider)
    if isinstance(embedding_provider, DependsPlaceholder):
        embedding_provider = await container.resolve(EmbeddingProvider)
    if isinstance(sparse_provider, DependsPlaceholder):
        try:
            # Resolving sparse_embedding might return None if not configured
            sparse_provider = await container._call_with_injection(get_sparse_embedding_provider)
        except Exception:
            sparse_provider = None
    if isinstance(reranking_provider, DependsPlaceholder):
        try:
            reranking_provider = await container.resolve(RerankingProvider)
        except Exception:
            reranking_provider = None

    start_time = time.monotonic()
    strategies_used: list[SearchStrategy] = []

    try:
        # Step 0: Auto-index if needed
        index_exists, chunk_count = await _check_index_status(context, vector_store=vector_store)

        if not index_exists or chunk_count == 0:
            # Full indexing needed - BLOCK and wait
            log_to_client_or_fallback(
                context,
                "warning",
                {
                    "message": "The code index is not ready. Starting index. This could take awhile..."
                },
            )
            await _ensure_index_ready(context, vector_store=vector_store)

        # Step 1: Intent detection
        if intent is not None:
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
        embeddings = await embed_query(
            query,
            context=context,
            dense_provider=embedding_provider,
            sparse_provider=sparse_provider,
        )

        # Step 3: Build query vector and determine strategy
        query_vector = build_query_vector(embeddings, query)
        strategies_used.append(query_vector.strategy)

        # Step 4: Execute vector search
        candidates = await execute_vector_search(
            query_vector, context=context, vector_store=vector_store
        )

        # Step 5: Post-search filtering
        candidates = apply_filters(
            candidates,
            include_tests=intent_type in {IntentType.DEBUG, IntentType.TEST},
            focus_languages=focus_languages,
        )

        logger.info("Vector search returned %d candidates after filtering", len(candidates))

        # Step 7: Rerank (optional, if provider configured)
        reranked_results, rerank_strategy = await rerank_results(
            query, candidates, context=context, reranking=reranking_provider
        )
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
        execution_time_ms = (time.monotonic() - start_time) * 1000

        response = build_success_response(
            code_matches=code_matches,
            query=query,
            intent_type=intent_type,
            total_candidates=len(scored_candidates),
            token_limit=token_limit,
            execution_time_ms=execution_time_ms,
            strategies_used=strategies_used,
        )

        # Step 12: Capture search telemetry
        settings = _get_settings()
        tools_over_privacy = settings["telemetry"]["tools_over_privacy"]
        try:
            from codeweaver.common.telemetry import get_telemetry_client

            client = get_telemetry_client()
            feature_flags = {
                "search-ranking-v2": client.get_feature_flag("search-ranking-v2"),
                "rerank-strategy": client.get_feature_flag("rerank-strategy"),
            }

            capture_search_event(
                response=response,
                query=query,
                intent_type=intent_type,
                strategies=strategies_used,
                execution_time_ms=execution_time_ms,
                tools_over_privacy=tools_over_privacy,
                feature_flags=feature_flags,
            )
        except Exception:
            logger.debug("Failed to capture search telemetry")

    except Exception as e:
        logger.warning("find_code failed: %s", e, exc_info=True)
        execution_time_ms = (time.monotonic() - start_time) * 1000
        error_response = build_error_response(e, intent, execution_time_ms)

        try:
            capture_search_event(
                response=error_response,
                query=query,
                intent_type=intent or IntentType.UNDERSTAND,
                strategies=strategies_used,
                execution_time_ms=execution_time_ms,
                tools_over_privacy=tools_over_privacy,
                feature_flags=None,
            )
        except Exception:
            logger.debug("Failed to capture error search telemetry")

        return error_response
    else:
        return response


__all__ = ("MatchedSection", "find_code")

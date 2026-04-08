# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""# Implementation of the find_code tool.

CodeWeaver differentiates between *internal* and *external* tools. External tools -- and there is only one, this one, the **`find_code`** tool -- are exposed to the user and user's AI agents. `find_code` is intentionally very simple. This module contains the back-end, execution-side, of the `find_code` tool. The entry-point exposed to users and agents is in `codeweaver.server.mcp`.

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
from typing import NamedTuple

from fastmcp.server.context import Context
from pydantic import NonNegativeInt, PositiveInt

from codeweaver.core import (
    INJECTED,
    SearchStrategy,
    SettingsDep,
    Span,
    TelemetryServiceDep,
    TelemetrySettingsDep,
    capture_search_event,
    log_to_client_or_fallback,
)
from codeweaver.core.config.settings_type import CodeWeaverSettingsType
from codeweaver.core.constants import DEFAULT_MAX_RESULTS, DEFAULT_MAX_TOKENS
from codeweaver.engine import IndexingServiceDep
from codeweaver.engine.services.indexing_service import IndexingService
from codeweaver.providers import SearchPackageDep, VectorStoreProvider
from codeweaver.providers.types import SearchPackage
from codeweaver.semantic import AgentTask
from codeweaver.server.agent_api.search.conversion import convert_search_result_to_code_match
from codeweaver.server.agent_api.search.filters import apply_filters
from codeweaver.server.agent_api.search.intent import (
    INTENT_TO_AGENT_TASK,
    IntentType,
    detect_intent,
)
from codeweaver.server.agent_api.search.pipeline import (
    build_query_vector,
    embed_query,
    execute_vector_search,
    rerank_results,
)
from codeweaver.server.agent_api.search.response import build_error_response, build_success_response
from codeweaver.server.agent_api.search.scoring import (
    process_reranked_results,
    process_unranked_results,
)
from codeweaver.server.agent_api.search.types import CodeMatch, FindCodeResponseSummary


logger = logging.getLogger(__name__)

def _get_settings(settings: SettingsDep=INJECTED) -> CodeWeaverSettingsType:
    """Get the CodeWeaver settings from the dependency."""
    return settings

class MatchedSection(NamedTuple):
    """Represents a matched section within a file."""
    content: str
    span: Span
    score: NonNegativeInt
    filename: str | None = None
    file_path: Path | None = None
    chunk_number: PositiveInt | None = None

async def _check_index_status(context: Context | None, vector_store: VectorStoreProvider | None) -> tuple[bool, int]:
    """Check if index exists and get chunk count.

    Args:
        context: Optional MCP context
        vector_store: Optional pre-initialized vector store instance

    Returns:
        Tuple of (index_exists, chunk_count) where:
        - index_exists: True if collection exists in vector store
        - chunk_count: Number of chunks in collection (0 if doesn't exist)
    """
    from codeweaver.core import Depends, DependsPlaceholder
    if vector_store is None or isinstance(vector_store, (Depends, DependsPlaceholder)):
        try:
            from codeweaver.core import get_container
            from codeweaver.providers import VectorStoreProvider
            vector_store = await get_container().resolve(VectorStoreProvider)
        except Exception:
            logger.warning('No vector store provider provided')
            return (False, 0)
    if vector_store is None:
        logger.warning('No vector store provider provided')
        return (False, 0)
    try:
        if hasattr(vector_store, '_initialize'):
            await vector_store._initialize()
        collection_name = getattr(vector_store, 'collection_name', None) or getattr(vector_store, 'collection', None)
        if not collection_name:
            return (False, 0)
        exists = await vector_store.client.collection_exists(collection_name)
        if not exists:
            return (False, 0)
        info = await vector_store.client.get_collection(collection_name)
    except Exception as e:
        logger.warning('Failed to check index status: %s', e)
        return (False, 0)
    else:
        return (True, info.points_count or 0)

def _get_indexer(indexer: IndexingServiceDep=INJECTED) -> IndexingService | None:
    """Get the indexing service from the dependency injection system."""
    return indexer

async def _resolve_indexer_from_container() -> IndexingService | None:
    """Resolve IndexingService from the DI container."""
    try:
        from codeweaver.core.di.container import get_container
        from codeweaver.engine import IndexingService

        container = get_container()
        return await container.resolve(IndexingService)
    except Exception as e:
        logger.warning("Failed to resolve IndexingService from container: %s", e, exc_info=True)
        return None

async def _ensure_index_ready(context: Context | None=None, vector_store: VectorStoreProvider | None=None, indexer: IndexingService | None=None) -> None:
    """Ensure that the codebase is indexed before performing a search.

    If indexing is already complete or in progress, this is a no-op.
    """
    indexer = indexer or await _resolve_indexer_from_container()
    if indexer is None:
        return
    if indexer._vector_store:
        try:
            await indexer.index_project(add_dense=True, add_sparse=True)
        except Exception as e:
            logger.warning('Auto-indexing failed: %s', e, exc_info=True)

async def _build_search_package(package: SearchPackageDep) -> SearchPackage:
    """Build a search package from the given dependency."""
    return package

async def _handle_intent_detection(query: str, intent: IntentType | None) -> tuple[IntentType, AgentTask]:
    """Detect or use provided intent and map to agent task.

    Args:
        query: Search query
        intent: Optional explicit intent override

    Returns:
        Tuple of (intent_type, agent_task)
    """
    if intent is not None:
        intent_type = intent
        confidence = 1.0
    else:
        query_intent_obj = detect_intent(query)
        intent_type = query_intent_obj.intent_type
        confidence = query_intent_obj.confidence
    raw_agent_task = INTENT_TO_AGENT_TASK.get(intent_type, 'DEFAULT')
    agent_task = AgentTask[raw_agent_task]
    logger.info('Query intent detected: %s (confidence: %.2f)', intent_type, confidence)
    return (intent_type, agent_task)

async def _process_and_score_candidates(query: str, candidates: list, intent_type: IntentType, agent_task: AgentTask, context: Context | None, reranking_provider) -> tuple[list, list[SearchStrategy]]:
    """Apply reranking and semantic scoring to search candidates.

    Args:
        query: Search query
        candidates: Initial search candidates
        intent_type: Detected query intent
        agent_task: Mapped agent task
        context: Optional MCP context
        reranking_provider: Optional reranking provider

    Returns:
        Tuple of (scored_candidates, strategies_used)
    """
    strategies_used: list[SearchStrategy] = []
    reranked_results, rerank_strategy = await rerank_results(query, candidates, context=context, reranking=reranking_provider)
    if rerank_strategy:
        strategies_used.append(rerank_strategy)
    if reranked_results:
        scored_candidates = process_reranked_results(reranked_results, candidates, intent_type, agent_task)
    else:
        scored_candidates = process_unranked_results(candidates, intent_type, agent_task)
    return (scored_candidates, strategies_used)

async def _finalize_response(code_matches: list[CodeMatch], query: str, intent_type: IntentType, total_candidates: int, token_limit: int, execution_time_ms: float, strategies_used: list[SearchStrategy], telemetry_settings, telemetry) -> FindCodeResponseSummary:
    """Build final response and capture telemetry.

    Args:
        code_matches: Converted search results
        query: Original search query
        intent_type: Detected intent
        total_candidates: Total number of candidates
        token_limit: Token limit for response
        execution_time_ms: Execution time in milliseconds
        strategies_used: List of search strategies used
        telemetry_settings: Telemetry configuration
        telemetry: Telemetry service

    Returns:
        Final response summary
    """
    response = build_success_response(code_matches=code_matches, query=query, intent_type=intent_type, total_candidates=total_candidates, token_limit=token_limit, execution_time_ms=execution_time_ms, strategies_used=strategies_used)
    if getattr(telemetry_settings, 'tools_over_privacy', False):
        feature_flags = {'search-ranking-v2': telemetry.client.get_feature_flag('search-ranking-v2'), 'rerank-strategy': telemetry.client.get_feature_flag('rerank-strategy')}
        try:
            await capture_search_event(response=response, query=query, intent_type=intent_type, strategies=strategies_used, execution_time_ms=execution_time_ms, tools_over_privacy=getattr(telemetry_settings, 'tools_over_privacy', False), feature_flags=feature_flags)
        except Exception:
            logger.debug('Failed to capture search telemetry')
    return response

async def find_code(query: str, *, intent: IntentType | None=None, token_limit: int=DEFAULT_MAX_TOKENS, focus_languages: tuple[str, ...] | None=None, max_results: int=DEFAULT_MAX_RESULTS, context: Context | None=None, search_package: SearchPackageDep=INJECTED, telemetry_settings: TelemetrySettingsDep=INJECTED, telemetry: TelemetryServiceDep=INJECTED) -> FindCodeResponseSummary:
    """Find relevant code based on semantic search with intent-driven ranking."""
    from codeweaver.core.di import get_container
    from codeweaver.core.di.dependency import is_depends_marker
    if is_depends_marker(search_package):
        container = get_container()
        search_package = await container.resolve(SearchPackage)
    if is_depends_marker(telemetry_settings):
        container = get_container()
        from codeweaver.core.config.telemetry import TelemetrySettings
        telemetry_settings = await container.resolve(TelemetrySettings)
    if is_depends_marker(telemetry):
        container = get_container()
        from codeweaver.core.telemetry.client import TelemetryService
        telemetry = await container.resolve(TelemetryService)
    start_time = time.monotonic()
    strategies_used: list[SearchStrategy] = []
    try:
        index_exists, chunk_count = await _check_index_status(context, vector_store=search_package.vector_store)
        if not index_exists or chunk_count == 0:
            await log_to_client_or_fallback(context, 'warning', {'message': 'The code index is not ready. Starting index. This could take awhile...'})
            await _ensure_index_ready(context, vector_store=search_package.vector_store)
        intent_type, agent_task = await _handle_intent_detection(query, intent)
        embeddings = await embed_query(query, context=context, dense_provider=search_package.embedding, sparse_provider=search_package.sparse_embedding)
        query_vector = build_query_vector(embeddings, query)
        strategies_used.append(query_vector.strategy)
        candidates = await execute_vector_search(query_vector, context=context, vector_store=search_package.vector_store)
        candidates = apply_filters(candidates, include_tests=intent_type in {IntentType.DEBUG, IntentType.TEST}, focus_languages=focus_languages)
        logger.info('Vector search returned %d candidates after filtering', len(candidates))
        scored_candidates, rerank_strategies = await _process_and_score_candidates(query, candidates, intent_type, agent_task, context, search_package.reranking)
        strategies_used.extend(rerank_strategies)
        scored_candidates.sort(key=lambda x: x.relevance_score if x.relevance_score is not None else x.score, reverse=True)
        search_results = scored_candidates[:max_results]
        code_matches: list[CodeMatch] = []
        for result in search_results:
            try:
                match: CodeMatch = await convert_search_result_to_code_match(result)
                code_matches.append(match)
            except Exception as e:
                logger.warning('Failed to convert search result to code match: %s', e)
                continue
        execution_time_ms = (time.monotonic() - start_time) * 1000
        response = await _finalize_response(code_matches, query, intent_type, len(scored_candidates), token_limit, execution_time_ms, strategies_used, telemetry_settings, telemetry)
    except Exception as e:
        logger.warning('find_code failed: %s', e, exc_info=True)
        execution_time_ms = (time.monotonic() - start_time) * 1000
        error_response = build_error_response(e, intent, execution_time_ms, vector_store=search_package.vector_store, dense=search_package.embedding, reranking=search_package.reranking, sparse=search_package.sparse_embedding)
        try:
            await capture_search_event(response=error_response, query=query, intent_type=intent or IntentType.UNDERSTAND, strategies=strategies_used, execution_time_ms=execution_time_ms, tools_over_privacy=getattr(telemetry_settings, 'tools_over_privacy', False), feature_flags=None)
        except Exception:
            logger.debug('Failed to capture error search telemetry')
        return error_response
    else:
        return response
from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.server.agent_api.search.filters import filter_by_languages, filter_test_files
    from codeweaver.server.agent_api.search.intent import (
        INTENT_KEYWORDS,
        IntentResult,
        QueryComplexity,
        QueryIntent,
    )
    from codeweaver.server.agent_api.search.pipeline import raise_value_error
    from codeweaver.server.agent_api.search.response import (
        calculate_token_count,
        extract_languages,
        generate_summary,
        get_indexer_state_info,
    )
    from codeweaver.server.agent_api.search.scoring import (
        apply_hybrid_weights,
        apply_semantic_weighting,
    )
    from codeweaver.server.agent_api.search.types import CodeMatchType, FindCodeSubmission
_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({'INTENT_KEYWORDS': (__spec__.parent, 'intent'), 'CodeMatchType': (__spec__.parent, 'types'), 'FindCodeSubmission': (__spec__.parent, 'types'), 'IntentResult': (__spec__.parent, 'intent'), 'QueryComplexity': (__spec__.parent, 'intent'), 'QueryIntent': (__spec__.parent, 'intent'), 'apply_hybrid_weights': (__spec__.parent, 'scoring'), 'apply_semantic_weighting': (__spec__.parent, 'scoring'), 'calculate_token_count': (__spec__.parent, 'response'), 'extract_languages': (__spec__.parent, 'response'), 'filter_by_languages': (__spec__.parent, 'filters'), 'filter_test_files': (__spec__.parent, 'filters'), 'generate_summary': (__spec__.parent, 'response'), 'get_indexer_state_info': (__spec__.parent, 'response'), 'raise_value_error': (__spec__.parent, 'pipeline')})
__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)
__all__ = ('INTENT_KEYWORDS', 'INTENT_TO_AGENT_TASK', 'CodeMatch', 'CodeMatchType', 'CodeWeaverSettingsType', 'FindCodeResponseSummary', 'FindCodeSubmission', 'IntentResult', 'IntentType', 'MatchedSection', 'QueryComplexity', 'QueryIntent', 'apply_filters', 'apply_hybrid_weights', 'apply_semantic_weighting', 'build_error_response', 'build_query_vector', 'build_success_response', 'calculate_token_count', 'convert_search_result_to_code_match', 'detect_intent', 'embed_query', 'execute_vector_search', 'extract_languages', 'filter_by_languages', 'filter_test_files', 'find_code', 'generate_summary', 'get_indexer_state_info', 'process_reranked_results', 'process_unranked_results', 'raise_value_error', 'rerank_results')

def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)

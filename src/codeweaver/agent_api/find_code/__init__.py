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
from typing import NamedTuple

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

        # Step 2: Embed query (dense + sparse)
        embeddings = await embed_query(query)

        # Step 3: Build query vector and determine strategy
        query_vector = build_query_vector(embeddings, query)
        strategies_used.append(query_vector.strategy)

        # Step 4: Execute vector search
        candidates = await execute_vector_search(query_vector)

        # Step 5: Post-search filtering (v0.1 simple approach)
        candidates = apply_filters(
            candidates, include_tests=include_tests, focus_languages=focus_languages
        )

        logger.info("Vector search returned %d candidates after filtering", len(candidates))

        # Step 6: Apply static dense/sparse weights (v0.1)
        if SearchStrategy.HYBRID_SEARCH in strategies_used:
            apply_hybrid_weights(candidates)

        # Step 7: Rerank (optional, if provider configured)
        reranked_results, rerank_strategy = await rerank_results(query, candidates)
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
        logger.exception("find_code failed")
        # Return empty response on failure (graceful degradation)
        execution_time_ms = (time.time() - start_time) * 1000
        return build_error_response(e, intent, execution_time_ms)


__all__ = ("MatchedSection", "find_code")

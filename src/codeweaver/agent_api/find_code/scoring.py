# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Scoring and reranking utilities for search results.

This module handles the scoring pipeline including:
- Hybrid search score combination (dense + sparse)
- Semantic reranking
- Intent-based semantic weighting
"""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING

from codeweaver.agent_api.find_code.intent import IntentType
from codeweaver.core.chunks import CodeChunk
from codeweaver.semantic.classifications import AgentTask


if TYPE_CHECKING:
    from codeweaver.core.types.search import SearchResult
    from codeweaver.providers.reranking.providers.base import RerankingResult


logger = logging.getLogger(__name__)


def apply_hybrid_weights(
    candidates: list[SearchResult], dense_weight: float = 0.65, sparse_weight: float = 0.35
) -> None:
    """Apply static weights to hybrid search scores (in-place).

    Args:
        candidates: List of search results with dense and sparse scores
        dense_weight: Weight for dense embeddings (default: 0.65)
        sparse_weight: Weight for sparse embeddings (default: 0.35)

    Note:
        Modifies candidates in place by updating the score attribute.
    """
    for candidate in candidates:
        # Static weights for v0.1: dense=0.65, sparse=0.35
        candidate.score = (
            getattr(candidate, "dense_score", candidate.score) * dense_weight
            + getattr(candidate, "sparse_score", 0.0) * sparse_weight
        )


def apply_semantic_weighting(
    base_score: float,
    chunk: CodeChunk | None,
    intent_type: IntentType,
    agent_task: AgentTask,
    boost_factor: float = 0.2,
) -> float:
    """Apply semantic importance weighting based on intent.

    Args:
        base_score: Base relevance score
        chunk: CodeChunk with potential semantic metadata
        intent_type: Detected query intent
        agent_task: Corresponding agent task
        boost_factor: Maximum boost percentage (default: 0.2 = 20%)

    Returns:
        Final score with semantic weighting applied
    """
    if chunk is None:
        return base_score

    semantic_class = getattr(chunk, "semantic_class", None)
    if not semantic_class or not hasattr(semantic_class, "importance_scores"):
        return base_score

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

    # Apply semantic boost (configurable % adjustment)
    return base_score * (1 + semantic_boost * boost_factor)


def process_reranked_results(
    reranked_results: list[RerankingResult],
    original_candidates: list[SearchResult],
    intent_type: IntentType,
    agent_task: AgentTask,
) -> list[SearchResult]:
    """Process reranked results and apply semantic weighting.

    Args:
        reranked_results: Results from reranking provider
        original_candidates: Original search results (for mapping back)
        intent_type: Detected query intent
        agent_task: Corresponding agent task

    Returns:
        List of SearchResult objects with updated scores
    """
    scored_candidates: list[SearchResult] = []

    for rerank_result in reranked_results:
        # Find original candidate by matching chunk
        original_candidate = original_candidates[rerank_result.original_index]
        base_score = rerank_result.score

        # Apply semantic weighting
        final_score = apply_semantic_weighting(
            base_score, rerank_result.chunk, intent_type, agent_task
        )

        # Create updated SearchResult with new scores
        scored_candidate = original_candidate.model_copy(
            update={"rerank_score": base_score, "relevance_score": final_score}
        )
        scored_candidates.append(scored_candidate)

    return scored_candidates


def process_unranked_results(
    candidates: list[SearchResult], intent_type: IntentType, agent_task: AgentTask
) -> list[SearchResult]:
    """Process results without reranking, applying semantic weighting to base scores.

    Args:
        candidates: Original search results
        intent_type: Detected query intent
        agent_task: Corresponding agent task

    Returns:
        List of SearchResult objects with updated relevance scores
    """
    scored_candidates: list[SearchResult] = []

    for candidate in candidates:
        base_score = candidate.score

        # Apply semantic weighting if semantic class available
        chunk_obj = candidate.content if isinstance(candidate.content, CodeChunk) else None
        final_score = apply_semantic_weighting(base_score, chunk_obj, intent_type, agent_task)

        # Create updated SearchResult with relevance score
        scored_candidate = candidate.model_copy(update={"relevance_score": final_score})
        scored_candidates.append(scored_candidate)

    return scored_candidates


__all__ = (
    "apply_hybrid_weights",
    "apply_semantic_weighting",
    "process_reranked_results",
    "process_unranked_results",
)

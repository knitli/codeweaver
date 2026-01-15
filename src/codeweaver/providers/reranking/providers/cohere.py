# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: avoid-single-character-names-variables, no-complex-if-expressions
"""Cohere reranking provider implementation."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, Any

from pydantic import SkipValidation

from codeweaver.core import Provider, rpartial
from codeweaver.providers.reranking.providers.base import RerankingProvider, RerankingResult


if TYPE_CHECKING:
    from codeweaver.core import CodeChunk


try:
    from cohere import AsyncClientV2 as CohereClient
    from cohere.v2.types.v2rerank_response import V2RerankResponse
    from cohere.v2.types.v2rerank_response_results_item import V2RerankResponseResultsItem
except ImportError as e:
    from codeweaver.core import ConfigurationError

    raise ConfigurationError(
        r'Please install the `cohere` package to use the Cohere provider, \nyou can use the `cohere` optional group -- `pip install "code-weaver\[cohere]"`'
    ) from e


def cohere_reranking_output_transformer(
    returned_result: V2RerankResponse,
    _original_chunks: Iterator[CodeChunk] | tuple[CodeChunk, ...],
    _instance: CohereRerankingProvider,
) -> list[RerankingResult]:
    """Transform the output of the Cohere reranking model.

    Cohere returns reranked results in order from highest score to lowest,
    with their original indices in the results.index field.
    """
    original_chunks = (
        tuple(_original_chunks) if isinstance(_original_chunks, Iterator) else _original_chunks
    )

    def map_result(batch_index: int, cohere_result: V2RerankResponseResultsItem) -> RerankingResult:
        return RerankingResult(
            original_index=cohere_result.index,
            batch_rank=batch_index + 1,
            score=cohere_result.relevance_score,
            chunk=original_chunks[cohere_result.index],
        )

    processed_results = [map_result(i, result) for i, result in enumerate(returned_result.results)]

    # Update token stats
    if (
        tokens := (
            returned_result.meta.tokens.output_tokens or returned_result.meta.tokens.input_tokens
        )
        if returned_result.meta and returned_result.meta.tokens
        else None
    ):
        _instance._update_token_stats(token_count=int(tokens))

    return processed_results


class CohereRerankingProvider(RerankingProvider[CohereClient]):
    """Cohere reranking provider."""

    client: SkipValidation[CohereClient]
    _provider = Provider.COHERE

    def _initialize(self) -> None:
        """Initialize the Cohere reranking provider after Pydantic setup."""
        # Set up the output transformer to use cohere_reranking_output_transformer
        self._output_transformer = rpartial(  # ty:ignore[invalid-assignment]
            cohere_reranking_output_transformer, _instance=self
        )

    @property
    def base_url(self) -> str:
        """Get the base URL for the Cohere API."""
        return "https://api.cohere.com"

    async def _execute_rerank(
        self, query: str, documents: Sequence[str], *, top_n: int = 10, **kwargs: Any
    ) -> V2RerankResponse:
        return await self.client.rerank(
            model=self.model_name or self.caps.name,
            query=query,
            documents=documents,
            top_n=top_n,
            **kwargs,
        )


__all__ = ("CohereRerankingProvider",)

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: avoid-single-character-names-variables
"""Cohere reranking provider implementation."""

import asyncio
import os

from collections.abc import Sequence
from typing import Any

from codeweaver._data_structures import CodeChunk
from codeweaver._settings import Provider
from codeweaver.exceptions import ConfigurationError
from codeweaver.reranking.capabilities.base import RerankingModelCapabilities
from codeweaver.reranking.providers.base import RerankingProvider, RerankingResult


try:
    from cohere import AsyncClientV2 as CohereClient
    from cohere.v2.types.v2rerank_response import V2RerankResponse
    from cohere.v2.types.v2rerank_response_results_item import V2RerankResponseResultsItem
except ImportError as e:
    raise ConfigurationError(
        'Please install the `cohere` package to use the Cohere provider, \nyou can use the `cohere` optional group — `pip install "codeweaver[provider-cohere]"`'
    ) from e


class CohereRerankingProvider(RerankingProvider[CohereClient]):
    """Cohere reranking provider."""

    _client: CohereClient
    _provider = Provider.COHERE
    _caps: RerankingModelCapabilities

    def __init__(
        self, caps: RerankingModelCapabilities, _client: CohereClient | None = None, **kwargs: Any
    ) -> None:
        """Initialize the Cohere reranking provider."""
        self._caps = caps
        self._provider = caps.provider or self._provider
        kwargs = kwargs or {}
        self.client_kwargs = kwargs.get("client_kwargs", {}) or kwargs
        self.client_kwargs["client_name"] = "codeweaver"
        if not self.client_kwargs.get("api_key"):
            if self._provider == Provider.COHERE:
                self.client_kwargs["api_key"] = kwargs.get("api_key") or os.getenv("COHERE_API_KEY")

            if not self.client_kwargs.get("api_key"):
                raise ConfigurationError(
                    f"API key not found for {self._provider.value} provider. Please set the API key in the client kwargs or as an environment variable."
                )
        self._client = _client or CohereClient(**self.client_kwargs)
        super().__init__(self._client, caps, **kwargs)

    @property
    def base_url(self) -> str:
        """Get the base URL for the Cohere API."""
        return "https://api.cohere.com"

    async def _execute_rerank(
        self, query: str, documents: Sequence[str], *, top_n: int = 40, **kwargs: dict[str, Any]
    ) -> V2RerankResponse:
        return await self._client.rerank(
            model=self.model_name or self._caps.name,
            query=query,
            documents=documents,
            top_n=top_n,
            **kwargs,  # pyright: ignore[reportArgumentType]
        )

    def process_cohere_output(
        self, response: V2RerankResponse, chunks: Sequence[CodeChunk]
    ) -> Sequence[RerankingResult]:
        """Process the output from the Cohere API.

        Cohere returns the raranked results *in order from highest score to lowest*, with their original indices in the results.index field.
        """

        def map_result(index: int, cohere_result: V2RerankResponseResultsItem) -> RerankingResult:
            return RerankingResult(
                original_index=cohere_result.index,
                batch_rank=index + 1,
                score=cohere_result.relevance_score,
                chunk=chunks[cohere_result.index],
            )

        processed_results = [map_result(i, result) for i, result in enumerate(response.results)]
        loop = asyncio.get_running_loop()
        if (
            tokens := (response.meta.tokens.output_tokens or response.meta.tokens.input_tokens)
            if response.meta and response.meta.tokens
            else None
        ):
            _ = loop.run_in_executor(None, self._update_token_stats, token_count=int(tokens))  # type: ignore
        else:
            _ = loop.run_in_executor(  # type: ignore
                None,
                self._update_token_stats,
                from_docs=self._input_transformer(chunks),  # type: ignore
            )  # type: ignore
        return processed_results

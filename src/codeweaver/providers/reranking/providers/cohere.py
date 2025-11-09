# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: avoid-single-character-names-variables
"""Cohere reranking provider implementation."""

from __future__ import annotations

import asyncio
import os

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from codeweaver.providers.provider import Provider
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
from codeweaver.providers.reranking.providers.base import RerankingProvider, RerankingResult


if TYPE_CHECKING:
    from codeweaver.core.chunks import CodeChunk


try:
    from cohere import AsyncClientV2 as CohereClient
    from cohere.v2.types.v2rerank_response import V2RerankResponse
    from cohere.v2.types.v2rerank_response_results_item import V2RerankResponseResultsItem
except ImportError as e:
    from codeweaver.exceptions import ConfigurationError

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
        # Prepare client options before calling super().__init__()
        kwargs = kwargs or {}
        client_options = kwargs.get("client_options", {}) or kwargs
        client_options["client_name"] = "codeweaver"

        provider = caps.provider or Provider.COHERE

        if not client_options.get("api_key"):
            if provider == Provider.COHERE:
                client_options["api_key"] = kwargs.get("api_key") or os.getenv("COHERE_API_KEY")

            if not client_options.get("api_key"):
                from codeweaver.exceptions import ConfigurationError

                raise ConfigurationError(
                    f"API key not found for {provider.value} provider. Please set the API key in the client kwargs or as an environment variable."
                )

        # Initialize client if not provided
        if _client is None:
            _client = CohereClient(**client_options)

        # Store client before calling super().__init__()
        self._client = _client

        # Call super().__init__() which handles Pydantic initialization
        super().__init__(self._client, caps, **kwargs)

    def _initialize(self) -> None:
        """Initialize the Cohere reranking provider after Pydantic setup."""
        # Set _caps and _provider after Pydantic initialization
        # Note: base class might set these, but we ensure they're correct here

    @property
    def base_url(self) -> str:
        """Get the base URL for the Cohere API."""
        return "https://api.cohere.com"

    async def _execute_rerank(
        self, query: str, documents: Sequence[str], *, top_n: int = 40, **kwargs: Any
    ) -> V2RerankResponse:
        return await self._client.rerank(
            model=self.model_name or self._caps.name,
            query=query,
            documents=documents,
            top_n=top_n,
            **kwargs,
        )

    def process_cohere_output(
        self, response: V2RerankResponse, chunks: tuple[CodeChunk]
    ) -> list[RerankingResult]:
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


__all__ = ("CohereRerankingProvider",)

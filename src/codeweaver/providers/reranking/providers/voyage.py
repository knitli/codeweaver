# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Voyage AI reranking provider implementation."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

from pydantic import ConfigDict

from codeweaver.common.utils.utils import rpartial
from codeweaver.exceptions import ProviderError
from codeweaver.providers.provider import Provider
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
from codeweaver.providers.reranking.providers.base import RerankingProvider, RerankingResult


if TYPE_CHECKING:
    from codeweaver.core.chunks import CodeChunk


try:
    from voyageai.client_async import AsyncClient
    from voyageai.object.reranking import RerankingObject
    from voyageai.object.reranking import RerankingResult as VoyageRerankingResult

except ImportError as e:
    from codeweaver.exceptions import ConfigurationError

    raise ConfigurationError(
        "Voyage AI SDK is not installed. Please install it with `pip install codeweaver[provider-voyage]`."
    ) from e


def voyage_reranking_output_transformer(
    returned_result: RerankingObject,
    _original_chunks: Iterator[CodeChunk] | tuple[CodeChunk, ...],
    _instance: VoyageRerankingProvider,
) -> list[RerankingResult]:
    """Transform the output of the Voyage AI reranking model."""
    original_chunks = (
        tuple(_original_chunks) if isinstance(_original_chunks, Iterator) else _original_chunks
    )

    def map_result(voyage_result: VoyageRerankingResult, new_index: int) -> RerankingResult:
        """Maps a VoyageRerankingResult to a CodeWeaver RerankingResult."""
        return RerankingResult(
            original_index=voyage_result.index,  # type: ignore
            batch_rank=new_index,
            score=voyage_result.relevance_score,  # type: ignore
            chunk=original_chunks[voyage_result.index],  # type: ignore
        )

    results, token_count = returned_result.results, returned_result.total_tokens
    _instance._update_token_stats(token_count=token_count)
    results.sort(key=lambda x: cast(float, x[2]), reverse=True)
    return [map_result(res, i) for i, res in enumerate(results, 1)]


class VoyageRerankingProvider(RerankingProvider[AsyncClient]):
    """Base class for reranking providers."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    _client: AsyncClient
    _provider: Provider = Provider.VOYAGE
    _prompt: str | None = None  # custom prompts not supported
    _caps: RerankingModelCapabilities

    _rerank_kwargs: MappingProxyType[str, Any]
    _output_transformer: Callable[
        [Any, Iterator[CodeChunk] | tuple[CodeChunk, ...]], list[RerankingResult]
    ] = lambda x, y: x  # placeholder, actually set in _initialize()

    def _initialize(self) -> None:
        type(self)._output_transformer = rpartial(
            voyage_reranking_output_transformer, _instance=self
        )

    async def _execute_rerank(
        self, query: str, documents: Sequence[str], *, top_n: int = 40, **kwargs: Any
    ) -> Any:
        """Execute the reranking process."""
        try:
            response = await self.client.rerank(
                query=query,
                documents=[documents] if isinstance(documents, str) else documents,  # ty: ignore[invalid-argument-type]
                model=self.caps.name,
                top_k=top_n,
                **kwargs,
            )
        except Exception as e:
            raise ProviderError(
                f"Voyage AI reranking request failed: {e}",
                details={
                    "provider": "voyage",
                    "model": self.caps.name,
                    "query_length": len(query),
                    "document_count": len(documents),
                    "error_type": type(e).__name__,
                },
                suggestions=[
                    "Check VOYAGE_API_KEY environment variable is set correctly",
                    "Verify network connectivity to Voyage AI API",
                    "Check API rate limits and quotas",
                    "Ensure the reranking model name is valid",
                ],
            ) from e
        else:
            return response


__all__ = ("VoyageRerankingProvider",)

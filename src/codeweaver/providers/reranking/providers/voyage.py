# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Voyage AI reranking provider implementation."""

from collections.abc import Callable, Iterator, Sequence
from types import MappingProxyType
from typing import Any, cast

from pydantic import ConfigDict

from codeweaver.core import CodeChunk
from codeweaver.exceptions import ConfigurationError
from codeweaver.providers.provider import Provider
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
from codeweaver.providers.reranking.providers.base import RerankingProvider, RerankingResult


try:
    from voyageai.client_async import AsyncClient
    from voyageai.object.reranking import RerankingObject
    from voyageai.object.reranking import RerankingResult as VoyageRerankingResult

except ImportError as e:
    raise ConfigurationError(
        "Voyage AI SDK is not installed. Please install it with `pip install codeweaver[provider-voyage]`."
    ) from e


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
        self._output_transformer = self.voyage_reranking_output_transformer

    async def _execute_rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_n: int = 40,
        **kwargs: dict[str, Any] | None,
    ) -> Any:
        """Execute the reranking process."""
        try:
            response = await self.client.rerank(
                query=query,
                documents=documents,  # pyright: ignore[reportArgumentType]  # a list is a sequence...
                model=self._caps.name,
                **{"top_n": top_n, **(kwargs or {})},  # pyright: ignore[reportArgumentType]
            )
        except Exception as e:
            raise RuntimeError(f"Error during reranking with Voyage AI: {e}") from e
        else:
            return response

    def voyage_reranking_output_transformer(
        self,
        returned_result: RerankingObject,
        _original_chunks: Iterator[CodeChunk] | tuple[CodeChunk, ...],
    ) -> list[RerankingResult]:
        """Transform the output of the Voyage AI reranking model."""
        original_chunks = (
            tuple(_original_chunks) if isinstance(_original_chunks, Iterator) else _original_chunks
        )

        def map_result(voyage_result: VoyageRerankingResult, new_index: int) -> RerankingResult:
            """Maps a VoyageRerankingResult to a CodeWeaver RerankingResult."""
            return RerankingResult(
                original_index=voyage_result[0],
                batch_rank=new_index,
                score=voyage_result[2],
                chunk=original_chunks[voyage_result[0]],
            )

        results, token_count = returned_result.results, returned_result.total_tokens
        self._update_token_stats(token_count=token_count)
        results.sort(key=lambda x: cast(float, x[2]), reverse=True)
        return [map_result(res, i) for i, res in enumerate(results, 1)]


__all__ = ("VoyageRerankingProvider",)

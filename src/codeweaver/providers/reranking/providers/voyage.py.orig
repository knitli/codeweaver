# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Voyage AI reranking provider implementation."""

from __future__ import annotations

import asyncio
import logging

from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast
from warnings import filterwarnings

from pydantic import ConfigDict, SkipValidation

from codeweaver.core import Provider, ProviderError, rpartial
from codeweaver.core.constants import DEFAULT_RERANKING_MAX_RESULTS
from codeweaver.providers.reranking.providers.base import RerankingProvider, RerankingResult


if TYPE_CHECKING:
    from codeweaver.core import CodeChunk

logger = logging.getLogger(__name__)

try:
    from voyageai.client_async import AsyncClient
    from voyageai.object.reranking import RerankingObject
    from voyageai.object.reranking import RerankingResult as VoyageRerankingResult

except ImportError as e:
    from codeweaver.core import ConfigurationError

    raise ConfigurationError(
        r"Voyage AI SDK is not installed. Please install it with `pip install code-weaver\[voyage]`."
    ) from e


# We need to filter UserWarning about shadowing the parent class
filterwarnings("ignore", category=UserWarning, message='.*RerankingProvider" shadows.*')


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
            original_index=voyage_result.index,
            batch_rank=new_index,
            score=voyage_result.relevance_score,
            chunk=original_chunks[voyage_result.index],
        )

    results, token_count = returned_result.results, returned_result.total_tokens
    try:
        loop = _instance._loop or asyncio.get_running_loop()
        _ = loop.call_soon_threadsafe(
            lambda: _instance._update_token_stats(token_count=token_count)
        )
    except RuntimeError:
        _instance._update_token_stats(token_count=token_count)
    # Sort by relevance_score - handle both tuple (x[2]) and attribute (x.relevance_score) access
    try:
        results.sort(key=lambda x: cast(float, x.relevance_score), reverse=True)
    except AttributeError:
        results.sort(key=lambda x: cast(float, x[2]), reverse=True)
    return [map_result(res, i) for i, res in enumerate(results, 1)]


class VoyageRerankingProvider(RerankingProvider[AsyncClient]):
    """Voyage AI reranking provider implementation."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    client: SkipValidation[AsyncClient]
    _provider: ClassVar[Literal[Provider.VOYAGE]] = Provider.VOYAGE

    def _initialize(self) -> None:
        """Initialize after Pydantic setup."""
        self._output_transformer = rpartial(  # ty:ignore[invalid-assignment]
            voyage_reranking_output_transformer, _instance=self
        )

    async def _execute_rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_n: int = DEFAULT_RERANKING_MAX_RESULTS,
        **kwargs: Any,
    ) -> Any:
        """Execute the reranking process."""
        try:
            # Voyage API doesn't accept extra kwargs - only query, documents, model, top_k
            response = await self.client.rerank(
                query=query,
                documents=[documents] if isinstance(documents, str) else documents,  # ty: ignore[invalid-argument-type]
                model=self.caps.name,
                top_k=top_n,
            )
            self._loop = await self._get_loop()
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


__all__ = ("VoyageRerankingProvider", "voyage_reranking_output_transformer")

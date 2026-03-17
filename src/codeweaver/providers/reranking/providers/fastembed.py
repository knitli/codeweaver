# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Reranking provider for FastEmbed."""

from __future__ import annotations

import logging

from collections.abc import Callable, Sequence
from functools import partial
from typing import Any, ClassVar, cast

import numpy as np

from codeweaver.core import Provider, ProviderError
from codeweaver.core.constants import DEFAULT_RERANKING_MAX_RESULTS
from codeweaver.providers.reranking.providers.base import RerankingProvider


logger = logging.getLogger(__name__)

try:
    from fastembed.rerank.cross_encoder import TextCrossEncoder

except ImportError as e:
    logger.warning(
        "Failed to import TextCrossEncoder from fastembed.rerank.cross_encoder", exc_info=True
    )
    from codeweaver.core import ConfigurationError

    raise ConfigurationError(
        r"FastEmbed is not installed. Please install it with `pip install code-weaver\[fastembed]` or `codeweaver\[fastembed-gpu]`."
    ) from e


class FastEmbedRerankingProvider(RerankingProvider[TextCrossEncoder]):
    """
    FastEmbed implementation of the reranking provider.

    model_name: The name of the FastEmbed model to use.
    """

    client: TextCrossEncoder
    _provider: ClassVar[Provider] = Provider.FASTEMBED

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
            # our batch_size needs to be the number of documents because we only get back the scores.
            # If we set it to a lower number, we wouldn't know what documents the scores correspond to without some extra setup.
            loop = await self._get_loop()
            partial_func = partial(
                cast(Callable[..., np.ndarray], self.client.rerank),
                query=query,
                documents=documents,
                batch_size=len(documents),
                convert_to_numpy=True,
                **(kwargs or {}),
            )
            response = await loop.run_in_executor(None, partial_func)
        except Exception as e:
            raise ProviderError(
                f"FastEmbed reranking execution failed: {e}",
                details={
                    "provider": "fastembed",
                    "model": self.caps.name,
                    "query_length": len(query),
                    "document_count": len(documents),
                    "batch_size": len(documents),
                    "error_type": type(e).__name__,
                },
                suggestions=[
                    "Verify FastEmbed model is properly initialized",
                    "Check if GPU/CUDA is available if using GPU acceleration",
                    "Reduce batch size if encountering memory issues",
                    "Ensure documents are valid text strings",
                ],
            ) from e
        else:
            if hasattr(response, "tolist"):
                return response.tolist()
            return list(response)


__all__ = ("FastEmbedRerankingProvider",)

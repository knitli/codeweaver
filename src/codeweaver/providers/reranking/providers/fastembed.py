# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Reranking provider for FastEmbed."""

from __future__ import annotations

import logging
import multiprocessing

from collections.abc import Sequence
from typing import Any, ClassVar

from codeweaver.core.types.provider import Provider
from codeweaver.exceptions import ProviderError
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
from codeweaver.providers.reranking.providers.base import RerankingProvider


logger = logging.getLogger(__name__)

try:
    from fastembed.rerank.cross_encoder import TextCrossEncoder

except ImportError as e:
    logger.warning(
        "Failed to import TextCrossEncoder from fastembed.rerank.cross_encoder", exc_info=True
    )
    from codeweaver.exceptions import ConfigurationError

    raise ConfigurationError(
        r"FastEmbed is not installed. Please install it with `pip install code-weaver\[fastembed]` or `codeweaver\[fastembed-gpu]`."
    ) from e


def fastembed_kwargs(**kwargs: Any) -> dict[str, Any]:
    """Get all possible kwargs for FastEmbed embedding methods."""
    default_kwargs: dict[str, Any] = {"threads": multiprocessing.cpu_count(), "lazy_load": True}
    if kwargs:
        device_ids: list[int] | None = kwargs.get("device_ids")
        cuda: bool | None = kwargs.get("cuda")
        if cuda == False:  # user **explicitly** disabled cuda  # noqa: E712
            return default_kwargs | kwargs
        cuda = bool(cuda)
        from codeweaver.providers.optimize import decide_fastembed_runtime

        decision = decide_fastembed_runtime(explicit_cuda=cuda, explicit_device_ids=device_ids)
        if isinstance(decision, tuple) and len(decision) == 2:
            cuda = True
            device_ids = decision[1]
        elif decision == "gpu":
            cuda = True
            device_ids = [0]
        else:
            cuda = False
            device_ids = None
        if cuda:
            kwargs["cuda"] = True
            kwargs["device_ids"] = device_ids
            kwargs["providers"] = ["CUDAExecutionProvider"]
    return default_kwargs | kwargs


class FastEmbedRerankingProvider(RerankingProvider[TextCrossEncoder]):
    """
    FastEmbed implementation of the reranking provider.

    model_name: The name of the FastEmbed model to use.
    """

    client: TextCrossEncoder
    _provider: Provider = Provider.FASTEMBED
    caps: RerankingModelCapabilities

    _kwargs: ClassVar[dict[str, Any]] = fastembed_kwargs()

    # default transformers work fine for fastembed]

    def _initialize(self) -> None:
        if "model_name" not in self.kwargs:
            self.kwargs["model_name"] = self.caps.name
        self.client = TextCrossEncoder(**self.kwargs)

    async def _execute_rerank(
        self, query: str, documents: Sequence[str], *, top_n: int = 40, **kwargs: Any
    ) -> Any:
        """Execute the reranking process."""
        try:
            # our batch_size needs to be the number of documents because we only get back the scores.
            # If we set it to a lower number, we wouldn't know what documents the scores correspond to without some extra setup.
            response = self.client.rerank(
                query=query, documents=documents, batch_size=len(documents), **(kwargs or {})
            )
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
            return response


__all__ = ("FastEmbedRerankingProvider",)

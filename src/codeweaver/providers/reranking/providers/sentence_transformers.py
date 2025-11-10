# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: no-complex-if-expressions
"""Reranking provider for FastEmbed."""

from __future__ import annotations

import asyncio
import logging

from collections.abc import Callable, Sequence
from types import MappingProxyType
from typing import Any, cast

import numpy as np

from codeweaver.common.utils.utils import rpartial
from codeweaver.exceptions import ValidationError as CodeWeaverValidationError
from codeweaver.providers.provider import Provider
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
from codeweaver.providers.reranking.providers.base import RerankingProvider


logger = logging.getLogger(__name__)

try:
    from sentence_transformers import CrossEncoder

except ImportError as e:
    logger.exception("Failed to import CrossEncoder from sentence_transformers")
    from codeweaver.exceptions import ConfigurationError

    raise ConfigurationError(
        "SentenceTransformers is not installed. Please install it with `pip install codeweaver[sentence-transformers]` or `codeweaver[sentence-transformers-gpu]`."
    ) from e


def preprocess_for_qwen(
    query: str, documents: Sequence[str], instruction: str, prefix: str, suffix: str
) -> Sequence[tuple[str, str]]:
    """Preprocess the query and documents for Qwen models."""

    def format_doc(doc: str) -> tuple[str, str]:
        return (
            f"{prefix}<Instruct>: {instruction}\n<Query>:\n{query}\n",
            f"<Document>:\n{doc}{suffix}",
        )

    return [format_doc(doc) for doc in documents]


class SentenceTransformersRerankingProvider(RerankingProvider[CrossEncoder]):
    """
    SentenceTransformers implementation of the reranking provider.

    model_name: The name of the SentenceTransformers model to use.
    """

    client: CrossEncoder
    _provider: Provider = Provider.SENTENCE_TRANSFORMERS
    caps: RerankingModelCapabilities

    _rerank_kwargs: MappingProxyType[str, Any] = MappingProxyType({"trust_remote_code": True})

    def __init__(
        self,
        capabilities: RerankingModelCapabilities,
        client: CrossEncoder | None = None,
        prompt: str | None = None,
        top_n: int = 40,
        **kwargs: Any,
    ) -> None:
        """Initialize the SentenceTransformersRerankingProvider."""
        # Prepare kwargs before calling super().__init__()
        rerank_kwargs = {**type(self)._rerank_kwargs, **kwargs}

        # Initialize client if not provided
        if client is None:
            client = CrossEncoder(capabilities.name, **rerank_kwargs)

        # Store client before calling super().__init__()
        self.client = client

        # Call super().__init__() which handles Pydantic initialization
        super().__init__(
            client=self.client,
            capabilities=capabilities,
            prompt=prompt,
            top_n=top_n,
            **rerank_kwargs,
        )

    def _initialize(self) -> None:
        """
        Initialize the SentenceTransformersRerankingProvider.
        """
        # Set default model path if not provided
        if "model_name" not in self.kwargs and "model_name_or_path" not in self.kwargs:
            self.kwargs["model_name_or_path"] = self.caps.name

        # Extract model name, with fallback to capabilities name
        name = (
            self.kwargs.pop("model_name", None)
            or self.kwargs.pop("model_name_or_path", None)
            or self.caps.name
        )

        if not isinstance(name, str):
            raise CodeWeaverValidationError(
                "Reranking model name must be a string",
                details={
                    "provider": "sentence_transformers",
                    "received_type": type(name).__name__,
                    "received_value": str(name)[:100],
                },
                suggestions=[
                    "Provide model_name as a string, not an object",
                    "Check model configuration in capabilities",
                    "Verify model name is properly initialized",
                ],
            )

        # Note: _client is already initialized by __init__, no need to reinitialize
        if "Qwen3" in name:
            self._setup_qwen3()

    async def _execute_rerank(
        self, query: str, documents: Sequence[str], *, top_n: int = 40, **kwargs: Any
    ) -> Any:
        """Execute the reranking process."""
        preprocessed = (
            preprocess_for_qwen(
                query=query,
                documents=documents,
                instruction=self.caps.custom_prompt or "",
                prefix=self._query_prefix,
                suffix=self._doc_suffix,
            )
            if "Qwen3" in self.caps.name
            else [(query, doc) for doc in documents]
        )
        predict_partial = rpartial(
            cast(Callable[..., np.ndarray], self.client.predict), convert_to_numpy=True
        )
        loop = asyncio.get_running_loop()
        scores = await loop.run_in_executor(None, predict_partial, preprocessed)
        return scores.tolist()

    def _setup_qwen3(self) -> None:
        """Sets up Qwen3 specific parameters."""
        if "Qwen3" not in cast(str, self.kwargs["model_name"]):
            return
        from importlib import metadata

        try:
            has_flash_attention = metadata.version("flash_attn")
        except Exception:
            has_flash_attention = None

        if other := self.caps.other:
            self._query_prefix = f"{other.get('prefix', '')}{self.caps.custom_prompt}\n<Query>:\n"
            self._doc_suffix = other.get("suffix", "")
        self.kwargs["model_kwargs"] = {"torch_dtype": "torch.float16"}
        if has_flash_attention:
            self.kwargs["model_kwargs"]["attention_implementation"] = "flash_attention_2"


__all__ = ("SentenceTransformersRerankingProvider",)

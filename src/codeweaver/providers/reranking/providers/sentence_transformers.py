# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: no-complex-if-expressions
"""Reranking provider for FastEmbed."""

from __future__ import annotations

import logging

from collections.abc import Callable, Sequence
from typing import Any, ClassVar, Literal, cast

import numpy as np

from codeweaver.core import Provider, has_package, rpartial
from codeweaver.core import ValidationError as CodeWeaverValidationError
from codeweaver.core.constants import DEFAULT_RERANKING_MAX_RESULTS
from codeweaver.providers.reranking.providers.base import RerankingProvider


logger = logging.getLogger(__name__)

try:
    from sentence_transformers import CrossEncoder

except ImportError as e:
    logger.warning("Failed to import CrossEncoder from sentence_transformers", exc_info=True)
    from codeweaver.core import ConfigurationError

    raise ConfigurationError(
        r"SentenceTransformers is not installed. Please install it with `pip install code-weaver\[sentence-transformers]` or `code-weaver\[sentence-transformers-gpu]`."
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
    _provider: ClassVar[Literal[Provider.SENTENCE_TRANSFORMERS]] = Provider.SENTENCE_TRANSFORMERS

    def _initialize(self) -> None:
        """
        Initialize the SentenceTransformers reranking provider after Pydantic setup.
        """
        # Extract model name from capabilities
        name = self.caps.name

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

        # Client is already initialized by DI, just set up model-specific configuration
        if "Qwen3" in name:
            self._setup_qwen3()

    async def _execute_rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_n: int = DEFAULT_RERANKING_MAX_RESULTS,
        **kwargs: Any,
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
            if ("qwen3" in str(self.model_name.lower()))
            else [(query, doc) for doc in documents]
        )
        predict_partial = rpartial(
            cast(Callable[..., np.ndarray], self.client.predict), convert_to_numpy=True
        )
        loop = await self._get_loop()
        scores = await loop.run_in_executor(None, predict_partial, preprocessed)
        return scores.tolist()

    def _setup_qwen3(self) -> None:
        """Sets up Qwen3 specific parameters."""
        if "Qwen3" not in cast(str, self.kwargs["model_name"]):
            return
        if other := self.caps.other:
            self._query_prefix = f"{other.get('prefix', '')}{self.caps.custom_prompt}\n<Query>:\n"
            self._doc_suffix = other.get("suffix", "")
        self.kwargs["model_kwargs"] = {"torch_dtype": "torch.float16"}
        if has_package("flash_attn"):
            self.kwargs["model_kwargs"]["attention_implementation"] = "flash_attention_2"


__all__ = ("SentenceTransformersRerankingProvider",)

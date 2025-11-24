# Copyright (c) 2024 to present Pydantic Services Inc
# SPDX-License-Identifier: MIT
# Applies to original code in this directory (`src/codeweaver/embedding_providers/`) from `pydantic_ai`.
#
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# applies to new/modified code in this directory (`src/codeweaver/embedding_providers/`)
"""HuggingFace embedding provider."""

from __future__ import annotations

import logging

from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, Any

import numpy as np

from codeweaver.exceptions import ConfigurationError
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.embedding.providers.base import EmbeddingProvider
from codeweaver.providers.provider import Provider


if TYPE_CHECKING:
    from codeweaver.core.chunks import CodeChunk


logger = logging.getLogger(__name__)


def huggingface_hub_input_transformer(chunks: Sequence[CodeChunk]) -> Iterator[str]:
    """Input transformer for Hugging Face Hub models."""
    # The hub client only takes a single string at a time, so we'll just use a generator here
    from codeweaver.core.chunks import CodeChunk

    return CodeChunk.dechunkify(chunks)


def huggingface_hub_output_transformer(
    output: Iterator[np.ndarray],
) -> list[list[float]] | list[list[int]]:
    """Output transformer for Hugging Face Hub models."""
    return [out.tolist() for out in output]


def huggingface_hub_embed_kwargs(**kwargs: Any) -> dict[str, Any]:
    """Keyword arguments for Hugging Face Hub models."""
    kwargs = kwargs or {}
    return {"normalize": True, "prompt_name": "passage", **kwargs}


def huggingface_hub_query_kwargs(**kwargs: Any) -> dict[str, Any]:
    """Keyword arguments for the query embedding method."""
    kwargs = kwargs or {}
    return {"normalize": True, "prompt_name": "query", **kwargs}


try:
    from huggingface_hub import AsyncInferenceClient

except ImportError as e:
    logger.debug("HuggingFace Hub is not installed.")
    raise ConfigurationError(
        'Please install the `huggingface_hub` package to use the HuggingFace provider, you can use the `huggingface` optional group -- `pip install "codeweaver[huggingface]"`'
    ) from e


class HuggingFaceEmbeddingProvider(EmbeddingProvider[AsyncInferenceClient]):
    """HuggingFace embedding provider."""

    client: AsyncInferenceClient
    _provider: Provider = Provider.HUGGINGFACE_INFERENCE
    caps: EmbeddingModelCapabilities

    _output_transformer = staticmethod(huggingface_hub_output_transformer)

    def _initialize(self, caps: EmbeddingModelCapabilities) -> None:
        """We don't need to do anything here."""
        self.doc_kwargs |= {
            "model": self.caps.name,
            **huggingface_hub_embed_kwargs(),
            "prompt_name": "passage",
        }
        self.query_kwargs |= {
            "model": self.caps.name,
            **huggingface_hub_query_kwargs(),
            "prompt_name": "query",
        }

    @property
    def base_url(self) -> str | None:
        """Get the base URL of the embedding provider."""
        return "https://router.huggingface.co/hf-inference/models/"

    async def _embed_sequence(
        self, sequence: Sequence[str], **kwargs: Any
    ) -> Sequence[Sequence[float]] | Sequence[Sequence[int]]:
        """Embed a sequence of strings into vectors."""
        all_output: Sequence[Sequence[float]] | Sequence[Sequence[int]] = []
        for doc in sequence:
            output = await self.client.feature_extraction(doc, **kwargs)  # type: ignore
            all_output.append(output)  # type: ignore
        return all_output

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Embed a list of documents into vectors."""
        transformed_input = self.chunks_to_strings(documents)
        all_output = await self._embed_sequence(transformed_input, **kwargs)
        self._fire_and_forget(lambda: self._update_token_stats(from_docs=transformed_input))
        return self._process_output(all_output)

    async def _embed_query(
        self, query: str | Sequence[str], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Embed a query into a vector."""
        query = [query] if isinstance(query, str) else query
        output = await self._embed_sequence(query, **kwargs)
        self._fire_and_forget(lambda: self._update_token_stats(from_docs=query))
        return self._process_output(output)

    @property
    def dimension(self) -> int:
        """Get the size of the vector for the collection.

        While some models may support multiple dimensions, the HF Inference API does not.
        """
        return self.caps.default_dimension or 1024


__all__ = ("HuggingFaceEmbeddingProvider",)

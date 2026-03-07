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
from typing import Any, ClassVar, Literal

import numpy as np

from codeweaver.core import CodeChunk, ConfigurationError, Provider
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.embedding.providers.base import (
    EmbeddingCustomDeps,
    EmbeddingImplementationDeps,
    EmbeddingProvider,
)


logger = logging.getLogger(__name__)


def huggingface_hub_input_transformer(chunks: Sequence[CodeChunk]) -> Iterator[str]:
    """Input transformer for Hugging Face Hub models."""
    # The hub client only takes a single string at a time, so we'll just use a generator here
    from codeweaver.core import CodeChunk

    return CodeChunk.dechunkify(chunks)


def huggingface_hub_output_transformer(
    output: Iterator[np.ndarray],
) -> list[list[float]] | list[list[int]]:
    """Output transformer for Hugging Face Hub models."""
    return [out.tolist() for out in output]


try:
    from huggingface_hub import AsyncInferenceClient

except ImportError as e:
    logger.debug("HuggingFace Hub is not installed.")
    raise ConfigurationError(
        r'Please install the `huggingface_hub` package to use the HuggingFace provider, you can use the `huggingface` optional group -- `pip install "code-weaver\[huggingface]"`'
    ) from e


class HuggingFaceEmbeddingProvider(EmbeddingProvider[AsyncInferenceClient]):
    """HuggingFace embedding provider."""

    client: AsyncInferenceClient
    _provider: ClassVar[Literal[Provider.HUGGINGFACE_INFERENCE]] = Provider.HUGGINGFACE_INFERENCE
    caps: EmbeddingModelCapabilities | None = None

    _output_transformer = staticmethod(huggingface_hub_output_transformer)

    def _initialize(
        self,
        impl_deps: EmbeddingImplementationDeps = None,
        custom_deps: EmbeddingCustomDeps = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the HuggingFace embedding client."""
        # Nothing to initialize here - options are set in model_post_init

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
            output = await self.client.feature_extraction(doc, **kwargs)
            all_output.append(output)
        return all_output

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Embed a list of documents into vectors."""
        transformed_input = self.chunks_to_strings(documents)
        all_output = await self._embed_sequence(transformed_input, **kwargs)
        loop = await self._get_loop()
        self._fire_and_forget(
            lambda: self._update_token_stats(from_docs=transformed_input), loop=loop
        )
        return self._process_output(all_output)

    async def _embed_query(
        self, query: str | Sequence[str], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Embed a query into a vector."""
        query = [query] if isinstance(query, str) else query
        output = await self._embed_sequence(query, **kwargs)
        loop = await self._get_loop()
        self._fire_and_forget(lambda: self._update_token_stats(from_docs=query), loop=loop)
        return self._process_output(output)


__all__ = (
    "HuggingFaceEmbeddingProvider",
    "huggingface_hub_input_transformer",
    "huggingface_hub_output_transformer",
)

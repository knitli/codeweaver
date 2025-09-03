# Copyright (c) 2024 to present Pydantic Services Inc
# SPDX-License-Identifier: MIT
# Applies to original code in this directory (`src/codeweaver/embedding_providers/`) from `pydantic_ai`.
#
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# applies to new/modified code in this directory (`src/codeweaver/embedding_providers/`)
"""HuggingFace embedding provider."""

import logging

from collections.abc import Iterator, Sequence
from typing import Any, cast

import numpy as np

from codeweaver._data_structures import CodeChunk
from codeweaver._settings import Provider
from codeweaver.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.embedding.providers.base import EmbeddingProvider


logger = logging.getLogger(__name__)


def huggingface_hub_input_transformer(chunks: Sequence[CodeChunk]) -> Sequence[str]:
    """Input transformer for Hugging Face Hub models."""
    # The hub client only takes a single string at a time, so we'll just use a generator here
    return [cast(str, chunk.serialize_for_embedding()) for chunk in chunks]


def huggingface_hub_output_transformer(
    output: Iterator[np.ndarray],
) -> Sequence[Sequence[float]] | Sequence[Sequence[int]]:
    """Output transformer for Hugging Face Hub models."""
    return [out.tolist() for out in output]


def huggingface_hub_embed_kwargs(**kwargs: dict[str, Any]) -> dict[str, Any]:
    """Keyword arguments for Hugging Face Hub models."""
    kwargs = kwargs or {}
    return {"normalize": True, "prompt_name": "passage", **kwargs}


def huggingface_hub_query_kwargs(**kwargs: dict[str, Any]) -> dict[str, Any]:
    """Keyword arguments for the query embedding method."""
    kwargs = kwargs or {}
    return {"normalize": True, "prompt_name": "query", **kwargs}


try:
    from huggingface_hub import AsyncInferenceClient

except ImportError as e:
    logger.debug("HuggingFace Hub is not installed.")
    raise ImportError(
        'Please install the `huggingface_hub` package to use the HuggingFace provider, you can use the `huggingface` optional group — `pip install "codeweaver[huggingface]"`'
    ) from e
"""
import os
from huggingface_hub import InferenceClient

client = InferenceClient(
    provider="hf-inference",
    api_key=os.environ["HF_TOKEN"],
)

result = client.feature_extraction(
    "Today is a sunny day and I will get some ice cream.",
    model="intfloat/multilingual-e5-large",
)

curl https://router.huggingface.co/hf-inference/models/intfloat/multilingual-e5-large/pipeline/feature-extraction \
    -X POST \
    -H "Authorization: Bearer $HF_TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{
        "inputs": "\"Today is a sunny day and I will get some ice cream.\""
    }'
"""


class HuggingFaceEmbeddingProvider(EmbeddingProvider[AsyncInferenceClient]):
    """HuggingFace embedding provider."""

    _client: AsyncInferenceClient
    _provider: Provider = Provider.HUGGINGFACE_INFERENCE
    _caps: EmbeddingModelCapabilities

    _output_transformer = staticmethod(huggingface_hub_output_transformer)

    def _initialize(self) -> None:
        """We don't need to do anything here."""
        self.doc_kwargs |= {
            "model": self._caps.name,
            **huggingface_hub_embed_kwargs(),
            "prompt_name": "passage",
        }
        self.query_kwargs |= {
            "model": self._caps.name,
            **huggingface_hub_query_kwargs(),
            "prompt_name": "query",
        }

    @property
    def base_url(self) -> str | None:
        """Get the base URL of the embedding provider."""
        return "https://router.huggingface.co/hf-inference/models/"

    async def _embed_sequence(
        self, sequence: Sequence[str], **kwargs: dict[str, Any]
    ) -> Sequence[Sequence[float]] | Sequence[Sequence[int]]:
        """Embed a sequence of strings into vectors."""
        all_output: Sequence[Sequence[float]] | Sequence[Sequence[int]] = []
        for doc in sequence:
            output = await self._client.feature_extraction(doc, **kwargs)  # type: ignore
            all_output.append(output)  # type: ignore
        return all_output

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: dict[str, Any] | None
    ) -> Sequence[Sequence[float]] | Sequence[Sequence[int]]:
        """Embed a list of documents into vectors."""
        transformed_input = self.chunks_to_strings(documents)
        all_output = await self._embed_sequence(transformed_input, **kwargs)  # pyright: ignore[reportArgumentType]
        self._fire_and_forget(
            lambda: self._update_token_stats(from_docs=transformed_input)  # pyright: ignore[reportArgumentType]
        )
        return self._process_output(all_output)

    async def _embed_query(
        self, query: str | Sequence[str], **kwargs: dict[str, Any] | None
    ) -> Sequence[Sequence[float]] | Sequence[Sequence[int]]:
        """Embed a query into a vector."""
        query = [query] if isinstance(query, str) else query
        output = await self._embed_sequence(query, **kwargs)  # pyright: ignore[reportArgumentType]
        self._fire_and_forget(lambda: self._update_token_stats(from_docs=query))
        return self._process_output(output)

    @property
    def dimension(self) -> int:
        """Get the size of the vector for the collection.

        While some models may support multiple dimensions, the HF Inference API does not.
        """
        return self._caps.default_dimension or 1024

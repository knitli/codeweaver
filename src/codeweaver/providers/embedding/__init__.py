# SPDX-FileCopyrightText: (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Entrypoint for CodeWeaver's embedding model system.

We wanted to mirror `pydantic-ai`'s handling of LLM models, but we had to make a lot of adjustments to fit the embedding use case.
"""

# sourcery skip: avoid-global-variables
from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.providers.embedding.capabilities.base import (
        EmbeddingModelCapabilities,
        SparseEmbeddingModelCapabilities,
    )
    from codeweaver.providers.embedding.capabilities.resolver import (
        EmbeddingCapabilityResolver,
        SparseEmbeddingCapabilityResolver,
    )
    from codeweaver.providers.embedding.fastembed_extensions import (
        get_sparse_embedder,
        get_text_embedder,
    )
    from codeweaver.providers.embedding.providers import (
        BedrockEmbeddingProvider,
        CohereEmbeddingProvider,
        FastEmbedEmbeddingProvider,
        FastEmbedSparseProvider,
        GoogleEmbeddingProvider,
        HuggingFaceEmbeddingProvider,
        MistralEmbeddingProvider,
        OpenAIEmbeddingBase,
        SentenceTransformersEmbeddingProvider,
        SentenceTransformersSparseProvider,
        VoyageEmbeddingProvider,
    )
    from codeweaver.providers.embedding.providers.base import (
        EmbeddingProvider,
        SparseEmbeddingProvider,
    )
    from codeweaver.providers.embedding.registry import EmbeddingRegistry, get_embedding_registry

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "BedrockEmbeddingProvider": (__spec__.parent, "providers.bedrock"),
    "CohereEmbeddingProvider": (__spec__.parent, "providers.cohere"),
    "EmbeddingCapabilityResolver": (__spec__.parent, "capabilities.resolver"),
    "SparseEmbeddingCapabilityResolver": (__spec__.parent, "capabilities.resolver"),
    "EmbeddingModelCapabilities": (__spec__.parent, "capabilities.base"),
    "EmbeddingProvider": (__spec__.parent, "providers.base"),
    "EmbeddingRegistry": (__spec__.parent, "registry"),
    "FastEmbedEmbeddingProvider": (__spec__.parent, "providers.fastembed"),
    "FastEmbedSparseProvider": (__spec__.parent, "providers.fastembed"),
    "GoogleEmbeddingProvider": (__spec__.parent, "providers.google"),
    "HuggingFaceEmbeddingProvider": (__spec__.parent, "providers.huggingface"),
    "MistralEmbeddingProvider": (__spec__.parent, "providers.mistral"),
    "OpenAIEmbeddingBase": (__spec__.parent, "providers.openai_factory"),
    "SentenceTransformersEmbeddingProvider": (__spec__.parent, "providers.sentence_transformers"),
    "SentenceTransformersSparseProvider": (__spec__.parent, "providers.sentence_transformers"),
    "SparseEmbeddingModelCapabilities": (__spec__.parent, "capabilities.base"),
    "SparseEmbeddingProvider": (__spec__.parent, "providers.base"),
    "VoyageEmbeddingProvider": (__spec__.parent, "providers.voyage"),
    "get_embedding_registry": (__spec__.parent, "registry"),
    "get_sparse_embedder": (__spec__.parent, "fastembed_extensions"),
    "get_text_embedder": (__spec__.parent, "fastembed_extensions"),
})


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "BedrockEmbeddingProvider",
    "CohereEmbeddingProvider",
    "EmbeddingCapabilityResolver",
    "EmbeddingModelCapabilities",
    "EmbeddingProvider",
    "EmbeddingRegistry",
    "FastEmbedEmbeddingProvider",
    "FastEmbedSparseProvider",
    "GoogleEmbeddingProvider",
    "HuggingFaceEmbeddingProvider",
    "InvalidEmbeddingModelError",
    "MistralEmbeddingProvider",
    "OpenAIEmbeddingBase",
    "SentenceTransformersEmbeddingProvider",
    "SentenceTransformersSparseProvider",
    "SparseEmbeddingCapabilityResolver",
    "SparseEmbeddingModelCapabilities",
    "SparseEmbeddingProvider",
    "VoyageEmbeddingProvider",
    "get_embedding_registry",
    "get_sparse_embedder",
    "get_text_embedder",
)


def __dir__() -> list[str]:
    """List available attributes for the embedding package."""
    return list(__all__)

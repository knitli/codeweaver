# Copyright (c) 2024 to present Pydantic Services Inc
# SPDX-License-Identifier: MIT
# Applies to original code in this directory (`src/codeweaver/embedding_providers/`) from `pydantic_ai`.
#
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# applies to new/modified code in this directory (`src/codeweaver/embedding_providers/`)

"""Entry point for embedding providers. Defines the abstract base class and includes a utility for retrieving specific provider implementations."""

from __future__ import annotations

from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.providers.embedding.providers.base import (
        EmbeddingProvider,
        SparseEmbeddingProvider,
    )
    from codeweaver.providers.embedding.providers.bedrock import BedrockEmbeddingProvider
    from codeweaver.providers.embedding.providers.cohere import CohereEmbeddingProvider
    from codeweaver.providers.embedding.providers.fastembed import (
        FastEmbedEmbeddingProvider,
        FastEmbedSparseEmbeddingProvider,
    )
    from codeweaver.providers.embedding.providers.google import GoogleEmbeddingProvider
    from codeweaver.providers.embedding.providers.huggingface import HuggingFaceEmbeddingProvider
    from codeweaver.providers.embedding.providers.mistral import MistralEmbeddingProvider
    from codeweaver.providers.embedding.providers.openai_factory import OpenAIEmbeddingBase
    from codeweaver.providers.embedding.providers.sentence_transformers import (
        SentenceTransformersEmbeddingProvider,
        SentenceTransformersSparseEmbeddingProvider,
    )
    from codeweaver.providers.embedding.providers.voyage import VoyageEmbeddingProvider

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "BedrockEmbeddingProvider": (__spec__.parent, "bedrock"),
    "CohereEmbeddingProvider": (__spec__.parent, "cohere"),
    "EmbeddingProvider": (__spec__.parent, "base"),
    "SparseEmbeddingProvider": (__spec__.parent, "base"),
    "FastEmbedEmbeddingProvider": (__spec__.parent, "fastembed"),
    "FastEmbedSparseEmbeddingProvider": (__spec__.parent, "fastembed"),
    "GoogleEmbeddingProvider": (__spec__.parent, "google"),
    "HuggingFaceEmbeddingProvider": (__spec__.parent, "huggingface"),
    "MistralEmbeddingProvider": (__spec__.parent, "mistral"),
    "OpenAIEmbeddingBase": (__spec__.parent, "openai_factory"),
    "SentenceTransformersEmbeddingProvider": (__spec__.parent, "sentence_transformers"),
    "SentenceTransformersSparseEmbeddingProvider": (__spec__.parent, "sentence_transformers"),
    "VoyageEmbeddingProvider": (__spec__.parent, "voyage"),
})


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the embedding providers package."""
    if name in _dynamic_imports:
        module_name, submodule_name = _dynamic_imports[name]
        module = import_module(f"{module_name}.{submodule_name}")
        result = getattr(module, name)
        globals()[name] = result  # Cache in globals for future access
        return result
    if globals().get(name) is not None:
        return globals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = (
    "BedrockEmbeddingProvider",
    "CohereEmbeddingProvider",
    "EmbeddingProvider",
    "FastEmbedEmbeddingProvider",
    "FastEmbedSparseEmbeddingProvider",
    "GoogleEmbeddingProvider",
    "HuggingFaceEmbeddingProvider",
    "MistralEmbeddingProvider",
    "OpenAIEmbeddingBase",
    "SentenceTransformersEmbeddingProvider",
    "SentenceTransformersSparseEmbeddingProvider",
    "SparseEmbeddingProvider",
    "VoyageEmbeddingProvider",
)


def __dir__() -> list[str]:
    """List available attributes for the embedding providers package."""
    return list(__all__)

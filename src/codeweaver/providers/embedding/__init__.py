# SPDX-FileCopyrightText: (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Entrypoint for CodeWeaver's embedding model system.

We wanted to mirror `pydantic-ai`'s handling of LLM models, but we had to make a lot of adjustments to fit the embedding use case.
"""

# sourcery skip: avoid-global-variables
from __future__ import annotations

from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.providers.embedding.capabilities.base import (
        EmbeddingModelCapabilities,
        SparseEmbeddingModelCapabilities,
        load_default_capabilities,
        load_sparse_capabilities,
    )
    from codeweaver.providers.embedding.fastembed_extensions import (
        get_sparse_embedder,
        get_text_embedder,
    )
    from codeweaver.providers.embedding.providers import (
        BedrockEmbeddingProvider,
        CohereEmbeddingProvider,
        FastEmbedEmbeddingProvider,
        FastEmbedSparseEmbeddingProvider,
        GoogleEmbeddingProvider,
        HuggingFaceEmbeddingProvider,
        MistralEmbeddingProvider,
        OpenAIEmbeddingBase,
        SentenceTransformersEmbeddingProvider,
        SentenceTransformersSparseEmbeddingProvider,
        VoyageEmbeddingProvider,
    )
    from codeweaver.providers.embedding.providers.base import (
        EmbeddingProvider,
        SparseEmbeddingProvider,
    )
    from codeweaver.providers.embedding.registry import EmbeddingRegistry, get_embedding_registry
    from codeweaver.providers.embedding.types import (
        ChunkEmbeddings,
        EmbeddingBatchInfo,
        EmbeddingKind,
        InvalidEmbeddingModelError,
        QueryResult,
        RawEmbeddingVectors,
        SparseEmbedding,
        StoredEmbeddingVectors,
    )


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "EmbeddingModelCapabilities": (__spec__.parent, "capabilities.base"),
    "SparseEmbeddingModelCapabilities": (__spec__.parent, "capabilities.base"),
    "EmbeddingProvider": (__spec__.parent, "providers.base"),
    "SparseEmbeddingProvider": (__spec__.parent, "providers.base"),
    "load_default_capabilities": (__spec__.parent, "capabilities.base"),
    "load_sparse_capabilities": (__spec__.parent, "capabilities.base"),
    "BedrockEmbeddingProvider": (__spec__.parent, "providers.bedrock"),
    "CohereEmbeddingProvider": (__spec__.parent, "providers.cohere"),
    "FastEmbedEmbeddingProvider": (__spec__.parent, "providers.fastembed"),
    "FastEmbedSparseEmbeddingProvider": (__spec__.parent, "providers.fastembed"),
    "GoogleEmbeddingProvider": (__spec__.parent, "providers.google"),
    "HuggingFaceEmbeddingProvider": (__spec__.parent, "providers.huggingface"),
    "MistralEmbeddingProvider": (__spec__.parent, "providers.mistral"),
    "OpenAIEmbeddingBase": (__spec__.parent, "providers.openai_factory"),
    "SentenceTransformersEmbeddingProvider": (__spec__.parent, "providers.sentence_transformers"),
    "SentenceTransformersSparseEmbeddingProvider": (
        __spec__.parent,
        "providers.sentence_transformers",
    ),
    "VoyageEmbeddingProvider": (__spec__.parent, "providers.voyage"),
    "get_sparse_embedder": (__spec__.parent, "fastembed_extensions"),
    "get_text_embedder": (__spec__.parent, "fastembed_extensions"),
    "EmbeddingRegistry": (__spec__.parent, "registry"),
    "get_embedding_registry": (__spec__.parent, "registry"),
    "InvalidEmbeddingModelError": (__spec__.parent, "types"),
    "SparseEmbedding": (__spec__.parent, "types"),
    "RawEmbeddingVectors": (__spec__.parent, "types"),
    "StoredEmbeddingVectors": (__spec__.parent, "types"),
    "EmbeddingKind": (__spec__.parent, "types"),
    "QueryResult": (__spec__.parent, "types"),
    "EmbeddingBatchInfo": (__spec__.parent, "types"),
    "ChunkEmbeddings": (__spec__.parent, "types"),
})


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the embedding package."""
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
    "ChunkEmbeddings",
    "CohereEmbeddingProvider",
    "EmbeddingBatchInfo",
    "EmbeddingKind",
    "EmbeddingModelCapabilities",
    "EmbeddingProvider",
    "EmbeddingRegistry",
    "FastEmbedEmbeddingProvider",
    "FastEmbedSparseEmbeddingProvider",
    "GoogleEmbeddingProvider",
    "HuggingFaceEmbeddingProvider",
    "InvalidEmbeddingModelError",
    "MistralEmbeddingProvider",
    "OpenAIEmbeddingBase",
    "QueryResult",
    "RawEmbeddingVectors",
    "SentenceTransformersEmbeddingProvider",
    "SentenceTransformersSparseEmbeddingProvider",
    "SparseEmbedding",
    "SparseEmbeddingModelCapabilities",
    "SparseEmbeddingProvider",
    "StoredEmbeddingVectors",
    "VoyageEmbeddingProvider",
    "get_embedding_registry",
    "get_sparse_embedder",
    "get_text_embedder",
    "load_default_capabilities",
    "load_sparse_capabilities",
)


def __dir__() -> list[str]:
    """List available attributes for the embedding package."""
    return list(__all__)

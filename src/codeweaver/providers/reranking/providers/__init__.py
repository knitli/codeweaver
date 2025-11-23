# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Entrypoint for reranking providers."""

from __future__ import annotations

from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.providers.reranking.providers.base import (
        QueryType,
        RerankingProvider,
        RerankingResult,
    )
    from codeweaver.providers.reranking.providers.bedrock import BedrockRerankingProvider
    from codeweaver.providers.reranking.providers.cohere import CohereRerankingProvider
    from codeweaver.providers.reranking.providers.fastembed import FastEmbedRerankingProvider
    from codeweaver.providers.reranking.providers.sentence_transformers import (
        SentenceTransformersRerankingProvider,
    )
    from codeweaver.providers.reranking.providers.voyage import VoyageRerankingProvider


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "QueryType": (__spec__.parent, "base"),
    "RerankingProvider": (__spec__.parent, "base"),
    "RerankingResult": (__spec__.parent, "base"),
    "BedrockRerankingProvider": (__spec__.parent, "bedrock"),
    "CohereRerankingProvider": (__spec__.parent, "cohere"),
    "FastEmbedRerankingProvider": (__spec__.parent, "fastembed"),
    "SentenceTransformersRerankingProvider": (__spec__.parent, "sentence_transformers"),
    "VoyageRerankingProvider": (__spec__.parent, "voyage"),
})


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the reranking providers package."""
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
    "BedrockRerankingProvider",
    "CohereRerankingProvider",
    "FastEmbedRerankingProvider",
    "QueryType",
    "RerankingProvider",
    "RerankingResult",
    "SentenceTransformersRerankingProvider",
    "VoyageRerankingProvider",
)


def __dir__() -> list[str]:
    return list(__all__)

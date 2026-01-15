# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Entrypoint for reranking providers."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.providers.reranking.providers.base import RerankingProvider
    from codeweaver.providers.reranking.providers.bedrock import BedrockRerankingProvider
    from codeweaver.providers.reranking.providers.cohere import CohereRerankingProvider
    from codeweaver.providers.reranking.providers.fastembed import FastEmbedRerankingProvider
    from codeweaver.providers.reranking.providers.sentence_transformers import (
        SentenceTransformersRerankingProvider,
    )
    from codeweaver.providers.reranking.providers.types import RerankingResult
    from codeweaver.providers.reranking.providers.voyage import VoyageRerankingProvider


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "RerankingProvider": (__spec__.parent, "base"),
    "RerankingResult": (__spec__.parent, "types"),
    "BedrockRerankingProvider": (__spec__.parent, "bedrock"),
    "CohereRerankingProvider": (__spec__.parent, "cohere"),
    "FastEmbedRerankingProvider": (__spec__.parent, "fastembed"),
    "SentenceTransformersRerankingProvider": (__spec__.parent, "sentence_transformers"),
    "VoyageRerankingProvider": (__spec__.parent, "voyage"),
})


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "BedrockRerankingProvider",
    "CohereRerankingProvider",
    "FastEmbedRerankingProvider",
    "RerankingProvider",
    "RerankingResult",
    "SentenceTransformersRerankingProvider",
    "VoyageRerankingProvider",
)


def __dir__() -> list[str]:
    return list(__all__)

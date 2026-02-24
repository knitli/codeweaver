# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Base class for reranking providers."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.providers.reranking.capabilities import (
        RerankingCapabilityResolver,
        RerankingModelCapabilities,
    )
    from codeweaver.providers.reranking.providers import (
        BedrockRerankingProvider,
        CohereRerankingProvider,
        FastEmbedRerankingProvider,
        RerankingProvider,
        RerankingResult,
        SentenceTransformersRerankingProvider,
        VoyageRerankingProvider,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "BedrockRerankingProvider": (__spec__.parent, "providers"),
    "CohereRerankingProvider": (__spec__.parent, "providers"),
    "FastEmbedRerankingProvider": (__spec__.parent, "providers"),
    "RerankingCapabilityResolver": (__spec__.parent, "capabilities"),
    "RerankingModelCapabilities": (__spec__.parent, "capabilities"),
    "RerankingProvider": (__spec__.parent, "providers"),
    "RerankingResult": (__spec__.parent, "providers"),
    "SentenceTransformersRerankingProvider": (__spec__.parent, "providers"),
    "VoyageRerankingProvider": (__spec__.parent, "providers"),
})


__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "BedrockRerankingProvider",
    "CohereRerankingProvider",
    "FastEmbedRerankingProvider",
    "RerankingCapabilityResolver",
    "RerankingModelCapabilities",
    "RerankingProvider",
    "RerankingResult",
    "SentenceTransformersRerankingProvider",
    "VoyageRerankingProvider",
)


def __dir__() -> list[str]:
    """List available attributes in the reranking providers package."""
    return list(__all__)

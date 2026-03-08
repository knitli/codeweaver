# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Entrypoint for CodeWeaver's reranking model capabilities.

Provides access to reranking model capabilities through the dependency injection system.
Use RerankingCapabilityResolver for capability lookup and management.
"""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.providers.reranking.capabilities.alibaba_nlp import (
        AlibabaNlpRerankingCapabilities,
        get_alibaba_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.amazon import (
        AmazonRerankingCapabilities,
        get_amazon_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.baai import (
        BaaiRerankingCapabilities,
        get_baai_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
    from codeweaver.providers.reranking.capabilities.cohere import (
        CohereRerankingCapabilities,
        cohere_max_input,
        get_cohere_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.jinaai import (
        JinaaiRerankingCapabilities,
        get_jinaai_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.mixed_bread_ai import (
        MixedBreadAiRerankingCapabilities,
        get_mixed_bread_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.ms_marco import (
        MsMarcoRerankingCapabilities,
        get_marco_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.qwen import (
        QwenRerankingCapabilities,
        get_qwen_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.resolver import RerankingCapabilityResolver
    from codeweaver.providers.reranking.capabilities.types import (
        PartialRerankingCapabilitiesDict,
        RerankingCapabilitiesDict,
    )
    from codeweaver.providers.reranking.capabilities.voyage import (
        VoyageRerankingCapabilities,
        get_voyage_reranking_capabilities,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "AlibabaNlpRerankingCapabilities": (__spec__.parent, "alibaba_nlp"),
    "AmazonRerankingCapabilities": (__spec__.parent, "amazon"),
    "BaaiRerankingCapabilities": (__spec__.parent, "baai"),
    "CohereRerankingCapabilities": (__spec__.parent, "cohere"),
    "JinaaiRerankingCapabilities": (__spec__.parent, "jinaai"),
    "MixedBreadAiRerankingCapabilities": (__spec__.parent, "mixed_bread_ai"),
    "MsMarcoRerankingCapabilities": (__spec__.parent, "ms_marco"),
    "PartialRerankingCapabilitiesDict": (__spec__.parent, "types"),
    "QwenRerankingCapabilities": (__spec__.parent, "qwen"),
    "RerankingCapabilitiesDict": (__spec__.parent, "types"),
    "RerankingCapabilityResolver": (__spec__.parent, "resolver"),
    "RerankingModelCapabilities": (__spec__.parent, "base"),
    "VoyageRerankingCapabilities": (__spec__.parent, "voyage"),
    "cohere_max_input": (__spec__.parent, "cohere"),
    "get_alibaba_reranking_capabilities": (__spec__.parent, "alibaba_nlp"),
    "get_amazon_reranking_capabilities": (__spec__.parent, "amazon"),
    "get_baai_reranking_capabilities": (__spec__.parent, "baai"),
    "get_cohere_reranking_capabilities": (__spec__.parent, "cohere"),
    "get_jinaai_reranking_capabilities": (__spec__.parent, "jinaai"),
    "get_marco_reranking_capabilities": (__spec__.parent, "ms_marco"),
    "get_mixed_bread_reranking_capabilities": (__spec__.parent, "mixed_bread_ai"),
    "get_qwen_reranking_capabilities": (__spec__.parent, "qwen"),
    "get_voyage_reranking_capabilities": (__spec__.parent, "voyage"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "AlibabaNlpRerankingCapabilities",
    "AmazonRerankingCapabilities",
    "BaaiRerankingCapabilities",
    "CohereRerankingCapabilities",
    "JinaaiRerankingCapabilities",
    "MixedBreadAiRerankingCapabilities",
    "MsMarcoRerankingCapabilities",
    "PartialRerankingCapabilitiesDict",
    "QwenRerankingCapabilities",
    "RerankingCapabilitiesDict",
    "RerankingCapabilityResolver",
    "RerankingModelCapabilities",
    "VoyageRerankingCapabilities",
    "cohere_max_input",
    "get_alibaba_reranking_capabilities",
    "get_amazon_reranking_capabilities",
    "get_baai_reranking_capabilities",
    "get_cohere_reranking_capabilities",
    "get_jinaai_reranking_capabilities",
    "get_marco_reranking_capabilities",
    "get_mixed_bread_reranking_capabilities",
    "get_qwen_reranking_capabilities",
    "get_voyage_reranking_capabilities",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)

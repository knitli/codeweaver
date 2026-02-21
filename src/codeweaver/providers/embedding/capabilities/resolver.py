# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Dependency injection setup for embedding model capabilities.

Provides lazy loading and resolution of embedding model capabilities by model name.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import cast

from codeweaver.core import dependency_provider
from codeweaver.providers import EmbeddingModelCapabilities
from codeweaver.providers.embedding.capabilities.base import SparseEmbeddingModelCapabilities
from codeweaver.providers.types import BaseCapabilityResolver, EmbeddingCapabilityType


@dependency_provider(scope="singleton")
class EmbeddingCapabilityResolver(BaseCapabilityResolver[EmbeddingModelCapabilities]):
    """Resolves embedding model capabilities by model name.

    Lazily loads all capability modules on first access to minimize startup overhead.
    Provides a singleton registry of all embedding model capabilities.
    """

    def __init__(self) -> None:
        """Initialize the capability resolver with empty cache."""
        super().__init__()
        self._sparse_capabilities_by_name: MappingProxyType[
            str, SparseEmbeddingModelCapabilities
        ] = MappingProxyType({})

    def _ensure_loaded(self) -> None:
        """Lazily import all capability modules and build the index."""
        if self._loaded:
            return

        # Import all capability getter functions (triggers @dependency_provider registration)
        from codeweaver.providers.embedding.capabilities.alibaba_nlp import (
            get_alibaba_nlp_embedding_capabilities,
        )
        from codeweaver.providers.embedding.capabilities.amazon import (
            get_amazon_embedding_capabilities,
        )
        from codeweaver.providers.embedding.capabilities.baai import get_baai_embedding_capabilities
        from codeweaver.providers.embedding.capabilities.cohere import (
            get_cohere_embedding_capabilities,
        )
        from codeweaver.providers.embedding.capabilities.google import (
            get_google_embedding_capabilities,
        )
        from codeweaver.providers.embedding.capabilities.ibm_granite import (
            get_ibm_granite_embedding_capabilities,
        )
        from codeweaver.providers.embedding.capabilities.intfloat import (
            get_intfloat_embedding_capabilities,
        )
        from codeweaver.providers.embedding.capabilities.jinaai import (
            get_jinaai_embedding_capabilities,
        )
        from codeweaver.providers.embedding.capabilities.minishlab import (
            get_minishlab_embedding_capabilities,
        )
        from codeweaver.providers.embedding.capabilities.mistral import (
            get_mistral_embedding_capabilities,
        )
        from codeweaver.providers.embedding.capabilities.mixedbread_ai import (
            get_mixedbread_ai_embedding_capabilities,
        )
        from codeweaver.providers.embedding.capabilities.morph import (
            get_morph_embedding_capabilities,
        )
        from codeweaver.providers.embedding.capabilities.nomic_ai import (
            get_nomic_ai_embedding_capabilities,
        )
        from codeweaver.providers.embedding.capabilities.openai import (
            get_openai_embedding_capabilities,
        )
        from codeweaver.providers.embedding.capabilities.qwen import get_qwen_embedding_capabilities
        from codeweaver.providers.embedding.capabilities.sentence_transformers import (
            get_sentence_transformers_embedding_capabilities,
        )
        from codeweaver.providers.embedding.capabilities.snowflake import (
            get_snowflake_embedding_capabilities,
        )
        from codeweaver.providers.embedding.capabilities.thenlper import (
            get_thenlper_embedding_capabilities,
        )
        from codeweaver.providers.embedding.capabilities.voyage import (
            get_voyage_embedding_capabilities,
        )
        from codeweaver.providers.embedding.capabilities.whereisai import (
            get_whereisai_embedding_capabilities,
        )

        # Call each getter to retrieve capabilities and build the lookup index
        temp_capabilities: dict[str, EmbeddingCapabilityType] = {}

        for getter in [
            get_alibaba_nlp_embedding_capabilities,
            get_amazon_embedding_capabilities,
            get_baai_embedding_capabilities,
            get_cohere_embedding_capabilities,
            get_google_embedding_capabilities,
            get_ibm_granite_embedding_capabilities,
            get_intfloat_embedding_capabilities,
            get_jinaai_embedding_capabilities,
            get_minishlab_embedding_capabilities,
            get_mistral_embedding_capabilities,
            get_mixedbread_ai_embedding_capabilities,
            get_morph_embedding_capabilities,
            get_nomic_ai_embedding_capabilities,
            get_openai_embedding_capabilities,
            get_qwen_embedding_capabilities,
            get_sentence_transformers_embedding_capabilities,
            get_snowflake_embedding_capabilities,
            get_thenlper_embedding_capabilities,
            get_voyage_embedding_capabilities,
            get_whereisai_embedding_capabilities,
        ]:
            for cap in getter():
                temp_capabilities[cap.name] = cap

        self._capabilities_by_name = MappingProxyType(
            cast(dict[str, EmbeddingModelCapabilities], temp_capabilities)
        )
        self._loaded = True


@dependency_provider(scope="singleton")
class SparseEmbeddingCapabilityResolver(BaseCapabilityResolver[SparseEmbeddingModelCapabilities]):
    """A capability resolver for sparse embedding models."""

    def __init__(self) -> None:
        """Initialize the capability resolver with empty cache."""
        super().__init__()
        self._capabilities_by_name: MappingProxyType[str, SparseEmbeddingModelCapabilities] = (
            MappingProxyType({})
        )

    def _ensure_loaded(self) -> None:
        """Lazily import all capability modules and build the index."""
        if self._loaded:
            return

        # Import sparse capabilities
        from codeweaver.providers.embedding.capabilities.base import get_sparse_caps

        self._capabilities_by_name = MappingProxyType({
            sparse_cap.name: sparse_cap for sparse_cap in get_sparse_caps()
        })
        self._loaded = True


__all__ = ("EmbeddingCapabilityResolver", "SparseEmbeddingCapabilityResolver")

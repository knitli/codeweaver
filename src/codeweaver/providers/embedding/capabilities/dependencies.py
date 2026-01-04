# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Dependency injection setup for embedding model capabilities.

Provides lazy loading and resolution of embedding model capabilities by model name.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Annotated

from codeweaver.core import Depends, dependency_provider
from codeweaver.providers.types import CapabilityResolver


if TYPE_CHECKING:
    from codeweaver.providers.embedding.capabilities.base import SparseEmbeddingModelCapabilities


@dependency_provider(scope="singleton")
class EmbeddingCapabilityResolver(CapabilityResolver["EmbeddingModelCapabilities"]):
    """Resolves embedding model capabilities by model name.

    Lazily loads all capability modules on first access to minimize startup overhead.
    Provides a singleton registry of all embedding model capabilities.
    """

    def __init__(self) -> None:
        """Initialize the capability resolver with empty cache."""
        super().__init__()
        self._sparse_capabilities_by_name: dict[str, SparseEmbeddingModelCapabilities] = {}

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

        # Import sparse capabilities
        from codeweaver.providers.embedding.capabilities.base import get_sparse_caps
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
                self._capabilities_by_name[cap.name] = cap

        # Index sparse capabilities
        for sparse_cap in get_sparse_caps():
            self._sparse_capabilities_by_name[sparse_cap.name] = sparse_cap

        self._loaded = True

    def resolve_sparse(self, model_name: str) -> SparseEmbeddingModelCapabilities | None:
        """Get sparse capabilities for a specific model name.

        Args:
            model_name: The name of the sparse embedding model.

        Returns:
            The sparse capabilities for the specified model, or None if not found.
        """
        self._ensure_loaded()
        return self._sparse_capabilities_by_name.get(model_name)

    def all_sparse_capabilities(self) -> Sequence[SparseEmbeddingModelCapabilities]:
        """Get all registered sparse embedding model capabilities.

        Returns:
            A sequence of all registered sparse capabilities.
        """
        self._ensure_loaded()
        return tuple(self._sparse_capabilities_by_name.values())

    def all_sparse_model_names(self) -> Sequence[str]:
        """Get all registered sparse embedding model names.

        Returns:
            A sequence of all registered sparse model names.
        """
        self._ensure_loaded()
        return tuple(self._sparse_capabilities_by_name.keys())


# Type alias for dependency injection
type EmbeddingCapabilityResolverDep = Annotated[
    EmbeddingCapabilityResolver, Depends(EmbeddingCapabilityResolver)
]


__all__ = ("EmbeddingCapabilityResolver", "EmbeddingCapabilityResolverDep")

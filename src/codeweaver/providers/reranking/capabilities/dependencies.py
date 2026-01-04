# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Dependency injection setup for reranking model capabilities.

Provides lazy loading and resolution of reranking model capabilities by model name.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from codeweaver.core import Depends, dependency_provider
from codeweaver.providers.types import CapabilityResolver


if TYPE_CHECKING:
    pass


@dependency_provider(scope="singleton")
class RerankingCapabilityResolver(CapabilityResolver["RerankingModelCapabilities"]):
    """Resolves reranking model capabilities by model name.

    Lazily loads all capability modules on first access to minimize startup overhead.
    Provides a singleton registry of all reranking model capabilities.
    """

    def _ensure_loaded(self) -> None:
        """Lazily import all capability modules and build the index."""
        if self._loaded:
            return

        # Import all capability getter functions (triggers @dependency_provider registration)
        from codeweaver.providers.reranking.capabilities.alibaba_nlp import (
            get_alibaba_reranking_capabilities,
        )
        from codeweaver.providers.reranking.capabilities.amazon import (
            get_amazon_reranking_capabilities,
        )
        from codeweaver.providers.reranking.capabilities.baai import get_baai_reranking_capabilities
        from codeweaver.providers.reranking.capabilities.cohere import (
            get_cohere_reranking_capabilities,
        )
        from codeweaver.providers.reranking.capabilities.jinaai import (
            get_jinaai_reranking_capabilities,
        )
        from codeweaver.providers.reranking.capabilities.mixed_bread_ai import (
            get_mixed_bread_reranking_capabilities,
        )
        from codeweaver.providers.reranking.capabilities.ms_marco import (
            get_marco_reranking_capabilities,
        )
        from codeweaver.providers.reranking.capabilities.qwen import get_qwen_reranking_capabilities
        from codeweaver.providers.reranking.capabilities.voyage import (
            get_voyage_reranking_capabilities,
        )

        # Call each getter to retrieve capabilities and build the lookup index
        for getter in [
            get_alibaba_reranking_capabilities,
            get_amazon_reranking_capabilities,
            get_baai_reranking_capabilities,
            get_cohere_reranking_capabilities,
            get_jinaai_reranking_capabilities,
            get_mixed_bread_reranking_capabilities,
            get_marco_reranking_capabilities,
            get_qwen_reranking_capabilities,
            get_voyage_reranking_capabilities,
        ]:
            for cap in getter():
                self._capabilities_by_name[cap.name] = cap

        self._loaded = True


# Type alias for dependency injection
type RerankingCapabilityResolverDep = Annotated[
    RerankingCapabilityResolver, Depends(RerankingCapabilityResolver)
]


__all__ = ("RerankingCapabilityResolver", "RerankingCapabilityResolverDep")

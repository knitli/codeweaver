# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dependency types and factories for SDK clients."""

from __future__ import annotations

from codeweaver.core.types import ProviderLiteralString


async def _resolve_type_from_container(provider_type: type) -> object:
    """Helper function to resolve a provider type from the DI container."""
    from codeweaver.core.di.container import get_container

    container = get_container()
    return await container.resolve(provider_type)


def _get_settings_for_category(category: ProviderLiteralString) -> ProviderCategorySettingsType:
    """Get the settings for a given provider category."""
    from codeweaver.providers.config.providers import (
        AgentProviderSettingsType,
        DataProviderSettingsType,
        EmbeddingProviderSettingsType,
        RerankingProviderSettingsType,
        SparseEmbeddingProviderSettingsType,
        VectorStoreProviderSettingsType,
    )

    if category == "embedding":
        return EmbeddingProviderSettingsType
    if category == "sparse_embedding":
        return SparseEmbeddingProviderSettingsType
    if category == "reranking":
        return RerankingProviderSettingsType
    if category == "data":
        return DataProviderSettingsType
    if category == "vector_store":
        return VectorStoreProviderSettingsType
    if category == "agent":
        return AgentProviderSettingsType
    raise ValueError(f"Unknown provider category: {category}")

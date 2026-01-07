# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dependency injection setup for provider configuration.

This module provides DI type aliases and factory functions for provider settings.
Settings classes are configured via DI to enable:
- Decoupled configuration from provider implementations
- Automatic dependency resolution (e.g., embedding dimensions ← vector store size)
- Ready-built SDK clients injected into providers
- Lazy resolution of provider configurations

## Architecture

Provider settings follow this pattern:
```
User Config (TOML/env vars)
↓
ProviderSettings (root config container)
↓
DI Resolution: EmbeddingProviderSettingsDep = Annotated[EmbeddingProviderSettingsType, depends(...)]
↓
Provider receives: client (SDK), config (settings), embedding_options, query_options
```

Each provider kind has:
- A union type (e.g., EmbeddingProviderSettingsType) discriminating by provider
- A DI type alias (e.g., EmbeddingProviderSettingsDep) for injection
- A factory function (placeholder for now) that resolves settings → SDK client

## Placeholder Status

This module contains intentional placeholders:
- Type aliases without corresponding factories (marked with "⏳ Factory pending")
- Factory functions marked as `...` (to be implemented)
- Import statements for types not yet fully defined

This is expected on the feat/di_monorepo branch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Generic, TypeVar

from codeweaver.core.dependencies import NoneDep
from codeweaver.core.di import depends


# ===========================================================================
# *                   GENERIC SDK CLIENT DEPENDENCY TYPE
# ===========================================================================

# Generic SDK client type variable (e.g., AsyncOpenAI, AsyncClient, etc.)
SDKClientType = TypeVar("SDKClientType")


# ⏳ Factory pending
def _create_sdk_client_dep(client_type: type[SDKClientType] | None = None) -> SDKClientType:  # type: ignore[return-value]
    """Factory for creating SDK clients from configuration.

    This is a placeholder. Implementation will:
    1. Resolve the configured provider type
    2. Get the provider-specific ClientOptions from settings
    3. Instantiate the appropriate SDK client
    4. Return the ready-to-use client

    Args:
        client_type: The SDK client type to create (e.g., AsyncOpenAI).
    """
    ...


type ClientDep[T] = Annotated[T, depends(lambda: None)]
"""Generic type alias for DI injection of SDK clients.

This is a placeholder pattern. When specialized to a concrete client type (e.g.,
ClientDep[AsyncOpenAI]), the DI system will resolve and inject the properly
configured SDK client instance.

Pattern:
    ```python
    def my_provider(
        client: ClientDep[AsyncOpenAI] = INJECTED,
    ) -> None:
        # client is already configured and ready to use
        ...
    ```

Note:
    Factories for specific client types will be defined in provider-specific
    dependencies.py files (e.g., providers/embedding/dependencies.py).
"""


if TYPE_CHECKING:
    # Aggregated union types (discriminated by provider)
    # Specific embedding provider settings
    # Reranking provider settings
    # Vector store provider settings
    # Other provider settings
    from codeweaver.providers.config.kinds import (
        AzureEmbeddingProviderSettings,
        BedrockEmbeddingProviderSettings,
        BedrockRerankingProviderSettings,
        FastEmbedEmbeddingProviderSettings,
        FastEmbedRerankingProviderSettings,
        FastEmbedSparseEmbeddingProviderSettings,
        QdrantVectorStoreProviderSettings,
    )

    # Root provider settings
    from codeweaver.providers.config.providers import (
        AgentProviderSettingsType,
        DataProviderSettingsType,
        EmbeddingProviderSettingsType,
        ProviderSettings,
        RerankingProviderSettingsType,
        SparseEmbeddingProviderSettingsType,
        VectorStoreProviderSettingsType,
    )


# ===========================================================================
# *              EMBEDDING PROVIDER SETTINGS - DI TYPE ALIASES
# ===========================================================================

# ⏳ Factory pending
def _create_embedding_provider_settings_dep() -> EmbeddingProviderSettingsType:  # type: ignore[name-defined]
    """Factory for creating embedding provider settings from configuration.

    This is a placeholder. Implementation will:
    1. Resolve the active embedding provider from root settings
    2. Create the appropriate provider-specific settings class
    3. Inject any interdependent values (e.g., vector dimensions)
    4. Return ready-to-use settings
    """
    ...


type EmbeddingProviderSettingsDep = Annotated[
    EmbeddingProviderSettingsType,  # type: ignore[name-defined]
    depends(_create_embedding_provider_settings_dep),
]
"""Type alias for DI injection of embedding provider settings.

When a function or class requests this type with = INJECTED, the DI container
will call the factory to resolve the appropriate embedding settings based on
the current configuration.

Example:
    ```python
    def create_embedding(
        settings: EmbeddingProviderSettingsDep = INJECTED
    ) -> EmbeddingProvider:
        # settings is already configured and ready to use
        return EmbeddingProvider(settings)
    ```
"""


# ⏳ Factory pending
def _create_azure_embedding_settings_dep() -> AzureEmbeddingProviderSettings:  # type: ignore[name-defined]
    """Factory for Azure-specific embedding provider settings."""
    ...


type AzureEmbeddingProviderSettingsDep = Annotated[
    AzureEmbeddingProviderSettings,  # type: ignore[name-defined]
    depends(_create_azure_embedding_settings_dep),
]
"""Type alias for DI injection of Azure embedding provider settings."""


# ⏳ Factory pending
def _create_bedrock_embedding_settings_dep() -> BedrockEmbeddingProviderSettings:  # type: ignore[name-defined]
    """Factory for Bedrock-specific embedding provider settings."""
    ...


type BedrockEmbeddingProviderSettingsDep = Annotated[
    BedrockEmbeddingProviderSettings,  # type: ignore[name-defined]
    depends(_create_bedrock_embedding_settings_dep),
]
"""Type alias for DI injection of Bedrock embedding provider settings."""


# ⏳ Factory pending
def _create_fastembed_embedding_settings_dep() -> FastEmbedEmbeddingProviderSettings:  # type: ignore[name-defined]
    """Factory for FastEmbed embedding provider settings."""
    ...


type FastEmbedEmbeddingProviderSettingsDep = Annotated[
    FastEmbedEmbeddingProviderSettings,  # type: ignore[name-defined]
    depends(_create_fastembed_embedding_settings_dep),
]
"""Type alias for DI injection of FastEmbed embedding provider settings."""


# ===========================================================================
# *            SPARSE EMBEDDING PROVIDER SETTINGS - DI TYPE ALIASES
# ===========================================================================

# ⏳ Factory pending
def _create_sparse_embedding_provider_settings_dep() -> SparseEmbeddingProviderSettingsType:  # type: ignore[name-defined]
    """Factory for creating sparse embedding provider settings."""
    ...


type SparseEmbeddingProviderSettingsDep = Annotated[
    SparseEmbeddingProviderSettingsType,  # type: ignore[name-defined]
    depends(_create_sparse_embedding_provider_settings_dep),
]
"""Type alias for DI injection of sparse embedding provider settings."""


# ⏳ Factory pending
def _create_fastembed_sparse_embedding_settings_dep() -> FastEmbedSparseEmbeddingProviderSettings:  # type: ignore[name-defined]
    """Factory for FastEmbed sparse embedding provider settings."""
    ...


type FastEmbedSparseEmbeddingProviderSettingsDep = Annotated[
    FastEmbedSparseEmbeddingProviderSettings,  # type: ignore[name-defined]
    depends(_create_fastembed_sparse_embedding_settings_dep),
]
"""Type alias for DI injection of FastEmbed sparse embedding provider settings."""


# ===========================================================================
# *              RERANKING PROVIDER SETTINGS - DI TYPE ALIASES
# ===========================================================================

# ⏳ Factory pending
def _create_reranking_provider_settings_dep() -> RerankingProviderSettingsType:  # type: ignore[name-defined]
    """Factory for creating reranking provider settings from configuration."""
    ...


type RerankingProviderSettingsDep = Annotated[
    RerankingProviderSettingsType,  # type: ignore[name-defined]
    depends(_create_reranking_provider_settings_dep),
]
"""Type alias for DI injection of reranking provider settings."""


# ⏳ Factory pending
def _create_fastembed_reranking_settings_dep() -> FastEmbedRerankingProviderSettings:  # type: ignore[name-defined]
    """Factory for FastEmbed reranking provider settings."""
    ...


type FastEmbedRerankingProviderSettingsDep = Annotated[
    FastEmbedRerankingProviderSettings,  # type: ignore[name-defined]
    depends(_create_fastembed_reranking_settings_dep),
]
"""Type alias for DI injection of FastEmbed reranking provider settings."""


# ⏳ Factory pending
def _create_bedrock_reranking_settings_dep() -> BedrockRerankingProviderSettings:  # type: ignore[name-defined]
    """Factory for Bedrock reranking provider settings."""
    ...


type BedrockRerankingProviderSettingsDep = Annotated[
    BedrockRerankingProviderSettings,  # type: ignore[name-defined]
    depends(_create_bedrock_reranking_settings_dep),
]
"""Type alias for DI injection of Bedrock reranking provider settings."""


# ===========================================================================
# *             VECTOR STORE PROVIDER SETTINGS - DI TYPE ALIASES
# ===========================================================================

# ⏳ Factory pending
def _create_vector_store_provider_settings_dep() -> VectorStoreProviderSettingsType:  # type: ignore[name-defined]
    """Factory for creating vector store provider settings from configuration."""
    ...


type VectorStoreProviderSettingsDep = Annotated[
    VectorStoreProviderSettingsType,  # type: ignore[name-defined]
    depends(_create_vector_store_provider_settings_dep),
]
"""Type alias for DI injection of vector store provider settings."""


# ⏳ Factory pending
def _create_qdrant_vector_store_settings_dep() -> QdrantVectorStoreProviderSettings:  # type: ignore[name-defined]
    """Factory for Qdrant vector store provider settings."""
    ...


type QdrantVectorStoreProviderSettingsDep = Annotated[
    QdrantVectorStoreProviderSettings,  # type: ignore[name-defined]
    depends(_create_qdrant_vector_store_settings_dep),
]
"""Type alias for DI injection of Qdrant vector store provider settings."""


# ===========================================================================
# *                  DATA PROVIDER SETTINGS - DI TYPE ALIASES
# ===========================================================================

# ⏳ Factory pending
def _create_data_provider_settings_dep() -> DataProviderSettingsType:  # type: ignore[name-defined]
    """Factory for creating data provider settings from configuration."""
    ...


type DataProviderSettingsDep = Annotated[
    DataProviderSettingsType,  # type: ignore[name-defined]
    depends(_create_data_provider_settings_dep),
]
"""Type alias for DI injection of data provider settings."""


# ===========================================================================
# *                 AGENT PROVIDER SETTINGS - DI TYPE ALIASES
# ===========================================================================

# ⏳ Factory pending
def _create_agent_provider_settings_dep() -> AgentProviderSettingsType:  # type: ignore[name-defined]
    """Factory for creating agent provider settings from configuration."""
    ...


type AgentProviderSettingsDep = Annotated[
    AgentProviderSettingsType,  # type: ignore[name-defined]
    depends(_create_agent_provider_settings_dep),
]
"""Type alias for DI injection of agent provider settings."""


# ===========================================================================
# *                    ROOT PROVIDER SETTINGS - DI TYPE ALIAS
# ===========================================================================

# ⏳ Factory pending
def _create_provider_settings_dep() -> ProviderSettings:  # type: ignore[name-defined]
    """Factory for creating root provider settings from configuration.

    This is the entry point for provider configuration DI. It:
    1. Loads the [provider] section from settings/environment
    2. Creates the root ProviderSettings container
    3. Resolves all embedded provider configurations
    """
    ...


type ProviderSettingsDep = Annotated[
    ProviderSettings,  # type: ignore[name-defined]
    depends(_create_provider_settings_dep),
]
"""Type alias for DI injection of root provider settings.

This is the top-level provider configuration. All provider-specific settings
are nested within this container. Requesting this type triggers resolution of
all configured providers.

Example:
    ```python
    async def initialize_providers(
        provider_settings: ProviderSettingsDep = INJECTED
    ) -> None:
        # provider_settings contains all configured providers
        embedding = provider_settings.embedding
        vector_store = provider_settings.vector_store
    ```
"""


# ===========================================================================
# *                            MODULE EXPORTS
# ===========================================================================

__all__ = (
    # Generic client dependency
    "ClientDep",
    "NoneDep",
    # Root provider settings
    "ProviderSettingsDep",
    # Embedding settings
    "EmbeddingProviderSettingsDep",
    "AzureEmbeddingProviderSettingsDep",
    "BedrockEmbeddingProviderSettingsDep",
    "FastEmbedEmbeddingProviderSettingsDep",
    # Sparse embedding settings
    "SparseEmbeddingProviderSettingsDep",
    "FastEmbedSparseEmbeddingProviderSettingsDep",
    # Reranking settings
    "RerankingProviderSettingsDep",
    "FastEmbedRerankingProviderSettingsDep",
    "BedrockRerankingProviderSettingsDep",
    # Vector store settings
    "VectorStoreProviderSettingsDep",
    "QdrantVectorStoreProviderSettingsDep",
    # Data provider settings
    "DataProviderSettingsDep",
    # Agent provider settings
    "AgentProviderSettingsDep",
)

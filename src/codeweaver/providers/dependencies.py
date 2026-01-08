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

from typing import TYPE_CHECKING, Annotated, Any

from codeweaver.core.dependencies import NoneDep
from codeweaver.core.di import depends
from codeweaver.providers.reranking.capabilities.resolver import RerankingCapabilityResolver


if TYPE_CHECKING:
    from codeweaver.core import BaseCodeWeaverSettings


def _resolve_global_settings() -> BaseCodeWeaverSettings:
    """Resolve the global CodeWeaver settings.

    Because nearly all provider dependencies ultimately depend on global settings,
    this function ensure that the global settings are loaded and available for other
    provider factories and dependencies.
    
    Note: This is imported for backwards compatibility. The canonical way to inject
    settings is now via SettingsDep from core.dependencies:
        from codeweaver.core.dependencies import SettingsDep
        
    Or directly via the container:
        from codeweaver.core.types.settings_model import BaseCodeWeaverSettings
        settings: BaseCodeWeaverSettings = INJECTED
    """
    from codeweaver.core.dependencies import bootstrap_settings
    
    return bootstrap_settings()


# ===========================================================================
# *                    CLIENT FACTORY (SDK CLIENT CREATION)
# ===========================================================================
#
# Universal client factory creates SDK clients (AsyncOpenAI, VoyageAI, etc.)
# based on the configured provider type. Since settings are bootstrapped before
# DI registration, pydantic discriminators already handle config typing, so we
# just need ONE factory that switches on provider type.
#
# Factory design:
# 1. Injects primary embedding config (EmbeddingProviderSettingsDep)
# 2. Extracts client options from config.client_options
# 3. Switches on config.provider to instantiate the right SDK client
# 4. Returns ready-to-use client
#
# Implementation Note: This factory is registered with @dependency_provider
# at module initialization to ensure it's available when providers are created.


def _create_embedding_client() -> Any:  # AsyncOpenAI
    """Universal client factory for all embedding providers.
    
    This factory creates SDK clients based on the provider type in the config.
    It supports:
    - OpenAI-compatible: OpenAI, Azure, Ollama, Fireworks, Together, GitHub, Heroku
    - Voyage AI
    - Cohere (including Azure Cohere, Heroku Cohere)
    - Mistral
    - Google Generative AI
    - AWS Bedrock
    - HuggingFace Inference
    - FastEmbed
    - Sentence Transformers
    
    Returns:
        Configured SDK client instance appropriate for the provider type
        
    Raises:
        ConfigurationError: If config is missing, provider unsupported, or SDK not installed
    """
    from codeweaver.core import ConfigurationError, Provider
    from codeweaver.core.di import INJECTED

    config: EmbeddingProviderSettingsType = INJECTED  # type: ignore[name-defined]

    if not config or not config.client_options:
        raise ConfigurationError(
            "Client factory requires config with client_options",
            details={"config_present": config is not None},
        )
    
    client_options = config.client_options.as_settings()
    
    # Switch on provider type to create appropriate SDK client
    match config.provider:
        # OpenAI-compatible providers (AsyncOpenAI)
        case (Provider.OPENAI | Provider.AZURE | Provider.OLLAMA | 
              Provider.FIREWORKS | Provider.TOGETHER | Provider.GITHUB | 
              Provider.HEROKU):
            try:
                from openai import AsyncOpenAI
                return AsyncOpenAI(**client_options)
            except ImportError as e:
                raise ConfigurationError(
                    f'Please install the `openai` package to use {config.provider}: '
                    'pip install "code-weaver[openai]"'
                ) from e
        
        # Voyage AI
        case Provider.VOYAGE:
            try:
                from voyageai import AsyncClient as VoyageAsyncClient
                return VoyageAsyncClient(**client_options)
            except ImportError as e:
                raise ConfigurationError(
                    'Please install the `voyageai` package: pip install "code-weaver[voyage]"'
                ) from e
        
        # Cohere (supports Azure Cohere, Heroku Cohere)
        case Provider.COHERE:
            try:
                from cohere import AsyncClientV2 as CohereAsyncClient
                return CohereAsyncClient(**client_options)
            except ImportError as e:
                raise ConfigurationError(
                    'Please install the `cohere` package: pip install "code-weaver[cohere]"'
                ) from e
        
        # Mistral
        case Provider.MISTRAL:
            try:
                from mistralai import Mistral
                return Mistral(**client_options)
            except ImportError as e:
                raise ConfigurationError(
                    'Please install the `mistralai` package: pip install "code-weaver[mistral]"'
                ) from e
        
        # Google Generative AI
        case Provider.GOOGLE:
            try:
                import google.genai as genai
                return genai.Client(**client_options)
            except ImportError as e:
                raise ConfigurationError(
                    'Please install the `google-genai` package: pip install "code-weaver[google]"'
                ) from e
        
        # AWS Bedrock
        case Provider.BEDROCK:
            try:
                from boto3 import client as boto3_client
                return boto3_client('bedrock-runtime', **client_options)
            except ImportError as e:
                raise ConfigurationError(
                    'Please install the `boto3` package: pip install "code-weaver[bedrock]"'
                ) from e
        
        # HuggingFace Inference
        case Provider.HUGGINGFACE_INFERENCE:
            try:
                from huggingface_hub import AsyncInferenceClient
                return AsyncInferenceClient(**client_options)
            except ImportError as e:
                raise ConfigurationError(
                    'Please install the `huggingface-hub` package: '
                    'pip install "code-weaver[huggingface]"'
                ) from e
        
        # FastEmbed
        case Provider.FASTEMBED:
            try:
                from fastembed import TextEmbedding
                return TextEmbedding(**client_options)
            except ImportError as e:
                raise ConfigurationError(
                    'Please install the `fastembed` package: pip install "code-weaver[fastembed]"'
                ) from e
        
        # Sentence Transformers
        case Provider.SENTENCE_TRANSFORMERS:
            try:
                from sentence_transformers import SentenceTransformer
                return SentenceTransformer(**client_options)
            except ImportError as e:
                raise ConfigurationError(
                    'Please install the `sentence-transformers` package: '
                    'pip install "code-weaver[sentence-transformers]"'
                ) from e
        
        # Unsupported provider
        case _:
            raise ConfigurationError(
                f"No client factory implementation for provider: {config.provider}",
                details={
                    "provider": str(config.provider),
                    "config_type": type(config).__name__,
                },
                suggestions=[
                    "Check that the provider is supported for embedding",
                    "Verify the config.provider value is correct",
                ],
            )


# REMOVE OLD INDIVIDUAL FACTORIES - they are replaced by _create_embedding_client above
# The following comment is a marker for deletion
# Voyage AI
def _create_voyage_client_DEPRECATED() -> Any:  # voyageai.AsyncClient
    """Factory for Voyage AI client.

    Returns:
        voyageai.AsyncClient: Configured Voyage client
    """
    from codeweaver.core.di import INJECTED

    config: EmbeddingProviderSettingsType = INJECTED  # type: ignore[name-defined]

    if not config or not config.client_options:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            "Voyage client factory requires config with client_options",
            details={"config_present": config is not None},
        )

    try:
        from voyageai import AsyncClient as VoyageAsyncClient

        client_options = config.client_options.as_settings()
        return VoyageAsyncClient(**client_options)
    except ImportError as e:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            'Please install the `voyageai` package: pip install "code-weaver[voyage]"'
        ) from e


# Cohere (also supports Azure Cohere and Heroku Cohere)
def _create_cohere_client() -> Any:  # cohere.AsyncClientV2
    """Factory for Cohere client - supports Cohere, Azure Cohere, and Heroku Cohere.

    Returns:
        cohere.AsyncClientV2: Configured Cohere client
    """
    from codeweaver.core.di import INJECTED

    config: EmbeddingProviderSettingsType = INJECTED  # type: ignore[name-defined]

    if not config or not config.client_options:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            "Cohere client factory requires config with client_options",
            details={"config_present": config is not None},
        )

    try:
        from cohere import AsyncClientV2 as CohereAsyncClient

        client_options = config.client_options.as_settings()
        return CohereAsyncClient(**client_options)
    except ImportError as e:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            'Please install the `cohere` package: pip install "code-weaver[cohere]"'
        ) from e


# Mistral
def _create_mistral_client() -> Any:  # Mistral
    """Factory for Mistral client.

    Returns:
        Mistral: Configured Mistral client
    """
    from codeweaver.core.di import INJECTED

    config: EmbeddingProviderSettingsType = INJECTED  # type: ignore[name-defined]

    if not config or not config.client_options:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            "Mistral client factory requires config with client_options",
            details={"config_present": config is not None},
        )

    try:
        from mistralai import Mistral

        client_options = config.client_options.as_settings()
        return Mistral(**client_options)
    except ImportError as e:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            'Please install the `mistralai` package: pip install "code-weaver[mistral]"'
        ) from e


# Google
def _create_google_client() -> Any:  # genai.Client
    """Factory for Google Generative AI client.

    Returns:
        genai.Client: Configured Google client
    """
    from codeweaver.core.di import INJECTED

    config: EmbeddingProviderSettingsType = INJECTED  # type: ignore[name-defined]

    if not config or not config.client_options:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            "Google client factory requires config with client_options",
            details={"config_present": config is not None},
        )

    try:
        import google.genai as genai

        client_options = config.client_options.as_settings()
        return genai.Client(**client_options)
    except ImportError as e:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            'Please install the `google-genai` package: pip install "code-weaver[google]"'
        ) from e


# AWS Bedrock
def _create_bedrock_client() -> Any:  # BedrockRuntimeClient
    """Factory for AWS Bedrock Runtime client.

    Returns:
        BedrockRuntimeClient: Configured Bedrock client
    """
    from codeweaver.core.di import INJECTED

    config: EmbeddingProviderSettingsType = INJECTED  # type: ignore[name-defined]

    if not config or not config.client_options:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            "Bedrock client factory requires config with client_options",
            details={"config_present": config is not None},
        )

    try:
        from boto3 import client as boto3_client

        client_options = config.client_options.as_settings()
        return boto3_client('bedrock-runtime', **client_options)
    except ImportError as e:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            'Please install the `boto3` package: pip install "code-weaver[bedrock]"'
        ) from e


# HuggingFace
def _create_huggingface_client() -> Any:  # AsyncInferenceClient
    """Factory for HuggingFace Inference client.

    Returns:
        AsyncInferenceClient: Configured HuggingFace client
    """
    from codeweaver.core.di import INJECTED

    config: EmbeddingProviderSettingsType = INJECTED  # type: ignore[name-defined]

    if not config or not config.client_options:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            "HuggingFace client factory requires config with client_options",
            details={"config_present": config is not None},
        )

    try:
        from huggingface_hub import AsyncInferenceClient

        client_options = config.client_options.as_settings()
        return AsyncInferenceClient(**client_options)
    except ImportError as e:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            'Please install the `huggingface-hub` package: pip install "code-weaver[huggingface]"'
        ) from e


# FastEmbed
def _create_fastembed_client() -> Any:  # TextEmbedding
    """Factory for FastEmbed TextEmbedding client.

    Returns:
        TextEmbedding: Configured FastEmbed client
    """
    from codeweaver.core.di import INJECTED

    config: EmbeddingProviderSettingsType = INJECTED  # type: ignore[name-defined]

    if not config or not config.client_options:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            "FastEmbed client factory requires config with client_options",
            details={"config_present": config is not None},
        )

    try:
        from fastembed import TextEmbedding

        client_options = config.client_options.as_settings()
        return TextEmbedding(**client_options)
    except ImportError as e:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            'Please install the `fastembed` package: pip install "code-weaver[fastembed]"'
        ) from e


# FastEmbed Sparse
def _create_fastembed_sparse_client() -> Any:  # SparseTextEmbedding
    """Factory for FastEmbed SparseTextEmbedding client.

    Returns:
        SparseTextEmbedding: Configured FastEmbed sparse client
    """
    from codeweaver.core.di import INJECTED

    config: SparseEmbeddingProviderSettingsType = INJECTED  # type: ignore[name-defined]

    if not config or not config.client_options:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            "FastEmbed sparse client factory requires config with client_options",
            details={"config_present": config is not None},
        )

    try:
        from fastembed import SparseTextEmbedding

        client_options = config.client_options.as_settings()
        return SparseTextEmbedding(**client_options)
    except ImportError as e:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            'Please install the `fastembed` package: pip install "code-weaver[fastembed]"'
        ) from e


# SentenceTransformers
def _create_sentence_transformers_client() -> Any:  # SentenceTransformer
    """Factory for SentenceTransformers client.

    Returns:
        SentenceTransformer: Configured SentenceTransformers client
    """
    from codeweaver.core.di import INJECTED

    config: EmbeddingProviderSettingsType = INJECTED  # type: ignore[name-defined]

    if not config or not config.client_options:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            "SentenceTransformers client factory requires config with client_options",
            details={"config_present": config is not None},
        )

    try:
        from sentence_transformers import SentenceTransformer

        client_options = config.client_options.as_settings()
        return SentenceTransformer(**client_options)
    except ImportError as e:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            'Please install the `sentence-transformers` package: pip install "code-weaver[sentence-transformers]"'
        ) from e


# SentenceTransformers Sparse
def _create_sentence_transformers_sparse_client() -> Any:  # SparseEncoder
    """Factory for SentenceTransformers SparseEncoder client.

    Returns:
        SparseEncoder: Configured SentenceTransformers sparse client
    """
    from codeweaver.core.di import INJECTED

    config: SparseEmbeddingProviderSettingsType = INJECTED  # type: ignore[name-defined]

    if not config or not config.client_options:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            "SentenceTransformers sparse client factory requires config with client_options",
            details={"config_present": config is not None},
        )

    try:
        from sentence_transformers import SparseEncoder

        client_options = config.client_options.as_settings()
        return SparseEncoder(**client_options)
    except ImportError as e:
        from codeweaver.core import ConfigurationError
        raise ConfigurationError(
            'Please install `sentence-transformers` with sparse support: pip install "code-weaver[sentence-transformers]"'
        ) from e


# Universal client dependency type for all embedding providers
type ClientDep[T] = Annotated[T, depends(_create_embedding_client)]
"""Universal client dependency type for embedding providers.

This type alias provides DI injection of SDK clients based on the configured provider.
The type parameter T should match the expected SDK client type (e.g., AsyncOpenAI,
VoyageAsyncClient, etc.).

Pattern:
    ```python
    class OpenAIEmbeddingProvider:
        def __init__(
            self,
            client: ClientDep[AsyncOpenAI] = INJECTED,
            config: EmbeddingConfigDep = INJECTED,
        ):
            self.client = client  # Already configured AsyncOpenAI instance
            self.config = config
    ```

Type Safety:
    The type parameter provides type hints for static analysis, while the actual
    client type is determined at runtime based on config.provider.
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
    from codeweaver.providers.embedding.capabilities.resolver import EmbeddingCapabilityResolver


# ===========================================================================
# *              EMBEDDING PROVIDER SETTINGS - DI TYPE ALIASES
# ===========================================================================


def _create_embedding_provider_settings_dep():
    """Factory for creating PRIMARY embedding provider config from settings.
    
    Returns the first (primary) embedding config from settings.provider.embedding.
    For all configs (primary + backups), inject Sequence[EmbeddingConfigT] instead.
    
    Note: This factory should be decorated with @dependency_provider at module init.
    """
    from codeweaver.core.types.settings_model import BaseCodeWeaverSettings
    from codeweaver.core.di import INJECTED
    
    settings: BaseCodeWeaverSettings = INJECTED
    return settings.provider.embedding[0] if settings.provider.embedding else None


def _create_all_embedding_configs():
    """Factory for creating ALL embedding configs (primary + backups) from settings.
    
    Returns a sequence of all configured embedding providers.
    Use this when you need access to backup providers, not just the primary.
    
    Note: This factory should be decorated with @dependency_provider at module init.
    """
    from codeweaver.core.types.settings_model import BaseCodeWeaverSettings
    from codeweaver.core.di import INJECTED
    
    settings: BaseCodeWeaverSettings = INJECTED
    return settings.provider.embedding if settings.provider.embedding else tuple()


type EmbeddingProviderSettingsDep = Annotated[


# Collection type for all embedding configs (primary + backups)
if TYPE_CHECKING:
    from typing import Sequence
    from codeweaver.providers.config.embedding import EmbeddingConfigT

type AllEmbeddingConfigsDep = Annotated[
    Sequence["EmbeddingConfigT"],  # type: ignore[name-defined]
    depends(_create_all_embedding_configs),
]
"""Type alias for DI injection of ALL embedding configs (primary + backups).

Use this when you need access to backup providers, not just the primary.

Example:
    ```python
    def handle_failover(
        all_configs: AllEmbeddingConfigsDep = INJECTED
    ) -> None:
        primary = all_configs[0]
        backups = all_configs[1:]
        # Implement failover logic...
    ```
"""
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


type AzureEmbeddingProviderSettingsDep = Annotated[
    AzureEmbeddingProviderSettings,  # type: ignore[name-defined]
    depends(_create_azure_embedding_settings_dep),
]
"""Type alias for DI injection of Azure embedding provider settings."""


# ⏳ Factory pending
def _create_bedrock_embedding_settings_dep() -> BedrockEmbeddingProviderSettings:  # type: ignore[name-defined]
    """Factory for Bedrock-specific embedding provider settings."""


type BedrockEmbeddingProviderSettingsDep = Annotated[
    BedrockEmbeddingProviderSettings,  # type: ignore[name-defined]
    depends(_create_bedrock_embedding_settings_dep),
]
"""Type alias for DI injection of Bedrock embedding provider settings."""


# ⏳ Factory pending
def _create_fastembed_embedding_settings_dep() -> FastEmbedEmbeddingProviderSettings:  # type: ignore[name-defined]
    """Factory for FastEmbed embedding provider settings."""


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


type SparseEmbeddingProviderSettingsDep = Annotated[
    SparseEmbeddingProviderSettingsType,  # type: ignore[name-defined]
    depends(_create_sparse_embedding_provider_settings_dep),
]
"""Type alias for DI injection of sparse embedding provider settings."""


# ⏳ Factory pending
def _create_fastembed_sparse_embedding_settings_dep() -> FastEmbedSparseEmbeddingProviderSettings:  # type: ignore[name-defined]
    """Factory for FastEmbed sparse embedding provider settings."""


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


type RerankingProviderSettingsDep = Annotated[
    RerankingProviderSettingsType,  # type: ignore[name-defined]
    depends(_create_reranking_provider_settings_dep),
]
"""Type alias for DI injection of reranking provider settings."""


# Type alias for dependency injection
type EmbeddingCapabilityResolverDep = Annotated[
    EmbeddingCapabilityResolver,
    depends(EmbeddingCapabilityResolver, use_cache=True, scope="singleton"),
]


# Type alias for dependency injection
type RerankingCapabilityResolverDep = Annotated[
    RerankingCapabilityResolver, depends(RerankingCapabilityResolver)
]


# ⏳ Factory pending
def _create_fastembed_reranking_settings_dep() -> FastEmbedRerankingProviderSettings:  # type: ignore[name-defined]
    """Factory for FastEmbed reranking provider settings."""


type FastEmbedRerankingProviderSettingsDep = Annotated[
    FastEmbedRerankingProviderSettings,  # type: ignore[name-defined]
    depends(_create_fastembed_reranking_settings_dep),
]
"""Type alias for DI injection of FastEmbed reranking provider settings."""


# ⏳ Factory pending
def _create_bedrock_reranking_settings_dep() -> BedrockRerankingProviderSettings:  # type: ignore[name-defined]
    """Factory for Bedrock reranking provider settings."""


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


type VectorStoreProviderSettingsDep = Annotated[
    VectorStoreProviderSettingsType,  # type: ignore[name-defined]
    depends(_create_vector_store_provider_settings_dep),
]
"""Type alias for DI injection of vector store provider settings."""


# ⏳ Factory pending
def _create_qdrant_vector_store_settings_dep() -> QdrantVectorStoreProviderSettings:  # type: ignore[name-defined]
    """Factory for Qdrant vector store provider settings."""


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
# *                    PROVIDER FACTORIES (WITH BACKUP SUPPORT)
# ===========================================================================
#
# These factories create actual provider instances (not just configs).
# They integrate with backup_factory.py to handle primary + backup discrimination.
#
# Pattern:
#   1. Get all configs from settings (primary + backups)
#   2. For each config after first, wrap class with create_backup_class()
#   3. Instantiate providers with resolved dependencies (client, caps, config)
#   4. Return as Sequence[Provider] for DI resolution
#
# Implementation Note: This is the core integration point between:
# - Settings system (config collection)
# - Client factories (SDK clients)
# - Capability resolvers (model capabilities)
# - Backup factory (type discrimination)


def _get_provider_class_for_config(config: EmbeddingConfigT) -> type:  # type: ignore[name-defined]
    """Map embedding config to its provider class.

    Args:
        config: The embedding configuration instance

    Returns:
        The provider class for this config type

    Raises:
        ConfigurationError: If no provider class found for config type
    """
    from codeweaver.core import ConfigurationError, Provider

    # Import provider classes
    from codeweaver.providers.embedding.providers import (
        BedrockEmbeddingProvider,
        CohereEmbeddingProvider,
        FastEmbedEmbeddingProvider,
        GoogleEmbeddingProvider,
        HuggingFaceEmbeddingProvider,
        MistralEmbeddingProvider,
        SentenceTransformersEmbeddingProvider,
        VoyageEmbeddingProvider,
    )
    from codeweaver.providers.embedding.providers.openai_factory import OpenAIEmbeddingBase

    # Map provider enum to provider class
    provider_map = {
        Provider.OPENAI: OpenAIEmbeddingBase,
        Provider.AZURE: OpenAIEmbeddingBase,
        Provider.OLLAMA: OpenAIEmbeddingBase,
        Provider.FIREWORKS: OpenAIEmbeddingBase,
        Provider.TOGETHER: OpenAIEmbeddingBase,
        Provider.GITHUB: OpenAIEmbeddingBase,
        Provider.HEROKU: OpenAIEmbeddingBase,
        Provider.VOYAGE: VoyageEmbeddingProvider,
        Provider.COHERE: CohereEmbeddingProvider,
        Provider.MISTRAL: MistralEmbeddingProvider,
        Provider.GOOGLE: GoogleEmbeddingProvider,
        Provider.BEDROCK: BedrockEmbeddingProvider,
        Provider.HUGGINGFACE_INFERENCE: HuggingFaceEmbeddingProvider,
        Provider.FASTEMBED: FastEmbedEmbeddingProvider,
        Provider.SENTENCE_TRANSFORMERS: SentenceTransformersEmbeddingProvider,
    }

    provider_cls = provider_map.get(config.provider)
    if not provider_cls:
        raise ConfigurationError(
            f"No provider class found for provider: {config.provider}",
            details={
                "provider": str(config.provider),
                "config_type": type(config).__name__,
                "available_providers": list(provider_map.keys()),
            },
            suggestions=[
                "Check that the provider is supported",
                "Verify the config.provider value is correct",
                "Ensure the provider module is imported",
            ],
        )

    return provider_cls


def _create_client_for_config(config: EmbeddingConfigT) -> Any:  # type: ignore[name-defined]
    """Create SDK client for the given config.

    This function wraps the universal client factory. Since we have a single
    factory that handles all provider types, we just delegate to it.

    Args:
        config: The embedding configuration instance (unused, kept for compatibility)

    Returns:
        The initialized SDK client

    Raises:
        ConfigurationError: If provider unsupported or SDK not installed
    """
    # Delegate to the universal client factory
    # The factory will use DI to inject the config
    return _create_embedding_client()


def _instantiate_provider(
    provider_cls: type,
    config: EmbeddingConfigT,  # type: ignore[name-defined]
    client: Any,
    caps: Any,
) -> Any:
    """Instantiate a provider with the given dependencies.

    Args:
        provider_cls: The provider class to instantiate
        config: The embedding configuration
        client: The SDK client instance
        caps: The model capabilities

    Returns:
        The initialized provider instance
    """
    # Instantiate provider with dependencies
    # Most providers expect: client, config, caps
    return provider_cls(
        client=client,
        config=config,
        caps=caps,
    )


async def create_all_embedding_providers() -> tuple[Any, ...]:
    """Factory for creating ALL embedding providers (primary + backups).

    This is the main provider factory that:
    1. Gets all embedding configs from settings (primary + backups)
    2. Creates backup classes for non-primary providers
    3. Resolves clients and capabilities for each provider
    4. Instantiates all providers with proper dependencies
    5. Returns as tuple for DI resolution

    Integration points:
    - backup_factory.create_backup_class() for type discrimination
    - Settings resolution for config collection
    - Client factories for SDK clients
    - Capability resolvers for model capabilities

    Returns:
        Tuple of all configured embedding providers (primary first, then backups)
    """
    from codeweaver.core.di import INJECTED
    from codeweaver.providers.backup_factory import create_backup_class

    # Inject dependencies
    configs: AllEmbeddingConfigsDep = INJECTED  # type: ignore[name-defined]
    caps_resolver: EmbeddingCapabilityResolverDep = INJECTED

    if not configs:
        return tuple()

    providers = []

    for i, config in enumerate(configs):
        is_backup = i > 0

        # Get provider class for this config
        provider_cls = _get_provider_class_for_config(config)

        # Wrap with backup class if this is a backup provider
        if is_backup:
            provider_cls = create_backup_class(provider_cls)

        # Create client for this config
        client = _create_client_for_config(config)

        # Resolve capabilities for this model
        caps = caps_resolver.resolve(config.model_name)

        # Instantiate provider
        provider = _instantiate_provider(provider_cls, config, client, caps)

        providers.append(provider)

    return tuple(providers)


async def get_primary_embedding_provider(
    all_providers: Any,  # Sequence[EmbeddingProvider]
) -> Any:  # EmbeddingProvider
    """Get the primary (first) embedding provider from the collection.

    Args:
        all_providers: All embedding providers (primary + backups)

    Returns:
        The primary embedding provider (first in sequence)

    Raises:
        ConfigurationError: If no providers are configured
    """
    from codeweaver.core import ConfigurationError

    if not all_providers:
        raise ConfigurationError(
            "No embedding providers configured",
            suggestions=["Configure at least one embedding provider in settings"],
        )

    return all_providers[0]


# Type aliases for provider injection
if TYPE_CHECKING:
    from typing import Sequence

    from codeweaver.providers.embedding.providers.base import EmbeddingProvider


type AllEmbeddingProvidersDep = Annotated[
    tuple[Any, ...],  # Sequence[EmbeddingProvider] in runtime
    depends(create_all_embedding_providers),
]
"""Type alias for DI injection of ALL embedding providers (primary + backups).

Use this when you need access to backup providers, not just the primary.

Example:
    ```python
    async def handle_failover(
        all_providers: AllEmbeddingProvidersDep = INJECTED
    ) -> None:
        primary = all_providers[0]
        backups = all_providers[1:]
        # Implement failover logic...
    ```
"""


type PrimaryEmbeddingProviderDep = Annotated[
    Any,  # EmbeddingProvider in runtime
    depends(get_primary_embedding_provider),
]
"""Type alias for DI injection of the primary embedding provider only.

Use this when you only need the primary provider, not backups.

Example:
    ```python
    async def embed_documents(
        provider: PrimaryEmbeddingProviderDep = INJECTED,
        documents: list[CodeChunk],
    ) -> list[list[float]]:
        return await provider.embed_documents(documents)
    ```
"""


# ===========================================================================
# *                            MODULE EXPORTS
# ===========================================================================

__all__ = (
    # Provider Settings Type Aliases
    "AgentProviderSettingsDep",
    "AllEmbeddingConfigsDep",
    "AzureEmbeddingProviderSettingsDep",
    "BedrockEmbeddingProviderSettingsDep",
    "BedrockRerankingProviderSettingsDep",
    "DataProviderSettingsDep",
    "EmbeddingProviderSettingsDep",
    "FastEmbedEmbeddingProviderSettingsDep",
    "FastEmbedRerankingProviderSettingsDep",
    "FastEmbedSparseEmbeddingProviderSettingsDep",
    "ProviderSettingsDep",
    "QdrantVectorStoreProviderSettingsDep",
    "RerankingProviderSettingsDep",
    "SparseEmbeddingProviderSettingsDep",
    "VectorStoreProviderSettingsDep",
    # Capability Resolver Type Aliases
    "EmbeddingCapabilityResolverDep",
    "RerankingCapabilityResolverDep",
    # Client Type Alias (Universal Factory)
    "ClientDep",
    # Provider Type Aliases (Phase 4)
    "AllEmbeddingProvidersDep",
    "PrimaryEmbeddingProviderDep",
    # Helper Functions (Phase 4)
    "create_all_embedding_providers",
    "get_primary_embedding_provider",
    # Utilities
    "NoneDep",
)

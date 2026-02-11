# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""
Models and TypedDict classes for provider and AI (embedding, sparse embedding, reranking, agent) model settings.

The overall pattern:
    - Each potential provider client (the actual client class, e.g., OpenAIClient) has a corresponding ClientOptions class (e.g., OpenAIClientOptions).
    - There is a baseline provider settings model, `BaseProviderCategorySettings`. Each provider type (embedding, data, vector store, etc.) has a corresponding settings model that extends `BaseProviderCategorySettings` (e.g., `EmbeddingProviderSettings`). These are mostly almost identical, but the class distinctions make identification easier and improves clarity.
    - Certain providers with unique settings requirements can define a mixin class that provides the additional required settings. Note that these should not overlap with the client options for the provider.
    - A series of discriminators help with identifying the correct client options and provider settings classes based on the provider and other settings.
"""

from __future__ import annotations

import logging
import os

from typing import Annotated, Any, Literal, NamedTuple, NotRequired, TypedDict, cast, is_typeddict

from pydantic import Field, SecretStr, computed_field, model_validator
from pydantic_ai.settings import ModelSettings as AgentModelSettings
from pydantic_ai.settings import merge_model_settings

from codeweaver.core.constants import ENV_EXPLICIT_TRUE_VALUES, LOCALHOST, ONE, ZERO
from codeweaver.core.types import (
    BasedModel,
    DictView,
    LiteralProviderCategoryType,
    ModelName,
    ModelNameT,
    Provider,
    ProviderCategory,
    ProviderCategoryLiteralString,
    Unset,
)
from codeweaver.core.utils import has_package
from codeweaver.providers import AnthropicAgentProviderSettings, VoyageClientOptions
from codeweaver.providers.config.categories import (
    AgentProviderSettingsType,
    AsymmetricEmbeddingProviderSettings,
    BaseAgentProviderSettings,
    BaseProviderCategorySettings,
    DataProviderSettingsType,
    DuckDuckGoProviderSettings,
    EmbeddingProviderSettings,
    EmbeddingProviderSettingsType,
    QdrantVectorStoreProviderSettings,
    RerankingProviderSettings,
    RerankingProviderSettingsType,
    SparseEmbeddingProviderSettings,
    SparseEmbeddingProviderSettingsType,
    TavilyProviderSettings,
    VectorStoreProviderSettingsType,
)
from codeweaver.providers.config.clients import (
    QdrantClientOptions,
    SentenceTransformersClientOptions,
)
from codeweaver.providers.config.sdk import (
    CollectionConfig,
    EmbeddingConfigT,
    FastEmbedEmbeddingConfig,
    FastEmbedRerankingConfig,
    FastEmbedSparseEmbeddingConfig,
    GoogleEmbeddingConfig,
    MistralEmbeddingConfig,
    RerankingConfigT,
    SentenceTransformersEmbeddingConfig,
    SentenceTransformersEncodeDict,
    SentenceTransformersRerankingConfig,
    SentenceTransformersSparseEmbeddingConfig,
    SparseEmbeddingConfigT,
    VoyageEmbeddingConfig,
    VoyageEmbeddingOptionsDict,
    VoyageRerankingConfig,
)


logger = logging.getLogger(__name__)


# ===========================================================================
# *                    More TypedDict versions of Models
# ===========================================================================


class ProviderSettingsDict(TypedDict, total=False):
    """A dictionary representation of provider settings."""

    agent: NotRequired[tuple[AgentProviderSettingsType, ...] | None]

    data: NotRequired[tuple[DataProviderSettingsType, ...] | None]
    # we currently only support one each of embedding, reranking and vector store providers
    # but we use tuples to allow for future expansion for some less common use cases
    embedding: NotRequired[
        tuple[EmbeddingProviderSettingsType | AsymmetricEmbeddingProviderSettings, ...] | None
    ]
    """Embedding configuration. Can include symmetric (single-model) or asymmetric (dual-model) embedding configs. Asymmetric embedding allows using different models for document and query embeddings while maintaining compatibility through shared vector spaces."""
    # rerank is probably the priority for multiple providers in the future, because they're vector agnostic, so you could have fallback providers, or use different ones for different tasks
    sparse_embedding: NotRequired[tuple[SparseEmbeddingProviderSettingsType, ...] | None]
    reranking: NotRequired[tuple[RerankingProviderSettingsType, ...] | None]

    vector_store: NotRequired[tuple[VectorStoreProviderSettingsType, ...] | None]


type ProviderSettingsView = DictView[ProviderSettingsDict]


def merge_agent_model_settings(
    base: AgentModelSettings | None, override: AgentModelSettings | None
) -> AgentModelSettings | None:
    """A convenience re-export of `merge_model_settings` for agent model settings."""
    return merge_model_settings(base, override)


def _create_default_data_provider_settings() -> tuple[DataProviderSettingsType, ...]:
    """Create default data provider settings (delayed initialization)."""
    if has_package("tavily") and Provider.TAVILY.has_env_auth:
        return (TavilyProviderSettings(provider=Provider.TAVILY),)
    return (
        (DuckDuckGoProviderSettings(provider=Provider.DUCKDUCKGO),) if has_package("ddgs") else ()
    )


class DeterminedDefaults(NamedTuple):
    """Tuple for determined default embedding settings."""

    provider: Provider | Literal[Provider.NOT_SET]
    model: ModelNameT | None
    enabled: bool | Literal[False]


def _get_default_embedding_settings() -> DeterminedDefaults:
    """Determine the default embedding provider, model, and enabled status based on available libraries."""
    for lib in (
        "voyageai",
        "mistral",
        "google",
        "sentence_transformers",
        "fastembed_gpu",
        "fastembed",
    ):
        if has_package(lib):
            # all three of the top defaults are extremely capable and finetuned for code tasks
            if lib == "voyageai" and Provider.VOYAGE.has_env_auth:
                return DeterminedDefaults(
                    provider=Provider.VOYAGE, model=ModelName("voyage-4"), enabled=True
                )
            if lib == "mistral" and Provider.MISTRAL.has_env_auth:
                return DeterminedDefaults(
                    provider=Provider.MISTRAL, model=ModelName("codestral-embed"), enabled=True
                )
            if lib == "google" and Provider.GOOGLE.has_env_auth:
                return DeterminedDefaults(
                    provider=Provider.GOOGLE, model=ModelName("gemini-embedding-001"), enabled=True
                )
            if lib in {"fastembed_gpu", "fastembed"}:
                return DeterminedDefaults(
                    provider=Provider.FASTEMBED,
                    model=ModelName("BAAI/bge-small-en-v1.5"),
                    enabled=True,
                )
            if lib == "sentence_transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    # embedding-small-english-r2 is *very lightweight* and quite capable with a good context window (8192 tokens)
                    # Good upgrade from the likes of all-minilm-L6-v2 while still being very efficient
                    model=ModelName("voyageai/voyage-4-nano"),
                    enabled=True,
                )
    logger.warning(
        "No default embedding provider libraries found. Embedding functionality will be disabled unless explicitly set in your config or environment variables."
    )
    return DeterminedDefaults(provider=Provider.NOT_SET, model=ModelName("NONE"), enabled=False)


_embedding_defaults = _get_default_embedding_settings()


def _produce_voyage_family(
    provider: Provider, model: ModelNameT
) -> AsymmetricEmbeddingProviderSettings:
    """Produce the Voyage4ModelFamily instance for the given provider and model."""
    query_config = SentenceTransformersEmbeddingConfig(
        model_name=ModelName("voyageai/voyage-4-nano"),
        embedding=SentenceTransformersEncodeDict(precision="uint8", truncate_dim=1024),
    )
    if Provider.VOYAGE.has_env_auth and str(model) in {
        "voyage-4",
        "voyage-4-lite",
        "voyage-4-large",
    }:
        embed_config = VoyageEmbeddingConfig(
            model_name=model,
            embedding=VoyageEmbeddingOptionsDict(output_dimension=1024, output_dtype="uint8"),
        )
    else:
        embed_config = query_config
    query_settings = EmbeddingProviderSettings(
        provider=Provider.SENTENCE_TRANSFORMERS,
        model_name=query_config.model_name,
        embedding_config=query_config,
        client_options=SentenceTransformersClientOptions(
            model_name_or_path=query_config.model_name, similarity_fn_name="dot", truncate_dim=1024
        ),
    )
    if embed_config.provider != query_config.provider:
        embed_settings = EmbeddingProviderSettings(
            provider=provider,
            model_name=model,
            embedding_config=embed_config,
            client_options=VoyageClientOptions(api_key=Provider.VOYAGE.get_env_api_key()),  # ty:ignore[invalid-argument-type]
        )
    else:
        embed_settings = query_settings
    return AsymmetricEmbeddingProviderSettings(
        embed_provider=embed_settings,
        query_provider=query_settings,
        validate_family_compatibility=True,
    )


def _create_embedding_config(provider: Provider, model: ModelNameT) -> EmbeddingConfigT:
    """Create provider-specific embedding config based on provider type."""
    if provider == Provider.VOYAGE:
        return VoyageEmbeddingConfig(model_name=model)
    if provider == Provider.MISTRAL:
        return MistralEmbeddingConfig(model_name=model)
    if provider == Provider.GOOGLE:
        return GoogleEmbeddingConfig(model_name=model)
    if provider == Provider.FASTEMBED:
        return FastEmbedEmbeddingConfig(model_name=model)
    if provider == Provider.SENTENCE_TRANSFORMERS:
        return SentenceTransformersEmbeddingConfig(model_name=model)
    raise ValueError(f"Unknown embedding provider: {provider}")


def _get_default_embedding_provider_settings() -> tuple[EmbeddingProviderSettings, ...] | None:
    """Get default embedding provider settings (delayed instantiation)."""
    if _embedding_defaults.provider == Provider.NOT_SET:
        return None
    return (
        EmbeddingProviderSettings(
            provider=_embedding_defaults.provider,
            model_name=_embedding_defaults.model,
            embedding_config=_create_embedding_config(
                _embedding_defaults.provider,
                _embedding_defaults.model,  # ty:ignore[invalid-argument-type]
            ),
        ),
    )


DefaultEmbeddingProviderSettings: tuple[EmbeddingProviderSettings, ...] | None = (
    None  # Will be lazy-initialized
)


def _get_default_sparse_embedding_settings() -> DeterminedDefaults:
    """Determine the default sparse embedding provider, model, and enabled status based on available libraries."""
    for lib in ("sentence_transformers", "fastembed_gpu", "fastembed"):
        if has_package(lib):
            if lib == "sentence_transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    model=ModelName("opensearch/opensearch-neural-sparse-encoding-doc-v3-gte"),
                    enabled=True,
                )
            if lib in {"fastembed_gpu", "fastembed"}:
                return DeterminedDefaults(
                    provider=Provider.FASTEMBED,
                    model=ModelName("prithivida/Splade_PP_en_v1"),
                    enabled=True,
                )
    # qdrant_client has built-in BM25 support
    # if FastEmbed isn't available, we will use that automatically
    return DeterminedDefaults(
        provider=Provider.FASTEMBED, model=ModelName("qdrant/bm25"), enabled=True
    )


_sparse_embedding_defaults = _get_default_sparse_embedding_settings()


def _create_sparse_embedding_config(
    provider: Provider, model: ModelNameT
) -> SparseEmbeddingConfigT:
    """Create provider-specific sparse embedding config based on provider type."""
    if provider == Provider.SENTENCE_TRANSFORMERS:
        return SentenceTransformersSparseEmbeddingConfig(model_name=model)
    if provider == Provider.FASTEMBED:
        return FastEmbedSparseEmbeddingConfig(model_name=model)
    raise ValueError(f"Unknown sparse embedding provider: {provider}")


def _get_default_sparse_embedding_provider_settings() -> tuple[
    SparseEmbeddingProviderSettings, ...
]:
    """Get default sparse embedding provider settings (delayed instantiation)."""
    return (
        SparseEmbeddingProviderSettings(
            provider=_sparse_embedding_defaults.provider,
            model_name=_sparse_embedding_defaults.model,
            sparse_embedding_config=_create_sparse_embedding_config(
                _sparse_embedding_defaults.provider,
                _sparse_embedding_defaults.model,  # ty:ignore[invalid-argument-type]
            ),
        ),
    )


DefaultSparseEmbeddingProviderSettings: tuple[SparseEmbeddingProviderSettings, ...] | None = (
    None  # Will be lazy-initialized
)


def _get_default_reranking_settings() -> DeterminedDefaults:
    """Determine the default reranking provider, model, and enabled status based on available libraries."""
    for lib in ("voyageai", "fastembed_gpu", "fastembed", "sentence_transformers"):
        if has_package(lib) is not None:
            if lib == "voyageai":
                return DeterminedDefaults(
                    provider=Provider.VOYAGE, model=ModelName("voyage:rerank-2.5"), enabled=True
                )
            if lib in {"fastembed-gpu", "fastembed"}:
                return DeterminedDefaults(
                    provider=Provider.FASTEMBED,
                    model=ModelName("fastembed:jinaai/jina-reranking-v2-base-multilingual"),
                    enabled=True,
                )
            if lib == "sentence-transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    # on the heavier side for what we aim for as a default but very capable
                    model=ModelName("sentence-transformers:BAAI/bge-reranking-v2-m3"),
                    enabled=True,
                )
    possible_libs = [has_package(lib) for lib in ("boto3", "cohere") if has_package(lib)]
    logger.warning(
        "No default reranking provider libraries found. Reranking functionality will be disabled unless explicitly set in your config or environment variables. %s",
        (
            f"It looks like you have {'these' if len(possible_libs) > 1 else 'this'} libraries installed that support reranking: {', '.join(lib.name for lib in possible_libs)}."
            if possible_libs
            else "You have no known reranking libraries installed."
        ),
    )
    return DeterminedDefaults(provider=Provider.NOT_SET, model=None, enabled=False)


_reranking_defaults = _get_default_reranking_settings()


def _create_reranking_config(provider: Provider, model: ModelNameT) -> RerankingConfigT:
    """Create provider-specific reranking config based on provider type."""
    if provider == Provider.VOYAGE:
        return VoyageRerankingConfig(model_name=model)
    if provider == Provider.FASTEMBED:
        return FastEmbedRerankingConfig(model_name=model)
    if provider == Provider.SENTENCE_TRANSFORMERS:
        return SentenceTransformersRerankingConfig(model_name=model)
    raise ValueError(f"Unknown reranking provider: {provider}")


def _get_default_reranking_provider_settings() -> tuple[RerankingProviderSettings, ...] | None:
    """Get default reranking provider settings (delayed instantiation)."""
    if _reranking_defaults.provider == Provider.NOT_SET:
        return None
    return (
        RerankingProviderSettings(
            provider=_reranking_defaults.provider,
            model_name=_reranking_defaults.model,
            reranking_config=_create_reranking_config(
                _reranking_defaults.provider,
                _reranking_defaults.model,  # ty:ignore[invalid-argument-type]
            ),
        ),
    )


DefaultRerankingProviderSettings: tuple[RerankingProviderSettings, ...] | None = (
    None  # Will be lazy-initialized
)

HAS_ANTHROPIC = (has_package("anthropic") or has_package("claude-agent-sdk")) is not None


def _get_default_agent_provider_settings() -> tuple[AgentProviderSettingsType, ...] | None:
    """Get default agent provider settings (delayed instantiation)."""
    if not HAS_ANTHROPIC:
        return None
    # Don't instantiate AgentModelSettings here to avoid forward reference issues
    return (
        AnthropicAgentProviderSettings(
            provider=Provider.ANTHROPIC,
            model_name="claude-haiku-4.5-latest",
            agent_config=None,  # Use None to avoid forward reference validation
        ),
    )


DefaultAgentProviderSettings: tuple[AgentProviderSettingsType, ...] | None = (
    None  # Will be lazy-initialized
)


def _get_default_vector_store_provider_settings() -> tuple[QdrantVectorStoreProviderSettings, ...]:
    """Get default vector store provider settings (delayed instantiation)."""
    return (
        QdrantVectorStoreProviderSettings(
            provider=Provider.QDRANT,
            client_options=QdrantClientOptions(host=LOCALHOST),
            collection=CollectionConfig(),
        ),
    )


DefaultVectorStoreProviderSettings: tuple[QdrantVectorStoreProviderSettings, ...] | None = (
    None  # Will be lazy-initialized
)


class ProviderNameMap(TypedDict):
    """Configured providers by category."""

    data: tuple[Provider, ...] | None
    embedding: Provider | tuple[Provider, ...] | None
    sparse_embedding: Provider | tuple[Provider, ...] | None
    reranking: Provider | tuple[Provider, ...] | None
    vector_store: Provider | tuple[Provider, ...] | None
    agent: Provider | tuple[Provider, ...] | None


class ProviderSettings(BasedModel):
    """Settings for provider configuration."""

    data: Annotated[
        tuple[DataProviderSettingsType, ...] | None,
        Field(description="""Data provider configuration"""),
    ] = None

    embedding: Annotated[
        tuple[EmbeddingProviderSettingsType | AsymmetricEmbeddingProviderSettings, ...] | None,
        Field(
            description="""Embedding provider configuration.

            Supports both symmetric (single-model) and asymmetric (dual-model) embedding:

            **Symmetric Mode (EmbeddingProviderSettings)**:
            - Uses the same model for both document and query embeddings
            - Traditional approach where a single model handles all embedding tasks
            - Simpler configuration, single provider setup

            **Asymmetric Mode (AsymmetricEmbeddingProviderSettings)**:
            - Uses different models for document embedding and query embedding
            - Enables cost/performance optimization (e.g., API model for docs, local for queries)
            - Requires models from the same model family for compatibility
            - Embedding dimensions validated automatically

            Requirements for Asymmetric:
              - Both models must belong to the same model family (e.g., Voyage-4)
              - Models must be explicitly marked as compatible
              - Embedding dimensions must match

            Benefits of Asymmetric:
              - Cost optimization: expensive models for documents, cheap for queries
              - Performance: local models for queries, API for indexing
              - Resource flexibility: different deployment strategies per model

            We will only use the first provider you configure here. We may add support for
            multiple embedding providers in the future.

            Example TOML configuration (symmetric):
              [providers.embedding.0]
              provider = "voyage"
              model_name = "voyage-code-3"

            Example TOML configuration (asymmetric):
              [providers.embedding.0]
              config_type = "asymmetric"
              validate_family_compatibility = true

              [providers.embedding.0.embed_provider]
              provider = "voyage"
              model_name = "voyage-4-large"

              [providers.embedding.0.query_provider]
              provider = "sentence-transformers"
              model_name = "voyageai/voyage-4-nano"

            See documentation: docs/configuration/embedding.md
            """
        ),
    ] = None

    sparse_embedding: Annotated[
        tuple[SparseEmbeddingProviderSettingsType, ...] | None,
        Field(
            description="""Sparse embedding provider configuration.

            We will only use the first provider you configure here. We may add support for multiple sparse embedding providers in the future."""
        ),
    ] = None

    reranking: Annotated[
        tuple[RerankingProviderSettingsType, ...] | None,
        Field(
            description="""Reranking provider configuration.

            We will only use the first provider you configure here. We may add support for multiple reranking providers in the future."""
        ),
    ] = None

    vector_store: Annotated[
        tuple[VectorStoreProviderSettingsType, ...] | None,
        Field(
            description="""Vector store provider configuration (Qdrant or in-memory), defaults to a local Qdrant instance."""
        ),
    ] = None

    agent: Annotated[
        tuple[BaseAgentProviderSettings, ...] | None,
        Field(description="""Agent provider configuration"""),
    ] = None

    disable_backup_system: Annotated[
        bool,
        Field(
            description="""Disable CodeWeaver's failsafe/backup system.

            If embedding and vector store providers are local (not in the cloud), then the system is disabled by default and can't be switched on.

            If you use a cloud provider for embeddings, then the backup system will use a lightweight local embedding model to keep embeddings stored on the same points in your vector store as your primary provider and sparse provider. Allowing CodeWeaver to simply switch to querying and updating the backup embeddings when your main provider is unreachable.

            If you use a cloud vector store, the backup system will use regular snapshots and write-ahead-logging to keep a local backup of your vector store, switching to it when the cloud vector store is unreachable.

            Sparse models are currently all local, so we don't backup sparse embeddings. Reranking models are interchangeable (mostly), so we fall back to local models if the primary is unavailable.

            If you set `disable_backup_system` to `True`, don't complain if CodeWeaver stops working when your main providers are unreachable!
            """
        ),
    ] = (
        os.environ.get("CODEWEAVER_DISABLE_BACKUP_SYSTEM", "false").lower()
        in ENV_EXPLICIT_TRUE_VALUES
    )

    def __init__(self, **data: Any) -> None:
        """Initialize ProviderSettings and register with DI container if available."""
        # We'll set the _category field on each class
        # this will help with identification of settings classes
        try:
            from codeweaver.core.di import get_container

            container = get_container()
            container.register(type(self), lambda: self)
        except Exception as e:
            # Log if DI not available
            logger.debug(
                "Dependency injection container not available, skipping registration of ProviderSettings: %s",
                e,
            )
        super().__init__(**data)

    @model_validator(mode="after")
    def validate_and_normalize_providers(self) -> ProviderSettings:
        """Validate and normalize provider settings after initialization."""
        # Lazy-initialize AllDefaultProviderSettings if needed
        global AllDefaultProviderSettings
        if AllDefaultProviderSettings is None:
            AllDefaultProviderSettings = _get_all_default_provider_settings()
        for key in self._field_names:
            value = getattr(self, key)
            if value is None and AllDefaultProviderSettings.get(key):
                default_value = AllDefaultProviderSettings.get(key)
                setattr(self, key, default_value)
                value = default_value
            if value is Unset:
                default_value = AllDefaultProviderSettings.get(key)
                setattr(self, key, default_value)
                value = default_value
            if not isinstance(value, tuple) and key != "disable_backup_system":
                value = (value,)
                setattr(self, key, value)
        return self

    @model_validator(mode="after")
    def validate_embedding_configuration(self) -> ProviderSettings:
        """Validate embedding configuration and log the selected mode.

        Returns:
            Self for method chaining.
        """
        if self.embedding is not None and self.embedding is not Unset and self.embedding:
            # Check if we have asymmetric or symmetric configs
            first_config = self.embedding[0]
            if isinstance(first_config, AsymmetricEmbeddingProviderSettings):
                logger.debug(
                    "Using asymmetric embedding mode: embed=%s, query=%s",
                    str(first_config.embed_provider.model_name),
                    str(first_config.query_provider.model_name),
                )
            else:
                logger.debug("Using symmetric embedding mode with providers: %s", self.embedding)
        else:
            logger.debug("No embedding configuration specified")

        return self

    def _telemetry_keys(self) -> None:
        return None

    def has_setting(
        self, setting_name: ProviderCategoryLiteralString | LiteralProviderCategoryType
    ) -> bool:
        """Check if a specific provider setting is configured.

        Args:
            setting_name: The name of the setting or ProviderCategory to check.
        """
        from codeweaver.core import ProviderCategory

        setting = (
            setting_name
            if setting_name in ProviderCategoryLiteralString.__value__.__args__
            else cast(ProviderCategory, setting_name).variable
        )
        return getattr(self, setting) is not Unset  # type: ignore

    @computed_field
    @property
    def providers(self) -> frozenset[Provider]:
        """Get a set of configured providers."""
        return frozenset({
            p
            for prov in self.provider_name_map.values()
            if prov
            for p in (prov if isinstance(prov, tuple) else (prov,))
        })  # type: ignore

    @property
    def _field_names(self) -> tuple[ProviderCategoryLiteralString, ...]:
        """Get the field names for provider settings."""
        return ProviderCategoryLiteralString.__value__.__args__

    @property
    def _all_configs(self) -> tuple[BaseProviderCategorySettings, ...]:
        """Get all provider settings as a flat tuple."""
        return tuple(
            setting
            for configs in self.provider_configs.values()
            if configs
            for setting in (configs if isinstance(configs, tuple) else (configs,))
        )

    @property
    def provider_configs(
        self,
    ) -> dict[ProviderCategoryLiteralString, tuple[BaseProviderCategorySettings, ...]]:
        """Get a summary of configured provider settings by category."""
        return {
            field_name: settings
            if isinstance(settings, tuple)
            else (settings,)
            if settings and settings is not Unset
            else ()
            for field_name, settings in self.model_dump().items()
            if field_name in self._field_names
        }

    @property
    def provider_name_map(self) -> ProviderNameMap:
        """Get a summary of configured providers by category."""
        provider_data: dict[
            ProviderCategoryLiteralString, Provider | tuple[Provider, ...] | None
        ] = {
            field_name: (
                tuple(s.provider for s in setting if setting and is_typeddict(s))
                if isinstance(setting, tuple)
                else (setting["provider"] if setting else None)
            )
            for field_name, setting in self.provider_configs.items()
        }

        return ProviderNameMap(**provider_data)  # type: ignore

    def settings_for_provider(
        self, provider: Provider
    ) -> BaseProviderCategorySettings | tuple[BaseProviderCategorySettings, ...] | None:
        """Get the settings for a specific provider."""
        if provider == Provider.NOT_SET:
            return None

        # Collect all fields containing this provider in a single pass
        matching_fields = []
        for field_name, config_value in self.provider_configs.items():
            if isinstance(config_value, tuple):
                if any(cfg.get("provider") == provider for cfg in config_value):
                    matching_fields.append(field_name)
            elif isinstance(config_value, dict) and config_value.get("provider") == provider:
                matching_fields.append(field_name)

        if not matching_fields:
            return None

        # Retrieve and flatten settings for matching fields
        all_settings: list[BaseProviderCategorySettings] = []
        for field in matching_fields:
            if setting := self.settings_for_category(field):
                if isinstance(setting, tuple):
                    all_settings.extend(setting)
                else:
                    all_settings.append(setting)

        return (
            all_settings[0]
            if len(all_settings) == ONE
            else tuple(all_settings)
            if all_settings
            else None
        )

    def _dig_for_secret_keys(self, settings: tuple[dict[str, Any], ...]) -> bool:
        """Recursively check if any secret keys are present in the settings dictionary."""
        properties = (
            "api_key",
            "token",
            "credentials",
            "access_token",
            "secret_key",
            "auth_token",
            "bearer_token",
            "azure_ad_token_provider",
            "aws_secret_key",
            "aws_access_key",
            "aws_session_token",
        )

        def _recurse(current: dict[str, Any]) -> bool:
            for key, value in current.items():
                if key in properties and value is not None:
                    return True
                if isinstance(value, SecretStr):
                    return True
                if isinstance(value, dict):
                    if _recurse(value):
                        return True
                elif isinstance(value, list | tuple | set):
                    for item in value:
                        if isinstance(item, dict) and _recurse(item):
                            return True
            return False

        return any(_recurse(setting) for setting in settings)

    def has_auth_configured(self, provider: Provider) -> bool:
        """Check if API key or TLS certs are set for the provider through settings or environment."""
        if not (settings := self.settings_for_provider(provider)):
            return False
        settings = settings if isinstance(settings, tuple) else (settings,)
        return self._dig_for_secret_keys(tuple(c.model_dump() for c in settings))

    def settings_for_category(
        self,
        category: ProviderCategoryLiteralString | LiteralProviderCategoryType,
        *,
        primary: bool = True,
        backup: bool = False,
    ) -> BaseProviderCategorySettings | tuple[BaseProviderCategorySettings, ...] | None:
        """Get the settings for a specific provider category.

        Args:
            category: The category of provider or ProviderCategory to get settings for.
            primary: Whether to return the primary settings or all settings.
            backup: Whether to return the backup settings instead of the primary.
        """
        setting_field = (
            category
            if category
            in {"data", "embedding", "sparse_embedding", "reranking", "vector_store", "agent"}
            else cast(ProviderCategory, category).variable
        )
        setting = getattr(self, setting_field, None)  # type: ignore
        if setting is None:
            return None
        if setting is Unset:
            setting = AllDefaultProviderSettings.get(setting_field)  # type: ignore
            setattr(self, setting_field, setting)  # type: ignore
        if primary and isinstance(setting, tuple) and len(setting) > ZERO:
            return setting[0]
        if backup:
            return setting[1] if isinstance(setting, tuple) and len(setting) > ONE else None
        return setting


def _get_all_default_provider_settings() -> ProviderSettingsDict:
    """Get all default provider settings (delayed initialization)."""
    from codeweaver.providers.config.profiles import ProviderSettingsDict

    return ProviderSettingsDict(
        data=_create_default_data_provider_settings(),
        embedding=DefaultEmbeddingProviderSettings,
        sparse_embedding=DefaultSparseEmbeddingProviderSettings,
        reranking=DefaultRerankingProviderSettings,
        agent=DefaultAgentProviderSettings,
    )


AllDefaultProviderSettings = None  # Will be lazy-initialized on first access


__all__ = (
    "AllDefaultProviderSettings",
    "EmbeddingProviderSettingsType",
    "ProviderSettings",
    "ProviderSettingsDict",
    "ProviderSettingsView",
    "RerankingProviderSettingsType",
    "VectorStoreProviderSettingsType",
    "merge_agent_model_settings",
)

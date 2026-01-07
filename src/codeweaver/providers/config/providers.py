# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""
Models and TypedDict classes for provider and AI (embedding, sparse embedding, reranking, agent) model settings.

The overall pattern:
    - Each potential provider client (the actual client class, e.g., OpenAIClient) has a corresponding ClientOptions class (e.g., OpenAIClientOptions).
    - There is a baseline provider settings model, `BaseProviderSettings`. Each provider type (embedding, data, vector store, etc.) has a corresponding settings model that extends `BaseProviderSettings` (e.g., `EmbeddingProviderSettings`). These are mostly almost identical, but the class distinctions make identification easier and improves clarity.
    - Certain providers with unique settings requirements can define a mixin class that provides the additional required settings. Note that these should not overlap with the client options for the provider.
    - A series of discriminators help with identifying the correct client options and provider settings classes based on the provider and other settings.
"""

from __future__ import annotations

import importlib
import logging

from typing import (
    Annotated,
    Any,
    Literal,
    LiteralString,
    NamedTuple,
    NotRequired,
    TypedDict,
    cast,
    is_typeddict,
)

from pydantic import Discriminator, Field, SecretStr, Tag, computed_field, model_validator
from pydantic_ai.settings import ModelSettings as AgentModelSettings
from pydantic_ai.settings import merge_model_settings

from codeweaver.core import (
    UNSET,
    BasedModel,
    DictView,
    LiteralProviderKindType,
    Provider,
    ProviderKind,
    Unset,
)
from codeweaver.providers.config.clients import QdrantClientOptions
from codeweaver.providers.config.embedding import (
    EmbeddingConfigT,
    FastEmbedEmbeddingConfig,
    FastEmbedSparseEmbeddingConfig,
    GoogleEmbeddingConfig,
    MistralEmbeddingConfig,
    SentenceTransformersEmbeddingConfig,
    SentenceTransformersSparseEmbeddingConfig,
    SparseEmbeddingConfigT,
    VoyageEmbeddingConfig,
)
from codeweaver.providers.config.kinds import (
    AgentProviderSettings,
    AzureEmbeddingProviderSettings,
    BaseProviderSettings,
    BedrockEmbeddingProviderSettings,
    BedrockRerankingProviderSettings,
    DataProviderSettings,
    EmbeddingProviderSettings,
    FastEmbedEmbeddingProviderSettings,
    FastEmbedRerankingProviderSettings,
    FastEmbedSparseEmbeddingProviderSettings,
    QdrantVectorStoreProviderSettings,
    RerankingProviderSettings,
    SparseEmbeddingProviderSettings,
)
from codeweaver.providers.config.reranking import (
    FastEmbedRerankingConfig,
    RerankingConfigT,
    SentenceTransformersRerankingConfig,
    VoyageRerankingConfig,
)


logger = logging.getLogger(__name__)


# ===========================================================================
# *                    Settings Discriminators
# ===========================================================================

# Vector Stores

type VectorStoreProviderSettingsType = Annotated[
    Annotated[QdrantVectorStoreProviderSettings, Tag(Provider.QDRANT.variable)],
    Field(description="Vector store provider settings type.", discriminator="tag"),
]
"""Type alias for vector store provider settings type. Currently only Qdrant is supported, but we create this for consistency and future expansion."""

# Embedding Providers

type SpecialEmbeddingProviderSettingsType = Annotated[
    Annotated[AzureEmbeddingProviderSettings, Tag(Provider.AZURE.variable)]
    | Annotated[BedrockEmbeddingProviderSettings, Tag(Provider.BEDROCK.variable)]
    | Annotated[FastEmbedEmbeddingProviderSettings, Tag(Provider.FASTEMBED.variable)],
    Field(description="Special embedding provider settings type.", discriminator="tag"),
]


def _discriminate_embedding_provider(v: Any) -> str:
    """Identify the embedding provider settings type for discriminator field."""
    return (
        tag
        if (tag := (v["tag"] if isinstance(v, dict) else v.tag))
        in {Provider.AZURE.variable, Provider.BEDROCK.variable, Provider.FASTEMBED.variable}
        else "none"
    )


type EmbeddingProviderSettingsType = Annotated[
    Annotated[EmbeddingProviderSettings, Tag("none")] | SpecialEmbeddingProviderSettingsType,
    Field(
        description="Embedding provider settings type.",
        discriminator=Discriminator(_discriminate_embedding_provider),
    ),
]

# Sparse Embedding Providers

type SparseEmbeddingProviderSettingsType = Annotated[
    Annotated[SparseEmbeddingProviderSettings, Tag(Provider.SENTENCE_TRANSFORMERS.variable)]
    | Annotated[FastEmbedSparseEmbeddingProviderSettings, Tag(Provider.FASTEMBED.variable)],
    Field(description="Sparse embedding provider settings type.", discriminator="tag"),
]

# Reranking Providers


def _discriminate_reranking_provider(v: Any) -> str:
    """Identify the reranking provider settings type for discriminator field."""
    return (
        tag
        if (tag := (v["tag"] if isinstance(v, dict) else v.tag))
        in {Provider.FASTEMBED.variable, Provider.BEDROCK.variable}
        else "none"
    )


type SpecialRerankingProviderSettingsType = Annotated[
    Annotated[FastEmbedRerankingProviderSettings, Tag(Provider.FASTEMBED.variable)]
    | Annotated[BedrockRerankingProviderSettings, Tag(Provider.BEDROCK.variable)],
    Field(description="Special reranking provider settings type.", discriminator="tag"),
]

type RerankingProviderSettingsType = Annotated[
    Annotated[RerankingProviderSettings, Tag("none")] | SpecialRerankingProviderSettingsType,
    Field(
        description="Reranking provider settings type.",
        discriminator=Discriminator(_discriminate_reranking_provider),
    ),
]

# ===== Data and Agent Providers just for consistency =====

type DataProviderSettingsType = Annotated[
    DataProviderSettings, Field(description="Data provider settings type.")
]

type AgentProviderSettingsType = Annotated[
    AgentProviderSettings, Field(description="Agent provider settings type.")
]

# ===========================================================================
# *                    More TypedDict versions of Models
# ===========================================================================


class ProviderSettingsDict(TypedDict, total=False):
    """A dictionary representation of provider settings."""

    data: NotRequired[tuple[DataProviderSettingsType, ...] | None]
    # we currently only support one each of embedding, reranking and vector store providers
    # but we use tuples to allow for future expansion for some less common use cases
    embedding: NotRequired[
        tuple[EmbeddingProviderSettingsType, ...] | EmbeddingProviderSettingsType | None
    ]
    # rerank is probably the priority for multiple providers in the future, because they're vector agnostic, so you could have fallback providers, or use different ones for different tasks
    sparse_embedding: NotRequired[
        tuple[SparseEmbeddingProviderSettingsType, ...] | SparseEmbeddingProviderSettingsType | None
    ]
    reranking: NotRequired[
        tuple[RerankingProviderSettingsType, ...] | RerankingProviderSettingsType | None
    ]

    vector_store: NotRequired[
        tuple[VectorStoreProviderSettingsType, ...] | VectorStoreProviderSettingsType | None
    ]
    agent: NotRequired[tuple[AgentProviderSettingsType, ...] | AgentProviderSettingsType | None]


type ProviderSettingsView = DictView[ProviderSettingsDict]


def merge_agent_model_settings(
    base: AgentModelSettings | None, override: AgentModelSettings | None
) -> AgentModelSettings | None:
    """A convenience re-export of `merge_model_settings` for agent model settings."""
    return merge_model_settings(base, override)


DefaultDataProviderSettings = (
    DataProviderSettings(provider=Provider.TAVILY),
    # DuckDuckGo
    DataProviderSettings(provider=Provider.DUCKDUCKGO),
)


class DeterminedDefaults(NamedTuple):
    """Tuple for determined default embedding settings."""

    provider: Provider
    model: LiteralString
    enabled: bool


def _get_default_embedding_settings() -> DeterminedDefaults:
    """Determine the default embedding provider, model, and enabled status based on available libraries."""
    for lib in (
        "voyageai",
        "mistral",
        "google",
        "fastembed-gpu",
        "fastembed",
        "sentence-transformers",
    ):
        if importlib.util.find_spec(lib) is not None:
            # all three of the top defaults are extremely capable and finetuned for code tasks
            if lib == "voyageai":
                return DeterminedDefaults(
                    provider=Provider.VOYAGE, model="voyage-code-3", enabled=True
                )
            if lib == "mistral":
                return DeterminedDefaults(
                    provider=Provider.MISTRAL, model="codestral-embed", enabled=True
                )
            if lib == "google":
                return DeterminedDefaults(
                    provider=Provider.GOOGLE, model="gemini-embedding-001", enabled=True
                )
            if lib in {"fastembed-gpu", "fastembed"}:
                return DeterminedDefaults(
                    provider=Provider.FASTEMBED, model="BAAI/bge-small-en-v1.5", enabled=True
                )
            if lib == "sentence-transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    # embedding-small-english-r2 is *very lightweight* and quite capable with a good context window (8192 tokens)
                    # Good upgrade from the likes of all-minilm-L6-v2 while still being very efficient
                    model="ibm-granite/granite-embedding-small-english-r2",
                    enabled=True,
                )
    logger.warning(
        "No default embedding provider libraries found. Embedding functionality will be disabled unless explicitly set in your config or environment variables."
    )
    return DeterminedDefaults(provider=Provider.NOT_SET, model="NONE", enabled=False)


_embedding_defaults = _get_default_embedding_settings()


def _create_embedding_config(provider: Provider, model: LiteralString) -> EmbeddingConfigT:
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


DefaultEmbeddingProviderSettings = (
    EmbeddingProviderSettings(
        provider=_embedding_defaults.provider,
        model_name=_embedding_defaults.model,
        embedding_config=_create_embedding_config(
            _embedding_defaults.provider, _embedding_defaults.model
        ),
    )
    if _embedding_defaults.provider != Provider.NOT_SET
    else None  # type: ignore[assignment]
)


def _get_default_sparse_embedding_settings() -> DeterminedDefaults:
    """Determine the default sparse embedding provider, model, and enabled status based on available libraries."""
    for lib in ("sentence-transformers", "fastembed-gpu", "fastembed"):
        if importlib.util.find_spec(lib) is not None:
            if lib == "sentence-transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    model="opensearch/opensearch-neural-sparse-encoding-doc-v3-gte",
                    enabled=True,
                )
            if lib in {"fastembed-gpu", "fastembed"}:
                return DeterminedDefaults(
                    provider=Provider.FASTEMBED, model="prithivida/Splade_PP_en_v1", enabled=True
                )
    # qdrant_client has built-in BM25 support
    # if FastEmbed isn't available, we will use that automatically
    return DeterminedDefaults(provider=Provider.FASTEMBED, model="qdrant/bm25", enabled=True)


_sparse_embedding_defaults = _get_default_sparse_embedding_settings()


def _create_sparse_embedding_config(
    provider: Provider, model: LiteralString
) -> SparseEmbeddingConfigT:
    """Create provider-specific sparse embedding config based on provider type."""
    if provider == Provider.SENTENCE_TRANSFORMERS:
        return SentenceTransformersSparseEmbeddingConfig(model_name=model)
    if provider == Provider.FASTEMBED:
        return FastEmbedSparseEmbeddingConfig(model_name=model)
    raise ValueError(f"Unknown sparse embedding provider: {provider}")


DefaultSparseEmbeddingProviderSettings = SparseEmbeddingProviderSettings(
    provider=_sparse_embedding_defaults.provider,
    model_name=_sparse_embedding_defaults.model,
    sparse_embedding_config=_create_sparse_embedding_config(
        _sparse_embedding_defaults.provider, _sparse_embedding_defaults.model
    ),
)


def _get_default_reranking_settings() -> DeterminedDefaults:
    """Determine the default reranking provider, model, and enabled status based on available libraries."""
    for lib in ("voyageai", "fastembed-gpu", "fastembed", "sentence-transformers"):
        if importlib.util.find_spec(lib) is not None:
            if lib == "voyageai":
                return DeterminedDefaults(
                    provider=Provider.VOYAGE, model="voyage:rerank-2.5", enabled=True
                )
            if lib in {"fastembed-gpu", "fastembed"}:
                return DeterminedDefaults(
                    provider=Provider.FASTEMBED,
                    model="fastembed:jinaai/jina-reranking-v2-base-multilingual",
                    enabled=True,
                )
            if lib == "sentence-transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    # on the heavier side for what we aim for as a default but very capable
                    model="sentence-transformers:BAAI/bge-reranking-v2-m3",
                    enabled=True,
                )
    possible_libs = [
        importlib.util.find_spec(lib)
        for lib in ("boto3", "cohere")
        if importlib.util.find_spec(lib) is not None
    ]
    logger.warning(
        "No default reranking provider libraries found. Reranking functionality will be disabled unless explicitly set in your config or environment variables. %s",
        (
            f"It looks like you have {'these' if len(possible_libs) > 1 else 'this'} libraries installed that support reranking: {', '.join(lib.name for lib in possible_libs)}."
            if possible_libs
            else "You have no known reranking libraries installed."
        ),
    )
    return DeterminedDefaults(provider=Provider.NOT_SET, model="NONE", enabled=False)


_reranking_defaults = _get_default_reranking_settings()


def _create_reranking_config(provider: Provider, model: LiteralString) -> RerankingConfigT:
    """Create provider-specific reranking config based on provider type."""
    if provider == Provider.VOYAGE:
        return VoyageRerankingConfig(model_name=model)
    if provider == Provider.FASTEMBED:
        return FastEmbedRerankingConfig(model_name=model)
    if provider == Provider.SENTENCE_TRANSFORMERS:
        return SentenceTransformersRerankingConfig(model_name=model)
    raise ValueError(f"Unknown reranking provider: {provider}")


DefaultRerankingProviderSettings = (
    RerankingProviderSettings(
        provider=_reranking_defaults.provider,
        model_name=_reranking_defaults.model,
        reranking_config=_create_reranking_config(
            _reranking_defaults.provider, _reranking_defaults.model
        ),
    )
    if _reranking_defaults.provider != Provider.NOT_SET
    else None  # type: ignore[assignment]
)

HAS_ANTHROPIC = (
    importlib.util.find_spec("anthropic") or importlib.util.find_spec("claude-agent-sdk")
) is not None
DefaultAgentProviderSettings = AgentProviderSettings(
    provider=Provider.ANTHROPIC, model="claude-haiku-4.5-latest", model_options=AgentModelSettings()
)


DefaultVectorStoreProviderSettings = QdrantVectorStoreProviderSettings(
    provider=Provider.QDRANT, client_options=QdrantClientOptions(host="127.0.0.1")
)

type ProviderField = Literal[
    "data", "embedding", "sparse_embedding", "reranking", "vector_store", "agent"
]


class ProviderNameMap(TypedDict):
    """Configured providers by kind."""

    data: tuple[Provider, ...] | None
    embedding: Provider | tuple[Provider, ...] | None
    sparse_embedding: Provider | tuple[Provider, ...] | None
    reranking: Provider | tuple[Provider, ...] | None
    vector_store: Provider | tuple[Provider, ...] | None
    agent: Provider | tuple[Provider, ...] | None


class ProviderSettings(BasedModel):
    """Settings for provider configuration."""

    data: Annotated[
        tuple[DataProviderSettings, ...] | DataProviderSettings | Unset,
        Field(description="""Data provider configuration"""),
    ] = DefaultDataProviderSettings

    embedding: Annotated[
        tuple[EmbeddingProviderSettingsType, ...] | EmbeddingProviderSettingsType | Unset,
        Field(
            description="""Embedding provider configuration.

            We will only use the first provider you configure here. We may add support for multiple embedding providers in the future.
            """
        ),
    ] = DefaultEmbeddingProviderSettings or UNSET

    sparse_embedding: Annotated[
        tuple[SparseEmbeddingProviderSettingsType, ...]
        | SparseEmbeddingProviderSettingsType
        | Unset,
        Field(
            description="""Sparse embedding provider configuration.

            We will only use the first provider you configure here. We may add support for multiple sparse embedding providers in the future."""
        ),
    ] = DefaultSparseEmbeddingProviderSettings

    reranking: Annotated[
        tuple[RerankingProviderSettingsType, ...] | RerankingProviderSettingsType | Unset,
        Field(
            description="""Reranking provider configuration.

            We will only use the first provider you configure here. We may add support for multiple reranking providers in the future."""
        ),
    ] = DefaultRerankingProviderSettings or UNSET

    vector_store: Annotated[
        tuple[VectorStoreProviderSettingsType, ...] | VectorStoreProviderSettingsType | Unset,
        Field(
            description="""Vector store provider configuration (Qdrant or in-memory), defaults to a local Qdrant instance."""
        ),
    ] = DefaultVectorStoreProviderSettings

    agent: Annotated[
        tuple[AgentProviderSettings, ...] | AgentProviderSettings | Unset,
        Field(description="""Agent provider configuration"""),
    ] = DefaultAgentProviderSettings

    @model_validator(mode="after")
    def validate_and_normalize_providers(self) -> ProviderSettings:
        """Validate and normalize provider settings after initialization."""
        for key in ("vector_store", "embedding", "sparse_embedding", "reranking", "agent"):
            value = getattr(self, key)
            if value is not Unset and not isinstance(value, tuple):
                setattr(self, key, (value,))
        return self

    def _telemetry_keys(self) -> None:
        return None

    def has_setting(self, setting_name: ProviderField | LiteralProviderKindType) -> bool:
        """Check if a specific provider setting is configured.

        Args:
            setting_name: The name of the setting or ProviderKind to check.
        """
        from codeweaver.core import ProviderKind

        setting = (
            setting_name
            if setting_name
            in {"data", "embedding", "sparse_embedding", "reranking", "vector_store", "agent"}
            else cast(ProviderKind, setting_name).variable
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
    def _field_names(self) -> tuple[ProviderField, ...]:
        """Get the field names for provider settings."""
        return ("data", "embedding", "sparse_embedding", "reranking", "vector_store", "agent")

    @property
    def provider_configs(self) -> dict[ProviderField, tuple[BaseProviderSettings, ...] | None]:
        """Get a summary of configured provider settings by kind."""
        configs: dict[ProviderField, tuple[BaseProviderSettings, ...] | None] = {}
        for field in self._field_names:
            setting = self.settings_for_kind(field)
            if setting is None or setting is Unset:
                continue
            # Normalize to tuple form
            configs[field] = setting if isinstance(setting, tuple) else (setting,)  # ty:ignore[invalid-assignment]
        return configs or None  # type: ignore[return-value]

    @property
    def provider_name_map(self) -> ProviderNameMap:
        """Get a summary of configured providers by kind."""
        provider_data: dict[ProviderField, Provider | tuple[Provider, ...] | None] = {
            field_name: (
                tuple(s.provider for s in setting if setting and is_typeddict(s))  # type: ignore
                if isinstance(setting, tuple)
                else (setting["provider"] if setting else None)
            )
            for field_name, setting in self.provider_configs.items()
        }

        return ProviderNameMap(**provider_data)  # type: ignore

    def get_provider_settings(
        self, provider: Provider
    ) -> BaseProviderSettings | tuple[BaseProviderSettings, ...] | None:
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
        all_settings: list[BaseProviderSettings] = []
        for field in matching_fields:
            if setting := self.settings_for_kind(field):
                if isinstance(setting, tuple):
                    all_settings.extend(setting)  # ty:ignore[invalid-argument-type]
                else:
                    all_settings.append(setting)

        return (
            all_settings[0]
            if len(all_settings) == 1
            else tuple(all_settings)
            if all_settings
            else None
        )

    def has_auth_configured(self, provider: Provider) -> bool:
        """Check if API key or TLS certs are set for the provider through settings or environment."""
        if not (settings := self.get_provider_settings(provider)):
            return False
        settings = settings if isinstance(settings, tuple) else (settings,)
        return next(
            (True for setting in settings if isinstance(setting.get("api_key"), SecretStr)),
            provider.has_env_auth,
        )

    def settings_for_kind(
        self, kind: ProviderField | LiteralProviderKindType
    ) -> BaseProviderSettings | tuple[BaseProviderSettings, ...] | None:
        """Get the settings for a specific provider kind.

        Args:
            kind: The kind of provider or ProviderKind to get settings for.
        """
        setting_field = (
            kind
            if kind
            in {"data", "embedding", "sparse_embedding", "reranking", "vector_store", "agent"}
            else cast(ProviderKind, kind).variable
        )
        setting = getattr(self, setting_field, None)  # type: ignore
        return None if setting is Unset else setting  # type: ignore


AllDefaultProviderSettings = ProviderSettingsDict(
    data=DefaultDataProviderSettings,
    embedding=DefaultEmbeddingProviderSettings,
    sparse_embedding=DefaultSparseEmbeddingProviderSettings,
    reranking=DefaultRerankingProviderSettings,
    agent=DefaultAgentProviderSettings,
)


__all__ = (
    "AgentProviderSettingsType",
    "AllDefaultProviderSettings",
    "DataProviderSettingsType",
    "EmbeddingProviderSettingsType",
    "ProviderSettings",
    "ProviderSettingsDict",
    "ProviderSettingsView",
    "RerankingProviderSettingsType",
    "VectorStoreProviderSettingsType",
    "merge_agent_model_settings",
)

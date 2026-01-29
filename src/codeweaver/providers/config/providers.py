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
import os

from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
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
    BasedModel,
    DictView,
    LiteralProviderKindType,
    Provider,
    ProviderKind,
    Unset,
)
from codeweaver.core.types import ModelName, ModelNameT


if TYPE_CHECKING:
    pass
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
    CollectionConfig,
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

# Embedding Providers - flattened union for pydantic discrimination


def _discriminate_embedding_provider(v: Any) -> str:
    """Identify the embedding provider settings type for discriminator field."""
    tag_value = v.get("tag") if isinstance(v, dict) else getattr(v, "tag", None)
    if tag_value in {
        Provider.AZURE.variable,
        Provider.BEDROCK.variable,
        Provider.FASTEMBED.variable,
    }:
        return tag_value
    return "none"


type EmbeddingProviderSettingsType = Annotated[
    Annotated[EmbeddingProviderSettings, Tag("none")]
    | Annotated[AzureEmbeddingProviderSettings, Tag(Provider.AZURE.variable)]
    | Annotated[BedrockEmbeddingProviderSettings, Tag(Provider.BEDROCK.variable)]
    | Annotated[FastEmbedEmbeddingProviderSettings, Tag(Provider.FASTEMBED.variable)],
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

# Reranking Providers - flattened union for pydantic discrimination


def _discriminate_reranking_provider(v: Any) -> str:
    """Identify the reranking provider settings type for discriminator field."""
    tag_value = v.get("tag") if isinstance(v, dict) else getattr(v, "tag", None)
    if tag_value in {Provider.FASTEMBED.variable, Provider.BEDROCK.variable}:
        return tag_value
    return "none"


type RerankingProviderSettingsType = Annotated[
    Annotated[RerankingProviderSettings, Tag("none")]
    | Annotated[FastEmbedRerankingProviderSettings, Tag(Provider.FASTEMBED.variable)]
    | Annotated[BedrockRerankingProviderSettings, Tag(Provider.BEDROCK.variable)],
    Field(
        description="Reranking provider settings type.",
        discriminator=Discriminator(_discriminate_reranking_provider),
    ),
]

# ===== Data and Agent Providers (no discrimination needed) =====

# Agent and Data providers use base classes without subclasses,
# so they don't need discriminated unions. The tuple type is sufficient.
type DataProviderSettingsType = DataProviderSettings

type AgentProviderSettingsType = AgentProviderSettings

# ===========================================================================
# *                    More TypedDict versions of Models
# ===========================================================================


class ProviderSettingsDict(TypedDict, total=False):
    """A dictionary representation of provider settings."""

    data: NotRequired[tuple[DataProviderSettingsType, ...] | None]
    # we currently only support one each of embedding, reranking and vector store providers
    # but we use tuples to allow for future expansion for some less common use cases
    embedding: NotRequired[tuple[EmbeddingProviderSettingsType, ...] | None]
    asymmetric_embedding: NotRequired[AsymmetricEmbeddingConfig | None]
    # rerank is probably the priority for multiple providers in the future, because they're vector agnostic, so you could have fallback providers, or use different ones for different tasks
    sparse_embedding: NotRequired[tuple[SparseEmbeddingProviderSettingsType, ...] | None]
    reranking: NotRequired[tuple[RerankingProviderSettingsType, ...] | None]

    vector_store: NotRequired[tuple[VectorStoreProviderSettingsType, ...] | None]
    agent: NotRequired[tuple[AgentProviderSettingsType, ...] | None]


type ProviderSettingsView = DictView[ProviderSettingsDict]


def merge_agent_model_settings(
    base: AgentModelSettings | None, override: AgentModelSettings | None
) -> AgentModelSettings | None:
    """A convenience re-export of `merge_model_settings` for agent model settings."""
    return merge_model_settings(base, override)


def _create_default_data_provider_settings() -> tuple[DataProviderSettings, ...]:
    """Create default data provider settings (delayed initialization)."""
    return (
        DataProviderSettings(provider=Provider.TAVILY),
        # DuckDuckGo
        DataProviderSettings(provider=Provider.DUCKDUCKGO),
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
        "fastembed-gpu",
        "fastembed",
        "sentence-transformers",
    ):
        if importlib.util.find_spec(lib) is not None:
            # all three of the top defaults are extremely capable and finetuned for code tasks
            if lib == "voyageai":
                return DeterminedDefaults(
                    provider=Provider.VOYAGE, model=ModelName("voyage-code-3"), enabled=True
                )
            if lib == "mistral":
                return DeterminedDefaults(
                    provider=Provider.MISTRAL, model=ModelName("codestral-embed"), enabled=True
                )
            if lib == "google":
                return DeterminedDefaults(
                    provider=Provider.GOOGLE, model=ModelName("gemini-embedding-001"), enabled=True
                )
            if lib in {"fastembed-gpu", "fastembed"}:
                return DeterminedDefaults(
                    provider=Provider.FASTEMBED,
                    model=ModelName("BAAI/bge-small-en-v1.5"),
                    enabled=True,
                )
            if lib == "sentence-transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    # embedding-small-english-r2 is *very lightweight* and quite capable with a good context window (8192 tokens)
                    # Good upgrade from the likes of all-minilm-L6-v2 while still being very efficient
                    model=ModelName("ibm-granite/granite-embedding-small-english-r2"),
                    enabled=True,
                )
    logger.warning(
        "No default embedding provider libraries found. Embedding functionality will be disabled unless explicitly set in your config or environment variables."
    )
    return DeterminedDefaults(provider=Provider.NOT_SET, model=ModelName("NONE"), enabled=False)


_embedding_defaults = _get_default_embedding_settings()


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
            model_name=_embedding_defaults.model,  # ty:ignore[invalid-argument-type]
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
    for lib in ("sentence-transformers", "fastembed-gpu", "fastembed"):
        if importlib.util.find_spec(lib) is not None:
            if lib == "sentence-transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    model=ModelName("opensearch/opensearch-neural-sparse-encoding-doc-v3-gte"),
                    enabled=True,
                )
            if lib in {"fastembed-gpu", "fastembed"}:
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
            model_name=_sparse_embedding_defaults.model,  # ty:ignore[invalid-argument-type]
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
    for lib in ("voyageai", "fastembed-gpu", "fastembed", "sentence-transformers"):
        if importlib.util.find_spec(lib) is not None:
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
            model_name=_reranking_defaults.model,  # ty:ignore[invalid-argument-type]
            reranking_config=_create_reranking_config(
                _reranking_defaults.provider,
                _reranking_defaults.model,  # ty:ignore[invalid-argument-type]
            ),
        ),
    )


DefaultRerankingProviderSettings: tuple[RerankingProviderSettings, ...] | None = (
    None  # Will be lazy-initialized
)

HAS_ANTHROPIC = (
    importlib.util.find_spec("anthropic") or importlib.util.find_spec("claude-agent-sdk")
) is not None


def _get_default_agent_provider_settings() -> tuple[AgentProviderSettings, ...] | None:
    """Get default agent provider settings (delayed instantiation)."""
    if not HAS_ANTHROPIC:
        return None
    # Don't instantiate AgentModelSettings here to avoid forward reference issues
    return (
        AgentProviderSettings(
            provider=Provider.ANTHROPIC,
            model="claude-haiku-4.5-latest",
            model_options=None,  # Use None to avoid forward reference validation
        ),
    )


DefaultAgentProviderSettings: tuple[AgentProviderSettings, ...] | None = (
    None  # Will be lazy-initialized
)


def _get_default_vector_store_provider_settings() -> tuple[QdrantVectorStoreProviderSettings, ...]:
    """Get default vector store provider settings (delayed instantiation)."""
    return (
        QdrantVectorStoreProviderSettings(
            provider=Provider.QDRANT,
            client_options=QdrantClientOptions(host="127.0.0.1"),
            collection=CollectionConfig(),
        ),
    )


DefaultVectorStoreProviderSettings: tuple[QdrantVectorStoreProviderSettings, ...] | None = (
    None  # Will be lazy-initialized
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
        tuple[DataProviderSettings, ...] | None,
        Field(description="""Data provider configuration"""),
    ] = None  # TODO: Add default_factory after fixing model_rebuild issue

    embedding: Annotated[
        tuple[EmbeddingProviderSettingsType, ...] | None,
        Field(
            description="""Embedding provider configuration (symmetric mode).

            Symmetric mode uses the same model for both document and query embeddings.
            This is the traditional approach where a single model handles all embedding tasks.

            We will only use the first provider you configure here. We may add support for multiple embedding providers in the future.

            Note: Cannot be used simultaneously with 'asymmetric_embedding' field.
            Choose one mode based on your requirements:
              - Symmetric: Single model, simpler configuration
              - Asymmetric: Different models for documents and queries, cost optimization

            Example TOML configuration (symmetric):
              [providers.embedding.0]
              provider = "voyage"
              model_name = "voyage-code-3"
            """,
            default_factory=_get_default_embedding_provider_settings,
        ),
    ]

    asymmetric_embedding: Annotated[
        AsymmetricEmbeddingConfig | None,
        Field(
            description="""Asymmetric embedding configuration (advanced mode).

            Asymmetric mode allows using different models for document embedding and query
            embedding while maintaining compatibility through shared vector spaces. This enables
            cost optimization (e.g., API-based model for document indexing, local model for queries)
            while preserving search accuracy.

            Requirements:
              - Both models must belong to the same model family (e.g., Voyage-4)
              - Models must be explicitly marked as compatible for asymmetric use
              - Embedding dimensions must match (validated automatically)

            Benefits:
              - Cost optimization: expensive models for documents, cheap for queries
              - Performance: local models for queries, API for indexing
              - Resource flexibility: different deployment strategies per model

            Note: Cannot be used simultaneously with 'embedding' field.
            Choose one mode based on your requirements:
              - Symmetric: Single model, simpler configuration
              - Asymmetric: Different models, cost/performance optimization

            Example TOML configuration (asymmetric):
              [providers.asymmetric_embedding]
              validate_family_compatibility = true

              [providers.asymmetric_embedding.embed_provider_settings]
              provider = "voyage"
              model_name = "voyage-code-3"

              [providers.asymmetric_embedding.query_provider_settings]
              provider = "voyage"
              model_name = "voyage-code-3-lite"

            See documentation: docs/configuration/asymmetric-embedding.md
            """,
            default=None,
        ),
    ]

    sparse_embedding: Annotated[
        tuple[SparseEmbeddingProviderSettingsType, ...] | None,
        Field(
            description="""Sparse embedding provider configuration.

            We will only use the first provider you configure here. We may add support for multiple sparse embedding providers in the future.""",
            default_factory=_get_default_sparse_embedding_provider_settings,
        ),
    ]

    reranking: Annotated[
        tuple[RerankingProviderSettingsType, ...] | None,
        Field(
            description="""Reranking provider configuration.

            We will only use the first provider you configure here. We may add support for multiple reranking providers in the future.""",
            default_factory=_get_default_reranking_provider_settings,
        ),
    ]

    vector_store: Annotated[
        tuple[VectorStoreProviderSettingsType, ...] | None,
        Field(
            description="""Vector store provider configuration (Qdrant or in-memory), defaults to a local Qdrant instance.""",
            default_factory=_get_default_vector_store_provider_settings,
        ),
    ]

    agent: Annotated[
        tuple[AgentProviderSettings, ...] | None,
        Field(
            description="""Agent provider configuration""",
            default_factory=_get_default_agent_provider_settings,
        ),
    ]

    disable_backup_system: Annotated[
        bool,
        Field(
            description="""Disable CodeWeaver's failsafe/backup system.

            CodeWeaver's backup system uses extremely lightweight local models to provide basic functionality when your main provider is unavailable (well, it is still probably better than most alternatives). Specifically, it keeps an alternate local vector store collection and uses the smallest available embedding, sparse embedding, and reranking models to provide basic functionality when the main providers are unreachable. This system keeps a a low-resource, always-available fallback that can be used offline or when cloud providers are unreachable.

            If you use a cloud vector store, the backup will be an in-memory vector store that is loaded and persisted from json. If you use a local vector store, the backup will be a separate collection in that vector store.

            If you set `disable_backup_system` to `True`, don't complain if CodeWeaver stops working when your main providers are unreachable!
            """
        ),
    ] = os.environ.get("CODEWEAVER_DISABLE_BACKUP_SYSTEM", "false").lower() in ("1", "true", "yes")

    def __init__(self, **data: Any) -> None:
        """Initialize ProviderSettings and register with DI container if available."""
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
        for key in self._field_names:
            value = getattr(self, key)
            if value is None:
                continue
            if value is Unset:
                default_value = AllDefaultProviderSettings.get(key)
                setattr(self, key, default_value)
                value = default_value
            if not isinstance(value, tuple):
                value = (value,)
                setattr(self, key, value)
        return self

    @model_validator(mode="after")
    def validate_embedding_mode_exclusivity(self) -> ProviderSettings:
        """Validate that only one embedding mode is configured at a time.

        Ensures mutual exclusivity between symmetric ('embedding') and asymmetric
        ('asymmetric_embedding') embedding configurations to prevent ambiguous
        provider selection and configuration conflicts.

        Returns:
            Self for method chaining.

        Raises:
            ConfigurationError: If both embedding modes are configured simultaneously.
        """
        from codeweaver.core.exceptions import ConfigurationError

        has_symmetric = self.embedding is not None and self.embedding is not Unset
        has_asymmetric = self.asymmetric_embedding is not None

        if has_symmetric and has_asymmetric:
            logger.error(
                "Configuration conflict: Both 'embedding' and 'asymmetric_embedding' are set. "
                "Only one embedding mode can be active at a time."
            )
            raise ConfigurationError(
                "Cannot specify both 'embedding' and 'asymmetric_embedding' configuration. "
                "Choose one mode:\n\n"
                "  Symmetric mode (traditional):\n"
                "    Use 'embedding' field for single model or fallback chain.\n"
                "    Same model used for both document and query embeddings.\n"
                "    Simpler configuration, works with any embedding model.\n\n"
                "  Asymmetric mode (advanced):\n"
                "    Use 'asymmetric_embedding' field for different models.\n"
                "    Requires model family compatibility (e.g., Voyage-4).\n"
                "    Optimizes for cost/performance trade-offs.\n"
                "    Different models for indexing vs querying.\n",
                details={
                    "symmetric_configured": has_symmetric,
                    "asymmetric_configured": has_asymmetric,
                    "embedding_providers": (
                        [str(s.provider) for s in self.embedding]  # ty:ignore[not-iterable]
                        if has_symmetric and self.embedding
                        else None
                    ),
                    "asymmetric_embed_provider": (
                        str(self.asymmetric_embedding.embed_provider_settings.provider)
                        if has_asymmetric and self.asymmetric_embedding
                        else None
                    ),
                    "asymmetric_query_provider": (
                        str(self.asymmetric_embedding.query_provider_settings.provider)
                        if has_asymmetric and self.asymmetric_embedding
                        else None
                    ),
                },
                suggestions=[
                    "Remove 'embedding' field to use asymmetric mode",
                    "Remove 'asymmetric_embedding' field to use symmetric mode",
                    "For most use cases, symmetric mode (embedding) is recommended",
                    "Use asymmetric mode only if you need different models for documents and queries",
                    "See documentation: docs/configuration/asymmetric-embedding.md",
                ],
            )

        # Log the selected mode for debugging
        if has_symmetric:
            logger.debug("Using symmetric embedding mode with providers: %s", self.embedding)
        elif has_asymmetric:
            logger.debug(
                "Using asymmetric embedding mode: embed=%s, query=%s",
                self.asymmetric_embedding.embed_provider_settings.provider,
                self.asymmetric_embedding.query_provider_settings.provider,
            )
        else:
            logger.debug("No embedding configuration specified")

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
    def _all_configs(self) -> tuple[BaseProviderSettings, ...]:
        """Get all provider settings as a flat tuple."""
        return tuple(
            setting
            for configs in self.provider_configs.values()
            if configs
            for setting in (configs if isinstance(configs, tuple) else (configs,))
        )

    @property
    def provider_configs(self) -> dict[ProviderField, tuple[BaseProviderSettings, ...]]:
        """Get a summary of configured provider settings by kind."""
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

    def settings_for_provider(
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
        if not (settings := self.settings_for_provider(provider)):
            return False
        settings = settings if isinstance(settings, tuple) else (settings,)
        return next(
            (True for setting in settings if isinstance(setting.get("api_key"), SecretStr)),
            provider.has_env_auth,
        )

    def settings_for_kind(
        self,
        kind: ProviderField | LiteralProviderKindType,
        *,
        primary: bool = True,
        backup: bool = False,
    ) -> BaseProviderSettings | tuple[BaseProviderSettings, ...] | None:
        """Get the settings for a specific provider kind.

        Args:
            kind: The kind of provider or ProviderKind to get settings for.
            primary: Whether to return the primary settings or all settings.
            backup: Whether to return the backup settings instead of the primary.
        """
        setting_field = (
            kind
            if kind
            in {"data", "embedding", "sparse_embedding", "reranking", "vector_store", "agent"}
            else cast(ProviderKind, kind).variable
        )
        setting = getattr(self, setting_field, None)  # type: ignore
        if setting is None:
            return None
        if setting is Unset:
            setting = AllDefaultProviderSettings.get(setting_field)  # type: ignore
            setattr(self, setting_field, setting)  # type: ignore
        if primary and isinstance(setting, tuple) and len(setting) > 0:
            return setting[0]
        if backup:
            return setting[1] if isinstance(setting, tuple) and len(setting) > 1 else None
        return setting

    def apply_profile(self, profile: Literal["recommended", "quickstart", "testing"]) -> None:
        """Apply a premade provider profile to the settings.

        Profiles are predefined sets of provider configurations that can be applied
        to quickly set up the environment for different use cases, and can be applied on top
        of existing settings.

        Args:
            profile: The profile to apply.
        """


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


class AsymmetricEmbeddingConfigDict(TypedDict):
    """Dictionary representation of asymmetric embedding configuration."""

    embed_provider_settings: EmbeddingProviderSettingsType
    query_provider_settings: EmbeddingProviderSettingsType
    validate_family_compatibility: bool


class AsymmetricEmbeddingConfig(BasedModel):
    """Configuration for asymmetric embedding setup with separate embed and query models.

    Asymmetric embedding allows using different models for document embedding and query
    embedding while maintaining compatibility through shared vector spaces. This enables
    cost optimization (e.g., API for embed, local for queries) while preserving accuracy.

    Attributes:
        embed_provider_settings: Provider settings for document embedding model.
        query_provider_settings: Provider settings for query embedding model.
        validate_family_compatibility: Whether to validate models belong to same family.
    """

    model_config = BasedModel.model_config

    embed_provider_settings: Annotated[
        EmbeddingProviderSettingsType,
        Field(description="Provider settings for the document embedding model."),
    ]
    query_provider_settings: Annotated[
        EmbeddingProviderSettingsType,
        Field(description="Provider settings for the query embedding model."),
    ]
    validate_family_compatibility: Annotated[
        bool,
        Field(description="Whether to validate that both models belong to the same model family."),
    ] = True

    @model_validator(mode="after")
    def validate_model_compatibility(self) -> AsymmetricEmbeddingConfig:
        """Validate that embed and query models are compatible.

        Validates:
        - Both models have registered capabilities
        - Both models belong to model families
        - Both models belong to the same family
        - Models are compatible within the family
        - Embedding dimensions match

        Returns:
            Self for method chaining.

        Raises:
            ConfigurationError: If models are incompatible.
        """
        from codeweaver.core.exceptions import ConfigurationError
        from codeweaver.providers.embedding.capabilities.resolver import EmbeddingCapabilityResolver

        if not self.validate_family_compatibility:
            logger.warning(
                "Family compatibility validation disabled for asymmetric embedding config. "
                "This may result in incompatible embeddings if models are from different families."
            )
            return self

        # Resolve capabilities for both models
        resolver = EmbeddingCapabilityResolver()
        embed_model_name = str(self.embed_provider_settings.model_name)
        query_model_name = str(self.query_provider_settings.model_name)

        embed_caps = resolver.resolve(embed_model_name)
        query_caps = resolver.resolve(query_model_name)

        # Verify both models have capabilities registered
        if not embed_caps:
            raise ConfigurationError(
                f"No capabilities found for embed model: {embed_model_name}",
                details={
                    "embed_model": embed_model_name,
                    "query_model": query_model_name,
                    "provider": self.embed_provider_settings.provider.value,
                },
                suggestions=[
                    f"Ensure model '{embed_model_name}' is registered in the capabilities system",
                    "Check that the model name is spelled correctly",
                    "Verify the provider supports this model",
                    "List available models with: codeweaver list models",
                ],
            )

        if not query_caps:
            raise ConfigurationError(
                f"No capabilities found for query model: {query_model_name}",
                details={
                    "embed_model": embed_model_name,
                    "query_model": query_model_name,
                    "provider": self.query_provider_settings.provider.value,
                },
                suggestions=[
                    f"Ensure model '{query_model_name}' is registered in the capabilities system",
                    "Check that the model name is spelled correctly",
                    "Verify the provider supports this model",
                    "List available models with: codeweaver list models",
                ],
            )

        # Verify both models belong to families
        if not embed_caps.model_family:  # ty:ignore[unresolved-attribute]
            raise ConfigurationError(
                f"Embed model '{embed_model_name}' does not belong to a model family",
                details={"embed_model": embed_model_name, "query_model": query_model_name},
                suggestions=[
                    "Asymmetric embedding requires both models to belong to a model family",
                    "Use symmetric embedding configuration for models without family support",
                    "Check if a newer version of the model has family support",
                ],
            )

        if not query_caps.model_family:  # ty:ignore[unresolved-attribute]
            raise ConfigurationError(
                f"Query model '{query_model_name}' does not belong to a model family",
                details={"embed_model": embed_model_name, "query_model": query_model_name},
                suggestions=[
                    "Asymmetric embedding requires both models to belong to a model family",
                    "Use symmetric embedding configuration for models without family support",
                    "Check if a newer version of the model has family support",
                ],
            )

        # Verify same family ID
        embed_family = embed_caps.model_family  # ty:ignore[unresolved-attribute]
        query_family = query_caps.model_family  # ty:ignore[unresolved-attribute]

        if embed_family.family_id != query_family.family_id:
            raise ConfigurationError(
                f"Models belong to different families: '{embed_family.family_id}' vs '{query_family.family_id}'",
                details={
                    "embed_model": embed_model_name,
                    "embed_family": embed_family.family_id,
                    "query_model": query_model_name,
                    "query_family": query_family.family_id,
                },
                suggestions=[
                    f"Use models from the same family (e.g., both from '{embed_family.family_id}')",
                    f"Available members of '{embed_family.family_id}': {', '.join(sorted(embed_family.member_models))}",
                    "Set validate_family_compatibility=False to bypass this check (not recommended)",
                ],
            )

        # Verify models are compatible within family
        if not embed_family.is_compatible(embed_model_name, query_model_name):
            raise ConfigurationError(
                f"Models are not compatible within family '{embed_family.family_id}'",
                details={
                    "embed_model": embed_model_name,
                    "query_model": query_model_name,
                    "family_id": embed_family.family_id,
                    "family_members": sorted(embed_family.member_models),
                },
                suggestions=[
                    "Ensure both models are listed as family members",
                    f"Valid family members: {', '.join(sorted(embed_family.member_models))}",
                    "Contact support if you believe this is an error",
                ],
            )

        # Verify dimensions match
        embed_dim = embed_caps.default_dimension
        query_dim = query_caps.default_dimension

        is_valid, error_msg = embed_family.validate_dimensions(embed_dim, query_dim)
        if not is_valid:
            raise ConfigurationError(
                f"Dimension mismatch: {error_msg}",
                details={
                    "embed_model": embed_model_name,
                    "embed_dimension": embed_dim,
                    "query_model": query_model_name,
                    "query_dimension": query_dim,
                    "expected_dimension": embed_family.vector_space_dimension,
                    "family_id": embed_family.family_id,
                },
                suggestions=[
                    "Ensure both models use the same embedding dimension",
                    f"Expected dimension for '{embed_family.family_id}': {embed_family.vector_space_dimension}",
                    "Check model configurations and verify dimension settings",
                ],
            )

        logger.info(
            "Asymmetric embedding configuration validated successfully: "
            "embed_model='%s', query_model='%s', family='%s', dimension=%d",
            embed_model_name,
            query_model_name,
            embed_family.family_id,
            embed_dim,
        )

        return self

    def _telemetry_keys(self) -> None:
        return None


__all__ = (
    "AgentProviderSettingsType",
    "AllDefaultProviderSettings",
    "AsymmetricEmbeddingConfig",
    "AsymmetricEmbeddingConfigDict",
    "DataProviderSettingsType",
    "EmbeddingProviderSettingsType",
    "ProviderSettings",
    "ProviderSettingsDict",
    "ProviderSettingsView",
    "RerankingProviderSettingsType",
    "VectorStoreProviderSettingsType",
    "merge_agent_model_settings",
)

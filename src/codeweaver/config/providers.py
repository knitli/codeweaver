# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""TypedDict classes for provider settings.

Provides configuration settings for all supported providers, including embedding models, reranking models, and agent models.
"""

from __future__ import annotations

import importlib.util as util
import logging

from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    NamedTuple,
    NotRequired,
    Required,
    TypedDict,
    cast,
    is_typeddict,
)

from pydantic import Field, PositiveFloat, PositiveInt, SecretStr, computed_field
from pydantic_ai.settings import ModelSettings as AgentModelSettings
from pydantic_ai.settings import merge_model_settings

from codeweaver.core.types import DictView
from codeweaver.core.types.models import BasedModel
from codeweaver.core.types.sentinel import Unset
from codeweaver.providers.provider import Provider


if TYPE_CHECKING:
    from codeweaver.common.registry.types import LiteralKinds


logger = logging.getLogger(__name__)

# ===========================================================================
# *            Provider Connection and Rate Limit Settings
# ===========================================================================


class ConnectionRateLimitConfig(TypedDict, total=False):
    """Settings for connection rate limiting."""

    max_requests_per_second: PositiveInt | None
    burst_capacity: PositiveInt | None
    backoff_multiplier: PositiveFloat | None
    max_retries: PositiveInt | None


class ConnectionConfiguration(TypedDict, total=False):
    """Settings for connection configuration. Only required for non-default transports."""

    host: str | None
    port: PositiveInt | None
    headers: NotRequired[dict[str, str] | None]
    rate_limits: NotRequired[ConnectionRateLimitConfig | None]


class BaseProviderSettings(TypedDict, total=False):
    """Base settings for all providers."""

    provider: Required[Provider]
    enabled: NotRequired[bool]
    api_key: NotRequired[SecretStr | None]
    connection: NotRequired[ConnectionConfiguration | None]
    client_options: NotRequired[dict[str, Any] | None]
    """Options to pass to the provider's client (like to `qdrant_client` for qdrant) as keyword arguments. You should refer to the provider's documentation for what options are available."""
    other: NotRequired[dict[str, Any] | None]
    """Other provider-specific settings. This is primarily for user-defined providers to pass custom options."""


# ===========================================================================
# *            Provider Settings classes
# ===========================================================================


class DataProviderSettings(BaseProviderSettings):
    """Settings for data providers."""


class EmbeddingModelSettings(TypedDict, total=False):
    """Embedding model settings. Use this class for dense (vector) models."""

    model: Required[str]
    dimension: NotRequired[PositiveInt | None]
    data_type: NotRequired[str | None]
    custom_prompt: NotRequired[str | None]
    """A custom prompt to use for the embedding model, if supported. Most models do not support custom prompts for embedding."""
    embed_options: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the *provider* **client's** (like `voyageai.async_client.AsyncClient`) `embed` method. These are different from `model_options`, which are passed to the model constructor itself."""
    model_options: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the model's constructor."""


class SparseEmbeddingModelSettings(TypedDict, total=False):
    """Sparse embedding model settings. Use this class for sparse (e.g. bag-of-words) models."""

    model: Required[str]
    embed_options: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the *provider* **client's** (like `sentence_transformers.SparseEncoder`) `embed` method. These are different from `model_options`, which are passed to the model constructor itself."""
    model_options: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the model's constructor."""


class RerankingModelSettings(TypedDict, total=False):
    """Rerank model settings."""

    model: Required[str]
    custom_prompt: NotRequired[str | None]
    rerank_options: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the *provider* **client's** (like `voyageai.async_client.AsyncClient`) `rerank` method."""
    client_options: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the *provider* **client's** (like `voyageai.async_client.AsyncClient`) constructor."""
    model_options: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the model's constructor."""


class AWSProviderSettings(TypedDict, total=False):
    """Settings for AWS provider.

    You need to provide these settings if you are using Bedrock, and you need to provide them for each Bedrock model you use. It might be repetitive, but a lot of people have different credentials for different models/services.
    """

    region_name: Required[str]
    model_arn: Required[str]
    aws_access_key_id: NotRequired[SecretStr | None]
    """Optional AWS access key ID. If not provided, we'll assume you have you have your AWS credentials configured in another way, such as environment variables, AWS config files, or IAM roles."""
    aws_secret_access_key: NotRequired[SecretStr | None]
    """Optional AWS secret access key. If not provided, we'll assume you have you have your AWS credentials configured in another way, such as environment variables, AWS config files, or IAM roles."""
    aws_session_token: NotRequired[SecretStr | None]
    """Optional AWS session token. If not provided, we'll assume you have you have your AWS credentials configured in another way, such as environment variables, AWS config files, or IAM roles."""


class AzureCohereProviderSettings(TypedDict, total=False):
    """Provider settings for Azure Cohere.

    You need to provide these settings if you are using Azure Cohere, and you need to provide them for each Azure Cohere model you use.
    They're **all required**. They're marked `NotRequired` in the TypedDict because you can also provide them by environment variables, but you must provide them one way or another.
    """

    model_deployment: NotRequired[str]
    """The deployment name of the model you want to use. Important: While the OpenAI API uses the model name to identify the model, you must separately provide a codeweaver-compatible name for the model, as well as your Azure resource name here. We're open to PRs if you want to add a parser for model names that can extract the deployment name from them."""
    api_key: NotRequired[SecretStr | None]
    """Your Azure API key. If not provided, we'll assume you have your Azure credentials configured in another way, such as environment variables."""
    azure_resource_name: NotRequired[str]
    """The name of your Azure resource. This is used to identify your resource in Azure."""
    azure_endpoint: NotRequired[str]
    """The endpoint for your Azure resource. This is used to send requests to your resource. Only provide the endpoint, not the full URL. For example, if your endpoint is `https://your-cool-resource.<region_name>.inference.ai.azure.com/v1`, you would only provide "your-cool-resource" here."""
    region_name: NotRequired[str]
    """The Azure region where your resource is located. This is used to route requests to the correct regional endpoint."""


class AzureOpenAIProviderSettings(TypedDict, total=False):
    """Provider settings for Azure OpenAI.

    You need to provide these settings if you are using Azure OpenAI, and you need to provide them for each Azure OpenAI model you use.

    **For embedding models:**
    **We only support the "**next-generation** Azure OpenAI API." Currently, you need to opt into this API in your Azure settings. We didn't want to start supporting the old API knowing it's going away.

    For agent models:
    We support both APIs for agentic models because our support comes from `pydantic_ai`, which supports both.
    """

    azure_resource_name: NotRequired[str]
    """The name of your Azure resource. This is used to identify your resource in Azure."""
    model_deployment: NotRequired[str]
    """The deployment name of the model you want to use. Important: While the OpenAI API uses the model name to identify the model, you must separately provide a codeweaver-compatible name for the model, as well as your Azure resource name here. We're open to PRs if you want to add a parser for model names that can extract the deployment name from them."""
    endpoint: NotRequired[str | None]
    """The endpoint for your Azure resource. This is used to send requests to your resource. Only provide the endpoint, not the full URL. For example, if your endpoint is `https://your-cool-resource.<region_name>.inference.ai.azure.com/v1`, you would only provide "your-cool-resource" here."""
    region_name: NotRequired[str]
    """The Azure region where your resource is located. This is used to route requests to the correct regional endpoint."""
    api_key: NotRequired[SecretStr | None]
    """Your Azure API key. If not provided, we'll assume you have your Azure credentials configured in another way, such as environment variables."""


class FastembedGPUProviderSettings(TypedDict, total=False):
    """Special settings for Fastembed-GPU provider.

    These settings only apply if you are using a Fastembed provider, installed the `codeweaver-mcp[provider-fastembed-gpu]` extra, have a CUDA-capable GPU, and have properly installed and configured the ONNX GPU runtime.
    You can provide these settings with your CodeWeaver embedding provider settings, or rerank provider settings. If you're using fastembed-gpu for both, we'll assume you are using the same settings for both if we find one of them.
    """

    cuda: NotRequired[bool | None]
    """Whether to use CUDA (if available). If `None`, will auto-detect. We'll generally assume you want to use CUDA if it's available unless you provide a `False` value here."""
    provider_settings: NotRequired[list[int] | None]
    """List of GPU device IDs to use. If `None`, we will try to detect available GPUs using `nvidia-smi` if we can find it. We recommend specifying them because our checks aren't perfect."""


# ===========================================================================
# *            Vector Store Provider Settings
# ===========================================================================


class QdrantConfig(TypedDict, total=False):
    """Configuration for Qdrant vector store provider."""

    url: NotRequired[str | None]
    """Qdrant server URL. Defaults to http://localhost:6333 if not specified."""
    api_key: NotRequired[SecretStr | None]
    """API key for authentication (required for remote instances unless you have custom authentication for a private instance)."""
    collection_name: NotRequired[str | None]
    """Collection name override. Defaults to project name if not specified."""
    prefer_grpc: NotRequired[bool]
    """Use gRPC instead of HTTP. Defaults to False."""
    batch_size: NotRequired[PositiveInt]
    """Batch size for bulk upsert operations. Defaults to 64."""
    dense_vector_name: NotRequired[str]
    """Named vector for dense embeddings. Defaults to 'dense'."""
    sparse_vector_name: NotRequired[str]
    """Named vector for sparse embeddings. Defaults to 'sparse'."""
    client_options: NotRequired[dict[str, Any] | None]
    """Additional keyword arguments to pass to the Qdrant client."""


class MemoryConfig(TypedDict, total=False):
    """Configuration for in-memory vector store provider."""

    persist_path: NotRequired[str]
    """Path for JSON persistence file. Defaults to {system_user_config}/codeweaver/{project_name}_vector_store.json."""
    auto_persist: NotRequired[bool]
    """Automatically save after operations. Defaults to True."""
    persist_interval: NotRequired[PositiveInt | None]
    """Periodic persist interval in seconds. Defaults to 300 (5 minutes). Set to None to disable periodic persistence."""
    collection_name: NotRequired[str]
    """Collection name override. Defaults to project name if not specified."""


type ProviderSpecificSettings = (
    FastembedGPUProviderSettings
    | AWSProviderSettings
    | AzureOpenAIProviderSettings
    | AzureCohereProviderSettings
)


class EmbeddingProviderSettings(BaseProviderSettings):
    """Settings for (dense) embedding models. It validates that the model and provider settings are compatible and complete, reconciling environment variables and config file settings as needed."""

    model_settings: Required[EmbeddingModelSettings]
    """Settings for the embedding model(s)."""
    provider_settings: NotRequired[ProviderSpecificSettings | None]
    """Settings for specific providers, if any. Some providers have special settings that are required for them to work properly, but you may provide them by environment variables as well as in your config, or both."""


class SparseEmbeddingProviderSettings(BaseProviderSettings):
    """Settings for sparse embedding models."""

    model_settings: Required[SparseEmbeddingModelSettings]
    """Settings for the sparse embedding model(s)."""
    provider_settings: NotRequired[ProviderSpecificSettings | None]


class RerankingProviderSettings(BaseProviderSettings):
    """Settings for re-ranking models."""

    model_settings: Required[RerankingModelSettings]
    """Settings for the re-ranking model(s)."""
    provider_settings: NotRequired[ProviderSpecificSettings | None]
    top_n: NotRequired[PositiveInt | None]


class VectorStoreProviderSettings(BaseProviderSettings, total=False):
    """Settings for vector store provider selection and configuration."""

    """Vector store provider: Provider.QDRANT or Provider.MEMORY. Defaults to Provider.QDRANT."""
    provider_settings: Required[QdrantConfig | MemoryConfig]


# Agent model settings are imported/defined from `pydantic_ai`

type ModelString = Annotated[
    str,
    Field(
        description="""The model string, as it appears in `pydantic_ai.models.KnownModelName`."""
    ),
]


class AgentProviderSettings(BaseProviderSettings):
    """Settings for agent models."""

    model: Required[ModelString | None]
    model_settings: Required[AgentModelSettings | None]
    """Settings for the agent model(s)."""


# ===========================================================================
# *                    More TypedDict versions of Models
# ===========================================================================


class ProviderSettingsDict(TypedDict, total=False):
    """A dictionary representation of provider settings."""

    data: NotRequired[tuple[DataProviderSettings, ...] | None]
    # we currently only support one each of embedding, reranking and vector store providers
    # but we use tuples to allow for future expansion for some less common use cases
    embedding: NotRequired[tuple[EmbeddingProviderSettings, ...] | EmbeddingProviderSettings | None]
    # rerank is probably the priority for multiple providers in the future, because they're vector agnostic, so you could have fallback providers, or use different ones for different tasks
    sparse_embedding: NotRequired[
        tuple[SparseEmbeddingProviderSettings, ...] | SparseEmbeddingProviderSettings | None
    ]
    reranking: NotRequired[tuple[RerankingProviderSettings, ...] | RerankingProviderSettings | None]
    vector: NotRequired[
        tuple[VectorStoreProviderSettings, ...] | VectorStoreProviderSettings | None
    ]
    agent: NotRequired[tuple[AgentProviderSettings, ...] | AgentProviderSettings | None]


type ProviderSettingsView = DictView[ProviderSettingsDict]


def merge_agent_model_settings(
    base: AgentModelSettings | None, override: AgentModelSettings | None
) -> AgentModelSettings | None:
    """A convenience re-export of `merge_model_settings` for agent model settings."""
    return merge_model_settings(base, override)


DefaultDataProviderSettings = (
    DataProviderSettings(provider=Provider.TAVILY, enabled=False, api_key=None, other=None),
    # DuckDuckGo
    DataProviderSettings(provider=Provider.DUCKDUCKGO, enabled=True, api_key=None, other=None),
)


class DeterminedDefaults(NamedTuple):
    """Tuple for determined default embedding settings."""

    provider: Provider
    model: str
    enabled: bool


def _get_default_embedding_settings() -> DeterminedDefaults:
    """Determine the default embedding provider, model, and enabled status based on available libraries."""
    for lib in (
        "voyageai",
        "mistral",
        "google",
        "fastembed_gpu",
        "fastembed",
        "sentence_transformers",
    ):
        if util.find_spec(lib) is not None:
            # all three of the top defaults are extremely capable
            if lib == "voyageai":
                return DeterminedDefaults(
                    provider=Provider.VOYAGE, model="voyage:voyage-code-3", enabled=True
                )
            if lib == "mistral":
                return DeterminedDefaults(
                    provider=Provider.MISTRAL, model="mistral:codestral-embed", enabled=True
                )
            if lib == "google":
                return DeterminedDefaults(
                    provider=Provider.GOOGLE, model="google/gemini-embedding-001", enabled=True
                )
            if lib in {"fastembed_gpu", "fastembed"}:
                return DeterminedDefaults(
                    # showing its age but it's still a solid lightweight option
                    provider=Provider.FASTEMBED,
                    model="fastembed:BAAI/bge-small-en-v1.5",
                    enabled=True,
                )
            if lib == "sentence_transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    # embedding-small-english-r2 is *very lightweight* and quite capable with a good context window (8192 tokens)
                    model="sentence-transformers:ibm-granite/granite-embedding-small-english-r2",
                    enabled=True,
                )
    logger.warning(
        "No default embedding provider libraries found. Embedding functionality will be disabled unless explicitly set in your config or environment variables."
    )
    return DeterminedDefaults(provider=Provider.NOT_SET, model="NONE", enabled=False)


_embedding_defaults = _get_default_embedding_settings()

DefaultEmbeddingProviderSettings = EmbeddingProviderSettings(
    provider=_embedding_defaults.provider,
    enabled=_embedding_defaults.enabled,
    model_settings=EmbeddingModelSettings(model=_embedding_defaults.model),
)


def _get_default_sparse_embedding_settings() -> DeterminedDefaults:
    """Determine the default sparse embedding provider, model, and enabled status based on available libraries."""
    for lib in ("sentence_transformers", "fastembed_gpu", "fastembed"):
        if util.find_spec(lib) is not None:
            if lib == "sentence_transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    model="opensearch:opensearch-neural-sparse-encoding-doc-v3-gte",
                    enabled=True,
                )
            if lib in {"fastembed_gpu", "fastembed"}:
                return DeterminedDefaults(
                    provider=Provider.FASTEMBED, model="prithivida/Splade_PP_en_v2", enabled=True
                )
    # Sentence-Transformers and Fastembed are the *only* sparse embedding options we support
    logger.warning(
        "No sparse embedding provider libraries found. Sparse embedding functionality disabled."
    )
    return DeterminedDefaults(provider=Provider.NOT_SET, model="NONE", enabled=False)


_sparse_embedding_defaults = _get_default_sparse_embedding_settings()

DefaultSparseEmbeddingProviderSettings = SparseEmbeddingProviderSettings(
    provider=_sparse_embedding_defaults.provider,
    enabled=_sparse_embedding_defaults.enabled,
    model_settings=SparseEmbeddingModelSettings(model=_sparse_embedding_defaults.model),
)


def _get_default_reranking_settings() -> DeterminedDefaults:
    """Determine the default reranking provider, model, and enabled status based on available libraries."""
    for lib in ("voyageai", "fastembed_gpu", "fastembed", "sentence_transformers"):
        if util.find_spec(lib) is not None:
            if lib == "voyageai":
                return DeterminedDefaults(
                    provider=Provider.VOYAGE, model="voyage:rerank-2.5", enabled=True
                )
            if lib in {"fastembed_gpu", "fastembed"}:
                return DeterminedDefaults(
                    provider=Provider.FASTEMBED,
                    model="fastembed:jinaai/jina-reranking-v2-base-multilingual",
                    enabled=True,
                )
            if lib == "sentence_transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    # on the heavier side for what we aim for as a default but very capable
                    model="sentence-transformers:BAAI/bge-reranking-v2-m3",
                    enabled=True,
                )
    logger.warning(
        "No default reranking provider libraries found. Reranking functionality will be disabled unless explicitly set in your config or environment variables."
    )
    return DeterminedDefaults(provider=Provider.NOT_SET, model="NONE", enabled=False)


_reranking_defaults = _get_default_reranking_settings()

DefaultRerankingProviderSettings = RerankingProviderSettings(
    provider=_reranking_defaults.provider,
    enabled=_reranking_defaults.enabled,
    model_settings=RerankingModelSettings(model=_reranking_defaults.model),
)

HAS_ANTHROPIC = util.find_spec("anthropic") is not None
DefaultAgentProviderSettings = AgentProviderSettings(
    provider=Provider.ANTHROPIC,
    enabled=HAS_ANTHROPIC,
    model="claude-sonnet-4-latest",
    model_settings=AgentModelSettings(),
)


DefaultVectorStoreProviderSettings = VectorStoreProviderSettings(
    provider=Provider.QDRANT, enabled=True, provider_settings=QdrantConfig()
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
        tuple[EmbeddingProviderSettings, ...] | EmbeddingProviderSettings | Unset,
        Field(
            description="""Embedding provider configuration.

            We will only use the first provider you configure here. We may add support for multiple embedding providers in the future.
            """
        ),
    ] = DefaultEmbeddingProviderSettings

    sparse_embedding: Annotated[
        tuple[SparseEmbeddingProviderSettings, ...] | SparseEmbeddingProviderSettings | Unset,
        Field(
            description="""Sparse embedding provider configuration.

            We will only use the first provider you configure here. We may add support for multiple sparse embedding providers in the future."""
        ),
    ] = DefaultSparseEmbeddingProviderSettings

    reranking: Annotated[
        tuple[RerankingProviderSettings, ...] | RerankingProviderSettings | Unset,
        Field(
            description="""Reranking provider configuration.

            We will only use the first provider you configure here. We may add support for multiple reranking providers in the future."""
        ),
    ] = DefaultRerankingProviderSettings

    vector_store: Annotated[
        tuple[VectorStoreProviderSettings, ...] | VectorStoreProviderSettings | Unset,
        Field(
            description="""Vector store provider configuration (Qdrant or in-memory), defaults to a local Qdrant instance."""
        ),
    ] = DefaultVectorStoreProviderSettings

    agent: Annotated[
        tuple[AgentProviderSettings, ...] | AgentProviderSettings | Unset,
        Field(description="""Agent provider configuration"""),
    ] = DefaultAgentProviderSettings

    def _telemetry_keys(self) -> None:
        return None

    def has_setting(self, setting_name: ProviderField | LiteralKinds) -> bool:
        """Check if a specific provider setting is configured.

        Args:
            setting_name: The name of the setting or ProviderKind to check.
        """
        from codeweaver.providers.provider import ProviderKind

        setting = (
            setting_name
            if setting_name
            in {"data", "embedding", "sparse_embedding", "reranking", "vector_store", "agent"}
            else cast(ProviderKind, setting_name).variable
        )
        return getattr(self, setting) is not Unset  # type: ignore

    def multiple_embedding_providers(self) -> bool:
        """Check if multiple embedding providers are configured."""
        return isinstance(self.embedding, tuple) and len(self.embedding) > 1

    def multiple_reranking_providers(self) -> bool:
        """Check if multiple reranking providers are configured."""
        return isinstance(self.reranking, tuple) and len(self.reranking) > 1

    def multiple_vector_store_providers(self) -> bool:
        """Check if multiple vector store providers are configured."""
        return isinstance(self.vector_store, tuple) and len(self.vector_store) > 1

    def multiple_agent_providers(self) -> bool:
        """Check if multiple agent providers are configured."""
        return isinstance(self.agent, tuple) and len(self.agent) > 1

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
            if setting is None:
                continue
            # Normalize to tuple form
            configs[field] = setting if isinstance(setting, tuple) else (setting,)
        return configs or None  # type: ignore[return-value]

    @property
    def provider_name_map(self) -> ProviderNameMap:
        """Get a summary of configured providers by kind."""
        provider_data: dict[ProviderField, Provider | tuple[Provider, ...] | None] = {
            field_name: (
                tuple(s["provider"] for s in setting if setting and is_typeddict(s))  # type: ignore
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
        if (
            provider
            not in {
                prov if isinstance(provider, tuple) else provider
                for prov in self.provider_configs.values()
            }
            or provider == Provider.NOT_SET
        ):
            return None
        fields = [
            k for k, v in self.provider_configs.items() if (v and (provider in v)) or v == provider
        ]
        if settings := [
            self.settings_for_kind(field) for field in fields if self.settings_for_kind(field)
        ]:
            flattened_settings: list[BaseProviderSettings] = [
                s if isinstance(setting, tuple) else setting
                for setting in settings
                for s in (setting if isinstance(setting, tuple) else (setting,))
            ]  # type: ignore
            return (
                flattened_settings[0] if len(flattened_settings) == 1 else tuple(flattened_settings)
            )
        return None

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
        self, kind: ProviderField | LiteralKinds
    ) -> BaseProviderSettings | tuple[BaseProviderSettings, ...] | None:
        """Get the settings for a specific provider kind.

        Args:
            kind: The kind of provider or ProviderKind to get settings for.
        """
        from codeweaver.providers.provider import ProviderKind

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
    "AWSProviderSettings",
    "AgentProviderSettings",
    "AllDefaultProviderSettings",
    "AzureCohereProviderSettings",
    "AzureOpenAIProviderSettings",
    "ConnectionConfiguration",
    "ConnectionRateLimitConfig",
    "DataProviderSettings",
    "EmbeddingModelSettings",
    "EmbeddingProviderSettings",
    "FastembedGPUProviderSettings",
    "MemoryConfig",
    "ModelString",
    "ProviderSettings",
    "ProviderSettingsDict",
    "ProviderSettingsDict",
    "ProviderSettingsView",
    "ProviderSpecificSettings",
    "QdrantConfig",
    "RerankingModelSettings",
    "RerankingProviderSettings",
    "SparseEmbeddingModelSettings",
    "VectorStoreProviderSettings",
)

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""
Models and TypedDict classes for providers by kind (embedding, sparse embedding, reranking, agent, vector store, data).

The overall pattern:
    - Each potential provider client (the actual client class, e.g., OpenAIClient) has a corresponding ClientOptions class (e.g., OpenAIClientOptions).
    - There is a baseline provider settings model, `BaseProviderSettings`. Each provider type (embedding, data, vector store, etc.) has a corresponding settings model that extends `BaseProviderSettings` (e.g., `EmbeddingProviderSettings`). These are mostly almost identical, but the class distinctions make identification easier and improves clarity.
    - Certain providers with unique settings requirements can define a mixin class that provides the additional required settings. Note that these should not overlap with the client options for the provider.
    - A series of discriminators help with identifying the correct client options and provider settings classes based on the provider and other settings.
"""

from __future__ import annotations

import contextlib
import logging

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Annotated, Any, Literal, NotRequired, Required, Self, TypedDict, cast

from pydantic import (
    Discriminator,
    Field,
    PositiveFloat,
    PositiveInt,
    SecretStr,
    Tag,
    computed_field,
    model_validator,
)
from pydantic_ai.settings import ModelSettings as AgentModelSettings
from qdrant_client.http.models.models import SparseVectorParams, VectorParams

from codeweaver.core import (
    AnonymityConversion,
    BasedModel,
    FilteredKey,
    FilteredKeyT,
    Provider,
    ProviderLiteral,
    SDKClient,
    get_user_config_dir,
)
from codeweaver.providers.config.clients import (
    BedrockClientOptions,
    CohereClientOptions,
    FastEmbedClientOptions,
    GeneralEmbeddingClientOptionsType,
    GeneralRerankingClientOptionsType,
    HttpxClientParams,
    OpenAIClientOptions,
    QdrantClientOptions,
    SentenceTransformersClientOptions,
    discriminate_azure_embedding_client_options,
)


logger = logging.getLogger(__name__)

type LiteralSDKClient = Literal[
    SDKClient.BEDROCK,
    SDKClient.COHERE,
    SDKClient.FASTEMBED,
    SDKClient.OPENAI,
    SDKClient.SENTENCE_TRANSFORMERS,
    SDKClient.QDRANT,
]


# ===========================================================================
# *            Provider Connection and Rate Limit Settings
# ===========================================================================


class ConnectionRateLimitConfig(BasedModel):
    """Settings for connection rate limiting."""

    max_requests_per_second: PositiveInt | None
    burst_capacity: PositiveInt | None
    backoff_multiplier: PositiveFloat | None
    max_retries: PositiveInt | None


class ConnectionConfiguration(BasedModel):
    """Settings for connection configuration. You probably don't need to set these unless you're doing something special."""

    headers: Annotated[
        dict[str, str] | None, Field(description="HTTP headers to include in requests.")
    ] = None
    rate_limits: Annotated[
        ConnectionRateLimitConfig | None,
        Field(description="Rate limit configuration for the connection."),
    ] = None
    httpx_config: Annotated[
        HttpxClientParams | None,
        Field(
            description="You may optionally provide custom client parameters for the httpx client. CodeWeaver will use your parameters when it constructs its http client pool. You probably don't need this unless you need to handle unique auth or similar requirements."
        ),
    ] = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey("headers"): AnonymityConversion.BOOLEAN,
            FilteredKey("httpx_config"): AnonymityConversion.BOOLEAN,
        }


class BaseProviderSettings(BasedModel, ABC):
    """Base settings for all providers."""

    provider: Provider
    connection: ConnectionConfiguration | None = None
    tag: ProviderLiteral = Field(
        default_factory=lambda data: (
            data.get("provider").variable if isinstance(data, dict) else data.provider.variable
        ),
        exclude=True,
        init=False,
        description="Discriminator tag for the provider.",
    )

    def _telemetry_keys(self) -> None:
        return None

    @abstractmethod
    @computed_field
    def client(self) -> LiteralSDKClient:
        """Return an SDKClient enum member corresponding to this provider settings instance.  Often this is the same as `self.provider`, but not always, and sometimes must be computed (e.g., Azure embedding models)."""


class BaseProviderSettingsDict(TypedDict, total=False):
    """Base settings for all providers. Represents `BaseProviderSettings` in a TypedDict form."""

    provider: Required[Provider]
    connection: NotRequired[ConnectionConfiguration | None]
    tag: NotRequired[ProviderLiteral]


# ===========================================================================
# *            Model Settings classes
# ===========================================================================


# =================== Provider-Specific Mixins ===================


class BedrockProviderMixin:
    """Settings for AWS provider."""

    model_arn: str

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {FilteredKey("model_arn"): AnonymityConversion.HASH}


class AzureProviderMixin:
    """Provider settings for Azure.

    You need to provide these settings if you are using Azure for either Cohere *embedding or reranking models* or OpenAI *embedding* models. You need to provide these for agentic models too, but not with this class (well, we'll probably try to make it work if you do, but no garauntees).

    **For OpenAI embedding models:**
    **We only support the "**next-generation** Azure OpenAI API." Currently, you need to opt into this API in your Azure settings. We didn't want to start supporting the old API knowing it's going away.

    Note that we don't currently support using Azure's SDKs directly for embedding or reranking models. Instead, we use the OpenAI or Cohere clients configured to use Azure endpoints.

    For agent models:
    We support both OpenAI APIs for agentic models because our support comes from `pydantic_ai`, which supports both, it also implements the Azure SDK for agents.
    """

    azure_resource_name: Annotated[
        str,
        Field(
            description="The name of your Azure resource. This is used to identify your resource in Azure."
        ),
    ]

    model_deployment: Annotated[
        str,
        Field(
            description="The deployment name of the model you want to use. This is *different* from the model name in `model_options`, which is the name of the model itself (`text-embedding-3-small`). You need to create a deployment in your Azure OpenAI resource for each model you want to use, and provide the deployment name here."
        ),
    ]

    endpoint: Annotated[
        str | None,
        Field(
            description='The endpoint for your Azure resource. This is used to send requests to your resource. Only provide the endpoint, not the full URL. For example, if your endpoint is `https://your-cool-resource.<region_name>.inference.ai.azure.com/v1`, you would only provide "your-cool-resource" here.'
        ),
    ] = None

    region_name: Annotated[
        str | None,
        Field(
            description="The region name for your Azure resource. This is used to identify the region your resource is in. For example, `eastus` or `westus2`."
        ),
    ] = None

    api_key: Annotated[
        SecretStr | None,
        Field(
            description="Your Azure API key. If not provided, we'll assume you have your Azure credentials configured in another way, such as environment variables."
        ),
    ] = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey("azure_resource_name"): AnonymityConversion.HASH,
            FilteredKey("model_deployment"): AnonymityConversion.HASH,
            FilteredKey("endpoint"): AnonymityConversion.HASH,
            FilteredKey("region_name"): AnonymityConversion.HASH,
            FilteredKey("api_key"): AnonymityConversion.BOOLEAN,
        }


class FastembedProviderMixin:
    """Special settings for Fastembed-GPU provider.

    These settings only apply if you are using a Fastembed provider, installed the `codeweaver[fastembed-gpu]` or `codeweaver[full-gpu]` extra, have a CUDA-capable GPU, and have properly installed and configured the ONNX GPU runtime (see ONNX docs).

    You can provide these settings with your CodeWeaver embedding provider settings, or rerank provider settings. If you're using fastembed-gpu for both, we'll assume you are using the same settings for both if we find one of them.

    Important: You cannot have both `fastembed` and `fastembed-gpu` installed at the same time. They conflict with each other. Make sure to uninstall `fastembed` if you want to use `fastembed-gpu`.
    """

    cuda: NotRequired[bool | None]
    """Whether to use CUDA (if available). If `None`, will auto-detect. We'll generally assume you want to use CUDA if it's available unless you provide a `False` value here."""
    device_ids: NotRequired[list[int] | None]
    """List of GPU device IDs to use. If `None`, we will try to detect available GPUs using `nvidia-smi` if we can find it. We recommend specifying them because our checks aren't perfect."""


# ===========================================================================
# *            Vector Store Provider Settings
# ===========================================================================


class VectorConfig(TypedDict, total=False):
    """Configuration for individual vector types in a collection."""

    dense: VectorParams | None
    sparse: SparseVectorParams | None


class CollectionConfig(TypedDict, total=False):
    """Common collection configuration for vector store providers."""

    collection_name: NotRequired[str | None]
    """Collection name override. Defaults to a unique name based on the project name."""
    dense_vector_name: NotRequired[str]
    """Named vector for dense embeddings. Defaults to 'dense'."""
    sparse_vector_name: NotRequired[str]
    """Named vector for sparse embeddings. Defaults to 'sparse'."""
    vector_config: NotRequired[VectorConfig | None]
    """Configuration for individual vector types in the collection."""


class MemoryConfig(TypedDict, total=False):
    """Configuration for in-memory vector store provider."""

    persist_path: NotRequired[Path]
    f"""Path for JSON persistence file. Defaults to {get_user_config_dir()}/codeweaver/vectors/[your_project_name]_vector_store.json."""
    auto_persist: NotRequired[bool]
    """Automatically save after operations. Defaults to True."""
    persist_interval: NotRequired[PositiveInt | None]
    """Periodic persist interval in seconds. Defaults to 300 (5 minutes). Set to None to disable periodic persistence."""


class QdrantProviderMixin:
    """Settings for Qdrant vector store provider."""

    collection: CollectionConfig | None = None
    in_memory_config: MemoryConfig | None = None

    def _telemetry_handler(self, _serialized_self: dict[str, Any], /) -> dict[str, Any]:
        """Custom telemetry handler to avoid logging sensitive collection names or paths."""
        if (collection := _serialized_self.get("collection")) and (
            collection_name := collection.get("collection_name")
        ):
            return {
                "collection": {
                    "collection_name": AnonymityConversion.HASH.filtered(collection_name)
                }
            }
        return {}


class VectorStoreProviderSettings(BaseProviderSettings):
    """Settings for vector store provider selection and configuration."""

    batch_size: Annotated[
        PositiveInt | None,
        Field(description="Batch size for bulk upsert operations. Defaults to 64."),
    ] = 64


class QdrantVectorStoreProviderSettings(QdrantProviderMixin, VectorStoreProviderSettings):
    """Qdrant-specific settings for the Qdrant and Memory providers. Qdrant is the only currently supported vector store, but others may be added in the future."""

    client_options: Annotated[
        QdrantClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None

    @model_validator(mode="after")
    def _ensure_consistent_config(self) -> Self:
        """Ensure consistent config for Qdrant and Memory providers."""
        if not self.client_options:
            self.client_options = QdrantClientOptions(
                location=":memory:" if self.provider == Provider.MEMORY else None,
                host="localhost" if self.provider == Provider.QDRANT else None,
            )
        if self.provider == Provider.MEMORY:
            # we'll resolve the project name later if the user didn't provide a path
            self.in_memory_config = MemoryConfig(auto_persist=True, persist_interval=300) | (
                self.in_memory_config or {}
            )
        # we'll handle collection config later too -- when models are getting instantiated it's much less painful to wait until the dust settles for inter-model dependencies
        return self

    @computed_field
    def client(self) -> Literal[SDKClient.QDRANT]:
        """Return the Qdrant SDKClient enum member."""
        return SDKClient.QDRANT


# ===========================================================================
# *                       Embedding Provider Settings
# ===========================================================================


class BaseEmbeddingProviderSettings(BaseProviderSettings, ABC):
    """Settings for (dense) embedding models. It validates that the model and provider settings are compatible and complete, reconciling environment variables and config file settings as needed."""

    @abstractmethod
    def get_embed_kwargs(self) -> dict[str, Any]:
        """Get keyword arguments for embedding requests based on the provider settings."""
        raise NotImplementedError("get_embed_kwargs must be implemented by subclasses.")

    @abstractmethod
    def get_query_embed_kwargs(self) -> dict[str, Any]:
        """Get keyword arguments for query embedding requests based on the provider settings."""
        raise NotImplementedError("get_query_embed_kwargs must be implemented by subclasses.")


class EmbeddingProviderSettings(BaseEmbeddingProviderSettings):
    """Settings for dense embedding models."""

    model_name: Annotated[
        str,
        Field(
            description="The name of the embedding model to use. This should correspond to a model supported by the selected provider and formatted as the provider expects. For builtin models, this is the name as listed with `codeweaver list models`."
        ),
    ]
    client_options: Annotated[
        GeneralEmbeddingClientOptionsType | None,
        Field(description="Client options for the provider's client.", discriminator="tag"),
    ] = None

    @computed_field
    @property
    def client(self) -> LiteralSDKClient:
        """Return the embedding SDKClient enum member."""
        is_sdkclient_member = False
        if self.provider == Provider.MEMORY:
            return SDKClient.QDRANT
        if self.provider.uses_openai_api and self.provider not in {Provider.COHERE, Provider.AZURE}:
            return SDKClient.OPENAI
        with contextlib.suppress(AttributeError, KeyError, ValueError):
            is_sdkclient_member = SDKClient.from_string(self.provider.variable) is not None
        if self.provider.only_uses_own_client and is_sdkclient_member:
            return cast(LiteralSDKClient, SDKClient.from_string(self.provider.variable))
        # Now we have azure and heroku left to consider
        if self.model_name.startswith("cohere") or self.model_name.startswith("embed"):
            return SDKClient.COHERE
        return SDKClient.OPENAI

    def get_embed_kwargs(self) -> dict[str, Any]:
        """Get keyword arguments for embedding requests based on the provider settings."""
        return {}

    def get_query_embed_kwargs(self) -> dict[str, Any]:
        """Get keyword arguments for query embedding requests based on the provider settings."""
        return {}


class AzureEmbeddingProviderSettings(AzureProviderMixin, EmbeddingProviderSettings):
    """Provider settings for Azure embedding models (Cohere or OpenAI)."""

    client_options: Annotated[
        Annotated[CohereClientOptions, Tag(Provider.COHERE.variable)]
        | Annotated[OpenAIClientOptions, Tag(Provider.OPENAI.variable)]
        | None,
        Field(
            description="Client options for the provider's client.",
            discriminator=Discriminator(discriminate_azure_embedding_client_options),
        ),
    ] = None


class BedrockEmbeddingProviderSettings(BedrockProviderMixin, EmbeddingProviderSettings):
    """Provider settings for Bedrock embedding models."""

    client_options: Annotated[
        BedrockClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None


class FastembedEmbeddingProviderSettings(FastembedProviderMixin, EmbeddingProviderSettings):
    """Provider settings for Fastembed embedding models."""

    client_options: Annotated[
        FastEmbedClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None


# ===========================================================================
# *               Sparse Embedding Provider Settings
# ===========================================================================


class SparseEmbeddingProviderSettings(BaseProviderSettings):
    """Settings for sparse embedding models."""

    model_name: Annotated[str, Field(description="The name of the sparse embedding model to use.")]
    model_options: SparseEmbeddingModelSettings
    """Settings for the sparse embedding model."""
    client_options: Annotated[
        SentenceTransformersClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None

    @computed_field
    @property
    def client(self) -> Literal[SDKClient.SENTENCE_TRANSFORMERS]:
        """Return the sparse embedding SDKClient enum member."""
        return SDKClient.SENTENCE_TRANSFORMERS


class FastembedSparseEmbeddingProviderSettings(
    FastembedProviderMixin, SparseEmbeddingProviderSettings
):
    """Provider settings for Fastembed sparse embedding models."""

    client_options: Annotated[
        FastEmbedClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None

    @computed_field
    @property
    def client(self) -> Literal[SDKClient.FASTEMBED]:
        """Return the sparse embedding SDKClient enum member."""
        return SDKClient.FASTEMBED


# ===========================================================================
# *                       Reranking Provider Settings
# ===========================================================================


class RerankingProviderSettings(BaseProviderSettings):
    """Settings for re-ranking models."""

    model_name: Annotated[str, Field(description="The name of the re-ranking model to use.")]
    model_options: RerankingModelSettings
    """Settings for the re-ranking model(s)."""
    top_n: PositiveInt | None = None
    client_options: (
        Annotated[
            GeneralRerankingClientOptionsType,
            Field(description="Client options for the provider's client."),
        ]
        | None
    ) = None

    @computed_field
    @property
    def client(self) -> LiteralSDKClient:
        """Return the reranking SDKClient enum member."""
        # currently all reranking providers only use their own clients
        return cast(LiteralSDKClient, SDKClient.from_string(self.provider.variable))


class FastembedRerankingProviderSettings(FastembedProviderMixin, RerankingProviderSettings):
    """Provider settings for Fastembed reranking models."""

    client_options: Annotated[
        FastEmbedClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None


class BedrockRerankingProviderSettings(BedrockProviderMixin, RerankingProviderSettings):
    """Provider settings for Bedrock reranking models."""

    client_options: Annotated[
        BedrockClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None


# NOTE: Data and Agent providers aren't yet fully integrated into the system, so their settings classes are defined here but not yet used. They are also likely to change as we integrate them more fully.

# ===========================================================================
# *                      Data Provider Settings
# ===========================================================================


class DataProviderSettings(BaseProviderSettings):
    """Settings for data providers."""

    other: Annotated[
        dict[str, Any] | None, Field(description="Other provider-specific settings.")
    ] = None

    @computed_field
    @property
    def client(self) -> LiteralSDKClient:
        """Return the data SDKClient enum member."""
        raise NotImplementedError("Data provider client resolution is not yet implemented.")


# ===========================================================================
# *                       Agent Provider Settings
# ===========================================================================

# Agent model settings are imported/defined from `pydantic_ai`

type ModelString = Annotated[
    str,
    Field(
        description="""The model string, as it appears in `pydantic_ai.models.KnownModelName`."""
    ),
]


# we also don't need to add it here because pydantic-ai handles the client
class AgentProviderSettings(BaseProviderSettings):
    """Settings for agent models."""

    model: Required[ModelString]
    model_options: Required[AgentModelSettings | None]
    """Settings for the agent model(s)."""

    @computed_field
    @property
    def client(self) -> LiteralSDKClient:
        """Return the agent SDKClient enum member."""
        raise NotImplementedError("Agent provider client resolution is not yet implemented.")


__all__ = (
    "AgentProviderSettings",
    "AzureEmbeddingProviderSettings",
    "AzureProviderMixin",
    "BaseProviderSettings",
    "BedrockEmbeddingProviderSettings",
    "BedrockProviderMixin",
    "BedrockRerankingProviderSettings",
    "CollectionConfig",
    "ConnectionConfiguration",
    "ConnectionRateLimitConfig",
    "DataProviderSettings",
    "EmbeddingProviderSettings",
    "FastembedEmbeddingProviderSettings",
    "FastembedProviderMixin",
    "FastembedRerankingProviderSettings",
    "FastembedSparseEmbeddingProviderSettings",
    "MemoryConfig",
    "QdrantVectorStoreProviderSettings",
    "RerankingProviderSettings",
    "SparseEmbeddingProviderSettings",
    "VectorConfig",
)

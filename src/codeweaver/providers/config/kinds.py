# SPDX-FileCopyrightText: 2026 Knitli Inc.
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

import asyncio
import contextlib
import logging
import re

from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Literal,
    NotRequired,
    Required,
    Self,
    TypedDict,
    cast,
)

from pydantic import (
    AnyUrl,
    ConfigDict,
    Discriminator,
    Field,
    PositiveFloat,
    PositiveInt,
    PrivateAttr,
    SecretStr,
    Tag,
    computed_field,
    model_validator,
)
from qdrant_client.models import (
    BinaryQuantization,
    CollectionParams,
    HnswConfig,
    OptimizersConfig,
    ProductQuantization,
    ScalarQuantization,
    SparseVectorParams,
    VectorParams,
    WalConfig,
)
from qdrant_client.models import CollectionConfig as QdrantCollectionConfig

from codeweaver.core import (
    INJECTED,
    AnonymityConversion,
    BasedModel,
    CodeWeaverDeveloperError,
    FilteredKey,
    FilteredKeyT,
    ModelName,
    ModelNameT,
    Provider,
    ProviderLiteralString,
    SDKClient,
    generate_collection_name,
    get_user_cache_dir,
    get_user_state_dir,
)
from codeweaver.core.constants import (
    DEFAULT_PERSIST_INTERVAL,
    DEFAULT_RERANKING_MAX_RESULTS,
    DEFAULT_VECTOR_STORE_BATCH_SIZE,
    DEFAULT_VECTOR_STORE_PERSIST_SUBPATH,
    LOCALHOST,
)
from codeweaver.core.utils.checks import is_local_host
from codeweaver.providers.agent.agent_models import AgentModelSettings
from codeweaver.providers.config import (
    AnthropicClientOptions,
    GoogleAgentModelConfig,
    HFInferenceClientOptions,
)
from codeweaver.providers.config.agent import (
    AgentModelConfig,
    AnthropicAgentModelConfig,
    CerebrasAgentModelConfig,
    CohereAgentModelConfig,
    GroqAgentModelConfig,
    HuggingFaceAgentModelConfig,
    MistralAgentModelConfig,
    OpenAIAgentModelConfig,
    OpenRouterAgentModelConfig,
)
from codeweaver.providers.config.clients import (
    AnthropicAzureClientOptions,
    AnthropicBedrockClientOptions,
    AnthropicGoogleVertexClientOptions,
    BedrockClientOptions,
    ClientOptions,
    CohereClientOptions,
    DuckDuckGoClientOptions,
    FastEmbedClientOptions,
    GeneralAgentClientOptionsType,
    GeneralDataClientOptionsType,
    GeneralEmbeddingClientOptionsType,
    GeneralRerankingClientOptionsType,
    GoogleClientOptions,
    GroqClientOptions,
    HttpxClientParams,
    MistralClientOptions,
    OpenAIClientOptions,
    PydanticGatewayClientOptions,
    QdrantClientOptions,
    SentenceTransformersClientOptions,
    TavilyClientOptions,
    discriminate_azure_embedding_client_options,
)
from codeweaver.providers.config.embedding import EmbeddingConfigT, SparseEmbeddingConfigT
from codeweaver.providers.config.reranking import RerankingConfigT
from codeweaver.providers.config.utils import (
    AzureOptions,
    ensure_endpoint_version,
    try_for_azure_endpoint,
)


if TYPE_CHECKING:
    from codeweaver.engine.config import FailoverSettings
    from codeweaver.engine.config.failover_detector import FailoverDetector
    from codeweaver.providers.dependencies import EmbeddingCapabilityGroupDep
    from codeweaver.providers.types import EmbeddingCapabilityGroup
    from codeweaver.providers.vector_stores.metadata import CollectionMetadata

logger = logging.getLogger(__name__)
type LiteralSDKClient = Literal[
    SDKClient.BEDROCK,
    SDKClient.COHERE,
    SDKClient.FASTEMBED,
    SDKClient.OPENAI,
    SDKClient.SENTENCE_TRANSFORMERS,
    SDKClient.QDRANT,
]


def _get_embedding_group(group: EmbeddingCapabilityGroupDep = INJECTED) -> EmbeddingCapabilityGroup:
    """Get the embedding capability group, using dependency injection."""
    return group


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
    client_options: Annotated[
        ClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None

    def __init__(self, **data: Any) -> None:
        """Initialize base provider settings."""
        from codeweaver.core.di import get_container

        try:
            container = get_container()
            container.register(type(self), lambda: self)
        except Exception as e:
            logger.debug(
                "Dependency injection container not available, skipping registration of ProviderSettings: %s",
                e,
            )
        data.pop("as_backup", None)
        data.pop("_as_backup", None)
        object.__setattr__(self, "client_options", data.get("client_options"))
        data |= {"client_options": self.client_options}
        if (
            "model_name" in type(self).model_fields
            and "model_name" not in data
            and (
                kind_config := (
                    getattr(self, "embedding_config", None)
                    or getattr(self, "sparse_embedding_config", None)
                    or getattr(self, "reranking_config", None)
                )
            )
            and kind_config.model_name
        ):
            object.__setattr__(self, "model_name", kind_config.model_name)
        elif (
            "model_name" in type(self).model_fields
            and "model_name" not in data
            and self.client_options
            and (
                model_name := next(
                    (
                        getattr(self.client_options, k, None)
                        for k in ("model_name", "model", "model_id", "model_name_or_path")
                        if getattr(self.client_options, k, None)
                    ),
                    None,
                )
            )
        ):
            object.__setattr__(self, "model_name", ModelName(model_name))
        self._initialize()
        super().__init__(**data)

    def _initialize(self) -> None:
        """Perform any additional initialization steps. Happens before pydantic initialization and the model's post_init."""

    def __model_post_init__(self) -> None:
        """Post-initialization to register in DI container and config registry."""
        try:
            from codeweaver.core.di import get_container

            container = get_container()
            container.register(type(self), lambda: self)
        except Exception as e:
            logger.debug(
                "Failed to register %s in DI container (monorepo mode): %s", type(self).__name__, e
            )

    @model_validator(mode="after")
    def _ensure_endpoint_version(self) -> Self:
        """Ensure that any endpoints in client_options have the correct version suffix."""
        if not self.client_options:
            return self
        if (
            self.client_options
            and self.client_options._core_provider in {Provider.COHERE, Provider.OPENAI}
            and (endpoint := getattr(self.client_options, "base_url", None))
        ):
            object.__setattr__(
                self,
                "client_options",
                self.client_options.model_copy(
                    update={
                        "base_url": ensure_endpoint_version(
                            endpoint, cohere=self.client_options._core_provider == Provider.COHERE
                        )
                    }
                ),
            )
        return self

    def _telemetry_keys(self) -> None:
        return None

    @abstractmethod
    def is_cloud(self) -> bool:
        """Return True if the provider settings are for a cloud deployment."""
        raise NotImplementedError("is_cloud must be implemented by subclasses.")

    def is_local(self) -> bool:
        """Return True if the provider settings are for a local deployment."""
        return not self.is_cloud

    @abstractmethod
    @computed_field
    def client(self) -> LiteralSDKClient:
        """Return an SDKClient enum member corresponding to this provider settings instance.  Often this is the same as `self.provider`, but not always, and sometimes must be computed (e.g., Azure embedding models)."""
        raise NotImplementedError("client must be implemented by subclasses.")

    async def get_client(self) -> Any:
        """Construct and return the client instance based on the provider settings."""
        options = (
            self.client_options.as_settings()
            if isinstance(self.client_options, ClientOptions)
            else {}
        )
        client_import = cast(SDKClient, self.client).client
        kind = next(
            (
                name
                for name in ("agent", "data", "sparse", "embed", "rerank")  # order matters here
                if name in type(self).__name__.lower()
            ),
            None,
        )
        if self.provider == Provider.BEDROCK:
            if not kind:
                raise CodeWeaverDeveloperError(
                    "Kind must be one of 'agent', 'data', 'sparse', 'embed', or 'rerank' for Bedrock provider. File an issue. This is unexpected."
                )
            return client_import._resolve()(
                "bedrock-runtime" if kind == "embed" else "bedrock-agent-runtime", **options
            )
        if self.provider in (Provider.SENTENCE_TRANSFORMERS, Provider.FASTEMBED):
            return await asyncio.to_thread(client_import._resolve(), **options)
        if not isinstance(client_import, dict):
            return client_import._resolve()(**options)
        client_class = client_import.get(kind)._resolve()
        return client_class(**options)


class BaseProviderSettingsDict(TypedDict, total=False):
    """Base settings for all providers. Represents `BaseProviderSettings` in a TypedDict form."""

    provider: Required[Provider]
    connection: NotRequired[ConnectionConfiguration | None]
    tag: NotRequired[ProviderLiteralString]
    client_options: NotRequired[ClientOptions | None]


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

    def as_azure_options(self) -> AzureOptions:
        """Return the settings as an AzureOptions TypedDict."""
        return AzureOptions(
            model_deployment=self.model_deployment,
            endpoint=self.endpoint,
            region_name=self.region_name,
            api_key=self.api_key,
        )


class FastEmbedProviderMixin:
    """Special settings for FastEmbed-GPU provider.

    These settings only apply if you are using a FastEmbed provider, installed the `codeweaver[fastembed-gpu]` or `codeweaver[full-gpu]` extra, have a CUDA-capable GPU, and have properly installed and configured the ONNX GPU runtime (see ONNX docs).

    You can provide these settings with your CodeWeaver embedding provider settings, or rerank provider settings. If you're using fastembed-gpu for both, we'll assume you are using the same settings for both if we find one of them.

    Important: You cannot have both `fastembed` and `fastembed-gpu` installed at the same time. They conflict with each other. Make sure to uninstall `fastembed` if you want to use `fastembed-gpu`.
    """

    cuda: bool | None = None
    "Whether to use CUDA (if available). If `None`, will auto-detect. We'll generally assume you want to use CUDA if it's available unless you provide a `False` value here."
    device_ids: list[int] | None = None
    "List of GPU device IDs to use. If `None`, we will try to detect available GPUs using `nvidia-smi` if we can find it. We recommend specifying them because our checks aren't perfect."


class VectorStoreProviderSettings(BaseProviderSettings):
    """Settings for vector store provider selection and configuration."""

    provider: ClassVar[Literal[Provider.QDRANT, Provider.MEMORY]]
    batch_size: Annotated[
        PositiveInt | None,
        Field(description="Batch size for bulk upsert operations. Defaults to 64."),
    ] = DEFAULT_VECTOR_STORE_BATCH_SIZE


def _deep_merge(dict1: dict[str, Any], dict2: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge two dictionaries."""
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class CollectionConfig(BasedModel):
    """Collection configuration for Qdrant and in-memory vector stores.

    NOTE: The vector configurations share many of the same properties as these collection parameters. If vector configurations exist, such as for hnsw_config or quantization_config, they will override the corresponding collection parameters.
    """

    collection_name: str | None = None
    "Collection name override. Defaults to a unique name based on the project name."
    vectors_config: Mapping[str, VectorParams] | None = None
    "Configuration for individual vector types in the collection."
    quantization_config: ScalarQuantization | ProductQuantization | BinaryQuantization | None = None
    "Configuration for quantization used in the collection."
    sparse_vectors_config: Mapping[str, SparseVectorParams] | None = None
    "Configuration for individual sparse vector types in the collection."
    wal_config: WalConfig | None = None
    "Configuration for the write-ahead log (WAL) used in the collection. We have no default configuration for the WAL at this time. Qdrant's defaults are good for nearly all cases, but you can customize it for performance tuning, resource, or durability requirements."
    optimizer_config: OptimizersConfig | None = None
    "Configuration for optimizers used in the collection. No default configuration. Optimizing segments can increase throughput/concurrency at the cost of additional memory usage.  See https://qdrant.tech/documentation/concepts/optimizer/"
    hnsw_config: HnswConfig | None = Field(
        default_factory=lambda: HnswConfig(
            m=24, ef_construct=130, payload_m=120, full_scan_threshold=10000
        )
    )
    "Configuration for HNSW (Hierarchical Navigable Small World) index used for approximate nearest neighbor search. We generally recommend you keep our defaults here, which we will tweak and fine-tune over time to get optimal performance for code search."
    _vectors_set: bool = PrivateAttr(default=False)

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """Return telemetry keys for privacy-first data collection."""
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {FilteredKey("collection_name"): AnonymityConversion.HASH}

    async def params(self) -> CollectionParams:
        """Return the Qdrant collection parameters for this configuration."""
        if not self._vectors_set:
            await self.set_vector_params()
        return CollectionParams.model_construct(
            vectors=self.vectors_config, sparse_vectors=self.sparse_vectors_config
        )

    async def set_vector_params(
        self, embedding_group: EmbeddingCapabilityGroup | None = None
    ) -> None:
        """Assemble the vector parameters for the collection."""
        embedding_group = embedding_group or _get_embedding_group()
        params = await embedding_group.as_vector_params()
        vectors = params.vectors
        if vectors is not None:
            if isinstance(vectors, dict):
                vectors_dict = cast(dict[str, VectorParams], vectors)
            else:
                vectors_dict = cast(dict[str, VectorParams], vectors.model_dump())
        else:
            vectors_dict = {}
        self.vectors_config = _deep_merge(dict(self.vectors_config or {}), vectors_dict)
        self.sparse_vectors_config = _deep_merge(
            dict(self.sparse_vectors_config or {}),
            cast(dict[str, SparseVectorParams], params.sparse_vectors or {}),
        )
        self._vectors_set = True

    async def as_qdrant_config(self, metadata: CollectionMetadata) -> QdrantCollectionConfig:
        """Convert the collection configuration to a QdrantCollectionConfig object."""
        return QdrantCollectionConfig.model_construct(
            params=await self.params(),
            hnsw_config=self.hnsw_config,
            optimizer_config=self.optimizer_config,
            wal_config=self.wal_config,
            metadata=metadata.model_dump(),
        )


class _BaseQdrantVectorStoreProviderSettings(VectorStoreProviderSettings):
    """Qdrant-specific settings for the Qdrant and Memory providers. Qdrant is the only currently supported vector store, but others may be added in the future."""

    client_options: Annotated[
        QdrantClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None
    collection: Annotated[
        CollectionConfig, Field(description="Collection configuration for the vector store.")
    ]

    def _initialize(self, **data: Any) -> None:
        """Initialize Qdrant vector store provider settings."""

    def __init__(
        self,
        provider: Literal[Provider.QDRANT, Provider.MEMORY] = Provider.QDRANT,
        connection: ConnectionConfiguration | None = None,
        client_options: QdrantClientOptions | None = None,
        collection: CollectionConfig | None = None,
        batch_size: PositiveInt | None = DEFAULT_VECTOR_STORE_BATCH_SIZE,
        *,
        project_name: str | None = None,
        project_path: Path | None = None,
    ) -> None:
        """Initialize Qdrant vector store provider settings.

        Args:
            provider: The vector store provider (Qdrant or Memory).
            connection: Connection configuration for the vector store.
            client_options: Client options for the provider's client.
            collection: Collection configuration for the vector store.
            batch_size: Batch size for bulk upsert operations.
            project_name: The name of the project.
            project_path: The path to the project.
        """
        prepared_client_options = (
            client_options if client_options is not None else QdrantClientOptions()
        )
        if collection is None:
            collection_dict = {}
        elif isinstance(collection, CollectionConfig):
            collection_dict = collection.model_dump(exclude_none=True)
        else:
            collection_dict = collection
        prepared_collection = CollectionConfig.model_validate(
            self._default_collection(
                project_name=project_name, project_path=project_path
            ).model_dump()
            | collection_dict
        )
        constructed = self.__class__.model_construct(
            provider=provider,
            tag=provider.variable,
            connection=connection,
            client_options=prepared_client_options,
            collection=prepared_collection,
            batch_size=batch_size,
        )
        for field_name in type(constructed).model_fields:
            object.__setattr__(self, field_name, getattr(constructed, field_name))

    _resolved_dimension: int | None = PrivateAttr(default=None)
    _resolved_datatype: str | None = PrivateAttr(default=None)

    def _default_collection(
        self, *, project_name: str | None = None, project_path: Path | None = None
    ) -> CollectionConfig:
        """Return the default collection config.

        Note: Vector configs are intentionally left as None and will be populated
        later by set_vector_params() based on the embedding configuration.
        """
        from codeweaver.core import generate_collection_name

        return CollectionConfig(
            collection_name=generate_collection_name(
                project_name=project_name, project_path=project_path
            ),
            vectors_config=None,
            sparse_vectors_config=None,
        )

    @model_validator(mode="after")
    def _ensure_consistent_config(self) -> Self:
        """Ensure consistent config for Qdrant and Memory providers."""
        if not self.client_options:
            self.client_options = QdrantClientOptions(
                location=":memory:" if self.provider == Provider.MEMORY else None,
                host=LOCALHOST if self.provider == Provider.QDRANT else None,
            )
        if self.provider == Provider.MEMORY:
            collection_name = None
            if isinstance(self.collection, dict):
                collection_name = self.collection.get("collection_name")
            elif hasattr(self.collection, "collection_name"):
                collection_name = self.collection.collection_name
            self.in_memory_config = self.in_memory_config or getattr(
                self,
                "_default_memory_config",
                lambda _x: {"collection_name": generate_collection_name()},
            )(collection_name)
        try:
            from codeweaver.core.di import get_container

            container = get_container()
            container.register(type(self), lambda: self, singleton=True)
        except Exception as e:
            logger.debug(
                "Failed to register %s in DI container (monorepo mode): %s", type(self).__name__, e
            )
        return self

    def is_cloud(self) -> bool:
        """Return True if the provider settings are for a cloud deployment."""
        return not self.is_local_qdrant or self.provider != Provider.MEMORY

    @computed_field
    @property
    def is_local_qdrant(self) -> bool:
        """Return whether this is a local Qdrant instance (Qdrant database on disk (not memory provider))."""
        return self.client_options.is_local_on_disk() if self.client_options else False

    @computed_field
    @property
    def client(self) -> Literal[SDKClient.QDRANT]:
        """Return the Qdrant SDKClient enum member."""
        return SDKClient.QDRANT

    async def get_collection_config(
        self,
        metadata: CollectionMetadata,
        *,
        embedding_group: EmbeddingCapabilityGroup | None = None,
        failover_settings: FailoverSettings | None = None,
        failover_detector: FailoverDetector | None = None,
    ) -> QdrantCollectionConfig:
        """Get collection configuration, merging failover WalConfig if backup system is enabled.

        This is a convenience method that delegates to QdrantVectorStoreService.
        For better testability, instantiate the service directly with explicit dependencies.

        When the backup system is active, failover WalConfig settings take precedence over
        user-configured settings to ensure proper snapshot and recovery functionality.

        Args:
            metadata: Collection metadata
            embedding_group: Optional embedding capability group (for testing)
            failover_settings: Optional failover settings (for testing)
            failover_detector: Optional failover detector (for testing)

        Returns:
            QdrantCollectionConfig with merged WalConfig settings

        Example:
            # Production (uses DI):
            config = await settings.get_collection_config(metadata)

            # Testing (explicit dependencies):
            config = await settings.get_collection_config(
                metadata,
                embedding_group=mock_embedding_group,
                failover_settings=mock_failover,
            )

            # Better testing (use service directly):
            from codeweaver.providers.vector_stores.qdrant_service import QdrantVectorStoreService
            service = QdrantVectorStoreService(settings, mock_embedding_group, mock_failover)
            config = await service.get_collection_config(metadata)
        """
        if embedding_group is not None:
            from codeweaver.providers.vector_stores.qdrant_service import QdrantVectorStoreService

            service = QdrantVectorStoreService(
                settings=self,  # ty:ignore[invalid-argument-type]
                embedding_group=embedding_group,
                failover_settings=failover_settings,
                failover_detector=failover_detector,
            )  # ty:ignore[invalid-argument-type]
            return await service.get_collection_config(metadata)
        try:
            from codeweaver.core.di import get_container
            from codeweaver.engine.config import FailoverSettings
            from codeweaver.engine.config.failover_detector import FailoverDetector
            from codeweaver.providers.vector_stores.qdrant_service import QdrantVectorStoreService

            container = get_container()
            embedding_group = await container.resolve(EmbeddingCapabilityGroup)
            failover_settings = await container.resolve(FailoverSettings)
            try:
                failover_detector = await container.resolve(FailoverDetector)
            except Exception:
                failover_detector = None
            service = QdrantVectorStoreService(
                settings=self,  # ty:ignore[invalid-argument-type]
                embedding_group=embedding_group,
                failover_settings=failover_settings,
                failover_detector=failover_detector,
            )  # ty:ignore[invalid-argument-type]
        except Exception as e:
            logger.debug("DI container not available, using basic config: %s", e)
            if not self.collection._vectors_set:
                if embedding_group is None:
                    embedding_group = _get_embedding_group()
                await self.collection.set_vector_params(embedding_group)
            return await self.collection.as_qdrant_config(metadata=metadata)
        else:
            return await service.get_collection_config(metadata)


class QdrantVectorStoreProviderSettings(_BaseQdrantVectorStoreProviderSettings):
    """Settings for Qdrant vector store provider."""

    provider: ClassVar[Literal[Provider.QDRANT]] = Provider.QDRANT
    tag: Literal["qdrant"] = "qdrant"


class MemoryConfig(TypedDict, total=False):
    """Configuration for in-memory vector store provider."""

    persist_path: NotRequired[Path]
    f"Path for JSON persistence file. Defaults to {get_user_cache_dir()}/vectors/[your_project_name]-[filepath-hash]"
    auto_persist: NotRequired[bool]
    "Automatically save after operations. Defaults to True."
    persist_interval: NotRequired[PositiveInt | None]
    "Periodic persist interval in seconds. Defaults to 300 (5 minutes). Set to None to disable periodic persistence."


class MemoryVectorStoreProviderSettings(_BaseQdrantVectorStoreProviderSettings):
    """Settings for in-memory vector store provider."""

    provider: ClassVar[Literal[Provider.MEMORY]] = Provider.MEMORY
    in_memory_config: Annotated[
        MemoryConfig, Field(description="In-memory vector store configuration.")
    ]

    def __init__(
        self,
        provider: Literal[Provider.MEMORY] = Provider.MEMORY,
        connection: ConnectionConfiguration | None = None,
        client_options: QdrantClientOptions | None = None,
        collection: CollectionConfig | None = None,
        batch_size: PositiveInt | None = DEFAULT_VECTOR_STORE_BATCH_SIZE,
        in_memory_config: MemoryConfig | None = None,
        *,
        project_name: str | None = None,
        project_path: Path | None = None,
    ) -> None:
        """Initialize Memory vector store provider settings."""
        prepared_client_options = (
            client_options if client_options is not None else QdrantClientOptions()
        )
        if collection is None:
            collection_dict = {}
        elif isinstance(collection, CollectionConfig):
            collection_dict = collection.model_dump(exclude_none=True)
        else:
            collection_dict = collection
        parent_default_collection = super()._default_collection(
            project_name=project_name, project_path=project_path
        )
        prepared_collection = CollectionConfig.model_validate(
            parent_default_collection.model_dump() | collection_dict
        )
        collection_name = prepared_collection.collection_name
        if in_memory_config is None:
            in_memory_config = self._default_memory_config(
                collection_name=collection_name,
                project_name=project_name,
                project_path=project_path,
            )
        constructed = self.__class__.model_construct(
            provider=provider,
            tag=provider.variable,
            connection=connection,
            client_options=prepared_client_options,
            collection=prepared_collection,
            batch_size=batch_size,
            in_memory_config=in_memory_config,
        )
        for field_name in constructed.model_fields:
            object.__setattr__(self, field_name, getattr(constructed, field_name))
        object.__setattr__(self, "__pydantic_fields_set__", set(constructed.model_fields.keys()))

    @staticmethod
    def _get_persist_path(
        *,
        collection_name: str | None = None,
        project_name: str | None = None,
        project_path: Path | None = None,
    ) -> Path:
        """Get the persist path from in_memory_config."""
        return Path(
            f"{get_user_state_dir()}/{DEFAULT_VECTOR_STORE_PERSIST_SUBPATH}/{generate_collection_name(project_name=project_name, project_path=project_path)}"
        )

    @staticmethod
    def _default_memory_config(
        collection_name: str | None = None,
        project_name: str | None = None,
        project_path: Path | None = None,
        persist_path: Path | None = None,
    ) -> MemoryConfig:
        """Return the default memory config."""
        return MemoryConfig(
            auto_persist=True,
            persist_interval=DEFAULT_PERSIST_INTERVAL,
            persist_path=persist_path
            or MemoryVectorStoreProviderSettings._get_persist_path(
                collection_name=collection_name,
                project_name=project_name,
                project_path=project_path,
            ),
        )


def _is_cloud_provider(_instance: BaseProviderSettings) -> bool:
    if _instance.provider.always_cloud or not _instance.provider.always_local:
        return True
    return bool(
        _instance.client_options
        and (
            url := getattr(
                _instance.client_options,
                "url",
                getattr(
                    _instance.client_options,
                    "endpoint",
                    getattr(_instance.client_options, "base_url", None),
                ),
            )
        )
        is not None
        and (not is_local_host(url))
    )


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

    def is_cloud(self) -> bool:
        """Return True if the provider settings are for a cloud deployment."""
        return _is_cloud_provider(self)


class EmbeddingProviderSettings(BaseEmbeddingProviderSettings):
    """Settings for dense embedding models."""

    config_type: Annotated[
        Literal["symmetric"],
        Field(default="symmetric", description="Discriminator for embedding config type."),
    ] = "symmetric"

    model_name: Annotated[
        ModelNameT,
        Field(
            description="The name of the embedding model to use. This should correspond to a model supported by the selected provider and formatted as the provider expects. For builtin models, this is the name as listed with `codeweaver list models`."
        ),
    ]
    embedding_config: Annotated[
        EmbeddingConfigT, Field(description="Model configuration for embedding operations.")
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
        if self.provider not in (Provider.AZURE, Provider.HEROKU):
            raise ValueError(
                f"Cannot resolve embedding client for provider {self.provider.variable}."
            )
        if str(self.model_name).startswith("cohere") or str(self.model_name).startswith("embed"):
            return SDKClient.COHERE
        return SDKClient.OPENAI

    def get_embed_kwargs(self) -> dict[str, Any]:
        """Get keyword arguments for embedding requests based on the provider settings."""
        embedding_config = self.embedding_config.as_options()
        return embedding_config.get("embedding", {})

    def get_query_embed_kwargs(self) -> dict[str, Any]:
        """Get keyword arguments for query embedding requests based on the provider settings."""
        embedding_config = self.embedding_config.as_options()
        return embedding_config.get("query", {})


class AzureEmbeddingProviderSettings(AzureProviderMixin, EmbeddingProviderSettings):
    """Provider settings for Azure embedding models (Cohere or OpenAI)."""

    model_config = EmbeddingProviderSettings.model_config | ConfigDict(frozen=False)
    tag: Literal["azure"] = "azure"
    client_options: (
        Annotated[
            Annotated[CohereClientOptions, Tag(Provider.COHERE.variable)]
            | Annotated[OpenAIClientOptions, Tag(Provider.OPENAI.variable)],
            Field(
                description="Client options for the provider's client.",
                discriminator=Discriminator(discriminate_azure_embedding_client_options),
            ),
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def _validate_client_options(self) -> Self:
        """Validate and adjust client options for Azure embedding providers."""
        if (
            self.client_options
            and self.client_options.base_url
            and (self.api_key or self.client_options.api_key)
        ):
            return self
        if not self.client_options:
            client_options = (
                CohereClientOptions() if self.client == SDKClient.COHERE else OpenAIClientOptions()
            )
        else:
            client_options = self.client_options
        api_key = self.api_key or self.client_options.api_key or Provider.AZURE.get_env_api_key()
        options = self.as_azure_options() | client_options.model_dump() | {"api_key": api_key}
        is_cohere = (
            isinstance(client_options, CohereClientOptions) or self.client == SDKClient.COHERE
        )
        if not options.get("base_url") and (
            endpoint := try_for_azure_endpoint(options, cohere=is_cohere)
        ):
            options["base_url"] = AnyUrl(endpoint)
        final_client_options = {
            k: v
            for k, v in options.items()
            if v is not None and k not in {"model_deployment", "endpoint", "region_name"}
        }
        client = (
            CohereClientOptions(**final_client_options)
            if is_cohere
            else OpenAIClientOptions(**final_client_options)
        )
        object.__setattr__(self, "client_options", client)
        for k, v in {
            key: value
            for key, value in options.items()
            if key in {"model_deployment", "endpoint", "region_name", "api_key"}
        }.items():
            if v and (
                not hasattr(self, k)
                or (value := getattr(self, k, None)) is None
                or (value and value != v)
            ):
                setattr(self, k, v)
        return self


class BedrockEmbeddingProviderSettings(BedrockProviderMixin, EmbeddingProviderSettings):
    """Provider settings for Bedrock embedding models."""

    client_options: Annotated[
        BedrockClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None
    tag: Literal["bedrock"] = "bedrock"

    @model_validator(mode="after")
    def _inject_model_arn_into_params(self) -> Self:
        """Inject model_arn into embedding/query params if not already present.

        Bedrock requires the model ARN at request time. This validator ensures it's
        available in the embedding_config's embedding and query parameters.
        """
        from codeweaver.providers.config.embedding import BedrockEmbeddingConfig

        # Type narrow to ensure we're working with BedrockEmbeddingConfig
        if not isinstance(self.embedding_config, BedrockEmbeddingConfig):
            return self

        # Inject ARN into embedding params
        if self.embedding_config.embedding:
            if "model_id" not in self.embedding_config.embedding:
                self.embedding_config.embedding["model_id"] = self.model_arn
        else:
            # Create embedding params with just the model_id
            object.__setattr__(self.embedding_config, "embedding", {"model_id": self.model_arn})

        # Inject ARN into query params
        if self.embedding_config.query:
            if "model_id" not in self.embedding_config.query:
                self.embedding_config.query["model_id"] = self.model_arn
        else:
            # Create query params with just the model_id
            object.__setattr__(self.embedding_config, "query", {"model_id": self.model_arn})

        return self


class FastEmbedEmbeddingProviderSettings(FastEmbedProviderMixin, EmbeddingProviderSettings):
    """Provider settings for FastEmbed embedding models."""

    client_options: Annotated[
        FastEmbedClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None
    tag: Literal["fastembed"] = "fastembed"


class SparseEmbeddingProviderSettings(BaseProviderSettings):
    """Settings for sparse embedding models."""

    model_name: Annotated[
        ModelNameT, Field(description="The name of the sparse embedding model to use.")
    ]
    sparse_embedding_config: Annotated[
        SparseEmbeddingConfigT,
        Field(description="Model configuration for sparse embedding operations."),
    ]
    client_options: Annotated[
        SentenceTransformersClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None

    @computed_field
    @property
    def client(self) -> Literal[SDKClient.SENTENCE_TRANSFORMERS]:
        """Return the sparse embedding SDKClient enum member."""
        return SDKClient.SENTENCE_TRANSFORMERS

    def is_cloud(self) -> bool:
        """Return True if the provider settings are for a cloud deployment."""
        return _is_cloud_provider(self)

    tag: Literal["sentence-transformers"] = "sentence-transformers"


class FastEmbedSparseEmbeddingProviderSettings(
    FastEmbedProviderMixin, SparseEmbeddingProviderSettings
):
    """Provider settings for FastEmbed sparse embedding models."""

    client_options: Annotated[
        FastEmbedClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None

    @computed_field
    @property
    def client(self) -> Literal[SDKClient.FASTEMBED]:
        """Return the sparse embedding SDKClient enum member."""
        return SDKClient.FASTEMBED

    tag: Literal["fastembed"] = "fastembed"


class RerankingProviderSettings(BaseProviderSettings):
    """Settings for re-ranking models."""

    model_name: Annotated[ModelNameT, Field(description="The name of the re-ranking model to use.")]
    reranking_config: Annotated[
        RerankingConfigT, Field(description="Model configuration for reranking operations.")
    ]
    top_n: PositiveInt | None = DEFAULT_RERANKING_MAX_RESULTS
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
        return cast(LiteralSDKClient, SDKClient.from_string(self.provider.variable))

    def is_cloud(self) -> bool:
        """Return True if the provider is a cloud provider, False otherwise."""
        return _is_cloud_provider(self)


class FastEmbedRerankingProviderSettings(FastEmbedProviderMixin, RerankingProviderSettings):
    """Provider settings for FastEmbed reranking models."""

    client_options: Annotated[
        FastEmbedClientOptions | None,
        Field(description="Client options for the SDK provider's client."),
    ] = None
    tag: Literal["fastembed"] = "fastembed"


class BedrockRerankingProviderSettings(BedrockProviderMixin, RerankingProviderSettings):
    """Provider settings for Bedrock reranking models."""

    client_options: Annotated[
        BedrockClientOptions | None,
        Field(description="Client options for the SDK provider's client."),
    ] = None
    tag: Literal["bedrock"] = "bedrock"

    @model_validator(mode="after")
    def _inject_model_arn_into_model_config(self) -> Self:
        """Inject model_arn into reranking_config.model if not already present.

        Bedrock requires the model ARN in the model configuration. This validator
        ensures it's available in the reranking_config's model field.
        """
        from codeweaver.providers.config.reranking import BedrockRerankingConfig

        # Type narrow to ensure we're working with BedrockRerankingConfig
        if not isinstance(self.reranking_config, BedrockRerankingConfig):
            return self

        # Inject ARN into model config
        if "model_arn" not in self.reranking_config.model:
            self.reranking_config.model["model_arn"] = self.model_arn

        return self


class BaseDataProviderSettings(BaseProviderSettings):
    """Settings for data providers."""

    provider: Literal[Provider.TAVILY, Provider.DUCKDUCKGO]
    tag: Literal["tavily", "duckduckgo"]

    client_options: GeneralDataClientOptionsType | None = None

    @computed_field(repr=False)
    @property
    def client(self) -> LiteralSDKClient:
        """Return the data SDKClient enum member."""
        return SDKClient.from_string(self.tag)  # ty:ignore[invalid-return-type]

    def is_cloud(self) -> bool:
        """Return True if the provider is a cloud provider, False otherwise."""
        return _is_cloud_provider(self)


class TavilyProviderSettings(BaseDataProviderSettings):
    """Settings for Tavily data provider."""

    provider: Literal[Provider.TAVILY] = Provider.TAVILY
    tag: Literal["tavily"] = "tavily"

    client_options: Annotated[
        TavilyClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None

    def __model_post_init__(self) -> None:
        """Post-initialization to set default API key if not provided."""
        if self.client_options is None or not self.client_options.api_key:
            api_key = Provider.TAVILY.get_env_api_key()
            self.client_options = (self.client_options or TavilyClientOptions()).model_copy(
                update={"api_key": api_key}
            )

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.TAVILY]:
        """Return the data SDKClient enum member."""
        return SDKClient.TAVILY


class DuckDuckGoProviderSettings(BaseDataProviderSettings):
    """Settings for DuckDuckGo data provider."""

    provider: Literal[Provider.DUCKDUCKGO] = Provider.DUCKDUCKGO
    tag: Literal["duckduckgo"] = "duckduckgo"

    client_options: Annotated[
        DuckDuckGoClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None

    def __model_post_init__(self) -> None:
        """Ensure we have a config."""
        self.client_options = self.client_options or DuckDuckGoClientOptions()

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.DUCKDUCKGO]:
        """Return the data SDKClient enum member."""
        return SDKClient.DUCKDUCKGO


type ModelString = Annotated[
    str,
    Field(description="The model string, as it appears in `pydantic_ai.models.KnownModelName`."),
]


class AgentProviderSettings(BaseProviderSettings):
    """Settings for agent models."""

    model_name: ModelString
    model_options: AgentModelSettings | None = None
    "Settings for the agent model(s)."
    client_options: Annotated[
        GeneralAgentClientOptionsType | None,
        Field(description="Client options for the provider's client."),
    ] = None

    @computed_field(repr=False)
    @property
    def client(self) -> LiteralSDKClient:
        """Return the agent SDKClient enum member."""
        raise NotImplementedError("Agent provider client resolution is not yet implemented.")

    def is_cloud(self) -> bool:
        """Return True if the provider is a cloud provider, False otherwise."""
        return _is_cloud_provider(self)


class OpenRouterAgentProviderSettings(AgentProviderSettings):
    """Settings for OpenRouter agent models."""

    provider: Literal[Provider.OPENROUTER] = Provider.OPENROUTER
    tag: Literal["openrouter"] = "openrouter"

    model_options: OpenRouterAgentModelConfig | None = None
    client_options: OpenAIClientOptions | None = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.OPENAI]:
        """Return the agent SDKClient enum member."""
        return SDKClient.OPENAI


class CerebrasAgentProviderSettings(AgentProviderSettings):
    """Settings for Cerebras agent models."""

    provider: Literal[Provider.CEREBRAS] = Provider.CEREBRAS
    tag: Literal["cerebras"] = "cerebras"

    model_options: CerebrasAgentModelConfig | None = None
    client_options: OpenAIClientOptions | None = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.OPENAI]:
        """Return the agent SDKClient enum member."""
        return SDKClient.OPENAI


class OpenAIAgentProviderSettings(AgentProviderSettings):
    """Settings for OpenAI agent models."""

    provider: Literal[
        Provider.OPENAI,
        Provider.ALIBABA,
        Provider.AZURE,
        Provider.DEEPSEEK,
        Provider.FIREWORKS,
        Provider.GITHUB,
        Provider.HEROKU,
        Provider.LITELLM,
        Provider.MOONSHOT,
        Provider.NEBIUS,
        Provider.OLLAMA,
        Provider.OVHCLOUD,
        Provider.PERPLEXITY,
        Provider.SAMBANOVA,
        Provider.TOGETHER,
        Provider.VERCEL,
        Provider.X_AI,
    ]
    tag: Literal[
        "openai",
        "alibaba",
        "azure",
        "deepseek",
        "fireworks",
        "github",
        "heroku",
        "litellm",
        "moonshot",
        "nebius",
        "ollama",
        "ovhcloud",
        "perplexity",
        "sambanova",
        "together",
        "vercel",
        "x_ai",
    ]

    model_options: OpenAIAgentModelConfig | None = None
    client_options: OpenAIClientOptions | None = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.OPENAI]:
        """Return the agent SDKClient enum member."""
        return SDKClient.OPENAI


_anthropic_model_pattern = r".*anthropic.*|.*claude.*|.*opus.*|.*sonnet.*|.*haiku.*"


class BedrockAnthropicAgentProviderSettings(BedrockProviderMixin, AgentProviderSettings):
    """Settings for Bedrock Anthropic agent models."""

    provider: Literal[Provider.BEDROCK] = Provider.BEDROCK
    tag: Literal["anthropic_bedrock"] = "anthropic_bedrock"

    model_name: Annotated[
        ModelString,
        Field(
            description="The model string for Bedrock Anthropic models.",
            pattern=_anthropic_model_pattern,
        ),
    ]
    model_options: AnthropicAgentModelConfig | None = None
    client_options: Annotated[
        AnthropicBedrockClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.ANTHROPIC]:
        """Return the agent SDKClient enum member."""
        return SDKClient.ANTHROPIC


class AzureAnthropicAgentProviderSettings(AzureProviderMixin, AgentProviderSettings):
    """Settings for Azure Anthropic agent models."""

    provider: Literal[Provider.AZURE] = Provider.AZURE
    tag: Literal["anthropic_azure"] = "anthropic_azure"

    model_name: Annotated[
        ModelString,
        Field(
            description="The model string for Azure Anthropic models.",
            pattern=_anthropic_model_pattern,
        ),
    ]
    model_options: AnthropicAgentModelConfig | None = None
    client_options: Annotated[
        AnthropicAzureClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.ANTHROPIC]:
        """Return the agent SDKClient enum member."""
        return SDKClient.ANTHROPIC


class GoogleVertexAnthropicAgentProviderSettings(AgentProviderSettings):
    """Settings for Google Vertex Anthropic agent models."""

    provider: Literal[Provider.GOOGLE] = Provider.GOOGLE
    tag: Literal["anthropic_google"] = "anthropic_google"

    model_name: Annotated[
        ModelString,
        Field(
            description="The model string for Google Vertex Anthropic models.",
            pattern=_anthropic_model_pattern,
        ),
    ]
    model_options: GoogleAgentModelConfig | None = None
    client_options: Annotated[
        AnthropicGoogleVertexClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.ANTHROPIC]:
        """Return the agent SDKClient enum member."""
        return SDKClient.ANTHROPIC


class GroqAgentProviderSettings(AgentProviderSettings):
    """Settings for Groq Anthropic agent models."""

    provider: Literal[Provider.GROQ] = Provider.GROQ
    tag: Literal["groq"] = "groq"

    model_name: Annotated[
        ModelString,
        Field(
            description="The model string for Groq Anthropic models.",
            pattern=_anthropic_model_pattern,
        ),
    ]
    model_options: GroqAgentModelConfig | None = None
    client_options: Annotated[
        GroqClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.GROQ]:
        """Return the agent SDKClient enum member."""
        return SDKClient.GROQ


class AnthropicAgentProviderSettings(AgentProviderSettings):
    """Settings for Anthropic agent models."""

    tag: Literal["anthropic"] = "anthropic"
    model_name: Annotated[
        ModelString,
        Field(
            description="The model string for Anthropic models.", pattern=_anthropic_model_pattern
        ),
    ]
    client_options: Annotated[
        AnthropicClientOptions | None,
        Field(description="Client options for the Anthropic provider's client."),
    ] = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.ANTHROPIC]:
        """Return the agent SDKClient enum member."""
        return SDKClient.ANTHROPIC


class GoogleAgentProviderSettings(AgentProviderSettings):
    """Settings for Google agent models."""

    provider: Literal[Provider.GOOGLE] = Provider.GOOGLE
    tag: Literal["google"] = "google"

    model_options: GoogleAgentModelConfig | None = None
    client_options: GoogleClientOptions | None = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.GOOGLE]:
        """Return the agent SDKClient enum member."""
        return SDKClient.GOOGLE


class CohereAgentProviderSettings(AgentProviderSettings):
    """Settings for Cohere agent models."""

    provider: Literal[Provider.COHERE] = Provider.COHERE
    tag: Literal["cohere"] = "cohere"

    model_options: CohereAgentModelConfig | None = None
    client_options: CohereClientOptions | None = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.COHERE]:
        """Return the agent SDKClient enum member."""
        return SDKClient.COHERE


class HFInferenceAgentProviderSettings(AgentProviderSettings):
    """Settings for Hugging Face Inference agent models."""

    provider: Literal[Provider.HUGGINGFACE_INFERENCE] = Provider.HUGGINGFACE_INFERENCE
    tag: Literal["hf_inference"] = "hf_inference"

    model_options: HuggingFaceAgentModelConfig | None = None
    client_options: HFInferenceClientOptions | None = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.HUGGINGFACE_INFERENCE]:
        """Return the agent SDKClient enum member."""
        return SDKClient.HUGGINGFACE_INFERENCE


class MistralAgentProviderSettings(AgentProviderSettings):
    """Settings for Mistral agent models."""

    provider: Literal[Provider.MISTRAL] = Provider.MISTRAL
    tag: Literal["mistral"] = "mistral"

    model_options: MistralAgentModelConfig | None = None
    client_options: MistralClientOptions | None = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.MISTRAL]:
        """Return the agent SDKClient enum member."""
        return SDKClient.MISTRAL


class PydanticGatewayProviderSettings(AgentProviderSettings):
    """Settings for Pydantic Gateway agent models."""

    provider: Literal[Provider.PYDANTIC_GATEWAY] = Provider.PYDANTIC_GATEWAY
    tag: Literal["pydantic_gateway"] = "pydantic_gateway"

    model_options: AgentModelConfig | None = None
    client_options: PydanticGatewayClientOptions | None = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.PYDANTIC_GATEWAY]:
        """Return the agent SDKClient enum member."""
        return SDKClient.PYDANTIC_GATEWAY


# ===========================================================================
# *                    Settings Discriminators
# ===========================================================================

type DataProviderSettingsType = Annotated[
    DuckDuckGoProviderSettings | TavilyProviderSettings, Field(discriminator="tag")
]


def _discriminate_anthropic_agent_providers(
    v: dict[str, Any], model_name: str, tag: str
) -> str | None:
    if (
        re.match(_anthropic_model_pattern, model_name or "")
        and tag
        and tag
        in {
            "azure",
            "bedrock",
            "google",
            "anthropic",
            "anthropic_azure",
            "anthropic_bedrock",
            "anthropic_google",
        }
    ):
        if tag in {"azure", "anthropic_azure"}:
            return "anthropic_azure"
        if tag in {"bedrock", "anthropic_bedrock"}:
            return "anthropic_bedrock"
        if tag in {"google", "anthropic_google"}:
            return "anthropic_google"
        return "anthropic"
    return None


def _discriminate_from_base_url(v: dict[str, Any]) -> str | None:
    """Discriminate provider based on base_url in client options."""
    url_keys = ("base_url", "endpoint", "url")
    for key in url_keys:
        if base_url := v.get("client_options", {}).get(key):
            if found_url := next(
                p.variable
                for p in Provider
                if p.variable.replace("_", "").replace("-", "") in base_url
            ):
                return found_url
            if "huggingface" in base_url.lower():
                return "hf_inference"
            if is_local_host(base_url):
                return "ollama"
    return None


def _discriminate_agent_settings(v: Any) -> str:
    """Discriminate agent model settings based on provider."""
    value = v if isinstance(v, dict) else v.model_dump()
    tag = value.get("tag") or value.get("client_options", {}).get("tag")
    if not tag and (provider := value.get("provider")):
        tag = provider.variable
    if tag and isinstance(tag, Provider):
        tag = tag.variable
    model_name = str(
        value.get("model_name") if isinstance(value, dict) else getattr(value, "model_name", "")
    )
    if tag and tag not in {
        "azure",
        "bedrock",
        "google",
        "anthropic_azure",
        "anthropic_bedrock",
        "anthropic_google",
    }:
        return tag
    if anthropic_tag := _discriminate_anthropic_agent_providers(v, model_name=model_name, tag=tag):
        return anthropic_tag
    if tag and tag in {"azure", "bedrock", "google"}:
        return tag
    if base_url_tag := _discriminate_from_base_url(value):
        return base_url_tag
    return "openai"


type AgentProviderSettingsType = Annotated[
    AgentProviderSettings
    | AnthropicAgentProviderSettings
    | AzureAnthropicAgentProviderSettings
    | BedrockAnthropicAgentProviderSettings
    | CerebrasAgentProviderSettings
    | CohereAgentProviderSettings
    | GoogleAgentProviderSettings
    | GoogleVertexAnthropicAgentProviderSettings
    | GroqAgentProviderSettings
    | HFInferenceAgentProviderSettings
    | MistralAgentProviderSettings
    | OpenAIAgentProviderSettings
    | OpenRouterAgentProviderSettings,
    Field(discriminator="tag"),
]


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
    Annotated[EmbeddingProviderSettings, Field(discriminator="tag"), Tag("none")]
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


with contextlib.suppress(Exception):
    from codeweaver.providers.config.clients import QdrantClientOptions

    if not QdrantClientOptions.__pydantic_complete__:
        QdrantClientOptions.model_rebuild()


__all__ = (
    "AgentProviderSettings",
    "AgentProviderSettingsType",
    "AzureEmbeddingProviderSettings",
    "AzureProviderMixin",
    "BaseDataProviderSettings",
    "BaseEmbeddingProviderSettings",
    "BaseProviderSettings",
    "BaseProviderSettingsDict",
    "BedrockEmbeddingProviderSettings",
    "BedrockProviderMixin",
    "BedrockRerankingProviderSettings",
    "CollectionConfig",
    "ConnectionConfiguration",
    "ConnectionRateLimitConfig",
    "DataProviderSettingsType",
    "DuckDuckGoProviderSettings",
    "EmbeddingProviderSettings",
    "EmbeddingProviderSettingsType",
    "FastEmbedEmbeddingProviderSettings",
    "FastEmbedProviderMixin",
    "FastEmbedRerankingProviderSettings",
    "FastEmbedSparseEmbeddingProviderSettings",
    "MemoryConfig",
    "MemoryVectorStoreProviderSettings",
    "ModelString",
    "QdrantVectorStoreProviderSettings",
    "RerankingProviderSettings",
    "RerankingProviderSettingsType",
    "SparseEmbeddingProviderSettings",
    "SparseEmbeddingProviderSettingsType",
    "TavilyProviderSettings",
    "VectorStoreProviderSettings",
    "VectorStoreProviderSettingsType",
)

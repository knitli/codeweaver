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
import importlib
import logging

from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any, Literal, NotRequired, Required, Self, TypedDict, cast

from beartype.typing import ClassVar
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
from pydantic_ai.settings import ModelSettings as AgentModelSettings
from qdrant_client.http.models.models import SparseVectorParams, VectorParams

from codeweaver.core import (
    AnonymityConversion,
    BasedModel,
    CodeWeaverDeveloperError,
    FilteredKey,
    FilteredKeyT,
    Provider,
    ProviderLiteral,
    SDKClient,
    generate_collection_name,
    get_user_cache_dir,
)
from codeweaver.providers.config.clients import (
    BedrockClientOptions,
    ClientOptions,
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
from codeweaver.providers.config.embedding import EmbeddingConfigT, SparseEmbeddingConfigT
from codeweaver.providers.config.reranking import RerankingConfigT
from codeweaver.providers.config.utils import (
    AzureOptions,
    ensure_endpoint_version,
    try_for_azure_endpoint,
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

    client_options: Annotated[
        ClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None

    as_backup: Annotated[
        bool,
        Field(
            description="Use this provider as a backup/failsafe. Overrides CodeWeaver's defaults for backup providers."
        ),
    ] = False

    def __init__(self, **data: Any) -> None:
        """Initialize base provider settings."""
        if "tag" not in data:
            data["tag"] = data.get("provider").variable
        object.__setattr__(self, "tag", data["tag"])
        object.__setattr__(self, "client_options", data.get("client_options"))
        object.__setattr__(self, "as_backup", data.get("as_backup", False))
        if self.as_backup and not hasattr(self, "is_provider_backup"):
            self = self._return_as_backup()
        data |= {
            "tag": self.tag,
            "client_options": self.client_options,
            "as_backup": self.as_backup,
        }
        super().__init__()

    @staticmethod
    def _handle_backup_client_options(client_options: ClientOptions | None) -> ClientOptions | None:
        """Handle client options for backup providers."""
        if client_options is None:
            return None
        if hasattr(client_options, "is_provider_backup"):
            return client_options
        from codeweaver.providers.config.utils import create_backup_class

        backup_cls = create_backup_class(
            type(client_options),
            namespace=importlib.import_module(client_options.__module__).__dict__,
        )

        return backup_cls.model_copy(update=(client_options.model_dump() | {"_as_backup": True}))

    def _return_as_backup(self) -> Self:
        """Return a copy of self with as_backup set to True."""
        from codeweaver.providers.config.utils import create_backup_class

        backup_cls = create_backup_class(type(self), namespace=globals())
        instance_settings = {
            k: v if k != "client_options" else self._handle_backup_client_options(v)
            for k, v in self.model_dump().items()
        }
        return backup_cls.model_copy(update=instance_settings)

    def __model_post_init__(self) -> None:
        """Post-initialization to register in DI container and config registry."""
        # Register self in DI container as singleton
        if self.as_backup and not getattr(self.client_options, "is_provider_backup", False):
            object.__setattr__(
                self, "client_options", self._handle_backup_client_options(self.client_options)
            )
        try:
            from codeweaver.core.di import get_container

            container = get_container()
            container.register(type(self), lambda: self)
        except Exception as e:
            # Log if DI not available (monorepo compatibility)
            logger.debug(
                "Failed to register %s in DI container (monorepo mode): %s", type(self).__name__, e
            )

        self._register_configurables()

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
                            endpoint, cohere=(self.client_options._core_provider == Provider.COHERE)
                        )
                    }
                ),
            )
        return self

    def _register_configurables(self) -> None:
        """Register self for config resolution. Classes may optionally implement this class method to register themselves for config resolution."""

    def _telemetry_keys(self) -> None:
        return None

    @abstractmethod
    @computed_field
    def client(self) -> LiteralSDKClient:
        """Return an SDKClient enum member corresponding to this provider settings instance.  Often this is the same as `self.provider`, but not always, and sometimes must be computed (e.g., Azure embedding models)."""
        raise NotImplementedError("client must be implemented by subclasses.")

    def get_client(self) -> Any:
        """Construct and return the client instance based on the provider settings."""
        options = (
            self.client_options.as_settings()
            if isinstance(self.client_options, ClientOptions)
            else {}
        )
        client_import = cast(SDKClient, self.client).client
        kind = next(
            (name for name in {"sparse", "embed", "rerank"} if name in type(self).__name__.lower()),
            None,
        )
        if self.provider == Provider.BEDROCK:
            if not kind:
                raise CodeWeaverDeveloperError(
                    "Kind must be one of 'sparse', 'embed', or 'rerank' for Bedrock provider. File an issue. This is unexpected."
                )
            return client_import._resolve()(
                "bedrock-runtime" if kind == "embed" else "bedrock-agent-runtime", **options
            )
        if not isinstance(client_import, dict):
            return client_import._resolve()(**options)

        client_class = client_import.get(kind)._resolve()

        return client_class(**options)


class BaseProviderSettingsDict(TypedDict, total=False):
    """Base settings for all providers. Represents `BaseProviderSettings` in a TypedDict form."""

    provider: Required[Provider]
    connection: NotRequired[ConnectionConfiguration | None]
    tag: NotRequired[ProviderLiteral]
    client_options: NotRequired[ClientOptions | None]
    as_backup: NotRequired[bool]


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

    cuda: NotRequired[bool | None]
    """Whether to use CUDA (if available). If `None`, will auto-detect. We'll generally assume you want to use CUDA if it's available unless you provide a `False` value here."""
    device_ids: NotRequired[list[int] | None]
    """List of GPU device IDs to use. If `None`, we will try to detect available GPUs using `nvidia-smi` if we can find it. We recommend specifying them because our checks aren't perfect."""


# ===========================================================================
# *            Vector Store Provider Settings
# ===========================================================================


class VectorStoreProviderSettings(BaseProviderSettings):
    """Settings for vector store provider selection and configuration."""

    provider: ClassVar[Literal[Provider.QDRANT, Provider.MEMORY]]

    batch_size: Annotated[
        PositiveInt | None,
        Field(description="Batch size for bulk upsert operations. Defaults to 64."),
    ] = 96


class CollectionConfig(TypedDict, total=False):
    """Common collection configuration for vector store providers."""

    collection_name: NotRequired[str | None]
    """Collection name override. Defaults to a unique name based on the project name."""

    vector_config: NotRequired[Mapping[str, VectorParams | SparseVectorParams] | None]
    """Configuration for individual vector types in the collection."""


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
        batch_size: PositiveInt | None = 96,
        *,
        project_name: str | None = None,
        project_path: Path | None = None,
        as_backup: bool | None = None,
    ) -> None:
        """Initialize Qdrant vector store provider settings.

        Args:
            provider: The vector store provider (Qdrant or Memory).
            connection: Connection configuration for the vector store.
            client_options: Client options for the provider's client.
            collection: Collection configuration for the vector store.
            batch_size: Batch size for bulk upsert operations.
            as_backup: Whether this provider is a backup provider.
            project_name: The name of the project.
            project_path: The path to the project.
        """
        object.__setattr__(self, "client_options", client_options or QdrantClientOptions())
        object.__setattr__(
            self,
            "collection",
            CollectionConfig(
                **(self._default_collection(project_name=project_name, project_path=project_path))
                | (collection or {})
            ),
        )
        object.__setattr__(self, "as_backup", as_backup)
        super().__setattr__("provider", provider)
        super().__setattr__("connection", connection)
        super().__setattr__("batch_size", batch_size)
        super().__init__(provider=provider, connection=connection, batch_size=batch_size)

    # Track resolved values
    _resolved_dimension: int | None = PrivateAttr(default=None)
    _resolved_datatype: str | None = PrivateAttr(default=None)

    def _default_collection(
        self, *, project_name: str | None = None, project_path: Path | None = None
    ) -> CollectionConfig:
        """Return the default collection config."""
        from codeweaver.core import generate_collection_name

        return CollectionConfig(
            collection_name=generate_collection_name(
                is_backup=self.as_backup, project_name=project_name, project_path=project_path
            ),
            vector_config={"dense": VectorParams(), "sparse": SparseVectorParams()},
        )

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
            self.in_memory_config = self.in_memory_config or getattr(
                self,
                "_default_memory_config",
                lambda _x: {"collection_name": generate_collection_name(is_backup=self.as_backup)},
            )(self.collection.get("collection_name"))
        # we'll handle collection config later too -- when models are getting instantiated it's much less painful to wait until the dust settles for inter-model dependencies

        # Register self in DI container as singleton
        try:
            from codeweaver.core.di import get_container

            container = get_container()
            container.register(type(self), lambda: self, singleton=True)
        except Exception as e:
            # Log if DI not available (monorepo compatibility)
            logger.debug(
                "Failed to register %s in DI container (monorepo mode): %s", type(self).__name__, e
            )

        return self

    def _register_configurables(self) -> None:
        """Register self for config resolution."""
        try:
            from codeweaver.core.config.registry import register_configurable

            register_configurable(self)
        except Exception as e:
            # Log if config system not available (monorepo compatibility)
            logger.debug(
                "Failed to register %s for config resolution (monorepo mode): %s",
                type(self).__name__,
                e,
            )

    def config_dependencies(self) -> dict[str, type]:
        """Vector store needs embedding config for dimension/datatype."""
        # Import here to avoid circular dependencies

        return {
            "provider.embedding": EmbeddingProviderSettings,
            "provider.sparse_embedding": SparseEmbeddingProviderSettings,
        }

    async def apply_resolved_config(self, **resolved: Any) -> None:
        """Apply dimension and datatype from embedding config.

        Args:
            **resolved: Should contain "provider.embedding" key with embedding config instance
        """
        config = self.collection.get("vector_config", ())
        dense_key, dense_config = (
            next((k, v) for k, v in config.items() if isinstance(v, VectorParams)),
            ("dense", None),
        )
        self.collection = self.collection or CollectionConfig(vector_config={})
        if (embedding_settings := resolved.get("provider.embedding")) is not None:
            dense_params = embedding_settings.embedding_config.as_vector_params()
            self._resolved_dimension = dense_params.size
            self._resolved_datatype = dense_params.datatype
            if dense_config:
                dense_key = dense_key or "dense"
                self.collection["vector_config"][dense_key] = dense_params  # ty:ignore[invalid-assignment]
        if (sparse_embedding_settings := resolved.get("provider.sparse_embedding")) is not None:
            sparse_config = self.collection.get("vector_config", ())
            sparse_key, sparse_params = (
                next((k, v) for k, v in sparse_config.items() if isinstance(v, SparseVectorParams)),
                None,
            )
            sparse_vector_params = (
                sparse_embedding_settings.embedding_config.as_sparse_vector_params()
            )
            if sparse_params:
                sparse_key = sparse_key or "sparse"
                self.collection["vector_config"][sparse_key] = sparse_vector_params  # ty:ignore[invalid-assignment]

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


class QdrantVectorStoreProviderSettings(_BaseQdrantVectorStoreProviderSettings):
    """Settings for Qdrant vector store provider."""

    provider: ClassVar[Literal[Provider.QDRANT]] = Provider.QDRANT


class MemoryConfig(TypedDict, total=False):
    """Configuration for in-memory vector store provider."""

    persist_path: NotRequired[Path]
    f"""Path for JSON persistence file. Defaults to {get_user_cache_dir()}/vectors/[your_project_name]_store.json."""
    auto_persist: NotRequired[bool]
    """Automatically save after operations. Defaults to True."""
    persist_interval: NotRequired[PositiveInt | None]
    """Periodic persist interval in seconds. Defaults to 300 (5 minutes). Set to None to disable periodic persistence."""


class MemoryVectorStoreProviderSettings(_BaseQdrantVectorStoreProviderSettings):
    """Settings for in-memory vector store provider."""

    provider: ClassVar[Literal[Provider.MEMORY]] = Provider.MEMORY

    in_memory_config: Annotated[
        MemoryConfig, Field(description="In-memory vector store configuration.")
    ]

    def __init__(self, **data: Any) -> None:
        """Initialize Memory vector store provider settings."""
        object.__setattr__(
            self,
            "in_memory_config",
            data.get("in_memory_config")
            or self._default_memory_config(
                collection_name=data.get("collection", {}).get("collection_name", None),
                project_name=data.get("project_name"),
                project_path=data.get("project_path"),
            ),
        )
        super().__init__(**data)

    @staticmethod
    def _get_persist_path(
        *,
        collection_name: str | None = None,
        project_name: str | None = None,
        project_path: Path | None = None,
    ) -> Path:
        """Get the persist path from in_memory_config."""
        return Path(
            f"{get_user_cache_dir()}/vectors/{generate_collection_name(collection_name=collection_name, project_name=project_name, project_path=project_path)}"
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
            persist_interval=300,
            persist_path=persist_path
            or MemoryVectorStoreProviderSettings._get_persist_path(
                collection_name=collection_name,
                project_name=project_name,
                project_path=project_path,
            ),
        )


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
        # Now we have azure and heroku left to consider
        if self.provider not in (Provider.AZURE, Provider.HEROKU):
            raise ValueError(
                f"Cannot resolve embedding client for provider {self.provider.variable}."
            )
        if self.model_name.startswith("cohere") or self.model_name.startswith("embed"):
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

    client_options: Annotated[
        Annotated[CohereClientOptions, Tag(Provider.COHERE.variable)]
        | Annotated[OpenAIClientOptions, Tag(Provider.OPENAI.variable)]
        | None,
        Field(
            description="Client options for the provider's client.",
            discriminator=Discriminator(discriminate_azure_embedding_client_options),
        ),
    ] = None

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
                (not hasattr(self, k))
                or ((value := getattr(self, k, None)) is None)
                or (value and value != v)
            ):
                setattr(self, k, v)
        return self


class BedrockEmbeddingProviderSettings(BedrockProviderMixin, EmbeddingProviderSettings):
    """Provider settings for Bedrock embedding models."""

    client_options: Annotated[
        BedrockClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None


class FastEmbedEmbeddingProviderSettings(FastEmbedProviderMixin, EmbeddingProviderSettings):
    """Provider settings for FastEmbed embedding models."""

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


# ===========================================================================
# *                       Reranking Provider Settings
# ===========================================================================


class RerankingProviderSettings(BaseProviderSettings):
    """Settings for re-ranking models."""

    model_name: Annotated[str, Field(description="The name of the re-ranking model to use.")]
    reranking_config: Annotated[
        RerankingConfigT, Field(description="Model configuration for reranking operations.")
    ]
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


class FastEmbedRerankingProviderSettings(FastEmbedProviderMixin, RerankingProviderSettings):
    """Provider settings for FastEmbed reranking models."""

    client_options: Annotated[
        FastEmbedClientOptions | None,
        Field(description="Client options for the SDK provider's client."),
    ] = None


class BedrockRerankingProviderSettings(BedrockProviderMixin, RerankingProviderSettings):
    """Provider settings for Bedrock reranking models."""

    client_options: Annotated[
        BedrockClientOptions | None,
        Field(description="Client options for the SDK provider's client."),
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
    "BaseEmbeddingProviderSettings",
    "BaseProviderSettings",
    "BaseProviderSettingsDict",
    "BedrockEmbeddingProviderSettings",
    "BedrockProviderMixin",
    "BedrockRerankingProviderSettings",
    "CollectionConfig",
    "ConnectionConfiguration",
    "ConnectionRateLimitConfig",
    "DataProviderSettings",
    "EmbeddingProviderSettings",
    "FastEmbedEmbeddingProviderSettings",
    "FastEmbedProviderMixin",
    "FastEmbedRerankingProviderSettings",
    "FastEmbedSparseEmbeddingProviderSettings",
    "MemoryConfig",
    "MemoryVectorStoreProviderSettings",
    "ModelString",
    "QdrantVectorStoreProviderSettings",
    "RerankingProviderSettings",
    "SparseEmbeddingProviderSettings",
    "VectorStoreProviderSettings",
)

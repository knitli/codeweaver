"""Top-level settings for vector store providers."""

from __future__ import annotations

import logging

from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, ClassVar, Literal, NotRequired, Self, TypedDict, cast

from pydantic import Field, PositiveInt, PrivateAttr, Tag, computed_field, model_validator
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

from codeweaver.core import ProviderCategory
from codeweaver.core.constants import (
    DEFAULT_PERSIST_INTERVAL,
    DEFAULT_VECTOR_STORE_BATCH_SIZE,
    DEFAULT_VECTOR_STORE_PERSIST_SUBPATH,
    LOCALHOST,
)
from codeweaver.core.di import INJECTED
from codeweaver.core.types import (
    AnonymityConversion,
    BasedModel,
    FilteredKey,
    FilteredKeyT,
    Provider,
    SDKClient,
)
from codeweaver.core.utils import (
    deep_merge_dicts,
    generate_collection_name,
    get_user_state_dir,
    has_package,
)
from codeweaver.providers.config.categories.base import (
    BaseProviderCategorySettings,
    ConnectionConfiguration,
)
from codeweaver.providers.config.categories.utils import PROVIDER_DISCRIMINATOR
from codeweaver.providers.config.clients.base import ClientOptions
from codeweaver.providers.config.clients.vector_store import QdrantClientOptions
from codeweaver.providers.dependencies import EmbeddingCapabilityGroupDep
from codeweaver.providers.types.embedding import EmbeddingCapabilityGroup
from codeweaver.providers.vector_stores.metadata import CollectionMetadata


logger = logging.getLogger(__name__)

if has_package("codeweaver.engine"):
    from codeweaver.engine.config import FailoverDetector, FailoverSettings


def _get_embedding_group(group: EmbeddingCapabilityGroupDep = INJECTED) -> EmbeddingCapabilityGroup:
    """Get the embedding capability group, using dependency injection."""
    return group


class BaseVectorStoreProviderSettings(BaseProviderCategorySettings):
    """Base settings for vector store providers."""

    provider: Literal[Provider.QDRANT, Provider.MEMORY]

    batch_size: Annotated[
        PositiveInt | None,
        Field(description="Batch size for bulk upsert operations. Defaults to 64."),
    ] = DEFAULT_VECTOR_STORE_BATCH_SIZE

    client_options: Annotated[
        ClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None

    category: ClassVar[Literal[ProviderCategory.VECTOR_STORE]] = ProviderCategory.VECTOR_STORE


class VectorStoreProviderSettings(BaseVectorStoreProviderSettings):
    """Settings for vector store provider selection and configuration.

    Generic settings for vector store providers. Currently unused as we only have one vector store provider (Qdrant), but this allows us to easily add more providers in the future without breaking changes.
    """


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
    _vectors_initialized: bool = PrivateAttr(default=False)

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """Return telemetry keys for privacy-first data collection."""
        from codeweaver.core.types import AnonymityConversion

        return {FilteredKey("collection_name"): AnonymityConversion.HASH}

    async def params(self) -> CollectionParams:
        """Return the Qdrant collection parameters for this configuration."""
        if not self._vectors_initialized:
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
                assembled_vectors = cast(dict[str, VectorParams], vectors)
            else:
                assembled_vectors = cast(dict[str, VectorParams], vectors.model_dump())
        else:
            assembled_vectors = {}
        self.vectors_config = deep_merge_dicts(dict(self.vectors_config or {}), assembled_vectors)  # type: ignore
        self.sparse_vectors_config = deep_merge_dicts(  # type: ignore
            dict(self.sparse_vectors_config or {}),  # type: ignore
            cast(dict[str, SparseVectorParams], params.sparse_vectors or {}),
        )
        self._vectors_initialized = True

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
            collection_data = {}
        elif isinstance(collection, CollectionConfig):
            collection_data = collection.model_dump(exclude_none=True)
        else:
            collection_data = collection
        prepared_collection = CollectionConfig.model_validate(
            self._default_collection(
                project_name=project_name, project_path=project_path
            ).model_dump()
            | collection_data
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
                settings=self,
                embedding_group=embedding_group,
                failover_settings=failover_settings,
                failover_detector=failover_detector,
            )
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
                settings=self,
                embedding_group=embedding_group,
                failover_settings=failover_settings,
                failover_detector=failover_detector,
            )
        except Exception as e:
            logger.debug("DI container not available, using basic config: %s", e)
            if not self.collection._vectors_initialized:
                if embedding_group is None:
                    embedding_group = _get_embedding_group()
                await self.collection.set_vector_params(embedding_group)
            return await self.collection.as_qdrant_config(metadata=metadata)
        else:
            return await service.get_collection_config(metadata)


class QdrantVectorStoreProviderSettings(_BaseQdrantVectorStoreProviderSettings):
    """Settings for Qdrant vector store provider."""

    provider: Literal[Provider.QDRANT]


class MemoryConfig(TypedDict, total=False):
    """Configuration for in-memory vector store provider."""

    persist_path: NotRequired[Path]
    "Path for JSON persistence file. Defaults to [your_user_directory]/codeweaver/vectors/[your_project_name]-[filepath-hash]"
    auto_persist: NotRequired[bool]
    "Automatically save after operations. Defaults to True."
    persist_interval: NotRequired[PositiveInt | None]
    "Periodic persist interval in seconds. Defaults to 300 (5 minutes). Set to None to disable periodic persistence."


class MemoryVectorStoreProviderSettings(_BaseQdrantVectorStoreProviderSettings):
    """Settings for in-memory vector store provider."""

    provider: Literal[Provider.MEMORY]
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
            collection_configuration = {}
        elif isinstance(collection, CollectionConfig):
            collection_configuration = collection.model_dump(exclude_none=True)
        else:
            collection_configuration = collection
        parent_default_collection = super()._default_collection(
            project_name=project_name, project_path=project_path
        )
        prepared_collection = CollectionConfig.model_validate(
            parent_default_collection.model_dump() | collection_configuration
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


type VectorStoreProviderSettingsType = Annotated[
    Annotated[QdrantVectorStoreProviderSettings, Tag("qdrant")]
    | Annotated[MemoryVectorStoreProviderSettings, Tag("memory")],
    Field(
        description="The settings for a vector store provider, which includes the provider type and its specific configuration.",
        discriminator=PROVIDER_DISCRIMINATOR,
    ),
]

__all__ = (
    "BaseVectorStoreProviderSettings",
    "CollectionConfig",
    "MemoryVectorStoreProviderSettings",
    "QdrantVectorStoreProviderSettings",
    "VectorStoreProviderSettings",
)

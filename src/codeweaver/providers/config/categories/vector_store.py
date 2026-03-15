# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Top-level settings for vector store providers."""

from __future__ import annotations

import logging

from pathlib import Path
from typing import Annotated, ClassVar, Literal, NotRequired, Self, TypedDict

from pydantic import Field, PositiveInt, PrivateAttr, Tag, computed_field, model_validator
from qdrant_client.models import CollectionConfig as QdrantCollectionConfig

from codeweaver.core import ProviderCategory
from codeweaver.core.constants import (
    DEFAULT_PERSIST_INTERVAL,
    DEFAULT_VECTOR_STORE_BATCH_SIZE,
    DEFAULT_VECTOR_STORE_PERSIST_SUBPATH,
    LOCALHOST,
)
from codeweaver.core.types import Provider, SDKClient
from codeweaver.core.utils import generate_collection_name, get_user_state_dir, has_package
from codeweaver.providers.config.categories.base import (
    BaseProviderCategorySettings,
    ConnectionConfiguration,
)
from codeweaver.providers.config.categories.utils import PROVIDER_DISCRIMINATOR
from codeweaver.providers.config.clients.base import ClientOptions
from codeweaver.providers.config.clients.vector_store import QdrantClientOptions
from codeweaver.providers.config.sdk.vector_store import CollectionConfig, get_embedding_group
from codeweaver.providers.types.embedding import EmbeddingCapabilityGroup
from codeweaver.providers.types.vector_store import CollectionMetadata


logger = logging.getLogger(__name__)

if has_package("codeweaver.engine"):
    from codeweaver.engine.config import FailoverDetector, FailoverSettings


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


class _BaseQdrantVectorStoreProviderSettings(VectorStoreProviderSettings):
    """Qdrant-specific settings for the Qdrant and Memory providers. Qdrant is the only currently supported vector store, but others may be added in the future."""

    client_options: Annotated[
        QdrantClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None
    collection: Annotated[
        CollectionConfig, Field(description="Collection configuration for the vector store.")
    ]
    in_memory_config: MemoryConfig | None = Field(
        default=None, description="In-memory vector store configuration."
    )

    def __init__(
        self,
        provider: Literal[Provider.QDRANT, Provider.MEMORY] = Provider.QDRANT,
        connection: ConnectionConfiguration | None = None,
        client_options: QdrantClientOptions | None = None,
        collection: CollectionConfig | None = None,
        batch_size: PositiveInt | None = DEFAULT_VECTOR_STORE_BATCH_SIZE,
        in_memory_config: MemoryConfig | None = None,
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
            in_memory_config: In-memory vector store configuration.
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
        super().__init__(
            provider=provider,
            connection=connection,
            client_options=prepared_client_options,
            collection=prepared_collection,  # ty: ignore[unknown-argument]
            batch_size=batch_size,
            in_memory_config=in_memory_config,  # ty: ignore[unknown-argument]
        )

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
                    embedding_group = get_embedding_group()
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
        collection_name: str | None = None,
    ) -> None:
        """Initialize Memory vector store provider settings."""
        if collection_name:
            if collection is None:
                collection = CollectionConfig(collection_name=collection_name)
            elif isinstance(collection, CollectionConfig):
                collection.collection_name = collection_name
            elif isinstance(collection, dict):
                collection["collection_name"] = collection_name

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
        super().__init__(
            provider=provider,
            connection=connection,
            client_options=prepared_client_options,
            collection=prepared_collection,
            batch_size=batch_size,
            in_memory_config=in_memory_config,
            project_name=project_name,
            project_path=project_path,
        )

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
    "MemoryConfig",
    "MemoryVectorStoreProviderSettings",
    "QdrantVectorStoreProviderSettings",
    "VectorStoreProviderSettings",
    "VectorStoreProviderSettingsType",
)

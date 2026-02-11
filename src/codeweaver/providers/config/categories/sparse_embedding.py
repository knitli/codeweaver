"""Top-level provider settings for sparse embedding providers."""

from typing import Annotated, Any, ClassVar, Literal

from pydantic import Field, Tag, computed_field

from codeweaver.core import Provider, ProviderCategory
from codeweaver.core.types import ModelNameT, SDKClient
from codeweaver.core.utils import has_package
from codeweaver.providers import ClientOptions
from codeweaver.providers.config.categories.base import BaseProviderCategorySettings
from codeweaver.providers.config.categories.mixins import FastEmbedProviderMixin
from codeweaver.providers.config.categories.utils import PROVIDER_DISCRIMINATOR, is_cloud_provider
from codeweaver.providers.config.clients import (
    FastEmbedClientOptions,
    SentenceTransformersClientOptions,
)
from codeweaver.providers.config.sdk.sparse_embedding import (
    BaseSparseEmbeddingConfig,
    SparseEmbeddingConfigT,
)


if has_package("sentence_transformers"):
    # SentenceTransformerModelCardData contains these forward references:
    # - eval_results_dict: dict[SentenceEvaluator, dict[str, Any]] | None
    # - model: SentenceTransformer | None
    # The type is used in SentenceTransformersClientOptions
    # So if the configured settings uses SentenceTransformersClientOptions
    # Then we need to have these in the namespace for pydantic to resolve
    from sentence_transformers import SentenceTransformer as SentenceTransformer
    from sentence_transformers.evaluation import SentenceEvaluator as SentenceEvaluator
    from sentence_transformers.model_card import (
        SentenceTransformerModelCardData as SentenceTransformerModelCardData,
    )


class BaseSparseEmbeddingProviderSettings(BaseProviderCategorySettings):
    """Base settings for sparse embedding providers."""

    provider: Literal[Provider.SENTENCE_TRANSFORMERS, Provider.FASTEMBED]

    model_name: Annotated[
        ModelNameT, Field(description="The name of the sparse embedding model to use.")
    ]
    sparse_embedding_config: Annotated[
        BaseSparseEmbeddingConfig,
        Field(description="Model configuration for sparse embedding operations."),
    ]
    client_options: Annotated[
        ClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None


class SparseEmbeddingProviderSettings(BaseSparseEmbeddingProviderSettings):
    """Settings for sparse embedding models."""

    provider: Literal[Provider.SENTENCE_TRANSFORMERS]

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

    category: ClassVar[Literal[ProviderCategory.SPARSE_EMBEDDING]] = (
        ProviderCategory.SPARSE_EMBEDDING
    )

    @computed_field
    @property
    def client(self) -> Literal[SDKClient.SENTENCE_TRANSFORMERS]:
        """Return the sparse embedding SDKClient enum member."""
        return SDKClient.SENTENCE_TRANSFORMERS

    def is_cloud(self) -> bool:
        """Return True if the provider settings are for a cloud deployment."""
        return is_cloud_provider(self)

    tag: Literal["sentence-transformers"] = "sentence-transformers"

    def __init__(self, **data: Any) -> None:
        """Initialize the SparseEmbeddingProviderSettings."""
        model_key = (
            "model_name_or_path" if self.client == SDKClient.SENTENCE_TRANSFORMERS else "model_name"
        )

        if "client_options" in data and isinstance(data["client_options"], dict):
            data["client_options"]["tag"] = self.client.variable
            data["client_options"][model_key] = data.get("model_name", self.model_name)
        elif data.get("client_options"):
            data["client_options"].tag = self.client.variable
            setattr(data["client_options"], model_key, data.get("model_name", self.model_name))
        if isinstance(data["sparse_embedding_config"], dict):
            data["sparse_embedding_config"]["model_name"] = data.get("model_name", self.model_name)
        else:
            data["sparse_embedding_config"].model_name = data.get("model_name", self.model_name)
        super().__init__(**data)


class FastEmbedSparseEmbeddingProviderSettings(
    FastEmbedProviderMixin, SparseEmbeddingProviderSettings
):
    """Provider settings for FastEmbed sparse embedding models."""

    provider: Literal[Provider.FASTEMBED]

    client_options: Annotated[
        FastEmbedClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None

    @computed_field
    @property
    def client(self) -> Literal[SDKClient.FASTEMBED]:
        """Return the sparse embedding SDKClient enum member."""
        return SDKClient.FASTEMBED


type SparseEmbeddingProviderSettingsType = Annotated[
    Annotated[FastEmbedSparseEmbeddingProviderSettings, Tag("fastembed")]
    | Annotated[SparseEmbeddingProviderSettings, Tag("sentence_transformers")],
    Field(
        description="A type alias representing all sparse embedding provider settings.",
        discriminator=PROVIDER_DISCRIMINATOR,
    ),
]
"""A type alias representing all sparse embedding provider settings."""

__all__ = (
    "FastEmbedSparseEmbeddingProviderSettings",
    "SparseEmbeddingProviderSettings",
    "SparseEmbeddingProviderSettingsType",
)

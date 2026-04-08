# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

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
    try:
        from sentence_transformers import SentenceTransformer as SentenceTransformer
        from sentence_transformers.evaluation import SentenceEvaluator as SentenceEvaluator
        from sentence_transformers.model_card import (
            SentenceTransformerModelCardData as SentenceTransformerModelCardData,
        )
    except ImportError:
        SentenceTransformer = Any  # type: ignore[assignment, misc]
        SentenceEvaluator = Any  # type: ignore[assignment, misc]
        SentenceTransformerModelCardData = Any  # type: ignore[assignment, misc]
else:
    SentenceTransformer = Any
    SentenceEvaluator = Any
    SentenceTransformerModelCardData = Any


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

    def __init__(self, **data: Any) -> None:
        """Initialize the SparseEmbeddingProviderSettings.

        Ensures `client_options` is always populated with a `model_name`-bearing
        client options instance before pydantic validation runs. The dispatch
        path in `providers/dependencies/providers.py::_construct_provider`
        unconditionally calls `settings.client_options.as_settings()` and
        passes the resulting kwargs to the fastembed factory or
        SentenceTransformer class — if `client_options` is `None`, the
        resolved class is instantiated with an empty kwargs dict and crashes
        with `missing 1 required positional argument: 'model_name'`.

        Mirrors the auto-population logic in
        `categories/embedding.py::EmbeddingProviderSettings._initialize`
        (which predates this fix and already correctly handles the
        dense-embedding path).
        """
        # Resolve the raw provider value from kwargs (string or enum) before
        # calling super().__init__; we can't read `self.provider` yet because
        # pydantic hasn't run validation. `self.client` is a classmethod-ish
        # @computed_field that returns a constant per subclass, so it IS safe
        # to access pre-init — but provider-specific branching is clearer via
        # the raw data.
        raw_provider = data.get("provider")
        provider = (
            raw_provider
            if isinstance(raw_provider, Provider)
            else Provider.from_string(raw_provider)
            if raw_provider
            else None
        )
        model_name = data.get("model_name")
        model_key = (
            "model_name_or_path"
            if provider == Provider.SENTENCE_TRANSFORMERS
            else "model_name"
        )

        # (a) No client_options yet — construct the right class from model_name.
        if "client_options" not in data and model_name:
            if provider == Provider.FASTEMBED:
                data["client_options"] = FastEmbedClientOptions(model_name=model_name)
            elif provider == Provider.SENTENCE_TRANSFORMERS:
                data["client_options"] = SentenceTransformersClientOptions(
                    model_name_or_path=str(model_name)
                )
        # (b) client_options supplied but may lack model_name — inject it.
        elif "client_options" in data and isinstance(data["client_options"], dict):
            data["client_options"].setdefault(model_key, model_name)
        elif (
            isinstance(data.get("client_options"), ClientOptions)
            and getattr(data["client_options"], model_key, None) is None
        ):
            setattr(data["client_options"], model_key, model_name)

        # Propagate model_name into sparse_embedding_config too, matching the
        # existing behavior.
        if isinstance(data.get("sparse_embedding_config"), dict):
            data["sparse_embedding_config"]["model_name"] = model_name
        elif data.get("sparse_embedding_config") is not None:
            data["sparse_embedding_config"].model_name = model_name

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
    "BaseSparseEmbeddingProviderSettings",
    "FastEmbedSparseEmbeddingProviderSettings",
    "SparseEmbeddingProviderSettings",
    "SparseEmbeddingProviderSettingsType",
)

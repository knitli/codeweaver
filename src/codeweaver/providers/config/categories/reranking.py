# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Top-level settings for reranking providers."""

from __future__ import annotations

import contextlib

from typing import Annotated, Any, ClassVar, Literal, Self, cast

from pydantic import Field, PositiveInt, Tag, computed_field, model_validator

from codeweaver.core import Provider
from codeweaver.core.constants import DEFAULT_RERANKING_MAX_RESULTS
from codeweaver.core.types import LiteralSDKClient, ModelNameT, ProviderCategory, SDKClient
from codeweaver.providers import (
    BedrockRerankingConfig,
    CohereClientOptions,
    CohereRerankingConfig,
    FastEmbedRerankingConfig,
    SentenceTransformersClientOptions,
    SentenceTransformersRerankingConfig,
    VoyageRerankingConfig,
)
from codeweaver.providers.config import BedrockRerankingModelConfig
from codeweaver.providers.config.categories import PROVIDER_DISCRIMINATOR
from codeweaver.providers.config.categories.base import BaseProviderCategorySettings
from codeweaver.providers.config.categories.mixins import (
    BedrockProviderMixin,
    FastEmbedProviderMixin,
)
from codeweaver.providers.config.categories.utils import is_cloud_provider
from codeweaver.providers.config.clients import (
    BedrockClientOptions,
    FastEmbedClientOptions,
    GeneralRerankingClientOptionsType,
)
from codeweaver.providers.config.sdk import RerankingConfigT


def _config_factory[T: RerankingConfigT](data: dict[str, Any], config_class: type[T]) -> T:
    """Factory function to create a reranking config instance from the input data."""
    defaults = config_class._defaults() if hasattr(config_class, "_defaults") else {}  # ty:ignore[invalid-argument-type]
    config_data = (
        defaults
        | {"model_name": data.get("model_name"), "provider": data.get("provider")}
        | (
            data.get("reranking_config", {})
            if isinstance(data.get("reranking_config"), dict)
            else data.get("reranking_config", {}).model_dump()
            if data.get("reranking_config")
            else {}
        )
    )
    if config_data.get("provider") == Provider.BEDROCK and data.get("model_arn"):
        config_data["model"] = cast(dict[str, Any], config_data.get("model", {})) | {
            "model_arn": data["model_arn"]
        }
    if (
        data.get("top_n", DEFAULT_RERANKING_MAX_RESULTS) != DEFAULT_RERANKING_MAX_RESULTS
        and (provider := config_data.get("provider"))
        and provider not in {Provider.VOYAGE, Provider.FASTEMBED}
    ):
        assert config_data["rerank"] is not None, (  # noqa: S101
            "rerank config must be provided if top_n is set to a value other than the default"
        )
        rerank = cast(dict[str, Any], config_data["rerank"])
        match provider:
            case Provider.SENTENCE_TRANSFORMERS:
                rerank["top_k"] = data["top_n"]
            case Provider.BEDROCK:
                rerank["number_of_results"] = data["top_n"]
            case Provider.COHERE:
                rerank["top_k"] = data["top_n"]
    return config_class.model_validate(config_data)


class BaseRerankingProviderSettings(BaseProviderCategorySettings):
    """Base settings for reranking providers."""

    model_name: Annotated[ModelNameT, Field(description="The name of the re-ranking model to use.")]
    reranking_config: Annotated[
        RerankingConfigT, Field(description="Model configuration for reranking operations.")
    ]
    top_n: PositiveInt = DEFAULT_RERANKING_MAX_RESULTS
    client_options: (
        Annotated[
            GeneralRerankingClientOptionsType,
            Field(description="Client options for the provider's client."),
        ]
        | None
    ) = None

    category: ClassVar[Literal[ProviderCategory.RERANKING]] = ProviderCategory.RERANKING

    @computed_field
    @property
    def client(self) -> LiteralSDKClient:
        """Return the reranking SDKClient enum member."""
        return cast(LiteralSDKClient, SDKClient.from_string(self.provider.variable))

    def is_cloud(self) -> bool:
        """Return True if the provider is a cloud provider, False otherwise."""
        return is_cloud_provider(self)


class RerankingProviderSettings(BaseRerankingProviderSettings):
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

    category: ClassVar[Literal[ProviderCategory.RERANKING]] = ProviderCategory.RERANKING

    def __init__(self, **data: Any) -> None:
        """Initialize the RerankingProviderSettings."""
        raw_provider = data.get("provider")
        provider = (
            raw_provider
            if isinstance(raw_provider, Provider)
            else Provider(raw_provider)
            if raw_provider
            else None
        )
        model_name = data.get("model_name")
        if (
            "client_options" not in data
            and model_name
            and provider in (Provider.SENTENCE_TRANSFORMERS, Provider.FASTEMBED)
        ):
            # Pre-build client_options to avoid default_factory field ordering issue:
            # client_options (from BaseProviderCategorySettings) is validated before model_name
            # (from RerankingProviderSettings) in pydantic v2, so default_factory can't access model_name.
            if provider == Provider.FASTEMBED:
                data["client_options"] = FastEmbedClientOptions(model_name=model_name)
            else:
                data["client_options"] = SentenceTransformersClientOptions(
                    model_name_or_path=str(model_name)
                )
        elif (
            "client_options" in data
            and isinstance(data["client_options"], dict)
            and provider in (Provider.SENTENCE_TRANSFORMERS, Provider.FASTEMBED)
        ):
            if provider == Provider.FASTEMBED:
                data["client_options"]["model_name"] = model_name
            else:
                data["client_options"]["model_name_or_path"] = model_name

        reranking_config = data.get("reranking_config")
        if isinstance(reranking_config, dict):
            reranking_config["model_name"] = model_name
            reranking_config["provider"] = provider
        elif reranking_config is not None:
            reranking_config.model_name = model_name
            with contextlib.suppress(AttributeError):
                reranking_config.provider = provider
                reranking_config.provider = provider
        super().__init__(**data)


def _construct_st_client_options(data: dict[str, Any]) -> SentenceTransformersClientOptions:
    """Construct a SentenceTransformersClientOptions from the input data."""
    return SentenceTransformersClientOptions(
        model_name_or_path=data["model_name"], **data.get("client_options", {})
    )


class CohereRerankingProviderSettings(RerankingProviderSettings):
    """Provider settings for Cohere re-ranking models."""

    provider: Literal[Provider.COHERE]
    client_options: Annotated[
        CohereClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None
    reranking_config: CohereRerankingConfig = Field(
        default_factory=lambda data: _config_factory(data, CohereRerankingConfig),
        description="Reranking configuration for the Cohere re-ranking provider.",
    )


class VoyageRerankingProviderSettings(RerankingProviderSettings):
    """Provider settings for Voyage re-ranking models."""

    provider: Literal[Provider.VOYAGE]
    client_options: Annotated[
        GeneralRerankingClientOptionsType | None,
        Field(description="Client options for the provider's client."),
    ] = None
    reranking_config: VoyageRerankingConfig = Field(
        default_factory=lambda data: _config_factory(data, VoyageRerankingConfig),
        description="Reranking configuration for the Voyage re-ranking provider.",
    )


class SentenceTransformersRerankingProviderSettings(RerankingProviderSettings):
    """Provider settings for Sentence Transformers re-ranking models."""

    provider: Literal[Provider.SENTENCE_TRANSFORMERS]
    client_options: SentenceTransformersClientOptions = Field(
        description="Client options for the Sentence Transformers re-ranking provider.",
        default_factory=lambda data: _construct_st_client_options(data),
    )
    reranking_config: SentenceTransformersRerankingConfig = Field(
        default_factory=lambda data: _config_factory(data, SentenceTransformersRerankingConfig),
        description="Client options for the Sentence Transformers re-ranking provider.",
    )


class FastEmbedRerankingProviderSettings(FastEmbedProviderMixin, RerankingProviderSettings):
    """Provider settings for FastEmbed reranking models."""

    provider: Literal[Provider.FASTEMBED]
    client_options: Annotated[
        FastEmbedClientOptions | None,
        Field(description="Client options for the SDK provider's client."),
    ] = None
    reranking_config: FastEmbedRerankingConfig = Field(
        default_factory=lambda data: _config_factory(data, FastEmbedRerankingConfig),
        description="Reranking configuration for the FastEmbed re-ranking provider.",
    )


class BedrockRerankingProviderSettings(BedrockProviderMixin, RerankingProviderSettings):
    """Provider settings for Bedrock reranking models."""

    provider: Literal[Provider.BEDROCK]
    client_options: BedrockClientOptions = Field(
        description="Client options for the Bedrock re-ranking provider.",
        default_factory=lambda data: BedrockClientOptions(**data.get("client_options", {})),
    )
    reranking_config: BedrockRerankingConfig = Field(
        description="Reranking configuration for the Bedrock re-ranking provider.",
        default_factory=lambda data: BedrockRerankingConfig(**data.get("reranking_config", {})),
    )

    @model_validator(mode="after")
    def _inject_model_arn_into_model_config(self) -> Self:
        """Inject model_arn into reranking_config.model if not already present.

        Bedrock requires the model ARN in the model configuration. This validator
        ensures it's available in the reranking_config's model field.
        """
        from codeweaver.providers.config.sdk import BedrockRerankingConfig

        # Type narrow to ensure we're working with BedrockRerankingConfig
        if not isinstance(self.reranking_config, BedrockRerankingConfig):
            return self

        # Inject ARN into model config
        if self.reranking_config and not self.reranking_config.model:
            self.reranking_config.model = BedrockRerankingModelConfig(model_arn=self.model_arn)

        return self


type RerankingProviderSettingsType = Annotated[
    Annotated[
        BedrockRerankingProviderSettings,
        Field(description="Settings for Bedrock reranking provider."),
        Tag("bedrock"),
    ]
    | Annotated[
        FastEmbedRerankingProviderSettings,
        Field(description="Settings for FastEmbed reranking provider."),
        Tag("fastembed"),
    ]
    | Annotated[
        VoyageRerankingProviderSettings,
        Field(description="Settings for Voyage reranking provider."),
        Tag("voyage"),
    ]
    | Annotated[
        CohereRerankingProviderSettings,
        Field(description="Settings for Cohere reranking provider."),
        Tag("cohere"),
    ]
    | Annotated[
        SentenceTransformersRerankingProviderSettings,
        Field(description="Settings for Sentence Transformers reranking provider."),
        Tag("sentence_transformers"),
    ]
    | Annotated[
        RerankingProviderSettings,
        Field(description="Settings for simple reranking provider."),
        Tag(""),
    ],
    PROVIDER_DISCRIMINATOR,
]

__all__ = (
    "BaseRerankingProviderSettings",
    "BedrockRerankingProviderSettings",
    "CohereRerankingProviderSettings",
    "FastEmbedRerankingProviderSettings",
    "RerankingProviderSettings",
    "RerankingProviderSettingsType",
    "SentenceTransformersRerankingProviderSettings",
    "VoyageRerankingProviderSettings",
)

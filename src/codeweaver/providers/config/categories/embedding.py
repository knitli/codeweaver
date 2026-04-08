# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Top-level settings classes for embedding providers."""

from __future__ import annotations

import contextlib
import importlib
import logging

from abc import ABC, abstractmethod
from functools import cached_property
from typing import Annotated, Any, ClassVar, Literal, NotRequired, Required, Self, TypedDict, cast

from pydantic import (
    AnyUrl,
    ConfigDict,
    Discriminator,
    Field,
    NonNegativeInt,
    PrivateAttr,
    Tag,
    computed_field,
    model_validator,
)

from codeweaver.core import DatatypeMismatchError, DimensionMismatchError, ProviderCategory
from codeweaver.core.types import (
    BasedModel,
    LiteralSDKClient,
    ModelName,
    ModelNameT,
    Provider,
    SDKClient,
)
from codeweaver.core.utils import has_package
from codeweaver.providers import (
    BedrockCohereConfigDict,
    BedrockEmbeddingConfig,
    BedrockEmbeddingRequestParams,
    BedrockTitanV2ConfigDict,
    EmbeddingModelCapabilities,
    FastEmbedEmbeddingConfig,
    GoogleClientOptions,
    GoogleEmbeddingConfig,
    HuggingFaceClientOptions,
    HuggingFaceEmbeddingConfig,
    MistralEmbeddingConfig,
    SentenceTransformersClientOptions,
    SentenceTransformersEmbeddingConfig,
    SentenceTransformersEncodeDict,
    VoyageClientOptions,
    VoyageEmbeddingConfig,
)
from codeweaver.providers.config import (
    CohereEmbeddingConfig,
    CohereEmbeddingOptionsDict,
    GoogleEmbeddingRequestParams,
    MistralClientOptions,
)
from codeweaver.providers.config.categories.base import BaseProviderCategorySettings
from codeweaver.providers.config.categories.mixins import (
    AzureProviderMixin,
    BedrockProviderMixin,
    FastEmbedProviderMixin,
)
from codeweaver.providers.config.categories.utils import (
    CORE_EMBEDDING_PROVIDER_DISCRIMINATOR,
    is_cloud_provider,
)
from codeweaver.providers.config.clients.multi import (
    BedrockClientOptions,
    CohereClientOptions,
    FastEmbedClientOptions,
    GeneralEmbeddingClientOptionsType,
    OpenAIClientOptions,
    discriminate_azure_embedding_client_options,
)
from codeweaver.providers.config.clients.utils import try_for_azure_endpoint
from codeweaver.providers.config.sdk import EmbeddingConfigT
from codeweaver.providers.data.utils import get_provider_names_for_category


logger = logging.getLogger(__name__)
if has_package("sentence_transformers"):
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
possible_tags = get_provider_names_for_category("embedding")


def _get_embedding_capabilities_sync(model_name: ModelNameT) -> EmbeddingModelCapabilities | None:
    """Synchronously get the embedding model capabilities for a given model name."""
    import asyncio

    try:
        resolver_module = importlib.import_module(
            "codeweaver.providers.embedding.capabilities.resolver"
        )
        resolver = resolver_module.EmbeddingCapabilityResolver()
    except Exception as e:
        logger.debug("Failed to resolve capabilities for %s: %s", model_name, e)
        return None
    else:
        return asyncio.run(resolver.resolve(model_name))


def _get_embedding_capabilities(model_name: ModelNameT) -> EmbeddingModelCapabilities | None:
    """Get the embedding model capabilities for a given model name.

    Args:
        model_name: The name of the embedding model.

    Returns:
        The embedding model capabilities or None if not found.
    """
    return _get_embedding_capabilities_sync(model_name)


class BaseEmbeddingProviderSettings(BaseProviderCategorySettings, ABC):
    """Settings for (dense) embedding models. It validates that the model and provider settings are compatible and complete, reconciling environment variables and config file settings as needed."""

    category: ClassVar[Literal[ProviderCategory.EMBEDDING]] = ProviderCategory.EMBEDDING
    config_type: Literal["symmetric"] = "symmetric"

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
        return is_cloud_provider(self)


class EmbeddingProviderSettings(BaseEmbeddingProviderSettings):
    """Settings for dense embedding models."""

    model_name: Annotated[
        ModelNameT,
        Field(
            description="The name of the embedding model to use. This should correspond to a model supported by the selected provider and formatted as the provider expects. For builtin models, this is the name as listed with `codeweaver list models`."
        ),
    ]
    embedding_config: Annotated[
        EmbeddingConfigT, Field(description="Model configuration for embedding operations.")
    ]
    client_options: GeneralEmbeddingClientOptionsType | None = None

    def _initialize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Perform any additional initialization steps. Happens before pydantic initialization and the model's post_init."""
        raw_provider = data.get("provider")
        provider = (
            raw_provider
            if isinstance(raw_provider, Provider)
            else Provider(raw_provider)
            if raw_provider
            else None
        )
        if provider in (
            Provider.HUGGINGFACE_INFERENCE,
            Provider.SENTENCE_TRANSFORMERS,
            Provider.FASTEMBED,
        ):
            model_name = data.get("model_name")
            if "client_options" not in data and model_name:
                if provider == Provider.FASTEMBED:
                    from codeweaver.providers.config.clients.multi import FastEmbedClientOptions

                    data["client_options"] = FastEmbedClientOptions(
                        model_name=ModelName(model_name)
                    )
                elif provider == Provider.SENTENCE_TRANSFORMERS:
                    from codeweaver.providers.config.clients.multi import (
                        SentenceTransformersClientOptions,
                    )

                    data["client_options"] = SentenceTransformersClientOptions(
                        model_name_or_path=str(model_name)
                    )
                elif provider == Provider.HUGGINGFACE_INFERENCE:
                    from codeweaver.providers.config.clients.multi import HuggingFaceClientOptions

                    data["client_options"] = HuggingFaceClientOptions(model=str(model_name))
            elif "client_options" in data:
                if provider == Provider.FASTEMBED:
                    data = self._set_client_option(data, "model_name", model_name)
                if provider == Provider.SENTENCE_TRANSFORMERS:
                    data = self._set_client_option(data, "model_name_or_path", model_name)
                else:
                    data = self._set_client_option(data, "model", model_name)
        data |= super()._initialize(data)
        return data

    def __init__(self, **data: Any) -> None:
        """Initialize embedding provider settings."""
        if model_name := data.get("model_name"):
            data["model_name"] = ModelName(model_name)
        config = data.get("embedding_config")
        if config is not None:
            if (
                not (
                    config_model_name := (
                        config.get("model_name") if isinstance(config, dict) else config.model_name
                    )
                )
                and model_name
            ):
                config["model_name"] = ModelName(model_name)
            elif config_model_name and (not model_name):
                data["model_name"] = ModelName(config_model_name)
        super().__init__(**data)

    def _get_capabilities(self) -> Any:
        """Get capabilities for the embedding model."""
        if self.embedding_config and self.embedding_config.capabilities:
            return self.embedding_config.capabilities
        return _get_embedding_capabilities(self.model_name)

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

    def _filter_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """An optional filter for embed and query kwargs that subclasses may implement."""
        return kwargs

    def get_embed_kwargs(self) -> dict[str, Any]:
        """Get keyword arguments for embedding requests based on the provider settings."""
        embedding_config = self.embedding_config.as_options()
        return self._filter_kwargs(embedding_config.get("embedding", {}))

    def get_query_embed_kwargs(self) -> dict[str, Any]:
        """Get keyword arguments for query embedding requests based on the provider settings."""
        embedding_config = self.embedding_config.as_options()
        return self._filter_kwargs(embedding_config.get("query", {}))

    def is_cloud(self) -> bool:
        """Return True if the provider settings are for a cloud deployment."""
        return self.client not in {SDKClient.SENTENCE_TRANSFORMERS, SDKClient.FASTEMBED}


type AzureClientOptionsType = Annotated[
    Annotated[CohereClientOptions, Tag(Provider.COHERE.variable)]
    | Annotated[OpenAIClientOptions, Tag(Provider.OPENAI.variable)],
    Field(
        description="Client options for the provider's client.",
        discriminator=Discriminator(discriminate_azure_embedding_client_options),
    ),
]


class AzureEmbeddingProviderSettings(AzureProviderMixin, EmbeddingProviderSettings):
    """Provider settings for Azure embedding models (Cohere or OpenAI)."""

    model_config = EmbeddingProviderSettings.model_config | ConfigDict(frozen=False)
    provider: Literal[Provider.AZURE]
    client_options: AzureClientOptionsType | None = Field(
        default=None, description="Client options for either Cohere or OpenAI client."
    )
    embedding_config: Annotated[
        CohereEmbeddingConfig | BedrockEmbeddingConfig,
        Field(
            description="Model configuration for embedding operations.", discriminator="provider"
        ),
    ]

    @property
    def uses_cohere_api(self) -> bool:
        """Determine if the provider is configured to use Cohere for embedding."""
        return self.client == SDKClient.COHERE

    @property
    def uses_openai_api(self) -> bool:
        """Determine if the provider is configured to use OpenAI for embedding."""
        return not self.uses_cohere_api

    def _filter_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Filter kwargs to ensure compatibility with Azure embedding requirements."""
        if (embedding_types := kwargs.get("embedding_types")) and embedding_types != "float":
            kwargs = kwargs.copy()
            kwargs["embedding_types"] = "float"
        return kwargs

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
                CohereClientOptions() if self.uses_cohere_api else OpenAIClientOptions()
            )
        else:
            client_options = self.client_options
        api_key = self.api_key or self.client_options.api_key or Provider.AZURE.get_env_api_key()
        options = self.as_azure_options() | client_options.model_dump() | {"api_key": api_key}
        if not options.get("base_url") and (
            endpoint := try_for_azure_endpoint(options, cohere=self.uses_cohere_api)
        ):
            options["base_url"] = AnyUrl(endpoint)
        final_client_options = {
            k: v
            for k, v in options.items()
            if v is not None and k not in {"model_deployment", "endpoint", "region_name"}
        }
        client = (
            CohereClientOptions(**final_client_options)
            if self.uses_cohere_api
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

    provider: Literal[Provider.BEDROCK]
    model_name: ModelNameT | None = Field(
        default=None,
        init=False,
        description="The name of the embedding model to use. For Bedrock, this is optional because the model ARN is required and contains the model name. If not provided, the model name will be inferred from the ARN.",
    )
    client_options: BedrockClientOptions = Field(
        default_factory=BedrockClientOptions, description="Client options for Bedrock."
    )
    embedding_config: BedrockEmbeddingConfig = Field(
        default_factory=lambda data: BedrockEmbeddingConfig(
            model_name=ModelName(data["model_name"] if isinstance(data, dict) else data.model_name)
        ),
        description="Model configuration for embedding operations.",
    )

    @property
    def is_cohere_model(self) -> bool:
        """Determine if the provider is configured to use a Cohere model for embedding."""
        return str(self.model_name).startswith("cohere")

    def _filter_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Ensure datatype is float. If not, we'll quantize when stored but not now."""
        if "embedding_types" in kwargs and kwargs["embedding_types"] != "float":
            kwargs = kwargs.copy()
            kwargs["embedding_types"] = "float"
        return kwargs

    @model_validator(mode="after")
    def _inject_model_arn_into_params(self) -> Self:
        """Inject model_arn into embedding/query params if not already present.

        Bedrock requires the model ARN at request time. This validator ensures it's
        available in the embedding_config's embedding and query parameters.
        """
        from codeweaver.providers.config.sdk import BedrockEmbeddingConfig

        if not isinstance(self.embedding_config, BedrockEmbeddingConfig):
            return self
        base_config = BedrockEmbeddingRequestParams(model_id=self.model_arn)
        base_model_options = (
            BedrockCohereConfigDict(embedding_types="float")
            if self.is_cohere_model
            else BedrockTitanV2ConfigDict(embedding_types="float")
        )
        model_name = str(self.model_name) or self.model_arn.split("/")[-1]
        self.model_name = self.model_name or ModelName(model_name)
        if self.embedding_config.embedding:
            self.embedding_config.embedding = base_config | self.embedding_config.embedding
        else:
            self.embedding_config = BedrockEmbeddingConfig(
                model_name=model_name,
                embedding=base_config,
                query=base_config,
                model=base_model_options,
            )
        return self


def _cohere_default_embedding_config_factory(data: dict[str, Any]) -> CohereEmbeddingConfig:
    """Default factory for Cohere embedding config."""
    data = data if isinstance(data, dict) else data.model_dump()
    model_name = ModelName(data["model_name"])
    if (capabilities := _get_embedding_capabilities(model_name)) is not None:
        options = CohereEmbeddingOptionsDict(
            output_dimension=capabilities.default_dimension, embedding_types="float"
        )
        config = CohereEmbeddingConfig(model_name=model_name, embedding=options, query=options)
        config.set_datatype("float")
        config.set_dimension(capabilities.default_dimension)
        return config
    return CohereEmbeddingConfig(
        model_name=model_name,
        embedding=CohereEmbeddingOptionsDict(),
        query=CohereEmbeddingOptionsDict(),
    )


class CohereEmbeddingProviderSettings(EmbeddingProviderSettings):
    """Provider settings for direct use of Cohere as a provider."""

    provider: Literal[Provider.COHERE]
    client_options: CohereClientOptions = Field(
        default_factory=CohereClientOptions,
        description="Client options for Cohere embedding client.",
    )
    embedding_config: CohereEmbeddingConfig = Field(
        default_factory=_cohere_default_embedding_config_factory
    )

    def _filter_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Filter kwargs to ensure compatibility with Cohere embedding requirements."""
        if (embedding_types := kwargs.get("embedding_types")) and embedding_types != "float":
            kwargs = kwargs.copy()
            kwargs["embedding_types"] = "float"
        return kwargs


class FastEmbedEmbeddingProviderSettings(FastEmbedProviderMixin, EmbeddingProviderSettings):
    """Provider settings for FastEmbed embedding models."""

    provider: Literal[Provider.FASTEMBED]
    client_options: FastEmbedClientOptions = Field(
        default_factory=lambda data: FastEmbedClientOptions(
            model_name=ModelName(data["model_name"] if isinstance(data, dict) else data.model_name)
        ),
        description="Client options for FastEmbed embedding client.",
    )
    embedding_config: FastEmbedEmbeddingConfig = Field(
        default_factory=lambda data: FastEmbedEmbeddingConfig(
            model_name=ModelName(data["model_name"] if isinstance(data, dict) else data.model_name)
        )
    )


def _google_default_embedding_config_factory(data: dict[str, Any]) -> GoogleEmbeddingConfig:
    """Default factory for Google embedding config."""
    data = data if isinstance(data, dict) else data.model_dump()
    model_name = ModelName(data["model_name"])
    if (capabilities := _get_embedding_capabilities(model_name)) is not None:
        options = GoogleEmbeddingRequestParams(output_dimensionality=capabilities.default_dimension)
        config = GoogleEmbeddingConfig(model_name=model_name, embedding=options, query=options)
        config.set_dimension(capabilities.default_dimension)
        config.set_datatype("float")
        return config
    return GoogleEmbeddingConfig(
        model_name=model_name,
        embedding=GoogleEmbeddingRequestParams(),
        query=GoogleEmbeddingRequestParams(),
    )


class GoogleEmbeddingProviderSettings(EmbeddingProviderSettings):
    """Provider settings for Google embedding models."""

    provider: Literal[Provider.GOOGLE]
    client_options: GoogleClientOptions = Field(
        default_factory=GoogleClientOptions,
        description="Client options for Google embedding client.",
    )
    embedding_config: GoogleEmbeddingConfig = Field(
        default_factory=_google_default_embedding_config_factory,
        description="Model configuration for Google embedding operations.",
    )


type CoreEmbeddingProviderSettingsType = Annotated[
    Annotated[EmbeddingProviderSettings, Tag("simple")]
    | Annotated[AzureEmbeddingProviderSettings, Tag(Provider.AZURE.variable)]
    | Annotated[BedrockEmbeddingProviderSettings, Tag(Provider.BEDROCK.variable)]
    | Annotated[FastEmbedEmbeddingProviderSettings, Tag(Provider.FASTEMBED.variable)],
    Field(
        description="Embedding provider settings type.",
        discriminator=CORE_EMBEDDING_PROVIDER_DISCRIMINATOR,
    ),
]
"A type alias representing all configuration classes for core embedding providers -- meaning an embedding provider that only represents one model. This is used as the type for the embed_provider and query_provider fields in the AsymmetricEmbeddingProviderSettings, which allows for asymmetric embedding configurations where the embed and query providers can be different but still must be from the same family."


class HuggingFaceEmbeddingProviderSettings(EmbeddingProviderSettings):
    """Provider settings for HuggingFace Inference embedding models."""

    provider: Literal[Provider.HUGGINGFACE_INFERENCE]
    client_options: HuggingFaceClientOptions = Field(
        default_factory=lambda data: HuggingFaceClientOptions(
            model=str(data["model_name"] if isinstance(data, dict) else data.model_name)
        ),
        description="Client options for HuggingFace Inference embedding client.",
    )
    embedding_config: HuggingFaceEmbeddingConfig = Field(
        default_factory=lambda data: HuggingFaceEmbeddingConfig(
            model_name=str(data["model_name"] if isinstance(data, dict) else data.model_name)
        )
    )


class MistralEmbeddingProviderSettings(EmbeddingProviderSettings):
    """Provider settings for Mistral embedding models."""

    provider: Literal[Provider.MISTRAL]
    client_options: MistralClientOptions = Field(
        description="Client options for Mistral embedding client.",
        default_factory=MistralClientOptions,
    )
    embedding_config: MistralEmbeddingConfig = Field(
        default_factory=lambda data: MistralEmbeddingConfig(
            model_name=ModelName(
                data["model_name"] if isinstance(data, dict) else data.model_name,
                **MistralEmbeddingConfig._defaults(),
            )
        ),
        description="Model configuration for Mistral embedding operations.",
    )

    def _filter_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Filter kwargs to ensure compatibility with Mistral embedding requirements."""
        if (dtype := kwargs.get("output_dtype")) and dtype != "float":
            kwargs = kwargs.copy()
            kwargs["output_dtype"] = "float"
        return kwargs


class SentenceTransformersEmbeddingProviderSettings(EmbeddingProviderSettings):
    """Provider settings for Sentence Transformers embedding models."""

    provider: Literal[Provider.SENTENCE_TRANSFORMERS]
    client_options: SentenceTransformersClientOptions = Field(
        default_factory=lambda data: SentenceTransformersClientOptions(
            model_name_or_path=str(
                data["model_name"] if isinstance(data, dict) else data.model_name
            )
        ),
        description="Client options for Sentence Transformers embedding client.",
    )
    embedding_config: SentenceTransformersEmbeddingConfig = Field(
        default_factory=lambda data: SentenceTransformersEmbeddingConfig(
            model_name=str(data["model_name"] if isinstance(data, dict) else data.model_name),
            embedding=SentenceTransformersEncodeDict(),
            query=SentenceTransformersEncodeDict(),
        )
    )

    def _filter_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Filter kwargs to ensure compatibility with Sentence Transformers embedding requirements."""
        if (precision := kwargs.get("precision")) is not None and precision != "float32":
            kwargs = kwargs.copy()
            kwargs["precision"] = "float32"
        return kwargs


class VoyageEmbeddingProviderSettings(EmbeddingProviderSettings):
    """Provider settings for Voyage embedding models."""

    provider: Literal[Provider.VOYAGE]
    client_options: VoyageClientOptions = Field(
        default_factory=VoyageClientOptions,
        description="Client options for Voyage embedding client.",
    )
    embedding_config: VoyageEmbeddingConfig = Field(
        default_factory=lambda data: VoyageEmbeddingConfig(
            model_name=ModelName(data["model_name"] if isinstance(data, dict) else data.model_name)
        ),
        description="Model configuration for Voyage embedding operations.",
    )

    def _filter_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Filter kwargs to ensure compatibility with Voyage embedding requirements."""
        if (dtype := kwargs.get("output_dtype")) and dtype != "float":
            kwargs = kwargs.copy()
            kwargs["output_dtype"] = "float"
        return kwargs


class AsymmetricEmbeddingProviderSettingsDict(TypedDict, total=False):
    """Dictionary representation of asymmetric embedding configuration."""

    embed_provider: Required[CoreEmbeddingProviderSettingsType]
    query_provider: Required[CoreEmbeddingProviderSettingsType]
    validate_family_compatibility: NotRequired[bool]


def _handle_ambiguous_property(v: Any, key: str) -> Any:
    """Handle ambiguous property for private attribute."""
    return v.get(key) if isinstance(v, dict) else getattr(v, key, None)


def _get_model_name_for_family(v: Any) -> ModelNameT:
    """Get model name for private attribute."""
    configs = (
        _handle_ambiguous_property(v, "embed_provider"),
        _handle_ambiguous_property(v, "query_provider"),
    )
    configs = [
        _handle_ambiguous_property(cfg, "embedding_config")
        or _handle_ambiguous_property(cfg, "embedding_config")
        for cfg in configs
        if cfg
    ]
    if (
        (caps := next((cfg.capabilities for cfg in configs if cfg and cfg.capabilities), None))
        and caps.model_family
        and (fam_id := caps.model_family.family_id)
    ):
        return fam_id
    if (
        name := next(
            (
                n
                for cfg in configs
                if cfg and (n := _handle_ambiguous_property(cfg, "model_name")) is not None
            ),
            None,
        )
    ) is not None:
        return ModelName(f"{name}-family")
    raise ValueError("Cannot determine model name for asymmetric embedding configuration.")


class AsymmetricEmbeddingProviderSettings(BasedModel):
    """Configuration for asymmetric embedding setup with separate embed and query models.

    Asymmetric embedding allows using different models for document embedding and query
    embedding while maintaining compatibility through shared vector spaces. This enables
    cost optimization (e.g., API for embed, local for queries) while preserving accuracy.

    Attributes:
        config_type: Discriminator field for union type matching.
        embed_provider: Provider settings for document embedding model.
        query_provider: Provider settings for query embedding model.
        validate_family_compatibility: Whether to validate models belong to same family.
    """

    config_type: Literal["asymmetric"] = "asymmetric"
    embed_provider: Annotated[
        CoreEmbeddingProviderSettingsType,
        Field(description="Provider settings for the document embedding model."),
    ]
    query_provider: Annotated[
        CoreEmbeddingProviderSettingsType,
        Field(description="Provider settings for the query embedding model."),
    ]
    validate_family_compatibility: Annotated[
        bool,
        Field(description="Whether to validate that both models belong to the same model family."),
    ] = True
    category: ClassVar[Literal[ProviderCategory.EMBEDDING]] = ProviderCategory.EMBEDDING
    _model_name: ModelNameT | None = PrivateAttr(default=None)

    def get_embed_kwargs(self) -> dict[str, Any]:
        """Get keyword arguments for the embed provider."""
        return self.embed_provider.get_embed_kwargs()

    def get_query_kwargs(self) -> dict[str, Any]:
        """Get keyword arguments for the query provider."""
        return self.query_provider.get_query_embed_kwargs()

    def __getattribute__(self, name: str) -> Any:
        """Delegate attribute access to embed provider for shared properties."""
        instance_dict = object.__getattribute__(self, "__dict__")
        if name in instance_dict:
            return instance_dict[name]
        if name == "get_embed_kwargs":
            return object.__getattribute__(self, "embed_provider").get_embed_kwargs
        if name == "get_query_kwargs":
            return object.__getattribute__(self, "query_provider").get_query_embed_kwargs
        return super().__getattribute__(name)

    @cached_property
    def dimension_tuple(self) -> tuple[int | None, int | None]:
        """Get the embedding dimensions for embed and query models."""
        try:
            embed_dim = self.embed_provider.embedding_config.dimension
            query_dim = self.query_provider.embedding_config.dimension
            if embed_dim is not None and query_dim is not None:
                return (embed_dim, query_dim)
            embed_caps = (
                self.embed_provider.embedding_config.capabilities
                or _get_embedding_capabilities(self.embed_provider.model_name)
            )
            query_caps = (
                self.query_provider.embedding_config.capabilities
                or _get_embedding_capabilities(self.query_provider.model_name)
            )
            if embed_dim is None and embed_caps:
                embed_dim = embed_caps.default_dimension
            if query_dim is None and query_caps:
                query_dim = query_caps.default_dimension
            if embed_dim is None and query_dim is not None:
                embed_dim = query_dim
            if query_dim is None and embed_dim is not None:
                query_dim = embed_dim
        except Exception:
            logger.exception("Error calculating dimension_tuple")
            return (None, None)
        else:
            return (embed_dim, query_dim)

    @cached_property
    def datatype_tuple(self) -> tuple[str | None, str | None]:
        """Get the embedding datatypes for embed and query models.

        Returns:
            A tuple of (embed_datatype, query_datatype).
        """
        embed_dt = self.embed_provider.embedding_config.datatype
        query_dt = self.query_provider.embedding_config.datatype
        if embed_dt is not None and query_dt is not None:
            return (embed_dt, query_dt)
        embed_caps = (
            self.embed_provider.embedding_config.capabilities
            or _get_embedding_capabilities(self.embed_provider.model_name)
        )
        query_caps = (
            self.query_provider.embedding_config.capabilities
            or _get_embedding_capabilities(self.query_provider.model_name)
        )
        if embed_dt is None and embed_caps:
            embed_dt = embed_caps.default_dtype
        if query_dt is None and query_caps:
            query_dt = query_caps.default_dtype
        if embed_dt is None and query_dt is not None:
            embed_dt = query_dt
        if query_dt is None and embed_dt is not None:
            query_dt = embed_dt
        return (embed_dt, query_dt)
        embed_dt = self.embed_provider.embedding_config.datatype
        query_dt = self.query_provider.embedding_config.datatype
        if embed_dt is not None and query_dt is not None:
            return (embed_dt, query_dt)
        embed_caps = (
            self.embed_provider.embedding_config.capabilities
            or _get_embedding_capabilities(self.embed_provider.model_name)
        )
        query_caps = (
            self.query_provider.embedding_config.capabilities
            or _get_embedding_capabilities(self.query_provider.model_name)
        )
        if embed_dt is None and embed_caps:
            embed_dt = embed_caps.default_dtype
        if query_dt is None and query_caps:
            query_dt = query_caps.default_dtype
        if embed_dt is None and query_dt is not None:
            embed_dt = query_dt
        if query_dt is None and embed_dt is not None:
            query_dt = embed_dt
        return (embed_dt, query_dt)

    @model_validator(mode="after")
    def validate_model_compatibility(self) -> AsymmetricEmbeddingProviderSettings:
        """Validate that embed and query models are compatible."""
        from codeweaver.core.exceptions import ConfigurationError

        try:
            if not self.validate_family_compatibility:
                return self
            if self.dimension_tuple[0] is not None and self.dimension_tuple[1] is not None:
                if self.dimension_tuple[0] != self.dimension_tuple[1]:
                    raise DimensionMismatchError(
                        f"Embedding dimension mismatch: embed model dimension {self.dimension_tuple[0]} != query model dimension {self.dimension_tuple[1]}",
                        details={
                            "embed_model": str(self.embed_provider.model_name),
                            "embed_dimension": self.dimension_tuple[0],
                            "query_model": str(self.query_provider.model_name),
                            "query_dimension": self.dimension_tuple[1],
                        },
                    )
            if self.datatype_tuple[0] is not None and self.datatype_tuple[1] is not None:
                if self.datatype_tuple[0] != self.datatype_tuple[1]:
                    embed_caps = (
                        self.embed_provider.embedding_config.capabilities
                        or _get_embedding_capabilities(self.embed_provider.model_name)
                    )
                    query_caps = (
                        self.query_provider.embedding_config.capabilities
                        or _get_embedding_capabilities(self.query_provider.model_name)
                    )
                    if (
                        embed_caps
                        and query_caps
                        and embed_caps.model_family
                        and (embed_caps.model_family == query_caps.model_family)
                        and (embed_caps.model_family.family_id == "voyage-4")
                    ):
                        pass
                    else:
                        raise DatatypeMismatchError(
                            f"Embedding datatype mismatch: embed model datatype '{self.datatype_tuple[0]}' != query model datatype '{self.datatype_tuple[1]}'"
                        )
            caps = self.embed_provider.embedding_config.capabilities or _get_embedding_capabilities(
                self.embed_provider.model_name
            )
            if caps is not None and caps.model_family is not None:
                if not caps.model_family.is_compatible(
                    str(self.embed_provider.model_name), str(self.query_provider.model_name)
                ):
                    raise ConfigurationError(
                        f"Models '{self.embed_provider.model_name}' and '{self.query_provider.model_name}' are not compatible within family '{caps.model_family.family_id}'",
                        suggestions=[
                            f"Use models from the same family (e.g., two '{caps.model_family.family_id}' models)",
                            "Set validate_family_compatibility=False to skip this check",
                        ],
                    )
        except (DimensionMismatchError, DatatypeMismatchError, ConfigurationError):
            raise
        except Exception as e:
            logger.error("Unexpected error in validate_model_compatibility: %s", e, exc_info=True)
            raise AssertionError(f"Internal validation error: {e!s}") from e
        else:
            return self

    @property
    def dimension(self) -> NonNegativeInt:
        """Get the embedding dimension for both models (they must match)."""
        return cast(NonNegativeInt, self.dimension_tuple[0] or 0)

    @property
    def datatype(self) -> str:
        """Get the embedding datatype for both models (they must match)."""
        return self.datatype_tuple[0] or "float32"

    @property
    def embedding_config(self) -> Any:
        """Get the embedding configuration for the embed provider."""
        return self.embed_provider.embedding_config

    @property
    def query_config(self) -> Any:
        """Get the embedding configuration for the query provider."""
        return self.query_provider.embedding_config

    @property
    def model_name(self) -> ModelNameT:
        """Get the model family name for the asymmetric embedding configuration."""
        if self._model_name is None:
            self._model_name = _get_model_name_for_family(self)
        return self._model_name

    def _telemetry_keys(self) -> None:
        """Telemetry keys implementation."""
        return


type EmbeddingProviderSettingsType = Annotated[
    Annotated[CoreEmbeddingProviderSettingsType, Tag("symmetric")]
    | Annotated[AsymmetricEmbeddingProviderSettings, Tag("asymmetric")],
    Field(
        description="A type alias representing all possible configuration classes for embedding providers.",
        discriminator="config_type",
    ),
]
"A type alias representing all possible configuration classes for embedding providers."
__all__ = (
    "AsymmetricEmbeddingProviderSettings",
    "AsymmetricEmbeddingProviderSettingsDict",
    "AzureClientOptionsType",
    "AzureEmbeddingProviderSettings",
    "BaseEmbeddingProviderSettings",
    "BedrockEmbeddingProviderSettings",
    "CohereEmbeddingProviderSettings",
    "CoreEmbeddingProviderSettingsType",
    "EmbeddingProviderSettings",
    "EmbeddingProviderSettingsType",
    "FastEmbedEmbeddingProviderSettings",
    "GoogleEmbeddingProviderSettings",
    "HuggingFaceEmbeddingProviderSettings",
    "MistralEmbeddingProviderSettings",
    "SentenceTransformersEmbeddingProviderSettings",
    "VoyageEmbeddingProviderSettings",
)

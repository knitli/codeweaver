"""Top-level settings classes for embedding providers."""

from __future__ import annotations

import contextlib
import logging

from abc import ABC, abstractmethod
from functools import cached_property
from typing import Annotated, Any, Literal, NotRequired, Required, Self, TypedDict, cast

from beartype.typing import ClassVar
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

possible_tags = get_provider_names_for_category("embedding")


class BaseEmbeddingProviderSettings(BaseProviderCategorySettings, ABC):
    """Settings for (dense) embedding models. It validates that the model and provider settings are compatible and complete, reconciling environment variables and config file settings as needed."""

    category: ClassVar[Literal[ProviderCategory.EMBEDDING]] = ProviderCategory.EMBEDDING
    config_type: ClassVar[Literal["symmetric"]] = "symmetric"

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
        if self.provider in (
            Provider.HUGGINGFACE_INFERENCE,
            Provider.SENTENCE_TRANSFORMERS,
            Provider.FASTEMBED,
        ):
            if self.provider == Provider.FASTEMBED:
                data = self._set_client_option(
                    data, "model_name", self.model_name or data.get("model_name")
                )
            if self.provider == Provider.SENTENCE_TRANSFORMERS:
                data = self._set_client_option(
                    data, "model_name_or_path", self.model_name or data.get("model_name")
                )
            else:
                data = self._set_client_option(
                    data, "model", self.model_name or data.get("model_name")
                )
        data |= super()._initialize(data)
        return data

    def __init__(self, **data: Any) -> None:
        """Initialize embedding provider settings."""
        if model_name := data.get("model_name"):
            data["model_name"] = ModelName(model_name)
        config = data["embedding_config"]
        if (
            not (
                config_model_name := config.get("model_name")
                if isinstance(config, dict)
                else config.model_name
            )
            and model_name
        ):
            config["model_name"] = ModelName(model_name)
        elif config_model_name and not model_name:
            data["model_name"] = ModelName(config_model_name)
        super().__init__(**data)

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

    provider: Literal[Provider.AZURE]
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
    provider: Literal[Provider.BEDROCK]

    @model_validator(mode="after")
    def _inject_model_arn_into_params(self) -> Self:
        """Inject model_arn into embedding/query params if not already present.

        Bedrock requires the model ARN at request time. This validator ensures it's
        available in the embedding_config's embedding and query parameters.
        """
        from codeweaver.providers.config.sdk import BedrockEmbeddingConfig

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

    provider: Literal[Provider.FASTEMBED]

    client_options: Annotated[
        FastEmbedClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None


type CoreEmbeddingProviderSettingsType = Annotated[
    Annotated[EmbeddingProviderSettings, Field(discriminator="tag"), Tag("simple")]
    | Annotated[AzureEmbeddingProviderSettings, Tag(Provider.AZURE.variable)]
    | Annotated[BedrockEmbeddingProviderSettings, Tag(Provider.BEDROCK.variable)]
    | Annotated[FastEmbedEmbeddingProviderSettings, Tag(Provider.FASTEMBED.variable)],
    Field(
        description="Embedding provider settings type.",
        discriminator=CORE_EMBEDDING_PROVIDER_DISCRIMINATOR,
    ),
]
"""A type alias representing all configuration classes for core embedding providers -- meaning an embedding provider that only represents one model. This is used as the type for the embed_provider and query_provider fields in the AsymmetricEmbeddingProviderSettings, which allows for asymmetric embedding configurations where the embed and query providers can be different but still must be from the same family."""


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
        (
            _handle_ambiguous_property(cfg, "embedding_config")
            or _handle_ambiguous_property(cfg, "embedding_config")
        )
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

    config_type: ClassVar[Literal["asymmetric"]] = "asymmetric"

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

    _model_name: ModelNameT = PrivateAttr(default_factory=_get_model_name_for_family)

    def get_embed_kwargs(self) -> dict[str, Any]:
        """Get keyword arguments for the embed provider."""
        return self.embed_provider.get_embed_kwargs()

    def get_query_kwargs(self) -> dict[str, Any]:
        """Get keyword arguments for the query provider."""
        return self.query_provider.get_query_embed_kwargs()

    def __getattribute__(self, name: str) -> Any:
        """Delegate attribute access to embed provider for shared properties."""
        if name in self.__dict__:
            return self.__dict__[name]
        if name == "get_embed_kwargs":
            return self.embed_provider.get_embed_kwargs
        if name == "get_query_kwargs":
            return self.query_provider.get_query_embed_kwargs
        if name in list(self.__dir__()):
            return super().__getattribute__(name)
        raise AttributeError(f"{self.__class__.__name__} object has no attribute '{name}'")

    @cached_property
    def dimension_tuple(self) -> tuple[NonNegativeInt, NonNegativeInt]:
        """Get the embedding dimensions for embed and query models.

        Returns:
            A tuple of (embed_dimension, query_dimension).
        """
        if (
            found_values := (
                self.embed_provider.embedding_config.dimension,
                self.query_provider.embedding_config.dimension,
            )
        ) and all(dim is not None for dim in found_values):
            return cast(
                tuple[NonNegativeInt, NonNegativeInt],
                (
                    self.embed_provider.embedding_config.dimension,
                    self.query_provider.embedding_config.dimension,
                ),
            )
        match found_values:
            case (int(), None):
                self.query_provider.embedding_config.set_dimension(cast(int, found_values[0]))
                return cast(tuple[int, int], (found_values[0], found_values[0]))
            case (None, int()):
                self.embed_provider.embedding_config.set_dimension(cast(int, found_values[1]))
                return cast(tuple[int, int], (found_values[1], found_values[1]))
            case _:
                embed_caps = (
                    self.embed_provider.embedding_config.capabilities
                    or self.query_provider.embedding_config.capabilities
                )
                if not embed_caps:
                    raise ValueError(
                        "Cannot determine embedding dimensions for asymmetric embedding config: "
                        "neither model has dimension set or capabilities registered."
                    )
                self.embed_provider.embedding_config.set_dimension(embed_caps.default_dimension)
                self.query_provider.embedding_config.set_dimension(embed_caps.default_dimension)
                return cast(
                    tuple[int, int], (embed_caps.default_dimension, embed_caps.default_dimension)
                )
        return cast(
            tuple[NonNegativeInt, NonNegativeInt],
            (
                self.embed_provider.embedding_config.dimension,
                self.query_provider.embedding_config.dimension,
            ),
        )

    @cached_property
    def datatype_tuple(self) -> tuple[str, str]:
        """Get the embedding datatypes for embed and query models.

        Returns:
            A tuple of (embed_datatype, query_datatype).
        """
        if (
            found_values := (
                self.embed_provider.embedding_config.datatype,
                self.query_provider.embedding_config.datatype,
            )
        ) and all(dt is not None for dt in found_values):
            return cast(
                tuple[str, str],
                (
                    self.embed_provider.embedding_config.datatype,
                    self.query_provider.embedding_config.datatype,
                ),
            )
        match found_values:
            case (str(), None):
                self.query_provider.embedding_config.set_datatype(cast(str, found_values[0]))
                return cast(tuple[str, str], (found_values[0], found_values[0]))
            case (None, str()):
                self.embed_provider.embedding_config.set_datatype(cast(str, found_values[1]))
                return cast(tuple[str, str], (found_values[1], found_values[1]))
            case _:
                embed_caps = (
                    self.embed_provider.embedding_config.capabilities
                    or self.query_provider.embedding_config.capabilities
                )
                if not embed_caps:
                    raise ValueError(
                        "Cannot determine embedding datatypes for asymmetric embedding config: "
                        "neither model has datatype set or capabilities registered."
                    )
                self.embed_provider.embedding_config.set_datatype(embed_caps.default_dtype)
                self.query_provider.embedding_config.set_datatype(embed_caps.default_dtype)
                return cast(tuple[str, str], (embed_caps.default_dtype, embed_caps.default_dtype))
        return cast(
            tuple[str, str],
            (
                self.embed_provider.embedding_config.datatype,
                self.query_provider.embedding_config.datatype,
            ),
        )

    @model_validator(mode="after")
    def validate_model_compatibility(self) -> AsymmetricEmbeddingProviderSettings:
        """Validate that embed and query models are compatible.

        Validates:
        - Both models have registered capabilities
        - Both models belong to model families
        - Both models belong to the same family
        - Models are compatible within the family
        - Embedding dimensions match

        Returns:
            Self for method chaining.

        Raises:
            ConfigurationError: If models are incompatible.
        """
        from codeweaver.core.exceptions import ConfigurationError

        if not self.validate_family_compatibility:
            logger.warning(
                "Family compatibility validation disabled for asymmetric embedding config. "
                "This may result in incompatible embeddings if models are from different families."
            )
            return self

        if self.dimension_tuple[0] != self.dimension_tuple[1]:
            raise DimensionMismatchError(
                f"Embedding dimension mismatch: embed model dimension {self.dimension_tuple[0]} != query model dimension {self.dimension_tuple[1]}",
                details={
                    "embed_model": str(self.embed_provider.model_name),
                    "embed_dimension": self.dimension_tuple[0],
                    "query_model": str(self.query_provider.model_name),
                    "query_dimension": self.dimension_tuple[1],
                },
                suggestions=[
                    "Ensure both models are configured with the same embedding dimension",
                    "Set dimensions explicitly in the embedding configurations if needed",
                ],
            )
        if self.datatype_tuple[0] != self.datatype_tuple[1]:
            raise DatatypeMismatchError(
                f"Embedding datatype mismatch: embed model datatype '{self.datatype_tuple[0]}' != query model datatype '{self.datatype_tuple[1]}'",
                details={
                    "embed_model": str(self.embed_provider.model_name),
                    "embed_datatype": self.datatype_tuple[0],
                    "query_model": str(self.query_provider.model_name),
                    "query_datatype": self.datatype_tuple[1],
                },
                suggestions=[
                    "Ensure both models are configured with the same embedding datatype",
                    "Set datatypes explicitly in the embedding configurations if needed",
                ],
            )
        if (
            caps := self.embed_provider.embedding_config.capabilities
            if self.embed_provider.embedding_config
            else self.query_provider.embedding_config.capabilities
            if self.query_provider.embedding_config
            else None
        ) is not None and caps.model_family is not None:
            if caps.model_family.is_compatible(
                str(self.embed_provider.model_name), str(self.query_provider.model_name)
            ):
                logger.info(
                    "Asymmetric embedding configuration validated successfully using pre-set capabilities: "
                    "embed_model='%s', query_model='%s', family='%s'",
                    str(self.embed_provider.model_name),
                    str(self.query_provider.model_name),
                    caps.model_family.family_id,
                )
                return self
            raise ConfigurationError(
                f"Models are not compatible within family '{caps.model_family.family_id}' based on pre-set capabilities",
                details={
                    "embed_model": str(self.embed_provider.model_name),
                    "query_model": str(self.query_provider.model_name),
                    "family_id": caps.model_family.family_id,
                    "family_members": sorted(caps.model_family.member_models),
                },
                suggestions=[
                    "Ensure both models are listed as family members",
                    f"Valid family members: {', '.join(sorted(caps.model_family.member_models))}",
                    "Contact support if you believe this is an error",
                ],
            )
        if not caps:
            raise ConfigurationError(
                "Cannot validate model compatibility: neither model has embedding capabilities registered",
                details={
                    "embed_model": str(self.embed_provider.model_name),
                    "query_model": str(self.query_provider.model_name),
                },
                suggestions=[
                    "Ensure both models have embedding capabilities registered",
                    "Check provider documentation for supported models and capabilities",
                ],
            )

        return self

    @property
    def dimension(self) -> NonNegativeInt:
        """Get the embedding dimension for both models (they must match)."""
        return self.dimension_tuple[0]

    @property
    def datatype(self) -> str:
        """Get the embedding datatype for both models (they must match)."""
        return self.datatype_tuple[0]

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
        return self._model_name

    def _telemetry_keys(self) -> None:
        """Telemetry keys implementation."""
        return


# we can simply use the "config_type" discriminator to determine the correct settings type for asymmetric embedding configs, so we don't need a custom discriminator function like we do for the core embedding provider settings
type EmbeddingProviderSettingsType = Annotated[
    Annotated[CoreEmbeddingProviderSettingsType, Tag("symmetric")]
    | Annotated[AsymmetricEmbeddingProviderSettings, Tag("asymmetric")],
    Field(
        description="A type alias representing all possible configuration classes for embedding providers.",
        discriminator="config_type",
    ),
]
"""A type alias representing all possible configuration classes for embedding providers."""

__all__ = (
    "AsymmetricEmbeddingProviderSettings",
    "AsymmetricEmbeddingProviderSettingsDict",
    "AzureEmbeddingProviderSettings",
    "BaseEmbeddingProviderSettings",
    "BedrockEmbeddingProviderSettings",
    "EmbeddingProviderSettings",
    "EmbeddingProviderSettingsType",
    "FastEmbedEmbeddingProviderSettings",
)

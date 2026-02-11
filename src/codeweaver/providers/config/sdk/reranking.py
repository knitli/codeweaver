# sourcery skip: lambdas-should-be-short
# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Provider-specific reranking configuration models and utilities."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Sequence
from typing import Annotated, Any, Literal, NotRequired, Required, TypedDict, cast, override

from pydantic import Field

from codeweaver.core.constants import DEFAULT_EMBEDDING_BATCH_SIZE, DEFAULT_RERANKING_MAX_RESULTS
from codeweaver.core.types import BasedModel, ModelName, ModelNameT, Provider
from codeweaver.providers import RerankingModelCapabilities


class SerializedRerankingOptionsDict(TypedDict, total=False):
    """A dictionary representing serialized reranking options for different providers."""

    model_name: Required[ModelNameT]
    """The name of the reranking model in the format used by the provider."""

    rerank: NotRequired[dict[str, Any]]
    """Parameters for reranking requests."""

    model: NotRequired[dict[str, Any]]
    """Model initialization/configuration parameters (Bedrock only)."""


# ============================================================================
# Provider-Specific Parameter TypedDicts
# ============================================================================


class VoyageRerankingOptionsDict(TypedDict, total=False):
    """Parameters for Voyage AI reranking requests."""

    truncation: NotRequired[bool]
    """Whether to truncate input to satisfy context length limits. Defaults to True."""


class CohereRerankingOptionsDict(TypedDict, total=False):
    """Parameters for Cohere reranking requests."""

    top_n: NotRequired[int]
    """Number of most relevant results to return. Defaults to length of documents."""

    max_tokens_per_doc: NotRequired[int]
    """Maximum tokens per document. Defaults to 4,096. Documents exceeding this are truncated.
    You don't need to set this because CodeWeaver sends everything pre-chunked to fit a confidence-based logarithmic window that caps out around 1,000 tokens, aiming for coherent code blocks, and automatically reduces that window for models with smaller context lengths.

    You would probably assume that 'context window' == 'max coherence', but nearly every model is trained on data that's in the 200 - 500 token range, so performance degrades significantly as you scale past that. Larger windows also put the model in the situation of assigning a single value to represent a large body of text, which is inherently lossy.

    But, there may be a case we can't foresee, so it's here.
    """

    rank_fields: NotRequired[Sequence[str]]
    """For JSON objects: specify which keys to consider for reranking (e.g., ['title', 'author', 'text'])."""


class BedrockRerankingModelConfig(TypedDict, total=False):
    """Model configuration for Bedrock reranking models."""

    model_arn: Required[str]
    """The ARN of the model. Required for Bedrock reranking."""

    additional_model_request_fields: NotRequired[None]
    """Reserved for future model-specific parameters. Currently unused."""


class BedrockRerankingOptionsDict(TypedDict, total=False):
    """Parameters for Bedrock reranking requests."""

    number_of_results: NotRequired[int]
    """Number of results to return (this is top_n). Defaults to 10."""


class FastEmbedRerankingOptionsDict(TypedDict, total=False):
    """Parameters for FastEmbed reranking requests."""

    batch_size: NotRequired[int]
    """Batch size for processing. Defaults to 64."""


class SentenceTransformersRerankingOptionsDict(TypedDict, total=False):
    """Parameters for Sentence Transformers cross-encoder reranking requests."""

    top_k: NotRequired[int]
    """Return only top-k documents. If None, returns all."""

    return_documents: NotRequired[bool]
    """If True, includes document text in results. Defaults to False."""

    batch_size: NotRequired[int]
    """Batch size for encoding. Defaults to 32."""

    show_progress_bar: NotRequired[bool]
    """Whether to display progress bar during reranking."""


# ============================================================================
# Base Config
# ============================================================================


class BaseRerankingConfig(BasedModel):
    """Base configuration for reranking models."""

    provider: Provider = Field(
        ...,
        description="The provider for this reranking configuration. Used for discriminated unions.",
    )

    model_name: ModelNameT = Field(
        default_factory=ModelName,
        description="The name of the reranking model to use. Note: The model name is required, but it's required at the provider level, so you don't have to provide it here if it's already set at the provider level. If you set it here, it will be used; if you don't set it here but it's set at the provider level, it will be injected here automatically. This field is primarily here for tracking and convenience when we break the configs apart.",
    )
    """The name of the reranking model."""

    rerank: Annotated[
        dict[str, Any] | None,
        Field(
            description="Parameters for reranking requests. Subclasses should implement a TypedDict with specific parameters for the provider."
        ),
    ] = None

    def _telemetry_keys(self) -> None:
        """Get the telemetry keys for the model."""

    @classmethod
    def _defaults(cls) -> dict[str, Any]:
        """Default config values as a dictionary. Subclasses can override this to provide default values for their specific parameters."""
        return {}

    @abstractmethod
    def _as_options(self) -> SerializedRerankingOptionsDict:
        """Return the configuration as a dictionary of options. Subclasses must implement this method."""
        raise NotImplementedError("Subclasses must implement _as_options method.")

    def as_options(self) -> SerializedRerankingOptionsDict:
        """Return the configuration as a dictionary of options."""
        return self._as_options()

    @property
    def capabilities(self) -> RerankingModelCapabilities | None:
        """Get the capabilities of the reranking model based on the provider and model name."""
        from codeweaver.providers.reranking.capabilities.resolver import RerankingCapabilityResolver

        resolver = RerankingCapabilityResolver()
        return resolver.resolve(str(self.model_name))


# ============================================================================
# Provider-Specific Configs
# ============================================================================


class VoyageRerankingConfig(BaseRerankingConfig):
    """Configuration options for Voyage AI reranking models."""

    provider: Literal[Provider.VOYAGE] = Provider.VOYAGE

    model_name: Literal["rerank-2.5", "rerank-2.5-lite"] | ModelNameT = Field(
        default_factory=ModelName,
        description="The Voyage AI reranking model to use (e.g., 'rerank-2.5', 'rerank-2.5-lite').",
    )
    """The Voyage AI reranking model to use (e.g., 'rerank-2.5', 'rerank-2.5-lite')."""

    rerank: VoyageRerankingOptionsDict = Field(default_factory=VoyageRerankingOptionsDict)
    """Parameters for Voyage reranking requests."""

    def _as_options(self) -> SerializedRerankingOptionsDict:
        """Convert the Voyage reranking configuration to a dictionary of options."""
        return SerializedRerankingOptionsDict(
            model_name=ModelName(self.model_name),
            rerank=cast(dict[str, Any], self.rerank or {}),
            model={},
        )

    @classmethod
    def _defaults(cls) -> dict[str, Any]:
        """Default config values as a dictionary."""
        # we don't ever need to truncate anything but if we did, this prevents things from breaking
        return {"rerank": {"truncation": True}}


class CohereRerankingConfig(BaseRerankingConfig):
    """Configuration options for Cohere reranking models."""

    tag: Literal["cohere"] = "cohere"
    provider: Literal[Provider.COHERE] = Provider.COHERE

    model_name: (
        Literal[
            "rerank-v4.0-pro",
            "rerank-v4.0-fast",
            "rerank-v3.5",
            "rerank-english-v3.0",
            "rerank-multilingual-v3.0",
        ]
        | ModelNameT
    ) = Field(
        default_factory=ModelName,
        description="The Cohere reranking model to use (e.g., 'rerank-v4.0-pro', 'rerank-v4.0-fast', 'rerank-v3.5', 'rerank-english-v3.0', 'rerank-multilingual-v3.0').",
    )
    """The Cohere reranking model to use."""

    rerank: CohereRerankingOptionsDict = Field(
        default_factory=lambda data: CohereRerankingOptionsDict(
            top_n=DEFAULT_RERANKING_MAX_RESULTS, max_tokens_per_doc=4096, **data.get("rerank", {})
        )
    )
    """Parameters for Cohere reranking requests."""

    def _as_options(self) -> SerializedRerankingOptionsDict:
        """Convert the Cohere reranking configuration to a dictionary of options."""
        return SerializedRerankingOptionsDict(
            model_name=ModelName(self.model_name),
            rerank=cast(dict[str, Any], self.rerank or {}) | {"model": self.model_name},
            model={},
        )

    @classmethod
    def _defaults(cls) -> dict[str, Any]:
        """Default config values as a dictionary."""
        return {"rerank": {"top_n": DEFAULT_RERANKING_MAX_RESULTS, "max_tokens_per_doc": 4096}}


class BedrockRerankingConfig(BaseRerankingConfig):
    """Configuration options for Bedrock reranking models.

    Bedrock is the only provider that requires model-level configuration.
    """

    provider: Literal[Provider.BEDROCK] = Provider.BEDROCK

    model_name: Literal["amazon.rerank-v1:0", "cohere.rerank-v3-5:0"] | ModelNameT = Field(
        default_factory=ModelName,
        description="The Bedrock reranking model to use (e.g., 'amazon.rerank-v1:0', 'cohere.rerank-v3-5:0').",
    )
    """The Bedrock reranking model to use (e.g., 'amazon.rerank-v1:0', 'cohere.rerank-v3-5:0')."""

    model: BedrockRerankingModelConfig | None = None
    """Model configuration including ARN and additional fields.

    NOTE: The model ARN is **required**, but you can set it on the provider settings directly, which injects it here in the model config. This is because Bedrock requires the ARN to be in the model configuration, but we want to allow users to set it at the provider level for convenience. If you set the ARN at the provider level, it will be injected into the model config automatically.
    """

    rerank: BedrockRerankingOptionsDict = Field(
        default_factory=lambda data: BedrockRerankingOptionsDict(
            number_of_results=DEFAULT_RERANKING_MAX_RESULTS, **data.get("rerank", {})
        )
    )
    """Parameters for Bedrock reranking requests."""

    def _as_options(self) -> SerializedRerankingOptionsDict:
        """Convert the Bedrock reranking configuration to a dictionary of options."""
        return SerializedRerankingOptionsDict(
            model_name=ModelName(self.model_name),
            rerank=cast(dict[str, Any], (type(self)._defaults() | (self.rerank or {}))),
            model=cast(dict[str, Any], self.model),
        )

    @classmethod
    def _defaults(cls) -> dict[str, Any]:
        """Default config values for the rerank config."""
        return {"rerank": {"number_of_results": DEFAULT_RERANKING_MAX_RESULTS}}


class FastEmbedRerankingConfig(BaseRerankingConfig):
    """Configuration options for FastEmbed reranking models."""

    provider: Literal[Provider.FASTEMBED] = Provider.FASTEMBED

    model_name: ModelNameT = Field(
        default_factory=ModelName,
        description="The FastEmbed reranking model to use (e.g., 'Xenova/ms-marco-MiniLM-L-6-v2').",
    )
    """The FastEmbed reranking model to use (e.g., 'Xenova/ms-marco-MiniLM-L-6-v2')."""

    rerank: FastEmbedRerankingOptionsDict = Field(default_factory=FastEmbedRerankingOptionsDict)
    """Parameters for FastEmbed reranking requests."""

    def _as_options(self) -> SerializedRerankingOptionsDict:
        """Convert the FastEmbed reranking configuration to a dictionary of options."""
        return SerializedRerankingOptionsDict(
            model_name=self.model_name, rerank=cast(dict[str, Any], self.rerank or {}), model={}
        )

    @classmethod
    def _defaults(cls) -> dict[str, Any]:
        """Default config values for the rerank config."""
        return {"rerank": {"batch_size": DEFAULT_EMBEDDING_BATCH_SIZE}}


class SentenceTransformersRerankingConfig(BaseRerankingConfig):
    """Configuration options for Sentence Transformers reranking models.

    Uses CrossEncoder models for reranking tasks.
    """

    provider: Literal[Provider.SENTENCE_TRANSFORMERS] = Provider.SENTENCE_TRANSFORMERS

    model_name: ModelNameT
    """The Sentence Transformers cross-encoder model to use (e.g., 'cross-encoder/ms-marco-MiniLM-L6-v2')."""

    rerank: SentenceTransformersRerankingOptionsDict = Field(
        default_factory=lambda data: SentenceTransformersRerankingOptionsDict(
            top_k=DEFAULT_RERANKING_MAX_RESULTS, **data.get("rerank", {})
        )
    )
    """Parameters for Sentence Transformers reranking requests."""

    def _as_options(self) -> SerializedRerankingOptionsDict:
        """Convert the Sentence Transformers reranking configuration to a dictionary of options."""
        return SerializedRerankingOptionsDict(
            model_name=self.model_name,
            rerank=cast(dict[str, Any], (self._defaults | (self.rerank or {}))),  # ty:ignore[unsupported-operator]
            model={},
        )

    @override
    @classmethod
    def _defaults(cls) -> dict[Literal["rerank"], SentenceTransformersRerankingOptionsDict]:  # ty:ignore[invalid-method-override]
        """Default config values for the rerank config."""
        return {
            "rerank": SentenceTransformersRerankingOptionsDict(
                top_k=DEFAULT_RERANKING_MAX_RESULTS,
                show_progress_bar=False,
                batch_size=DEFAULT_EMBEDDING_BATCH_SIZE,
                return_documents=False,
            )
        }


RerankingConfigT = Annotated[
    VoyageRerankingConfig
    | CohereRerankingConfig
    | BedrockRerankingConfig
    | FastEmbedRerankingConfig
    | SentenceTransformersRerankingConfig,
    Field(
        description="All defined reranking configuration types, not including base types. This is used for type annotations in provider settings."
    ),
]
# This isn't a discriminated union because the classes are discriminated by their parent classes (i.e. FastEmbedRerankingProviderSettings uses FastEmbedRerankingConfig, which is how we determine the type), so we don't need a discriminator here. This is just a convenient type annotation for all the specific config types.

__all__ = (
    "BaseRerankingConfig",
    "BedrockRerankingConfig",
    "BedrockRerankingModelConfig",
    "BedrockRerankingOptionsDict",
    "CohereRerankingConfig",
    "CohereRerankingOptionsDict",
    "FastEmbedRerankingConfig",
    "FastEmbedRerankingOptionsDict",
    "RerankingConfigT",
    "SentenceTransformersRerankingConfig",
    "SentenceTransformersRerankingOptionsDict",
    "SerializedRerankingOptionsDict",
    "VoyageRerankingConfig",
    "VoyageRerankingOptionsDict",
)

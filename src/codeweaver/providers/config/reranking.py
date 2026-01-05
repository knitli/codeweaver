"""Provider-specific reranking configuration models and utilities."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Sequence
from typing import Annotated, Any, Literal, LiteralString, NotRequired, Required, TypedDict

from pydantic import Field

from codeweaver.core import BasedModel, LiteralProvider, Provider


class SerializedRerankingOptionsDict(TypedDict, total=False):
    """A dictionary representing serialized reranking options for different providers."""

    model_name: Required[LiteralString]
    """The name of the reranking model in the format used by the provider."""

    reranking: NotRequired[dict[str, Any]]
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

    return_documents: NotRequired[bool]
    """If False: returns {index, relevance_score}. If True: returns {index, text, relevance_score}. Defaults to False."""

    max_chunks_per_doc: NotRequired[int]
    """Maximum chunks to produce internally from a document. Constraint: num_documents * max_chunks_per_doc ≤ 10,000."""

    max_tokens_per_doc: NotRequired[int]
    """Maximum tokens per document. Defaults to 4,096. Documents exceeding this are truncated."""

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
    """Number of results to return (this is top_n). Defaults to 40."""


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

    _tag: LiteralProvider = Field(
        ...,
        description="The provider tag for the reranking model. Used for discriminated unions.",
        exclude=True,
    )

    provider: Provider = Field(
        ...,
        description="The provider for this reranking configuration. Used for discriminated unions.",
    )

    model_name: LiteralString
    """The name of the reranking model."""

    reranking: Annotated[
        dict[str, Any] | None, Field(description="Parameters for reranking requests.")
    ] = None

    def _telemetry_keys(self) -> None:
        """Get the telemetry keys for the model."""

    @abstractmethod
    def _as_options(self) -> SerializedRerankingOptionsDict:
        """Return the configuration as a dictionary of options. Subclasses must implement this method."""
        raise NotImplementedError("Subclasses must implement _as_options method.")

    def as_options(self) -> SerializedRerankingOptionsDict:
        """Return the configuration as a dictionary of options."""
        return self._as_options()


# ============================================================================
# Provider-Specific Configs
# ============================================================================


class VoyageRerankingConfig(BaseRerankingConfig):
    """Configuration options for Voyage AI reranking models."""

    _tag: Literal["voyage"] = "voyage"
    provider: Literal[Provider.VOYAGE] = Provider.VOYAGE

    model_name: LiteralString
    """The Voyage AI reranking model to use (e.g., 'rerank-2.5', 'rerank-2.5-lite')."""

    reranking: VoyageRerankingOptionsDict | None = None
    """Parameters for Voyage reranking requests."""

    def _as_options(self) -> SerializedRerankingOptionsDict:
        """Convert the Voyage reranking configuration to a dictionary of options."""
        return SerializedRerankingOptionsDict(
            model_name=self.model_name,
            reranking=self.reranking or {},
            model={},
        )


class CohereRerankingConfig(BaseRerankingConfig):
    """Configuration options for Cohere reranking models."""

    _tag: Literal["cohere"] = "cohere"
    provider: Literal[Provider.COHERE] = Provider.COHERE

    model_name: LiteralString
    """The Cohere reranking model to use (e.g., 'rerank-v4.0-pro', 'rerank-v3.5')."""

    reranking: CohereRerankingOptionsDict | None = None
    """Parameters for Cohere reranking requests."""

    def _as_options(self) -> SerializedRerankingOptionsDict:
        """Convert the Cohere reranking configuration to a dictionary of options."""
        return SerializedRerankingOptionsDict(
            model_name=self.model_name,
            reranking=self.reranking or {},
            model={},
        )


class BedrockRerankingConfig(BaseRerankingConfig):
    """Configuration options for Bedrock reranking models.

    Bedrock is the only provider that requires model-level configuration.
    """

    _tag: Literal["bedrock"] = "bedrock"
    provider: Literal[Provider.BEDROCK] = Provider.BEDROCK

    model_name: LiteralString
    """The Bedrock reranking model to use (e.g., 'amazon.rerank-v1:0', 'cohere.rerank-v3-5:0')."""

    model: BedrockRerankingModelConfig
    """Model configuration including ARN and additional fields."""

    reranking: BedrockRerankingOptionsDict | None = None
    """Parameters for Bedrock reranking requests."""

    def _as_options(self) -> SerializedRerankingOptionsDict:
        """Convert the Bedrock reranking configuration to a dictionary of options."""
        return SerializedRerankingOptionsDict(
            model_name=self.model_name,
            reranking=self.reranking or {},
            model=self.model,
        )


class FastEmbedRerankingConfig(BaseRerankingConfig):
    """Configuration options for FastEmbed reranking models."""

    _tag: Literal["fastembed"] = "fastembed"
    provider: Literal[Provider.FASTEMBED] = Provider.FASTEMBED

    model_name: LiteralString
    """The FastEmbed reranking model to use (e.g., 'Xenova/ms-marco-MiniLM-L-6-v2')."""

    reranking: FastEmbedRerankingOptionsDict | None = None
    """Parameters for FastEmbed reranking requests."""

    def _as_options(self) -> SerializedRerankingOptionsDict:
        """Convert the FastEmbed reranking configuration to a dictionary of options."""
        return SerializedRerankingOptionsDict(
            model_name=self.model_name,
            reranking=self.reranking or {},
            model={},
        )


class SentenceTransformersRerankingConfig(BaseRerankingConfig):
    """Configuration options for Sentence Transformers reranking models.

    Uses CrossEncoder models for reranking tasks.
    """

    _tag: Literal["sentence_transformers"] = "sentence_transformers"
    provider: Literal[Provider.SENTENCE_TRANSFORMERS] = Provider.SENTENCE_TRANSFORMERS

    model_name: LiteralString
    """The Sentence Transformers cross-encoder model to use (e.g., 'cross-encoder/ms-marco-MiniLM-L6-v2')."""

    reranking: SentenceTransformersRerankingOptionsDict | None = None
    """Parameters for Sentence Transformers reranking requests."""

    def _as_options(self) -> SerializedRerankingOptionsDict:
        """Convert the Sentence Transformers reranking configuration to a dictionary of options."""
        return SerializedRerankingOptionsDict(
            model_name=self.model_name,
            reranking=self.reranking or {},
            model={},
        )


# ============================================================================
# Discriminator Type Union
# ============================================================================

RerankingConfigT = Annotated[
    VoyageRerankingConfig
    | CohereRerankingConfig
    | BedrockRerankingConfig
    | FastEmbedRerankingConfig
    | SentenceTransformersRerankingConfig,
    Field(discriminator="provider"),
]
"""Discriminated union type for all reranking configuration classes."""

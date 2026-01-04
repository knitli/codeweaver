from __future__ import annotations

from abc import abstractmethod
from typing import Annotated, Any, Literal, LiteralString, NotRequired, Required, TypedDict

from pydantic import Discriminator, Field, Tag

from codeweaver.core import BasedModel


def adjust_collection_config_for_datatype(datatype: Literal["float16", "uint8"]) -> None:
    """Adjust the collection configuration based on the specified datatype.

    Qdrant currently expects to receive floats, but can quantize to float16 or uint8 on ingest. So we need to adjust the collection config accordingly. (it can also handle binary vectors, but setting them up is more complex and we don't support that yet)

    Args:
        datatype (Literal["float16", "uint8"]): The datatype for the embeddings.

    Raises:
        ValueError: If an unsupported datatype is provided.
    """
    raise NotImplementedError("This function is a placeholder, this needs to be implemented later.")


def adjust_collection_config_for_dimensionality(dimensions: int) -> None:
    """Adjust the collection configuration based on the specified dimensionality.

    If we are dealing with non-default dimensionality embeddings, we need to update the collection config accordingly.

    Args:
        dimensions (int): The dimensionality of the embeddings.
    """
    raise NotImplementedError("This function is a placeholder, this needs to be implemented later.")


class SerializedEmbeddingOptionsDict(TypedDict, total=False):
    """A dictionary representing serialized embedding options for different providers."""

    model_name: Required[LiteralString]
    """The name of the embedding model in the format used by the provider."""

    constructor: NotRequired[dict[str, Any]]

    embedding: NotRequired[dict[str, Any]]

    model: NotRequired[dict[str, Any]]

    query: NotRequired[dict[str, Any]]


class BaseEmbeddingConfig(BasedModel):
    """Base configuration for embedding models."""

    model_name: LiteralString
    """The name of the embedding model."""

    def _telemetry_keys(self) -> None:
        """Get the telemetry keys for the model."""

    @abstractmethod
    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Return the configuration as a dictionary of options. Subclasses must implement this method and should leave the as_options method alone."""
        raise NotImplementedError("Subclasses must implement as_options method.")

    def as_options(self) -> SerializedEmbeddingOptionsDict:
        """Return the configuration as a dictionary of options."""
        return SerializedEmbeddingOptionsDict(**(self._defaults | self._as_options()))  # ty:ignore[missing-typed-dict-key]

    @property
    def _defaults(self) -> dict[str, Any]:
        """Return default values for the configuration."""
        return {}


class BedrockEmbeddingRequestParams(TypedDict, total=False):
    """Parameters for Bedrock embedding requests."""

    model_id: Required[str]
    """The model ID to use for generating embeddings. The value for this depends on the model, your account, and other factors. [See the Bedrock docs](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-runtime/client/invoke_model.html) for more information. tl;dr **use the model ARN if you aren't sure.**"""
    trace: NotRequired[Literal["ENABLED", "DISABLED", "ENABLED_FULL"]]
    """Whether to enable tracing for the requests made to Bedrock. Defaults to "DISABLED"."""
    guardrail_identifier: NotRequired[str]
    """The guardrail identifier to use for the request. This is used to enforce safety and compliance policies. We'll default to null/None. If you need this, you'll know."""
    guardrail_version: NotRequired[str]
    """The guardrail version to use for the request, if using guardrails."""
    performance_config_latency: NotRequired[Literal["standard", "optimized"]]
    """The performance configuration for latency. Can be "standard" or "optimized". Defaults to "standard"."""


class BedrockTitanV2ConfigDict(TypedDict, total=False):
    """Configuration options specific to the Bedrock Titan V2 embedding model."""

    dimensions: NotRequired[Literal[256, 512, 1024]]
    """Number of dimensions for the embeddings. Can be 256, 512, or 1024. Defaults to 1024."""
    embedding_types: NotRequired[Literal["float", "binary"]]


class BedrockCohereConfigDict(TypedDict, total=False):
    """Configuration options specific to Bedrock Cohere embedding models."""

    truncate: NotRequired[Literal["NONE", "START", "END"]]
    """Truncation strategy for inputs that exceed the model's maximum context length. Can be "NONE", "START", or "END". Defaults to "NONE"."""
    embedding_types: NotRequired[Literal["float", "int8", "uint8", "binary", "ubinary"]]


def _set_bedrock_model_config_discriminator(v: Any) -> Literal["cohere", "titan"]:
    """Set the discriminator for Bedrock model configuration based on the model name."""
    model_name = v.get("model_name") if isinstance(v, dict) else v.model_name
    return "cohere" if model_name.startswith("cohere") else "titan"


type BedrockModelConfig = Annotated[
    Annotated[BedrockCohereConfigDict, Tag("cohere")]
    | Annotated[BedrockTitanV2ConfigDict, Tag("titan")],
    Discriminator(_set_bedrock_model_config_discriminator),
]


class BedrockEmbeddingConfig(BaseEmbeddingConfig):
    """Configuration options for Bedrock embedding models."""

    model_name: (
        Literal[
            "amazon.titan-embed-text-v2:0",
            "cohere.embed-english-v3.0",
            "cohere.embed-multilingual-v3.0",
        ]
        | LiteralString
    )
    """The Bedrock embedding model to use. Can be one of the predefined models or a custom model identifier. Note that this isn't the AWS `model_id` (usually its ARN) - that's specified in the embedding request params."""

    model: Annotated[
        BedrockModelConfig, Field(description="Model-specific embedding configuration options.")
    ]
    """Model-specific embedding configuration options."""

    embedding: BedrockEmbeddingRequestParams | None
    """Parameters for the embedding request to Bedrock."""

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the Bedrock embedding configuration to a dictionary of options."""
        model = self.model.copy()
        if model.get("embedding_types", "float") in ["int8", "uint8", "binary", "ubinary"]:
            adjust_collection_config_for_datatype("uint8")
            model.pop("embedding_types", None)
        if dimensions := model.get("dimensions"):
            adjust_collection_config_for_dimensionality(dimensions)
        return SerializedEmbeddingOptionsDict(
            model_name=self.model_name,
            model=model,  # ty:ignore[invalid-argument-type]
            embedding=self.embedding or {},  # ty:ignore[invalid-argument-type]
            query=self.embedding or {},  # ty:ignore[invalid-argument-type]
        )

    @property
    def _defaults(self) -> dict[str, Any]:
        """Return default values for the configuration."""
        if self.model_name.startswith("cohere"):
            return {"model": {"embedding_types": "float", "truncate": "NONE"}}
        if self.model_name.startswith(
            "amazon.titan-embed-text-v2"
        ):  # be specific because models change and dimensions might too
            return {"model": {"dimensions": 1024, "embedding_types": "float"}}
        return {}


class FastembedEmbeddingConfigDict(BaseEmbeddingConfig):
    """Configuration options for Fastembed embedding models."""

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the Fastembed embedding configuration to a dictionary of options."""
        return SerializedEmbeddingOptionsDict(
            model_name=self.model_name, embedding={}, query={}, model={}
        )


class GoogleEmbeddingRequestParams(TypedDict, total=False):
    """Parameters for Google embedding requests."""

    output_dimensionality: NotRequired[int]
    """The desired output dimensionality for the embeddings. Defaults to 768. `gemini-test-embedding-001` supports 3072, 1536, or 768 dimensions. We default to 768 because the retrieval performance hit is tiny (~1%) and the size savings are significant (4x smaller), and you get faster inference too."""


class GoogleEmbeddingConfig(BaseEmbeddingConfig):
    """Configuration options for Google embedding models."""

    model_name: Literal["gemini-embedding-001"] | LiteralString
    """The Google embedding model to use."""
    embedding: GoogleEmbeddingRequestParams | None
    """Parameters for the embedding request to Google."""

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the Google embedding configuration to a dictionary of options."""
        if (
            output_dimensionality := self.embedding.get("output_dimensionality")
            if self.embedding
            else None
        ):
            adjust_collection_config_for_dimensionality(output_dimensionality)
        embedding_options = {"model": self.model_name} | (self.embedding or {})
        return SerializedEmbeddingOptionsDict(
            model_name=self.model_name,
            embedding=embedding_options,
            query=embedding_options,
            model={},
        )

    @property
    def _defaults(self) -> dict[str, Any]:
        """Return default values for the configuration."""
        return (
            {"embedding": {"output_dimensionality": 768}}
            if self.model_name == "gemini-embedding-001"
            else {}
        )


class HuggingFaceEmbeddingConfigDict(BaseEmbeddingConfig):
    """Configuration options for HuggingFace embedding models."""

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the HuggingFace embedding configuration to a dictionary of options."""
        return SerializedEmbeddingOptionsDict(
            model_name=self.model_name,
            embedding={"model": self.model_name},
            query={"model": self.model_name},
            model={},
        )

    @property
    def _defaults(self) -> dict[str, Any]:
        """Return default values for the configuration."""
        return {
            "embedding": {
                "normalize": True,
                "prompt_name": "passage",
                "truncation_direction": "right",
            },
            "query": {"normalize": True, "prompt_name": "query", "truncation_direction": "left"},
        }

# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Provider-specific embedding configuration models and utilities."""

from __future__ import annotations

import logging

from abc import abstractmethod
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Literal,
    LiteralString,
    NotRequired,
    Required,
    TypedDict,
    cast,
    overload,
)

from cyclopts.types import PositiveInt
from pydantic import Discriminator, Field, Tag, computed_field

from codeweaver.core import BasedModel, ConfigurationError, LiteralProvider, Provider
from codeweaver.providers.config.types import CohereRequestOptionsDict


logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from codeweaver.providers.embedding.capabilities.base import (
        EmbeddingModelCapabilities,
        SparseEmbeddingModelCapabilities,
    )

DATATYPE_FIELDS = {"encoding_format", "output_dtype", "embedding_types", "precision"}
"""Fields that specify the datatype of embeddings in provider configs."""

INCOMPATIBLE_FIELDS = {"prompt_name", "prompt", "task"}
"""Fields that cannot be shared between query and embedding configs even if the types are the same."""

DIMENSION_FIELDS = {
    "dimension",
    "dimensions",
    "output_dimension",
    "output_dimensions",
    "output_dimensionality",
    "truncate_dim",
}


@overload
def _get_embedding_capabilities_for_model(
    model_name: LiteralString, *, sparse: Literal[True]
) -> SparseEmbeddingModelCapabilities | None: ...
@overload
def _get_embedding_capabilities_for_model(
    model_name: LiteralString, *, sparse: Literal[False] = False
) -> EmbeddingModelCapabilities | None: ...
def _get_embedding_capabilities_for_model(
    model_name: LiteralString, *, sparse: bool = False
) -> EmbeddingModelCapabilities | SparseEmbeddingModelCapabilities | None:
    """Get the embedding model capabilities for a given model name.

    Args:
        model_name: The name of the embedding model.
        sparse: Whether to get sparse embedding capabilities.

    Returns:
        The embedding model capabilities or None if not found.
    """


class SerializedEmbeddingOptionsDict(TypedDict, total=False):
    """A dictionary representing serialized embedding options for different providers."""

    model_name: Required[LiteralString]
    """The name of the embedding model in the format used by the provider."""

    embedding: NotRequired[dict[str, Any]]

    model: NotRequired[dict[str, Any]]

    query: NotRequired[dict[str, Any]]


class BaseEmbeddingConfig(BasedModel):
    """Base configuration for embedding models."""

    _is_sparse: ClassVar[bool] = False

    _tag: LiteralProvider = Field(
        ...,
        description="The provider tag for the embedding model. Used for discriminated unions.",
        exclude=True,
    )

    provider: Provider = Field(
        ...,
        description="The provider for this embedding configuration. Used for discriminated unions.",
    )

    model_name: LiteralString
    """The name of the embedding model."""

    embedding: Annotated[
        dict[str, Any] | None, Field(description="Parameters for document embedding requests.")
    ] = None

    query: Annotated[
        dict[str, Any] | None,
        Field(
            description="Parameters for query embedding requests (often the same as embedding; if the types for each are the same, we'll copy the values so you only need to provide one)."
        ),
    ] = None

    def __init__(self, **data: Any) -> None:
        """Initialize the embedding configuration."""
        if (
            ((embedding := data.get("embedding")) and not (query := data.get("query")))
            or (query and not embedding)
        ) and self._query_and_embedding_same_type():
            # if only one of embedding or query is provided, and they are the same type, copy it over, with caveats
            no_copy_keys = {"prompt", "prompt_name", "task"}
            if embedding and not query:
                data["query"] = {k: v for k, v in embedding.copy().items() if k not in no_copy_keys}
            elif query and not embedding:
                data["embedding"] = {k: v for k, v in query.copy().items() if k not in no_copy_keys}
        if not embedding:
            data["embedding"] = {}
        if not query:
            data["query"] = {}
        super().__init__(**data)

    def config_dependencies(self) -> dict[str, type]:
        """Embedding configs don't depend on others - they provide values."""
        return {}

    async def apply_resolved_config(self, **resolved: Any) -> None:
        """Nothing to apply - we're a provider, not a consumer."""

    async def get_dimension(self) -> int | Literal[0]:
        """Get resolved dimension through fallback chain.

        Resolution order:
        1. Explicit config (self.embedding/self.query fields)
        2. Model capabilities (from capability resolver)
        3. User-registered defaults
        4. Hardcoded fallback

        Returns:
            Resolved dimension or 0 if sparse embeddings
        """
        if type(self)._is_sparse:
            return 0
        # 1. Explicit config
        for field in ("embedding", "query"):
            if (
                (config := getattr(self, field, None))
                and (found_field := next((f for f in DIMENSION_FIELDS if f in config), None))
                and isinstance(config[found_field], int)
            ):
                return config[found_field]

        # 2. Model capabilities
        if (caps := self.capabilities) and (dim := getattr(caps, "default_dimension", None)):
            return dim

        # 3. User-registered defaults
        from codeweaver.core.config.defaults import get_default

        if user_default := get_default("primary.embedding.dimension"):
            return user_default

        raise ConfigurationError(
            "Could not resolve embedding dimension from config, capabilities, or registered defaults. You need to specify it explicitly, for best results, register an `EmbeddingModelCapabilities` subclass with the capability resolver."
        )

    async def get_datatype(self) -> str | None:
        """Get resolved datatype through fallback chain.

        Resolution order:
        1. Explicit config
        2. Model capabilities
        3. User-registered defaults
        4. Provider-specific defaults

        Returns:
            Resolved datatype or None
        """
        # 1. Explicit config
        for field in ("embedding", "query", "model"):
            if (config := getattr(self, field, None)) and (
                found_field := next((f for f in DATATYPE_FIELDS if f in config), None)
            ):
                return config[found_field]

        # 2. Model capabilities
        if (caps := self.capabilities) and (dtype := getattr(caps, "default_datatype", None)):
            return dtype

        # 3. User-registered defaults
        from codeweaver.core.config.defaults import get_default

        if user_default := get_default("primary.embedding.datatype"):
            return user_default
        # 4. Provider-specific defaults
        if output_default := next(
            (f for f in DATATYPE_FIELDS if f in self._defaults.get("embedding", {})), None
        ):
            return self._defaults.get("embedding", {}).get(output_default)
        return "float16"

    @staticmethod
    def _clean_dtypes(
        kwargs: dict[Literal["embedding", "query", "model"], Any],
    ) -> dict[Literal["embedding", "query", "model"], Any]:
        """Clean up datatype fields from embedding and query configurations."""
        if found_field := next(
            (
                f
                for f in DATATYPE_FIELDS
                if f in kwargs.get("embedding", {})
                or f in kwargs.get("query", {})
                or f in kwargs.get("model", {})
            ),
            None,
        ):
            if "embedding" in kwargs:
                kwargs["embedding"].pop(found_field, None)
            if "query" in kwargs:
                kwargs["query"].pop(found_field, None)
            if "model" in kwargs:
                kwargs["model"].pop(found_field, None)
        if "embedding" in kwargs:
            kwargs["embedding"] = BaseEmbeddingConfig._clean_dtypes(kwargs.get("embedding", {}))
        if "query" in kwargs:
            kwargs["query"] = BaseEmbeddingConfig._clean_dtypes(kwargs.get("query", {}))
        if "model" in kwargs:
            kwargs["model"] = BaseEmbeddingConfig._clean_dtypes(kwargs.get("model", {}))
        return kwargs

    @property
    def capabilities(self) -> EmbeddingModelCapabilities | SparseEmbeddingModelCapabilities | None:
        """Get the embedding model capabilities for this configuration."""
        return _get_embedding_capabilities_for_model(self.model_name, sparse=type(self)._is_sparse)

    @classmethod
    def _query_and_embedding_same_type(cls) -> bool:
        """Check if both query and embedding configurations are of the same type."""
        query_field_info = cls.model_fields.get("query")
        embedding_field_info = cls.model_fields.get("embedding")
        return query_field_info.annotation == embedding_field_info.annotation

    def _telemetry_keys(self) -> None:
        """Get the telemetry keys for the model."""

    @abstractmethod
    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Return the configuration as a dictionary of options. Subclasses must implement this method and should leave the as_options method alone."""
        raise NotImplementedError("Subclasses must implement as_options method.")

    def as_options(self) -> SerializedEmbeddingOptionsDict:
        """Return the configuration as a dictionary of options."""
        serialized = self._as_options()
        return SerializedEmbeddingOptionsDict(  # type: ignore
            **type(self)._clean_dtypes(self._defaults | serialized)  # type: ignore
        )

    @property
    def _defaults(self) -> dict[Literal["embedding", "query", "model"], Any]:
        """Return default values for the configuration."""
        return {}

    @computed_field
    @property
    def dimension(self) -> int | None:
        """Get the embedding dimension (computed field for backward compatibility).

        Note: This is synchronous but get_dimension() is async. For full
        resolution, use get_dimension() directly. This property returns
        only explicitly configured values or None.
        """
        for field in ("embedding", "query"):
            if (
                (config := getattr(self, field, None))
                and (found_field := next((f for f in DIMENSION_FIELDS if f in config), None))
                and isinstance(config[found_field], int)
            ):
                return config[found_field]
        return None


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

    _tag: Literal["bedrock"] = "bedrock"
    provider: Literal[Provider.BEDROCK] = Provider.BEDROCK

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


class CohereEmbeddingOptionsDict(TypedDict, total=False):
    """Embedding request options for Cohere embedding API.

    These parameters are passed to the embed() method.
    """

    model: Required[LiteralString]
    """The Cohere embedding model to use."""

    max_tokens: NotRequired[PositiveInt]
    """The maximum number of tokens to process. Will truncate inputs longer than this using the truncation strategy."""

    output_dimension: NotRequired[Literal[256, 512, 1024, 1536]]
    """The desired output dimensionality for the embeddings. Default is 1536."""

    embedding_types: NotRequired[Literal["float", "int8", "uint8", "binary", "ubinary"]]

    truncate: NotRequired[Literal["NONE", "START", "END"]]
    """Truncation strategy for inputs that exceed the model's maximum context length. Can be "NONE", "START", or "END". Defaults to "NONE"."""

    request_options: CohereRequestOptionsDict | None
    """Additional request options for the Cohere API."""


class CohereEmbeddingConfig(BaseEmbeddingConfig):
    """Configuration options for Cohere embedding models."""

    _tag: Literal["cohere"] = "cohere"
    provider: Literal[Provider.COHERE] = Provider.COHERE

    model_name: (
        Literal[
            "embed-v4.0",
            "embed-english-v3.0",
            "embed-english-light-v3.0",
            "embed-multilingual-v3.0",
            "embed-multilingual-light-v3.0",
        ]
        | LiteralString
    )
    """The Cohere embedding model to use."""

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the Cohere embedding configuration to a dictionary of options."""
        embedding_options = {"model": self.model_name} | (self.embedding or {})
        query_options = {"model": self.model_name} | (self.query or {})
        return SerializedEmbeddingOptionsDict(
            model_name=self.model_name, embedding=embedding_options, query=query_options, model={}
        )


class FastEmbedEmbeddingConfig(BaseEmbeddingConfig):
    """Configuration options for FastEmbed embedding models."""

    _tag: Literal["fastembed"] = "fastembed"
    provider: Literal[Provider.FASTEMBED] = Provider.FASTEMBED

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the FastEmbed embedding configuration to a dictionary of options."""
        return SerializedEmbeddingOptionsDict(
            model_name=self.model_name, embedding={}, query={}, model={}
        )


class GoogleEmbeddingRequestParams(TypedDict, total=False):
    """Parameters for Google embedding requests."""

    output_dimensionality: NotRequired[int]
    """The desired output dimensionality for the embeddings. Defaults to 768. `gemini-test-embedding-001` supports 3072, 1536, or 768 dimensions. We default to 768 because the retrieval performance hit is tiny (~1%) and the size savings are significant (4x smaller), and you get faster inference too."""


class GoogleEmbeddingConfig(BaseEmbeddingConfig):
    """Configuration options for Google embedding models."""

    _tag: Literal["google"] = "google"
    provider: Literal[Provider.GOOGLE] = Provider.GOOGLE

    model_name: Literal["gemini-embedding-001"] | LiteralString
    """The Google embedding model to use."""
    embedding: GoogleEmbeddingRequestParams | None = None
    """Parameters for the embedding request to Google."""

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the Google embedding configuration to a dictionary of options."""
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


class HuggingFaceEmbeddingConfig(BaseEmbeddingConfig):
    """Configuration options for HuggingFace embedding models."""

    _tag: Literal["huggingface"] = "huggingface"
    provider: Literal[Provider.HUGGINGFACE_INFERENCE] = Provider.HUGGINGFACE_INFERENCE

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
                "truncate": True,
                "truncation_direction": "right",
            },
            "query": {
                "normalize": True,
                "prompt_name": "query",
                "truncate": True,
                "truncation_direction": "left",
            },
        }


class MistralEmbeddingOptionsDict(TypedDict, total=False):
    """Embedding request options for Mistral AI embedding API.

    These parameters are passed to the embeddings.create() method.
    """

    output_dimension: NotRequired[int]
    """Target embedding dimension (max 3072 for codestral-embed). First n dimensions ordered by relevance."""

    output_dtype: NotRequired[Literal["float", "int8", "uint8", "binary", "ubinary"]]
    """Embedding precision/format. Default is 'float' (32-bit single-precision)."""


class MistralEmbeddingConfig(BaseEmbeddingConfig):
    """Configuration options for Mistral AI embedding models."""

    _tag: Literal["mistral"] = "mistral"
    provider: Literal[Provider.MISTRAL] = Provider.MISTRAL

    model_name: Literal["mistral-embed", "codestral-embed"] | LiteralString
    """The Mistral AI embedding model to use."""

    embedding: MistralEmbeddingOptionsDict | None = None
    """Parameters for document embedding requests."""

    query: MistralEmbeddingOptionsDict | None = None
    """Parameters for query embedding requests (same as embedding for Mistral)."""

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the Mistral embedding configuration to a dictionary of options."""
        return SerializedEmbeddingOptionsDict(
            model_name=self.model_name,
            embedding=cast(dict[str, Any], self.embedding or {}),
            query=cast(dict[str, Any], self.query or {}),
            model={},
        )


class OpenAIEmbeddingRequestParams(TypedDict, total=False):
    """Parameters for OpenAI-compatible embedding requests.

    These parameters work across all OpenAI-compatible providers including
    Azure OpenAI, Ollama, Fireworks, Together AI, GitHub Models, and Groq.
    """

    dimensions: NotRequired[int]
    """Output dimensionality for the embeddings. Only supported by text-embedding-3-* models."""

    user: NotRequired[str]
    """End-user identifier for abuse monitoring and tracking."""

    timeout: NotRequired[float]
    """Request timeout in seconds."""

    extra_headers: NotRequired[dict[str, str]]
    """Additional HTTP headers for the request."""

    extra_query: NotRequired[dict[str, Any]]
    """Additional query parameters for the request."""

    extra_body: NotRequired[dict[str, Any]]
    """Additional request body parameters."""


class OpenAIEmbeddingConfig(BaseEmbeddingConfig):
    """Configuration options for OpenAI and OpenAI-compatible embedding models.

    Supports OpenAI, Azure OpenAI, Ollama, Fireworks, Together AI, GitHub Models, Groq, and other OpenAI-compatible providers.
    """

    _tag: Literal["openai"] = "openai"
    provider: Literal[Provider.OPENAI] = Provider.OPENAI

    model_name: Literal["text-embedding-3-large", "text-embedding-3-small"] | LiteralString
    """The OpenAI-compatible embedding model to use."""

    embedding: OpenAIEmbeddingRequestParams | None = None
    """Parameters for document embedding requests."""

    query: OpenAIEmbeddingRequestParams | None = None
    """Parameters for query embedding requests (same as embedding for OpenAI)."""

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the OpenAI embedding configuration to a dictionary of options."""
        return SerializedEmbeddingOptionsDict(
            model_name=self.model_name,
            embedding=cast(dict[str, Any], self.embedding or {}),
            query=cast(dict[str, Any], self.query or {}),
            model={},
        )

    @property
    def _defaults(self) -> dict[str, Any]:
        """Return default values for the configuration."""
        return {
            "embedding": {"encoding_format": "float", "timeout": 30.0},
            "query": {"encoding_format": "float", "timeout": 30.0},
        }

    def _telemetry_handler(self, _serialized_self: dict[str, Any], /) -> dict[str, Any]:
        """Custom telemetry filtering for OpenAI embedding config."""
        # the class init will copy over the embedding/query dicts if only one is provided, so we just check one
        if self.embedding:
            filtered_embedding: dict[str, Any] = self.embedding.copy()  # ty:ignore[invalid-assignment]
            if "extra_headers" in filtered_embedding:
                filtered_embedding["extra_headers"] = True
            if "extra_query" in filtered_embedding:
                filtered_embedding["extra_query"] = True
            if "extra_body" in filtered_embedding:
                filtered_embedding["extra_body"] = True
            if "user" in filtered_embedding:
                from codeweaver.core import get_blake_hash

                filtered_embedding["user"] = get_blake_hash(filtered_embedding["user"])
        return {"embedding": filtered_embedding, "query": filtered_embedding.copy()}


class SentenceTransformersEncodeDict(TypedDict, total=False):
    """Parameters for the SentenceTransformer encode() method."""

    prompt_name: NotRequired[str]
    """Name of prompt from model's prompts dictionary."""

    prompt: NotRequired[str]
    """Custom prompt text prepended to sentences."""

    batch_size: NotRequired[int]
    """Batch size for encoding. Default is 32."""

    show_progress_bar: NotRequired[bool]
    """Display progress bar during encoding."""

    output_value: NotRequired[Literal["sentence_embedding", "token_embeddings"]]
    """Return type for embeddings. Default is 'sentence_embedding'."""

    precision: NotRequired[Literal["float32", "int8", "uint8", "binary", "ubinary"]]
    """Quantization level for embeddings. Default is 'float32'."""

    device: NotRequired[str | list[str]]
    """Computation device(s). E.g., 'cuda:0', 'cpu', or list for multi-process."""

    truncate_dim: NotRequired[int]
    """Dimension reduction for Matryoshka models."""

    pool: NotRequired[dict[str, Any]]
    """Multi-process pool configuration."""

    chunk_size: NotRequired[int]
    """Chunk size for multi-process encoding."""

    task: NotRequired[str]
    """Task identifier for Router models (e.g., 'query', 'document')."""

    max_active_dims: NotRequired[int]
    """Maximum active dimensions for SparseAutoEncoder models."""


class SentenceTransformersEmbeddingConfig(BaseEmbeddingConfig):
    """Configuration options for Sentence Transformers embedding models.

    Note: Sentence Transformers receives model kwargs through its client constructor. Provide model options to the `model_kwargs` field in `SentenceTransformersClientOptions`.
    """

    _tag: Literal["sentence_transformers"] = "sentence_transformers"
    provider: Literal[Provider.SENTENCE_TRANSFORMERS] = Provider.SENTENCE_TRANSFORMERS

    model_name: LiteralString
    """The Sentence Transformers model to use."""

    embedding: SentenceTransformersEncodeDict | None = None
    """Parameters for document/corpus encoding."""

    query: SentenceTransformersEncodeDict | None = None
    """Parameters for query encoding (if different from document)."""

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the Sentence Transformers configuration to a dictionary of options."""
        return SerializedEmbeddingOptionsDict(
            model_name=self.model_name,
            embedding=cast(dict[str, Any], self.embedding or {}),
            query=cast(dict[str, Any], self.query or {}),
            model={},
        )

    @property
    def _defaults(self) -> dict[str, Any]:
        """Return default values for the configuration."""
        return {
            "embedding": {
                "normalize_embeddings": True,
                "convert_to_numpy": True,
                "batch_size": 64,
                "show_progress_bar": False,
            },
            "query": {
                "normalize_embeddings": True,
                "convert_to_numpy": True,
                "batch_size": 64,
                "show_progress_bar": False,
            },
        }


class VoyageEmbeddingOptionsDict(TypedDict, total=False):
    """Parameters for Voyage AI embedding requests."""

    truncation: NotRequired[bool]
    """Whether to truncate inputs exceeding context length. Default is True."""

    output_dimension: NotRequired[int]
    """Desired output dimensionality (model-dependent)."""

    output_dtype: NotRequired[Literal["float", "int8", "uint8", "binary", "ubinary"]]
    """Data type for embeddings. Default is 'float'."""


class VoyageEmbeddingConfig(BaseEmbeddingConfig):
    """Configuration options for Voyage AI embedding models."""

    _tag: Literal["voyage"] = "voyage"
    provider: Literal[Provider.VOYAGE] = Provider.VOYAGE

    model_name: (
        Literal[
            "voyage-code-3", "voyage-3.5", "voyage-3.5-lite", "voyage-3-large", "voyage-context-3"
        ]
        | LiteralString
    )
    """The Voyage AI embedding model to use."""

    embedding: VoyageEmbeddingOptionsDict | None = None
    """Parameters for document embedding requests."""

    query: VoyageEmbeddingOptionsDict | None = None
    """Parameters for query embedding requests."""

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the Voyage embedding configuration to a dictionary of options."""
        return SerializedEmbeddingOptionsDict(
            model_name=self.model_name,
            embedding=cast(dict[str, Any], (self.embedding or {}) | {"input_type": "document"}),
            query=cast(dict[str, Any], (self.query or {}) | {"input_type": "query"}),
            model={},
        )

    @property
    def _defaults(self) -> dict[str, Any]:
        """Return default values for the configuration."""
        return {
            "embedding": {"input_type": "document", "truncation": True, "output_dtype": "float"},
            "query": {"input_type": "query", "truncation": True, "output_dtype": "float"},
        }


# ============================================================================
# Sparse Embedding Configs (Reuse dense configs with renamed classes)
# ============================================================================


class SentenceTransformersSparseEmbeddingConfig(SentenceTransformersEmbeddingConfig):
    """Configuration options for Sentence Transformers sparse embedding models.

    Inherits all configuration from SentenceTransformersEmbeddingConfig.
    """

    _is_sparse: ClassVar[bool] = True


class FastEmbedSparseEmbeddingConfig(FastEmbedEmbeddingConfig):
    """Configuration options for FastEmbed sparse embedding models.

    Inherits all configuration from FastEmbedEmbeddingConfig.
    """

    _is_sparse: ClassVar[bool] = True


# ============================================================================
# Discriminator Type Unions
# ============================================================================

EmbeddingConfigT = Annotated[
    BedrockEmbeddingConfig
    | FastEmbedEmbeddingConfig
    | GoogleEmbeddingConfig
    | HuggingFaceEmbeddingConfig
    | MistralEmbeddingConfig
    | OpenAIEmbeddingConfig
    | SentenceTransformersEmbeddingConfig
    | VoyageEmbeddingConfig,
    Field(discriminator="provider"),
]
"""Discriminated union type for all embedding configuration classes."""

SparseEmbeddingConfigT = Annotated[
    SentenceTransformersSparseEmbeddingConfig | FastEmbedSparseEmbeddingConfig,
    Field(discriminator="provider"),
]
"""Discriminated union type for all sparse embedding configuration classes."""


__all__ = (
    "DATATYPE_FIELDS",
    "DIMENSION_FIELDS",
    "BaseEmbeddingConfig",
    "BedrockCohereConfigDict",
    "BedrockEmbeddingConfig",
    "BedrockEmbeddingRequestParams",
    "BedrockTitanV2ConfigDict",
    "EmbeddingConfigT",
    "FastEmbedEmbeddingConfig",
    "FastEmbedSparseEmbeddingConfig",
    "GoogleEmbeddingConfig",
    "GoogleEmbeddingRequestParams",
    "HuggingFaceEmbeddingConfig",
    "MistralEmbeddingConfig",
    "MistralEmbeddingOptionsDict",
    "OpenAIEmbeddingConfig",
    "OpenAIEmbeddingRequestParams",
    "SentenceTransformersEmbeddingConfig",
    "SentenceTransformersEncodeDict",
    "SentenceTransformersSparseEmbeddingConfig",
    "SerializedEmbeddingOptionsDict",
    "SparseEmbeddingConfigT",
    "VoyageEmbeddingConfig",
    "VoyageEmbeddingOptionsDict",
)

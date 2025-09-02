# SPDX-FileCopyrightText: (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

"""Base types and models for CodeWeaver embedding models."""

from __future__ import annotations

from typing import Annotated, Any, Literal, LiteralString, NotRequired, Required, Self, TypedDict

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt

from codeweaver._common import BaseEnum
from codeweaver._settings import Provider


class TransformersEmbeddingTask(BaseEnum):
    """An enum representing the different types of embedding tasks supported by Hugging Face Transformers models."""

    QUERY = "query"
    PASSAGE = "passage"

    # These are hybrids that are used by jinaai/jina-embeddings-v4
    RETRIEVAL_QUERY = "retrieval.query"
    RETRIEVAL_PASSAGE = "retrieval.passage"
    CODE_QUERY = "code.query"
    CODE_PASSAGE = "code.passage"

    @property
    def prompt_name(self) -> Literal["query", "passage"]:
        """Return the prompt name for the embedding task."""
        return "query" if self in {self.QUERY, self.RETRIEVAL_QUERY, self.CODE_QUERY} else "passage"

    @property
    def task_name(self) -> LiteralString:
        """Return the task name for the embedding task."""
        if self in {self.QUERY, self.PASSAGE}:
            return self.value
        return "code" if self in {self.CODE_QUERY, self.CODE_PASSAGE} else "retrieval"


class PoolingMethod(BaseEnum):
    """An enum representing the different types of pooling methods supported by Hugging Face Transformers models."""

    CLS = "cls"
    """Use the embedding of the [CLS] token."""
    MEAN = "mean"
    """Mean pooling over the token embeddings."""
    MAX = "max"
    """Max pooling over the token embeddings."""
    MIN = "min"
    """Min pooling over the token embeddings."""
    SUM = "sum"
    """Sum pooling over the token embeddings."""
    MEDIAN = "median"
    """Median pooling over the token embeddings."""
    FIRST_LAST_AVG = "first_last_avg"
    """Average of the first and last hidden layers."""
    LAST_AVG = "last_avg"
    """Average of the last hidden layer."""

    @property
    def description(self) -> str:
        """Return a description of the pooling method."""
        match self:
            case PoolingMethod.CLS:
                return "Use the embedding of the [CLS] token."
            case PoolingMethod.MEAN:
                return "Mean pooling over the token embeddings."
            case PoolingMethod.MAX:
                return "Max pooling over the token embeddings."
            case PoolingMethod.MIN:
                return "Min pooling over the token embeddings."
            case PoolingMethod.SUM:
                return "Sum pooling over the token embeddings."
            case PoolingMethod.MEDIAN:
                return "Median pooling over the token embeddings."
            case PoolingMethod.FIRST_LAST_AVG:
                return "Average of the first and last hidden layers."
            case PoolingMethod.LAST_AVG:
                return "Average of the last hidden layer."

    @classmethod
    def by_model(cls, model_name: LiteralString) -> PoolingMethod | None:
        """Return the default pooling method for a given model name, if known."""
        model_name = model_name.lower()
        if model_name in frozenset({
            "intfloat/multilingual-e5-large",
            "intfloat/multilingual-e5-large-instruct",
            "jinaai/jina-embeddings-v2-base-code",
            "jinaai/jina-embeddings-v4",
            "jinai/jina-embeddings-v3",
            "nomic-ai/modernbert-embed-base",
            "nomic-ai/nomic-embed-text-v1.5",
            "nomic-ai/nomic-embed-text-v1.5-gguf",
            "nomic-ai/nomic-embed-text-v2-moe",
            "sentence-transformers/all-MiniLM-L12-v2",
            "sentence-transformers/all-MiniLM-L6-v2",
            "sentence-transformers/all-mpnet-base-v2",
            "sentence-transformers/gtr-t5-base",
            "sentence-transformers/multi-qa-MiniLM-L6-cos-v1",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
            "thenlper/gte-base",
            "thenlper/gte-large",
        }):
            return cls.MEAN
        if model_name in frozenset({
            "alibaba-nlp/gte-modernbert-base",
            "alibaba-nlp/gte-multilingual-base",
            "baai/bge-base-en-v1.5",
            "baai/bge-large-en-v1.5",
            "baai/bge-m3",
            "baai/bge-small-en-v1.5",
            "ibm-granite/granite-embedding-278m-multilingual",
            "ibm-granite/granite-embedding-30m-english",
            "mixedbread-ai/mxbai-embed-large",
            "snowflake/snowflake-arctic-embed-l",
            "snowflake/snowflake-arctic-embed-l-v2.0",
            "snowflake/snowflake-arctic-embed-m",
            "snowflake/snowflake-arctic-embed-m-long",
            "snowflake/snowflake-arctic-embed-m-v2.0",
            "snowflake/snowflake-arctic-embed-s",
            "snowflake/snowflake-arctic-embed-xs",
        }):
            return cls.CLS
        if model_name in frozenset({
            "qwen/qwen3-embedding-0.6b",
            "qwen/qwen3-embedding-4b",
            "qwen/qwen3-embedding-8b",
        }):
            return cls.LAST_AVG
        return None


type PartialCapabilities = dict[
    Literal[
        "context_window",
        "custom_document_prompt",
        "custom_query_prompt",
        "default_dimension",
        "default_dtype",
        "other",
        "is_normalized",
        "hf_name",
        "name",
        "output_dimensions",
        "output_dtypes",
        "preferred_metrics",
        "provider",
        "supports_context_chunk_embedding",
        "supports_custom_prompts",
        "tokenizer",
        "tokenizer_model",
        "version",
    ],
    Literal[
        "tokenizers", "tiktoken", "dot", "cosine", "euclidean", "manhattan", "hamming", "chebyshev"
    ]
    | str
    | PositiveInt
    | PositiveFloat
    | bool
    | Provider
    | None
    | dict[str, Any]
    | tuple[str, ...]
    | tuple[PositiveInt, ...],
]


class EmbeddingCapabilities(TypedDict, total=False):
    """Describes the capabilities of an embedding model, such as the default dimension."""

    name: Required[str]
    provider: Required[Provider]
    version: NotRequired[str | int | None]
    default_dimension: NotRequired[PositiveInt]
    output_dimensions: NotRequired[tuple[PositiveInt, ...] | None]
    default_dtype: NotRequired[str | None]
    output_dtypes: NotRequired[tuple[str, ...] | None]
    supports_custom_prompts: NotRequired[bool]
    custom_document_prompt: NotRequired[str] | None
    custom_query_prompt: NotRequired[str] | None
    is_normalized: NotRequired[bool]
    context_window: NotRequired[PositiveInt]
    supports_context_chunk_embedding: NotRequired[bool]
    tokenizer: NotRequired[Literal["tokenizers", "tiktoken"]]
    tokenizer_model: NotRequired[str]
    preferred_metrics: NotRequired[
        tuple[Literal["dot", "cosine", "euclidean", "manhattan", "hamming", "chebyshev"], ...]
    ]
    hf_name: NotRequired[str]
    other: NotRequired[dict[str, Any]]


class EmbeddingModelCapabilities(BaseModel):
    """Describes the capabilities of an embedding model, such as the default dimension."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="allow",
        arbitrary_types_allowed=True,
        serialize_by_alias=True,
    )

    name: Annotated[
        str, Field(min_length=3, description="The name of the model or family of models.")
    ] = ""
    provider: Annotated[
        Provider,
        Field(
            description="The provider of the model. Since available settings vary across providers, each capabilities instance is tied to a provider."
        ),
    ] = Provider._UNSET  # type: ignore
    version: Annotated[
        str | int | None,
        Field(
            description="The version of the model, if applicable. Can be a string or an integer. If not specified, defaults to `None`."
        ),
    ] = None
    default_dimension: Annotated[PositiveInt, Field(multiple_of=8)] = 512
    output_dimensions: Annotated[
        tuple[PositiveInt, ...] | None,
        Field(
            multiple_of=8,
            description="Supported output dimensions, if the model and provider support multiple output dimensions. If not specified, defaults to `None`.",
        ),
    ] = None
    default_dtype: Annotated[
        str | None,
        Field(
            description="A string representing the default data type of the model, such as `float`, if the provider/model accepts different data types. If not specified, defaults to `None`."
        ),
    ] = None
    output_dtypes: Annotated[
        tuple[str, ...] | None,
        Field(
            description="A list of accepted values for output data types, if the model/provider allows different output data types. When available, you can use this to reduce the size of the returned vectors, at the cost of some accuracy (depending on which you choose).",
            examples=[
                "VoyageAI: `('float', 'uint8', 'int8', 'binary', 'ubinary')` for the voyage 3-series models."
            ],
        ),
    ] = None
    is_normalized: bool = False
    context_window: Annotated[PositiveInt, Field(ge=256)] = 512
    supports_context_chunk_embedding: bool = False
    tokenizer: Literal["tokenizers", "tiktoken"] | None = None
    tokenizer_model: Annotated[
        str | None,
        Field(
            min_length=3,
            description="The tokenizer model used by the embedding model. If the tokenizer is `tokenizers`, this should be the full name of the tokenizer or model (if it's listed by its model name), *including the organization*. Like: `voyageai/voyage-code-3`",
        ),
    ] = None
    preferred_metrics: Annotated[
        tuple[Literal["dot", "cosine", "euclidean", "manhattan", "hamming", "chebyshev"], ...],
        Field(
            description="A tuple of preferred metrics for comparing embeddings.",
            examples=[
                "VoyageAI: `('dot',)` for the voyage 3-series models, since they are normalized to length 1."
            ],
        ),
    ] = ("cosine", "dot", "euclidean")
    _version: Annotated[
        str,
        Field(
            init=False,
            pattern=r"^\d{1,2}\.\d{1,3}\.\d{1,3}$",
            description="The version for the capabilities schema.",
        ),
    ] = "1.0.0"
    hf_name: Annotated[
        str | None,
        Field(
            description="The Hugging Face model name, if it applies *and* is different from the model name. Currently only applies to some models from `fastembed` and `ollama`"
        ),
    ] = None
    other: dict[str, Any] | None = None

    @classmethod
    def default(cls) -> Self:
        """Create a default instance of the model profile."""
        return cls()

    @property
    def schema_version(self) -> str:
        """Get the schema version of the capabilities."""
        return self._version

    @classmethod
    def from_capabilities(cls, capabilities: EmbeddingCapabilities) -> Self:
        """Create an instance from a dictionary of capabilities."""
        return cls.model_validate(capabilities)


from importlib.util import find_spec


HAS_FASTEMBED = find_spec("fastembed") is not None
HAS_ST = find_spec("sentence_transformers") is not None


class SparseEmbeddingModelCapabilities(BaseModel):
    """A model describing the capabilities of a sparse embedding model.

    Sparse embeddings are much simpler than dense embeddings, so this model is much simpler.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="allow",
        arbitrary_types_allowed=True,
        serialize_by_alias=True,
    )

    name: Annotated[LiteralString, Field(description="The name of the model.")]
    multilingual: bool = False
    provider: Annotated[
        Literal[Provider.FASTEMBED, Provider.SENTENCE_TRANSFORMERS, Provider._UNSET],  # pyright: ignore[reportPrivateUsage]
        Field(
            default_factory=lambda data: Provider.FASTEMBED
            if HAS_FASTEMBED and data["name"].lower().startswith("qdrant")
            else Provider.SENTENCE_TRANSFORMERS
            if (
                HAS_ST
                and (
                    data["name"].startswith("opensearch") or data["name"].startswith("ibm-granite")
                )
            )
            else Provider._UNSET,  # pyright: ignore[reportPrivateUsage]
            description="The provider of the model. We currently only support local providers for sparse embeddings. Since Sparse embedding tend to be very efficient and low resource, they are well-suited for deployment in resource-constrained environments.",
        ),
    ] = (
        Provider.FASTEMBED
        if HAS_FASTEMBED
        else Provider.SENTENCE_TRANSFORMERS
        if HAS_ST
        else Provider._UNSET  # pyright: ignore[reportPrivateUsage]
    )
    hf_name: Annotated[
        str | None,
        Field(
            description="The Hugging Face model name, if it applies *and* is different from the model name. Currently only applies to some models from `fastembed` and `ollama`"
        ),
    ] = None


def get_sparse_caps() -> tuple[SparseEmbeddingModelCapabilities, ...]:
    """Get sparse embedding model capabilities."""
    caps = {
        "Qdrant/bm25": {"name": "Qdrant/bm25", "multilingual": True},
        "Qdrant/bm42-all-minilm-l6-v2-attentions": {
            "name": "Qdrant/bm42-all-minilm-l6-v2-attentions",
            "multilingual": False,
        },
        "prithivida/Splade-PP_en_v1": {
            "name": "prithivida/Splade-PP_en_v1",
            "multilingual": False,
            "hf_name": "Qdrant/Splade-PP_en_v1",
        },
        "prithivida/Splade-PP_en_v2": {
            "name": "prithivida/Splade-PP_en_v2",
            "multilingual": False,
            "hf_name": None,
        },
        "ibm-granite/granite-embedding-30m-sparse": {
            "name": "ibm-granite/granite-embedding-30m-sparse",
            "multilingual": False,
        },
        "opensearch-project/opensearch-neural-sparse-encoding-doc-v2-mini": {
            "name": "opensearch-project/opensearch-neural-sparse-encoding-doc-v2-mini",
            "multilingual": False,
        },
        "opensearch-project/opensearch-neural-sparse-encoding-doc-v3-distill": {
            "name": "opensearch-project/opensearch-neural-sparse-encoding-doc-v3-distill",
            "multilingual": False,
        },
        "opensearch-project/opensearch-neural-sparse-encoding-doc-v3-gte": {
            "name": "opensearch-project/opensearch-neural-sparse-encoding-doc-v3-gte",
            "multilingual": False,
        },
    }
    fastembed_caps = tuple(
        SparseEmbeddingModelCapabilities.model_validate(cap | {"provider": Provider.FASTEMBED})
        for cap in list(caps.values())[:4]
    )
    st_caps = tuple(
        SparseEmbeddingModelCapabilities.model_validate(
            cap | {"provider": Provider.SENTENCE_TRANSFORMERS}
        )
        for cap in list(caps.values())[3:]
    )
    return fastembed_caps + st_caps

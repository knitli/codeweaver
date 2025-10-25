# SPDX-FileCopyrightText: (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

"""Base types and models for CodeWeaver embedding models."""

from __future__ import annotations

from typing import Annotated, Any, Literal, NotRequired, Required, Self, TypedDict

from pydantic import ConfigDict, Field, PositiveFloat, PositiveInt

from codeweaver.core.types.models import BASEDMODEL_CONFIG, BasedModel
from codeweaver.providers.provider import Provider


class EmbeddingSettingsDict(TypedDict, total=False):
    """A dictionary representing the settings for an embedding client, embedding model, and the embedding call itself. If any."""

    client_kwargs: dict[str, Any]
    model_kwargs: dict[str, Any]
    call_kwargs: dict[str, Any]


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


class EmbeddingModelCapabilities(BasedModel):
    """Describes the capabilities of an embedding model, such as the default dimension."""

    model_config = BASEDMODEL_CONFIG | ConfigDict(extra="allow")

    name: Annotated[
        str, Field(min_length=3, description="""The name of the model or family of models.""")
    ] = ""
    provider: Annotated[
        Provider,
        Field(
            description="""The provider of the model. Since available settings vary across providers, each capabilities instance is tied to a provider."""
        ),
    ] = Provider.UNSET  # type: ignore
    version: Annotated[
        str | PositiveInt | PositiveFloat | None,
        Field(
            description="""The version of the model, if applicable. Can be a string or an integer. If not specified, defaults to `None`."""
        ),
    ] = None
    default_dimension: Annotated[PositiveInt, Field(multiple_of=8)] = 512
    output_dimensions: Annotated[
        tuple[PositiveInt, ...] | None,
        Field(
            description="""Supported output dimensions, if the model and provider support multiple output dimensions. If not specified, defaults to `None`."""
        ),
    ] = None
    default_dtype: Annotated[
        str | None,
        Field(
            description="""A string representing the default data type of the model, such as `float`, if the provider/model accepts different data types. If not specified, defaults to `None`."""
        ),
    ] = None
    output_dtypes: Annotated[
        tuple[str, ...] | None,
        Field(
            description="""A list of accepted values for output data types, if the model/provider allows different output data types. When available, you can use this to reduce the size of the returned vectors, at the cost of some accuracy (depending on which you choose).""",
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
            description="""The tokenizer model used by the embedding model. If the tokenizer is `tokenizers`, this should be the full name of the tokenizer or model (if it's listed by its model name), *including the organization*. Like: `voyageai/voyage-code-3`""",
        ),
    ] = None
    preferred_metrics: Annotated[
        tuple[Literal["dot", "cosine", "euclidean", "manhattan", "hamming", "chebyshev"], ...],
        Field(
            description="""A tuple of preferred metrics for comparing embeddings.""",
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
            description="""The version for the capabilities schema.""",
        ),
    ] = "1.0.0"
    hf_name: Annotated[
        str | None,
        Field(
            description="""The Hugging Face model name, if it applies *and* is different from the model name. Currently only applies to some models from `fastembed` and `ollama`"""
        ),
    ] = None
    other: Annotated[dict[str, Any], Field(description="""Extra model-specific settings.""")] = {}
    _available: Annotated[
        bool,
        Field(
            init=False,
            description="""Whether the model is currently available with the required dependencies installed. Value set when the capability is registered for builtin capabilities. It may be unset for custom capabilities.""",
        ),
    ] = False

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

    @property
    def available(self) -> bool:
        """Check if the model is available."""
        return self._available

    def _telemetry_keys(self) -> None:
        return None


from importlib.util import find_spec


HAS_FASTEMBED = find_spec("fastembed") is not None
HAS_ST = find_spec("sentence_transformers") is not None


class SparseEmbeddingModelCapabilities(BasedModel):
    """A model describing the capabilities of a sparse embedding model.

    Sparse embeddings are much simpler than dense embeddings, so this model is much simpler.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="allow",
        arbitrary_types_allowed=True,
        serialize_by_alias=True,
    )

    name: Annotated[str, Field(description="""The name of the model.""")]
    multilingual: bool = False
    provider: Annotated[
        Literal[Provider.FASTEMBED, Provider.SENTENCE_TRANSFORMERS, Provider.UNSET],  # pyright: ignore[reportPrivateUsage]
        Field(
            description="""The provider of the model. We currently only support local providers for sparse embeddings. Since Sparse embedding tend to be very efficient and low resource, they are well-suited for deployment in resource-constrained environments."""
        ),
    ] = (
        Provider.FASTEMBED
        if HAS_FASTEMBED
        else Provider.SENTENCE_TRANSFORMERS
        if HAS_ST
        else Provider.UNSET  # pyright: ignore[reportPrivateUsage]
    )
    hf_name: Annotated[
        str | None,
        Field(
            description="""The Hugging Face model name, if it applies *and* is different from the model name. Currently only applies to some models from `fastembed` and `ollama`"""
        ),
    ] = None
    other: Annotated[
        dict[str, Any],
        Field(description="""Extra model-specific settings.""", default_factory=dict),
    ]

    _available: Annotated[
        bool, Field(description="""Whether the model is available for use.""")
    ] = False

    @property
    def available(self) -> bool:
        """Check if the model is available."""
        return self._available

    def _telemetry_keys(self) -> None:
        return None


def get_sparse_caps() -> tuple[SparseEmbeddingModelCapabilities, ...]:
    """Get sparse embedding model capabilities."""
    caps = {  # type: ignore
        "Qdrant/bm25": {"name": "Qdrant/bm25", "multilingual": True},
        "Qdrant/bm42-all-minilm-l6-v2-attentions": {
            "name": "Qdrant/bm42-all-minilm-l6-v2-attentions",
            "multilingual": False,
            "other": {},
            "_available": HAS_FASTEMBED,
        },
        "prithivida/Splade-PP_en_v1": {
            "name": "prithivida/Splade-PP_en_v1",
            "multilingual": False,
            "hf_name": "Qdrant/Splade-PP_en_v1",
            "other": {},
            "_available": HAS_FASTEMBED,
        },
        "prithivida/Splade-PP_en_v2": {
            "name": "prithivida/Splade-PP_en_v2",
            "multilingual": False,
            "hf_name": None,
            "other": {},
            "_available": HAS_FASTEMBED or HAS_ST,
        },
        "ibm-granite/granite-embedding-30m-sparse": {
            "name": "ibm-granite/granite-embedding-30m-sparse",
            "multilingual": False,
            "other": {},
            "_available": HAS_ST,
        },
        "opensearch-project/opensearch-neural-sparse-encoding-doc-v2-mini": {
            "name": "opensearch-project/opensearch-neural-sparse-encoding-doc-v2-mini",
            "multilingual": False,
            "other": {},
            "_available": HAS_ST,
        },
        "opensearch-project/opensearch-neural-sparse-encoding-doc-v3-distill": {
            "name": "opensearch-project/opensearch-neural-sparse-encoding-doc-v3-distill",
            "multilingual": False,
            "other": {},
            "_available": HAS_ST,
        },
        "opensearch-project/opensearch-neural-sparse-encoding-doc-v3-gte": {
            "name": "opensearch-project/opensearch-neural-sparse-encoding-doc-v3-gte",
            "multilingual": False,
            "other": {},
            "_available": HAS_ST,
        },
    }
    fastembed_caps = tuple(
        SparseEmbeddingModelCapabilities.model_validate(cap | {"provider": Provider.FASTEMBED})
        for cap in list(caps.values())[:4]  # type: ignore
    )
    st_caps = tuple(
        SparseEmbeddingModelCapabilities.model_validate(
            cap | {"provider": Provider.SENTENCE_TRANSFORMERS}
        )
        for cap in list(caps.values())[3:]  # type: ignore
    )
    return fastembed_caps + st_caps


__all__ = (
    "EmbeddingCapabilities",
    "EmbeddingModelCapabilities",
    "PartialCapabilities",
    "SparseEmbeddingModelCapabilities",
    "get_sparse_caps",
)

"""Base types for CodeWeaver embedding models."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, NotRequired, Required, TypedDict

from pydantic import PositiveFloat, PositiveInt


if TYPE_CHECKING:
    from codeweaver.providers.provider import Provider


class EmbeddingSettingsDict(TypedDict, total=False):
    """A dictionary representing the settings for an embedding client, embedding model, and the embedding call itself. If any."""

    client_options: dict[str, Any]
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


__all__ = ("EmbeddingCapabilities", "EmbeddingSettingsDict", "PartialCapabilities")

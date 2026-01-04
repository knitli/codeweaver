"""General model options for embedding, sparse embedding, and reranking."""

from typing import Any, Literal, NotRequired, Required, TypedDict

from pydantic import PositiveInt


class EmbeddingModelSettings(TypedDict, total=False):
    """Embedding model settings. Use this class for dense (vector) models."""

    model: Required[str]
    dimension: NotRequired[PositiveInt | None]
    data_type: NotRequired[str | None]
    custom_prompt: NotRequired[str | None]
    """A custom prompt to use for the embedding model, if supported. Most models do not support custom prompts for embedding."""
    embed_options: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the *provider* **client's** (like `voyageai.async_client.AsyncClient`) `embed` method. These are different from `model_options`, which are passed to the model constructor itself."""
    model_options: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the model's constructor."""


class SparseEmbeddingModelSettings(TypedDict, total=False):
    """Sparse embedding model settings. Use this class for sparse (e.g. bag-of-words) models."""

    model: Required[str]
    embed_options: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the *provider* **client's** (like `sentence_transformers.SparseEncoder`) `embed` method. These are different from `model_options`, which are passed to the model constructor itself."""
    model_options: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the model's constructor."""
    data_type: NotRequired[Literal["float32", "float16", "int8", "binary"] | None]


class RerankingModelSettings(TypedDict, total=False):
    """Rerank model settings."""

    model: Required[str]
    custom_prompt: NotRequired[str | None]

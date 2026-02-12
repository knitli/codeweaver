# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""
This module defines configuration models for sparse embedding providers in CodeWeaver, including Sentence Transformers and FastEmbed. Each model includes provider-specific configuration options for embedding and query encoding, as well as methods to convert these configurations into the format expected by the respective provider's SDK. The base class `BaseSparseEmbeddingConfig` provides common functionality for all sparse embedding configurations, while specific classes like `SentenceTransformersSparseEmbeddingConfig` and `FastEmbedSparseEmbeddingConfig` implement provider-specific details.
"""

from __future__ import annotations

import logging

from typing import Annotated, Any, ClassVar, Literal, Self, cast

from pydantic import Field
from qdrant_client.models import Datatype, Modifier, SparseIndexParams

from codeweaver.core.constants import DEFAULT_LOCAL_EMBEDDING_BATCH_SIZE, ZERO
from codeweaver.core.types import BasedModel, ModelName, ModelNameT, Provider
from codeweaver.providers.config.sdk.embedding import (
    EmbeddingMixin,
    SentenceTransformersEncodeDict,
    SerializedEmbeddingOptionsDict,
)
from codeweaver.providers.config.sdk.vector_store import SparseVectorParams


logger = logging.getLogger(__name__)

# ============================================================================
# Sparse Embedding Configs
# ============================================================================


async def _to_sparse_vector_params(instance: BaseSparseEmbeddingConfig) -> SparseVectorParams:
    """Convert a sparse embedding config to SparseVectorParams."""
    datatype = await instance.get_datatype()
    logger.debug(
        "Found set datatype '%s' for sparse embedding config with model name '%s'",
        datatype,
        instance.model_name,
    )
    logger.debug("Setting params datatype to float for Qdrant; will quantize in database.")
    index_params = SparseIndexParams(datatype=Datatype("float32"))
    modifier = Modifier.IDF if ("bm25" in str(instance.model_name).lower()) else Modifier.NONE
    return SparseVectorParams(index=index_params, modifier=modifier)


class BaseSparseEmbeddingConfig(BasedModel, EmbeddingMixin):
    """Base configuration for sparse embedding models."""

    provider: Provider | None = Field(
        None,
        description="The provider for this embedding configuration. You don't have to provide this value -- while provider is a required setting at the top-level EmbeddingProviderSettings object, we will inject that value into the embedding configuration for you, so you can just specify the provider-specific config without worrying about the provider field in most cases.",
    )

    model_name: ModelNameT | None = Field(
        default_factory=ModelName,
        description="The name of the embedding model to use. This should be in the format used by the provider (e.g., for Bedrock, this would be the model ARN). Like with `provider`, we can inject that value into the embedding configuration for you, so you can just specify the model-specific config without worrying about the model_name field in most cases.",
    )

    embedding: Annotated[
        dict[str, Any] | None,
        Field(
            description="Parameters for document embedding requests. The specific parameters that can be included here depend on the provider and model you're using. Subclasses should implement a TypedDict for these parameters."
        ),
    ] = None

    query: Annotated[
        dict[str, Any] | None,
        Field(
            description="Parameters for query embedding requests. Often the same as the embedding parameters, but some providers/models allow for different parameters for query vs document embeddings, so this is a separate field. If the types for embedding and query are the same, and you only provide one of them, we'll copy the values over to the other one for you."
        ),
    ] = None

    _is_sparse: ClassVar[bool] = True

    def set_dimension(self, dimension: int) -> Self:
        """No op for sparse embeddings."""
        if self._dimension is None:
            object.__setattr__(self, "_dimension", ZERO)
        return self


def _st_options_factory() -> SentenceTransformersEncodeDict:
    """Factory function to create default options for Sentence Transformers encoding."""
    return SentenceTransformersEncodeDict(
        batch_size=DEFAULT_LOCAL_EMBEDDING_BATCH_SIZE, show_progress_bar=False
    )


class SentenceTransformersSparseEmbeddingConfig(BaseSparseEmbeddingConfig):
    """Configuration options for Sentence Transformers sparse embedding models."""

    _is_sparse: ClassVar[bool] = True

    provider: Literal[Provider.SENTENCE_TRANSFORMERS] = Provider.SENTENCE_TRANSFORMERS

    embedding: SentenceTransformersEncodeDict = Field(
        default_factory=_st_options_factory, description="Parameters for document/corpus encoding."
    )
    """Parameters for document/corpus encoding."""

    query: SentenceTransformersEncodeDict = Field(
        default_factory=_st_options_factory,
        description="Parameters for query encoding (if different from document).",
    )
    """Parameters for query encoding (if different from document)."""

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the Sentence Transformers configuration to a dictionary of options."""
        return SerializedEmbeddingOptionsDict(
            model_name=ModelName(self.model_name),
            embedding=cast(dict[str, Any], self.embedding or {}),
            query=cast(dict[str, Any], self.query or {}),
            model={},
        )

    def set_dimension(self, dimension: int) -> Self:
        """No op for sparse embeddings since dimension is determined by the tokenizer and not fixed. Return self for chaining."""
        object.__setattr__(self, "_dimension", ZERO)
        return self

    def set_datatype(self, datatype: str) -> Self:
        """Set the embedding datatype explicitly in the embedding configuration.

        Args:
            datatype: The datatype to set.
        """
        object.__setattr__(self, "_datatype", datatype)
        self.embedding = self.embedding or SentenceTransformersEncodeDict(
            **self._defaults["embedding"]
        )
        if "float" in datatype:
            resolved_datatype = "float32"
        elif "int" in datatype:
            resolved_datatype = "uint8"
        else:
            resolved_datatype = "ubinary"
        self.embedding["precision"] = cast(
            Literal["float32", "uint8", "ubinary"], resolved_datatype
        )
        self.query = self.query or SentenceTransformersEncodeDict(**self._defaults["query"])
        self.query["precision"] = datatype  # ty:ignore[invalid-assignment]
        return self

    def _get_dimension(self) -> Literal[0]:
        """No op for sparse embeddings since dimension is determined by the tokenizer and not fixed. Return 0 as a placeholder."""
        return ZERO  # ty:ignore[invalid-return-type]

    def _get_datatype(self) -> str:
        """Get explicitly configured datatype without fallbacks.
        Optional field for subclasses to implement as a helper for get_datatype.

        Returns:
            Explicitly configured datatype or None
        """
        if self.embedding and (precision := self.embedding.get("precision")):
            return precision
        return "float16"

    @property
    def _defaults(self) -> dict[str, Any]:
        """Return default values for the configuration."""
        return {
            "embedding": {
                "normalize_embeddings": True,
                "convert_to_numpy": True,
                "batch_size": DEFAULT_LOCAL_EMBEDDING_BATCH_SIZE,
                "show_progress_bar": False,
            },
            "query": {
                "normalize_embeddings": True,
                "convert_to_numpy": True,
                "batch_size": DEFAULT_LOCAL_EMBEDDING_BATCH_SIZE,
                "show_progress_bar": False,
            },
        }

    async def as_sparse_vector_params(self) -> SparseVectorParams:
        """Get Qdrant SparseVectorParams for this sparse embedding configuration."""
        return await _to_sparse_vector_params(self)


class FastEmbedSparseEmbeddingConfig(BaseSparseEmbeddingConfig):
    """Configuration options for FastEmbed sparse embedding models.

    Inherits all configuration from FastEmbedEmbeddingConfig.
    """

    _is_sparse: ClassVar[bool] = True

    provider: Literal[Provider.FASTEMBED] = Provider.FASTEMBED

    embedding: dict[str, Any] = Field(
        default_factory=dict, description="Parameters for document embedding requests."
    )
    """Parameters for document embedding requests."""

    query: dict[str, Any] = Field(
        default_factory=dict, description="Parameters for query embedding requests."
    )
    """Parameters for query embedding requests."""

    async def as_sparse_vector_params(self) -> SparseVectorParams:
        """Get Qdrant SparseVectorParams for this sparse embedding configuration."""
        return await _to_sparse_vector_params(self)

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the FastEmbed embedding configuration to a dictionary of options."""
        return SerializedEmbeddingOptionsDict(
            model_name=ModelName(self.model_name),
            embedding=self.embedding or {},
            query=self.query or {},
            model={},
        )

    def set_dimension(self, dimension: int) -> Self:
        """Set the embedding dimension explicitly in the embedding configuration.

        Args:
            dimension: The dimension to set.
        """
        object.__setattr__(self, "_dimension", ZERO)
        return self

    def set_datatype(self, datatype: str) -> Self:
        """Set the embedding datatype explicitly in the embedding configuration.

        Args:
            datatype: The datatype to set.
        """
        object.__setattr__(self, "_datatype", datatype)
        return self

    @classmethod
    def _defaults(cls) -> dict[str, Any]:
        """Return default values for the configuration."""
        return {}


# ============================================================================
# Discriminator Type Unions
# ============================================================================

SparseEmbeddingConfigT = Annotated[
    SentenceTransformersSparseEmbeddingConfig | FastEmbedSparseEmbeddingConfig,
    Field(description="All sparse embedding config classes."),
]


__all__ = (
    "BaseSparseEmbeddingConfig",
    "FastEmbedSparseEmbeddingConfig",
    "SentenceTransformersSparseEmbeddingConfig",
    "SparseEmbeddingConfigT",
)

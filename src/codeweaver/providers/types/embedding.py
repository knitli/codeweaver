# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: no-complex-if-expressions
"""Embedding-related types and classes for provider systems."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, NamedTuple, Self

from pydantic import PositiveInt
from qdrant_client.http.models import Datatype
from qdrant_client.models import (
    CollectionParams,
    Modifier,
    ScalarQuantization,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)

from codeweaver.core.constants import PRIMARY_SPARSE_VECTOR_NAME, PRIMARY_VECTOR_NAME
from codeweaver.core.exceptions import InvalidEmbeddingModelError
from codeweaver.core.types import ModelName, ModelNameT
from codeweaver.providers.config.provider_kinds import AsymmetricEmbeddingProviderSettings
from codeweaver.providers.config.provider_kinds import (
    EmbeddingProviderSettings,
    SparseEmbeddingProviderSettings,
)
from codeweaver.providers.embedding.capabilities.base import (
    EmbeddingModelCapabilities,
    SparseEmbeddingModelCapabilities,
)


class ConfiguredCapability(NamedTuple):
    """Contains a capability and its associated configuration.

    Note: user-defined capabilities may not have a capabilities object, but hopefully they define one :). If they don't we have to assume conservative defaults.

    For asymmetric embedding configurations, the config field may be an AsymmetricEmbeddingProviderSettings,
    which contains both embed_provider and query_provider settings.
    """

    capability: EmbeddingModelCapabilities | SparseEmbeddingModelCapabilities | None

    config: (
        EmbeddingProviderSettings
        | SparseEmbeddingProviderSettings
        | AsymmetricEmbeddingProviderSettings
    )

    @property
    def model_name(self) -> ModelNameT:
        """Get the model name associated with this capability."""
        # Get the embedding config - use sparse_embedding_config for sparse providers
        embedding_config = (
            self.config.sparse_embedding_config
            if isinstance(self.config, SparseEmbeddingProviderSettings)
            else self.config.embedding_config
        )
        return ModelName(
            self.config.model_name or embedding_config.model_name or self.capability.name
        )

    async def datatype(self) -> str | None:
        """Get the data type of the embedding vectors for this capability."""
        # Get the embedding config - use sparse_embedding_config for sparse providers
        embedding_config = (
            self.config.sparse_embedding_config
            if isinstance(self.config, SparseEmbeddingProviderSettings)
            else self.config.embedding_config
        )
        return await embedding_config.get_datatype()

    async def distance(self) -> Literal["Cosine", "Dot", "Euclidean", "Manhattan"] | None:
        """Get the preferred distance metric for this capability."""
        if self.is_sparse or self.is_idf:
            return None
        if self.capability:
            return next(
                (
                    metric
                    for metric in self.capability.preferred_metrics
                    if metric.lower() in ("cosine", "dot", "euclidean", "manhattan")
                ),
                "Cosine",
            )
        return "Cosine"

    async def dimension(self) -> PositiveInt | None:
        """Get the dimensionality of the embedding vectors for this capability."""
        if isinstance(self.capability, SparseEmbeddingModelCapabilities) or isinstance(
            self.config, SparseEmbeddingProviderSettings
        ):
            return None
        default_dimension = self.capability.default_dimension if self.capability else None
        # Get the embedding config - use sparse_embedding_config for sparse providers
        embedding_config = (
            self.config.sparse_embedding_config
            if isinstance(self.config, SparseEmbeddingProviderSettings)
            else self.config.embedding_config
        )
        configured_dimension = await embedding_config.get_dimension() or default_dimension
        allowed_values = (
            self.capability.output_dimensions
            if self.capability and self.capability.output_dimensions
            else (
                [self.capability.default_dimension]
                if self.capability and self.capability.default_dimension
                else [configured_dimension]
            )
        )
        if not configured_dimension and not allowed_values:
            raise InvalidEmbeddingModelError(
                "Invalid embedding model configuration. We weren't able to determine a valid embedding dimension for what looks like a dense embedding model. Please either explicitly provide a dimension in your embedding config, or preferably, provide an EmbeddingModelCapabilities instance/configuration."
            )
        if allowed_values and (max_value := max(allowed_values)):
            configured_dimension = min(max_value, configured_dimension or max_value)
        if allowed_values and configured_dimension not in allowed_values:
            # align to the closest allowed value
            closest_value = min(allowed_values, key=lambda x: abs(x - configured_dimension))
            configured_dimension = closest_value
        return configured_dimension

    @property
    def is_dense(self) -> bool:
        """Check if this capability represents a dense embedding model."""
        return self.capability is not None and not isinstance(
            self.capability, SparseEmbeddingModelCapabilities
        )

    @property
    def is_sparse(self) -> bool:
        """Check if this capability represents a sparse embedding model."""
        return self.capability is not None and isinstance(
            self.capability, SparseEmbeddingModelCapabilities
        )

    @property
    def is_idf(self) -> bool:
        """Check if this capability represents an IDF (BM25) embedding model."""
        return (
            self.is_sparse
            and self.capability is not None
            and "bm25" in str(self.capability.name).lower()
            if self.capability is not None
            else False
        )


class EmbeddingCapabilityGroup(NamedTuple):
    """A group of embedding model capabilities for use with vector search. The goal here is to define a group of models that can be used for different types of vector search based on needs and assessed intent/strategy.

    Currently, we only use it to define sparse and dense providers (or IDF in lieu of sparse if configured), but the overall plan is to take a multivector, tailored, approach to each search based on needs. Right now it's just simple RRF (reciprocal rank fusion) between sparse and dense vectors or idf and dense vectors (which is still more robust than essentially every other code search tool out there...).
    """

    dense: ConfiguredCapability | None = None
    """Configured dense embedding model capabilities. Dense models are what you think of when you think of 'vector embeddings' or 'vector search'. CodeWeaver employs a range of different kinds of models but the core strength of semantic search comes from dense models. You can technically run CodeWeaver without a dense model, but I'm not sure why you would want to."""

    sparse: ConfiguredCapability | None = None
    """Configured sparse embedding model capabilities that **are not** generic idf type indexes. These are models like Splade.

    True sparse models, also known as "bag-of-words" models, are typically derived from dense models, and in most cases create sparse vectors *from* dense vectors. This has the advantage of adding *some* semantic meaning to the results, so long as it's within the model's set vocabulary. Sparse models are actually *slower* to generate embeddings than equivalent dense models, but once they are generated, are significantly faster at inference (i.e. search) [^1]. So you trade time up front for efficiency when searching. Data show combining sparse and dense models improves search result accuracy in nearly every case, often by 15% or more.

    CodeWeaver defaults to hybrid search using dense *and* sparse models.

    [^1]: While sparse models are slower to generate embeddings than equivalent dense models, they unfortunately are not widely supported by cloud inference providers. So unlike dense models, we need to run these models locally at the expense of latent processing capacity, which slows things down more. The only cloud provider we could find that offers sparse models is `Qdrant Cloud`; we hope to add support soon.
    """

    idf: ConfiguredCapability | None = None
    """From a capabilities perspective, we treat IDF, like BM-25, as a type of sparse embedding. But it's not really a model at all and requires different handling within vector operations.

    The main advantage of IDF is that it can be extremely fast and low resource, but it lacks semantic capabilities (i.e. meaning). This is your traditional "keyword search." It shines when you know exactly what you are looking for by name. IDF can be combined with both sparse and dense models to increase result confidence or narrow-in on results.
    """

    late_interaction: None = None
    """CodeWeaver doesn't currently implement late_interaction model (i.e. colBERT) handling, but we hope to soon. This is a placeholder for when that happens."""

    @classmethod
    def from_capabilities(cls, capabilities: Sequence[ConfiguredCapability]) -> Self:
        """Creates an EmbeddingCapabilityGroup from a sequence of model capabilities."""
        values = dict.fromkeys(("dense", "sparse", "idf", "late_interaction"))

        for capability in capabilities:
            config = capability.config
            if (
                isinstance(config, SparseEmbeddingProviderSettings)
                and (model_name := config.model_name or config.sparse_embedding_config.model_name)
                and any(
                    n
                    for n in ("bm25", "idf", "inverse")
                    if n in str(model_name).lower().replace("-", "")
                )
            ):
                values["idf"] = values["idf"] or capability
            elif isinstance(config, SparseEmbeddingProviderSettings):
                values["sparse"] = values["sparse"] or capability
            else:
                values["dense"] = values["dense"] or capability
        return cls(**values)

    @property
    def dense_model(self) -> ModelNameT | None:
        """Get the name of the dense embedding model."""
        return self.dense.model_name

    @property
    def sparse_model(self) -> ModelNameT | None:
        """Get the name of the sparse embedding model."""
        return self.sparse.model_name if self.sparse else None

    @property
    def idf_model(self) -> ModelNameT | None:
        """Get the name of the IDF embedding model."""
        return self.idf.model_name if self.idf else None

    async def as_vector_params(self) -> CollectionParams:
        """Convert the embedding capability group to Qdrant collection parameters.

        Uses role-based vector names: "primary" for dense, "sparse" for sparse/idf.
        """
        from qdrant_client.models import Distance

        params: dict[str, Any] = {}
        if self.dense:
            if not (size := await self.dense.dimension()) and size != 0:
                raise InvalidEmbeddingModelError(
                    "Cannot create vector params: dense embedding model dimension is not configured."
                )
            datatype = await self.dense.datatype()
            distance_metric_name = await self.dense.distance()

            # Create proper VectorParams object
            params["vectors"] = {
                PRIMARY_VECTOR_NAME: VectorParams(  # Changed from "dense" to "primary" (role-based architecture)
                    size=size,
                    distance=Distance(distance_metric_name.title())
                    if isinstance(distance_metric_name, str)
                    else distance_metric_name or Distance("Cosine"),
                    on_disk=None,
                    quantization_config=ScalarQuantization.model_construct(scalar={"type": "uint8"})
                    if datatype == "uint8"
                    else None,
                    datatype=Datatype(datatype) if datatype else Datatype.FLOAT16,
                )
            }
        if self.sparse:
            datatype = await self.sparse.datatype()
            params["sparse_vectors"] = {
                PRIMARY_SPARSE_VECTOR_NAME: SparseVectorParams.model_construct(
                    index=SparseIndexParams.model_construct(
                        datatype=Datatype(datatype) if datatype else Datatype.FLOAT16
                    ),
                    modifier=None,
                )
            }
        if self.idf:
            datatype = await self.idf.datatype()
            params["sparse_vectors"] = {
                "idf": SparseVectorParams(index=None, modifier=Modifier.IDF)
            }

        return CollectionParams.model_construct(**params)


__all__ = ("ConfiguredCapability", "EmbeddingCapabilityGroup")

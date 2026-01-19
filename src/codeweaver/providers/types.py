# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Shared types and base classes for provider systems."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from functools import cache
from threading import Lock
from types import MappingProxyType
from typing import NamedTuple

from pydantic import PositiveInt

from codeweaver.core import BaseEnum, InvalidEmbeddingModelError, ModelName, ModelNameT
from codeweaver.providers.config import EmbeddingProviderSettings, SparseEmbeddingProviderSettings
from codeweaver.providers.embedding.capabilities.base import (
    EmbeddingModelCapabilities,
    SparseEmbeddingModelCapabilities,
)
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities


type EmbeddingCapabilityType = EmbeddingModelCapabilities | SparseEmbeddingModelCapabilities
type RerankingCapabilityType = RerankingModelCapabilities


class CircuitBreakerState(BaseEnum):
    """Circuit breaker states for provider resilience."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class BaseCapabilityResolver[Capability: (EmbeddingCapabilityType | RerankingCapabilityType)](ABC):
    """Base class for capability resolvers.

    Provides a generic pattern for lazy-loading and resolving model capabilities
    by name. Subclasses must implement `_ensure_loaded()` to populate the
    capabilities registry.

    Type parameter Capability should be the capability model type (e.g., EmbeddingModelCapabilities).
    """

    def __init__(self) -> None:
        """Initialize the capability resolver with empty cache."""
        self._lock = Lock()
        self._capabilities_by_name: MappingProxyType[str, Capability] = MappingProxyType({})
        self._loaded = False

    @abstractmethod
    def _ensure_loaded(self) -> None:
        """Load all capabilities into the registry.

        Subclasses must implement this to:
        1. Import all capability getter functions
        2. Call each getter and populate self._capabilities_by_name
        3. Set self._loaded = True

        This method should be idempotent - calling multiple times should be safe.
        """
        ...

    def resolve(self, model_name: str) -> Capability | None:
        """Get capabilities for a specific model name.

        Args:
            model_name: The name of the model.

        Returns:
            The capabilities for the specified model, or None if not found.
        """
        with self._lock:
            self._ensure_loaded()
        return self._capabilities_by_name.get(model_name)

    def all_capabilities(self) -> Sequence[Capability]:
        """Get all registered model capabilities.

        Returns:
            A sequence of all registered capabilities.
        """
        with self._lock:
            self._ensure_loaded()
        return tuple(self._capabilities_by_name.values())

    def all_model_names(self) -> Sequence[str]:
        """Get all registered model names.

        Returns:
            A sequence of all registered model names.
        """
        with self._lock:
            self._ensure_loaded()
        return tuple(self._capabilities_by_name.keys())


class BaseRerankingCapabilityResolver(BaseCapabilityResolver[RerankingCapabilityType]):
    """A capability resolver for reranking models."""


class BaseEmbeddingCapabilityResolver(BaseCapabilityResolver[EmbeddingModelCapabilities]):
    """A capability resolver for embedding models."""


class BaseSparseEmbeddingCapabilityResolver(
    BaseCapabilityResolver[SparseEmbeddingModelCapabilities]
):
    """A capability resolver for sparse embedding models."""


@cache
def get_all_provider_types() -> tuple[type, ...]:
    """Get all defined provider types.

    Returns:
        A tuple of all provider type classes.
    """
    import textcase

    import codeweaver.providers.config

    cls_names = [
        cls_name
        for cls_name in codeweaver.providers.config.__all__
        if textcase.pascal.match(cls_name)
        and not cls_name.startswith("Base")
        and not cls_name.endswith(("T", "Type"))
        and any(
            name
            for name in ("Client", "Embedding", "Reranking", "Settings", "Qdrant", "VectorStore")
            if name in cls_name
        )
    ]
    return tuple(getattr(codeweaver.providers.config, cls_name) for cls_name in cls_names)


class ConfiguredCapability(NamedTuple):
    """Contains a capability and its associated configuration.

    Note: user-defined capabilities may not have a capabilities object, but hopefully they define one :). If they don't we have to assume conservative defaults.
    """

    capability: EmbeddingModelCapabilities | SparseEmbeddingModelCapabilities | None

    config: EmbeddingProviderSettings | SparseEmbeddingProviderSettings

    @property
    def model_name(self) -> ModelNameT:
        return ModelName(
            self.config.model_name
            or self.config.embedding_config.model_name
            or self.capability.name
        )

    async def datatype(self) -> str | None:
        return await self.config.embedding_config.get_datatype()

    async def dimension(self) -> PositiveInt | None:
        if isinstance(self.capability, SparseEmbeddingModelCapabilities) or isinstance(
            self.config, SparseEmbeddingProviderSettings
        ):
            return None
        default_dimension = self.capability.default_dimension if self.capability else None
        configured_dimension = (
            await self.config.embedding_config.get_dimension() or default_dimension
        )
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


class EmbeddingCapabilityGroup(NamedTuple):
    """A group of embedding model capabilities for use with vector search. The goal here is to define a group of models that can be used for different types of vector search based on needs and assessed intent/strategy.

    Currently, we only use it to define sparse and dense providers (or IDF in lieu of sparse if configured), but the overall plan is to take a multivector, tailored, approach to each search based on needs. Right now it's just simple RRF (reciprocal rank fusion) between sparse and dense vectors or idf and dense vectors (which is still more robust than essentially every other code search tool out there...).
    """

    dense: ConfiguredCapability | None = None
    """Configured dense embedding model capabilities. Dense models are what you think of when you think of 'vector embeddings' or 'vector search'. CodeWeaver employs a range of different kinds of models but the core strength of semantic search comes from dense models. You can technically run CodeWeaver without a dense model, but I'm not sure why you would want to."""

    sparse: ConfiguredCapability | None = None
    """Configured sparse embedding model capabilities that **are not** generic idf type indexes. These are models like Splade.

    True sparse models, also known as "bag-of-words" models, are typically derived from dense models, and in most cases create sparse vectors *from* dense vectors. This has the advantage of adding *some* semantic meaning to the results, so long as it's within the model's set vocabulary. Sparse models are actually *slower* to generate embeddings than dense models, but once they are generated, are significantly faster at inference (i.e. search) [^1]. So you trade time up front for efficiency when searching. Data show combining sparse and dense models improves search result accuracy in nearly every case, often by 15% or more.

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
    def from_capabilities(cls, capabilities: Sequence[ConfiguredCapability]):
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

    @property
    def dense_model(self) -> ModelNameT | None:
        """Get the name of the dense embedding model."""
        return self.dense.model_name

    @property
    def sparse_model(self) -> ModelNameT | None:
        """Get the name of the sparse embedding model."""
        return self.sparse.model_name
    @property
    def idf_model(self) -> ModelNameT | None:
        """Get the name of the IDF embedding model."""
        return self.idf.model_name if self.idf else None


__all__ = (
    "BaseEmbeddingCapabilityResolver",
    "BaseRerankingCapabilityResolver",
    "BaseSparseEmbeddingCapabilityResolver",
    "CircuitBreakerState",
    "EmbeddingCapabilityGroup",
)

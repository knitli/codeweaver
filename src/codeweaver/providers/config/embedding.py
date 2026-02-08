# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Provider-specific embedding configuration models and utilities."""

from __future__ import annotations

import importlib
import logging

from abc import abstractmethod
from collections.abc import Hashable
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Literal,
    NotRequired,
    Required,
    Self,
    TypedDict,
    cast,
    overload,
    override,
)

from pydantic import Discriminator, Field, PositiveInt, PrivateAttr, Tag, computed_field
from qdrant_client.models import (
    Datatype,
    Distance,
    Modifier,
    ScalarQuantization,
    ScalarType,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)

from codeweaver.core import (
    BasedModel,
    ConfigurationError,
    ModelName,
    ModelNameT,
    Provider,
    ProviderLiteralString,
)
from codeweaver.core.constants import (
    DATATYPE_FIELDS,
    DEFAULT_EMBEDDING_TIMEOUT,
    DEFAULT_LOCAL_EMBEDDING_BATCH_SIZE,
    DIMENSION_FIELDS,
)
from codeweaver.core.utils import deep_merge_dicts
from codeweaver.providers.config.types import CohereRequestOptionsDict


logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from codeweaver.providers.embedding.capabilities.base import (
        EmbeddingModelCapabilities,
        SparseEmbeddingModelCapabilities,
    )

INCOMPATIBLE_FIELDS = {"prompt_name", "prompt", "task"}
"""Fields that cannot be shared between query and embedding configs even if the types are the same."""


@overload
def _get_embedding_capabilities_for_model(
    model_name: ModelNameT, *, sparse: Literal[True]
) -> SparseEmbeddingModelCapabilities | None: ...
@overload
def _get_embedding_capabilities_for_model(
    model_name: ModelNameT, *, sparse: Literal[False] = False
) -> EmbeddingModelCapabilities | None: ...
def _get_embedding_capabilities_for_model(
    model_name: ModelNameT, *, sparse: bool = False
) -> EmbeddingModelCapabilities | SparseEmbeddingModelCapabilities | None:
    """Get the embedding model capabilities for a given model name.

    Args:
        model_name: The name of the embedding model.
        sparse: Whether to get sparse embedding capabilities.

    Returns:
        The embedding model capabilities or None if not found.
    """
    resolver_module = importlib.import_module(
        "codeweaver.providers.embedding.capabilities.resolver"
    )
    if sparse:
        resolver = getattr(resolver_module, "SparseEmbeddingCapabilityResolver", None)
    else:
        resolver = getattr(resolver_module, "EmbeddingCapabilityResolver", None)
    return None if resolver is None else resolver().resolve(model_name)


class SerializedEmbeddingOptionsDict(TypedDict, total=False):
    """A dictionary representing serialized embedding options for different providers."""

    model_name: Required[ModelNameT]
    """The name of the embedding model in the format used by the provider."""

    embedding: NotRequired[dict[str, Any]]

    model: NotRequired[dict[str, Any]]

    query: NotRequired[dict[str, Any]]


class BaseEmbeddingConfig(BasedModel):
    """Base configuration for embedding models."""

    _is_sparse: ClassVar[bool] = False
    _dimension: int | None = PrivateAttr(default=None)
    _datatype: str | None = PrivateAttr(default=None)

    tag: ProviderLiteralString = Field(
        ...,
        description="The provider tag for the embedding model. Used for discriminated unions.",
        exclude=True,
    )

    provider: Provider = Field(
        ...,
        description="The provider for this embedding configuration. Used for discriminated unions.",
    )

    model_name: ModelNameT
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

    model: Annotated[
        dict[str, Any] | None,
        Field(
            description="Parameters for model-level configuration (separate from embedding/query options)."
        ),
    ] = None

    def __init__(self, **data: Any) -> None:
        """Initialize the embedding configuration."""
        embedding = data.get("embedding")
        query = data.get("query")
        if (
            (embedding and not query) or (query and not embedding)
        ) and self._query_and_embedding_same_type():
            # if only one of embedding or query is provided, and they are the same type, copy it over, with caveats
            no_copy_keys = {"prompt", "prompt_name", "task"}
            if embedding:
                data["query"] = {k: v for k, v in embedding.copy().items() if k not in no_copy_keys}
            elif query:
                data["embedding"] = {k: v for k, v in query.copy().items() if k not in no_copy_keys}
        if not embedding:
            data["embedding"] = {}
        if not query:
            data["query"] = {}
        if "model" not in data or not data.get("model"):
            data["model"] = {}
        object.__setattr__(self, "_is_sparse", data.pop("_is_sparse", False))
        super().__init__(**data)
        from codeweaver.core.di import get_container

        try:
            container = get_container()
            container.register(type(self), lambda: self)
        except Exception as e:
            # Log if DI not available (monorepo compatibility)
            logger.debug(
                "Dependency injection container not available, skipping registration of EmbeddingConfig: %s",
                e,
            )

    @abstractmethod
    def set_dimension(self, dimension: int) -> Self:
        """Set the embedding dimension explicitly in the embedding configuration.

        Args:
            dimension: The dimension to set.
        """
        raise NotImplementedError("Subclasses must implement set_dimension method.")

    @abstractmethod
    def set_datatype(self, datatype: str) -> Self:
        """Set the embedding datatype explicitly in the embedding configuration."""
        raise NotImplementedError("Subclasses must implement set_datatype method.")

    @staticmethod
    def _filter_and_merge(
        first_dict: dict[str, Any], second_dict: dict[str, Any]
    ) -> dict[str, Any]:
        """Filter out incompatible fields and merge two dictionaries."""
        filtered_second = {k: v for k, v in second_dict.items() if k not in INCOMPATIBLE_FIELDS}
        return cast(
            dict[str, Any],
            deep_merge_dicts(
                cast(dict[Hashable, Any], first_dict), cast(dict[Hashable, Any], filtered_second)
            ),
        )

    def mirror_settings(self, **updates: Any) -> Self:
        """If the types for embedding and query are the same, mirrors settings between them with deep merge. If updates are provided, overrides resolved settings with the updates."""
        if self._query_and_embedding_same_type():
            new_embedding = self._filter_and_merge(self.embedding or {}, self.query or {})
            new_embedding = self._filter_and_merge(new_embedding, updates or {})
            return self.model_copy(update={"embedding": new_embedding, "query": new_embedding})
        if all(
            k
            for k in updates
            if k in {k for k in (self.embedding or {}) if k not in INCOMPATIBLE_FIELDS}
        ):
            new_embedding = self._filter_and_merge(self.embedding or {}, updates or {})
            return self.model_copy(update={"embedding": new_embedding})
        if all(
            k
            for k in updates
            if k in {k for k in (self.query or {}) if k not in INCOMPATIBLE_FIELDS}
        ):
            new_query = self._filter_and_merge(self.query or {}, updates or {})
            return self.model_copy(update={"query": new_query})
        logger.warning(
            "Could not mirror settings between embedding and query configs; they are of different types and we can't tell where to apply them."
        )
        return self

    def _get_dimension(self) -> int | None:
        """Get explicitly configured dimension without fallbacks.
        Optional field for subclasses to implement as a helper for get_dimension.

        Returns:
            Explicitly configured dimension or None
        """
        return

    def _get_datatype(self) -> str | None:
        """Get explicitly configured datatype without fallbacks.
        Optional field for subclasses to implement as a helper for get_datatype.

        Returns:
            Explicitly configured datatype or None
        """
        return

    def get_dimension_sync(self) -> int | Literal[0] | None:
        """Synchronous version of get_dimension() for backward compatibility.

        Note: This does not perform full resolution like the async version.
        For full resolution, use get_dimension() directly.

        Returns:
            Resolved dimension or None
        """
        if self._dimension:
            return self._dimension
        if type(self)._is_sparse:
            object.__setattr__(self, "_dimension", 0)
            return 0
        if dimension := self._get_dimension():
            object.__setattr__(self, "_dimension", dimension)
            return dimension
        # 1. Explicit config
        for field in ("embedding", "query"):
            if (
                (config := getattr(self, field, None))
                and (found_field := next((f for f in DIMENSION_FIELDS if f in config), None))
                and isinstance(config[found_field], int)
            ):
                object.__setattr__(self, "_dimension", config[found_field])
                return config[found_field]
        if cap := self.capabilities:
            if dim := getattr(cap, "default_dimension", None):
                object.__setattr__(self, "_dimension", dim)
                return dim
            if cap.output_dimensions:
                object.__setattr__(self, "_dimension", cap.output_dimensions[0])
                return cap.output_dimensions[0]
        raise ConfigurationError(
            "Could not resolve embedding dimension from config, capabilities, or registered defaults. You need to specify it explicitly, for best results, register an `EmbeddingModelCapabilities` subclass with the capability resolver."
        )

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
        if self._dimension:
            return self._dimension
        if type(self)._is_sparse:
            object.__setattr__(self, "_dimension", 0)
            return 0
        if dimension := self._get_dimension():
            object.__setattr__(self, "_dimension", dimension)
            return dimension
        # 1. Explicit config
        for field in ("embedding", "query"):
            if (
                (config := getattr(self, field, None))
                and (found_field := next((f for f in DIMENSION_FIELDS if f in config), None))
                and isinstance(config[found_field], int)
            ):
                object.__setattr__(self, "_dimension", config[found_field])
                return config[found_field]

        # 2. Model capabilities
        if (caps := self.capabilities) and (dim := getattr(caps, "default_dimension", None)):
            object.__setattr__(self, "_dimension", dim)
            return dim

        raise ConfigurationError(
            "Could not resolve embedding dimension from config, capabilities, or registered defaults. You need to specify it explicitly, for best results, register an `EmbeddingModelCapabilities` subclass with the capability resolver."
        )

    async def get_datatype(self) -> str:
        """Get resolved datatype through fallback chain.

        Resolution order:
        1. Explicit config
        2. Model capabilities
        3. Provider-specific defaults

        Returns:
            Resolved datatype or None
        """
        if self._datatype:
            return self._datatype
        if datatype := self._get_datatype():
            object.__setattr__(self, "_datatype", datatype)
            return datatype
        # 1. Explicit config
        for field in ("embedding", "query", "model"):
            if (config := getattr(self, field, None)) and (
                found_field := next((f for f in DATATYPE_FIELDS if f in config), None)
            ):
                object.__setattr__(self, "_datatype", config[found_field])
                return config[found_field]

        # 2. Model capabilities
        if (caps := self.capabilities) and (dtype := getattr(caps, "default_datatype", None)):
            object.__setattr__(self, "_datatype", dtype)
            return dtype

        # 3. Provider-specific defaults
        if output_default := next(
            (f for f in DATATYPE_FIELDS if f in self._defaults.get("embedding", {})), None
        ):
            object.__setattr__(
                self, "_datatype", self._defaults.get("embedding", {}).get(output_default)
            )
            return self._defaults.get("embedding", {}).get(output_default)
        object.__setattr__(self, "_datatype", "float16")
        return "float16"

    def get_datatype_sync(self) -> str:
        """Synchronous version of get_datatype() for backward compatibility.

        Note: This does not perform full resolution like the async version.
        For full resolution, use get_datatype() directly.

        Returns:
            Resolved datatype
        """
        if self._datatype:
            return self._datatype
        if datatype := self._get_datatype():
            object.__setattr__(self, "_datatype", datatype)
            return datatype
        # 1. Explicit config
        for field in ("embedding", "query", "model"):
            if (config := getattr(self, field, None)) and (
                found_field := next((f for f in DATATYPE_FIELDS if f in config), None)
            ):
                object.__setattr__(self, "_datatype", config[found_field])
                return config[found_field]

        # 2. Model capabilities
        if (caps := self.capabilities) and (dtype := getattr(caps, "default_datatype", None)):
            object.__setattr__(self, "_datatype", dtype)
            return dtype

        # 3. Provider-specific defaults
        if output_default := next(
            (f for f in DATATYPE_FIELDS if f in self._defaults.get("embedding", {})), None
        ):
            object.__setattr__(
                self, "_datatype", self._defaults.get("embedding", {}).get(output_default)
            )
            return self._defaults.get("embedding", {}).get(output_default)
        object.__setattr__(self, "_datatype", "float16")
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

    async def as_vector_params(self) -> VectorParams:
        """Get Qdrant VectorParams for this embedding configuration.

        Returns:
            VectorParams instance with dimension and datatype set.
        """
        dimension = await self.get_dimension()
        datatype = await self.get_datatype()
        if datatype and datatype not in ("float32", "float16", "uint8"):
            datatype = "float16" if "float" in datatype else "uint8"
        distance_metrics = (
            self.capabilities.preferred_metrics
            if self.capabilities and self.capabilities.preferred_metrics
            else []
        )
        metric = next(
            (m for m in distance_metrics if m in ("cosine", "dot", "euclidean", "manhattan")), None
        )
        quantization = (
            None
            if not datatype or "float" in datatype
            else ScalarQuantization.model_validate({"scalar": {"type": ScalarType.INT8}})
        )
        return VectorParams(
            size=dimension,
            distance=Distance((metric or "cosine").title()),
            datatype=Datatype(datatype or "float16") if datatype else None,
            quantization_config=quantization,
        )

    @property
    def capabilities(self) -> EmbeddingModelCapabilities | SparseEmbeddingModelCapabilities | None:
        """Get the embedding model capabilities for this configuration."""
        return _get_embedding_capabilities_for_model(self.model_name, sparse=type(self)._is_sparse)

    @classmethod
    def _query_and_embedding_same_type(cls) -> bool:
        """Check if both query and embedding configurations are of the same type."""
        query_field_info = cls.model_fields.get("query")
        embedding_field_info = cls.model_fields.get("embedding")
        if (
            query_field_info
            and embedding_field_info
            and query_field_info.annotation
            and embedding_field_info.annotation
        ):
            return query_field_info.annotation == embedding_field_info.annotation
        # ! IMPORTANT: Revisit if adding a provider.
        # We're prepared for a situation where this isn't true, but with our current providers
        # it is always true.
        return True

    def _telemetry_keys(self) -> None:
        """Get the telemetry keys for the model."""
        return

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
        return self._dimension or self.get_dimension_sync()

    @property
    def datatype(self) -> str | None:
        """Get the embedding datatype (computed field for backward compatibility).

        Note: This is synchronous but get_datatype() is async. For full
        resolution, use get_datatype() directly. This property returns
        only explicitly configured values or None.
        """
        return self._datatype or self.get_datatype_sync()


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
    return "cohere" if str(model_name).startswith("cohere") else "titan"


type BedrockModelConfig = Annotated[
    Annotated[BedrockCohereConfigDict, Tag("cohere")]
    | Annotated[BedrockTitanV2ConfigDict, Tag("titan")],
    Discriminator(_set_bedrock_model_config_discriminator),
]


class BedrockEmbeddingConfig(BaseEmbeddingConfig):
    """Configuration options for Bedrock embedding models."""

    tag: Literal["bedrock"] = "bedrock"
    provider: Literal[Provider.BEDROCK] = Provider.BEDROCK

    model_name: (
        Literal[
            "amazon.titan-embed-text-v2:0",
            "cohere.embed-english-v3.0",
            "cohere.embed-multilingual-v3.0",
            "cohere.embed-v4:0",
        ]
        | ModelNameT
    )
    """The Bedrock embedding model to use. Can be one of the predefined models or a custom model identifier. Note that this isn't the AWS `model_id` (usually its ARN) - that's specified in the embedding request params."""

    model: Annotated[
        BedrockModelConfig, Field(description="Model-specific embedding configuration options.")
    ]
    """Model-specific embedding configuration options."""

    embedding: BedrockEmbeddingRequestParams | None
    """Parameters for the embedding request to Bedrock."""

    query: BedrockEmbeddingRequestParams | None
    """Parameters for the query request to Bedrock."""

    def set_dimension(self, dimension: int) -> Self:
        """Set the embedding dimension explicitly in the embedding configuration.

        Args:
            dimension: The dimension to set.
        """
        self.model = self.model or {}  # ty:ignore[invalid-assignment]
        object.__setattr__(self, "_dimension", dimension)
        if str(self.model_name).startswith("amazon.titan-embed-text-v2"):
            self.model = BedrockTitanV2ConfigDict(**(self.model | {"dimensions": dimension}))
        return self

    def set_datatype(self, datatype: str) -> Self:
        """Set the embedding datatype explicitly in the embedding configuration.

        Args:
            datatype: The datatype to set.
        """
        self.model = self.model or {}  # ty:ignore[invalid-assignment]
        if str(self.model_name).startswith("amazon.titan-embed"):
            datatype = "binary" if "binary" in datatype else "float"
            self.model["embedding_types"] = datatype
        elif "cohere" in str(self.model_name):
            datatype = (
                "float"
                if "float" in datatype
                else "int8"
                if "int8" in datatype
                else "uint8"
                if "uint8" in datatype
                else "binary"
                if "binary" in datatype
                else "ubinary"
                if "ubinary" in datatype
                else "float"
            )
            self.model["embedding_types"] = datatype  # ty:ignore[invalid-assignment]
        object.__setattr__(self, "_datatype", datatype)
        return self

    def _get_dimension(self) -> int | None:
        """Get explicitly configured dimension without fallbacks.
        Optional field for subclasses to implement as a helper for get_dimension.

        Returns:
            Explicitly configured dimension or None
        """
        if (dim := self._dimension) is not None:
            return dim
        if (model_settings := self.model) and (dimensions := model_settings.get("dimensions")):
            return dimensions
        if self.model_name and str(self.model_name).startswith("amazon.titan-embed-text-v2"):
            return 1024
        return None

    def _get_datatype(self) -> str:
        """Get explicitly configured datatype without fallbacks.
        Optional field for subclasses to implement as a helper for get_datatype.

        Returns:
            Explicitly configured datatype or None
        """
        if self._datatype is not None:
            return self._datatype
        if (model_settings := self.model) and (
            embedding_types := model_settings.get("embedding_types")
        ):
            return embedding_types
        return "float"

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the Bedrock embedding configuration to a dictionary of options."""
        model = self.model.copy()
        return SerializedEmbeddingOptionsDict(
            model_name=ModelName(self.model_name),
            model=model,  # ty:ignore[invalid-argument-type]
            embedding=self.embedding or self.query or {},  # ty:ignore[invalid-argument-type]
            query=self.query or self.embedding or {},  # ty:ignore[invalid-argument-type]
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

    tag: Literal["cohere"] = "cohere"
    provider: Literal[Provider.COHERE] = Provider.COHERE

    model_name: (
        Literal[
            "embed-v4.0",
            "embed-english-v3.0",
            "embed-english-light-v3.0",
            "embed-multilingual-v3.0",
            "embed-multilingual-light-v3.0",
        ]
        | ModelNameT
    )
    """The Cohere embedding model to use."""

    embedding: CohereEmbeddingOptionsDict | None = None

    query: CohereEmbeddingOptionsDict | None = None

    model: dict[str, Any] | None = None

    @override
    def set_dimension(self, dimension: Literal[256, 512, 1024, 1536]) -> Self:  # ty:ignore[invalid-method-override]
        """Set the embedding dimension explicitly in the embedding configuration.

        Args:
            dimension: The dimension to set.
        """
        object.__setattr__(self, "_dimension", dimension)
        if self.embedding:
            self.embedding["output_dimension"] = dimension
        if self.query:
            self.query["output_dimension"] = dimension
        return self

    def set_datatype(self, datatype: str) -> Self:
        """Set the embedding datatype explicitly in the embedding configuration.

        Args:
            datatype: The datatype to set.
        """
        datatype: Literal["float", "int8", "uint8", "binary", "ubinary"] = cast(
            Literal["float", "int8", "uint8", "binary", "ubinary"],
            "float"
            if "float" in datatype
            else (datatype if datatype in {"int8", "uint8", "binary", "ubinary"} else "float"),
        )
        object.__setattr__(self, "_datatype", datatype)
        if self.embedding:
            self.embedding["embedding_types"] = datatype
        if self.query:
            self.query["embedding_types"] = datatype
        return self

    def _get_dimension(self) -> int:
        """Get explicitly configured dimension without fallbacks.
        Optional field for subclasses to implement as a helper for get_dimension.

        Returns:
            Explicitly configured dimension or None
        """
        if self._dimension is not None:
            return self._dimension
        if self.embedding and (output_dimension := self.embedding.get("output_dimension")):
            return output_dimension
        if self.query and (output_dimension := self.query.get("output_dimension")):
            return output_dimension
        return 1536

    def _get_datatype(self) -> str:
        """Get explicitly configured datatype without fallbacks.
        Optional field for subclasses to implement as a helper for get_datatype.

        Returns:
            Explicitly configured datatype or None
        """
        if self._datatype is not None:
            return self._datatype
        if self.embedding and (embedding_types := self.embedding.get("embedding_types")):
            return embedding_types
        if self.query and (embedding_types := self.query.get("embedding_types")):
            return embedding_types
        return "float"

    @property
    def _defaults(self) -> dict[str, Any]:
        """Return default values for the configuration."""
        return {
            "embedding": {
                "model": self.model_name,
                "output_dimension": 1536,
                "embedding_types": "float",
                "truncate": "NONE",
            },
            "query": {
                "model": self.model_name,
                "output_dimension": 1536,
                "embedding_types": "float",
                "truncate": "NONE",
            },
        }

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the Cohere embedding configuration to a dictionary of options."""
        embedding_options = {"model": self.model_name} | (self.embedding or {})
        query_options = {"model": self.model_name} | (self.query or {})
        return SerializedEmbeddingOptionsDict(
            model_name=ModelName(self.model_name),
            embedding=embedding_options,
            query=query_options,
            model={},
        )


class FastEmbedEmbeddingConfig(BaseEmbeddingConfig):
    """Configuration options for FastEmbed embedding models."""

    tag: Literal["fastembed"] = "fastembed"
    provider: Literal[Provider.FASTEMBED] = Provider.FASTEMBED

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the FastEmbed embedding configuration to a dictionary of options."""
        return SerializedEmbeddingOptionsDict(
            model_name=self.model_name, embedding={}, query={}, model={}
        )

    def set_dimension(self, dimension: int) -> Self:
        """Set the embedding dimension explicitly in the embedding configuration.

        Args:
            dimension: The dimension to set.
        """
        object.__setattr__(self, "_dimension", dimension)
        return self

    def set_datatype(self, datatype: str) -> Self:
        """Set the embedding datatype explicitly in the embedding configuration.

        Args:
            datatype: The datatype to set.
        """
        object.__setattr__(self, "_datatype", datatype)
        return self


class GoogleEmbeddingRequestParams(TypedDict, total=False):
    """Parameters for Google embedding requests."""

    output_dimensionality: NotRequired[int]
    """The desired output dimensionality for the embeddings. Defaults to 768. `gemini-test-embedding-001` supports 3072, 1536, or 768 dimensions. We default to 768 because the retrieval performance hit is tiny (~1%) and the size savings are significant (4x smaller), and you get faster inference too."""


class GoogleEmbeddingConfig(BaseEmbeddingConfig):
    """Configuration options for Google embedding models."""

    tag: Literal["google"] = "google"
    provider: Literal[Provider.GOOGLE] = Provider.GOOGLE

    model_name: Literal["gemini-embedding-001"] | ModelNameT
    """The Google embedding model to use."""
    embedding: GoogleEmbeddingRequestParams | None = None
    """Parameters for the embedding request to Google."""

    query: GoogleEmbeddingRequestParams | None = None
    """Parameters for the query request to Google."""

    def set_dimension(self, dimension: int) -> Self:
        """Set the embedding dimension explicitly in the embedding configuration.

        Args:
            dimension: The dimension to set.
        """
        object.__setattr__(self, "_dimension", dimension)
        if self.embedding:
            self.embedding["output_dimensionality"] = dimension
        if self.query:
            self.query["output_dimensionality"] = dimension
        return self

    def set_datatype(self, datatype: str) -> Self:
        """Set the embedding datatype explicitly in the embedding configuration.

        Args:
            datatype: The datatype to set.
        """
        object.__setattr__(self, "_datatype", datatype)
        return self

    def _get_dimension(self) -> int:
        """Get explicitly configured dimension without fallbacks.
        Optional field for subclasses to implement as a helper for get_dimension.

        Returns:
            Explicitly configured dimension or None
        """
        if self.embedding and (output_dimension := self.embedding.get("output_dimensionality")):
            return output_dimension
        if default := self._defaults.get("embedding", {}):
            return default.get("output_dimensionality")
        return 768

    def _get_datatype(self) -> Literal["float"]:
        """Get explicitly configured datatype without fallbacks.
        Optional field for subclasses to implement as a helper for get_datatype.

        Returns:
            Explicitly configured datatype or None
        """
        if not self._datatype:
            object.__setattr__(self, "_datatype", "float")
        return self._datatype  # type: ignore[return-value]

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the Google embedding configuration to a dictionary of options."""
        embedding_options = {"model": self.model_name} | (self.embedding or {})
        query_options = {"model": self.model_name} | (self.query or embedding_options)
        return SerializedEmbeddingOptionsDict(
            model_name=ModelName(self.model_name),
            embedding=embedding_options,
            query=query_options,
            model={},
        )

    @property
    def _defaults(self) -> dict[str, Any]:
        """Return default values for the configuration."""
        return (
            {"embedding": {"output_dimensionality": 768}}
            if self.model_name == ModelName("gemini-embedding-001")
            else {}
        )


class HuggingFaceEmbeddingConfig(BaseEmbeddingConfig):
    """Configuration options for HuggingFace embedding models."""

    tag: Literal["huggingface"] = "huggingface"
    provider: Literal[Provider.HUGGINGFACE_INFERENCE] = Provider.HUGGINGFACE_INFERENCE

    def set_dimension(self, dimension: int) -> Self:
        """Set the embedding dimension explicitly in the embedding configuration.

        Args:
            dimension: The dimension to set.
        """
        object.__setattr__(self, "_dimension", dimension)
        return self

    def set_datatype(self, datatype: str) -> Self:
        """Set the embedding datatype explicitly in the embedding configuration.

        Args:
            datatype: The datatype to set.
        """
        object.__setattr__(self, "_datatype", datatype)
        return self

    def _get_dimension(self) -> int | None:
        """Get explicitly configured dimension without fallbacks.
        Optional field for subclasses to implement as a helper for get_dimension.

        Returns:
            Explicitly configured dimension or None
        """
        return self._dimension

    def _get_datatype(self) -> str | None:
        """Get explicitly configured datatype without fallbacks.
        Optional field for subclasses to implement as a helper for get_datatype.

        Returns:
            Explicitly configured datatype or None
        """
        return self._datatype

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

    tag: Literal["mistral"] = "mistral"
    provider: Literal[Provider.MISTRAL] = Provider.MISTRAL

    model_name: Literal["mistral-embed", "codestral-embed"] | ModelNameT
    """The Mistral AI embedding model to use."""

    embedding: MistralEmbeddingOptionsDict | None = None
    """Parameters for document embedding requests."""

    query: MistralEmbeddingOptionsDict | None = None
    """Parameters for query embedding requests (same as embedding for Mistral)."""

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the Mistral embedding configuration to a dictionary of options."""
        return SerializedEmbeddingOptionsDict(
            model_name=ModelName(self.model_name),
            embedding=cast(dict[str, Any], self.embedding or {}),
            query=cast(dict[str, Any], self.query or {}),
            model={},
        )

    @property
    def _defaults(self) -> dict[str, Any]:
        """Return default values for the configuration."""
        dimension = (
            1024
            if str(self.model_name) == "mistral-embed"
            else 1536
            if str(self.model_name) == "codestral-embed"
            else None
        )
        return {
            "embedding": {"output_dimension": dimension, "output_dtype": "float"},
            "query": {"output_dimension": dimension, "output_dtype": "float"},
        }

    def set_dimension(self, dimension: int) -> Self:
        """Set the embedding dimension explicitly in the embedding configuration.

        Args:
            dimension: The dimension to set.
        """
        object.__setattr__(self, "_dimension", dimension)
        self.embedding = self.embedding or {}  # ty:ignore[invalid-assignment]
        self.query = self.query or {}  # ty:ignore[invalid-assignment]
        self.embedding["output_dimension"] = dimension  # ty:ignore[invalid-assignment]
        self.query["output_dimension"] = dimension  # ty:ignore[invalid-assignment]
        return self

    def _get_dimension(self) -> int | None:
        """Get explicitly configured dimension without fallbacks.
        Optional field for subclasses to implement as a helper for get_dimension.

        Returns:
            Explicitly configured dimension or None
        """
        if self.embedding and (output_dimension := self.embedding.get("output_dimension")):
            return output_dimension
        return (
            1024
            if str(self.model_name) == "mistral-embed"
            else 1536
            if str(self.model_name) == "codestral-embed"
            else None
        )

    def _get_datatype(self) -> str:
        """Get explicitly configured datatype without fallbacks.
        Optional field for subclasses to implement as a helper for get_datatype.

        Returns:
            Explicitly configured datatype or None
        """
        if self.embedding and (output_dtype := self.embedding.get("output_dtype")):
            return output_dtype
        return "float"


class OpenAIEmbeddingRequestParams(TypedDict, total=False):
    """Parameters for OpenAI-compatible embedding requests.

    These parameters work across all OpenAI-compatible providers including
    Azure OpenAI, Ollama, Fireworks, Together AI, GitHub Models, and Groq.
    """

    dimensions: NotRequired[int]
    """Output dimensionality for the embeddings. Only supported by text-embedding-3-* models for OpenAI, but can be used for other non-OpenAI providers."""

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

    tag: Literal["openai"] = "openai"
    provider: Literal[Provider.OPENAI] = Provider.OPENAI

    model_name: Literal["text-embedding-3-large", "text-embedding-3-small"] | ModelNameT
    """The OpenAI-compatible embedding model to use."""

    embedding: OpenAIEmbeddingRequestParams | None = None
    """Parameters for document embedding requests."""

    query: OpenAIEmbeddingRequestParams | None = None
    """Parameters for query embedding requests (same as embedding for OpenAI)."""

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the OpenAI embedding configuration to a dictionary of options."""
        return SerializedEmbeddingOptionsDict(
            model_name=ModelName(self.model_name),
            embedding=cast(dict[str, Any], self.embedding or {}),
            query=cast(dict[str, Any], self.query or {}),
            model={},
        )

    def set_dimension(self, dimension: int) -> Self:
        """Set the embedding dimension explicitly in the embedding configuration.

        Args:
            dimension: The dimension to set.
        """
        object.__setattr__(self, "_dimension", dimension)
        self.embedding = self.embedding or {}  # ty:ignore[invalid-assignment]
        self.query = self.query or {}  # ty:ignore[invalid-assignment]
        self.embedding["dimensions"] = dimension  # ty:ignore[invalid-assignment]
        self.query["dimensions"] = dimension  # ty:ignore[invalid-assignment]
        return self

    def set_datatype(self, datatype: str) -> Self:
        """Set the embedding datatype explicitly in the embedding configuration.

        Args:
            datatype: The datatype to set.
        """
        object.__setattr__(self, "_datatype", datatype)
        return self

    def _get_dimension(self) -> int | None:
        """Get explicitly configured dimension without fallbacks.
        Optional field for subclasses to implement as a helper for get_dimension.

        Returns:
            Explicitly configured dimension or None
        """
        if self.embedding and (dimensions := self.embedding.get("dimensions")):
            return dimensions
        return None

    def _get_datatype(self) -> str:
        """Get explicitly configured datatype without fallbacks.
        Optional field for subclasses to implement as a helper for get_datatype.

        Returns:
            Explicitly configured datatype or None
        """
        return self._datatype if self._datatype is not None else "float"

    @property
    def _defaults(self) -> dict[str, Any]:
        """Return default values for the configuration."""
        dimension = (
            3072
            if str(self.model_name) == "text-embedding-3-large"
            else 1_536
            if str(self.model_name) == "text-embedding-3-small"
            else None
        )
        return {
            "embedding": {
                "dimensions": dimension,
                "encoding_format": "float",
                "timeout": DEFAULT_EMBEDDING_TIMEOUT,
            },
            "query": {
                "dimensions": dimension,
                "encoding_format": "float",
                "timeout": DEFAULT_EMBEDDING_TIMEOUT,
            },
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

    tag: Literal["sentence_transformers"] = "sentence_transformers"
    provider: Literal[Provider.SENTENCE_TRANSFORMERS] = Provider.SENTENCE_TRANSFORMERS

    model_name: ModelNameT
    """The Sentence Transformers model to use."""

    embedding: SentenceTransformersEncodeDict | None = None
    """Parameters for document/corpus encoding."""

    query: SentenceTransformersEncodeDict | None = None
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
        """Set the embedding dimension explicitly in the embedding configuration.

        Args:
            dimension: The dimension to set.
        """
        object.__setattr__(self, "_dimension", dimension)
        self.embedding = self.embedding or {}  # ty:ignore[invalid-assignment]
        self.embedding["truncate_dim"] = dimension  # ty:ignore[invalid-assignment]
        self.query = self.query or {}  # ty:ignore[invalid-assignment]
        self.query["truncate_dim"] = dimension  # ty:ignore[invalid-assignment]
        return self

    def set_datatype(self, datatype: str) -> Self:
        """Set the embedding datatype explicitly in the embedding configuration.

        Args:
            datatype: The datatype to set.
        """
        object.__setattr__(self, "_datatype", datatype)
        self.embedding = self.embedding or {}  # ty:ignore[invalid-assignment]
        self.embedding["precision"] = datatype  # ty:ignore[invalid-assignment]
        self.query = self.query or {}  # ty:ignore[invalid-assignment]
        self.query["precision"] = datatype  # ty:ignore[invalid-assignment]
        return self

    def _get_dimension(self) -> int | None:
        """Get explicitly configured dimension without fallbacks.
        Optional field for subclasses to implement as a helper for get_dimension.

        Returns:
            Explicitly configured dimension or None
        """
        if self.embedding and (output_dimension := self.embedding.get("truncate_dim")):
            return output_dimension
        return None

    def _get_datatype(self) -> str:
        """Get explicitly configured datatype without fallbacks.
        Optional field for subclasses to implement as a helper for get_datatype.

        Returns:
            Explicitly configured datatype or None
        """
        if self.embedding and (precision := self.embedding.get("precision")):
            return precision
        return "float32"

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

    tag: Literal["voyage"] = "voyage"
    provider: Literal[Provider.VOYAGE] = Provider.VOYAGE

    model_name: (
        Literal[
            "voyage-code-3",
            "voyage-3.5",
            "voyage-3.5-lite",
            "voyage-3-large",
            "voyage-context-3",
            "voyage-4",
            "voyage-4-lite",
            "voyage-4-large",
        ]
        | ModelNameT
    )
    """The Voyage AI embedding model to use."""

    embedding: VoyageEmbeddingOptionsDict | None = None
    """Parameters for document embedding requests."""

    query: VoyageEmbeddingOptionsDict | None = None
    """Parameters for query embedding requests."""

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert the Voyage embedding configuration to a dictionary of options."""
        return SerializedEmbeddingOptionsDict(
            model_name=ModelName(self.model_name),
            embedding=cast(dict[str, Any], (self.embedding or {}) | {"input_type": "document"}),
            query=cast(dict[str, Any], (self.query or {}) | {"input_type": "query"}),
            model={},
        )

    def _get_dimension(self) -> int:
        """Get explicitly configured dimension without fallbacks.
        Optional field for subclasses to implement as a helper for get_dimension.

        Returns:
            Explicitly configured dimension or None
        """
        if self.embedding and (output_dimension := self.embedding.get("output_dimension")):
            return output_dimension
        return 1024

    def _get_datatype(self) -> str:
        """Get explicitly configured datatype without fallbacks.
        Optional field for subclasses to implement as a helper for get_datatype.

        Returns:
            Explicitly configured datatype or None
        """
        if self.embedding and (output_dtype := self.embedding.get("output_dtype")):
            return output_dtype
        return "uint8"

    @property
    def supports_asymmetric_queries(self) -> bool:
        """Check if the model supports asymmetric query/document. These models can query each others' embeddings."""
        return str(self.model_name).startswith("voyage-4")

    @property
    def _defaults(self) -> dict[str, Any]:
        """Return default values for the configuration."""
        return {
            "embedding": {"input_type": "document", "truncation": True, "output_dtype": "uint8"},
            "query": {"input_type": "query", "truncation": True, "output_dtype": "uint8"},
        }


# ============================================================================
# Sparse Embedding Configs (Reuse dense configs with renamed classes)
# ============================================================================
async def _to_sparse_vector_params(instance: BaseEmbeddingConfig) -> SparseVectorParams:
    """Convert a sparse embedding config to SparseVectorParams."""
    datatype = await instance.get_datatype()
    resolved_datatype = (
        datatype
        if datatype and datatype in ("float32", "float16", "uint8")
        else "float16"
        if (not datatype or "float" in datatype)
        else "uint8"
    )
    index_params = SparseIndexParams(datatype=Datatype(resolved_datatype))
    modifier = Modifier.IDF if ("bm25" in str(instance.model_name).lower()) else Modifier.NONE
    return SparseVectorParams(index=index_params, modifier=modifier)


class SentenceTransformersSparseEmbeddingConfig(SentenceTransformersEmbeddingConfig):
    """Configuration options for Sentence Transformers sparse embedding models.

    Inherits all configuration from SentenceTransformersEmbeddingConfig.
    """

    _is_sparse: ClassVar[bool] = True

    async def as_sparse_vector_params(self) -> SparseVectorParams:
        """Get Qdrant SparseVectorParams for this sparse embedding configuration."""
        return await _to_sparse_vector_params(self)


class FastEmbedSparseEmbeddingConfig(FastEmbedEmbeddingConfig):
    """Configuration options for FastEmbed sparse embedding models.

    Inherits all configuration from FastEmbedEmbeddingConfig.
    """

    _is_sparse: ClassVar[bool] = True

    async def as_sparse_vector_params(self) -> SparseVectorParams:
        """Get Qdrant SparseVectorParams for this sparse embedding configuration."""
        return await _to_sparse_vector_params(self)


# ============================================================================
# Discriminator Type Unions
# ============================================================================

EmbeddingConfigT = Annotated[
    BedrockEmbeddingConfig
    | CohereEmbeddingConfig
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

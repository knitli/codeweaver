# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: no-complex-if-expressions
"""Settings for asymmetric embedding providers."""

from __future__ import annotations

import logging

from functools import cached_property
from typing import Annotated, Literal, NotRequired, Required, TypedDict, cast

from pydantic import Field, NonNegativeInt, model_validator

from codeweaver.core.exceptions import DatatypeMismatchError, DimensionMismatchError
from codeweaver.core.types import BasedModel
from codeweaver.providers.config.kinds import EmbeddingProviderSettingsType


logger = logging.getLogger(__name__)


class AsymmetricEmbeddingConfigDict(TypedDict, total=False):
    """Dictionary representation of asymmetric embedding configuration."""

    embed_provider: Required[EmbeddingProviderSettingsType]
    query_provider: Required[EmbeddingProviderSettingsType]
    validate_family_compatibility: NotRequired[bool]


class AsymmetricEmbeddingConfig(BasedModel):
    """Configuration for asymmetric embedding setup with separate embed and query models.

    Asymmetric embedding allows using different models for document embedding and query
    embedding while maintaining compatibility through shared vector spaces. This enables
    cost optimization (e.g., API for embed, local for queries) while preserving accuracy.

    Attributes:
        config_type: Discriminator field for union type matching.
        embed_provider: Provider settings for document embedding model.
        query_provider: Provider settings for query embedding model.
        validate_family_compatibility: Whether to validate models belong to same family.
    """

    config_type: Annotated[
        Literal["asymmetric"],
        Field(default="asymmetric", description="Discriminator for embedding config type."),
    ] = "asymmetric"

    embed_provider: Annotated[
        EmbeddingProviderSettingsType,
        Field(description="Provider settings for the document embedding model."),
    ]
    query_provider: Annotated[
        EmbeddingProviderSettingsType,
        Field(description="Provider settings for the query embedding model."),
    ]
    validate_family_compatibility: Annotated[
        bool,
        Field(description="Whether to validate that both models belong to the same model family."),
    ] = True

    @cached_property
    def dimension_tuple(self) -> tuple[NonNegativeInt, NonNegativeInt]:
        """Get the embedding dimensions for embed and query models.

        Returns:
            A tuple of (embed_dimension, query_dimension).
        """
        if (
            found_values := (
                self.embed_provider.embedding_config.dimension,
                self.query_provider.embedding_config.dimension,
            )
        ) and all(dim is not None for dim in found_values):
            return cast(
                tuple[NonNegativeInt, NonNegativeInt],
                (
                    self.embed_provider.embedding_config.dimension,
                    self.query_provider.embedding_config.dimension,
                ),
            )
        match found_values:
            case (int(), None):
                self.query_provider.embedding_config.set_dimension(cast(int, found_values[0]))  # ty:ignore[invalid-argument-type]
                return cast(tuple[int, int], (found_values[0], found_values[0]))
            case (None, int()):
                self.embed_provider.embedding_config.set_dimension(cast(int, found_values[1]))  # ty:ignore[invalid-argument-type]
                return cast(tuple[int, int], (found_values[1], found_values[1]))
            case _:
                embed_caps = (
                    self.embed_provider.embedding_config.capabilities
                    or self.query_provider.embedding_config.capabilities
                )
                if not embed_caps:
                    raise ValueError(
                        "Cannot determine embedding dimensions for asymmetric embedding config: "
                        "neither model has dimension set or capabilities registered."
                    )
                self.embed_provider.embedding_config.set_dimension(embed_caps.default_dimension)  # ty:ignore[invalid-argument-type]
                self.query_provider.embedding_config.set_dimension(embed_caps.default_dimension)  # ty:ignore[invalid-argument-type]
                return cast(
                    tuple[int, int], (embed_caps.default_dimension, embed_caps.default_dimension)
                )
        return cast(
            tuple[NonNegativeInt, NonNegativeInt],
            (
                self.embed_provider.embedding_config.dimension,
                self.query_provider.embedding_config.dimension,
            ),
        )

    @cached_property
    def datatype_tuple(self) -> tuple[str, str]:
        """Get the embedding datatypes for embed and query models.

        Returns:
            A tuple of (embed_datatype, query_datatype).
        """
        if (
            found_values := (
                self.embed_provider.embedding_config.datatype,
                self.query_provider.embedding_config.datatype,
            )
        ) and all(dt is not None for dt in found_values):
            return cast(
                tuple[str, str],
                (
                    self.embed_provider.embedding_config.datatype,
                    self.query_provider.embedding_config.datatype,
                ),
            )
        match found_values:
            case (str(), None):
                self.query_provider.embedding_config.set_datatype(cast(str, found_values[0]))  # ty:ignore[invalid-argument-type]
                return cast(tuple[str, str], (found_values[0], found_values[0]))
            case (None, str()):
                self.embed_provider.embedding_config.set_datatype(cast(str, found_values[1]))  # ty:ignore[invalid-argument-type]
                return cast(tuple[str, str], (found_values[1], found_values[1]))
            case _:
                embed_caps = (
                    self.embed_provider.embedding_config.capabilities
                    or self.query_provider.embedding_config.capabilities
                )
                if not embed_caps:
                    raise ValueError(
                        "Cannot determine embedding datatypes for asymmetric embedding config: "
                        "neither model has datatype set or capabilities registered."
                    )
                self.embed_provider.embedding_config.set_datatype(embed_caps.default_dtype)  # ty:ignore[invalid-argument-type]
                self.query_provider.embedding_config.set_datatype(embed_caps.default_dtype)  # ty:ignore[invalid-argument-type]
                return cast(tuple[str, str], (embed_caps.default_dtype, embed_caps.default_dtype))
        return cast(
            tuple[str, str],
            (
                self.embed_provider.embedding_config.datatype,
                self.query_provider.embedding_config.datatype,
            ),
        )

    @model_validator(mode="after")
    def validate_model_compatibility(self) -> AsymmetricEmbeddingConfig:
        """Validate that embed and query models are compatible.

        Validates:
        - Both models have registered capabilities
        - Both models belong to model families
        - Both models belong to the same family
        - Models are compatible within the family
        - Embedding dimensions match

        Returns:
            Self for method chaining.

        Raises:
            ConfigurationError: If models are incompatible.
        """
        from codeweaver.core.exceptions import ConfigurationError

        if not self.validate_family_compatibility:
            logger.warning(
                "Family compatibility validation disabled for asymmetric embedding config. "
                "This may result in incompatible embeddings if models are from different families."
            )
            return self

        if self.dimension_tuple[0] != self.dimension_tuple[1]:
            raise DimensionMismatchError(
                f"Embedding dimension mismatch: embed model dimension {self.dimension_tuple[0]} != query model dimension {self.dimension_tuple[1]}",
                details={
                    "embed_model": str(self.embed_provider.model_name),
                    "embed_dimension": self.dimension_tuple[0],
                    "query_model": str(self.query_provider.model_name),
                    "query_dimension": self.dimension_tuple[1],
                },
                suggestions=[
                    "Ensure both models are configured with the same embedding dimension",
                    "Set dimensions explicitly in the embedding configurations if needed",
                ],
            )
        if self.datatype_tuple[0] != self.datatype_tuple[1]:
            raise DatatypeMismatchError(
                f"Embedding datatype mismatch: embed model datatype '{self.datatype_tuple[0]}' != query model datatype '{self.datatype_tuple[1]}'",
                details={
                    "embed_model": str(self.embed_provider.model_name),
                    "embed_datatype": self.datatype_tuple[0],
                    "query_model": str(self.query_provider.model_name),
                    "query_datatype": self.datatype_tuple[1],
                },
                suggestions=[
                    "Ensure both models are configured with the same embedding datatype",
                    "Set datatypes explicitly in the embedding configurations if needed",
                ],
            )
        if (
            caps := self.embed_provider.embedding_config.capabilities
            if self.embed_provider.embedding_config
            else self.query_provider.embedding_config.capabilities
            if self.query_provider.embedding_config
            else None
        ) is not None and caps.model_family is not None:
            if caps.model_family.is_compatible(
                str(self.embed_provider.model_name), str(self.query_provider.model_name)
            ):
                logger.info(
                    "Asymmetric embedding configuration validated successfully using pre-set capabilities: "
                    "embed_model='%s', query_model='%s', family='%s'",
                    str(self.embed_provider.model_name),
                    str(self.query_provider.model_name),
                    caps.model_family.family_id,
                )
                return self
            raise ConfigurationError(
                f"Models are not compatible within family '{caps.model_family.family_id}' based on pre-set capabilities",
                details={
                    "embed_model": str(self.embed_provider.model_name),
                    "query_model": str(self.query_provider.model_name),
                    "family_id": caps.model_family.family_id,
                    "family_members": sorted(caps.model_family.member_models),
                },
                suggestions=[
                    "Ensure both models are listed as family members",
                    f"Valid family members: {', '.join(sorted(caps.model_family.member_models))}",
                    "Contact support if you believe this is an error",
                ],
            )
        if not caps:
            raise ConfigurationError(
                "Cannot validate model compatibility: neither model has embedding capabilities registered",
                details={
                    "embed_model": str(self.embed_provider.model_name),
                    "query_model": str(self.query_provider.model_name),
                },
                suggestions=[
                    "Ensure both models have embedding capabilities registered",
                    "Check provider documentation for supported models and capabilities",
                ],
            )

        return self

    @property
    def dimension(self) -> NonNegativeInt:
        """Get the embedding dimension for both models (they must match)."""
        return self.dimension_tuple[0]

    @property
    def datatype(self) -> str:
        """Get the embedding datatype for both models (they must match)."""
        return self.datatype_tuple[0]

    def _telemetry_keys(self) -> None:
        """Telemetry keys implementation."""
        return


__all__ = ("AsymmetricEmbeddingConfig",)

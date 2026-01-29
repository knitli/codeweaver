# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""
Vector configuration types for Qdrant integration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast

from pydantic import Field
from qdrant_client.models import SparseVectorParams, VectorParams

from codeweaver.core.types import BasedModel, BaseEnum, EmbeddingKind, ModelName, ModelNameT


if TYPE_CHECKING:
    from codeweaver.providers.config.kinds import (
        EmbeddingProviderSettings,
        SparseEmbeddingProviderSettings,
    )
    from codeweaver.providers.config.profiles import ProviderProfile


__all__ = ("VectorConfig", "VectorRole", "VectorSet")


# ============================================================================
# Vector Types (Role-Based Architecture)
# ============================================================================
# Role-based vector configuration system with direct Qdrant alignment.


class VectorRole(BaseEnum):
    """Semantic roles for vectors (extensible for future strategies).

    The enum values should match common physical vector names by default.
    Use .variable property to get snake_case string representation.

    Example:
        >>> VectorRole.PRIMARY.variable
        'primary'
        >>> VectorRole.BACKUP.variable
        'backup'

    Future extensions might include:
        - SEMANTIC_CODE: "semantic_code"
        - SEMANTIC_DOCS: "semantic_docs"
        - KEYWORD: "keyword"
    """

    PRIMARY = "primary"
    BACKUP = "backup"
    SPARSE = "sparse"


class VectorConfig(BasedModel, frozen=True):
    """Immutable configuration for a single named vector in Qdrant.

    Aligns directly with Qdrant's vector configuration while adding
    minimal metadata for generation and identification.

    Attributes:
        name: Physical Qdrant vector name (e.g., "primary", "backup", "sparse")
              Should reflect the vector's purpose/role, not the model.
        model_name: Model used to generate this vector (metadata for generation)
        params: Direct Qdrant VectorParams or SparseVectorParams
        role: Optional semantic role (defaults to name if not provided)

    Example:
        >>> config = VectorConfig(
        ...     name="primary",
        ...     model_name=ModelName("voyage-large-2-instruct"),
        ...     params=VectorParams(size=1024, distance="Cosine"),
        ...     role=VectorRole.PRIMARY,
        ... )
    """

    name: Annotated[
        str,
        Field(
            description="Physical Qdrant vector name (purpose-based, e.g., 'primary', 'backup')",
            pattern=r"^[a-z][a-z0-9_]*$",
            min_length=1,
            max_length=50,
        ),
    ]

    model_name: Annotated[ModelNameT, Field(description="Model used to generate this vector")]

    params: Annotated[
        VectorParams | SparseVectorParams, Field(description="Direct Qdrant vector parameters")
    ]

    role: Annotated[
        VectorRole | str | None,
        Field(default=None, description="Optional semantic role (defaults to name)"),
    ] = None

    def __init__(self, **data):
        """Initialize VectorConfig with role defaulting to name."""
        super().__init__(**data)
        # Normalize role to string - convert enum to string if needed, default to name if None
        role_value = self.role
        if role_value is None:
            # Use object.__setattr__ because frozen=True
            object.__setattr__(self, "role", self.name)
        elif isinstance(role_value, VectorRole):
            # Convert enum to string using .variable property
            object.__setattr__(self, "role", role_value.variable)
        # else: already a string, keep as is

    def _telemetry_keys(self):
        """Return telemetry keys for privacy-aware serialization.

        VectorConfig contains no user-identifying information, all fields are safe.
        """
        return

    # Properties

    @property
    def kind(self) -> EmbeddingKind:
        """Infer embedding kind from params type.

        Returns:
            EmbeddingKind.DENSE for VectorParams
            EmbeddingKind.SPARSE for SparseVectorParams
        """
        return (
            EmbeddingKind.DENSE if isinstance(self.params, VectorParams) else EmbeddingKind.SPARSE
        )

    @property
    def is_dense(self) -> bool:
        """Check if this is a dense vector configuration."""
        return self.kind == EmbeddingKind.DENSE

    @property
    def is_sparse(self) -> bool:
        """Check if this is a sparse vector configuration."""
        return self.kind == EmbeddingKind.SPARSE

    # Conversion methods

    def to_qdrant_config(self) -> tuple[str, VectorParams | SparseVectorParams]:
        """Return (name, params) tuple for Qdrant collection config.

        Returns:
            Tuple of (physical_vector_name, vector_params) ready for
            Qdrant's vectors_config or sparse_vectors_config dict.

        Example:
            >>> config = VectorConfig(name="primary", ...)
            >>> name, params = config.to_qdrant_config()
            >>> collection_config = CollectionParams(vectors_config={name: params})
        """
        return (self.name, self.params)

    # Factory methods

    @classmethod
    async def from_provider_settings(
        cls,
        config: EmbeddingProviderSettings | SparseEmbeddingProviderSettings,
        *,
        name: str,
        role: VectorRole | str | None = None,
    ) -> VectorConfig:
        """Create VectorConfig from provider settings.

        Args:
            config: Provider settings (embedding or sparse)
            name: Physical Qdrant vector name (REQUIRED, purpose-based)
                  e.g., "primary", "backup", "sparse", "semantic_code"
            role: Optional semantic role (defaults to name)

        Returns:
            Configured VectorConfig instance

        Example:
            >>> from codeweaver.providers.config.kinds import EmbeddingProviderSettings
            >>> settings = EmbeddingProviderSettings(...)
            >>> config = await VectorConfig.from_provider_settings(
            ...     settings, name="primary", role=VectorRole.PRIMARY
            ... )
        """
        from codeweaver.providers.config.kinds import SparseEmbeddingProviderSettings

        model_name = ModelName(config.model_name)

        # Get Qdrant params from config
        if isinstance(config, SparseEmbeddingProviderSettings):
            params = await config.sparse_embedding_config.as_sparse_vector_params()
        else:
            params = await config.embedding_config.as_vector_params()

        return cls(
            name=name,
            model_name=model_name,
            params=params,
            role=role or name,  # Default role to name
        )


class VectorSet(BasedModel, frozen=True):
    """Immutable collection of vectors for a search/indexing strategy.

    Manages multiple named vectors with flexible organization. Vectors
    can be keyed by strategy name, intent, or any identifier. Provides
    query methods and conversion to Qdrant collection configuration.

    Attributes:
        vectors: Dict of VectorConfig keyed by logical identifier
                 (e.g., "primary", "backup", "sparse", "semantic_v1")

    Example:
        >>> vector_set = VectorSet(vectors={
        ...     "primary": VectorConfig(name="primary", ...),
        ...     "backup": VectorConfig(name="backup", ...),
        ...     "sparse": VectorConfig(name="sparse", ...),
        ... })
        >>>
        >>> # Convert to Qdrant config
        >>> vectors_config = vector_set.to_qdrant_vectors_config()
        >>> sparse_config = vector_set.to_qdrant_sparse_vectors_config()
    """

    vectors: Annotated[
        dict[str, VectorConfig],
        Field(description="Vector configurations keyed by logical identifier"),
    ]

    def __init__(self, **data):
        """Initialize and validate vector name uniqueness."""
        super().__init__(**data)

        # Validate physical vector names are unique
        names = [v.name for v in self.vectors.values()]
        if len(names) != len(set(names)):
            duplicates = {n for n in names if names.count(n) > 1}
            raise ValueError(
                f"Duplicate physical vector names found: {duplicates}. "
                "Each vector must have a unique physical name in Qdrant."
            )

    def _telemetry_keys(self) -> None:
        """Return telemetry keys for privacy-aware serialization.

        VectorSet contains no user-identifying information, all fields are safe.
        """
        return

    # Query methods

    def by_role(self, role: VectorRole | str) -> list[VectorConfig]:
        """Get all vectors with a specific role.

        Supports multiple vectors with the same role for future
        multi-strategy support.

        Args:
            role: VectorRole enum or string role name

        Returns:
            List of matching VectorConfigs (may be empty)

        Example:
            >>> primaries = vector_set.by_role(VectorRole.PRIMARY)
            >>> backups = vector_set.by_role("backup")
        """
        role_name = role.variable if isinstance(role, VectorRole) else role
        return [
            v
            for v in self.vectors.values()
            if (v.role.variable if isinstance(v.role, VectorRole) else v.role) == role_name
        ]

    def by_name(self, name: str) -> VectorConfig | None:
        """Get vector by its physical Qdrant name.

        Args:
            name: Physical vector name (e.g., "primary", "backup")

        Returns:
            Matching VectorConfig or None
        """
        return next((v for v in self.vectors.values() if v.name == name), None)

    def by_key(self, key: str) -> VectorConfig | None:
        """Get vector by its logical dict key.

        Args:
            key: Logical identifier used in vectors dict

        Returns:
            Matching VectorConfig or None
        """
        return self.vectors.get(key)

    def dense_vectors(self) -> dict[str, VectorConfig]:
        """Get all dense vectors.

        Returns:
            Dict of dense VectorConfigs (preserves keys)
        """
        return {k: v for k, v in self.vectors.items() if v.is_dense}

    def sparse_vectors(self) -> dict[str, VectorConfig]:
        """Get all sparse vectors.

        Returns:
            Dict of sparse VectorConfigs (preserves keys)
        """
        return {k: v for k, v in self.vectors.items() if v.is_sparse}

    # Convenience accessors for common patterns

    def primary(self) -> VectorConfig | None:
        """Get primary dense vector (common case).

        Returns first vector with PRIMARY role, or None.
        """
        matches = self.by_role(VectorRole.PRIMARY)
        return matches[0] if matches else None

    def backup(self) -> VectorConfig | None:
        """Get backup dense vector (common case).

        Returns first vector with BACKUP role, or None.
        """
        matches = self.by_role(VectorRole.BACKUP)
        return matches[0] if matches else None

    def sparse(self) -> VectorConfig | None:
        """Get sparse vector (common case).

        Returns first vector with SPARSE role, or None.
        """
        matches = self.by_role(VectorRole.SPARSE)
        return matches[0] if matches else None

    # Qdrant conversion methods

    def to_qdrant_vectors_config(self) -> dict[str, VectorParams]:
        """Generate Qdrant vectors_config dict for dense vectors.

        Returns:
            Dict mapping physical vector names to VectorParams,
            ready for CollectionConfig.vectors_config

        Example:
            >>> config = CollectionParams(vectors_config=vector_set.to_qdrant_vectors_config())
        """
        return cast(
            dict[str, VectorParams], {v.name: v.params for v in self.vectors.values() if v.is_dense}
        )

    def to_qdrant_sparse_vectors_config(self) -> dict[str, SparseVectorParams]:
        """Generate Qdrant sparse_vectors_config dict for sparse vectors.

        Returns:
            Dict mapping physical vector names to SparseVectorParams,
            ready for CollectionConfig.sparse_vectors_config

        Example:
            >>> config = CollectionParams(
            ...     sparse_vectors_config=vector_set.to_qdrant_sparse_vectors_config()
            ... )
        """
        return cast(
            dict[str, SparseVectorParams],
            {v.name: v.params for v in self.vectors.values() if v.is_sparse},
        )

    # Factory methods

    @classmethod
    async def from_profile(cls, profile: ProviderProfile) -> VectorSet:
        """Create VectorSet from provider profile.

        Creates standard layout with primary, backup (optional), and
        sparse (optional) vectors based on profile configuration.
        Uses role-based physical vector names.

        Args:
            profile: Provider profile with embedding configurations

        Returns:
            Configured VectorSet with standard layout

        Example:
            >>> from codeweaver.providers.config.profiles import ProviderProfile
            >>> vector_set = await VectorSet.from_profile(ProviderProfile.RECOMMENDED)
        """
        vectors = {}

        # Primary dense (required)
        if profile.embedding and profile.embedding[0]:
            vectors["primary"] = await VectorConfig.from_provider_settings(
                profile.embedding[0],
                name="primary",  # Role-based physical name
                role=VectorRole.PRIMARY,
            )

        # Backup dense (optional, if different from primary)
        if (
            profile.embedding
            and len(profile.embedding) > 1
            and profile.embedding[1]
            and profile.embedding[1] != profile.embedding[0]
        ):
            vectors["backup"] = await VectorConfig.from_provider_settings(
                profile.embedding[1],
                name="backup",  # Role-based physical name
                role=VectorRole.BACKUP,
            )

        # Sparse (optional)
        if profile.sparse_embedding and profile.sparse_embedding[0]:
            vectors["sparse"] = await VectorConfig.from_provider_settings(
                profile.sparse_embedding[0],
                name="sparse",  # Role-based physical name
                role=VectorRole.SPARSE,
            )

        return cls(vectors=vectors)

    @classmethod
    async def default(cls) -> VectorSet:
        """Create default VectorSet with recommended configuration.

        Returns:
            VectorSet with recommended profile configuration
        """
        from codeweaver.providers.config.profiles import ProviderProfile

        return await cls.from_profile(ProviderProfile.RECOMMENDED)


__all__ = ("SparseVectorParams", "VectorConfig", "VectorParams", "VectorRole", "VectorSet")

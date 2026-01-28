# Vector Types Refactor Implementation Plan

## Overview

Refactor vector handling system in `src/codeweaver/providers/types/vectors.py` to:
1. Remove "lazy" flag and model-based naming
2. Align directly with Qdrant's VectorParams and SparseVectorParams
3. Support arbitrary numbers of vectors per point (future-proofing for multi-strategy)
4. Use role-based naming instead of model-based naming

## Goals

- ✅ Remove hardcoded assumptions about vector count (dense + sparse only)
- ✅ Eliminate confusing "lazy" flag
- ✅ Align types with Qdrant's native types for trivial conversion
- ✅ Use role-based physical vector names (e.g., "primary", "backup", "sparse")
- ✅ Support extensible VectorRole enum using BaseEnum
- ✅ Prepare for multiple vectors per point for different search strategies

## Type Specifications

### Qdrant Type Alignment

**VectorParams** (from qdrant_client.models):
- Required: `size: int`, `distance: Distance`
- Optional: `hnsw_config`, `quantization_config`, `on_disk`, `datatype`, `multivector_config`

**SparseVectorParams** (from qdrant_client.models):
- Optional: `index: SparseIndexParams | None`, `modifier: Modifier | None`

### CodeWeaver Type Requirements

- Use `ModelName` NewType and `ModelNameT` annotated type from `codeweaver.core.types`
- Use `BaseEnum` for VectorRole with `.variable` property for string conversion
- Use `BasedModel` from `codeweaver.core.types` for all models
- Make configuration objects immutable with `frozen=True`

## Implementation Steps

### Phase 1: Core Type Definitions

**File**: `src/codeweaver/providers/types/vectors.py`

#### 1.1 Define VectorRole Enum

```python
from codeweaver.core.types import BaseEnum

class VectorRole(BaseEnum):
    """Semantic roles for vectors (extensible for future strategies).

    The enum values should match common physical vector names by default.
    Use .variable property to get snake_case string representation.
    """
    PRIMARY = "primary"
    BACKUP = "backup"
    SPARSE = "sparse"
    # Future extensions:
    # SEMANTIC_CODE = "semantic_code"
    # SEMANTIC_DOCS = "semantic_docs"
    # KEYWORD = "keyword"
```

**Notes**:
- Use `BaseEnum` (not standard `Enum`)
- Values are lowercase strings matching intended physical names
- Access string form via `.variable` property: `VectorRole.PRIMARY.variable` → "primary"
- Extensible for future search strategies

#### 1.2 Define VectorConfig

```python
from typing import Annotated
from pydantic import Field
from qdrant_client.models import VectorParams, SparseVectorParams
from codeweaver.core.types import BasedModel, ModelName, ModelNameT, EmbeddingKind

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
        ...     role=VectorRole.PRIMARY
        ... )
    """

    name: Annotated[
        str,
        Field(
            description="Physical Qdrant vector name (purpose-based, e.g., 'primary', 'backup')",
            pattern=r"^[a-z][a-z0-9_]*$",
            min_length=1,
            max_length=50,
        )
    ]

    model_name: Annotated[
        ModelNameT,
        Field(description="Model used to generate this vector")
    ]

    params: Annotated[
        VectorParams | SparseVectorParams,
        Field(description="Direct Qdrant vector parameters")
    ]

    role: Annotated[
        VectorRole | str | None,
        Field(
            default=None,
            description="Optional semantic role (defaults to name)"
        )
    ] = None

    def __init__(self, **data):
        """Initialize VectorConfig with role defaulting to name."""
        super().__init__(**data)
        # Default role to name if not provided
        if self.role is None:
            # Use object.__setattr__ because frozen=True
            object.__setattr__(self, 'role', self.name)

    # Properties

    @property
    def kind(self) -> EmbeddingKind:
        """Infer embedding kind from params type.

        Returns:
            EmbeddingKind.DENSE for VectorParams
            EmbeddingKind.SPARSE for SparseVectorParams
        """
        return (
            EmbeddingKind.DENSE
            if isinstance(self.params, VectorParams)
            else EmbeddingKind.SPARSE
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
            >>> collection_config = CollectionParams(
            ...     vectors_config={name: params}
            ... )
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
            ...     settings,
            ...     name="primary",
            ...     role=VectorRole.PRIMARY
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
            role=role or name  # Default role to name
        )
```

**Critical Requirements**:
- ✅ `frozen=True` for immutability
- ✅ Direct VectorParams/SparseVectorParams (not wrapped/discriminated)
- ✅ ModelNameT type from core.types
- ✅ Name is REQUIRED in from_provider_settings (no auto-generation)
- ✅ Role-based naming (purpose, not model)
- ✅ Role defaults to name if not provided
- ✅ Trivial conversion via to_qdrant_config()

#### 1.3 Define VectorSet

```python
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
        Field(description="Vector configurations keyed by logical identifier")
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
        role_str = role.variable if isinstance(role, VectorRole) else role
        return [v for v in self.vectors.values() if v.role == role_str]

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
            >>> config = CollectionParams(
            ...     vectors_config=vector_set.to_qdrant_vectors_config()
            ... )
        """
        return {
            v.name: v.params
            for v in self.vectors.values()
            if v.is_dense
        }

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
        return {
            v.name: v.params
            for v in self.vectors.values()
            if v.is_sparse
        }

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
                role=VectorRole.PRIMARY
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
                role=VectorRole.BACKUP
            )

        # Sparse (optional)
        if profile.sparse_embedding and profile.sparse_embedding[0]:
            vectors["sparse"] = await VectorConfig.from_provider_settings(
                profile.sparse_embedding[0],
                name="sparse",  # Role-based physical name
                role=VectorRole.SPARSE
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
```

**Critical Requirements**:
- ✅ `frozen=True` for immutability
- ✅ Validates physical vector name uniqueness in `__init__`
- ✅ Uses `.variable` property when converting VectorRole to string
- ✅ Flexible dict[str, VectorConfig] supports arbitrary vectors
- ✅ Query methods: by_role(), by_name(), by_key()
- ✅ Convenience methods: primary(), backup(), sparse()
- ✅ Trivial Qdrant conversion methods
- ✅ Role-based naming in factory methods

### Phase 2: Migration and Deprecation

#### 2.1 Mark Old Types as Deprecated

Add deprecation warnings to existing types:

```python
import warnings
from typing_extensions import deprecated

@deprecated("VectorStrategy is deprecated, use VectorConfig instead")
class VectorStrategy(BasedModel):
    """DEPRECATED: Use VectorConfig instead.

    This class will be removed in the next major release.
    """
    ...

@deprecated("EmbeddingStrategy is deprecated, use VectorSet instead")
class EmbeddingStrategy(BasedModel):
    """DEPRECATED: Use VectorSet instead.

    This class will be removed in the next major release.
    """
    ...
```

#### 2.2 Add Conversion Utilities (Temporary)

```python
# Conversion helpers for migration period
def vector_strategy_to_config(strategy: VectorStrategy) -> VectorConfig:
    """Convert old VectorStrategy to new VectorConfig.

    WARNING: This is a temporary migration helper.
    """
    # Infer role-based name from old hardcoded patterns
    name = "primary"  # Default
    role = VectorRole.PRIMARY

    # Try to infer from context (this is imperfect)
    model_str = str(strategy.model_name).lower()
    if "backup" in model_str or model_str.startswith("jina"):
        name = "backup"
        role = VectorRole.BACKUP
    elif strategy.kind == EmbeddingKind.SPARSE:
        name = "sparse"
        role = VectorRole.SPARSE

    return VectorConfig(
        name=name,
        model_name=strategy.model_name,
        params=strategy.params,
        role=role
    )

def embedding_strategy_to_vector_set(strategy: EmbeddingStrategy) -> VectorSet:
    """Convert old EmbeddingStrategy to new VectorSet.

    WARNING: This is a temporary migration helper.
    """
    vectors = {}
    for key, vec_strategy in strategy.vectors.items():
        vector_config = vector_strategy_to_config(vec_strategy)
        # Use original key, but vector has role-based physical name
        vectors[key] = vector_config

    return VectorSet(vectors=vectors)
```

#### 2.3 Update Consumers

**Files to update**:
1. `src/codeweaver/providers/vector_stores/base.py`
2. `src/codeweaver/providers/vector_stores/qdrant_base.py`
3. `src/codeweaver/providers/vector_stores/qdrant.py`
4. `src/codeweaver/providers/vector_stores/inmemory.py`
5. `src/codeweaver/engine/indexer/indexer.py`
6. `src/codeweaver/agent_api/find_code/pipeline.py`
7. Any other files importing VectorStrategy or EmbeddingStrategy

**Update pattern**:
```python
# Old
from codeweaver.providers.types.vectors import VectorStrategy, EmbeddingStrategy

# New
from codeweaver.providers.types.vectors import VectorConfig, VectorSet, VectorRole
```

### Phase 3: Vector Store Integration

#### 3.1 Update Collection Configuration

**File**: `src/codeweaver/providers/vector_stores/qdrant_base.py`

Update collection creation to use VectorSet:

```python
async def create_collection(
    self,
    collection_name: str,
    vector_set: VectorSet,
    **kwargs
) -> None:
    """Create Qdrant collection with vectors from VectorSet.

    Args:
        collection_name: Name of the collection
        vector_set: VectorSet containing vector configurations
        **kwargs: Additional collection parameters
    """
    from qdrant_client.models import CollectionParams

    # Trivial conversion from VectorSet
    params = CollectionParams(
        vectors_config=vector_set.to_qdrant_vectors_config(),
        sparse_vectors_config=vector_set.to_qdrant_sparse_vectors_config(),
        **kwargs
    )

    await self.client.create_collection(
        collection_name=collection_name,
        **params.model_dump(exclude_none=True)
    )
```

#### 3.2 Update Point Storage

Update point upsert to handle named vectors:

```python
async def upsert_points(
    self,
    collection_name: str,
    points: list[PointStruct],
    vector_set: VectorSet,
) -> None:
    """Upsert points with vectors.

    Args:
        collection_name: Name of the collection
        points: Points to upsert
        vector_set: VectorSet defining expected vectors
    """
    # Validate points have all required vectors
    expected_names = {v.name for v in vector_set.vectors.values()}

    for point in points:
        point_vectors = set(point.vector.keys())
        missing = expected_names - point_vectors
        if missing:
            logger.warning(
                "Point %s missing vectors: %s",
                point.id,
                missing
            )

    await self.client.upsert(
        collection_name=collection_name,
        points=points
    )
```

#### 3.3 Backup Vector Reconciliation

Add method to check and generate missing backup vectors:

```python
async def reconcile_vectors(
    self,
    collection_name: str,
    vector_set: VectorSet,
) -> dict[str, int]:
    """Reconcile missing vectors on points.

    Identifies points missing expected vectors and returns
    statistics about what needs to be generated.

    Args:
        collection_name: Name of the collection
        vector_set: Expected vector configuration

    Returns:
        Dict mapping vector names to count of missing points
    """
    expected_names = {v.name for v in vector_set.vectors.values()}
    missing_counts = {name: 0 for name in expected_names}

    # Scroll through all points
    offset = None
    while True:
        points, offset = await self.client.scroll(
            collection_name=collection_name,
            offset=offset,
            limit=100,
            with_vectors=False  # Just need to check keys
        )

        for point in points:
            point_vectors = set(point.vector.keys())
            for name in expected_names:
                if name not in point_vectors:
                    missing_counts[name] += 1

        if offset is None:
            break

    return missing_counts
```

### Phase 4: Remove Old Types

After all consumers are updated:

1. Delete `VectorStrategy` class
2. Delete `EmbeddingStrategy` class
3. Delete `VectorNames` class (or simplify if still useful)
4. Delete conversion utility functions
5. Update all imports

### Phase 5: Testing

#### 5.1 Unit Tests

**File**: `tests/unit/providers/types/test_vectors.py`

```python
import pytest
from qdrant_client.models import VectorParams, SparseVectorParams
from codeweaver.core.types import ModelName
from codeweaver.providers.types.vectors import (
    VectorConfig,
    VectorRole,
    VectorSet,
)


class TestVectorRole:
    """Test VectorRole enum."""

    def test_variable_property(self):
        """Test .variable property returns snake_case string."""
        assert VectorRole.PRIMARY.variable == "primary"
        assert VectorRole.BACKUP.variable == "backup"
        assert VectorRole.SPARSE.variable == "sparse"

    def test_extensibility(self):
        """Test that new roles can be added."""
        # Future roles should work the same way
        # This test documents the extension pattern
        pass


class TestVectorConfig:
    """Test VectorConfig model."""

    def test_creation_dense(self):
        """Test creating dense VectorConfig."""
        config = VectorConfig(
            name="primary",
            model_name=ModelName("voyage-large-2"),
            params=VectorParams(size=1024, distance="Cosine"),
            role=VectorRole.PRIMARY
        )

        assert config.name == "primary"
        assert config.is_dense
        assert not config.is_sparse
        assert config.role == VectorRole.PRIMARY.variable

    def test_creation_sparse(self):
        """Test creating sparse VectorConfig."""
        config = VectorConfig(
            name="sparse",
            model_name=ModelName("opensearch/sparse"),
            params=SparseVectorParams(),
            role=VectorRole.SPARSE
        )

        assert config.name == "sparse"
        assert config.is_sparse
        assert not config.is_dense
        assert config.role == VectorRole.SPARSE.variable

    def test_role_defaults_to_name(self):
        """Test role defaults to name if not provided."""
        config = VectorConfig(
            name="primary",
            model_name=ModelName("voyage-large-2"),
            params=VectorParams(size=1024, distance="Cosine")
        )

        assert config.role == "primary"

    def test_immutability(self):
        """Test that VectorConfig is immutable."""
        config = VectorConfig(
            name="primary",
            model_name=ModelName("voyage-large-2"),
            params=VectorParams(size=1024, distance="Cosine")
        )

        with pytest.raises(Exception):  # Pydantic ValidationError
            config.name = "backup"

    def test_to_qdrant_config(self):
        """Test conversion to Qdrant config tuple."""
        params = VectorParams(size=1024, distance="Cosine")
        config = VectorConfig(
            name="primary",
            model_name=ModelName("voyage-large-2"),
            params=params
        )

        name, returned_params = config.to_qdrant_config()
        assert name == "primary"
        assert returned_params is params


class TestVectorSet:
    """Test VectorSet model."""

    def test_creation(self):
        """Test creating VectorSet."""
        vector_set = VectorSet(vectors={
            "primary": VectorConfig(
                name="primary",
                model_name=ModelName("voyage-large-2"),
                params=VectorParams(size=1024, distance="Cosine"),
                role=VectorRole.PRIMARY
            ),
            "sparse": VectorConfig(
                name="sparse",
                model_name=ModelName("opensearch/sparse"),
                params=SparseVectorParams(),
                role=VectorRole.SPARSE
            )
        })

        assert len(vector_set.vectors) == 2
        assert "primary" in vector_set.vectors
        assert "sparse" in vector_set.vectors

    def test_duplicate_names_rejected(self):
        """Test that duplicate physical names are rejected."""
        with pytest.raises(ValueError, match="Duplicate physical vector names"):
            VectorSet(vectors={
                "v1": VectorConfig(
                    name="primary",  # Same physical name
                    model_name=ModelName("voyage-large-2"),
                    params=VectorParams(size=1024, distance="Cosine")
                ),
                "v2": VectorConfig(
                    name="primary",  # Same physical name
                    model_name=ModelName("jina-v3"),
                    params=VectorParams(size=768, distance="Cosine")
                )
            })

    def test_query_by_role(self):
        """Test querying vectors by role."""
        vector_set = VectorSet(vectors={
            "primary": VectorConfig(
                name="primary",
                model_name=ModelName("voyage-large-2"),
                params=VectorParams(size=1024, distance="Cosine"),
                role=VectorRole.PRIMARY
            ),
            "backup": VectorConfig(
                name="backup",
                model_name=ModelName("jina-v3"),
                params=VectorParams(size=768, distance="Cosine"),
                role=VectorRole.BACKUP
            )
        })

        primaries = vector_set.by_role(VectorRole.PRIMARY)
        assert len(primaries) == 1
        assert primaries[0].name == "primary"

        backups = vector_set.by_role("backup")
        assert len(backups) == 1
        assert backups[0].name == "backup"

    def test_convenience_accessors(self):
        """Test convenience accessor methods."""
        vector_set = VectorSet(vectors={
            "primary": VectorConfig(
                name="primary",
                model_name=ModelName("voyage-large-2"),
                params=VectorParams(size=1024, distance="Cosine"),
                role=VectorRole.PRIMARY
            )
        })

        assert vector_set.primary() is not None
        assert vector_set.primary().name == "primary"
        assert vector_set.backup() is None
        assert vector_set.sparse() is None

    def test_to_qdrant_vectors_config(self):
        """Test conversion to Qdrant vectors_config."""
        vector_set = VectorSet(vectors={
            "primary": VectorConfig(
                name="primary",
                model_name=ModelName("voyage-large-2"),
                params=VectorParams(size=1024, distance="Cosine"),
                role=VectorRole.PRIMARY
            ),
            "backup": VectorConfig(
                name="backup",
                model_name=ModelName("jina-v3"),
                params=VectorParams(size=768, distance="Cosine"),
                role=VectorRole.BACKUP
            )
        })

        config = vector_set.to_qdrant_vectors_config()
        assert "primary" in config
        assert "backup" in config
        assert isinstance(config["primary"], VectorParams)
        assert config["primary"].size == 1024

    def test_to_qdrant_sparse_vectors_config(self):
        """Test conversion to Qdrant sparse_vectors_config."""
        vector_set = VectorSet(vectors={
            "sparse": VectorConfig(
                name="sparse",
                model_name=ModelName("opensearch/sparse"),
                params=SparseVectorParams(),
                role=VectorRole.SPARSE
            )
        })

        config = vector_set.to_qdrant_sparse_vectors_config()
        assert "sparse" in config
        assert isinstance(config["sparse"], SparseVectorParams)
```

#### 5.2 Integration Tests

Test with actual Qdrant client:

```python
@pytest.mark.integration
async def test_collection_creation_with_vector_set():
    """Test creating Qdrant collection from VectorSet."""
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import CollectionParams

    vector_set = VectorSet(vectors={
        "primary": VectorConfig(
            name="primary",
            model_name=ModelName("voyage-large-2"),
            params=VectorParams(size=1024, distance="Cosine")
        ),
        "sparse": VectorConfig(
            name="sparse",
            model_name=ModelName("opensearch/sparse"),
            params=SparseVectorParams()
        )
    })

    client = AsyncQdrantClient(":memory:")

    await client.create_collection(
        collection_name="test_collection",
        vectors_config=vector_set.to_qdrant_vectors_config(),
        sparse_vectors_config=vector_set.to_qdrant_sparse_vectors_config()
    )

    # Verify collection was created correctly
    collection_info = await client.get_collection("test_collection")
    assert "primary" in collection_info.config.params.vectors
    assert "sparse" in collection_info.config.params.sparse_vectors
```

## Migration Checklist

- [ ] Phase 1: Implement core types (VectorRole, VectorConfig, VectorSet)
- [ ] Phase 2: Add deprecation warnings to old types
- [ ] Phase 2: Create temporary conversion utilities
- [ ] Phase 2: Update vector store providers
- [ ] Phase 2: Update indexing service
- [ ] Phase 2: Update search pipeline
- [ ] Phase 2: Update any other consumers
- [ ] Phase 3: Integrate with backup system
- [ ] Phase 3: Add vector reconciliation methods
- [ ] Phase 4: Remove old types (VectorStrategy, EmbeddingStrategy, VectorNames)
- [ ] Phase 5: Write comprehensive unit tests
- [ ] Phase 5: Write integration tests
- [ ] Phase 5: Update documentation

## Benefits Summary

1. ✅ **Removes "lazy" flag** - no more confusing hardcoded logic
2. ✅ **Role-based naming** - physical names reflect purpose, not implementation
3. ✅ **Qdrant alignment** - trivial conversion to Qdrant types
4. ✅ **Future-proof** - supports arbitrary numbers of vectors
5. ✅ **Type safety** - immutable, validated configurations
6. ✅ **Extensible** - VectorRole enum can grow with new strategies
7. ✅ **Flexible queries** - by_role(), by_name(), by_key() methods
8. ✅ **Simpler mental model** - VectorConfig ≈ Qdrant named vector + minimal metadata

## Breaking Changes

- `VectorStrategy` → `VectorConfig`
- `EmbeddingStrategy` → `VectorSet`
- "lazy" flag removed entirely
- Model-based vector names → role-based vector names
- `from_provider_settings()` requires explicit `name` parameter

## Backward Compatibility

- Deprecation warnings for one release cycle
- Temporary conversion utilities during migration
- Factory methods maintain similar API patterns

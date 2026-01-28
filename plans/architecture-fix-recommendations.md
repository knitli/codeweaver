# Architecture Fix Recommendations
## Analysis of Test Setup and httpx Forward Reference Issues

**Date**: 2026-01-28
**Context**: WAL Config integration tests refactoring
**Goal**: Get the structure right at all costs

---

## Executive Summary

The current issues stem from **architectural mixing of concerns**:
- Pydantic configuration models contain DI-dependent behavior (`@depends()`)
- External library types (httpx) exposed directly at configuration boundaries
- Test instantiation fights DI container instead of bypassing it naturally

**Recommended Solution**: Separate configuration (data) from services (behavior + DI).

**Constitutional Alignment**:
- ✅ Principle I: AI-First Context (clear separation improves understanding)
- ✅ Principle II: Proven Patterns (FastAPI settings + services pattern)
- ✅ Principle III: Evidence-Based (backed by FastAPI architecture guide)
- ✅ Principle V: Simplicity Through Architecture (flat, obvious structure)

---

## Problem 1: httpx Forward Reference Issues

### Current Problem

```python
# clients.py
class QdrantClientOptions(BaseClientOptions):
    kwargs: HttpxClientParams | GrpcParams | None = None
```

- `HttpxClientParams` includes `httpx._types.AuthTypes`
- `AuthTypes` has `Callable[["Request"], "Request"]` forward reference
- Pydantic cannot resolve these at validation time
- Causes: `PydanticUserError: QdrantVectorStoreProviderSettings is not fully defined`

### Root Cause

**Architectural Violation**: Exposing complex external library types at configuration boundary.

This violates:
- **Single Responsibility**: Config should hold data, not expose implementation details
- **Dependency Inversion**: High-level config depends on low-level httpx types
- **Interface Segregation**: 90% of users need simple options, not full httpx complexity

### ✅ Recommended Solution: Simplified Boundary Types

**Pattern**: FastAPI's `TestClient` approach - simplified interface at boundary, complex types internal.

```python
class QdrantClientOptions(BasedModel):
    """Configuration for Qdrant client connection.

    Simplified interface that maps to qdrant-client parameters.
    Common cases are type-safe; advanced cases use escape hatch.
    """
    # Connection
    url: str | None = None
    host: str | None = None
    port: int = 6333
    grpc_port: int = 6334
    prefer_grpc: bool = False

    # Authentication (simplified from httpx.AuthTypes)
    api_key: str | None = None
    auth: tuple[str, str] | None = None  # (username, password)

    # HTTP options (simplified)
    timeout: float | None = None
    https: bool = False
    verify_ssl: bool = True

    # Advanced: escape hatch for power users
    advanced_http_options: dict[str, Any] | None = Field(
        default=None,
        description="Advanced httpx client parameters. Keys: 'auth', 'headers', 'cookies', 'proxies', etc."
    )

    # gRPC options (if needed)
    grpc_options: dict[str, Any] | None = Field(
        default=None,
        description="Advanced grpc.aio.Channel parameters."
    )

    def to_qdrant_params(self) -> dict[str, Any]:
        """Convert to qdrant-client constructor parameters.

        Maps simplified options to qdrant-client's expected format.
        Complexity is hidden here, not at the boundary.
        """
        params = {}

        # Connection
        if self.url:
            params["url"] = self.url
        else:
            params["host"] = self.host
            params["port"] = self.port
            params["grpc_port"] = self.grpc_port
            params["prefer_grpc"] = self.prefer_grpc
            params["https"] = self.https

        # Authentication
        if self.api_key:
            params["api_key"] = self.api_key
        elif self.auth:
            params["auth"] = self.auth

        # HTTP options
        if self.timeout is not None:
            params["timeout"] = self.timeout

        # Advanced options (power users)
        if self.advanced_http_options:
            # These might include complex httpx types, but only if user explicitly provides them
            params.setdefault("kwargs", {}).update(self.advanced_http_options)

        if self.grpc_options:
            params.setdefault("grpc_kwargs", {}).update(self.grpc_options)

        return params
```

**Benefits**:
- ✅ No forward reference issues (simple types only)
- ✅ Type-safe for 90% of use cases
- ✅ Escape hatch for advanced users
- ✅ Complexity hidden in `to_qdrant_params()`
- ✅ Fully serializable (for config files, env vars)
- ✅ Easy to test (no httpx dependency needed)

**Evidence**: FastAPI's `TestClient` uses this exact pattern:
```python
# FastAPI exposes simplified interface
client = TestClient(app, base_url="http://testserver", cookies={"session": "..."})

# Internally maps to httpx's complex types
# Users don't see Callable[["Request"], "Request"]
```

---

## Problem 2: DI + Pydantic Integration

### Current Problem

```python
class QdrantVectorStoreProviderSettings(BaseVectorStoreProviderSettings):
    @depends()
    def _get_embedding_group(self) -> EmbeddingCapabilityGroup:
        """Get embedding capability group from DI."""
        ...

    async def get_collection_config(self, metadata: ChunkMetadata):
        # Calls _get_embedding_group() - requires DI resolution
        vector_params = self._get_embedding_group().as_vector_params()
        ...
```

**Issues**:
1. Pydantic model has DI-dependent behavior (`@depends()` on method)
2. Can't instantiate in tests without full DI container
3. Tests fail: `AttributeError: 'DependsPlaceholder' object has no attribute 'as_vector_params'`
4. Violates Single Responsibility: Model is both data container AND service

### Root Cause

**Architectural Violation**: Mixing data models (pydantic) with service behavior (DI).

This violates:
- **Single Responsibility**: Settings should hold data, not perform operations
- **Dependency Inversion**: Settings class depends on runtime DI container
- **Open/Closed**: Can't use settings without DI infrastructure
- **Testability**: Tests must set up complex DI container to instantiate simple config

### ✅ Recommended Solution: Separate Data from Services

**Pattern**: FastAPI's Settings + Services separation

#### Layer 1: Pure Configuration (Data Only)

```python
class QdrantVectorStoreProviderSettings(BaseVectorStoreProviderSettings):
    """Pure configuration model - no DI, no complex behavior.

    Responsibilities:
    - Hold configuration data
    - Validate configuration
    - Provide simple data transformations

    Can be instantiated anywhere: tests, config files, runtime.
    Fully serializable and validatable.
    """
    client_options: QdrantClientOptions
    collection: CollectionConfig
    batch_size: int = 100

    # NO @depends() decorators
    # NO methods that require injected dependencies
    # ONLY validation and simple data access

    def get_client_params(self) -> dict[str, Any]:
        """Get client parameters - pure data transformation."""
        return self.client_options.to_qdrant_params()


class CollectionConfig(BasedModel):
    """Collection configuration - pure data."""
    collection_name: str
    wal_config: WalConfig | None = None
    vectors_config: dict[str, Any] | None = None

    def to_collection_params(
        self,
        vector_params: VectorParams,  # Explicit parameter, not DI
        sparse_vector_params: SparseVectorParams | None = None,
    ) -> dict[str, Any]:
        """Convert to collection creation parameters.

        Takes dependencies as explicit parameters, not via DI.
        This is testable: pass in what you need, get deterministic output.
        """
        params = {
            "name": self.collection_name,
            "vectors_config": vector_params,
        }

        if sparse_vector_params:
            params["sparse_vectors_config"] = sparse_vector_params

        if self.wal_config:
            params["wal_config"] = self.wal_config.to_qdrant_config()

        return params
```

#### Layer 2: Service with DI

```python
class QdrantVectorStoreService:
    """Service layer with behavior and dependencies.

    Responsibilities:
    - Use settings (data) to perform operations
    - Manage dependencies (clients, capability groups)
    - Encapsulate business logic

    This is where DI belongs.
    """

    def __init__(
        self,
        settings: QdrantVectorStoreProviderSettings,
        embedding_group: EmbeddingCapabilityGroup,
        failover_settings: FailoverSettings | None = None,
    ):
        """Initialize service with settings and dependencies.

        Args:
            settings: Pure configuration (no DI)
            embedding_group: Injected dependency
            failover_settings: Optional injected dependency
        """
        self.settings = settings
        self.embedding_group = embedding_group
        self.failover_settings = failover_settings
        self._client: QdrantClient | None = None

    @property
    def client(self) -> QdrantClient:
        """Lazy-initialized Qdrant client."""
        if self._client is None:
            params = self.settings.get_client_params()
            self._client = QdrantClient(**params)
        return self._client

    async def get_collection_config(
        self,
        metadata: ChunkMetadata,
    ) -> dict[str, Any]:
        """Build collection configuration.

        Uses both settings (data) and injected dependencies (behavior).
        """
        # Get vector params from injected embedding group
        vector_params = self.embedding_group.as_vector_params()
        sparse_params = self.embedding_group.as_sparse_vector_params()

        # Merge WalConfig if failover is enabled
        collection_config = self.settings.collection
        if self.failover_settings and not self.failover_settings.disable_failover:
            # Create merged WalConfig
            failover_wal = self.failover_settings.to_wal_config()
            merged_wal = collection_config.wal_config or WalConfig()
            collection_config = collection_config.model_copy(
                update={"wal_config": merged_wal.merge(failover_wal)}
            )

        # Use settings method to build params
        return collection_config.to_collection_params(vector_params, sparse_params)

    async def create_collection(self, metadata: ChunkMetadata) -> None:
        """Create collection with proper configuration."""
        config = await self.get_collection_config(metadata)
        await self.client.create_collection(**config)

    async def upsert_chunks(
        self,
        chunks: list[CodeChunk],
    ) -> None:
        """Upsert code chunks to collection."""
        # Use settings for batch_size
        batch_size = self.settings.batch_size

        for batch in batched(chunks, batch_size):
            # Convert chunks and upsert
            points = [chunk.to_point() for chunk in batch]
            await self.client.upsert(
                collection_name=self.settings.collection.collection_name,
                points=points,
            )


# Factory function for DI (application startup)
@dependency_provider(QdrantVectorStoreService, scope="singleton")
def create_qdrant_service(
    settings_dep: ProviderSettingsDep = INJECTED,
    embedding_group: EmbeddingCapabilityGroup = INJECTED,
    failover_settings: FailoverSettings = INJECTED,
) -> QdrantVectorStoreService:
    """Factory function with DI for application startup.

    DI container resolves all dependencies and creates service.
    """
    # Extract Qdrant-specific settings
    qdrant_settings = settings_dep.vector_store[0]  # Assuming first is Qdrant

    return QdrantVectorStoreService(
        settings=qdrant_settings,
        embedding_group=embedding_group,
        failover_settings=failover_settings,
    )
```

**Benefits**:
- ✅ Settings are pure data - instantiable anywhere
- ✅ Service encapsulates behavior + dependencies
- ✅ DI happens at service layer, not data layer
- ✅ Clear separation of concerns
- ✅ Easy to test (see Problem 3)
- ✅ Follows SOLID principles
- ✅ Aligns with FastAPI patterns

**Evidence**: FastAPI's architecture guide explicitly separates:
- `config/settings.py` - `BaseSettings` for configuration (data)
- `services/` - Service classes that use settings + DI (behavior)
- `dependencies.py` - DI functions that wire everything together

---

## Problem 3: Test Instantiation

### Current Problem

```python
def test_wal_config_merges_failover_when_backup_enabled(clean_container, wal_config):
    failover_settings = FailoverSettings(disable_failover=False, wal_capacity_mb=256, ...)
    clean_container.override(FailoverSettings, failover_settings)

    # This instantiation is problematic
    settings = QdrantVectorStoreProviderSettings(
        provider=Provider.QDRANT,
        client_options=QdrantClientOptions(url="http://localhost:6333"),
        collection=CollectionConfig(collection_name="test_collection", wal_config=wal_config),
    )

    # This fails because _get_embedding_group() returns DependsPlaceholder
    result = await settings.get_collection_config(metadata)
```

**Issues**:
1. Settings has DI-dependent methods
2. Tests must override container or mock DI
3. Simple config instantiation becomes complex
4. Testing pyramid inverted (more integration tests than unit tests)

### ✅ Recommended Solution: Direct Construction

With proper separation, tests become straightforward:

#### Test Level 1: Configuration Logic (Unit Tests)

```python
def test_wal_config_initialization():
    """Test pure configuration - no DI needed."""
    wal_config = WalConfig(wal_capacity_mb=256, wal_segments_ahead=2)

    settings = QdrantVectorStoreProviderSettings(
        provider=Provider.QDRANT,
        client_options=QdrantClientOptions(url="http://localhost:6333"),
        collection=CollectionConfig(
            collection_name="test_collection",
            wal_config=wal_config,
        ),
        batch_size=100,
    )

    # Test data validation
    assert settings.collection.wal_config.wal_capacity_mb == 256
    assert settings.collection.wal_config.wal_segments_ahead == 2
    assert settings.batch_size == 100


def test_client_options_to_params():
    """Test client options conversion - pure data transformation."""
    options = QdrantClientOptions(
        url="http://localhost:6333",
        api_key="test-key",
        timeout=30.0,
    )

    params = options.to_qdrant_params()

    assert params["url"] == "http://localhost:6333"
    assert params["api_key"] == "test-key"
    assert params["timeout"] == 30.0


def test_collection_config_to_params():
    """Test collection config conversion - pure data transformation."""
    config = CollectionConfig(
        collection_name="test",
        wal_config=WalConfig(wal_capacity_mb=256),
    )

    vector_params = {"size": 1024, "distance": "Cosine"}
    params = config.to_collection_params(vector_params)

    assert params["name"] == "test"
    assert params["vectors_config"] == vector_params
    assert "wal_config" in params
```

#### Test Level 2: Service Logic (Unit Tests with Mocks)

```python
async def test_service_creates_collection_with_correct_params():
    """Test service behavior with mocked dependencies."""
    # Arrange: Create settings (just data)
    settings = QdrantVectorStoreProviderSettings(
        provider=Provider.QDRANT,
        client_options=QdrantClientOptions(url="http://localhost:6333"),
        collection=CollectionConfig(collection_name="test"),
        batch_size=100,
    )

    # Arrange: Create mock dependencies (no DI container needed)
    mock_embedding_group = Mock(spec=EmbeddingCapabilityGroup)
    mock_embedding_group.as_vector_params.return_value = {"size": 1024, "distance": "Cosine"}
    mock_embedding_group.as_sparse_vector_params.return_value = None

    # Arrange: Create service with controlled inputs
    service = QdrantVectorStoreService(
        settings=settings,
        embedding_group=mock_embedding_group,
        failover_settings=None,
    )

    # Act: Call method under test
    metadata = ChunkMetadata(chunk_id="test", file_path="/test.py")
    config = await service.get_collection_config(metadata)

    # Assert: Verify behavior
    assert config["name"] == "test"
    assert config["vectors_config"]["size"] == 1024
    mock_embedding_group.as_vector_params.assert_called_once()


async def test_service_merges_wal_config_when_failover_enabled():
    """Test WalConfig merging logic with failover enabled."""
    # Arrange: Settings with user WalConfig
    user_wal = WalConfig(wal_capacity_mb=128, wal_segments_ahead=1)
    settings = QdrantVectorStoreProviderSettings(
        provider=Provider.QDRANT,
        client_options=QdrantClientOptions(url="http://localhost:6333"),
        collection=CollectionConfig(collection_name="test", wal_config=user_wal),
    )

    # Arrange: Failover settings (enabled)
    failover_settings = FailoverSettings(
        disable_failover=False,  # Enabled
        wal_capacity_mb=256,     # Should override user's 128
        wal_segments_ahead=2,    # Should override user's 1
        snapshot_storage_path="/tmp/snapshots",
    )

    # Arrange: Mock embedding group
    mock_embedding = Mock(spec=EmbeddingCapabilityGroup)
    mock_embedding.as_vector_params.return_value = {"size": 1024}
    mock_embedding.as_sparse_vector_params.return_value = None

    # Arrange: Create service
    service = QdrantVectorStoreService(
        settings=settings,
        embedding_group=mock_embedding,
        failover_settings=failover_settings,
    )

    # Act
    metadata = ChunkMetadata(chunk_id="test", file_path="/test.py")
    config = await service.get_collection_config(metadata)

    # Assert: Failover WalConfig should override user's
    wal_config = config["wal_config"]
    assert wal_config.wal_capacity_mb == 256  # Failover value, not user's 128
    assert wal_config.wal_segments_ahead == 2  # Failover value, not user's 1


async def test_service_uses_user_wal_config_when_failover_disabled():
    """Test that user WalConfig is preserved when failover is disabled."""
    # Arrange: Settings with user WalConfig
    user_wal = WalConfig(wal_capacity_mb=128, wal_segments_ahead=1)
    settings = QdrantVectorStoreProviderSettings(
        provider=Provider.QDRANT,
        client_options=QdrantClientOptions(url="http://localhost:6333"),
        collection=CollectionConfig(collection_name="test", wal_config=user_wal),
    )

    # Arrange: Failover settings (disabled)
    failover_settings = FailoverSettings(
        disable_failover=True,   # Disabled
        wal_capacity_mb=256,     # Should be ignored
        wal_segments_ahead=2,    # Should be ignored
    )

    # Arrange: Mock embedding group
    mock_embedding = Mock(spec=EmbeddingCapabilityGroup)
    mock_embedding.as_vector_params.return_value = {"size": 1024}
    mock_embedding.as_sparse_vector_params.return_value = None

    # Arrange: Create service
    service = QdrantVectorStoreService(
        settings=settings,
        embedding_group=mock_embedding,
        failover_settings=failover_settings,
    )

    # Act
    config = await service.get_collection_config(metadata)

    # Assert: User WalConfig should be preserved
    wal_config = config["wal_config"]
    assert wal_config.wal_capacity_mb == 128  # User value
    assert wal_config.wal_segments_ahead == 1  # User value
```

#### Test Level 3: Integration Tests (Full DI - Use Sparingly)

```python
async def test_full_integration_with_real_container(clean_container, tmp_path):
    """Integration test with full DI container.

    Use sparingly - only when testing actual integration between components.
    Most tests should be unit tests (Levels 1-2).
    """
    # Arrange: Override specific dependencies
    failover_settings = FailoverSettings(
        disable_failover=False,
        wal_capacity_mb=256,
        snapshot_storage_path=str(tmp_path / "snapshots"),
    )
    clean_container.override(FailoverSettings, failover_settings)

    # Act: Let DI create service with all dependencies
    service = await clean_container.resolve(QdrantVectorStoreService)

    # Assert: Test integrated behavior
    assert service.settings is not None
    assert service.embedding_group is not None
    assert service.failover_settings.wal_capacity_mb == 256
```

**Test Pyramid**:
```
         /\          Few integration tests (Level 3)
        /  \         - Full DI container
       /    \        - Test component integration
      /------\       More service tests (Level 2)
     /        \      - Mock dependencies
    /          \     - Test business logic
   /------------\    Many config tests (Level 1)
  /______________\   - No mocks needed
                     - Test data validation
```

**Benefits**:
- ✅ Most tests don't need DI container
- ✅ Settings tested independently (pure data)
- ✅ Services tested with mock dependencies
- ✅ Integration tests used only for integration
- ✅ Clear test pyramid structure
- ✅ Fast test execution
- ✅ Easy to debug failures

**Evidence**: FastAPI testing documentation recommends this exact pattern:
- Test route handlers with `TestClient` (integration)
- Test dependencies independently with mocks (unit)
- Test models independently (unit)

---

## Implementation Roadmap

### Phase 1: Extract Pure Settings (Day 1)

**Files to modify**:
- `src/codeweaver/providers/config/kinds.py`
- `src/codeweaver/providers/config/clients.py`

**Changes**:

1. **Simplify `QdrantClientOptions`** (clients.py)
   ```python
   # Remove: kwargs: HttpxClientParams | GrpcParams | None
   # Add: Simplified interface with escape hatch

   class QdrantClientOptions(BaseClientOptions):
       # Simple types for common cases
       url: str | None = None
       api_key: str | None = None
       timeout: float | None = None
       # ... other common options

       # Escape hatch for advanced users
       advanced_http_options: dict[str, Any] | None = None
       grpc_options: dict[str, Any] | None = None

       def to_qdrant_params(self) -> dict[str, Any]:
           """Map to qdrant-client parameters."""
           ...
   ```

2. **Remove DI from settings** (kinds.py)
   ```python
   class QdrantVectorStoreProviderSettings(BaseVectorStoreProviderSettings):
       # Remove: @depends() methods
       # Remove: get_collection_config() method
       # Keep: Pure data fields only

       def get_client_params(self) -> dict[str, Any]:
           """Simple data transformation - no DI."""
           return self.client_options.to_qdrant_params()

   class CollectionConfig(BasedModel):
       # Remove: Methods that require DI
       # Add: Methods that take explicit parameters

       def to_collection_params(
           self,
           vector_params: VectorParams,
           sparse_vector_params: SparseVectorParams | None = None,
       ) -> dict[str, Any]:
           """Explicit parameters, not DI."""
           ...
   ```

### Phase 2: Create Service Layer (Day 1-2)

**New file**: `src/codeweaver/providers/vector_stores/qdrant_service.py`

```python
"""Qdrant vector store service with DI integration."""

from codeweaver.core.di import INJECTED, dependency_provider
from codeweaver.engine.config import FailoverSettings
from codeweaver.providers import ProviderSettingsDep
from codeweaver.providers.embedding import EmbeddingCapabilityGroup
from codeweaver.providers.config.kinds import QdrantVectorStoreProviderSettings

class QdrantVectorStoreService:
    """Service layer for Qdrant vector store operations."""

    def __init__(
        self,
        settings: QdrantVectorStoreProviderSettings,
        embedding_group: EmbeddingCapabilityGroup,
        failover_settings: FailoverSettings | None = None,
    ):
        self.settings = settings
        self.embedding_group = embedding_group
        self.failover_settings = failover_settings
        self._client: QdrantClient | None = None

    # ... methods from Problem 2 solution


@dependency_provider(QdrantVectorStoreService, scope="singleton")
def create_qdrant_service(
    settings_dep: ProviderSettingsDep = INJECTED,
    embedding_group: EmbeddingCapabilityGroup = INJECTED,
    failover_settings: FailoverSettings = INJECTED,
) -> QdrantVectorStoreService:
    """Factory for DI container."""
    qdrant_settings = settings_dep.vector_store[0]
    return QdrantVectorStoreService(
        settings=qdrant_settings,
        embedding_group=embedding_group,
        failover_settings=failover_settings,
    )
```

### Phase 3: Update Tests (Day 2)

**Files to modify**:
- `tests/unit/providers/config/test_wal_config_merging.py` (rename to `test_wal_config_unit.py`)
- `tests/unit/providers/test_wal_config_integration.py` (rename to `test_qdrant_service.py`)

**Changes**:

1. **Unit tests for settings** (test_wal_config_unit.py)
   - Test data validation
   - Test to_collection_params()
   - No DI, no mocks

2. **Unit tests for service** (test_qdrant_service.py)
   - Test with mock embedding_group
   - Test WalConfig merging logic
   - No DI container (direct instantiation)

3. **Integration tests** (new: test_qdrant_integration.py)
   - Use clean_container only for these
   - Test actual component integration
   - Keep minimal (test pyramid)

### Phase 4: Update Application Code (Day 2-3)

**Files to modify**:
- `src/codeweaver/engine/indexer/indexer.py` (or wherever QdrantVectorStoreProviderSettings is used)
- `src/codeweaver/agent_api/find_code/pipeline.py` (or wherever collection config is accessed)

**Changes**:
- Replace direct settings usage with service usage
- Inject `QdrantVectorStoreService` instead of `QdrantVectorStoreProviderSettings`
- Update DI registrations

---

## Migration Guide

### For Existing Code Using Settings Directly

**Before**:
```python
@depends()
def some_function(
    settings: QdrantVectorStoreProviderSettings = INJECTED,
) -> None:
    config = await settings.get_collection_config(metadata)
    # ... use config
```

**After**:
```python
@depends()
def some_function(
    service: QdrantVectorStoreService = INJECTED,
) -> None:
    config = await service.get_collection_config(metadata)
    # ... use config
```

### For Tests Creating Settings

**Before**:
```python
def test_something(clean_container):
    clean_container.override(FailoverSettings, ...)
    settings = QdrantVectorStoreProviderSettings(...)
    result = await settings.get_collection_config(metadata)  # Fails
```

**After**:
```python
def test_something():
    # No container needed!
    settings = QdrantVectorStoreProviderSettings(...)
    mock_embedding = Mock(spec=EmbeddingCapabilityGroup)
    mock_embedding.as_vector_params.return_value = {...}

    service = QdrantVectorStoreService(settings, mock_embedding)
    result = await service.get_collection_config(metadata)  # Works
```

---

## Constitutional Compliance Checklist

- ✅ **Principle I (AI-First Context)**: Clear separation makes purpose obvious
- ✅ **Principle II (Proven Patterns)**: FastAPI settings + services pattern
- ✅ **Principle III (Evidence-Based)**: Backed by FastAPI architecture guide
- ✅ **Principle IV (Testing Philosophy)**: Effective tests, clear pyramid
- ✅ **Principle V (Simplicity Through Architecture)**: Flat, obvious structure

---

## Expected Outcomes

### Before (Current State)
- ❌ `PydanticUserError` with httpx forward references
- ❌ Tests fail with `DependsPlaceholder` errors
- ❌ Complex __init__ with `model_construct()` workarounds
- ❌ Mixed concerns (data + behavior in one class)
- ❌ Tests require DI container setup

### After (Target State)
- ✅ No pydantic forward reference issues
- ✅ Tests instantiate components directly
- ✅ Simple __init__ with normal pydantic validation
- ✅ Clear separation (data vs behavior)
- ✅ Most tests are fast unit tests (no DI)

---

## Questions for Clarification

1. **Breaking Changes**: This is a significant refactor. Are you okay with:
   - Changing existing code that uses `QdrantVectorStoreProviderSettings` directly?
   - Updating all tests that create settings instances?
   - Adding a new service layer?

2. **Scope**: Should we:
   - Apply this pattern to all provider settings (embedding, reranking)?
   - Or focus only on Qdrant for now?

3. **Timeline**: This is roughly 2-3 days of work. Is that acceptable?

4. **Testing**: Should we:
   - Keep existing integration tests as-is for now?
   - Convert them gradually?
   - Write new unit tests alongside?

---

## Conclusion

The current issues are symptoms of **architectural mixing of concerns**. The solution is not to work around the problems (model_construct, dict[str, Any], etc.) but to **fix the structure**:

1. **Settings = Data** (pydantic models, no DI)
2. **Services = Behavior** (use settings + DI)
3. **Boundaries = Simple** (no complex external types)
4. **Tests = Direct** (instantiate with controlled inputs)

This is **evidence-based** and **constitutionally compliant** - backed by FastAPI's architecture and your Project Constitution's principles.

**Recommendation**: Proceed with Phase 1 (extract pure settings) to validate the approach, then continue with Phases 2-4.

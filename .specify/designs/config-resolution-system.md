<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Configuration Resolution System Design

## Problem Statement

CodeWeaver has complex interdependent configuration objects that can conflict or need to agree on shared concerns:

1. **Cross-Config Dependencies**: Embedding config provides dimensionality/datatype → Vector store collection config must match
2. **Multi-Source Defaults**: Need to resolve values from: explicit config → vector store config → model capabilities → user-registered defaults
3. **Initialization Timing**: Can't resolve during `__init__` due to chicken-and-egg problems
4. **Monorepo Compatibility**: Not all config packages will be available simultaneously (selective installation)

### Example Conflict Scenario

```python
# User configures non-default embedding dimension
embedding_config = VoyageEmbeddingConfig(
    model_name="voyage-code-3",
    embedding={"output_dimension": 512}  # Non-default!
)

# Vector store config needs to know this dimension for collection setup
vector_store_config = QdrantVectorStoreProviderSettings(
    # How does it know to use dimension=512?
)
```

## Proposed Solution: DI-Integrated Config Resolution

### Core Insight

**The DI container IS the configuration registry.** Config objects register their instances in the DI container, and resolution happens by directly accessing and modifying registered instances.

### Architecture Components

#### 1. ConfigurableComponent Protocol

```python
class ConfigurableComponent(Protocol):
    """Protocol for components participating in config resolution."""

    def config_dependencies(self) -> dict[str, type]:
        """Types this config needs from DI to resolve properly."""
        ...

    def apply_resolved_config(self, **resolved: Any) -> None:
        """Apply configuration from resolved dependencies."""
        ...
```

#### 2. Component Registry

```python
# Simple module-level registry for tracking configurables
_configurable_components: list[ConfigurableComponent] = []

def register_configurable(component: ConfigurableComponent) -> None:
    """Register component for resolution."""
    ...

def get_configurable_components() -> list[ConfigurableComponent]:
    """Get all registered components."""
    ...
```

#### 3. Resolution Service

```python
@dataclass
class ConfigResolutionService:
    """Coordinates config resolution across registered components."""

    async def resolve_configs(self) -> None:
        """Resolve all configurations by pulling from DI and cross-applying."""
        container = get_container()
        configurables = get_configurable_components()

        for configurable in configurables:
            deps = configurable.config_dependencies()
            resolved = {}

            for dep_name, dep_type in deps.items():
                try:
                    resolved[dep_name] = await container.resolve(dep_type)
                except Exception:
                    continue  # Dependency not available (monorepo)

            if resolved:
                configurable.apply_resolved_config(**resolved)
```

## Implementation Details

### Phase 1: Core Infrastructure

#### File: `src/codeweaver/core/config/resolver.py`

```python
"""Configuration resolution system using DI container."""

from __future__ import annotations

from typing import Any, Protocol

from codeweaver.core.di import get_container


class ConfigurableComponent(Protocol):
    """Protocol for components participating in config resolution.

    Components implementing this protocol can:
    1. Declare what other configs they depend on
    2. Receive resolved instances and adjust their own config
    """

    def config_dependencies(self) -> dict[str, type]:
        """Return types this config needs to resolve against.

        Returns:
            Dict mapping dependency name to type from DI container.
            Example: {"embedding": EmbeddingProviderSettings}
        """
        ...

    def apply_resolved_config(self, **resolved: Any) -> None:
        """Apply resolved configuration from dependencies.

        Args:
            **resolved: Resolved dependency instances from DI container.
                       Keys match those from config_dependencies().
        """
        ...


async def resolve_all_configs() -> None:
    """Resolve all configurations across the application.

    This should be called during settings finalization, after all
    configs are initialized but before the application starts.
    """
    from codeweaver.core.config.registry import get_configurable_components

    container = get_container()
    configurables = get_configurable_components()

    for configurable in configurables:
        deps = configurable.config_dependencies()
        resolved = {}

        for dep_name, dep_type in deps.items():
            try:
                resolved[dep_name] = await container.resolve(dep_type)
            except Exception:
                # Dependency not available (monorepo - package not installed)
                continue

        if resolved:
            configurable.apply_resolved_config(**resolved)
```

#### File: `src/codeweaver/core/config/registry.py`

```python
"""Registry for configurable components."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from codeweaver.core.config.resolver import ConfigurableComponent


_configurable_components: list[ConfigurableComponent] = []


def register_configurable(component: ConfigurableComponent) -> None:
    """Register a component for config resolution.

    Args:
        component: Component implementing ConfigurableComponent protocol.
    """
    if component not in _configurable_components:
        _configurable_components.append(component)


def get_configurable_components() -> list[ConfigurableComponent]:
    """Get all registered configurable components.

    Returns:
        Copy of the registered components list.
    """
    return _configurable_components.copy()


def clear_configurables() -> None:
    """Clear all registered components.

    Primarily for testing - ensures clean state between tests.
    """
    _configurable_components.clear()
```

#### File: `src/codeweaver/core/config/defaults.py`

```python
"""User-extensible default value system."""

from collections.abc import Callable
from typing import Any


_default_providers: dict[str, list[Callable[[], Any | None]]] = {}


def register_default_provider(key: str, provider: Callable[[], Any | None]) -> None:
    """Register a default value provider for a config key.

    Providers are called in registration order. First non-None value wins.

    Args:
        key: Config key like "primary.embedding.dimension"
        provider: Callable that returns the default value or None

    Example:
        ```python
        # Register a custom default dimension
        register_default_provider(
            "primary.embedding.dimension",
            lambda: 768
        )

        # Register with conditional logic
        register_default_provider(
            "primary.embedding.datatype",
            lambda: "float16" if has_gpu() else "uint8"
        )
        ```
    """
    if key not in _default_providers:
        _default_providers[key] = []
    _default_providers[key].append(provider)


def get_default(key: str) -> Any | None:
    """Get a default value by calling registered providers.

    Args:
        key: Config key to get default for.

    Returns:
        First non-None value from registered providers, or None.
    """
    for provider in _default_providers.get(key, []):
        if (value := provider()) is not None:
            return value
    return None


def clear_defaults() -> None:
    """Clear all registered default providers.

    Primarily for testing.
    """
    _default_providers.clear()
```

### Phase 2: Embedding Config Integration

#### Updates to `src/codeweaver/providers/config/embedding.py`

```python
# Add imports
from codeweaver.core.config.resolver import ConfigurableComponent
from codeweaver.core.config.registry import register_configurable
from codeweaver.core.config.defaults import get_default


class BaseEmbeddingConfig(BasedModel, ConfigurableComponent):
    """Base configuration for embedding models."""

    # ... existing fields ...

    def __init__(self, **data: Any) -> None:
        """Initialize and register in DI container."""
        super().__init__(**data)

        # Register self in DI container as singleton
        from codeweaver.core.di import get_container
        container = get_container()

        # Use type(self) so each concrete class registers separately
        container.register(type(self), lambda: self, singleton=True)

        # Register for config resolution
        register_configurable(self)

    def config_dependencies(self) -> dict[str, type]:
        """Embedding configs don't depend on others - they provide values."""
        return {}

    def apply_resolved_config(self, **resolved: Any) -> None:
        """Nothing to apply - we're a provider, not a consumer."""
        pass

    async def get_dimension(self) -> int | None:
        """Get resolved dimension through fallback chain.

        Resolution order:
        1. Explicit config (self.embedding/self.query fields)
        2. Model capabilities (from capability resolver)
        3. User-registered defaults
        4. Hardcoded fallback

        Returns:
            Resolved dimension or None
        """
        # 1. Explicit config
        for field in ("embedding", "query"):
            if (
                (config := getattr(self, field, None))
                and (found_field := next((f for f in DIMENSION_FIELDS if f in config), None))
                and isinstance(config[found_field], int)
            ):
                return config[found_field]

        # 2. Model capabilities
        from codeweaver.core.di import get_container
        from codeweaver.providers.embedding.capabilities.dependencies import (
            EmbeddingCapabilityResolverDep
        )

        container = get_container()
        try:
            cap_resolver = await container.resolve(EmbeddingCapabilityResolverDep)
            if caps := cap_resolver.resolve(self.model_name):
                if dim := getattr(caps, 'default_dimension', None):
                    return dim
        except Exception:
            pass

        # 3. User-registered defaults
        if user_default := get_default("primary.embedding.dimension"):
            return user_default

        # 4. Final fallback (could be None)
        return None

    async def get_datatype(self) -> str | None:
        """Get resolved datatype through fallback chain.

        Resolution order:
        1. Explicit config
        2. Model capabilities
        3. User-registered defaults
        4. Provider-specific defaults

        Returns:
            Resolved datatype or None
        """
        # 1. Explicit config
        for field in ("embedding", "query"):
            if (
                (config := getattr(self, field, None))
                and (found_field := next((f for f in DATATYPE_FIELDS if f in config), None))
            ):
                return config[found_field]

        # 2. Model capabilities
        from codeweaver.core.di import get_container
        from codeweaver.providers.embedding.capabilities.dependencies import (
            EmbeddingCapabilityResolverDep
        )

        container = get_container()
        try:
            cap_resolver = await container.resolve(EmbeddingCapabilityResolverDep)
            if caps := cap_resolver.resolve(self.model_name):
                if dtype := getattr(caps, 'default_datatype', None):
                    return dtype
        except Exception:
            pass

        # 3. User-registered defaults
        if user_default := get_default("primary.embedding.datatype"):
            return user_default

        # 4. Provider-specific defaults
        return self._defaults.get("embedding", {}).get("output_dtype")

    @computed_field
    @property
    def dimension(self) -> int | None:
        """Get the embedding dimension (computed field for backward compatibility).

        Note: This is synchronous but get_dimension() is async. For full
        resolution, use get_dimension() directly. This property returns
        only explicitly configured values or None.
        """
        for field in ("embedding", "query"):
            if (
                (config := getattr(self, field, None))
                and (found_field := next((f for f in DIMENSION_FIELDS if f in config), None))
                and isinstance(config[found_field], int)
            ):
                return config[found_field]
        return None
```

### Phase 3: Vector Store Config Integration

#### Updates to `src/codeweaver/providers/config.provider_kinds.py`

```python
# Add to QdrantVectorStoreProviderSettings

from codeweaver.core.config.resolver import ConfigurableComponent
from codeweaver.core.config.registry import register_configurable


class QdrantVectorStoreProviderSettings(
    BaseProviderCategorySettings,
    ConfigurableComponent
):
    """Settings for Qdrant vector store provider."""

    provider: Literal[Provider.QDRANT] = Provider.QDRANT
    client_options: QdrantClientOptions

    # Collection configuration
    collection_config: dict[str, Any] | None = Field(
        default=None,
        description="Qdrant collection configuration. Will be auto-configured based on embedding settings if not provided."
    )

    # Track resolved values
    _resolved_dimension: int | None = PrivateAttr(default=None)
    _resolved_datatype: str | None = PrivateAttr(default=None)

    def __init__(self, **data: Any) -> None:
        """Initialize and register in DI container."""
        super().__init__(**data)

        # Register in DI container
        from codeweaver.core.di import get_container
        container = get_container()
        container.register(type(self), lambda: self, singleton=True)

        # Register for config resolution
        register_configurable(self)

    def config_dependencies(self) -> dict[str, type]:
        """Vector store needs embedding config for dimension/datatype."""
        # Import here to avoid circular dependencies
        from codeweaver.providers.config.embedding import BaseEmbeddingConfig

        return {
            "embedding": BaseEmbeddingConfig,
        }

    async def apply_resolved_config(self, **resolved: Any) -> None:
        """Apply dimension and datatype from embedding config.

        Args:
            **resolved: Should contain "embedding" key with embedding config instance
        """
        if not (embedding_config := resolved.get("embedding")):
            return

        # Get dimension and datatype from embedding config
        dimension = await embedding_config.get_dimension()
        datatype = await embedding_config.get_datatype()

        # Apply if we got values
        if dimension:
            self._resolved_dimension = dimension
            self._configure_for_dimension(dimension)

        if datatype:
            self._resolved_datatype = datatype
            self._configure_for_datatype(datatype)

    def _configure_for_dimension(self, dimension: int) -> None:
        """Configure collection for specific dimension.

        Args:
            dimension: Embedding dimension to configure for
        """
        if not self.collection_config:
            self.collection_config = {}

        # Update vector configuration
        if "vectors" not in self.collection_config:
            self.collection_config["vectors"] = {}

        self.collection_config["vectors"]["size"] = dimension

        # Set default distance metric if not specified
        if "distance" not in self.collection_config["vectors"]:
            self.collection_config["vectors"]["distance"] = "Cosine"

    def _configure_for_datatype(self, datatype: str) -> None:
        """Configure collection quantization based on datatype.

        Args:
            datatype: Embedding datatype (float16, uint8, etc.)
        """
        if not self.collection_config:
            self.collection_config = {}

        # Configure quantization for reduced precision types
        if datatype in ("float16", "uint8", "int8"):
            self.collection_config["quantization_config"] = {
                "scalar": {
                    "type": datatype,
                    "quantile": 0.99 if "int" in datatype else None,
                    "always_ram": True,
                }
            }
```

### Phase 4: Settings Integration

#### Updates to `src/codeweaver/server/config/settings.py`

```python
class CodeWeaverSettings(BaseSettings):
    """Main configuration model."""

    # ... existing fields ...

    _resolution_complete: bool = PrivateAttr(default=False)

    async def finalize(self) -> Self:
        """Finalize settings with config resolution.

        This should be called after all configs are loaded but before
        the application starts. It resolves all interdependencies.

        Returns:
            Self for chaining
        """
        if self._resolution_complete:
            return self

        from codeweaver.core.config.resolver import resolve_all_configs

        # Trigger config resolution across all registered components
        await resolve_all_configs()

        self._resolution_complete = True
        return self
```

## Usage Examples

### Basic Usage (Automatic Resolution)

```python
# User configuration
settings = CodeWeaverSettings(
    provider=ProviderSettings(
        embedding=VoyageEmbeddingConfig(
            model_name="voyage-code-3",
            embedding={"output_dimension": 512}  # Non-default!
        ),
        vector_store=QdrantVectorStoreProviderSettings(
            client_options=QdrantClientOptions(url="http://localhost:6333")
        )
    )
)

# Finalize triggers resolution
await settings.finalize()

# Vector store now auto-configured for dimension=512
assert settings.provider.vector_store[0].collection_config["vectors"]["size"] == 512
```

### User Custom Defaults

```python
from codeweaver.core.config.defaults import register_default_provider

# Register custom defaults
register_default_provider("primary.embedding.dimension", lambda: 768)
register_default_provider("primary.embedding.datatype", lambda: "float16")

# Now when configs resolve, they'll use these as fallback
settings = CodeWeaverSettings(...)
await settings.finalize()
```

### Testing with Overrides

```python
async def test_config_resolution():
    from codeweaver.core.di import get_container
    from codeweaver.core.config.registry import clear_configurables

    # Clean state
    clear_configurables()
    container = get_container()
    container.clear()

    # Create mock embedding config
    mock_embedding = MagicMock()
    mock_embedding.get_dimension = AsyncMock(return_value=384)

    # Override in DI
    from codeweaver.providers.config.embedding import BaseEmbeddingConfig
    container.override(BaseEmbeddingConfig, mock_embedding)

    # Create vector store and resolve
    vector_store = QdrantVectorStoreProviderSettings(...)
    await vector_store.apply_resolved_config(embedding=mock_embedding)

    # Verify
    assert vector_store.collection_config["vectors"]["size"] == 384
```

## Implementation Plan

### Task 1: Core Infrastructure
- [ ] Create `src/codeweaver/core/config/resolver.py`
- [ ] Create `src/codeweaver/core/config/registry.py`
- [ ] Create `src/codeweaver/core/config/defaults.py`
- [ ] Update `src/codeweaver/core/config/__init__.py` exports

### Task 2: Embedding Config Integration
- [ ] Update `BaseEmbeddingConfig` with ConfigurableComponent protocol
- [ ] Add `get_dimension()` and `get_datatype()` methods
- [ ] Add DI registration in `__init__`
- [ ] Update all concrete embedding configs (Voyage, Mistral, Google, etc.)

### Task 3: Vector Store Config Integration
- [ ] Update `QdrantVectorStoreProviderSettings` with ConfigurableComponent
- [ ] Add `_configure_for_dimension()` and `_configure_for_datatype()`
- [ ] Add DI registration
- [ ] Implement `config_dependencies()` and `apply_resolved_config()`

### Task 4: Settings Integration
- [ ] Add `finalize()` method to `CodeWeaverSettings`
- [ ] Update initialization flows to call `finalize()`
- [ ] Add `_resolution_complete` tracking

### Task 5: Testing
- [ ] Unit tests for resolver components
- [ ] Integration tests for config resolution
- [ ] Test monorepo scenarios (missing packages)
- [ ] Test user custom defaults
- [ ] Test DI overrides in tests

### Task 6: Documentation
- [ ] Update configuration documentation
- [ ] Add examples for custom defaults
- [ ] Document config resolution flow
- [ ] Update architecture docs

## Success Criteria

1. ✅ Vector store auto-configures based on embedding dimension/datatype
2. ✅ Config resolution works with missing packages (monorepo-safe)
3. ✅ Users can register custom defaults
4. ✅ No chicken-and-egg initialization problems
5. ✅ All tests pass with DI overrides
6. ✅ Clear, maintainable code following existing patterns

## Non-Goals

- Runtime config changes (configs are still immutable after finalization)
- Complex validation rules (keep it simple - just apply values)
- Cross-package config dependencies beyond embedding→vector store

## Future Enhancements

- Config validation service (check for conflicts before applying)
- Config migration system (update configs across versions)
- Visual config dependency graph
- Config change notifications

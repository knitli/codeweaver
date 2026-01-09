<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Monorepo Config Resolution Integration Design

## Problem Statement

CodeWeaver's monorepo allows selective package installation, creating these challenges:

1. **Unknown Config Availability**: Can't assume all config types exist
2. **Multiple Potential Root Settings**:
   - `CodeWeaverSettings` (server) - depends on everything
   - `ProviderSettings` (providers)
   - `IndexerSettings` + `ChunkerSettings` (engine) - TWO roots!
   - Logging/Telemetry (core) - always available

3. **TOML Structure Conflicts**:
   ```toml
   # When CodeWeaverSettings is root:
   [provider]
   embedding.provider = "voyage"

   # When ProviderSettings is standalone root:
   # Can't use [provider] table - pydantic-settings validation fails!
   embedding.provider = "voyage"  # Must be at root level
   ```

4. **Config Resolution Timing**: Need `finalize()` to work regardless of which settings class is root

## Proposed Solution: Adaptive Root Detection + Flexible Finalization

### Core Concept

1. **Move `finalize()` to `BaseCodeWeaverSettings`** - all settings classes inherit it
2. **Auto-detect root context** - settings detect if they're standalone or nested
3. **Conditional TOML parsing** - adapt structure based on context
4. **Safe resolution** - config resolution gracefully handles missing types

### Implementation

#### 1. Enhanced BaseCodeWeaverSettings

```python
# src/codeweaver/core/types/settings_model.py

class BaseCodeWeaverSettings(BaseSettings):
    """Base settings with adaptive config resolution."""

    _resolution_complete: bool = PrivateAttr(default=False)
    _is_root_settings: bool = PrivateAttr(default=False)

    # Class-level registry of which settings type this is
    _settings_type: ClassVar[Literal["core", "provider", "engine", "server"]]

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        # Detect if we're the root settings class
        self._is_root_settings = self._detect_root_context()

    def _detect_root_context(self) -> bool:
        """Detect if this settings instance is the root configuration.

        Root indicators:
        - No parent CodeWeaverSettings available
        - Loaded from top-level config file
        - Environment variable CODEWEAVER_ROOT_SETTINGS matches our type
        """
        import importlib.util

        # Check if server package (CodeWeaverSettings) is available
        if importlib.util.find_spec("codeweaver.server") is not None:
            # Server exists - only server should be root
            return self._settings_type == "server"

        # No server - check env var for explicit root designation
        env_root = os.getenv("CODEWEAVER_ROOT_SETTINGS", "").lower()
        if env_root:
            return env_root == self._settings_type

        # Default: we're root if we're the highest-level available package
        return True

    async def finalize(self) -> Self:
        """Finalize settings with safe config resolution.

        Only performs resolution if:
        1. We're the root settings (or resolution not done elsewhere)
        2. Config resolution module is available
        3. Not already finalized
        """
        if self._resolution_complete:
            return self

        # Only root settings should trigger global resolution
        if not self._is_root_settings:
            return self

        try:
            from codeweaver.core.config.resolver import resolve_all_configs

            # Trigger config resolution across all registered components
            await resolve_all_configs()

            self._resolution_complete = True
        except ImportError:
            # Config resolution not available (minimal install)
            logger.debug("Config resolution not available - skipping")
        except Exception as e:
            logger.warning(f"Config resolution failed: {e}")

        return self
```

#### 2. Adaptive TOML Parsing

**Option A: Field Aliasing (Recommended)**

Use pydantic's `validation_alias` to support both nested and root-level config:

```python
# src/codeweaver/providers/config/providers.py

class ProviderSettings(BaseCodeWeaverSettings):
    """Provider configuration - works standalone or nested."""

    _settings_type: ClassVar[Literal["provider"]] = "provider"

    embedding: Annotated[
        EmbeddingConfigT | None,
        Field(
            default=None,
            validation_alias=AliasChoices(
                "embedding",  # Standalone: embedding.provider=...
                "provider__embedding"  # Nested: [provider] embedding.provider=...
            )
        )
    ]

    vector_store: Annotated[
        VectorStoreConfigT | None,
        Field(
            default=None,
            validation_alias=AliasChoices(
                "vector_store",
                "provider__vector_store"
            )
        )
    ]
```

**Option B: Custom Settings Source (More Complex)**

Create a custom `TomlConfigSettingsSource` that adapts based on root context:

```python
class AdaptiveTomlSource(TomlConfigSettingsSource):
    """TOML source that adapts to standalone vs nested context."""

    def __init__(self, settings_cls: type[BaseSettings], toml_file: Path):
        super().__init__(settings_cls, toml_file)
        self.is_nested = self._detect_nested_context(settings_cls)

    def _detect_nested_context(self, settings_cls: type[BaseSettings]) -> bool:
        """Check if this settings class is nested under another."""
        # If CodeWeaverSettings exists and we're not it, we're nested
        if hasattr(settings_cls, '_settings_type'):
            return settings_cls._settings_type != "server"
        return False

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        """Get field value with adaptive prefix."""
        if self.is_nested:
            # Look under [provider] table
            prefixed_name = f"{self.settings_cls._settings_type}__{field_name}"
        else:
            # Look at root level
            prefixed_name = field_name

        return super().get_field_value(field, prefixed_name)
```

#### 3. Engine Package: Multiple Root Settings

For engine package with TWO top-level settings:

```python
# src/codeweaver/engine/config/settings.py

class EngineSettings(BaseCodeWeaverSettings):
    """Composite engine settings - container for indexer and chunker."""

    _settings_type: ClassVar[Literal["engine"]] = "engine"

    indexer: IndexerSettings = Field(default_factory=IndexerSettings)
    chunker: ChunkerSettings = Field(default_factory=ChunkerSettings)

    async def finalize(self) -> Self:
        """Finalize engine settings and sub-settings."""
        # Finalize children first
        await self.indexer.finalize()
        await self.chunker.finalize()
        # Then finalize self
        return await super().finalize()


# Alternative: Both IndexerSettings and ChunkerSettings can be root independently
class IndexerSettings(BaseCodeWeaverSettings):
    _settings_type: ClassVar[Literal["indexer"]] = "indexer"
    # ... fields

class ChunkerSettings(BaseCodeWeaverSettings):
    _settings_type: ClassVar[Literal["chunker"]] = "chunker"
    # ... fields
```

TOML structure for engine:

```toml
# Option 1: Composite EngineSettings as root
[indexer]
batch_size = 100

[chunker]
max_chunk_size = 1000

# Option 2: IndexerSettings standalone
batch_size = 100
# (no table prefix)

# Option 3: ChunkerSettings standalone
max_chunk_size = 1000
# (no table prefix)
```

#### 4. Settings Detection Priority

```python
def get_root_settings() -> BaseCodeWeaverSettings:
    """Get the appropriate root settings for current environment."""

    # Priority order (highest to lowest)
    settings_priority = [
        ("codeweaver.server", "CodeWeaverSettings"),
        ("codeweaver.engine", "EngineSettings"),  # Composite
        ("codeweaver.providers", "ProviderSettings"),
        ("codeweaver.core", "CoreSettings"),  # Logging + Telemetry only
    ]

    for module_path, class_name in settings_priority:
        try:
            module = importlib.import_module(f"{module_path}.config.settings")
            settings_class = getattr(module, class_name)
            return settings_class()
        except (ImportError, AttributeError):
            continue

    raise RuntimeError("No CodeWeaver settings module found")
```

### Usage Patterns

#### Full Installation (Server Package)

```python
# All packages available
from codeweaver.server.config.settings import CodeWeaverSettings

settings = CodeWeaverSettings()
await settings.finalize()  # Resolves all configs
```

```toml
# codeweaver.toml
[provider]
embedding.provider = "voyage"

[engine.indexer]
batch_size = 100

[logging]
level = "INFO"
```

#### Provider-Only Installation

```python
from codeweaver.providers.config.providers import ProviderSettings

settings = ProviderSettings()
await settings.finalize()  # Resolves only provider configs
```

```toml
# codeweaver.toml (no [provider] table!)
embedding.provider = "voyage"
primary.embedding.model_name = "voyage-code-3"
vector_store.provider = "qdrant"
```

#### Engine-Only Installation

```python
# Option 1: Composite
from codeweaver.engine.config.settings import EngineSettings

settings = EngineSettings()
await settings.finalize()
```

```toml
[indexer]
batch_size = 100

[chunker]
max_chunk_size = 1000
```

```python
# Option 2: Standalone indexer
from codeweaver.engine.config.indexer import IndexerSettings

settings = IndexerSettings()
await settings.finalize()
```

```toml
# No table - root level
batch_size = 100
parallel_workers = 4
```

### Config Resolution Integration

The resolution system already handles missing configs gracefully:

```python
# In resolve_all_configs()
for configurable in configurables:
    deps = configurable.config_dependencies()
    resolved = {}

    for dep_name, dep_type in deps.items():
        try:
            resolved[dep_name] = await container.resolve(dep_type)
        except Exception:
            # Dependency not available (monorepo) - skip
            continue

    if resolved:
        await configurable.apply_resolved_config(**resolved)
```

This means:
- If `EmbeddingConfig` doesn't exist, vector store config just won't get dimension/datatype
- If `VectorStoreConfig` doesn't exist, embedding config still works
- Each package only resolves what's available

### Migration Path

1. **Phase 1**: Add `_settings_type` and `finalize()` to `BaseCodeWeaverSettings`
2. **Phase 2**: Update each settings class to set `_settings_type`
3. **Phase 3**: Add field aliases for dual-mode TOML support
4. **Phase 4**: Update documentation with examples for each installation mode
5. **Phase 5**: Add integration tests for each package combo

### Testing Strategy

```python
# Test matrix
test_scenarios = [
    ("full", ["server", "engine", "providers", "core"]),
    ("engine-only", ["engine", "core"]),
    ("providers-only", ["providers", "core"]),
    ("core-only", ["core"]),
]

for scenario_name, installed_packages in test_scenarios:
    # Mock package availability
    # Load appropriate config
    # Verify finalize() works
    # Verify configs resolve correctly
```

## Implementation Checklist

- [ ] Add `finalize()` to `BaseCodeWeaverSettings`
- [ ] Add `_settings_type` to all settings classes
- [ ] Add `_detect_root_context()` logic
- [ ] Add field aliases for provider settings
- [ ] Create `EngineSettings` composite or decide on standalone
- [ ] Update TOML examples in docs
- [ ] Write integration tests for each package combo
- [ ] Add env var `CODEWEAVER_ROOT_SETTINGS` support

## Open Questions

1. **Engine Package**: Composite `EngineSettings` or two independent root settings?
   - Composite is cleaner for TOML structure
   - Independent gives more flexibility for library users

2. **Field Aliasing vs Custom Source**: Which approach for TOML adaptation?
   - Aliasing is simpler, more maintainable
   - Custom source is more powerful, handles edge cases

3. **Resolution Idempotency**: Should `finalize()` be callable multiple times safely?
   - Current implementation has `_resolution_complete` flag
   - Should we allow re-resolution or enforce single-call?

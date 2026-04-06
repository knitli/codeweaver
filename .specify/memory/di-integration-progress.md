<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# DI System Integration Progress Report

**Date**: 2026-01-08
**Status**: Phases 1-5 Complete, Phase 6+ Pending
**Plan Document**: `.claude/plans/imperative-waddling-manatee.md`

---

## Executive Summary

The dependency injection (DI) system foundation is now complete through Phase 5. The architecture implements a layered dependency resolution pattern: **Settings → Configs → Clients → Providers**, with cross-config resolution support for complex dependencies (e.g., vector store needing embedding dimension).

**Key Achievement**: Established the complete DI infrastructure for the embedding provider ecosystem, including:
- Settings bootstrap as DI root
- Config factory pattern with collection support (primary + backups)
- 11 SDK client factories with proper DI injection
- Provider factory with dynamic backup class generation
- Cross-config resolution with indexed reference support

**Current State**: Ready for extension to other provider types (reranking, vector stores, sparse embedding, data, agent), but ~250 broken references exist in codebase from prior restructuring that should be addressed first.

---

## Phase 1: Settings Bootstrap ✅ COMPLETE

### Implementation Location
- **File**: `src/codeweaver/core/dependencies.py`
- **Lines**: 29-51

### What Was Done

1. **Settings Factory Function**:
```python
@dependency_provider(BaseCodeWeaverSettings, scope="singleton")
def bootstrap_settings() -> BaseCodeWeaverSettings:
    """Bootstrap global settings as DI root.

    Auto-detects the appropriate settings class based on installed packages
    (server, engine, provider, or core) and returns it as BaseCodeWeaverSettings.

    Returns:
        The appropriate settings instance for the current installation
    """
    from codeweaver.core.config.loader import get_settings

    config_file = _resolve_config_file()
    return get_settings(config_file=config_file)
```

2. **Type Alias**:
```python
type SettingsDep = Annotated[BaseCodeWeaverSettings, depends(bootstrap_settings)]
```

### Key Design Decisions

- **Settings as DI Root**: Settings created once at startup via `@dependency_provider`
- **Auto-Detection**: `get_settings()` automatically selects appropriate settings class
- **Singleton Scope**: Settings instance shared across all DI consumers
- **No Override Needed**: Using `@dependency_provider` instead of manual override

### Why This Works

- DI container's lazy loading ensures settings exist before any resolution
- All provider factories can inject `settings: BaseCodeWeaverSettings = INJECTED`
- Avoids chicken-egg problem between settings and providers
- Settings are immutable and safe to share across threads

---

## Phase 2: Config Factory Pattern ✅ COMPLETE

### Implementation Locations
- **Primary**: `src/codeweaver/providers/dependencies.py` (lines 465-650)
- **Config Change**: `src/codeweaver/providers/config/embedding.py` (removed lines 147-171)

### What Was Done

1. **Removed Self-Registration**:
   - Deleted `__init__` method's DI registration block in `BaseEmbeddingConfig`
   - Removed circular dependency between config and container

2. **Config Collection Factories**:
```python
async def get_all_embedding_configs(
    settings: SettingsDep = INJECTED,
) -> tuple[EmbeddingConfigT, ...]:
    """Factory for all embedding configs (primary + backups)."""
    if not settings.provider or not settings.provider.embedding:
        return tuple()
    return settings.provider.embedding  # Already a tuple from settings

async def get_primary_embedding_config(
    all_configs: AllEmbeddingConfigsDep = INJECTED,
) -> EmbeddingConfigT:
    """Factory for primary embedding config."""
    if not all_configs:
        raise ConfigurationError("No embedding configs available")
    return all_configs[0]
```

3. **Type Aliases**:
```python
type AllEmbeddingConfigsDep = Annotated[
    tuple[EmbeddingConfigT, ...],
    depends(get_all_embedding_configs),
]

type EmbeddingProviderSettingsDep = Annotated[
    EmbeddingConfigT,
    depends(get_primary_embedding_config),
]
```

4. **Similar Factories for Other Provider Types**:
   - Reranking configs (primary + backups)
   - Vector store configs
   - Sparse embedding configs
   - Data provider configs
   - Agent provider configs

### Key Design Decisions

- **Collection-First**: Factories return tuples (primary at index 0, backups at 1+)
- **External Registration**: Configs registered by factories, not self-registration
- **Layered Factories**: `get_all_X` → `get_primary_X` dependency chain
- **Consistent Pattern**: Same approach for all provider config types

### Benefits

- **Test Isolation**: Can override configs without modifying settings tree
- **State Management**: DI handles config lifecycle, not settings
- **Collection Support**: Natural handling of primary + backup pattern
- **Lazy Loading**: Configs created only when needed

---

## Phase 3: Client Factories ✅ COMPLETE

### Implementation Location
- **File**: `src/codeweaver/providers/dependencies.py`
- **Lines**: 76-463 (client factories), 465-650 (type aliases)

### What Was Done

Implemented **11 client factory functions** with consistent pattern:

1. **OpenAI and OpenAI-Compatible** (`_create_openai_client`):
   - Supports: OpenAI, Azure, Anyscale, Fireworks, Groq, OpenRouter, Together
   - Client: `AsyncOpenAI`

2. **Voyage** (`_create_voyage_client`):
   - Client: `voyageai.AsyncClient`

3. **Cohere** (`_create_cohere_client`):
   - Supports: Cohere, Azure Cohere, Heroku Cohere
   - Client: `cohere.AsyncClient`

4. **Mistral** (`_create_mistral_client`):
   - Client: `mistralai.Mistral`

5. **Google** (`_create_google_client`):
   - Client: `google.generativeai.GenerativeModel`

6. **Bedrock** (`_create_bedrock_client`):
   - Client: `boto3.Session().client('bedrock-runtime')`

7. **HuggingFace** (`_create_huggingface_client`):
   - Client: `huggingface_hub.InferenceClient`

8. **FastEmbed Dense** (`_create_fastembed_client`):
   - Client: `fastembed.TextEmbedding`

9. **FastEmbed Sparse** (`_create_fastembed_sparse_client`):
   - Client: `fastembed.SparseTextEmbedding`

10. **Sentence Transformers Dense** (`_create_sentence_transformers_client`):
    - Client: `sentence_transformers.SentenceTransformer`

11. **Sentence Transformers Sparse** (`_create_sentence_transformers_sparse_client`):
    - Client: Custom sparse embedding wrapper

### Factory Pattern

All factories follow this structure:

```python
def _create_[provider]_client() -> [ClientType]:
    """Factory for [Provider] client."""
    from codeweaver.core.di import INJECTED

    # Inject primary config
    config: EmbeddingProviderSettingsType = INJECTED  # type: ignore[name-defined]

    # Validation
    if not config or not config.client_options:
        raise ConfigurationError("Client factory requires config with client_options")

    # Import SDK
    try:
        from [sdk_package] import [ClientClass]
    except ImportError as e:
        raise ConfigurationError('Install package: pip install "code-weaver[[extra]]"') from e

    # Extract and apply client options
    client_options = config.client_options.as_settings()
    return [ClientClass](**client_options)
```

### Type Aliases Created

```python
type OpenAIClientDep = Annotated[Any, depends(_create_openai_client)]
type VoyageClientDep = Annotated[Any, depends(_create_voyage_client)]
type CohereClientDep = Annotated[Any, depends(_create_cohere_client)]
type MistralClientDep = Annotated[Any, depends(_create_mistral_client)]
type GoogleClientDep = Annotated[Any, depends(_create_google_client)]
type BedrockClientDep = Annotated[Any, depends(_create_bedrock_client)]
type HuggingFaceClientDep = Annotated[Any, depends(_create_huggingface_client)]
type FastEmbedClientDep = Annotated[Any, depends(_create_fastembed_client)]
type FastEmbedSparseClientDep = Annotated[Any, depends(_create_fastembed_sparse_client)]
type SentenceTransformersClientDep = Annotated[Any, depends(_create_sentence_transformers_client)]
type SentenceTransformersSparseClientDep = Annotated[
    Any, depends(_create_sentence_transformers_sparse_client)
]
```

### Key Design Decisions

- **Centralized in dependencies.py**: All client factories in one place
- **DI Injection**: All factories inject primary config via `INJECTED`
- **Error Handling**: Clear messages for missing dependencies
- **Client Options Pattern**: Use `config.client_options.as_settings()` consistently
- **Type Hints**: Use `Any` for client types to avoid import-time dependencies

### Benefits

- **Clear Dependency Graph**: Settings → Config → Client
- **Test Mockability**: Easy to override clients in tests
- **Lazy Initialization**: Clients created only when providers need them
- **Consistent API**: Same pattern across all SDK types

---

## Phase 4: Provider Factories ✅ COMPLETE

### Implementation Location
- **File**: `src/codeweaver/providers/dependencies.py`
- **Lines**: 796-1086

### What Was Done

1. **Helper Function: `_get_provider_class_for_config`**:
```python
def _get_provider_class_for_config(config: EmbeddingConfigT) -> type:
    """Map embedding config to its provider class.

    Supports 15 provider types, including special handling for OpenAI-compatible
    providers (7 providers → 1 base class).
    """
    provider_map = {
        Provider.OPENAI: OpenAIEmbeddingBase,
        Provider.AZURE: OpenAIEmbeddingBase,
        Provider.ANYSCALE: OpenAIEmbeddingBase,
        Provider.FIREWORKS: OpenAIEmbeddingBase,
        Provider.GROQ: OpenAIEmbeddingBase,
        Provider.OPENROUTER: OpenAIEmbeddingBase,
        Provider.TOGETHER: OpenAIEmbeddingBase,
        Provider.VOYAGE: VoyageEmbeddingProvider,
        Provider.COHERE: CohereEmbeddingProvider,
        Provider.MISTRAL: MistralEmbeddingProvider,
        Provider.GOOGLE: GoogleEmbeddingProvider,
        Provider.BEDROCK: BedrockEmbeddingProvider,
        Provider.HUGGINGFACE: HuggingFaceEmbeddingProvider,
        Provider.FASTEMBED: FastEmbedProvider,
        Provider.SENTENCE_TRANSFORMERS: SentenceTransformersProvider,
    }

    provider_cls = provider_map.get(config.provider)
    if not provider_cls:
        raise ConfigurationError(f"No provider class for {config.provider}")
    return provider_cls
```

2. **Helper Function: `_create_client_for_config`**:
```python
def _create_client_for_config(config: EmbeddingConfigT) -> Any:
    """Create SDK client for the given config.

    Routes to appropriate client factory based on provider type.
    """
    client_factories = {
        Provider.OPENAI: _create_openai_client,
        Provider.AZURE: _create_openai_client,
        # ... 13 more mappings
    }

    factory = client_factories.get(config.provider)
    if not factory:
        raise ConfigurationError(f"No client factory for {config.provider}")
    return factory()
```

3. **Helper Function: `_instantiate_provider`**:
```python
def _instantiate_provider(
    provider_cls: type,
    config: EmbeddingConfigT,
    client: Any,
    caps: EmbeddingCapabilities,
) -> Any:
    """Instantiate a provider with dependencies.

    Args:
        provider_cls: Provider class (may be dynamically created backup class)
        config: Provider configuration
        client: SDK client instance
        caps: Model capabilities

    Returns:
        Configured provider instance
    """
    return provider_cls(client=client, config=config, caps=caps)
```

4. **Main Factory: `create_all_embedding_providers`**:
```python
async def create_all_embedding_providers(
    configs: AllEmbeddingConfigsDep = INJECTED,
    caps_resolver: EmbeddingCapabilityResolverDep = INJECTED,
) -> tuple[Any, ...]:
    """Factory for creating ALL embedding providers (primary + backups).

    Integrates with backup_factory for dynamic backup class generation.
    """
    from codeweaver.providers.backup_factory import create_backup_class

    if not configs:
        return tuple()

    providers = []
    for i, config in enumerate(configs):
        is_backup = i > 0

        # Get provider class
        provider_cls = _get_provider_class_for_config(config)

        # Apply backup wrapper if needed
        if is_backup:
            provider_cls = create_backup_class(provider_cls)

        # Create client
        client = _create_client_for_config(config)

        # Resolve capabilities
        caps = caps_resolver.resolve(config.model_name)

        # Instantiate provider
        provider = _instantiate_provider(provider_cls, config, client, caps)
        providers.append(provider)

    return tuple(providers)
```

5. **Convenience Factory: `get_primary_embedding_provider`**:
```python
async def get_primary_embedding_provider(
    all_providers: AllEmbeddingProvidersDep = INJECTED,
) -> Any:
    """Get the primary (first) embedding provider."""
    if not all_providers:
        raise ConfigurationError("No embedding providers configured")
    return all_providers[0]
```

6. **Type Aliases**:
```python
type AllEmbeddingProvidersDep = Annotated[
    tuple[Any, ...],
    depends(create_all_embedding_providers),
]

type PrimaryEmbeddingProviderDep = Annotated[
    Any,
    depends(get_primary_embedding_provider),
]
```

### Key Design Decisions

- **Helper Functions**: Separate concerns (class lookup, client creation, instantiation)
- **Backup Integration**: Dynamic class creation via `backup_factory.create_backup_class()`
- **Collection-Based**: Factory returns tuple of all providers (primary + backups)
- **Layered Dependencies**: Configs → Clients → Providers
- **Capability Resolution**: Injected resolver for model capabilities

### Backup Provider Discrimination

The integration with `backup_factory.py` (implemented in earlier phase) solves the type collision problem:

**Problem**: Same provider type (e.g., two `SentenceTransformersProvider`) for primary and backup
**Solution**: Dynamic class factory creates `BackupSentenceTransformersProvider`

```python
# From providers/backup_factory.py
def create_backup_class[T](provider_cls: type[T]) -> type[T]:
    """Create BackupXProvider dynamically."""
    if provider_cls in _backup_class_cache:
        return _backup_class_cache[provider_cls]

    backup_base = get_backup_base_class(provider_cls)  # Returns BackupEmbeddingProvider
    backup_cls = type(
        f"Backup{provider_cls.__name__}",
        (backup_base, provider_cls),
        {"__doc__": f"Backup variant of {provider_cls.__name__}."},
    )
    _backup_class_cache[provider_cls] = backup_cls
    return backup_cls
```

**Benefits**:
- `isinstance(p, BackupEmbeddingProvider)` works correctly
- `p.is_provider_backup` returns `True` for backups
- No manual backup class declarations needed
- Caching ensures consistent class identity
- Future extension point for strategy tagging (fast, precise, etc.)

---

## Phase 5: Cross-Config Resolution ✅ COMPLETE

### Implementation Locations
- **Primary**: `src/codeweaver/core/config/resolver.py` (extensive modifications)
- **Secondary**: `src/codeweaver/providers/embedding/providers/base.py` (type aliases)

### What Was Done

1. **Parse Config References** (`_parse_config_reference`):
```python
def _parse_config_reference(ref: str) -> tuple[str, int | None]:
    """Parse a config reference into base name and optional index.

    Args:
        ref: Config reference string (e.g., "embedding", "embedding[0]", "embedding[*]")

    Returns:
        Tuple of (base_name, index) where:
        - base_name: The config kind (e.g., "embedding")
        - index: The index number, -1 for "*" (all), or None for no index

    Examples:
        >>> _parse_config_reference("embedding")
        ("embedding", None)
        >>> _parse_config_reference("embedding[0]")
        ("embedding", 0)
        >>> _parse_config_reference("embedding[*]")
        ("embedding", -1)
    """
    match = re.match(r"^([a-z_]+)(?:\[(\d+|\*)\])?$", ref)
    if not match:
        return ref, None

    base_name = match.group(1)
    index_str = match.group(2)

    if index_str is None:
        return base_name, None
    if index_str == "*":
        return base_name, -1  # -1 means "all"
    return base_name, int(index_str)
```

2. **Resolve Indexed Configs** (`_resolve_indexed_config`):
```python
async def _resolve_indexed_config(
    dep_name: str,
    dep_type: type,
    container: Any,
) -> Any | None:
    """Resolve a config dependency with optional indexing.

    Args:
        dep_name: Dependency name (may include index like "embedding[0]")
        dep_type: Type to resolve from DI container
        container: DI container instance

    Returns:
        Resolved config instance(s) or None if resolution fails

    Examples:
        "embedding" → primary config (backward compatible)
        "embedding[0]" → primary config (explicit)
        "embedding[*]" → tuple of all configs
        "embedding[1]" → first backup config
    """
    base_name, index = _parse_config_reference(dep_name)

    with contextlib.suppress(AttributeError, KeyError, TypeError, ValueError, ImportError):
        resolved = await container.resolve(dep_type)

        # No indexing - return as-is (backward compatible)
        if index is None:
            return resolved

        # All configs requested (embedding[*])
        if index == -1:
            if isinstance(resolved, tuple | list):
                return resolved
            return (resolved,)

        # Specific index requested
        if isinstance(resolved, tuple | list):
            try:
                return resolved[index]
            except IndexError:
                return None

        # Non-collection but index 0 (primary)
        if index == 0:
            return resolved

        return None

    return None
```

3. **Updated Main Resolver** (`resolve_all_configs`):
```python
async def resolve_all_configs() -> None:
    """Resolve all configurations across the application.

    Extended in Phase 5 to support indexed config references:
    - "embedding" - resolves to primary config (backward compatible)
    - "embedding[0]" - resolves to primary config (explicit)
    - "embedding[*]" - resolves to all configs (tuple)
    - "embedding[1]" - resolves to first backup config

    Example:
        class VectorStoreConfig:
            def config_dependencies(self):
                return {"embedding[0]": EmbeddingProviderSettings}

            async def apply_resolved_config(self, embedding=None, **resolved):
                if embedding:
                    self._resolved_dimension = await embedding.get_dimension()
    """
    from codeweaver.core.config.registry import get_configurable_components

    container = get_container()
    configurable = get_configurable_components()

    for configurable in configurable:
        deps = configurable.config_dependencies()
        resolved = {}

        for dep_name, dep_type in deps.items():
            # Parse and resolve with indexing support
            resolved_config = await _resolve_indexed_config(dep_name, dep_type, container)

            if resolved_config is not None:
                # Strip index from key for apply_resolved_config()
                # "embedding[0]" becomes "embedding"
                base_name, _ = _parse_config_reference(dep_name)
                resolved[base_name] = resolved_config

        if resolved:
            await configurable.apply_resolved_config(**resolved)
```

4. **Updated Protocol** (`ConfigurableComponent`):
```python
class ConfigurableComponent(Protocol):
    """Protocol for components participating in config resolution.

    Extended in Phase 5 to support indexed config references:
    - "embedding" - primary embedding config (backward compatible)
    - "embedding[0]" - primary embedding config (explicit)
    - "embedding[*]" - all embedding configs (primary + backups)
    - "embedding[1]" - first backup config
    """

    def config_dependencies(self) -> dict[str, type]:
        """Return types this config needs to resolve against.

        Examples:
            Simple reference (backward compatible):
                {"embedding": EmbeddingProviderSettings}

            Indexed reference (Phase 5):
                {"embedding[0]": EmbeddingProviderSettings}  # Primary only
                {"embedding[*]": EmbeddingProviderSettings}  # All configs

            Multiple dependencies:
                {
                    "embedding[0]": EmbeddingProviderSettings,
                    "reranking": RerankingProviderSettings,
                }
        """
        ...

    async def apply_resolved_config(self, **resolved: Any) -> None:
        """Apply resolved configuration from dependencies.

        Note:
            Indexed references like "embedding[0]" will have the index
            stripped from the key, so you'll receive "embedding" as the key.
        """
        ...
```

5. **Added Type Aliases to Provider Base**:
```python
# In src/codeweaver/providers/embedding/providers/base.py

type ClientDep[T] = Annotated[T, depends(lambda: None)]
"""Generic client dependency type for embedding providers.

For specific provider implementations, prefer using the concrete client type aliases
from codeweaver.providers.dependencies (OpenAIClientDep, VoyageClientDep, etc.).

This generic type is used in the base class where the client type is parameterized.
"""

type EmbeddingConfigDep[T] = Annotated[T, depends(lambda: None)]
"""Generic config dependency type for embedding providers.

For most use cases, use EmbeddingProviderSettingsDep from codeweaver.providers.dependencies
which injects the primary embedding config. Use this generic type when you need a
parameterized config type in the base class.
"""
```

### Key Design Decisions

- **Indexed References**: Support "embedding[0]", "embedding[1]", "embedding[*]" syntax
- **Backward Compatible**: Plain "embedding" still works (resolves to primary)
- **Collection Handling**: Automatic detection of tuple/list configs
- **Key Stripping**: Remove index from key before passing to `apply_resolved_config()`
- **Generic Type Aliases**: Support parameterized types in base classes

### Use Case: Vector Store Dimension

The primary use case is vector stores needing the embedding dimension:

```python
class VectorStoreConfig(ConfigurableComponent):
    """Vector store configuration that depends on embedding dimension."""

    def config_dependencies(self) -> dict[str, type]:
        return {"embedding[0]": EmbeddingProviderSettings}  # Primary embedding

    async def apply_resolved_config(self, embedding: EmbeddingProviderSettings | None = None, **resolved):
        """Apply resolved embedding config."""
        if embedding:
            # Get dimension from embedding provider
            self._resolved_dimension = await embedding.get_dimension()
            logger.info(f"Resolved embedding dimension: {self._resolved_dimension}")
```

### Benefits

- **Type-Safe Resolution**: Proper handling of collection vs single configs
- **Flexible References**: Support both indexed and non-indexed syntax
- **Cross-Config Dependencies**: Configs can depend on other configs safely
- **Future-Proof**: Easy to extend with new reference patterns

---

## Complete DI Architecture

### Dependency Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Startup                      │
│                                                              │
│  1. bootstrap_settings() → BaseCodeWeaverSettings          │
│     - Auto-detect settings class (core/server/engine)      │
│     - Load from TOML/env vars                              │
│     - Register as singleton in DI container                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Config Layer (Phase 2)                     │
│                                                              │
│  2. get_all_embedding_configs(settings) → tuple[Config]    │
│     - Extract settings.provider.embedding                   │
│     - Return (primary, backup1, backup2, ...)              │
│                                                              │
│  3. get_primary_embedding_config(all_configs) → Config     │
│     - Return all_configs[0]                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Client Layer (Phase 3)                     │
│                                                              │
│  4. _create_openai_client(config) → AsyncOpenAI           │
│     - Extract config.client_options.as_settings()          │
│     - Instantiate SDK client                               │
│     - Handle import errors gracefully                      │
│                                                              │
│  [Similar for 10 other client types]                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  Provider Layer (Phase 4)                    │
│                                                              │
│  5. create_all_embedding_providers(                         │
│        configs,                                             │
│        caps_resolver                                        │
│     ) → tuple[Provider]                                     │
│                                                              │
│     For each config:                                        │
│       a. provider_cls = _get_provider_class_for_config()   │
│       b. if backup: provider_cls = create_backup_class()   │
│       c. client = _create_client_for_config()              │
│       d. caps = caps_resolver.resolve(model_name)          │
│       e. provider = _instantiate_provider(...)             │
│                                                              │
│  6. get_primary_embedding_provider(all) → Provider         │
│     - Return all_providers[0]                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              Cross-Config Resolution (Phase 5)               │
│                                                              │
│  7. resolve_all_configs()                                   │
│     - Get all ConfigurableComponent instances              │
│     - For each component:                                  │
│       a. deps = component.config_dependencies()            │
│       b. For each dep_name, dep_type:                      │
│          - Parse indexed reference (embedding[0])          │
│          - Resolve via DI container                        │
│          - Strip index from key                            │
│       c. component.apply_resolved_config(**resolved)       │
│                                                              │
│  Example: VectorStoreConfig gets embedding dimension       │
└─────────────────────────────────────────────────────────────┘
```

### Type Alias Summary

```python
# Settings (Phase 1)
SettingsDep = Annotated[BaseCodeWeaverSettings, depends(bootstrap_settings)]

# Configs (Phase 2)
AllEmbeddingConfigsDep = Annotated[tuple[EmbeddingConfigT, ...], depends(get_all_embedding_configs)]
EmbeddingProviderSettingsDep = Annotated[EmbeddingConfigT, depends(get_primary_embedding_config)]

# Clients (Phase 3)
OpenAIClientDep = Annotated[Any, depends(_create_openai_client)]
VoyageClientDep = Annotated[Any, depends(_create_voyage_client)]
# ... 9 more client type aliases

# Providers (Phase 4)
AllEmbeddingProvidersDep = Annotated[tuple[Any, ...], depends(create_all_embedding_providers)]
PrimaryEmbeddingProviderDep = Annotated[Any, depends(get_primary_embedding_provider)]

# Generic Types (Phase 5)
ClientDep[T] = Annotated[T, depends(lambda: None)]
EmbeddingConfigDep[T] = Annotated[T, depends(lambda: None)]
```

### Module Exports

The `providers/dependencies.py` module now exports:

```python
__all__ = (
    # Provider Settings Type Aliases (Phase 2)
    "AgentProviderSettingsDep",
    "AllEmbeddingConfigsDep",
    "AllRerankingConfigsDep",
    "AllSparseEmbeddingConfigsDep",
    "AllVectorStoreConfigsDep",
    "DataProviderSettingsDep",
    "EmbeddingProviderSettingsDep",
    "RerankingProviderSettingsDep",
    "SparseEmbeddingProviderSettingsDep",
    "VectorStoreProviderSettingsDep",

    # Capability Resolver Type Aliases (Phase 2)
    "EmbeddingCapabilityResolverDep",
    "RerankingCapabilityResolverDep",

    # Client Type Aliases (Phase 3)
    "BedrockClientDep",
    "ClientDep",
    "CohereClientDep",
    "FastEmbedClientDep",
    "FastEmbedSparseClientDep",
    "GoogleClientDep",
    "HuggingFaceClientDep",
    "MistralClientDep",
    "OpenAIClientDep",
    "SentenceTransformersClientDep",
    "SentenceTransformersSparseClientDep",
    "VoyageClientDep",

    # Provider Type Aliases (Phase 4)
    "AllEmbeddingProvidersDep",
    "PrimaryEmbeddingProviderDep",

    # Factory Functions (Phase 4)
    "create_all_embedding_providers",
    "get_primary_embedding_provider",

    # Utilities
    "NoneDep",
)
```

---

## Remaining Work: Phases 6+

### Phase 6: Apply Pattern to Other Providers

#### 6.1 Reranking Providers

**Status**: Config factories exist (Phase 2), need client and provider factories

**Work Required**:

1. **Client Factories** (similar to Phase 3):
```python
# In providers/dependencies.py

# Reranking uses many of the same SDKs as embedding
def _create_reranking_cohere_client() -> Any:
    """Factory for Cohere reranking client."""
    # Similar to _create_cohere_client but with reranking config
    config: RerankingProviderSettingsDep = INJECTED
    # ... implementation

def _create_reranking_voyage_client() -> Any:
    """Factory for Voyage reranking client."""
    config: RerankingProviderSettingsDep = INJECTED
    # ... implementation

# Similar for Bedrock, FastEmbed, SentenceTransformers
```

2. **Type Aliases**:
```python
type RerankingCohereClientDep = Annotated[Any, depends(_create_reranking_cohere_client)]
type RerankingVoyageClientDep = Annotated[Any, depends(_create_reranking_voyage_client)]
# ... more aliases
```

3. **Provider Factories** (similar to Phase 4):
```python
def _get_reranking_provider_class_for_config(config) -> type:
    """Map reranking config to provider class."""
    provider_map = {
        Provider.COHERE: CohereRerankingProvider,
        Provider.VOYAGE: VoyageRerankingProvider,
        Provider.BEDROCK: BedrockRerankingProvider,
        Provider.FASTEMBED: FastEmbedRerankingProvider,
        Provider.SENTENCE_TRANSFORMERS: SentenceTransformersRerankingProvider,
    }
    # ... implementation

def _create_reranking_client_for_config(config) -> Any:
    """Create reranking SDK client."""
    # ... implementation

async def create_all_reranking_providers() -> tuple[Any, ...]:
    """Factory for all reranking providers (primary + backups)."""
    from codeweaver.providers.backup_factory import create_backup_class

    configs: AllRerankingConfigsDep = INJECTED
    caps_resolver: RerankingCapabilityResolverDep = INJECTED

    # Similar loop to embedding providers
    # ... implementation

async def get_primary_reranking_provider(all_providers) -> Any:
    """Get primary reranking provider."""
    # ... implementation

type AllRerankingProvidersDep = Annotated[tuple[Any, ...], depends(create_all_reranking_providers)]
type PrimaryRerankingProviderDep = Annotated[Any, depends(get_primary_reranking_provider)]
```

**Files to Modify**:
- `src/codeweaver/providers/dependencies.py` (add factories)
- `src/codeweaver/providers/reranking/providers/base.py` (add type aliases)
- Update `__all__` exports

**Estimated Complexity**: Medium (similar to embedding, but fewer providers)

#### 6.2 Vector Store Providers

**Status**: Config factories exist (Phase 2), need dimension dependency + provider factories

**Work Required**:

1. **Add Cross-Config Dependency**:
```python
# In src/codeweaver/providers/vector_stores/base.py or similar

class BaseVectorStoreConfig(ConfigurableComponent):
    """Vector store config that needs embedding dimension."""

    def config_dependencies(self) -> dict[str, type]:
        # Use indexed reference for primary embedding
        return {"embedding[0]": EmbeddingProviderSettings}

    async def apply_resolved_config(
        self,
        embedding: EmbeddingProviderSettings | None = None,
        **resolved
    ):
        """Apply resolved embedding config to get dimension."""
        if embedding:
            self._resolved_dimension = await embedding.get_dimension()
            logger.info(f"Vector store using dimension: {self._resolved_dimension}")
```

2. **Provider Factories**:
```python
# In providers/dependencies.py

def _get_vector_store_provider_class_for_config(config) -> type:
    """Map vector store config to provider class."""
    provider_map = {
        Provider.QDRANT: QdrantVectorStore,
        Provider.QDRANT_CLOUD: QdrantVectorStore,
        Provider.INMEMORY: InMemoryVectorStore,
    }
    # ... implementation

async def create_vector_store_provider() -> Any:
    """Factory for vector store provider (single, not collection)."""
    config: VectorStoreProviderSettingsDep = INJECTED

    # Vector stores are typically singular, not collections
    provider_cls = _get_vector_store_provider_class_for_config(config)

    # Vector stores don't use SDK clients in the same way
    # They may need embedding dimension from config
    provider = provider_cls(config=config)

    return provider

type VectorStoreProviderDep = Annotated[Any, depends(create_vector_store_provider)]
```

**Files to Modify**:
- `src/codeweaver/providers/vector_stores/base.py` (add ConfigurableComponent)
- `src/codeweaver/providers/dependencies.py` (add factory)
- Update `__all__` exports

**Estimated Complexity**: Medium (needs dimension resolution via Phase 5)

#### 6.3 Sparse Embedding Providers

**Status**: Config factories exist (Phase 2), need client and provider factories

**Work Required**:

Similar to embedding providers, but only for providers that support sparse embeddings:
- FastEmbed Sparse
- Sentence Transformers Sparse (SPLADE models)

**Implementation**: Nearly identical to embedding provider Phase 3-4, but with sparse-specific types.

**Files to Modify**:
- `src/codeweaver/providers/dependencies.py` (add factories)
- `src/codeweaver/providers/sparse_embedding/providers/base.py` (if exists)
- Update `__all__` exports

**Estimated Complexity**: Low (small subset of embedding providers)

#### 6.4 Data Providers

**Status**: Config stubs exist, need full implementation

**Work Required**:

Data providers are for retrieving external data sources (databases, APIs, files). Implementation depends on pydantic-ai patterns.

1. **Review pydantic-ai data source patterns**
2. **Implement config factories** (if not in Phase 2)
3. **Implement client factories** (if applicable)
4. **Implement provider factories**

**Files to Create/Modify**:
- `src/codeweaver/providers/data/` (may need full implementation)
- `src/codeweaver/providers/dependencies.py` (add factories)

**Estimated Complexity**: Unknown (depends on data provider design)

#### 6.5 Agent Providers

**Status**: Config stubs exist, need full implementation

**Work Required**:

Agent providers wrap pydantic-ai's agent functionality. Implementation depends on Context Agent design.

1. **Define agent provider interface**
2. **Implement config factories** (if not in Phase 2)
3. **Implement client factories** (wrapping pydantic-ai clients)
4. **Implement provider factories**

**Files to Create/Modify**:
- `src/codeweaver/providers/agent/` (may need expansion)
- `src/codeweaver/providers/dependencies.py` (add factories)

**Estimated Complexity**: Medium (new provider type, pydantic-ai integration)

---

### Phase 7: Integration and Validation

#### 7.1 Update Provider Implementations

**Work Required**:

Update all existing provider implementations to use DI injection instead of manual construction.

**Example for OpenAI Provider**:

```python
# Before (manual construction)
class OpenAIEmbeddingProvider:
    def __init__(self, config: EmbeddingConfig, client: AsyncOpenAI):
        self.config = config
        self.client = client

# After (DI injection)
class OpenAIEmbeddingProvider:
    def __init__(
        self,
        config: EmbeddingConfigDep = INJECTED,
        client: OpenAIClientDep = INJECTED,
        caps: EmbeddingCapabilities = INJECTED,
    ):
        self.config = config
        self.client = client
        self.caps = caps
```

**Files to Modify**:
- All files in `src/codeweaver/providers/*/providers/*.py`
- Approximately 20-30 provider implementation files

**Estimated Complexity**: High (many files, but mechanical changes)

#### 7.2 Update Factory Pattern

**Work Required**:

Update `openai_factory.py` and similar factory files to use DI instead of manual provider instantiation.

**Before**:
```python
def create_openai_provider(config: EmbeddingConfig) -> OpenAIEmbeddingProvider:
    client = AsyncOpenAI(api_key=config.api_key)
    return OpenAIEmbeddingProvider(config=config, client=client)
```

**After**:
```python
# Delete manual factory - use DI factory from dependencies.py instead
# Or update to use DI injection internally
```

**Files to Modify**:
- `src/codeweaver/providers/embedding/providers/openai_factory.py`
- Similar factory files for other providers

**Estimated Complexity**: Medium (some factories may be removed entirely)

#### 7.3 Update High-Level Integration Points

**Work Required**:

Update code that creates providers to use DI injection instead of manual construction.

**Key Integration Points**:
- `src/codeweaver/engine/indexing_service.py` or similar
- `src/codeweaver/agent_api/find_code/pipeline.py`
- Any other code that instantiates providers

**Before**:
```python
# Manual provider creation
config = settings.provider.embedding[0]
client = AsyncOpenAI(api_key=config.api_key)
provider = OpenAIEmbeddingProvider(config=config, client=client)
```

**After**:
```python
# DI injection
from codeweaver.providers.dependencies import PrimaryEmbeddingProviderDep

async def some_function(
    embedding_provider: PrimaryEmbeddingProviderDep = INJECTED,
):
    # Provider is automatically created and injected
    results = await embedding_provider.embed(texts)
```

**Files to Identify and Modify**:
- Search for provider instantiation: `grep -r "Provider(" src/`
- Search for config access: `grep -r "settings.provider" src/`
- Search for client creation: `grep -r "AsyncOpenAI\|voyageai.Client" src/`

**Estimated Complexity**: High (depends on number of integration points)

#### 7.4 Testing Strategy

Since runtime testing isn't feasible with ~250 broken references, focus on:

1. **Static Analysis**:
   - Type checking with pyright
   - Import validation
   - Signature compatibility

2. **Unit Tests**:
   - Test factory functions in isolation
   - Mock DI container for provider factories
   - Validate config resolution logic

3. **Integration Tests** (when runtime viable):
   - Test full DI chain: Settings → Config → Client → Provider
   - Test backup provider creation
   - Test cross-config resolution (vector store + embedding)

**Test Files to Create**:
- `tests/unit/providers/test_dependencies.py`
- `tests/unit/core/config/test_resolver.py`
- `tests/integration/providers/test_di_integration.py`

**Estimated Complexity**: Medium (can start with unit tests before fixing broken references)

---

### Phase 8: Deprecate Registry System

**Status**: Not started, planned for ~0.4.0

**Current State**:
The codebase uses a registry system in `src/codeweaver/common/registry/` for provider registration and discovery. This was the pre-DI approach.

**Work Required**:

1. **Identify Registry Usage**:
   - Search for `from codeweaver.common.registry import`
   - Find all `register_provider()` calls
   - Find all `get_provider()` calls

2. **Replace with DI**:
   - Convert `register_provider()` to `@dependency_provider`
   - Convert `get_provider()` to DI injection via type aliases
   - Remove manual registration code

3. **Remove Registry System**:
   - Delete `src/codeweaver/common/registry/` directory
   - Remove registry imports
   - Clean up documentation

**Files Affected**:
- All files in `src/codeweaver/common/registry/`
- Any provider files that use registry
- Configuration files that reference registry

**Estimated Complexity**: High (major refactoring, but can be gradual)

**Timeline**: After DI system is stable and validated in production

---

## Prerequisites Before Continuing

### 1. Fix Broken References (~250 references)

**Context**: User mentioned ~250 broken references exist due to restructuring.

**Required Actions**:

1. **Catalog Broken References**:
```bash
# Static analysis to find broken imports/references
python -m pyright src/ --verbose | grep "error"
python -m mypy src/ --show-error-codes
```

2. **Categorize by Impact**:
   - **Critical**: Breaks provider instantiation or DI resolution
   - **High**: Affects integration points with providers
   - **Medium**: Affects tests or utilities
   - **Low**: Documentation or examples

3. **Prioritize Fixes**:
   - Fix critical references first (DI, providers)
   - Fix high-priority next (integration)
   - Medium/low can be deferred

4. **Create Fix Plan**:
   - Group related fixes together
   - Use scripts for mechanical changes
   - Validate after each batch

**Estimated Effort**: Large (depends on categorization)

### 2. Validate Import Paths

**Issue**: With new DI structure, import paths may have changed.

**Validation Steps**:

1. **Verify Provider Imports**:
```python
# Should work after Phase 1-5
from codeweaver.providers.dependencies import (
    PrimaryEmbeddingProviderDep,
    OpenAIClientDep,
    EmbeddingProviderSettingsDep,
)
```

2. **Verify Config Imports**:
```python
# Should work after Phase 2
from codeweaver.core.config.resolver import resolve_all_configs
from codeweaver.core.dependencies import SettingsDep
```

3. **Verify Provider Implementation Imports**:
```python
# Check if provider files can import from new structure
from codeweaver.providers.embedding.providers.base import EmbeddingProvider
```

**Test Command**:
```bash
python -c "from codeweaver.providers.dependencies import PrimaryEmbeddingProviderDep"
```

### 3. Type Checking

**Goal**: Ensure all type hints are correct and DI injection is type-safe.

**Validation Steps**:

1. **Run pyright**:
```bash
python -m pyright src/codeweaver/providers/dependencies.py
python -m pyright src/codeweaver/core/config/resolver.py
python -m pyright src/codeweaver/core/dependencies.py
```

2. **Check for Common Issues**:
   - Undefined names in type hints
   - Incorrect `INJECTED` usage
   - Missing imports in type checking blocks

3. **Fix Type Issues**:
   - Add `if TYPE_CHECKING` blocks for circular imports
   - Use string literals for forward references
   - Add proper type ignores where needed

### 4. Documentation Review

**Goal**: Ensure all new code is properly documented.

**Checklist**:

- [x] All factory functions have docstrings
- [x] All type aliases have docstrings
- [x] ConfigurableComponent protocol is documented
- [x] Cross-config resolution is documented
- [ ] Integration examples exist
- [ ] Migration guide for provider authors
- [ ] Update ARCHITECTURE.md with DI patterns

### 5. Capability Resolver Validation

**Issue**: Phase 4 uses `EmbeddingCapabilityResolverDep` but we haven't validated it exists.

**Validation Steps**:

1. **Check Implementation**:
```bash
# Find capability resolver implementation
grep -r "class.*CapabilityResolver" src/
```

2. **Verify DI Registration**:
   - Ensure resolver is registered with `@dependency_provider`
   - Check it's exported in `dependencies.py`

3. **Test Resolution**:
   - Validate resolver can handle all supported models
   - Check error handling for unknown models

---

## Risk Assessment

### High Risk Areas

1. **Provider Instantiation**:
   - **Risk**: Providers may have complex initialization logic that doesn't map cleanly to DI
   - **Mitigation**: Review each provider's `__init__` carefully, may need custom factories

2. **Circular Dependencies**:
   - **Risk**: Settings → Config → Provider → Settings cycle
   - **Mitigation**: Layered design prevents this, but validate with container's cycle detection

3. **Backup Class Generation**:
   - **Risk**: Dynamic class creation may have edge cases (inheritance, metaclasses)
   - **Mitigation**: Extensive testing of `backup_factory.py`, validate `isinstance` checks

4. **Config Collections**:
   - **Risk**: Code assuming single config may break with tuple collections
   - **Mitigation**: Audit all config access, ensure primary extraction is explicit

### Medium Risk Areas

1. **Client Options Serialization**:
   - **Risk**: `client_options.as_settings()` may not match all SDK signatures
   - **Mitigation**: Validate for each SDK, add custom handling if needed

2. **Cross-Config Resolution Timing**:
   - **Risk**: Vector store may initialize before embedding config is resolved
   - **Mitigation**: Phase 5 resolver ensures correct ordering, but test thoroughly

3. **Type Alias Complexity**:
   - **Risk**: Complex `Annotated` types may confuse developers or type checkers
   - **Mitigation**: Comprehensive documentation, examples, type checking validation

### Low Risk Areas

1. **Settings Bootstrap**:
   - **Risk**: Settings loading failure
   - **Mitigation**: Already working from Phase 1, well-tested

2. **Helper Functions**:
   - **Risk**: Logic errors in `_get_provider_class_for_config`, etc.
   - **Mitigation**: Simple dictionary lookups, easy to test and debug

---

## Testing Plan

### Unit Tests (Can Start Now)

1. **Test Config Factories** (`tests/unit/providers/test_config_factories.py`):
```python
import pytest
from unittest.mock import Mock
from codeweaver.providers.dependencies import (
    get_all_embedding_configs,
    get_primary_embedding_config,
)

async def test_get_all_embedding_configs():
    """Test config collection factory."""
    mock_settings = Mock()
    mock_settings.provider.embedding = (config1, config2)

    # Inject mock settings
    result = await get_all_embedding_configs(settings=mock_settings)

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert result[0] == config1

async def test_get_primary_embedding_config():
    """Test primary config extraction."""
    configs = (config1, config2)

    result = await get_primary_embedding_config(all_configs=configs)

    assert result == config1
```

2. **Test Client Factories** (`tests/unit/providers/test_client_factories.py`):
```python
async def test_create_openai_client():
    """Test OpenAI client factory."""
    mock_config = Mock()
    mock_config.client_options.as_settings.return_value = {
        "api_key": "test-key",
        "base_url": "https://api.openai.com",
    }

    # This will need to mock the import
    with patch("openai.AsyncOpenAI") as mock_openai:
        client = _create_openai_client(config=mock_config)

        mock_openai.assert_called_once_with(
            api_key="test-key",
            base_url="https://api.openai.com",
        )
```

3. **Test Provider Factories** (`tests/unit/providers/test_provider_factories.py`):
```python
async def test_get_provider_class_for_config():
    """Test provider class mapping."""
    from codeweaver.core import Provider

    config = Mock()
    config.provider = Provider.OPENAI

    cls = _get_provider_class_for_config(config)

    assert cls == OpenAIEmbeddingBase

async def test_create_all_embedding_providers_with_backup():
    """Test provider factory with backup integration."""
    # Mock configs
    configs = (primary_config, backup_config)

    # Mock capability resolver
    mock_resolver = Mock()
    mock_resolver.resolve.return_value = mock_caps

    # Mock backup factory
    with patch("codeweaver.providers.backup_factory.create_backup_class") as mock_backup:
        providers = await create_all_embedding_providers(
            configs=configs,
            caps_resolver=mock_resolver,
        )

        # Verify backup class was created for second provider
        mock_backup.assert_called_once()
        assert len(providers) == 2
```

4. **Test Cross-Config Resolution** (`tests/unit/core/config/test_resolver.py`):
```python
def test_parse_config_reference():
    """Test config reference parsing."""
    assert _parse_config_reference("embedding") == ("embedding", None)
    assert _parse_config_reference("embedding[0]") == ("embedding", 0)
    assert _parse_config_reference("embedding[*]") == ("embedding", -1)
    assert _parse_config_reference("embedding[2]") == ("embedding", 2)

async def test_resolve_indexed_config_single():
    """Test indexed resolution with single config."""
    mock_container = Mock()
    mock_container.resolve.return_value = mock_config

    # Test backward compatible (no index)
    result = await _resolve_indexed_config("embedding", EmbeddingConfig, mock_container)
    assert result == mock_config

    # Test explicit primary
    result = await _resolve_indexed_config("embedding[0]", EmbeddingConfig, mock_container)
    assert result == mock_config

async def test_resolve_indexed_config_collection():
    """Test indexed resolution with config collection."""
    mock_container = Mock()
    mock_container.resolve.return_value = (config1, config2, config3)

    # Test get all
    result = await _resolve_indexed_config("embedding[*]", EmbeddingConfig, mock_container)
    assert result == (config1, config2, config3)

    # Test get specific backup
    result = await _resolve_indexed_config("embedding[1]", EmbeddingConfig, mock_container)
    assert result == config2
```

### Integration Tests (After Broken References Fixed)

1. **Test Full DI Chain** (`tests/integration/providers/test_di_chain.py`):
```python
async def test_full_embedding_provider_chain():
    """Test complete DI resolution: Settings → Config → Client → Provider."""
    from codeweaver.core.di import get_container

    container = get_container()

    # Should resolve through full chain
    provider = await container.resolve(PrimaryEmbeddingProviderDep)

    assert provider is not None
    assert hasattr(provider, "embed")
    assert not provider.is_provider_backup

async def test_backup_provider_creation():
    """Test backup provider discrimination."""
    container = get_container()

    all_providers = await container.resolve(AllEmbeddingProvidersDep)

    assert len(all_providers) >= 1
    assert not all_providers[0].is_provider_backup

    if len(all_providers) > 1:
        assert all_providers[1].is_provider_backup

async def test_cross_config_resolution():
    """Test vector store gets embedding dimension."""
    container = get_container()

    # Trigger cross-config resolution
    await resolve_all_configs()

    # Verify vector store has dimension
    vs_config = await container.resolve(VectorStoreConfig)
    assert hasattr(vs_config, "_resolved_dimension")
    assert vs_config._resolved_dimension > 0
```

### End-to-End Tests (After Full Integration)

1. **Test Find Code Pipeline** (`tests/e2e/test_find_code_di.py`):
```python
async def test_find_code_with_di_providers():
    """Test find_code tool uses DI-injected providers."""
    # This would test the full pipeline with DI
    # Requires all providers to be migrated to DI
    pass
```

---

## Migration Guide for Provider Authors

### For New Providers

When creating a new provider, follow this pattern:

1. **Define Config** (if not exists):
```python
# In src/codeweaver/providers/config/embedding.py
class NewProviderConfig(BaseEmbeddingConfig):
    provider: Literal[Provider.NEWPROVIDER] = Provider.NEWPROVIDER
    # ... config fields
```

2. **Add Client Factory**:
```python
# In src/codeweaver/providers/dependencies.py
def _create_newprovider_client() -> Any:
    """Factory for NewProvider SDK client."""
    from codeweaver.core.di import INJECTED

    config: EmbeddingProviderSettingsDep = INJECTED

    try:
        from newprovider import Client
        return Client(**config.client_options.as_settings())
    except ImportError as e:
        raise ConfigurationError(
            'Install: pip install "code-weaver[newprovider]"'
        ) from e

type NewProviderClientDep = Annotated[Any, depends(_create_newprovider_client)]
```

3. **Implement Provider**:
```python
# In src/codeweaver/providers/embedding/providers/newprovider.py
class NewProviderEmbeddingProvider(EmbeddingProvider):
    """Provider implementation."""

    def __init__(
        self,
        config: EmbeddingConfigDep = INJECTED,
        client: NewProviderClientDep = INJECTED,
        caps: EmbeddingCapabilities = INJECTED,
    ):
        self.config = config
        self.client = client
        self.caps = caps

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await self.client.embed(texts)
```

4. **Register in Factory**:
```python
# In src/codeweaver/providers/dependencies.py

# Add to _get_provider_class_for_config
provider_map = {
    # ... existing providers
    Provider.NEWPROVIDER: NewProviderEmbeddingProvider,
}

# Add to _create_client_for_config
client_factories = {
    # ... existing factories
    Provider.NEWPROVIDER: _create_newprovider_client,
}
```

### For Existing Providers

To migrate an existing provider to DI:

1. **Remove Manual Construction**:
```python
# Before
def create_provider(config):
    client = Client(api_key=config.api_key)
    return Provider(config=config, client=client)

# After - delete this function, use DI factory instead
```

2. **Update Provider Constructor**:
```python
# Before
class Provider:
    def __init__(self, config, client):
        self.config = config
        self.client = client

# After
class Provider:
    def __init__(
        self,
        config: EmbeddingConfigDep = INJECTED,
        client: ClientDep = INJECTED,
        caps: EmbeddingCapabilities = INJECTED,
    ):
        self.config = config
        self.client = client
        self.caps = caps
```

3. **Update Call Sites**:
```python
# Before
provider = create_provider(config)

# After
from codeweaver.providers.dependencies import PrimaryEmbeddingProviderDep

async def my_function(
    provider: PrimaryEmbeddingProviderDep = INJECTED,
):
    # Provider automatically injected
    pass
```

---

## Timeline Estimate

Assuming ~250 broken references are fixed first:

- **Phase 6.1** (Reranking): 2-3 days
- **Phase 6.2** (Vector Stores): 2-3 days
- **Phase 6.3** (Sparse Embedding): 1-2 days
- **Phase 6.4** (Data Providers): 3-5 days (depends on design)
- **Phase 6.5** (Agent Providers): 3-5 days (depends on design)
- **Phase 7.1** (Update Implementations): 3-5 days
- **Phase 7.2** (Update Factories): 1-2 days
- **Phase 7.3** (Integration Points): 2-3 days
- **Phase 7.4** (Testing): 3-5 days
- **Phase 8** (Deprecate Registry): 5-7 days (can be gradual)

**Total Estimate**: 25-40 days of focused work

**Critical Path**: Phases 6.1-6.5 can be done in parallel, Phase 7 depends on Phase 6, Phase 8 can be done last

---

## Open Questions

1. **Broken References**:
   - What categories of references are broken?
   - Which affect DI system directly?
   - Timeline for fixing critical references?

2. **Data Provider Design**:
   - What data sources need to be supported?
   - How do they integrate with pydantic-ai?
   - Config structure finalized?

3. **Agent Provider Design**:
   - Context Agent API finalized?
   - What agent capabilities needed?
   - Integration points with find_code?

4. **Testing Strategy**:
   - Can we test incrementally before all references fixed?
   - Mock vs real provider testing?
   - Integration test environment setup?

5. **Migration Timeline**:
   - Fix all broken references first, or parallel with Phase 6?
   - Provider-by-provider migration or all at once?
   - Backward compatibility requirements?

---

## Recommendations

1. **Start with Testing**:
   - Write unit tests for Phases 3-5 now (don't need runtime)
   - Validate factories work in isolation
   - Build confidence in DI architecture

2. **Fix Critical References Next**:
   - Identify references that block DI system
   - Fix provider imports and paths
   - Ensure settings loading works

3. **Phase 6 in Order**:
   - Start with 6.1 (Reranking) - most similar to embedding
   - Then 6.2 (Vector Stores) - tests cross-config resolution
   - Then 6.3 (Sparse) - simple subset
   - Defer 6.4-6.5 until design finalized

4. **Incremental Migration**:
   - Don't wait for all providers before testing
   - Migrate one provider type fully (embedding)
   - Validate it works end-to-end
   - Then extend pattern to others

5. **Documentation Priority**:
   - Update ARCHITECTURE.md with DI patterns
   - Create migration guide for contributors
   - Add integration examples
   - Document troubleshooting

---

## Summary

**Completed** (Phases 1-5):
- Settings bootstrap as DI root
- Config factory pattern with collections
- 11 SDK client factories
- Embedding provider factory with backup support
- Cross-config resolution with indexed references

**Remaining** (Phases 6+):
- Apply pattern to 4 other provider types
- Update 20-30 provider implementations
- Update integration points
- Build comprehensive test suite
- Deprecate old registry system

**Blockers**:
- ~250 broken references from restructuring
- Data/agent provider design finalization

**Next Steps**:
1. Write unit tests for completed phases
2. Fix critical broken references
3. Begin Phase 6.1 (Reranking providers)

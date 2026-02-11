<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Reranking Provider DI Migration Plan

## Overview

Migrate reranking providers to align with the new DI patterns established in embedding providers. The embedding providers serve as the reference implementation for this migration.

## Background

The embedding providers have been refactored to:
1. Remove singleton patterns and classvars in favor of multiple instances
2. Use factory functions in `dependencies.py` for DI-based provider construction
3. Separate backup/primary logic into the DI layer (not provider classes)
4. Use capability resolvers for model queries and CLI listing
5. Simplify provider constructors to receive pre-built clients and configs

## Key Pattern Differences: Embedding vs Reranking

### Embedding Providers Pattern

```python
class EmbeddingProvider:
    client: EmbeddingClient  # Injected SDK client
    config: EmbeddingProviderSettings  # Full config with embedding/query/model options
    registry: EmbeddingRegistry  # Embedding cache/dedup
    caps: EmbeddingModelCapabilities | None

    # Instance-level stores (not classvars)
    _store: UUIDStore[list] = make_uuid_store(...)
    _hash_store: BlakeStore[UUID7] = make_blake_store(...)

    def __init__(self, client, config, registry, caps, ...):
        # Initialize instance attributes
        object.__setattr__(self, "_store", make_uuid_store(...))
        object.__setattr__(self, "_hash_store", make_blake_store(...))
        self._initialize(impl_deps, custom_deps)
        super().__init__(client=client, config=config, caps=caps, registry=registry)
```

### Reranking Providers Current State

```python
class RerankingProvider:
    client: RerankingClient
    caps: RerankingModelCapabilities

    # PROBLEM: ClassVar for shared state
    _rerank_kwargs: ClassVar[MappingProxyType[str, Any]]

    # PROBLEM: Complex constructor with many kwargs
    def __init__(self, client, caps, top_n=40, **kwargs):
        # Complex kwargs merging logic
        _rerank_kwargs = kwargs or {}
        class_rerank_kwargs = type(self)._rerank_kwargs
        ...
```

## Migration Tasks

### Phase 1: Update Base RerankingProvider Class

**File**: `src/codeweaver/providers/reranking/providers/base.py`

#### Task 1.1: Remove ClassVar Pattern

**Current**:
```python
_rerank_kwargs: ClassVar[MappingProxyType[str, Any]]
```

**New**:
```python
# Remove ClassVar, make instance-level
_rerank_kwargs: dict[str, Any] = {}
```

**Rationale**: Each provider instance should have its own kwargs, not share them via ClassVar. This enables multiple instances with different configurations.

#### Task 1.2: Simplify Constructor Signature

**Current**:
```python
def __init__(
    self,
    client: RerankingClient,
    caps: RerankingModelCapabilities,
    top_n: PositiveInt = 40,
    **kwargs: Any,
) -> None:
```

**New**:
```python
def __init__(
    self,
    client: RerankingClient,
    config: RerankingProviderSettings,  # Add config parameter
    caps: RerankingModelCapabilities,  # Keep as 'caps' not 'capabilities'
    **kwargs: Any,
) -> None:
```

**Changes**:
- Add `config: RerankingProviderSettings` parameter
- Config contains `reranking_options` (kwargs for rerank calls)
- Remove complex kwargs merging - get from config instead
- **IMPORTANT**: Parameter is `caps` not `capabilities` for consistency
- Constructor parameters are normal names: `client`, `config`, `caps` (no underscores)
- Field definitions keep `validation_alias="_client"` etc. for pydantic internals

#### Task 1.3: Update Constructor Implementation

**Current**:
```python
def __init__(self, client, caps, top_n=40, **kwargs):
    _rerank_kwargs = kwargs or {}
    with contextlib.suppress(AttributeError, TypeError):
        class_rerank_kwargs = type(self)._rerank_kwargs
        if class_rerank_kwargs and isinstance(class_rerank_kwargs, dict):
            _rerank_kwargs = {**class_rerank_kwargs, **_rerank_kwargs}
    ...
```

**New**:
```python
def __init__(
    self,
    client: RerankingClient,
    config: RerankingProviderSettings,
    caps: RerankingModelCapabilities,  # Note: 'caps' not 'capabilities'
    **kwargs: Any,
) -> None:
    # Store for later pydantic initialization
    object.__setattr__(self, "_model_dump_json", super().model_dump_json)

    # Initialize circuit breaker state
    object.__setattr__(self, "_circuit_state", CircuitBreakerState.CLOSED)
    object.__setattr__(self, "_failure_count", 0)
    object.__setattr__(self, "_last_failure_time", None)

    # Extract rerank options from config
    rerank_options = config.reranking if config and config.reranking else {}
    object.__setattr__(self, "_rerank_kwargs", rerank_options | kwargs)
    object.__setattr__(self, "_top_n", rerank_options.get("top_n", 40))

    # Initialize pydantic
    super().__init__(client=client, caps=caps, config=config)  # Note: caps=caps

    # Optional post-initialization hook
    self._initialize()
```

#### Task 1.4: Add Config Field to Base Class

```python
config: Annotated[
    RerankingProviderSettings,
    Field(description="Configuration for the reranking model, including all request options."),
]
```

This mirrors the embedding provider pattern.

### Phase 2: Update Individual Reranking Providers

**Files**:
- `src/codeweaver/providers/reranking/providers/voyage.py`
- `src/codeweaver/providers/reranking/providers/cohere.py`
- `src/codeweaver/providers/reranking/providers/bedrock.py`
- `src/codeweaver/providers/reranking/providers/fastembed.py`
- `src/codeweaver/providers/reranking/providers/sentence_transformers.py`

#### Task 2.1: Update Constructor Signatures

**Current (Voyage example)**:
```python
def __init__(
    self,
    client: AsyncClient | None = None,
    caps: RerankingModelCapabilities | None = None,
    **kwargs: Any,
) -> None:
```

**New**:
```python
def __init__(
    self,
    client: AsyncClient,
    config: RerankingProviderSettings,
    caps: RerankingModelCapabilities,  # Keep as 'caps'
    **kwargs: Any,
) -> None:
```

**Changes**:
- Remove `| None` from client and caps - they're required now (provided by DI)
- Add `config` parameter
- **IMPORTANT**: Keep parameter name as `caps` (NOT `capabilities`)
- All constructor parameters use normal names: `client`, `config`, `caps` (no underscores)

#### Task 2.2: Remove Provider-Level Client/Caps Creation

**Current (Voyage example)**:
```python
if caps is None:
    from codeweaver.core import get_model_registry
    registry = get_model_registry()
    caps = registry.configured_models_for_category("reranking")
    ...

if client is None:
    if api_key := kwargs.pop("api_key", None) or os.getenv("VOYAGE_API_KEY"):
        client = AsyncClient(api_key=api_key)
```

**New**:
```python
# Remove all this - client and caps come from DI system
# Just call super().__init__
super().__init__(client=client, config=config, caps=caps, **kwargs)
```

**Rationale**: Client creation happens in `dependencies.py` now. Providers should not create their own clients.

**IMPORTANT**: Use `caps=caps` not `capabilities=capabilities` in the super() call!

#### Task 2.3: Remove ClassVar Definitions

**Current**:
```python
_rerank_kwargs: MappingProxyType[str, Any]
```

**New**: Remove entirely. Instance-level `_rerank_kwargs` is in base class now.

### Phase 3: Verify dependencies.py (Already Complete)

**File**: `src/codeweaver/providers/dependencies.py`

The following are already implemented:

✅ Client factories:
- `_create_reranking_client()` (lines 245-269)

✅ Config factories:
- `_create_all_reranking_configs()` (lines 453-463)
- `_create_primary_reranking_config()` (lines 466-469)
- `_create_backup_reranking_config()` (lines 472-475)

✅ Type aliases:
- `RerankingProviderSettingsDep` (lines 478-481)
- `BackupRerankingProviderSettingsDep` (lines 484-487)
- `AllRerankingConfigsDep` (lines 490-494)
- `RerankingCapabilityResolverDep` (lines 497-500)

✅ Provider factories:
- `_get_reranking_provider_for_config()` (lines 813-829)
- `_get_backup_reranking_provider_for_config()` (lines 832-850)

✅ Provider type aliases:
- `RerankingProviderDep` (lines 853-859)
- `BackupRerankingProviderDep` (lines 862-869)

**Verification needed**: Ensure provider factories match new constructor signature.

#### Task 3.1: Update Provider Factory to Pass Config

**Current** (lines 813-829):
```python
def _get_reranking_provider_for_config(config: RerankingProviderSettings) -> RerankingProvider:
    client = _resolve_client(config.client)
    capabilities = config.reranking_config.capabilities
    provider = config.client.reranking_provider
    try:
        resolved_provider = provider._resolve()
    except (AttributeError, ImportError) as e:
        raise ConfigurationError(...)
    client = _instantiate_client(client, config.client_options)
    return resolved_provider(client=client, capabilities=capabilities, config=config)
```

**CRITICAL Update Needed**:
```python
# Change from:
return resolved_provider(client=client, capabilities=capabilities, config=config)

# To (using consistent 'caps' naming):
return resolved_provider(client=client, config=config, caps=capabilities)
```

**Rationale**: Constructor parameter is `caps`, but we extract it as `capabilities` from config. Rename in the call to match the constructor signature.

**Also update embedding factory** (`_get_embedding_provider_for_config`):
```python
# Change from:
return resolved_provider(client=client, registry=registry, capabilities=capabilities, config=config)

# To:
return resolved_provider(client=client, registry=registry, caps=capabilities, config=config)
```

### Phase 4: Config Structure Verification

**File**: `src/codeweaver/providers/config/providers.py`

Need to verify reranking config has proper structure similar to embedding.

#### Expected Structure (based on embedding):

```python
class SomeRerankingProviderSettings(BaseProviderCategorySettings):
    provider: Literal[Provider.SOME_PROVIDER]

    # Model configuration
    model_name: str

    # Reranking-specific options (like query_options/embed_options for embedding)
    reranking: dict[str, Any] | None = None  # kwargs for rerank() calls

    # Client configuration
    client_options: ClientOptions | None = None

    # Capabilities reference
    reranking_config: RerankingConfig  # Contains capabilities

    # SDK client reference
    @property
    def client(self) -> SDKClient:
        return SDKClient(
            as_title="Some Provider",
            client=lazy_import("some_sdk", "SomeClient"),
            reranking_provider=lazy_import("codeweaver.providers.reranking.providers", "SomeRerankingProvider")
        )
```

#### Task 4.1: Verify/Create RerankingConfig Type

Should mirror `EmbeddingConfig`:
```python
class RerankingConfig:
    capabilities: RerankingModelCapabilities
    # Any other reranking-specific config
```

#### Task 4.2: Verify Provider Settings Have Proper Structure

Check each provider settings class (VoyageRerankingProviderSettings, CohereRerankingProviderSettings, etc.) has:
- `reranking: dict[str, Any]` field for method kwargs
- `reranking_config: RerankingConfig` field with capabilities
- `client_options: ClientOptions` field

### Phase 5: Update Tests

**Files**:
- `tests/unit/providers/reranking/test_*.py`
- `tests/integration/providers/reranking/test_*.py`

#### Task 5.1: Update Provider Initialization in Tests

**Current**:
```python
provider = VoyageRerankingProvider(client=mock_client, caps=mock_caps)
```

**New**:
```python
provider = VoyageRerankingProvider(
    client=mock_client,
    config=mock_config,
    caps=mock_caps  # Note: 'caps' not 'capabilities'
)
```

#### Task 5.2: Remove ClassVar Tests

Any tests that relied on ClassVar behavior need updating.

#### Task 5.3: Add DI Integration Tests

Test that:
- Primary/backup configs resolve correctly
- Provider factories create providers correctly
- Capability resolver works

### Phase 6: Update CLI/Registry Integration

**File**: `src/codeweaver/cli/commands/list.py`

Ensure CLI commands use `RerankingCapabilityResolver` for listing models/providers.

#### Task 6.1: Verify Capability Resolver Usage

```python
# Should use DI-injected resolver
def list_reranking_models(resolver: RerankingCapabilityResolverDep = INJECTED):
    models = resolver.list_models()
    # Display logic
```

## Implementation Order

1. **Phase 1**: Update `RerankingProvider` base class
2. **Phase 2**: Update individual provider implementations (Voyage first as reference)
3. **Phase 3**: Verify dependencies.py factories (minimal changes expected)
4. **Phase 4**: Verify/update config structures
5. **Phase 5**: Update tests
6. **Phase 6**: Verify CLI integration

## Testing Strategy

### Unit Tests
- Provider initialization with new constructor
- Circuit breaker behavior
- Error handling

### Integration Tests
- DI resolution of providers
- Primary/backup provider creation
- End-to-end reranking with DI-injected providers

### Manual Testing
- `cw list reranking` - should use capability resolver
- Reranking in find_code pipeline
- Backup provider fallback

## Success Criteria

1. ✅ No classvars for shared state in reranking providers
2. ✅ Constructor signature matches embedding provider pattern
3. ✅ All providers receive client and config from DI system
4. ✅ Backup providers created via factory pattern
5. ✅ Capability resolver works for model listing
6. ✅ All tests pass
7. ✅ CLI commands work correctly
8. ✅ No broken references in IDE
9. ✅ **Naming consistency**: All use `caps` not `capabilities`
10. ✅ **Normal parameter names**: `client`, `config`, `caps` (no underscores in constructor signatures)

## Dependencies

- Embedding provider pattern (complete)
- `dependencies.py` factories (complete)
- Config types in `providers.py` (needs verification)
- Capability resolver (complete)

## Risks & Mitigations

### Risk: Breaking existing provider usage
**Mitigation**: Update all provider instantiations in tests first to verify pattern

### Risk: Config structure incomplete
**Mitigation**: Review embedding config structure as reference, ensure parity

### Risk: Missing backup logic
**Mitigation**: Verify `create_backup_class()` works correctly for reranking

## Notes

- Reranking does NOT need a registry like embedding (no deduplication needed)
- Circuit breaker pattern is already implemented correctly
- Retry logic is already implemented correctly
- The main changes are structural (remove classvars, update constructors)

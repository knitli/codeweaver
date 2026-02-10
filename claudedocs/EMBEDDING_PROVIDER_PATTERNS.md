<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Embedding Provider DI Patterns - Reference Document

**Branch**: `feat/di_monorepo`
**Status**: Reference for implementation alignment
**Date**: 2025-01-06

## Executive Summary

This document captures the DI patterns discovered in the base embedding provider (`providers/embedding/providers/base.py`) and establishes the standard patterns that all provider implementations must follow. This is critical for the next phase: ensuring all implemented providers align with the new DI-driven patterns.

---

## Base Class Patterns

### 1. **`__init__` Method Signature**

```python
def __init__(
    self,
    client: ClientDep[EmbeddingClient] = INJECTED,
    config: EmbeddingConfigT | None = None,
    caps: EmbeddingCapabilityResolverDep | NoneDep = INJECTED,
    impl_deps: EmbeddingImplementationDeps = None,
    custom_deps: EmbeddingCustomDeps = None,
    **kwargs: Any,
) -> None:
```

**Pattern Analysis:**

| Parameter | Type | Source | Purpose |
|-----------|------|--------|---------|
| `client` | `ClientDep[EmbeddingClient]` | DI-injected | Pre-configured SDK client (e.g., AsyncOpenAI, AsyncClient) |
| `config` | `EmbeddingConfigT \| None` | Passed or DI | Provider configuration with embedding/query options |
| `caps` | `EmbeddingCapabilityResolverDep \| NoneDep` | DI-injected | Model capabilities or None (optional) |
| `impl_deps` | `EmbeddingImplementationDeps` | Optional | Implementation-specific dependencies (placeholder) |
| `custom_deps` | `EmbeddingCustomDeps` | Optional | Custom user-provided dependencies (placeholder) |
| `**kwargs` | `Any` | Optional | Additional initialization parameters (store configs, etc.) |

**Key Characteristics:**
- SDK `client` is **pre-configured and ready to use** - no construction logic in provider
- Settings contain ALL SDK-compatible parameters - no transformation in provider
- Capabilities are optional - some providers may not need them
- Implementation and custom deps are extensibility points for specialized needs
- Uses `object.__setattr__` to set attributes during init (avoiding pydantic validation issues)

---

### 2. **`_initialize` Method Signature**

```python
@abstractmethod
def _initialize(
    self,
    impl_deps: EmbeddingImplementationDeps = None,
    custom_deps: EmbeddingCustomDeps = None
) -> None:
    """Initialize the embedding provider.

    This method is called at the end of __init__ and before pydantic validation
    to allow for any additional setup. It offers a flexible opportunity to insert
    implementation-specific or custom dependencies needed for the provider.
    """
```

**Pattern Analysis:**

- **Called in `__init__` BEFORE pydantic validation** - allows setup of mutable state
- **Abstract in base** - each provider implements its own initialization logic
- **Receives dependencies** - impl_deps and custom_deps for provider-specific setup
- **Does NOT receive** - client, config, or caps (already set as attributes)

**Typical Implementation Pattern (from VoyageEmbeddingProvider):**

```python
def _initialize(self, caps: EmbeddingModelCapabilities) -> None:
    # Provider-specific setup using capabilities
    self._is_context_model = 'context' in caps.name

    # Build request options combining config + capabilities
    configured_dimension = self.get_dimension()
    shared_kwargs = {
        'model': caps.name,
        'output_dimension': configured_dimension,
        'output_dtype': 'float'
    }

    # Update class kwargs (CURRENT PATTERN - to be replaced)
    self.embed_options |= shared_kwargs
    self.query_options |= shared_kwargs
```

**Note**: The current pattern of mutating ClassVars is being replaced by the new DI pattern where options are stored in `config` instead.

---

### 3. **Core Attributes**

```python
class EmbeddingProvider[EmbeddingClient](BasedModel, ABC):
    # SDK Client (DI-injected)
    client: Annotated[
        SkipValidation[EmbeddingClient],
        Field(
            description="The client for the embedding provider.",
            exclude=True,
            validation_alias="_client",
        ),
    ]

    # Model Capabilities (DI-injected)
    caps: Annotated[
        EmbeddingModelCapabilities | None,
        Field(
            description="The capabilities of the embedding model. Can be None if not available."
        ),
    ] = None

    # Configuration (contains embedding & query options)
    config: Annotated[
        EmbeddingConfigT,
        Field(
            description="Configuration for the embedding model, including all request options."
        ),
    ]

    # ClassVars for transformers (to be replaced)
    _provider: ClassVar[LiteralProvider] = cast(LiteralProvider, Provider.NOT_SET)
    _input_transformer: ClassVar[Callable[[StructuredDataInput], Any]] = ...
    _output_transformer: ClassVar[Callable[[Any], list[list[float]]]]] = ...
```

**Attribute Patterns:**

| Attribute | Type | Mutability | Purpose |
|-----------|------|-----------|---------|
| `client` | `EmbeddingClient` | Immutable | Pre-configured SDK client |
| `config` | `EmbeddingConfigT` | Immutable (pydantic) | All SDK-compatible settings |
| `caps` | `EmbeddingModelCapabilities \| None` | Immutable | Model capabilities (optional) |
| `_provider` | `ClassVar[LiteralProvider]` | Class-level | Identifies provider type |
| `_output_transformer` | `ClassVar[Callable]` | Class-level | Transforms provider output to standard format |

---

## Configuration Structure

### **EmbeddingConfigT Attributes**

The `config` attribute contains two key dict fields for SDK requests:

```python
class BaseEmbeddingConfig(BasedModel):
    provider: Provider  # e.g., Provider.VOYAGE
    model_name: LiteralString  # e.g., "voyage-code-3"

    # Document embedding request parameters
    embedding: dict[str, Any] | None = None
    # Example: {'input_type': 'document', 'model': '...', 'output_dimension': 1024}

    # Query embedding request parameters
    query: dict[str, Any] | None = None
    # Example: {'input_type': 'query', 'model': '...', 'output_dimension': 1024}
```

**How Embedding/Query Options Work:**

1. **User Config** (TOML/env vars):
   ```toml
   [provider.embedding]
   provider = "voyage"
   model_name = "voyage-code-3"
   embedding = {input_type = "document"}
   query = {input_type = "query"}
   ```

2. **DI Resolution** creates `EmbeddingConfigT` with embedded options

3. **Provider Usage** in `_embed_documents`:
   ```python
   results = await self.client.embed(
       texts=documents,
       **kwargs | self.config.embedding  # Merge with config options
   )
   ```

**Current Implementation Detail:**
- ClassVars `embed_options` and `query_options` are mutated in `_initialize()`
- **New pattern**: Options should be stored in `config` instead, not mutated ClassVars

---

## Type Aliases & DI Infrastructure

### **Generic Client Dependency**

```python
# From providers/dependencies.py
SDKClientType = TypeVar("SDKClientType")

type ClientDep[T] = Annotated[T, depends(lambda: None)]
```

**Usage Pattern:**
```python
def __init__(
    self,
    client: ClientDep[AsyncOpenAI] = INJECTED,  # Specialized for OpenAI
    ...
):
```

---

### **Embedding-Specific Dependencies**

```python
# From providers/embedding/providers/base.py

# Provider implementation can request implementation-specific dependencies
type EmbeddingImplementationDeps = Annotated[Any, depends(lambda: None)]

# Providers can request custom dependencies
type EmbeddingCustomDeps = Annotated[Any, depends(lambda: None)]

# Capability resolver (always optional)
from codeweaver.providers.embedding import EmbeddingCapabilityResolverDep
```

---

### **Provider Settings Dependencies**

```python
# From providers/dependencies.py

# Root settings container
type ProviderSettingsDep = Annotated[
    ProviderSettings,
    depends(_create_provider_settings_dep),
]

# Specific embedding settings (discriminated union by provider)
type EmbeddingProviderSettingsDep = Annotated[
    EmbeddingProviderSettingsType,  # Union of all embedding providers
    depends(_create_embedding_provider_settings_dep),
]

# Provider-specific types
type VoyageEmbeddingProviderSettingsDep = Annotated[
    VoyageEmbeddingConfig,
    depends(_create_voyage_embedding_settings_dep),
]
```

---

## Implementation Checklist for Providers

When reviewing implemented providers, verify:

### **Class Definition**
- [ ] Inherits from `EmbeddingProvider[ClientType]`
- [ ] `_provider` ClassVar set to correct provider
- [ ] Generic client type specified (e.g., `AsyncOpenAI`, `AsyncClient`)

### **`__init__` Compatibility**
- [ ] Calls `super().__init__(client=client, config=config, caps=caps, **defaults)`
- [ ] Uses `object.__setattr__` for any custom attributes
- [ ] Accepts `impl_deps` and `custom_deps` parameters
- [ ] Passes them to `_initialize()`

### **`_initialize` Implementation**
- [ ] Abstract method implemented (not using base implementation)
- [ ] Receives capabilities and sets up provider state
- [ ] **NEW PATTERN**: Options should be extracted from `config` instead of mutating ClassVars
- [ ] Can receive and use `impl_deps` and `custom_deps`

### **Attributes**
- [ ] No direct mutation of `embed_options` or `query_options` (ClassVars)
- [ ] Uses `self.config.embedding` and `self.config.query` for request options
- [ ] Optional: defines `_output_transformer` if needed
- [ ] Uses `caps` (EmbeddingModelCapabilities) for configuration

### **Request Methods**
- [ ] `_embed_documents(documents, **kwargs)` merges kwargs with `config.embedding`
- [ ] `_embed_query(query, **kwargs)` merges kwargs with `config.query`
- [ ] Both return `list[list[float]]` or `list[list[int]]`

### **Error Handling**
- [ ] Uses circuit breaker pattern (inherited from base)
- [ ] Proper logging of failures
- [ ] Graceful degradation for batch issues (e.g., token limits)

---

## Key Findings - State Management

### **OLD PATTERN (Being Replaced)**
```python
class VoyageEmbeddingProvider(EmbeddingProvider[AsyncClient]):
    embed_options: ClassVar[dict] = {'input_type': 'document'}
    query_options: ClassVar[dict] = {'input_type': 'query'}

    def _initialize(self, caps):
        # Mutating ClassVar - shared across instances!
        self.embed_options |= shared_kwargs  # PROBLEM: ClassVar mutation
```

**Problems:**
- ClassVar mutations affect all instances
- Backup providers interfere with primary
- Difficult to reason about state
- Configuration not cleanly separated from state

### **NEW PATTERN (In Progress)**
```python
class VoyageEmbeddingProvider(EmbeddingProvider[AsyncClient]):
    # No ClassVar kwargs - options live in config

    def _initialize(self, caps):
        # All options are in self.config
        embedding_opts = self.config.embedding  # Dict[str, Any]
        query_opts = self.config.query          # Dict[str, Any]
        # Use these directly in _embed_documents / _embed_query
```

**Benefits:**
- Each instance has its own configuration
- Primary and backup don't interfere
- Configuration is explicit and traceable
- Easier to test and debug

---

## Required Type Additions to dependencies.py

### **✅ Already Added**

```python
# Generic client dependency (parametric)
type ClientDep[T] = Annotated[T, depends(lambda: None)]



# All provider settings dependencies
type EmbeddingProviderSettingsDep = Annotated[...]
type VoyageEmbeddingProviderSettingsDep = Annotated[...]
# ... and 15+ others
```

---

## Next Phase: Provider Alignment

The next task is to:

1. **Review each implemented provider** in `providers/embedding/providers/`
2. **Verify `__init__` signature** matches new pattern
3. **Check `_initialize` implementation** for alignment
4. **Update attribute access** from ClassVar mutations to `config.embedding`/`config.query`
5. **Update dependencies.py** with provider-specific settings types
6. **Create provider-specific `dependencies.py`** (e.g., `providers/embedding/dependencies.py`)

---

## Files & Locations

| File | Purpose | Status |
|------|---------|--------|
| `providers/embedding/providers/base.py` | Base class defining all patterns | ✅ Reference source |
| `providers/dependencies.py` | Root provider DI configuration | ✅ Created (406 lines) |
| `providers/config/embedding.py` | Embedding config classes with options | ⚠️ Partial (some classes) |
| `providers/config/clients.py` | All SDK client option classes | ✅ Complete (171+ imports) |
| `providers/embedding/providers/voyage.py` | Example implementation | ⏳ Needs alignment |
| `providers/embedding/dependencies.py` | To be created | ❌ Not yet created |

---

## Summary

The new DI-driven embedding provider pattern establishes:

1. **DI-injected clients** - Pre-configured and ready to use
2. **Configuration in pydantic models** - Not transformation logic
3. **Options in config.embedding/config.query** - Not ClassVar mutations
4. **Capability resolution via DI** - Optional, injected when available
5. **Provider-specific initialization** - Via `_initialize()` method
6. **Extensibility points** - impl_deps and custom_deps for specialized needs

This replaces the old pattern where providers managed state via shared ClassVars, which caused the backup provider state management nightmare addressed by Problem 1 of the DI refactor.

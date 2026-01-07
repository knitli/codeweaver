<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver `feat/di_monorepo` Branch - Architectural Refactoring Status

**Branch**: `feat/di_monorepo`
**Current Status**: Major Architectural Refactor - Partial Implementation, Intentional Placeholders
**Last Updated**: 2025-01-06
**Stability**: ⚠️ DO NOT EXPECT TO RUN - Placeholders and broken imports are intentional

---

## Executive Summary

The `feat/di_monorepo` branch is executing a **comprehensive architectural refactor** to address fundamental structural mistakes in CodeWeaver. This is not a standard feature branch - it's a "pull off the bandaid" effort to fix problems that have been accumulating:

1. **State Management Nightmare**: Provider classes managing multiple configurations (primary + backup) via ClassVars
2. **Configuration Reconciliation Burden**: Settings classes performing excessive transformation of user input
3. **Registry System Limitations**: Provider/model/service registries inadequate for monorepo structure
4. **Monorepo Preparation**: Repository structure incomplete for planned expansion

**Status**: ~40% complete with intentional partial implementation and placeholder code. This is a work-in-progress refactor where incomplete sections are being built incrementally.

**Important**: Agents working on this branch should understand that:
- Broken imports and missing implementations are **intentional placeholders**
- Type aliases like `ClientDep = INJECTED` without corresponding factories are **temporary scaffolding**
- Things are not expected to run until the refactoring is complete
- The method is deliberate and intentional - this enables getting structural decisions right before moving forward

---

## Refactoring Theme: "Let's Pull Off the Bandaid"

This refactor addresses **seven interconnected architectural problems** that could no longer be deferred:

### Problem 1: Backup Provider State Management ❌→✅ (Partial)
**The Issue**: Provider classes attempted to manage both primary and backup configurations within a single instance. This required:
- ClassVar dedup stores and caches
- Complex internal state toggling
- Shared mutation risk between configurations
- Difficult to reason about state transitions

**The Solution**: Create independent instances
- Primary and backup are now **separate class instances**
- Backup classes are subclasses: `EmbeddingProvider` → `BackupEmbeddingProvider`
- Only difference between primary/backup: `_is_provider_backup` classvar
- All state management becomes local to each instance

**Implementation Status**:
- ✅ Embedding Registry - Complete
- ✅ Embedding Providers (sparse and dense) - Complete
- ❌ Vector Store - Not yet refactored
- ❌ Reranking - Not yet refactored
- ✅ `CodeChunk` handling - Minimal changes (only rare edge case of identical chunks)

**Why This Matters**: Eliminates entire categories of state-related bugs and makes provider behavior predictable and testable.

---

### Problem 2: Provider Settings Configuration Reconciliation ❌→✅ (Partial)
**The Issue**: Settings classes performed heavy transformation logic:
- User-provided config → internal normalization → SDK-compatible kwargs
- Multiple layers of "cleaning" and "reconciling" passed arguments
- Settings classes didn't mirror their underlying SDK clients
- Difficult to trace what config actually gets passed to SDKs

**The Solution**: Mirror SDK client signatures exactly
- Each SDK Client now has its own settings class (e.g., `CohereClientOptions`)
- Settings classes define **exact fields** the SDK client expects
- No transformation logic in settings - pydantic validates, DI injects
- Settings become a pure data container, not a transformation layer

**Example Flow**:
```
User Config: Azure embedding + Cohere model
↓
DI Resolution: Build CohereClientOptions (the Cohere SDK's expected config)
↓
Provider receives: client (properly configured), config options, embedding/query kwargs
↓
Provider usage: client.query(**self.query_options) - no construction logic
```

**Implementation Status**:
- ✅ All Client Options classes - Complete (`providers/config/clients.py`)
  - BedrockClientOptions
  - CohereClientOptions (including Azure, Heroku variants)
  - OpenAI and ~8 variants
  - All others (Mistral, Voyage, etc.)

- ⚠️ Provider-specific Settings Classes - **PARTIALLY DONE**
  - Embedding providers/config.py - Only a few classes implemented
  - Vector Store settings - Not started
  - Reranking settings - Not started

**Why This Matters**: Eliminates 40%+ of provider implementation code. Settings become trivial to test. SDK integration becomes reliable.

---

### Problem 3: Registry System Inadequacy ❌→✅
**The Issue**: Three separate registries (provider, model, service) were inadequate:
- Monorepo structure requires more flexible discovery
- Registries lived in `src/codeweaver/common/registry/` - centralized bottleneck
- Couldn't support decentralized type registration across packages
- Complex registry lookups scattered throughout codebase

**The Solution**: Unified DI-based discovery via `@dependency_provider` decorator
```python
# Old pattern:
registry.register("embedding", "openai", OpenAIEmbedding)
# Registry lived in central location, big lookup table

# New pattern:
@dependency_provider(scope="singleton")
class OpenAIEmbedding:
    def __init__(self, config: OpenAIEmbeddingConfig): ...

# Provider registers itself where it's defined, no central registry needed
```

**Implementation Status**:
- ✅ DI decorator system (`core/di/utils.py`) - Complete
- ✅ Core container and resolution - Complete
- ⚠️ Provider package `dependencies.py` modules - In progress
  - Embedding dependencies - Partially done
  - Vector store dependencies - Not started
  - Reranking dependencies - Not started
  - Engine dependencies - Not started

**Why This Matters**: Enables monorepo structure. Each package self-registers. No central bottleneck. Supports lazy loading.

---

### Problem 4: Monorepo Structure Not Ready ❌→✅ (Partial)
**The Issue**: Repository structure didn't align with monorepo goals:
- All code in single `src/codeweaver/` directory
- No clear package boundaries
- Couldn't separate concerns for independent release cycles

**The Solution**: Pre-package restructuring
```
packages/
├── codeweaver_daemon/           # Standalone daemon service
├── codeweaver_tokenizers/       # Standalone tokenizer package
└── (future: other independent packages)

src/codeweaver/                  # Main integrated packages
├── core/                        # Core DI, logging, exceptions
├── engine/                       # Indexing engine
├── providers/                    # All provider implementations
├── server/                       # MCP server, HTTP endpoints
├── config/                       # Unified configuration loader
└── cli/                          # Command-line interface
```

**Implementation Status**:
- ✅ Structure defined and packages moved
- ✅ Import paths aligned for new structure
- ⚠️ Some legacy registry references may remain

**Why This Matters**: Enables monorepo release strategy. Clear package boundaries. Independent testing per package.

---

### Problem 5: Configuration System Split & Layering ❌→✅
**The Issue**: Single monolithic settings class tried to handle all scenarios. Caused issues when certain packages weren't installed.

**The Solution**: Layered configuration system
```
codeweaver.core.config.core_settings
  └─ CodeWeaverCoreSettings (logging + telemetry only)

codeweaver.engine.config
  └─ CodeWeaverEngineSettings (when engine is top-level)

codeweaver.providers.config
  └─ CodeWeaverProviderSettings (when providers is top-level)

codeweaver.server.config (future)
  └─ CodeWeaverSettings (full integration - only when full server installed)
```

Plus a unified loader:
```python
from codeweaver.config.loader import get_settings

settings = get_settings()  # Auto-detects what's available, loads appropriately
```

**Implementation Status**:
- ✅ Layer structure designed
- ✅ Core settings and loader - Complete
- ✅ Provider settings layer - Complete
- ⚠️ Engine settings layer - In progress
- ⏳ Full server settings layer - Not started

**Why This Matters**: Packages can be used independently. No "missing dependency" errors when partial install. Configuration adapts to available packages.

---

### Problem 6: DI-Driven Defaults & Interdependency Resolution ⏳ (Not Started)
**The Issue**: Complex configuration logic scattered across:
- Config classes performing validation
- Provider classes resolving settings
- Special case handling for quirks (e.g., vector dimensions, qdrant datatype mapping)

**The Solution**: Unified interdependency resolution system
- `codeweaver.core.config.resolver` - Coordination logic
- `codeweaver.core.registry` - Tracks which config values affect others
- DI automatically resolves dependencies between config values

**Example**: Dense embedding provider's vector dimensions must match vector store's vector size
```python
# Instead of: "dense provider manually queries vector store config"
# Now: DI injects vector_dim directly into embedding config
# Resolver ensures they stay synchronized

@dependency_provider
class DenseEmbeddingConfig:
    def __init__(self, vector_dim: VectorDimensionDep = INJECTED): ...
```

**Implementation Status**:
- 📝 Design complete, structure skeleton created
- ⏳ Not yet implemented - marked as intentional to-do
- Will be heavily used once settings are complete

**Why This Matters**: Eliminates manual config reconciliation. Automatic consistency. One place to express "these two settings must match."

---

### Problem 7: Provider Configuration System Complete Refactor ✅ (Partial)
**The Issue**: Provider configuration mixed SDK-specific fields with internal transformation logic. Required extensive "cleaning" of kwargs.

**The Solution**: Settings classes that mirror SDK client signatures exactly
- `providers/config/clients.py` - All SDK client option classes (DONE)
- `providers/config/embedding.py` - Embedding provider settings (IN PROGRESS - partial)
- `providers/config/reranking.py` - Reranking settings (NOT STARTED)
- `providers/config/vector_stores.py` - Vector store settings (NOT STARTED)

**Example**: Cohere embedding provider after refactoring
```python
# Before: Settings class does transformation
class CohereEmbeddingConfig:
    api_key: str
    model: str
    # ... internally transformed to SDK format

# After: Settings class mirrors SDK exactly
class CohereClientOptions:
    api_key: SecretStr  # Exactly as Cohere SDK expects
    model: str
    # ... no transformation, DI provides ready-to-use config

# Provider receives:
class CohereEmbedding:
    def __init__(
        self,
        client: CohereAsyncClient,  # Already instantiated
        embedding: dict[str, Any],  # {"model": "...", "truncate": "..."}
        query: dict[str, Any],      # {"truncate": "..."}
    ):
        # Usage is trivial:
        results = await client.embed(**self.embedding)
```

**Implementation Status**:
- ✅ All client option classes - Complete (171+ imports in `clients.py`)
- ⚠️ Embedding provider configs - Partial (only a few classes in `embedding.py`)
- ❌ Reranking configs - Not started
- ❌ Vector store configs - Not started

**Why This Matters**: Massive code reduction. Provider implementation becomes simple. Tests become reliable.

---

## Current Implementation State

### ✅ Complete (Ready to Build Upon)

**Core DI System** (`src/codeweaver/core/di/`)
- Container with async support, circular detection, scope management
- Dependency markers (`Depends`, `INJECTED`)
- `@dependency_provider` decorator system
- Exception hierarchy for DI errors
- All Phase 1 features

**Configuration Infrastructure**
- `codeweaver.config.loader` - Unified settings loader
- `codeweaver.core.config.core_settings` - Base settings
- `codeweaver.providers.config.clients` - All SDK client option classes (171+ imports)
- Settings validation via pydantic with discriminators

**Provider Architecture (Embedding)**
- Independent primary/backup instances
- `BackupEmbeddingProvider` subclass pattern
- Settings classes for embedding providers (partial)
- Registry refactoring for embedding complete

### ⚠️ In Progress (Intentional Placeholders)

**Provider Settings Classes**
```python
# These exist but are partially implemented:
# providers/config/embedding.py - only a few provider settings defined
# Placeholders like this are intentional:

class SomeProvider:
    client: ClientDep = INJECTED  # Factory will be defined later
    config: ProviderConfigDep = INJECTED  # Pending resolution
```

**Provider Package Dependencies**
- `providers/dependencies.py` - Exists, partially populated
- Type aliases defined, factories pending
- Other packages' `dependencies.py` - Not yet created

### ❌ Not Started (Intentional To-Do)

**Provider Settings Classes**:
- Reranking provider configs
- Vector store provider configs
- Service/agent provider configs

**Provider Package Dependencies**:
- Engine package `dependencies.py`
- Server package `dependencies.py` (future)
- Orchestration dependencies

**Interdependency Resolver**:
- `codeweaver.core.config.resolver` - Skeleton exists, implementation pending
- `codeweaver.core.registry` - Tracking mechanism not implemented

**Provider Refactoring**:
- Vector store backup provider architecture
- Reranking backup provider architecture

---

## Key Architectural Improvements

### 1. State Management: From Shared to Isolated
**Before**: ClassVar stores, shared mutation, complex toggling
```python
class Provider:
    _cache = {}  # Shared between primary and backup! 🚨

    def __init__(self, is_backup=False):
        self.is_backup = is_backup  # Runtime flag causing state issues
```

**After**: Independent instances
```python
class Provider:
    # All state is instance-level, not shared
    def __init__(self, config): self.config = config

class BackupProvider(Provider):  # Completely independent
    _is_provider_backup = True  # ClassVar, not instance state
```

### 2. Configuration: From Transformation Layer to Data Container
**Before**: Heavy lifting in config classes
```python
class Config:
    api_key: str  # User input

    def get_sdk_kwargs(self):
        # Reconcile, transform, clean...
        return {"api_key": SecretStr(self.api_key), ...}
```

**After**: Direct SDK mirror
```python
class CohereClientOptions:
    api_key: SecretStr  # Already what SDK expects
    # DI injects this ready to use
```

### 3. Discovery: From Registry Lookups to Self-Registration
**Before**: Central lookups
```python
registry.register("embedding", "openai", OpenAIEmbedding)
# ... later, complex lookup logic
provider = registry.get("embedding", "openai")
```

**After**: Decorator-based self-registration
```python
@dependency_provider(scope="singleton")
class OpenAIEmbedding:
    pass
# DI discovers automatically, no lookup needed
```

### 4. Package Boundaries: From Monolithic to Modular
**Before**: Single `src/codeweaver/` with unclear boundaries
**After**: Clear separation
- `codeweaver.core` - Foundation (DI, logging, exceptions, types)
- `codeweaver.engine` - Indexing engine with independent tests
- `codeweaver.providers` - All providers with independent tests
- `codeweaver.server` - MCP server, HTTP endpoints
- Standalone packages in `packages/` (daemon, tokenizers)

---

## Issues & Blockers

### 1. ⚠️ Incomplete Settings Classes
**Scope**: Embedding settings only partially done
**Impact**: Reranking and vector store providers cannot be initialized via DI yet
**Resolution**: Complete remaining settings classes (10-15 hours)
**Blocker**: No, can be done incrementally - placeholder clients prevent actual runs anyway

### 2. ⚠️ Missing Provider Dependency Factories
**Scope**: `dependencies.py` modules have type aliases but no factories
**Example**:
```python
type ClientDep = Depends(get_cohere_client)  # Factory not defined yet
```
**Impact**: Intentional placeholders - prevents accidental usage before ready
**Resolution**: Define factories once settings structure finalized (20-30 hours)
**Blocker**: No, intentional staging

### 3. ⚠️ Legacy Registry References May Remain
**Scope**: Some code may still reference old `provider/model/service` registries
**Impact**: Potential import errors or unused code
**Resolution**: Grep for registry references and update to DI pattern (5-10 hours)
**Blocker**: No, can be found and fixed methodically

### 4. ⚠️ Interdependency Resolver Not Implemented
**Scope**: `codeweaver.core.config.resolver` skeleton exists, no logic
**Impact**: Configuration values that depend on each other aren't automatically synchronized
**Example**: Embedding vector dims must match vector store size
**Resolution**: Implement resolver once all settings are defined (15-20 hours)
**Blocker**: No, can be added after settings complete

### 5. ⏳ Monorepo Move Not Yet Executed
**Scope**: Structure prepared but packages not yet moved
**Impact**: Import paths may be wrong, unclear which code belongs where
**Resolution**: Execute package moves to `packages/` directory (2-4 hours)
**Blocker**: No, structure is ready, just needs to be done

---

## For Agents Working on This Branch

### What to Understand

1. **Placeholders Are Intentional**
   ```python
   client: ClientDep = INJECTED  # Missing import? It's on purpose.
   ```
   These are deliberately incomplete pending architecture decisions.

2. **Broken Imports Are Expected**
   - Many imports will fail
   - Settings classes are incomplete
   - Registry references may exist alongside DI code
   - **This is fine** - it's a work-in-progress refactor

3. **Things Won't Run**
   - Don't try to execute tests yet
   - Don't try to start the server
   - Placeholders everywhere are intentional staging
   - Once you get a specific task, you'll have clear context

### When Given Specific Tasks

**You will receive tasks like:**
- "Complete the reranking settings classes following the embedding pattern"
- "Define the factory functions in `providers/dependencies.py`"
- "Update references to the old registry system to use DI"
- "Implement the interdependency resolver for vector dimensions"

**For each task you'll get:**
- Specific scope (which files, which pattern to follow)
- Reference implementation (how embedding was done)
- Expected outcome (what should work when done)
- Architectural constraints (what must align with Constitution)

**When you're given a task, ask if something doesn't make sense.** The refactoring is deliberate - if something seems wrong, it might be, or it might be intentional scaffolding.

### When You See Something Wrong

**Logic errors** (actual bugs): Report immediately
```python
# Example: This is a real bug, report it
if vector_dim > max_size:
    vector_dim = vector_dim + max_size  # Adding when should subtract? Bug!
```

**Missing imports**: Probably intentional, don't fix without asking
```python
from typing import SomeType  # This import doesn't exist yet
client: ClientDep = INJECTED  # Intentional - factory will be defined later
```

**Dead code**: Might be leftover from refactoring, ask before deleting
```python
def old_registry_lookup():  # Still here from old pattern
    # Is this used anywhere? Ask before deleting.
```

---

## Implementation Roadmap

### Phase A: Complete Settings Architecture (In Progress)
- [ ] Reranking provider settings classes
- [ ] Vector store provider settings classes
- [ ] Service/agent provider settings classes
- [ ] Validation for all settings via pydantic discriminators

### Phase B: Complete DI Registration (Next)
- [ ] Factory functions in provider `dependencies.py`
- [ ] Engine package `dependencies.py`
- [ ] Server package `dependencies.py`
- [ ] Type alias resolution and registration

### Phase C: Complete Provider Refactoring (Following)
- [ ] Vector store backup provider architecture
- [ ] Reranking backup provider architecture
- [ ] Remove remaining ClassVar state objects
- [ ] Ensure all providers follow new pattern

### Phase D: Interdependency Resolution (After Settings Complete)
- [ ] Implement config resolver coordination logic
- [ ] Registry tracking for dependent values
- [ ] Automatic synchronization of related configs
- [ ] Special case handling (vector dims, qdrant datatype, etc.)

### Phase E: Integration & Testing (Final)
- [ ] Comprehensive test suite for DI system
- [ ] Integration tests with real providers
- [ ] Configuration validation tests
- [ ] Monorepo package independence tests

---

## Constitutional Alignment

### Principle I: AI-First Context ✅
DI system enables precise context delivery through:
- Decentralized provider registration
- Clean dependency graphs
- Plugin discovery via `@dependency_provider`

### Principle II: Proven Patterns ✅
Uses established approaches from:
- FastAPI dependency injection (familiar to Python developers)
- Pydantic ecosystem (validation, settings)
- Standard async/generator patterns

### Principle III: Evidence-Based Development ✅
All architectural decisions backed by:
- Problems identified in current codebase (state management, config reconciliation)
- Solutions validated against similar projects (FastAPI, pydantic)
- Incremental implementation with testing before moving forward

### Principle IV: Testing Philosophy ⚠️ In Progress
- DI system is complete but untested
- Phase 1.9: Comprehensive test suite required
- Focus on realistic integration scenarios

### Principle V: Simplicity Through Architecture ✅
Refactoring dramatically simplifies:
- Provider implementation (no state management)
- Configuration (no transformation layer)
- Discovery (no registry lookups)
- Package structure (clear boundaries)

---

## Success Criteria

The refactoring will be complete when:

1. ✅ All provider settings classes defined (mirroring SDKs exactly)
2. ✅ All DI factories registered in `dependencies.py` modules
3. ✅ Backup provider architecture applied to all provider types
4. ✅ Legacy registry references removed from codebase
5. ✅ Configuration resolver implements interdependency coordination
6. ✅ Comprehensive test suite validates DI and configuration
7. ✅ Monorepo package moves completed
8. ✅ All imports resolve cleanly (no placeholders remain)
9. ✅ Full server boots and responds to basic requests

---

## Summary for Stakeholders

**Current Status**: Major refactoring 40% complete with intentional partial implementation

**What's Solid**:
- DI container and decorator system battle-tested
- Configuration layer structure defined and mostly working
- Provider architecture pattern established (embedding complete)

**What's In Flight**:
- Settings classes for remaining provider types
- DI factory registration in provider packages
- Interdependency resolver implementation

**What's Coming**:
- Comprehensive testing of complete system
- Monorepo package separation (structure ready)
- Integration validation with real providers

**Timeline**: This is a "pull off the bandaid" refactor - best executed with focused scope and clear priorities rather than trying to coordinate everything at once.

**Risk**: Low - no active users, breaking changes acceptable, structure is deliberate

**Confidence**: High - architectural approach is sound, implementation is incremental and testable

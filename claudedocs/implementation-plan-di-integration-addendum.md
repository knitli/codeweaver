<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# DI Integration Addendum: Embedding Integrity Migration

**Date**: 2026-02-12
**Corrects**: embedding-integrity-migration-implementation-plan.md, implementation-plan-review-synthesis.md
**Issue**: Architectural review incorrectly assumed DI was "upcoming" - DI is 95% implemented

---

## Critical Correction

**WRONG ASSUMPTION** (from reviews):
> "How does this align with upcoming DI refactor?"
> "Keep interfaces simple, avoid deep Registry dependencies"

**REALITY**:
- DI system is **95% implemented** in `codeweaver.core.di`
- All managers/services **already use DI** (CheckpointManager, ManifestManager, etc.)
- Pattern is **FastAPI-inspired**: `@dependency_provider` + type aliases
- New services **MUST follow DI pattern** for consistency

---

## DI Architecture (Actual Implementation)

### Pattern Overview

```python
# 1. Create service class
class MigrationService:
    def __init__(
        self,
        vector_store: VectorStoreProviderDep = INJECTED,
        checkpoint_manager: CheckpointManagerDep = INJECTED,
        manifest_manager: ManifestManagerDep = INJECTED,
    ):
        self.vector_store = vector_store
        self.checkpoint_manager = checkpoint_manager
        self.manifest_manager = manifest_manager

# 2. Register with DI container
@dependency_provider(MigrationService, scope="singleton")
def _create_migration_service(
    vector_store: VectorStoreProviderDep = INJECTED,
    checkpoint_manager: CheckpointManagerDep = INJECTED,
    manifest_manager: ManifestManagerDep = INJECTED,
) -> MigrationService:
    """Factory for migration service."""
    return MigrationService(
        vector_store=vector_store,
        checkpoint_manager=checkpoint_manager,
        manifest_manager=manifest_manager,
    )

# 3. Create type alias for injection
type MigrationServiceDep = Annotated[
    MigrationService, depends(_create_migration_service, scope="singleton")
]
```

### Existing DI Structure

**Core DI (`codeweaver.core.di`):**
- `Container` - DI container implementation
- `@dependency_provider` - Registration decorator
- `INJECTED` - Sentinel for dependency injection
- `depends()` - Dependency marker for type aliases

**Core Dependencies (`codeweaver.core.dependencies`):**
- `SettingsDep` - CodeWeaver settings
- `LoggerDep` - Structured logger
- `TelemetryServiceDep` - Telemetry client
- `ProgressReporterDep` - Progress reporting

**Provider Dependencies (`codeweaver.providers.dependencies`):**
- `EmbeddingProviderSettingsDep` - Embedding config
- `VectorStoreProviderSettingsDep` - Vector store config
- `EmbeddingCapabilityResolverDep` - Capability resolver
- `TokenizerDep` - Token counter

**Engine Dependencies (`codeweaver.engine.dependencies`):**
- `CheckpointManagerDep` - **Already registered!**
- `ManifestManagerDep` - **Already registered!**
- `IndexingServiceDep` - Main indexing service
- `ChunkingServiceDep` - Chunking orchestration

---

## Revised Architecture: DI-First Approach

### Location Decision

**NEW LOCATION**: `codeweaver.providers.vector_stores.dependencies`

**Rationale:**
1. Migration is **vector store-specific** (Qdrant operations)
2. Follows existing pattern: vector store code in `providers.vector_stores`
3. DI dependencies should be co-located with implementations
4. Engine dependencies are for **indexing/chunking**, not vector store operations

**Structure:**
```
codeweaver/providers/vector_stores/
├── __init__.py
├── base.py                  # Existing
├── qdrant_base.py          # Existing
├── inmemory.py             # Existing
├── qdrant.py               # Existing
├── dependencies.py         # NEW - DI registrations
├── migration_service.py    # NEW - Migration orchestration
├── config_analyzer.py      # NEW - Change classification
└── migration_validator.py  # NEW - Data integrity validation
```

---

## Phase 1 Revised: DI Integration

### Week 1: DI-Aware Checkpoint Enhancement

#### 1. Create `codeweaver.providers.vector_stores.dependencies.py`

```python
"""DI setup for vector store services."""

from __future__ import annotations

from typing import Annotated

from codeweaver.core import INJECTED, dependency_provider, depends
from codeweaver.engine.dependencies import CheckpointManagerDep, ManifestManagerDep
from codeweaver.providers.dependencies import VectorStoreProviderSettingsDep


# Import service classes (implemented in other modules)
from codeweaver.providers.vector_stores.config_analyzer import ConfigChangeAnalyzer
from codeweaver.providers.vector_stores.migration_service import MigrationService
from codeweaver.providers.vector_stores.migration_validator import MigrationValidator


# ===========================================================================
# Configuration Analysis
# ===========================================================================


@dependency_provider(ConfigChangeAnalyzer, scope="singleton")
def _create_config_analyzer(
    checkpoint_manager: CheckpointManagerDep = INJECTED,
    manifest_manager: ManifestManagerDep = INJECTED,
) -> ConfigChangeAnalyzer:
    """Factory for configuration change analyzer."""
    return ConfigChangeAnalyzer(
        checkpoint_manager=checkpoint_manager,
        manifest_manager=manifest_manager,
    )


type ConfigChangeAnalyzerDep = Annotated[
    ConfigChangeAnalyzer, depends(_create_config_analyzer, scope="singleton")
]


# ===========================================================================
# Migration Services
# ===========================================================================


@dependency_provider(MigrationService, scope="singleton")
def _create_migration_service(
    vector_store_settings: VectorStoreProviderSettingsDep = INJECTED,
    checkpoint_manager: CheckpointManagerDep = INJECTED,
    manifest_manager: ManifestManagerDep = INJECTED,
    validator: MigrationValidatorDep = INJECTED,
) -> MigrationService:
    """Factory for migration service."""
    return MigrationService(
        vector_store_settings=vector_store_settings,
        checkpoint_manager=checkpoint_manager,
        manifest_manager=manifest_manager,
        validator=validator,
    )


type MigrationServiceDep = Annotated[
    MigrationService, depends(_create_migration_service, scope="singleton")
]


@dependency_provider(MigrationValidator, scope="singleton")
def _create_migration_validator(
    vector_store_settings: VectorStoreProviderSettingsDep = INJECTED,
) -> MigrationValidator:
    """Factory for migration validator."""
    return MigrationValidator(vector_store_settings=vector_store_settings)


type MigrationValidatorDep = Annotated[
    MigrationValidator, depends(_create_migration_validator, scope="singleton")
]


__all__ = (
    "ConfigChangeAnalyzerDep",
    "MigrationServiceDep",
    "MigrationValidatorDep",
)
```

#### 2. Enhance CheckpointManager with Asymmetric Support

**Location**: `codeweaver/engine/managers/checkpoint_manager.py` (existing)

```python
# Add to CheckpointManager class

async def is_config_compatible(
    self,
    checkpoint: IndexingCheckpoint,
    new_config: EmbeddingProviderSettingsType,
) -> tuple[bool, ChangeImpact]:
    """Check if checkpoint is compatible with new config.

    DI-aware: Delegates to ConfigChangeAnalyzer for classification.
    """
    # Import at runtime to avoid circular dependency
    from codeweaver.core.di import get_container
    from codeweaver.providers.vector_stores.dependencies import ConfigChangeAnalyzerDep

    # Resolve analyzer from DI container
    container = get_container()
    analyzer = await container.resolve(ConfigChangeAnalyzerDep)

    # Delegate to analyzer
    analysis = await analyzer.analyze_change(checkpoint, new_config)

    return (
        analysis.impact != ChangeImpact.BREAKING,
        analysis.impact,
    )
```

**Key Points:**
- CheckpointManager **already exists** and is **already registered in DI**
- We ADD a method that delegates to ConfigChangeAnalyzer
- Resolves analyzer from DI container (no hard dependencies)
- Maintains separation of concerns

#### 3. ConfigChangeAnalyzer Implementation

**Location**: `codeweaver/providers/vector_stores/config_analyzer.py` (new)

```python
"""Configuration change analysis for migration decisions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from codeweaver.core import BasedModel, INJECTED
from codeweaver.core.types import ChangeImpact


if TYPE_CHECKING:
    from codeweaver.engine.dependencies import CheckpointManagerDep, ManifestManagerDep
    from codeweaver.engine.managers.checkpoint_manager import IndexingCheckpoint
    from codeweaver.providers.config.categories.embedding import (
        AsymmetricEmbeddingProviderSettings,
        EmbeddingProviderSettingsType,
    )


class ConfigChangeAnalyzer:
    """Analyzes configuration changes for migration decisions.

    DI-managed service that coordinates checkpoint and manifest managers
    to determine impact of configuration changes.
    """

    def __init__(
        self,
        checkpoint_manager: CheckpointManagerDep = INJECTED,
        manifest_manager: ManifestManagerDep = INJECTED,
    ):
        self.checkpoint_manager = checkpoint_manager
        self.manifest_manager = manifest_manager

    async def analyze_change(
        self,
        checkpoint: IndexingCheckpoint,
        new_config: EmbeddingProviderSettingsType,
    ) -> ConfigChangeAnalysis:
        """Analyze configuration change impact."""
        # Implementation here...
        # Access checkpoint_manager and manifest_manager as needed
```

---

## Integration with Existing Code

### Doctor Command Enhancement

**Location**: `codeweaver/cli/commands/doctor.py`

```python
# Add new check function

async def check_embedding_compatibility(
    settings: ProviderSettings
) -> DoctorCheck:
    """Check embedding config compatibility with index."""
    from codeweaver.core.di import get_container
    from codeweaver.providers.vector_stores.dependencies import ConfigChangeAnalyzerDep

    # Resolve from DI container
    container = get_container()
    analyzer = await container.resolve(ConfigChangeAnalyzerDep)

    # Get current checkpoint
    checkpoint = await analyzer.checkpoint_manager.load_checkpoint()
    if not checkpoint:
        return DoctorCheck.set_check(
            "Embedding Compatibility",
            "warn",
            "No checkpoint found - run indexing first",
            ["Run: cw index"]
        )

    # Analyze compatibility
    current_config = settings.embedding[0]
    analysis = await analyzer.analyze_change(checkpoint, current_config)

    if analysis.impact == ChangeImpact.BREAKING:
        return DoctorCheck.set_check(
            "Embedding Compatibility",
            "fail",
            f"Breaking change: {analysis.message}",
            analysis.recommendations
        )

    return DoctorCheck.set_check(
        "Embedding Compatibility",
        "success",
        "Configuration is compatible",
        []
    )
```

**Key Points:**
- Uses `get_container()` to resolve dependencies
- No hard imports of service classes
- Clean separation from doctor command logic

### Config Command Enhancement

**Location**: `codeweaver/cli/commands/config.py` (or similar)

```python
@app.command()
async def set_config(key: str, value: str):
    """Set configuration with proactive validation."""
    from codeweaver.core.di import get_container
    from codeweaver.providers.vector_stores.dependencies import ConfigChangeAnalyzerDep

    # Check if this is an embedding config change
    if key.startswith("provider.embedding"):
        # Resolve analyzer
        container = get_container()
        analyzer = await container.resolve(ConfigChangeAnalyzerDep)

        # Analyze impact
        current_checkpoint = await analyzer.checkpoint_manager.load_checkpoint()
        new_config = simulate_config_change(key, value)

        analysis = await analyzer.analyze_change(current_checkpoint, new_config)

        # Show impact
        console.print(f"⚠️  Configuration Change Detected")
        console.print(f"  Impact: {analysis.impact.value}")
        console.print(f"  {analysis.message}")

        if analysis.impact == ChangeImpact.BREAKING:
            if not Confirm.ask("Continue?"):
                return

    # Apply change
    settings.set(key, value)
```

---

## Benefits of DI-First Approach

### 1. **Consistency with Existing Code**

All engine and provider services already use DI:
- CheckpointManager (line 112 in engine/dependencies.py)
- ManifestManager (line 126)
- IndexingService (line 192)
- ChunkingService (line 182)

New migration services follow **exact same pattern**.

### 2. **Testability**

```python
# Easy to test with mock dependencies
async def test_migration_service():
    from codeweaver.core.di import Container

    # Create container with mocks
    container = Container()
    container.register(VectorStoreProviderSettingsDep, mock_settings)
    container.register(CheckpointManagerDep, mock_checkpoint)

    # Resolve service (gets mocks automatically)
    service = await container.resolve(MigrationServiceDep)

    # Test
    result = await service.migrate(...)
    assert result.success
```

### 3. **Loose Coupling**

Services don't import each other directly:
- ConfigAnalyzer doesn't import MigrationService
- Doctor command doesn't import any service classes
- CLI resolves dependencies at runtime
- Easy to swap implementations

### 4. **Singleton Management**

DI container handles singleton lifecycle:
- CheckpointManager created once per session
- MigrationService reused across commands
- No manual singleton patterns needed

### 5. **Constitutional Compliance**

✅ **Principle II: Proven Patterns** - FastAPI-inspired DI is proven
✅ **Principle III: Evidence-Based** - DI is 95% implemented and working
✅ **Principle V: Simplicity** - Follows existing codebase patterns exactly

---

## Revised Implementation Checklist

### Phase 1: Foundation (Week 1)

- [ ] Create `codeweaver/providers/vector_stores/dependencies.py`
- [ ] Implement `ConfigChangeAnalyzer` with DI injection
- [ ] Register `ConfigChangeAnalyzerDep` in DI container
- [ ] Add `is_config_compatible()` to CheckpointManager
- [ ] Extend doctor command using `get_container().resolve()`
- [ ] Add config command proactive validation

**DI-Specific Tests:**
```python
def test_config_analyzer_resolves_from_di():
    """Verify ConfigChangeAnalyzer can be resolved."""
    container = get_container()
    analyzer = await container.resolve(ConfigChangeAnalyzerDep)
    assert analyzer is not None
    assert isinstance(analyzer, ConfigChangeAnalyzer)

def test_analyzer_receives_dependencies():
    """Verify DI injects checkpoint and manifest managers."""
    container = get_container()
    analyzer = await container.resolve(ConfigChangeAnalyzerDep)
    assert analyzer.checkpoint_manager is not None
    assert analyzer.manifest_manager is not None
```

### Phase 2: Migration Services (Week 3-5)

- [ ] Implement `MigrationService` with DI injection
- [ ] Register `MigrationServiceDep` in DI container
- [ ] Implement `MigrationValidator` with DI injection
- [ ] Register `MigrationValidatorDep` in DI container
- [ ] Wire up CLI commands using `container.resolve()`

**DI-Specific Tests:**
```python
def test_migration_service_resolves_with_all_deps():
    """Verify MigrationService gets all dependencies."""
    container = get_container()
    service = await container.resolve(MigrationServiceDep)
    assert service.vector_store_settings is not None
    assert service.checkpoint_manager is not None
    assert service.validator is not None
```

---

## Removed from Original Plan

### ❌ REMOVED: "Avoid Deep Registry Dependencies"

**Original Recommendation** (WRONG):
> "Keep interfaces simple, avoid deep Registry dependencies"

**Reality**:
- Registry system is being **deprecated** (correct)
- DI system is the **replacement** (already 95% complete)
- New code should **embrace DI**, not avoid it

### ❌ REMOVED: Manual Service Instantiation

**Original Approach** (WRONG):
```python
# DON'T DO THIS
checkpoint_manager = CheckpointManager(...)
analyzer = ConfigChangeAnalyzer(checkpoint_manager, ...)
```

**Correct Approach**:
```python
# DO THIS
from codeweaver.core.di import get_container

container = get_container()
analyzer = await container.resolve(ConfigChangeAnalyzerDep)
# analyzer already has checkpoint_manager injected
```

---

## Summary of Changes

| Aspect | Original Plan | Revised (DI-First) |
|--------|---------------|-------------------|
| Location | `codeweaver.engine.services` | `codeweaver.providers.vector_stores` |
| Registration | Manual instantiation | `@dependency_provider` |
| Injection | Constructor parameters | `= INJECTED` markers |
| Resolution | Direct imports | `container.resolve()` |
| Testing | Mock constructors | Mock DI registrations |
| Pattern | Ad-hoc | Follows existing code exactly |

---

## Constitutional Compliance (Updated)

✅ **Principle I: AI-First Context** - Unchanged, still valid
✅ **Principle II: Proven Patterns** - **NOW CORRECT**: Using proven DI pattern from existing code
✅ **Principle III: Evidence-Based** - **NOW CORRECT**: DI is 95% implemented (evidence!)
✅ **Principle IV: Testing Philosophy** - Improved: DI makes testing easier
✅ **Principle V: Simplicity** - **NOW CORRECT**: Follows existing architecture exactly

**Violations Removed:**
- ~~"Avoid deep Registry dependencies"~~ - DI is not Registry, embrace it!
- ~~Manual service instantiation~~ - Use DI container
- ~~Location in engine.services~~ - Should be in vector_stores package

---

## Recommended Next Steps

1. **Review this addendum** with architectural review agent
2. **Update implementation plan** to reflect DI-first approach
3. **Start with dependencies.py** in Phase 1 Week 1
4. **Follow existing DI patterns** from engine/dependencies.py exactly

---

## Appendix: DI Pattern Reference

### Full Pattern Example

```python
# 1. Service implementation
class MyService:
    def __init__(
        self,
        dependency_a: DependencyADep = INJECTED,
        dependency_b: DependencyBDep = INJECTED,
    ):
        self.dep_a = dependency_a
        self.dep_b = dependency_b

# 2. Factory registration
@dependency_provider(MyService, scope="singleton")
def _create_my_service(
    dependency_a: DependencyADep = INJECTED,
    dependency_b: DependencyBDep = INJECTED,
) -> MyService:
    return MyService(
        dependency_a=dependency_a,
        dependency_b=dependency_b,
    )

# 3. Type alias for injection
type MyServiceDep = Annotated[
    MyService, depends(_create_my_service, scope="singleton")
]

# 4. Usage in other services
class ConsumerService:
    def __init__(self, my_service: MyServiceDep = INJECTED):
        self.service = my_service

# 5. Manual resolution (CLI commands)
async def my_command():
    container = get_container()
    service = await container.resolve(MyServiceDep)
    result = await service.do_something()
```

### Scope Options

- `"singleton"` - One instance per application (most services)
- `"request"` - One instance per request (HTTP handlers)
- `"function"` - New instance per resolution (stats, trackers)

**Migration Services**: Use `"singleton"` scope (matches CheckpointManager, ManifestManager)

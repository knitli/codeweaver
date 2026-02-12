<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Architecture Corrections Summary

**Date**: 2026-02-12
**Version**: Plan v2.1 (Architecture-Corrected)

## Critical Corrections Made

### 1. Service Location: Engine, Not Providers ✅

**Original (Wrong)**:
```
providers/vector_stores/
├── config_analyzer.py
├── migration_service.py
└── dependencies.py
```

**Corrected**:
```
engine/
├── services/
│   ├── config_analyzer.py      # NEW
│   └── migration_service.py    # NEW
└── dependencies.py              # UPDATE with factories
```

**Rationale**: Migration is **pipeline machinery**, not a pluggable provider. It belongs with indexing/chunking in engine, keeping providers architecture-agnostic.

---

### 2. DI Pattern: Factory Wrappers, Not Service Signatures ✅

**Original (Wrong)**:
```python
class ConfigChangeAnalyzer:
    def __init__(
        self,
        settings: SettingsDep = INJECTED,           # ❌ Wrong
        checkpoint_manager: CheckpointManagerDep = INJECTED,  # ❌ Wrong
    ):
        ...
```

**Corrected**:
```python
# Service: Plain class, NO DI
class ConfigChangeAnalyzer:
    def __init__(
        self,
        settings: Settings,                    # ✅ Plain parameter
        checkpoint_manager: CheckpointManager,  # ✅ Plain parameter
    ):
        self.settings = settings
        self.checkpoint_manager = checkpoint_manager

# Factory: Handles DI integration
@dependency_provider(ConfigChangeAnalyzer, scope="singleton")
def _create_config_analyzer(
    settings: SettingsDep = INJECTED,              # ✅ DI in factory
    checkpoint_manager: CheckpointManagerDep = INJECTED,  # ✅ DI in factory
) -> ConfigChangeAnalyzer:
    return ConfigChangeAnalyzer(
        settings=settings,
        checkpoint_manager=checkpoint_manager,
    )
```

**Rationale**: Services can be instantiated directly without DI (testability). DI is an optional wrapper layer, not a requirement.

---

### 3. Package Boundaries Maintained ✅

**Key Principle**: Avoid creating new dependencies between `engine` and `providers` implementations.

**Correct Pattern**:
```python
# In engine/services/migration_service.py
from codeweaver.providers.vector_stores.base import VectorStoreProvider  # ✅ Abstract

class MigrationService:
    def __init__(
        self,
        vector_store: VectorStoreProvider,  # ✅ Uses abstract base
        ...
    ):
        self.vector_store = vector_store
```

**NOT**:
```python
# ❌ WRONG - Don't import specific implementations
from codeweaver.providers.vector_stores.qdrant import QdrantVectorStore
```

**Rationale**: Maintains separation for future package installability:
- `providers` depends only on `core`
- `engine` depends on `core`, `providers` (abstractions only)
- Clean dependency flow enables separate packaging

---

### 4. Testing Pattern: Direct Instantiation ✅

**Unit Tests** (No DI needed):
```python
@pytest.fixture
def config_analyzer():
    """Direct instantiation with mocks."""
    return ConfigChangeAnalyzer(
        settings=Mock(),
        checkpoint_manager=Mock(),
        manifest_manager=Mock(),
    )

async def test_analyze_config(config_analyzer):
    """Test service directly."""
    result = await config_analyzer.analyze_config_change(...)
    assert result.impact == ChangeImpact.COMPATIBLE
```

**Integration Tests** (Use DI):
```python
async def test_full_flow():
    """Test with DI container."""
    container = get_container()
    analyzer = await container.resolve(ConfigChangeAnalyzerDep)
    result = await analyzer.analyze_current_config()
    assert result is not None
```

---

## Updated Architecture

### Package Structure

```
core/                    (No external codeweaver deps)
├── di/                 (DI container implementation)
└── dependencies/       (Core service factories)

providers/              (Depends: core only)
├── embedding/          (Provider implementations - plain classes)
├── vector_stores/      (Provider implementations - plain classes)
└── dependencies/       (Factory wrappers for providers)

engine/                 (Depends: core, providers abstractions)
├── services/           (Service implementations - plain classes)
│   ├── config_analyzer.py      ← NEW
│   └── migration_service.py    ← NEW
├── managers/           (Manager implementations - plain classes)
│   ├── checkpoint_manager.py
│   └── manifest_manager.py
└── dependencies.py     (Factory functions with DI)

server/                 (Depends: all above)
cli/                    (Depends: all above)
```

### DI Integration Levels

| Component | DI in Constructor | Factory with DI | Direct Instantiation |
|-----------|-------------------|-----------------|----------------------|
| **Providers** | ❌ No | ✅ Yes (factory wrapper) | ✅ Yes (easy) |
| **Engine Services** | ❌ No | ✅ Yes (factory wrapper) | ✅ Yes (easy) |
| **CLI Commands** | ✅ Yes (`= INJECTED`) | N/A | ❌ No (via container) |

---

## Documents Updated

1. **`embedding-integrity-migration-implementation-plan.md`** → v2.1 (Architecture-Corrected)
   - All service locations changed to `engine/services/`
   - All DI patterns updated to factory wrapper model
   - Testing patterns updated to show direct instantiation
   - Package boundaries clarified throughout

2. **`di-architecture-corrected.md`** (NEW)
   - Comprehensive DI analysis from agent
   - Correct factory wrapper patterns documented
   - Package dependency structure explained
   - Testing patterns with and without DI

3. **`di-architecture-diagram.md`** (SUPERSEDED)
   - Original diagram had wrong locations/patterns
   - Replaced by corrected architecture document

---

## Implementation Checklist (Corrected)

### Phase 1: Configuration Analysis

- [ ] Create `engine/services/config_analyzer.py` (plain class)
  - Plain `__init__` with no DI markers
  - All methods use `self.settings`, `self.checkpoint_manager`, etc.

- [ ] Update `engine/dependencies.py` with factory
  - Add `@dependency_provider` decorator
  - Factory function has `= INJECTED` parameters
  - Define `ConfigChangeAnalyzerDep` type alias

- [ ] Export from `engine/__init__.py`
  - Add `ConfigChangeAnalyzerDep` to exports

- [ ] Update `cli/commands/doctor.py`
  - Add parameter: `config_analyzer: ConfigChangeAnalyzerDep = INJECTED`
  - Use service methods directly

- [ ] Update `cli/commands/config.py`
  - Add parameter: `config_analyzer: ConfigChangeAnalyzerDep = INJECTED`
  - Use for proactive validation

- [ ] Write unit tests
  - Direct instantiation with mocks (no DI container)
  - Test service methods independently

- [ ] Write integration tests
  - Use DI container to resolve real services
  - Test full CLI workflows

### Phase 2: Migration Service

- [ ] Create `engine/services/migration_service.py` (plain class)
- [ ] Update `engine/dependencies.py` with factory
- [ ] Export `MigrationServiceDep` from `engine/__init__.py`
- [ ] Create `cli/commands/migrate.py` with `= INJECTED`
- [ ] Write unit tests (direct instantiation)
- [ ] Write integration tests (DI container)

---

## Key Takeaways

1. **Services are plain**: No DI in constructors, easy to test
2. **Factories handle DI**: Wrapper layer with `@dependency_provider`
3. **CLI uses DI**: Commands receive services via `= INJECTED`
4. **Package boundaries**: Engine uses provider abstractions, not implementations
5. **Testability**: Direct instantiation for unit tests, DI for integration tests
6. **Future-proof**: Architecture supports package separation for monorepo split

---

## Questions Resolved

✅ **Q**: Should services be in `providers` or `engine`?
**A**: Engine. Migration is pipeline machinery, not a pluggable provider.

✅ **Q**: Should services have DI in their signatures?
**A**: No. Services are plain classes, factories handle DI integration.

✅ **Q**: Can services be instantiated without DI?
**A**: Yes. That's the whole point - testability and flexibility.

✅ **Q**: How do package boundaries work?
**A**: Unidirectional flow: providers → core, engine → core/providers (abstractions), server → all.

✅ **Q**: Where do CheckpointManager and ManifestManager live?
**A**: `engine/managers/`, already registered in `engine/dependencies.py`.

---

## Next Steps

1. ✅ Architecture corrections complete
2. ✅ DI patterns documented
3. ✅ Implementation plan updated
4. ➡️ Ready to begin Phase 1 implementation with correct architecture

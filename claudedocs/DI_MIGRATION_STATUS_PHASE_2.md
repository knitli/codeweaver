<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Original Issue and Spec

## Phase 2: DI Integration - Breaking Circular Dependencies

**Parent Epic**: #116  
**Depends On**: #117 (DI Foundation)
**Target**: Week 2 (7-10 days)
**Risk Level**: Medium

Migrate core services to DI, **eliminating 120-130 circular dependencies** and validating clean package boundaries.

## Goals

- Migrate Indexer and search services to DI
- **Eliminate 75% of circular dependencies** (120-130 violations)
- Old pattern still works (coexistence during migration)
- Update tests to use DI overrides
- Validate package boundaries
- No performance regression
- Documentation updated

## Why This Phase Matters

**This is where the magic happens!** By migrating services to DI:
- ✅ **Eliminates** providers → engine dependency (20 violations)
- ✅ **Eliminates** telemetry → engine/config dependencies (10 violations)
- ✅ **Eliminates** config → CLI dependencies (multiple violations)
- ✅ **Breaks** registry coupling that creates circular imports
- ✅ **Enables** clean package separation in Phase 3

**Impact:** From 164 violations → ~30-40 violations (75% reduction)

## How DI Breaks Circular Dependencies

### Before: Manual Registry Access Creates Coupling
```python
class Indexer:
    def __init__(self):
        # Creates providers → engine → config → providers cycle
        registry = get_provider_registry()
        self.embedding = registry.get_embedding_provider_instance(...)
        # Direct config import creates coupling
        self.settings = get_settings()
```

**Problems:**
- Imports from registry, config, providers
- Creates circular dependencies
- Hard to test (manual mocking)
- Scattered instantiation logic

### After: DI Injection Breaks Cycles
```python
class Indexer:
    def __init__(self, embedding: EmbeddingDep, settings: SettingsDep):
        self.embedding = embedding  # Injected!
        self.settings = settings    # Injected!
```

**Benefits:**
- ✅ No imports from registry, config, or providers
- ✅ No circular dependencies
- ✅ Easy to test (container.override)
- ✅ Clean package boundaries

## Implementation Checklist

### Service Migration (Days 1-4)

**Priority 1: Indexer** (Eliminates most violations)
- [ ] Update Indexer constructor with DI
  - [ ] `embedding: EmbeddingDep`
  - [ ] `vector_store: VectorStoreDep`
  - [ ] `settings: SettingsDep`
- [ ] Remove manual provider fetching
- [ ] Update all instantiation points
- [ ] Update tests to use container overrides
- [ ] **Validate: 20+ violations eliminated**

**Priority 2: Search Services**
- [ ] Migrate `SemanticSearchService`
  - [ ] DI for embedding provider
  - [ ] DI for vector store
- [ ] Migrate `HybridSearchService`
  - [ ] DI for reranking provider
- [ ] Migrate query processing services
- [ ] **Validate: 30+ violations eliminated**

**Priority 3: Chunking Service**
- [ ] Migrate chunking service to DI
- [ ] Inject tokenizer dependencies
- [ ] Update configuration injection

**Priority 4: Server Initialization**
- [ ] Use container lifecycle
- [ ] Register providers at startup
- [ ] Health checks via DI
- [ ] Graceful shutdown with DI

### Example: Indexer Migration

**Before:**
```python
class Indexer:
    def __init__(self):
        from codeweaver.common.registry import get_provider_registry
        from codeweaver.config.settings import get_settings
        
        registry = get_provider_registry()
        self.embedding = registry.get_embedding_provider_instance(...)
        self.vector_store = registry.get_vector_store_instance(...)
        self.settings = get_settings()
        # Circular dependencies created!
```

**After:**
```python
from codeweaver.di.providers import EmbeddingDep, VectorStoreDep, SettingsDep

class Indexer:
    def __init__(
        self,
        embedding: EmbeddingDep,
        vector_store: VectorStoreDep,
        settings: SettingsDep,
    ):
        self.embedding = embedding
        self.vector_store = vector_store
        self.settings = settings
        # No imports from registry/config!
        # No circular dependencies!
```

### Testing Updates (Days 5-6)

**Migrate to DI overrides:**
- [ ] Update existing tests to use DI
- [ ] Replace manual mocking with container.override
- [ ] Ensure all tests still pass
- [ ] Add integration tests with DI
- [ ] **Measure: Test setup should be 50-80% less verbose**

**Example test transformation:**
```python
# Before: Manual mocking
def test_indexer():
    indexer = Indexer()
    indexer.embedding = MockEmbedding()  # Fragile!
    indexer.vector_store = MockVectorStore()

# After: Clean DI overrides
def test_indexer(container):
    container.override(EmbeddingProvider, MockEmbedding())
    container.override(VectorStore, MockVectorStore())
    indexer = container.resolve(Indexer)  # Clean!
```

### Package Boundary Validation (Days 7-8)

**Validate clean dependencies:**
- [ ] Run dependency analysis
- [ ] Verify providers → engine eliminated
- [ ] Verify telemetry → engine eliminated
- [ ] Verify config → CLI eliminated
- [ ] **Target: < 50 violations (down from 164)**

**Natural boundaries should emerge:**
- Services declare dependencies via types
- No manual imports of registry/config
- Clean dependency flow: core → utils → providers → engine → app

### Performance Testing (Day 9)

**Benchmark DI overhead:**
- [ ] Measure DI resolution time
- [ ] Compare to baseline (manual instantiation)
- [ ] Optimize hot paths if needed
- [ ] Profile memory usage
- [ ] **Target: Within 5% of baseline**

**Performance mitigation:**
- Singleton caching (already in DI)
- Lazy resolution where appropriate
- Pre-warm frequently used dependencies

### Documentation (Day 10)

- [ ] Update service documentation
- [ ] Migration examples (before/after)
- [ ] Testing guide updates
- [ ] Troubleshooting guide
- [ ] **Document violations eliminated**

## Validation Checklist

**Dependency Analysis:**
- [ ] Run: `python scripts/validate_proposed_structure.py`
- [ ] Verify: providers → engine = 0 imports
- [ ] Verify: telemetry → engine = 0 imports
- [ ] Verify: config → CLI = 0 imports
- [ ] **Total violations < 50** (75% reduction achieved)

**Functional Testing:**
- [ ] All existing tests pass
- [ ] No breaking changes
- [ ] Performance within 5% of baseline
- [ ] Old pattern still works (coexistence verified)

## Acceptance Criteria

- [ ] Core services migrated to DI
- [ ] **120-130 violations eliminated** (75% reduction)
- [ ] All tests passing with DI overrides
- [ ] Performance validated (within 5%)
- [ ] Package boundaries validated
- [ ] Documentation complete
- [ ] Code review approved
- [ ] Old pattern coexistence confirmed

## Coexistence Strategy

**During migration:**
- DI services can coexist with old pattern
- Gradual migration, service by service
- No big-bang switchover
- Rollback possible at any point

**Example coexistence:**
```python
# Old pattern still works
indexer_old = Indexer()

# New pattern also works
container = get_container()
indexer_new = container.resolve(Indexer)
```

## Violations Eliminated

### Before: 164 Total Violations

**Category 1: Registry/Config Access (101)**
- codeweaver → core (68)
- codeweaver → utils (23)
- codeweaver → telemetry (10)

**Category 2: Provider Coupling (24)**
- providers → engine (20) ← **ELIMINATED**
- providers → agent_api (4) ← Partially fixed by SearchResult move

**Category 3: Telemetry Coupling (10)**
- telemetry → config (3) ← **ELIMINATED**
- telemetry → engine (3) ← **ELIMINATED**
- telemetry → utils (3) ← **ELIMINATED**
- telemetry → semantic (1)

**Category 4: Engine Coupling (5)**
- engine → CLI (5) ← **ELIMINATED**

### After DI: ~30-40 Violations Remaining

**Still need manual fixes:**
- core → utils (9) - Move utilities to core
- semantic → utils (4) - Move utilities
- providers → agent_api (4) - Fixed by SearchResult move in Phase 1
- Minor type movements (10-15)

## Success Metrics

**Technical:**
- 75% reduction in violations (164 → ~40)
- 0 test failures
- Performance within 5%
- Clean package boundaries

**Quality:**
- 50-80% less verbose test setup
- Services declare clean dependencies
- No circular imports between major modules
- FastAPI-familiar patterns

## Next Phase Preview

**Phase 3 (Monorepo Structure) becomes trivial because:**
- ✅ Circular dependencies broken
- ✅ Services don't import across packages
- ✅ Clean dependency flow established
- ✅ Just need to organize into packages/

## Connection to Monorepo Strategy

This phase implements **Week 2** of the integrated strategy:
- DI Integration → **Breaks 75% of circular dependencies**
- Package boundaries validated → **Ready for Phase 3 organization**
- Testing updated → **Proof that architecture is sound**

## Reference

- Planning: `INTEGRATED_DI_MONOREPO_STRATEGY.md` (Week 2)
- Architecture: `plans/dependency-injection-architecture-plan.md`
- Visualization: `DI_IMPACT_VISUALIZATION.md`

## Risk Mitigation

**Medium Risk: Breaking existing code**
- **Mitigation:** Coexistence strategy, gradual migration
- **Rollback:** Old pattern still works throughout

**Medium Risk: Performance impact**
- **Mitigation:** Early benchmarking, singleton caching
- **Target:** Within 5% of baseline

**Low Risk: Learning curve**
- **Mitigation:** Clear docs, FastAPI familiarity, examples

[end spec]
---
[status report]
# Dependency Injection Migration Status - Phase 2 (Indexer Core)

## Status Summary Overview
We are currently in the middle of migrating the core indexing engine to the new Dependency Injection (DI) system. The primary goal is to remove hardcoded registry lookups and singleton dependencies, replacing them with constructor-injected providers managed by the central container.

### Completed Accomplishments
1.  **Indexer Refactor**: `src/codeweaver/engine/indexer/indexer.py` has been fully refactored to accept its dependencies (`VectorStoreProvider`, `EmbeddingProvider`, `SparseEmbeddingProvider`, `ChunkingService`, etc.) via its constructor.
2.  **Unit Test Migration**:
    - `tests/unit/test_indexer_reconciliation.py`: Successfully migrated to DI and passing. Verified that missing sparse embeddings are correctly added to existing dense chunks.
    - `tests/unit/test_indexer_remove_path.py`: Successfully migrated to DI and passing. Verified that file removal logic correctly cleans up both the manifest and the internal store.
    - `tests/unit/test_indexer_stale_point_removal.py`: Partially migrated. Core logic for single-file indexing is verified and passing under DI.

## Uncovered Issues & Root Causes

### 1. Batch Indexing Path Mismatch (`_index_files_batch`)
The `TestStalePointRemovalInBatchIndexing` is currently failing because `delete_by_file` is not being triggered during batch operations.
-   **Discovery**: The `Indexer` relativizes paths against `self._project_path`. In test environments, `tmp_path` is often used as the root. If the path passed to `_index_files_batch` is already relative, or if `self._project_path` is not perfectly aligned with the manifest's expected keys, the `has_file` lookup fails.
-   **Technical Nuance**: Even when paths look identical in strings, type mismatches (e.g., `Path` vs `str`) or `PurePath` vs `PosixPath` representations in the manifest's internal dictionary keys can cause misses.
-   **Current State**: I have added robust `relative_to` logic with fallbacks to `set_relative_path` in `indexer.py`, but the tests are still recording 0 calls to `delete_by_file`.

### 2. Manifest Key Inconsistency
-   **Uncovered**: The `IndexFileManifest` stores paths as strings internally (using `str(path)`), but the `has_file` and `get_file` methods often accept `Path` objects. While they attempt to cast, discrepancies between how `set_relative_path` and `Path.relative_to` represent the leading `./` or root can cause lookup failures in the indexing pipeline.

## Remaining Work for Phase 2

### Immediate Fixes (Indexer Engine)
-   **Resolve Batch Deletion**: Fix the path matching logic in `_index_files_batch` so that it correctly identifies files already present in the manifest, ensuring stale chunks are purged before new ones are added.
-   **Migrate Stale Point Removal Tests**: Finish the remaining failures in `tests/unit/test_indexer_stale_point_removal.py`.
-   **Migrate Indexer Config Tests**: `tests/unit/test_indexer_config.py` still needs to be updated to use the DI container instead of manual instantiation.

### Broader Phase 2 Tasks (Pending)
-   **Chunker Migration**: The Chunker families and delimiters are still largely managed via the old registry system. These need to be transitioned to DI providers.
-   **Watcher Migration**: `src/codeweaver/engine/watcher/watcher.py` needs to be refactored to receive its `Indexer` and `IgnoreFilter` via injection.
-   **Agent API Tooling**: The `find_code` tool implementation (`src/codeweaver/agent_api/find_code/pipeline.py`) needs to be migrated to resolve its search engine and providers via the DI container.
-   **Integration Verification**: Once all core components are migrated, a full suite run of `mise run test --profile integration` is required to ensure that the wired-up daemon behaves correctly in a real environment.

## Blockers
-   None currently, but the path relativization logic is proven to be more fragile than expected and may require a unified "Path Normalizer" service to ensure consistency across the Indexer, Manifest, and Vector Store.

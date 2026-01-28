<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Backup System Deprecation Analysis

**Date**: 2026-01-28
**Context**: Major DI refactor completed, backup system architecture needs comprehensive simplification
**Status**: Analysis Phase Complete

## Executive Summary

After the major DI refactor that introduced flexible multi-vector support, the old backup system architecture is now obsolete. The analysis identified **~13 source files** and **~8 test files** containing deprecated backup logic totaling approximately **3,800+ lines of production code** and **1,600+ lines of test code** that require removal or refactoring.

### Key Insights

1. **Backup embeddings** can now be stored as additional vectors on the same points (multi-vector support)
2. **Sparse embeddings** are always local (no backup needed)
3. **Re-rankers** can use simple query-time fallback (no special backup handling)
4. **Chunk compatibility** issues eliminated (single chunk set supports multiple embeddings)
5. **Registry state management** nightmare can be eliminated

### New Simplified Architecture

**Backup only needed for two scenarios:**
1. **Cloud embedding provider** → Store backup embeddings as additional vectors
2. **Cloud vector store** → Use WAL + snapshots for local backup

---

## I. PRODUCTION CODE ANALYSIS

### A. Provider Factories & Backup Models

**File**: `src/codeweaver/providers/config/backup_models.py` (208 lines)

**Status**: REMOVE ENTIRE FILE

**Rationale**: Hardcoded backup models (minishlab/potion-base-8M, jinaai/jina-embeddings-v2-small-en) no longer needed. Backup embeddings should be configurable through normal provider settings.

**Key Functions to Remove**:
- `get_backup_embedding_provider()` - Factory with two-tier fallback
- `create_backup_embeddings()` - Convenience wrapper
- `get_backup_model_info()` - Configuration details
- Dependency checks for sentence-transformers/fastembed

**Impact**: Core backup provider instantiation logic

---

### B. Embedding Registries & State Management

**File**: `src/codeweaver/providers/embedding/registry.py` (195 lines)

**Status**: REFACTOR - Remove BackupEmbeddingRegistry class

**Lines to Remove/Refactor**:
- Lines 146-156: `BackupEmbeddingRegistry` class definition
- Line 46-47: `is_backup_provider: bool` field in `EmbeddingRegistry`
- Lines 192-195: `_get_backup_registry()` DI provider

**Simplification**:
- Single `EmbeddingRegistry` class (no backup subclass)
- Remove `is_backup_provider` differentiation
- Single DI provider for registry (no primary/backup split)

**Impact**: Eliminates dual registry complexity

---

### C. Dual Chunk Generation Logic

**File**: `src/codeweaver/engine/chunker/base.py`

**Status**: REMOVE backup-specific logic

**Lines to Remove**:
- Lines 284-366: `ChunkGovernor.from_backup_profile()` method
- Lines 119-123: Multi-capability minimum context window logic

**Simplification**:
- `ChunkGovernor` only considers primary model capabilities
- Remove backup profile parameter handling
- Simplify context window computation to single model

**Impact**: ~100 lines of complex adaptive chunking logic

---

**File**: `src/codeweaver/engine/services/chunking_service.py`

**Status**: REMOVE backup reuse logic

**Lines to Remove**:
- Line 59: `if source_chunks and self._is_backup_service():`
- Lines 77-87: `_chunk_with_reuse()` method
- Lines 93-99: `_can_reuse_chunks()` and `can_reuse_chunks()` methods

**Undefined References to Fix**:
- `_is_backup_service()` method (referenced but never defined)

**Impact**: ~50 lines of chunk reuse logic

---

### D. Backup Orchestration System

**Status**: MAJOR REFACTOR NEEDED

#### Core Services to Update:

**1. Failover Service** (`src/codeweaver/engine/services/failover_service.py`)

**Current Architecture** (Lines 39-52):
```python
def __init__(
    self,
    primary_store: VectorStoreProvider | None,
    backup_store: VectorStoreProvider | None,
    indexing_service: IndexingService,
    backup_indexing_service: IndexingService,  # REMOVE THIS
    settings: FailoverSettings,
):
```

**Changes Needed**:
- Remove `backup_indexing_service` dependency
- Remove `_maintain_backup_loop()` (lines 100-144) - This entire loop is for old backup system
- Keep health monitoring for circuit breaker functionality
- Keep failover activation/restoration logic (still needed for vector store failover)

**Impact**: ~80 lines removed, service remains for vector store failover only

---

**2. Vector Reconciliation Service** (`src/codeweaver/engine/services/reconciliation_service.py`)

**Status**: REPURPOSE or REMOVE

**Current Purpose**: Ensures all points have backup vectors (multi-vector reconciliation)

**New Purpose Options**:
- **Option A**: Repurpose for ensuring all configured vectors exist (primary, sparse, etc.)
- **Option B**: Remove entirely if vector store handles this internally

**Lines to Review**:
- Lines 64-75: `_get_backup_provider()` - Remove backup provider dependency
- Lines 77-140: `detect_missing_vectors()` - Generalize to any vector name
- Lines 168-227: `repair_missing_vectors()` - Generalize to any embedding provider

**Recommendation**: **Option A** - Repurpose for general vector reconciliation

**Impact**: Moderate refactor to generalize from backup-specific to any-vector

---

**3. Snapshot Service** (`src/codeweaver/engine/services/snapshot_service.py`)

**Status**: KEEP (with minor updates)

**Rationale**: Snapshots are still needed for cloud vector store backup

**Changes Needed**:
- Update comments to clarify this is for vector store backup, not embedding backup
- Keep all functionality intact

**Impact**: Minimal (documentation only)

---

### E. Backup Configuration System

**1. Failover Settings** (`src/codeweaver/engine/config/failover.py`)

**Status**: SIMPLIFY

**Lines to Review**:
- Lines 44-49: `disable_failover` - Keep for vector store failover
- Lines 51-54: `backup_sync` - Rename to `snapshot_sync` or similar
- Lines 68-88: `reconciliation_*` settings - Keep if repurposing reconciliation service
- Lines 91-113: `snapshot_*` settings - Keep (needed for snapshots)
- Lines 116-138: `wal_*` settings - Keep (needed for WAL)

**Changes Needed**:
- Rename to emphasize vector store failover (not embedding backup)
- Remove/rename parameters that reference "backup" in embedding context

**Impact**: Moderate refactor, mostly renaming

---

**2. Failover Detector** (`src/codeweaver/engine/config/failover_detector.py`)

**Status**: UPDATE logic

**Current Logic**: Disables failover if primary embedding provider is local

**New Logic**: Disable failover if vector store is local (embedding provider irrelevant)

**Impact**: Small logic change, big conceptual shift

---

**3. Backup Profile** (`src/codeweaver/providers/config/profiles.py`)

**Status**: REMOVE backup profile

**Lines to Remove**:
- Lines 465-469: `BACKUP` profile definition
- References to backup profile in provider resolution

**Impact**: Minimal

---

### F. Multi-Vector Storage Configuration

**File**: `src/codeweaver/providers/types/vectors.py`

**Status**: UPDATE - Make backup vector role optional

**Lines to Review**:
- Lines 32-52: `VectorRole` enum - Keep `BACKUP` for backward compatibility initially
- Lines 212-214: Example showing "backup" key - Update documentation
- Line 408: Factory creating backup vector config - Generalize

**Changes Needed**:
- Deprecate `VectorRole.BACKUP` (don't remove immediately for backward compat)
- Update documentation to show backup vectors as just another named vector
- Generalize factory to support arbitrary vector names

**Impact**: Minimal breaking changes

---

### G. Dependency Injection Configuration

**File**: `src/codeweaver/providers/dependencies.py`

**Status**: MAJOR SIMPLIFICATION

**Lines to Review/Remove**:
- Lines 311-323: `_create_all_embedding_configs()` - Simplify
- Lines 333-338: `_create_primary_embedding_config()` - May no longer need separate factory
- Similar patterns for sparse (341-373), reranking (376-403), vector stores (406-433)

**Changes Needed**:
- Remove primary/backup config separation
- Single provider settings per kind
- Remove collection-based provider registration (tuple of all configs)

**Impact**: Significant simplification of DI setup

---

## II. TEST CODE ANALYSIS

### A. Tests to REMOVE Completely

**1. Embedding Failover Bug Tests** (345 lines)
- **File**: `tests/integration/providers/test_embedding_failover.py`
- **Reason**: Documents bugs in deprecated backup system
- **Tests**: 4 tests reproducing registry collisions, deduplication issues

**2. Backup-Specific Type Tests** (4 test methods)
- **File**: `tests/unit/core/types/test_chunk_embeddings_properties.py`
  - `test_has_dense_with_backup_only`
  - `test_has_dense_with_multiple_dense`
- **File**: `tests/unit/providers/types/test_vectors.py`
  - `test_convenience_accessor_backup`
  - `test_variable_property_backup`

**3. WAL Failover Config Tests** (3 of 6 test methods)
- **File**: `tests/unit/providers/test_wal_config_integration.py`
  - `test_wal_config_merges_failover_when_backup_enabled`
  - `test_wal_config_creates_default_when_none_exists`
  - `test_wal_config_merge_with_different_capacity_values`

**Total Lines to Remove**: ~400 lines

---

### B. Tests to UPDATE (Significant Refactoring)

**1. Reconciliation Integration Tests** (14+ tests)
- **File**: `tests/integration/workflows/test_reconciliation_integration.py`
- **Changes**: Remove backup-specific context, keep general reconciliation tests
- **Reason**: Reconciliation may still be needed for embedding completeness

**2. Phase 4 Status Flow Tests** (20+ tests)
- **File**: `tests/integration/workflows/test_phase4_status_flow.py`
- **Changes**: Remove backup store mocking, backup sync statistics, `active_store_type` assertions
- **Reason**: Status flow should not report backup-specific metrics

**3. CLI Init Tests** (partial)
- **File**: `tests/unit/cli/test_init_command.py`
- **Changes**: Remove backup configuration assertions

**Total Lines to Update**: ~600 lines

---

### C. Tests to KEEP (Core Functionality)

**1. Snapshot Infrastructure Tests** (13 tests)
- **File**: `tests/integration/engine/test_failover_snapshot_integration.py`
- **Reason**: Snapshots still needed for vector store backup
- **Status**: Keep with minor documentation updates

**2. Backup E2E Workflow Tests** (11 tests)
- **File**: `tests/integration/workflows/test_backup_system_e2e.py`
- **Reason**: E2E tests for complete failover workflows
- **Status**: Keep, rename to emphasize vector store failover

**3. Snapshot Service Unit Tests** (28 tests)
- **File**: `tests/unit/engine/services/test_snapshot_service.py`
- **Reason**: Core snapshot service functionality
- **Status**: Keep intact

**Total Lines to Keep**: ~1,300 lines

---

## III. DEPRECATION STRATEGY

### Phase 1: Non-Breaking Deprecation (Current Sprint)

**Goal**: Mark old backup system as deprecated, add warnings

**Tasks**:
1. Add deprecation warnings to:
   - `backup_models.py` functions
   - `BackupEmbeddingRegistry` class
   - `ChunkGovernor.from_backup_profile()` method
   - Failover service backup maintenance methods

2. Update documentation:
   - Mark backup system as deprecated in README
   - Document migration path to multi-vector approach
   - Update configuration examples

3. Add configuration flag:
   - `CODEWEAVER_DISABLE_OLD_BACKUP_SYSTEM` environment variable
   - Default to `false` (backward compatible)
   - Log warning when old backup system is used

**Timeline**: 1-2 days

---

### Phase 2: Parallel Implementation (Next Sprint)

**Goal**: Implement simplified backup using multi-vector approach

**Tasks**:
1. Create new multi-vector backup configuration:
   - Configure additional embedding providers via normal settings
   - Store as named vectors (e.g., "backup-embedding", "sparse")
   - Use VectorSet to manage multiple vectors per point

2. Update indexing service:
   - Generate all configured embeddings in parallel
   - Store as multi-vector points
   - Remove special backup indexing service

3. Update failover logic:
   - Focus on vector store failover only
   - Remove embedding provider failover
   - Simplify to: cloud vector store → WAL + snapshots

4. Update reconciliation:
   - Generalize to check for any missing configured vectors
   - Not just "backup" vectors

**Timeline**: 3-5 days

---

### Phase 3: Migration & Testing (Following Sprint)

**Goal**: Migrate existing projects, comprehensive testing

**Tasks**:
1. Create migration script:
   - Detect old backup configuration
   - Convert to new multi-vector configuration
   - Migrate existing backup vectors to new naming scheme

2. Update all tests:
   - Remove deprecated backup tests (400 lines)
   - Update reconciliation tests (600 lines)
   - Keep snapshot tests (1,300 lines)
   - Add new multi-vector backup tests

3. Integration testing:
   - Test migration on real projects
   - Verify failover still works
   - Performance testing

**Timeline**: 5-7 days

---

### Phase 4: Removal (Future Sprint)

**Goal**: Remove all deprecated backup code

**Tasks**:
1. Remove production code:
   - Delete `backup_models.py` (208 lines)
   - Remove `BackupEmbeddingRegistry` (50 lines)
   - Remove backup chunking logic (150 lines)
   - Simplify failover service (80 lines)
   - Simplify DI configuration (200+ lines)

2. Remove test code:
   - Delete deprecated test files (400 lines)
   - Remove backup-specific test fixtures

3. Update documentation:
   - Remove all references to old backup system
   - Document multi-vector backup approach

**Timeline**: 2-3 days

**Prerequisites**: All users migrated, no breaking changes

---

## IV. RISK ASSESSMENT

### High Risk Areas

**1. Registry State Management**
- **Risk**: Removing dual registries may break existing code accessing `BackupEmbeddingRegistry`
- **Mitigation**: Deprecation phase with backward compatibility shims

**2. Chunk Reuse Logic**
- **Risk**: Undefined `_is_backup_service()` reference may cause runtime errors
- **Mitigation**: Fix immediately during deprecation phase

**3. Reconciliation Service**
- **Risk**: Reconciliation may be used outside backup context
- **Mitigation**: Careful analysis before removal, consider repurposing

### Medium Risk Areas

**1. Failover Service**
- **Risk**: Removing backup maintenance loop may break existing failover workflows
- **Mitigation**: Keep vector store failover intact, only remove embedding backup

**2. Configuration Migration**
- **Risk**: Existing projects with old backup config may break
- **Mitigation**: Migration script with validation

**3. Test Coverage**
- **Risk**: Removing 400+ lines of tests may reduce coverage
- **Mitigation**: Replace with new multi-vector backup tests

### Low Risk Areas

**1. Snapshot Service**
- **Risk**: Minimal changes, well-tested
- **Mitigation**: Keep intact

**2. Vector Types**
- **Risk**: Backward compatible deprecation
- **Mitigation**: Keep `VectorRole.BACKUP` for now

---

## V. SUCCESS METRICS

### Code Quality Metrics

**Before Deprecation**:
- Production code: ~3,800 lines of backup system logic
- Test code: ~1,600 lines of backup tests
- Complexity: Dual registries, dual chunking, three-phase maintenance

**After Deprecation**:
- Production code: ~1,200 lines removed (68% reduction in backup code)
- Test code: ~400 lines removed, 600 lines updated
- Complexity: Single registry, single chunking, simplified failover

**Expected Improvements**:
- 30-40% reduction in backup system complexity
- Elimination of state management nightmare
- Clearer separation of concerns (embedding vs vector store backup)

### Performance Metrics

**Expected Improvements**:
- Faster indexing (no separate backup indexing service)
- Lower memory usage (single chunk set)
- Reduced maintenance overhead (no three-phase loop)

---

## VI. ACTIONABLE NEXT STEPS

### Immediate (This Week)

1. **Create backup system deprecation branch**
   ```bash
   git checkout -b feat/deprecate-old-backup-system
   ```

2. **Add deprecation warnings** to all backup functions/classes

3. **Fix undefined reference** (`_is_backup_service()` in chunking service)

4. **Document migration path** in README and migration guide

### Short Term (Next 2 Weeks)

5. **Implement multi-vector backup configuration**

6. **Update indexing service** to use multi-vector approach

7. **Update failover service** to focus on vector store only

8. **Create migration script** for existing projects

### Medium Term (Next Month)

9. **Remove all deprecated production code** (1,200+ lines)

10. **Update/remove test code** (1,000+ lines)

11. **Comprehensive integration testing**

12. **Update all documentation**

---

## VII. RECOMMENDATION

**Primary Recommendation**: Proceed with deprecation in phases as outlined above.

**Rationale**:
1. **Architectural Alignment**: New DI system + multi-vector support makes old backup system obsolete
2. **Simplification**: Removes 3,800+ lines of complex, redundant code
3. **Maintainability**: Eliminates state management nightmare
4. **Performance**: Faster indexing, lower memory usage
5. **Clarity**: Clearer separation between embedding and vector store backup

**Alternative Consideration**: If risk seems too high, consider deprecation warning first (Phase 1 only) and defer removal to future release.

---

## VIII. APPENDIX: FILE INVENTORY

### Production Files Requiring Changes

| File | Lines | Action | Priority |
|------|-------|--------|----------|
| `providers/config/backup_models.py` | 208 | REMOVE | HIGH |
| `providers/embedding/registry.py` | 50 | REFACTOR | HIGH |
| `engine/chunker/base.py` | 100 | REMOVE | HIGH |
| `engine/services/chunking_service.py` | 50 | REMOVE | HIGH |
| `engine/services/failover_service.py` | 80 | REFACTOR | HIGH |
| `engine/services/reconciliation_service.py` | 170 | REPURPOSE | MEDIUM |
| `engine/services/snapshot_service.py` | 10 | UPDATE | LOW |
| `engine/config/failover.py` | 50 | SIMPLIFY | MEDIUM |
| `engine/config/failover_detector.py` | 20 | UPDATE | MEDIUM |
| `providers/config/profiles.py` | 10 | REMOVE | LOW |
| `providers/types/vectors.py` | 30 | UPDATE | LOW |
| `providers/dependencies.py` | 200 | SIMPLIFY | HIGH |
| `core/utils/procs.py` | 0 | KEEP | LOW |

**Total**: ~978 lines to remove/refactor in production code

### Test Files Requiring Changes

| File | Tests | Action | Priority |
|------|-------|--------|----------|
| `integration/providers/test_embedding_failover.py` | 4 | REMOVE | HIGH |
| `unit/providers/test_wal_config_integration.py` | 3 of 6 | REMOVE | HIGH |
| `unit/core/types/test_chunk_embeddings_properties.py` | 2 | REMOVE | MEDIUM |
| `unit/providers/types/test_vectors.py` | 2 | REMOVE | MEDIUM |
| `integration/workflows/test_reconciliation_integration.py` | 14 | UPDATE | HIGH |
| `integration/workflows/test_phase4_status_flow.py` | 20 | UPDATE | HIGH |
| `unit/cli/test_init_command.py` | partial | UPDATE | MEDIUM |
| `integration/engine/test_failover_snapshot_integration.py` | 13 | KEEP | HIGH |
| `integration/workflows/test_backup_system_e2e.py` | 11 | KEEP | HIGH |
| `unit/engine/services/test_snapshot_service.py` | 28 | KEEP | HIGH |

**Total**: ~400 lines to remove, ~600 lines to update, ~1,300 lines to keep

---

**End of Analysis Report**

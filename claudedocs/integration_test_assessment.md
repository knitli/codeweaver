<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Integration Test Failure Analysis
**Date**: 2025-11-04
**Analyzer**: Quality Engineer Agent
**Test Suite**: tests/integration/
**Branch**: 003-our-aim-to

## Executive Summary

**Total Tests**: 98 integration tests collected
**Passed**: 5 (5%)
**Failed**: At least 12 identified failures
**Timeout/Hang**: 1 critical infinite recursion bug
**Not Run**: ~81 tests (not executed due to early termination)

### Critical Findings

1. **CRITICAL**: Infinite recursion in settings initialization (`CodeWeaverSettings` → `get_storage_path()` → `get_settings()` loop)
2. **HIGH**: Pydantic model definition issues (forward references not resolved)
3. **HIGH**: Provider registry API signature mismatch (unpacking error)
4. **MEDIUM**: Multiple test infrastructure issues requiring external services

### Quality Impact

Integration testing is currently **BLOCKED** by 3 critical architectural issues that must be fixed before meaningful integration testing can proceed:

1. Settings initialization recursion (affects ~80+ tests)
2. Pydantic model rebuild requirements (affects chunking tests)
3. Provider registry API contract violations (affects provider instantiation tests)

---

## Summary

### Test Execution Results

```
Total Collected: 98 tests
Passed: 5 tests (5%)
Failed: 12+ tests (12%+)
Timeout: 1 test (infinite recursion)
Not Executed: ~81 tests (stopped due to timeout)
```

### Failure Breakdown by Category

| Category | Count | Severity | Subsystem |
|----------|-------|----------|-----------|
| Circular Dependency | 1 | CRITICAL | Configuration |
| Pydantic Model Definition | 5 | HIGH | Chunking |
| API Signature Mismatch | 6 | HIGH | Provider Registry |
| Test Infrastructure | Unknown | MEDIUM | All |

---

## Failure Categories

### 1. Circular Dependency / Infinite Recursion (CRITICAL)

**Impact**: BLOCKS ~80+ integration tests from running
**Root Cause**: Settings initialization calls itself recursively
**Affected Subsystem**: Configuration initialization

#### Test Cases Affected

```
test_custom_configuration (TIMEOUT - infinite recursion)
+ ~80 other tests that depend on settings initialization
```

#### Error Evidence

```python
# Infinite loop cycle:
get_settings()
 → CodeWeaverSettings.__init__()
  → model_post_init()
   → model_dump()
    → IndexingSettings.cache_dir (property)
     → get_storage_path()
      → _get_project_name()
       → get_settings()  # RECURSION!
        → CodeWeaverSettings.__init__()
         → ... (repeats infinitely)
```

**Stack Trace Pattern**:
```
File "src/codeweaver/config/settings.py", line 670, in get_settings
    _settings = CodeWeaverSettings()
File "src/codeweaver/config/settings.py", line 399, in model_post_init
    self._map = cast(DictView[CodeWeaverSettingsDict], DictView(self.model_dump()))
File "src/codeweaver/config/indexing.py", line 323, in cache_dir
    path = self._index_cache_dir or get_storage_path()
File "src/codeweaver/config/indexing.py", line 95, in _get_project_name
    settings = _get_settings()
File "src/codeweaver/config/indexing.py", line 88, in _get_settings
    return get_settings()
[INFINITE RECURSION - repeats until timeout]
```

#### Root Cause Analysis

**Problem**: Settings initialization requires computing `cache_dir` property, which requires settings to be initialized.

**File**: `src/codeweaver/config/indexing.py`
**Functions**: `IndexingSettings.cache_dir`, `get_storage_path()`, `_get_project_name()`

**Circular dependency chain**:
1. `CodeWeaverSettings()` initializer calls `model_post_init()`
2. `model_post_init()` calls `model_dump()` to create internal `_map`
3. `model_dump()` serializes all fields, including `indexing.cache_dir` property
4. `cache_dir` property calls `get_storage_path()` if `_index_cache_dir` not set
5. `get_storage_path()` calls `_get_project_name()`
6. `_get_project_name()` calls `get_settings()` to get project path
7. `get_settings()` creates new `CodeWeaverSettings()` → **RECURSION**

#### Fix Strategy

**Solution**: Break the circular dependency by:
1. **Option A**: Make `cache_dir` lazy (only compute when accessed, not during serialization)
2. **Option B**: Use `@computed_field` with `mode='simple'` to exclude from `model_dump()`
3. **Option C**: Pass required values as constructor parameters instead of calling `get_settings()`
4. **Option D**: Use `model_validator(mode='before')` to set defaults before initialization

**Recommended Fix (Option B)**:
```python
# src/codeweaver/config/indexing.py
from pydantic import computed_field

class IndexingSettings(BaseModel):
    _index_cache_dir: Path | None = PrivateAttr(default=None)

    @computed_field(return_type=Path)
    @property
    def cache_dir(self) -> Path:
        """Compute cache_dir without triggering settings init during serialization."""
        if self._index_cache_dir is not None:
            return self._index_cache_dir
        # Use fallback logic WITHOUT calling get_settings()
        # Option: Accept project_path as parameter or use environment variable
        return Path(".codeweaver/cache")  # Safe default
```

#### Dependencies

**Blocks**: ALL tests that instantiate `CodeWeaverSettings` or depend on configuration
**Complexity**: MODERATE (architectural issue, requires careful refactoring)
**Estimated Fix Time**: 2-4 hours

---

### 2. Pydantic Model Definition Issues (HIGH)

**Impact**: Blocks 5 parallel chunking integration tests
**Root Cause**: Forward references not resolved before model usage
**Affected Subsystem**: Chunking (parallel processing tests)

#### Test Cases Affected

```
tests/integration/chunker/test_e2e.py::test_e2e_multiple_files_parallel_process (FAILED)
tests/integration/chunker/test_e2e.py::test_e2e_multiple_files_parallel_thread (FAILED)
tests/integration/chunker/test_e2e.py::test_e2e_parallel_error_handling (FAILED)
tests/integration/chunker/test_e2e.py::test_e2e_parallel_empty_file_list (FAILED)
tests/integration/chunker/test_e2e.py::test_e2e_parallel_dict_convenience (FAILED)
```

#### Error Evidence

```
pydantic.errors.PydanticUserError: `ChunkerSettings` is not fully defined;
you should define `LanguageFamily`, then call `ChunkerSettings.model_rebuild()`.

For further information visit https://errors.pydantic.dev/2.12/u/class-not-fully-defined

File: tests/integration/chunker/test_e2e.py:150
Code: settings = ChunkerSettings(...)
```

#### Root Cause Analysis

**Problem**: `ChunkerSettings` model references `LanguageFamily` as a forward reference, but `model_rebuild()` was not called before instantiation.

**File**: Likely `src/codeweaver/engine/chunking_service.py` or related chunking config files

**Pydantic Requirement**: When models use forward references (e.g., `language_family: "LanguageFamily"`), you must:
1. Define all referenced models first
2. Call `Model.model_rebuild()` after all definitions are complete

#### Fix Strategy

**Solution**: Add `model_rebuild()` call after all model definitions:

```python
# After all model definitions in chunking module
from codeweaver.language import LanguageFamily  # Ensure LanguageFamily is imported
from codeweaver.engine.chunking.settings import ChunkerSettings

# Rebuild model after LanguageFamily is fully defined
ChunkerSettings.model_rebuild()
```

**Alternative Solution**: Use string literal forward references consistently:
```python
# Instead of:
language_family: LanguageFamily

# Use:
language_family: "LanguageFamily"  # String literal forward reference
```

**Then add at module level**:
```python
# At end of module after all definitions
from __future__ import annotations
# OR
ChunkerSettings.model_rebuild()
```

#### Dependencies

**Blocks**: Parallel chunking functionality tests
**Complexity**: SIMPLE (add single `model_rebuild()` call)
**Estimated Fix Time**: 30 minutes

---

### 3. Provider Registry API Signature Mismatch (HIGH)

**Impact**: Blocks 6 provider instantiation tests
**Root Cause**: `_provider_map` structure changed but unpacking logic not updated
**Affected Subsystem**: Provider Registry (embedding, vector store creation)

#### Test Cases Affected

```
test_create_provider_with_client_from_map (FAILED)
test_create_provider_skips_client_if_provided (FAILED)
test_create_provider_handles_client_creation_failure (FAILED)
test_qdrant_provider_with_memory_mode (FAILED)
test_qdrant_provider_with_url_mode (FAILED)
test_string_provider_kind_in_create_provider (FAILED)
```

#### Error Evidence

```
ValueError: too many values to unpack (expected 2)

File: src/codeweaver/common/registry/provider.py:814
Code: registry, kind_name = self._provider_map[provider_kind]

Context:
def get_provider_class(self, provider, provider_kind):
    registry, kind_name = self._provider_map[provider_kind]  # LINE 814
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
```

#### Root Cause Analysis

**Problem**: Code expects `_provider_map[provider_kind]` to return 2-tuple `(registry, kind_name)`, but actual structure returns something different (likely 3-tuple or dict).

**File**: `src/codeweaver/common/registry/provider.py`
**Line**: 814 in `get_provider_class()`

**Evidence from contract tests**: Contract tests show `_provider_map` may have been refactored to include additional metadata (possibly client factory info).

#### Fix Strategy

**Investigation Required**: Check current `_provider_map` structure:

```python
# Check what _provider_map actually contains:
print(f"Provider map type: {type(self._provider_map[provider_kind])}")
print(f"Provider map value: {self._provider_map[provider_kind]}")
```

**Likely Fix Options**:

**Option A**: Structure changed to 3-tuple:
```python
# If _provider_map now returns (registry, kind_name, client_factory):
registry, kind_name, _ = self._provider_map[provider_kind]
# Or explicitly:
registry, kind_name, client_factory = self._provider_map[provider_kind]
```

**Option B**: Structure changed to dict:
```python
# If _provider_map now returns a dict:
provider_info = self._provider_map[provider_kind]
registry = provider_info["registry"]
kind_name = provider_info["kind_name"]
```

**Option C**: Update all unpacking calls to match new structure:
```python
# Find all instances of tuple unpacking from _provider_map
# Update to match actual structure
```

#### Dependencies

**Blocks**: Provider instantiation and client factory integration
**Complexity**: MODERATE (requires API contract analysis)
**Estimated Fix Time**: 1-2 hours (investigation + fix)

---

### 4. Test Infrastructure Issues (MEDIUM-LOW)

**Impact**: Tests not yet executed due to early termination
**Note**: Cannot fully assess until critical blockers are fixed

#### Potentially Affected Tests (Not Yet Run)

```
tests/integration/test_error_recovery.py (10 tests)
tests/integration/test_health_monitoring.py (13 tests)
tests/integration/test_hybrid_ranking.py (unknown)
tests/integration/test_hybrid_storage.py (unknown)
tests/integration/test_incremental_updates.py (unknown)
tests/integration/test_memory_persistence.py (unknown)
tests/integration/test_partial_embeddings.py (unknown)
tests/integration/test_persistence.py (unknown)
tests/integration/test_provider_switch.py (unknown)
tests/integration/test_reference_queries.py (25 tests expected)
tests/integration/test_search_workflows.py (11 tests)
tests/integration/test_server_indexing.py (5 tests)
```

#### Anticipated Issues (Based on Constitution Requirements)

1. **External Service Dependencies**:
   - Qdrant vector store not running
   - VoyageAI API keys not configured
   - PostHog telemetry service unavailable

2. **Test Fixture Setup**:
   - Test project fixtures may not exist
   - Temporary directories not created
   - Mock services not properly initialized

3. **Async Test Infrastructure**:
   - Event loop cleanup issues
   - Async fixtures not properly awaited
   - Timeout issues in async operations

#### Fix Strategy

**Phase 1**: Fix critical blockers first (recursion, pydantic, registry)
**Phase 2**: Run remaining tests to identify specific infrastructure issues
**Phase 3**: Implement fixes based on actual failures observed

---

## Prioritization Matrix

### By Severity and Impact

| Issue | Severity | Impact | Tests Blocked | Fix Complexity | Priority |
|-------|----------|--------|---------------|----------------|----------|
| Settings Recursion | CRITICAL | 80+ tests | ~82% of suite | MODERATE | 1 |
| Pydantic Model Definition | HIGH | 5 tests | Chunking subsystem | SIMPLE | 2 |
| Provider Registry API | HIGH | 6 tests | Provider creation | MODERATE | 3 |
| Test Infrastructure | MEDIUM | Unknown | Unknown until run | VARIES | 4 |

### By Subsystem

| Subsystem | Critical | High | Medium | Low | Total | % of Suite |
|-----------|----------|------|--------|-----|-------|------------|
| Configuration | 1 | 0 | 0 | 0 | 1 | ~82% |
| Chunking | 0 | 5 | 0 | 0 | 5 | ~5% |
| Provider Registry | 0 | 6 | 0 | 0 | 6 | ~6% |
| Test Infrastructure | 0 | 0 | TBD | TBD | TBD | ~7% |

---

## Common Root Causes

### 1. Circular Dependencies (Architectural)

**Pattern**: Settings → Property Evaluation → Settings (recursion)

**Affected Areas**:
- Configuration initialization
- Storage path resolution
- Project path detection

**Solution Strategy**: Break circular dependencies through:
- Lazy evaluation (computed fields)
- Dependency injection (pass values instead of calling getters)
- Caching (memoization to prevent re-initialization)

### 2. Pydantic Model Lifecycle Issues

**Pattern**: Forward references not resolved before model usage

**Affected Areas**:
- Chunking configuration
- Potentially other models with forward references

**Solution Strategy**:
- Add `model_rebuild()` calls after all definitions
- Use `from __future__ import annotations` consistently
- Review all forward references in codebase

### 3. API Contract Violations

**Pattern**: Internal APIs changed without updating all call sites

**Affected Areas**:
- Provider registry unpacking logic
- Client factory integration

**Solution Strategy**:
- Review API contract changes in recent commits
- Update all call sites to match new signatures
- Add integration tests for API contracts

---

## Fixing Strategy

### Phase 1: Critical Sequential Fixes (MUST complete before testing can proceed)

**Priority Order**: Fix in sequence (each unblocks next batch of tests)

#### Fix 1: Settings Recursion (CRITICAL)

**Estimated Time**: 2-4 hours
**Complexity**: MODERATE
**Unblocks**: 80+ tests

**Actions**:
1. Analyze `IndexingSettings.cache_dir` property and `get_storage_path()` logic
2. Implement one of:
   - Use `@computed_field` with lazy evaluation
   - Pass `project_path` as constructor parameter
   - Use environment variable or safe default
3. Test settings initialization in isolation
4. Verify no recursion with `pytest tests/integration/test_custom_config.py -v`

**Files to Modify**:
- `src/codeweaver/config/indexing.py` (lines 88-95, 125, 323)
- `src/codeweaver/config/settings.py` (lines 399, 670)

**Success Criteria**:
- ✅ `CodeWeaverSettings()` initializes without hanging
- ✅ `test_custom_configuration` passes without timeout
- ✅ Settings can be accessed in test context

---

#### Fix 2: Pydantic Model Rebuild (HIGH)

**Estimated Time**: 30 minutes
**Complexity**: SIMPLE
**Unblocks**: 5 chunking tests

**Actions**:
1. Locate `ChunkerSettings` definition
2. Find where `LanguageFamily` is imported/defined
3. Add `ChunkerSettings.model_rebuild()` after imports
4. Run chunking tests to verify

**Files to Modify**:
- `src/codeweaver/engine/chunking/settings.py` (or similar)
- Add at module level after all definitions

**Success Criteria**:
- ✅ `ChunkerSettings(...)` instantiates without error
- ✅ All 5 parallel chunking tests pass

---

#### Fix 3: Provider Registry Unpacking (HIGH)

**Estimated Time**: 1-2 hours
**Complexity**: MODERATE
**Unblocks**: 6 provider instantiation tests

**Actions**:
1. Inspect `_provider_map` structure in `ProviderRegistry`
2. Review recent commits for API changes
3. Update unpacking logic in `get_provider_class()` (line 814)
4. Search codebase for other unpacking patterns: `grep -r "self._provider_map\[" src/`
5. Update all call sites to match new structure

**Files to Modify**:
- `src/codeweaver/common/registry/provider.py` (line 814, potentially more)

**Success Criteria**:
- ✅ `registry.create_provider()` works without unpacking error
- ✅ All 6 client factory integration tests pass

---

### Phase 2: Parallel Fixes (Can be done simultaneously after Phase 1)

Once critical blockers are fixed, these can be addressed in parallel:

#### Group A: Test Infrastructure
- External service mocking (Qdrant, VoyageAI)
- Async test fixtures
- Temporary directory setup

#### Group B: Remaining Integration Tests
- Health monitoring tests
- Error recovery tests
- Search workflow tests
- Server indexing tests

---

## Next Actions

### Immediate (Before Any Testing Can Proceed)

1. **Fix Settings Recursion** (CRITICAL - Priority 1)
   - Assign to: Architecture/Config specialist
   - Branch: `fix/settings-recursion`
   - Est. Time: 2-4 hours
   - Verification: `pytest tests/integration/test_custom_config.py::test_custom_configuration -v`

2. **Fix Pydantic Model Rebuild** (HIGH - Priority 2)
   - Assign to: Chunking subsystem specialist
   - Branch: `fix/chunker-settings-rebuild`
   - Est. Time: 30 minutes
   - Verification: `pytest tests/integration/chunker/test_e2e.py -k parallel -v`

3. **Fix Provider Registry API** (HIGH - Priority 3)
   - Assign to: Provider registry specialist
   - Branch: `fix/registry-unpacking`
   - Est. Time: 1-2 hours
   - Verification: `pytest tests/integration/test_client_factory_integration.py -v`

### Sequential (After Critical Fixes)

4. **Run Complete Test Suite** (After Phase 1 complete)
   - Command: `uv run pytest tests/integration/ -v --tb=short --timeout=60`
   - Capture all remaining failures
   - Categorize by subsystem and severity
   - Create follow-up fix tasks

5. **Test Infrastructure Assessment** (After #4 complete)
   - Identify missing external services
   - Document test fixture requirements
   - Create setup documentation for CI/CD

---

## Success Metrics

### Phase 1 Completion Criteria

✅ **Settings Recursion Fixed**:
- `test_custom_configuration` passes without timeout
- Settings initialization completes in <100ms
- No infinite recursion in stack traces

✅ **Pydantic Models Fixed**:
- All 5 parallel chunking tests pass
- `ChunkerSettings` instantiates without rebuild error

✅ **Provider Registry Fixed**:
- All 6 client factory tests pass
- Provider instantiation works without unpacking errors

### Phase 2 Completion Criteria

Target after Phase 1 fixes:
- **Passed**: ≥70% of integration tests (69/98 tests)
- **Failed**: ≤20% requiring infrastructure/setup (20/98 tests)
- **Blocked**: 0 tests due to architectural issues

### Integration Test Quality Gates (Constitutional Requirements)

From `.specify/memory/constitution.md`:
- ✅ Tests validate user-affecting behavior
- ✅ Integration tests preferred over unit tests
- ✅ Tests validate quickstart scenarios (6 scenarios in `specs/003-our-aim-to/quickstart.md`)
- ✅ Tests check realistic input/output, not implementation details

---

## Appendices

### A. Test File Inventory

```
Total Integration Test Files: 18
- chunker/test_e2e.py (7 tests, 5 failing)
- test_build_flow.py (3 tests, ALL PASSING)
- test_client_factory_integration.py (7 tests, 6 failing)
- test_custom_config.py (1 test, TIMEOUT)
- test_error_recovery.py (10 tests, NOT RUN)
- test_health_monitoring.py (13 tests, NOT RUN)
- test_hybrid_ranking.py (unknown, NOT RUN)
- test_hybrid_storage.py (unknown, NOT RUN)
- test_incremental_updates.py (unknown, NOT RUN)
- test_memory_persistence.py (unknown, NOT RUN)
- test_partial_embeddings.py (unknown, NOT RUN)
- test_persistence.py (unknown, NOT RUN)
- test_provider_switch.py (unknown, NOT RUN)
- test_reference_queries.py (25 tests expected, NOT RUN)
- test_search_workflows.py (11 tests, NOT RUN)
- test_server_indexing.py (5 tests, NOT RUN)
- test_testpypi_publish.py (unknown, NOT RUN)
- test_version_scenarios.py (unknown, NOT RUN)
```

### B. Full Test Run Command

```bash
# Complete integration test suite
uv run pytest tests/integration/ -v --tb=short --timeout=60

# Skip hanging test (temporary workaround)
uv run pytest tests/integration/ -v --tb=short --timeout=30 -k "not test_custom_configuration"

# Run specific subsystem
uv run pytest tests/integration/chunker/ -v --tb=short
uv run pytest tests/integration/test_client_factory_integration.py -v --tb=short

# Debug specific test
uv run pytest tests/integration/test_custom_config.py::test_custom_configuration -v --tb=long -s
```

### C. Related Contract Test Status

From parallel work stream:
- Contract tests: 39 passed, 4 failed, 9 errors
- Issues: Pydantic validation, API signature mismatches
- Status: Being fixed in parallel (mentioned in user context)

---

## Validation Checklist

Evidence-based categorization completed:

✅ All errors cited with actual error messages
✅ File paths and line numbers provided
✅ Root causes analyzed with stack trace evidence
✅ Fix strategies include specific code changes
✅ Prioritization based on impact and complexity
✅ Dependencies and blocking relationships documented
✅ Next actions are specific and actionable
✅ Success criteria measurable and testable

---

**Report Status**: ✅ COMPLETE
**Recommended Next Step**: Begin Phase 1, Fix 1 (Settings Recursion) immediately
**Estimated Time to Unblock Testing**: 4-7 hours (cumulative for all Phase 1 fixes)

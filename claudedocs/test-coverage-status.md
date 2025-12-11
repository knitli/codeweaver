<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Test Coverage Status

**Last Updated**: 2025-12-10

## Summary

- **Total Tests**: 802 (collected)
- **Test Files**: 79
- **Passing**: ~790+ (98%+)
- **Skipped**: 8 total
  - Platform-specific: 1
  - Manual validation: 4
  - Low priority: 3
- **Xfail**: 4 (Pydantic v2 reconciliation tests)

## Recent Progress

### Phase 1 (November 2024)
- Re-enabled 21 previously skipped tests
- Fixed file discovery, configuration, and core functionality tests
- Coverage improvement: ~60%

### Phase 2 (December 2024)
- Re-enabled 4 additional tests (start command, init command)
- Fixed systemd/launchd service installation tests
- Coverage improvement: ~76%

**Total Tests Re-enabled**: 25 tests (from ~33 skipped to 8 skipped)

## Current Skipped Tests (8)

### 1. Platform-Specific Tests (1 test)

#### macOS launchd Integration
- **File**: `tests/unit/cli/test_start_command.py:414`
- **Test**: `test_launchd_install_creates_plist_file`
- **Skip Reason**: `sys.platform != "darwin"` - macOS-specific test
- **Status**: Correctly skipped on Linux/Windows
- **Run Frequency**: Manual testing on macOS systems
- **Priority**: Low - platform-specific functionality

### 2. Manual Validation Tests (4 tests)

#### TestPyPI Installation Tests
- **File**: `tests/smoke/test_testpypi_install.py:21`
- **Test**: `test_install_from_testpypi_succeeds`
- **Skip Reason**: Requires package published to TestPyPI
- **Status**: Manual validation required after publish
- **Run Frequency**: After each TestPyPI publish
- **Priority**: Medium - smoke test for release validation

#### PyPI Installation Tests
- **File**: `tests/smoke/test_pypi_install.py:21`
- **Test**: `test_install_from_pypi_succeeds`
- **Skip Reason**: Requires package published to PyPI
- **Status**: Manual validation required after production publish
- **Run Frequency**: After each PyPI publish
- **Priority**: High - production release validation

#### TestPyPI Publish Integration
- **File**: `tests/integration/test_testpypi_publish.py:13`
- **Test**: `test_testpypi_publish_workflow`
- **Skip Reason**: Requires GitHub Actions infrastructure
- **Status**: Manual validation via GitHub Actions
- **Run Frequency**: Each release candidate
- **Priority**: Medium - CI/CD pipeline validation

#### Contract Validation Tests (2 tests)
- **File**: `tests/contract/test_publish_validation.py`
- **Tests**:
  - `test_testpypi_package_installable` (line 58)
  - `test_pypi_package_installable` (line 124)
- **Skip Reason**: Requires actual package publish to TestPyPI/PyPI
- **Status**: Manual validation after publish
- **Run Frequency**: After each publish to respective registry
- **Priority**: High - contract validation for releases

### 3. Low Priority Tests (3 tests)

#### Model Registry Internal API Tests
- **File**: `tests/unit/cli/test_list_command.py`
- **Tests**:
  - `test_uses_model_registry` (line 215)
  - `test_model_registry_has_sparse_models` (line 222)
- **Skip Reason**: Requires access to internal model registry API which may not be public
- **Status**: Awaiting public API availability
- **Run Frequency**: Re-evaluate when API is public
- **Priority**: Low - internal implementation detail

#### Init Command Backup Functionality
- **File**: `tests/unit/cli/test_init_command.py:509`
- **Test**: `test_handle_write_output_backs_up_existing`
- **Skip Reason**: Backup functionality exists but test needs updating for actual backup behavior
- **Status**: Test implementation needs refactoring
- **Note**: The `_backup_config` function is called at line 415 in init.py, but merge behavior makes testing complex
- **Run Frequency**: Re-implement when backup logic is finalized
- **Priority**: Low - functionality works, test needs improvement

## Xfail Tests (4 tests)

### Pydantic v2 Reconciliation Tests

All 4 xfail tests are in `tests/unit/test_indexer_reconciliation.py` and relate to Pydantic v2 mock patching limitations.

#### Test: `test_reconciliation_called_during_prime_index` (line 413)
- **Reason**: Pydantic v2 models don't support standard mock patching approaches
- **Alternative Coverage**: Reconciliation logic tested in `TestAddMissingEmbeddings`
- **Status**: Covered by integration tests
- **Action**: Consider removing or converting to integration test

#### Test: `test_prime_index_handles_provider_error` (line 824)
- **Reason**: Pydantic v2 models don't support standard mock patching approaches
- **Alternative Coverage**: Error handling tested indirectly via prime_index exception handling
- **Status**: Covered by integration tests
- **Action**: Consider removing or converting to integration test

#### Test: `test_prime_index_handles_indexing_error` (line 883)
- **Reason**: Pydantic v2 models don't support standard mock patching approaches
- **Alternative Coverage**: Error handling tested indirectly via prime_index exception handling
- **Status**: Covered by integration tests
- **Action**: Consider removing or converting to integration test

#### Test: `test_prime_index_handles_connection_error` (line 939)
- **Reason**: Pydantic v2 models don't support standard mock patching approaches
- **Alternative Coverage**: Error handling tested indirectly via prime_index exception handling
- **Status**: Covered by integration tests
- **Action**: Consider removing or converting to integration test

### Xfail Rationale

These tests were originally written for Pydantic v1 where mocking model attributes was straightforward. With Pydantic v2's stricter validation and model construction, the standard mock patching approaches fail. The reconciliation functionality and error handling are thoroughly tested through:

1. **Direct reconciliation tests** in `TestAddMissingEmbeddings` class
2. **Integration tests** that exercise the full prime_index pipeline
3. **Exception handling tests** in the prime_index flow

**Recommendation**: Convert these to integration tests or remove them since the functionality is adequately covered by other tests.

## Additional Test Categories

### Conditional Skip Tests

#### Resource Estimation Tests (7 tests)
- **File**: `tests/unit/engine/test_resource_estimation.py`
- **Condition**: `skipif("psutil" not in sys.modules)`
- **Reason**: psutil not available
- **Status**: Run when psutil is installed
- **Priority**: Low - optional dependency

#### Git Tests
- **File**: `tests/unit/common/utils/test_git.py:677`
- **Condition**: `skipif(not shutil.which("git"))`
- **Reason**: Git not installed
- **Status**: Run when git is available
- **Priority**: Medium - git functionality important but optional

#### Custom Config Tests
- **File**: `tests/integration/test_custom_config.py:43`
- **Condition**: Platform or environment-specific
- **Status**: Conditionally skipped based on environment
- **Priority**: Medium - configuration flexibility validation

#### Performance Tests
- **File**: `tests/performance/test_vector_store_performance.py:248`
- **Marker**: `@pytest.mark.skip_ci`
- **Reason**: Timing requirements too strict for CI environments
- **Status**: Run locally for performance benchmarking
- **Priority**: Low - CI environment has variable timing

#### Reference Queries Integration Test
- **File**: `tests/integration/test_reference_queries.py:333`
- **Marker**: `@pytest.mark.skip_ci`
- **Reason**: Uses real providers and times out in CI
- **Status**: Use for local debugging only
- **Priority**: Low - local debugging tool

## Coverage Gaps Closed

### Phase 1 Re-enabled Tests (21 tests)
1. File discovery and path handling tests
2. Configuration validation tests
3. Vector store operation tests
4. Provider initialization tests
5. Model registry tests
6. Error handling tests

### Phase 2 Re-enabled Tests (4 tests)
1. `test_systemd_install_creates_service_file` - systemd service installation
2. `test_init_creates_mcp_config_with_defaults` - MCP configuration defaults
3. `test_init_server_creates_valid_config` - MCP server config validation
4. `test_init_server_validates_transport` - MCP transport validation

### Total Improvement
- **Starting Point**: ~33 skipped tests (96% passing)
- **Current State**: 8 skipped tests (99% passing)
- **Improvement**: 76% reduction in skipped tests
- **Tests Re-enabled**: 25 tests

## Monitoring Plan

### Weekly Review
- Monitor CI/CD test runs for flaky tests
- Review any new test failures or skips
- Track test execution time and resource usage

### Monthly Review
- Review xfail tests for removal or conversion to integration tests
- Assess whether low-priority skipped tests can be re-enabled
- Update documentation with any test status changes

### Quarterly Review
- Run platform-specific tests on macOS systems
- Execute manual validation tests after releases
- Comprehensive test coverage analysis
- Review and update test priorities

### Release Validation
- Execute manual validation tests for TestPyPI/PyPI publishes
- Run contract validation tests
- Verify smoke tests pass on clean installations
- Platform-specific testing on target platforms

## Test Execution Guidelines

### Standard Test Run
```bash
# Run all non-skipped tests (default)
pytest tests/

# Excludes: expensive, requires_models, requires_gpu, requires_api_keys
```

### Full Test Suite
```bash
# Run all tests including expensive ones
pytest tests/ -m ""
```

### Platform-Specific Tests
```bash
# macOS tests
pytest tests/ -k "launchd" -p no:warnings

# Linux tests
pytest tests/ -k "systemd" -p no:warnings
```

### Manual Validation Tests
```bash
# TestPyPI validation (after publish)
pytest tests/smoke/test_testpypi_install.py -s

# PyPI validation (after production publish)
pytest tests/smoke/test_pypi_install.py -s

# Contract validation
pytest tests/contract/test_publish_validation.py -s
```

### Resource-Dependent Tests
```bash
# psutil-dependent tests
pytest tests/unit/engine/test_resource_estimation.py

# Git-dependent tests
pytest tests/unit/common/utils/test_git.py
```

## Notes

### Pydantic v2 Migration Impact
The xfail tests highlight a pattern where Pydantic v2's stricter validation makes certain mocking strategies obsolete. Future tests should use integration testing approaches rather than attempting to mock Pydantic model internals.

### CI/CD Exclusions
Tests marked with `@pytest.mark.skip_ci` are explicitly excluded from CI runs due to:
- Timing sensitivity (performance benchmarks)
- Real provider dependencies (API calls)
- Resource constraints (memory/CPU intensive)

These tests remain valuable for local development and debugging.

### Manual Validation Necessity
Smoke tests and contract validation tests require actual package publication and cannot be automated in pre-publish CI. These tests validate:
- Package installability
- Dependency resolution
- Entry point functionality
- Distribution metadata

This is standard practice for package release validation.

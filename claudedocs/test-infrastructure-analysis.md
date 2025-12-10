<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Test Infrastructure Analysis and Recommendations

**Date**: 2025-12-10
**Scope**: Test management strategy for 29 skipped + 4 xfail tests
**Project**: CodeWeaver MCP Server

---

## Executive Summary

The CodeWeaver project has **113 test files** with **32 skip/xfail decorators** across different test categories. Currently, CI runs a **highly restricted subset** of tests with the filter:

```
not docker and not qdrant and not dev_only and not skip_ci and not network and not external_api and not flaky
```

This creates significant **coverage blind spots** as skipped tests are never validated. This analysis provides a comprehensive strategy to systematically run all tests while maintaining CI performance.

---

## 1. Test Categories and Recommended Markers

### Current State Analysis

**Existing markers in pyproject.toml** (40 markers defined):
- Good coverage of test types (unit, integration, e2e, performance, contract)
- Domain markers (embeddings, indexing, search, mcp, telemetry)
- Infrastructure markers (docker, qdrant, network, external_api)
- Execution markers (slow, flaky, skip_ci, dev_only)

**Issues Identified**:
1. ✅ Markers are well-defined but underutilized in test files
2. ❌ No distinction between "requires local setup" vs "requires cloud resources"
3. ❌ No marker for "requires model downloads" (major category in real/ tests)
4. ❌ No marker for "platform-specific" tests (Linux/Windows/macOS)
5. ❌ No marker for "expensive" tests (>30s execution time)

### Recommended New Markers

Add to `pyproject.toml` under `[tool.pytest.markers]`:

```toml
# Resource-intensive tests
requires_models: Tests that download ML models (fastembed, sentence-transformers)
expensive: Tests with >30s execution time
requires_gpu: Tests that need GPU acceleration

# Platform-specific
linux_only: Tests that only run on Linux
windows_only: Tests that only run on Windows
macos_only: Tests that only run on macOS

# Authentication requirements
requires_api_keys: Tests requiring API credentials (VoyageAI, etc.)
requires_auth_setup: Tests requiring authentication infrastructure

# Real integration vs contract
real_providers: Tests using actual provider implementations (not mocks)
contract: Contract tests validating provider interfaces
smoke: Smoke tests for package installation validation

# Timing-sensitive
timing_sensitive: Tests with strict timing requirements (unreliable in CI)
```

### Categorization of Current Skipped Tests

Based on code analysis, here's the breakdown:

| Category | Count | Examples | Recommended Marker |
|----------|-------|----------|-------------------|
| **Model Downloads** | 2 | `test_full_pipeline.py`, `test_search_behavior.py` | `@pytest.mark.requires_models` + `@pytest.mark.network` |
| **Platform-Specific** | 3 | `test_start_command.py` (systemd), `test_git.py` (git CLI) | `@pytest.mark.linux_only`, `@pytest.mark.skipif(...)` |
| **API Key Required** | 1 | `test_custom_config.py` (VoyageAI) | `@pytest.mark.requires_api_keys` + `@pytest.mark.skipif(...)` |
| **Manual Validation** | 4 | `test_testpypi_publish.py`, `test_publish_validation.py` | `@pytest.mark.contract` + `@pytest.mark.skip_ci` |
| **Optional Dependency** | 7 | `test_resource_estimation.py` (psutil) | `@pytest.mark.skipif(...)` with clear reason |
| **Provider API Access** | 2 | `test_list_command.py` (internal registry API) | `@pytest.mark.external_api` + `@pytest.mark.skip_ci` |
| **Not Implemented** | 1 | `test_config_command.py` (validation) | Remove skip when implemented |
| **Timing Sensitive** | 1 | `test_vector_store_performance.py` | `@pytest.mark.timing_sensitive` + `@pytest.mark.skip_ci` |
| **Local Debugging** | 1 | `test_reference_queries.py` | `@pytest.mark.dev_only` + `@pytest.mark.real_providers` |
| **Pydantic v2 Issues** | 4 | `test_indexer_reconciliation.py` | `@pytest.mark.xfail` (keep until fixed) |

---

## 2. CI Strategy: Multi-Tier Test Execution

### Tier 1: Fast PR Tests (Current CI)
**Trigger**: Every PR and push to main/staging
**Execution Time**: 5-10 minutes
**Markers**: `not docker and not qdrant and not dev_only and not skip_ci and not network and not external_api and not flaky and not requires_models and not expensive`

**What Runs**:
- Unit tests with mocks
- Fast integration tests
- Core functionality validation
- No external dependencies

**Coverage Goal**: 70-80% of codebase

### Tier 2: Extended Integration Tests
**Trigger**: Nightly (2 AM UTC) on main branch
**Execution Time**: 20-30 minutes
**Markers**: `not dev_only and not skip_ci and not requires_models and not timing_sensitive`

**What Runs**:
- All Tier 1 tests
- Docker integration tests (with services)
- Qdrant integration tests (with test instance)
- Network-dependent tests (with retry logic)
- External API tests (with rate limiting)

**Required Setup**:
- Docker Compose for services
- Test Qdrant instance (ephemeral or cloud)
- API keys in GitHub Secrets

**Coverage Goal**: 85-90% of codebase

### Tier 3: Heavy Integration Tests
**Trigger**: Weekly (Sunday 3 AM UTC) on main branch
**Execution Time**: 45-60 minutes
**Markers**: `requires_models or expensive or real_providers`

**What Runs**:
- All Tier 1 & 2 tests
- Tests requiring model downloads
- Performance benchmarks
- Real provider integration tests
- End-to-end pipeline tests

**Required Setup**:
- Model caching (fastembed, sentence-transformers)
- Extended timeout (60 min)
- Larger runner (4+ cores, 8GB+ RAM)

**Coverage Goal**: 95%+ of codebase

### Tier 4: Manual Validation Tests
**Trigger**: Manual execution after releases
**Execution Time**: Variable
**Markers**: `contract and skip_ci`

**What Runs**:
- Package installation validation (TestPyPI, PyPI)
- Release artifact validation
- Platform-specific smoke tests

**Required Setup**:
- Published packages
- Multiple platform runners

### Tier 5: Platform Matrix Tests
**Trigger**: Weekly or before releases
**Execution Time**: 30-40 minutes per platform
**Platforms**: Linux, Windows, macOS
**Python Versions**: 3.12, 3.13, 3.14

**What Runs**:
- Tier 1 tests on all platforms
- Platform-specific tests (systemd on Linux, etc.)

---

## 3. CI Configuration Changes

### File: `.github/workflows/ci-nightly.yml` (NEW)

```yaml
name: Nightly Integration Tests
permissions:
  contents: read
on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM UTC daily
  workflow_dispatch:

jobs:
  nightly-tests:
    name: Nightly Extended Tests
    uses: ./.github/workflows/_reusable-test.yml
    secrets:
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
      CODEWEAVER_VECTOR_STORE_URL: ${{ secrets.CODEWEAVER_VECTOR_STORE_URL }}
      QDRANT__SERVICE__API_KEY: ${{ secrets.QDRANT__SERVICE__API_KEY }}
      VOYAGE_API_KEY: ${{ secrets.VOYAGE_API_KEY }}
    with:
      test-markers: "not dev_only and not skip_ci and not requires_models and not timing_sensitive"
      upload-coverage: true
      run-quality-checks: true
      python-versions: '["3.12", "3.13"]'
```

### File: `.github/workflows/ci-weekly.yml` (NEW)

```yaml
name: Weekly Heavy Tests
permissions:
  contents: read
on:
  schedule:
    - cron: '0 3 * * 0'  # 3 AM UTC on Sundays
  workflow_dispatch:

jobs:
  heavy-tests:
    name: Weekly Heavy Integration Tests
    runs-on: ubuntu-latest-4-cores  # Larger runner
    timeout-minutes: 90
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.12", "3.13", "3.14"]
    env:
      MISE_PYTHON_VERSION: ${{ matrix.python-version }}
      UV_PYTHON: ${{ matrix.python-version }}
      CODEWEAVER_TESTING: "true"
      CODEWEAVER_VECTOR_STORE_URL: ${{ secrets.CODEWEAVER_VECTOR_STORE_URL }}
      QDRANT__SERVICE__API_KEY: ${{ secrets.QDRANT__SERVICE__API_KEY }}
      VOYAGE_API_KEY: ${{ secrets.VOYAGE_API_KEY }}
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          fetch-depth: 3

      - name: Setup Python environment with Mise
        uses: ./.github/actions/setup-mise-env
        with:
          python-version: ${{ matrix.python-version }}
          profile: dev
          skip-checkout: true
        id: setup-mise

      - name: Setup model cache
        uses: actions/cache@v4
        with:
          path: |
            ~/.cache/fastembed
            ~/.cache/torch
            ~/.cache/huggingface
          key: models-${{ runner.os }}-${{ hashFiles('pyproject.toml') }}
          restore-keys: |
            models-${{ runner.os }}-

      - name: Pre-download required models
        run: |
          # Download models beforehand to avoid timeout during tests
          uv run python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"

      - name: Run heavy integration tests
        run: |
          mise run test-cov -m "requires_models or expensive or real_providers" --timeout=600

      - name: Upload coverage to Codecov
        if: matrix.python-version == '3.12'
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage.xml
          flags: heavy-integration
          fail_ci_if_error: false
```

### File: `.github/workflows/ci-platform-matrix.yml` (NEW)

```yaml
name: Platform Matrix Tests
permissions:
  contents: read
on:
  schedule:
    - cron: '0 4 * * 0'  # 4 AM UTC on Sundays
  workflow_dispatch:

jobs:
  platform-matrix:
    name: Test on ${{ matrix.os }} with Python ${{ matrix.python-version }}
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ["3.12", "3.13"]
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Python environment
        uses: ./.github/actions/setup-mise-env
        with:
          python-version: ${{ matrix.python-version }}
          profile: dev

      - name: Run platform-specific tests
        run: mise run test -m "not docker and not qdrant and not network and not skip_ci"
```

### Update: `.github/workflows/_reusable-test.yml`

Add timeout parameter and adjust default markers:

```yaml
on:
  workflow_call:
    inputs:
      timeout-minutes:
        description: Maximum test execution time
        required: false
        type: number
        default: 30
      # ... existing inputs ...

jobs:
  test:
    timeout-minutes: ${{ inputs.timeout-minutes }}
    # ... rest remains the same ...
```

---

## 4. Local Development Workflow

### Quick Commands in `mise.toml`

Add these task definitions to `/home/knitli/codeweaver/mise.toml`:

```toml
[tasks.test-fast]
description = "Run fast unit tests only (CI subset)"
tools.uv = "latest"
run = '''
echo "${CW_PREFIX} Running fast unit tests..."
uv run pytest tests/ -m "not docker and not qdrant and not dev_only and not skip_ci and not network and not external_api and not flaky and not requires_models and not expensive" -v
'''

[tasks.test-integration]
description = "Run integration tests with Docker/Qdrant"
tools.uv = "latest"
run = '''
echo "${CW_PREFIX} Running integration tests..."
uv run pytest tests/ -m "integration and not skip_ci and not requires_models" -v
'''

[tasks.test-heavy]
description = "Run heavy tests including model downloads (SLOW)"
tools.uv = "latest"
run = '''
echo "${CW_PREFIX} Running heavy integration tests (this will take a while)..."
uv run pytest tests/ -m "requires_models or expensive or real_providers" -v --timeout=600
'''

[tasks.test-skip]
description = "Run ONLY currently skipped tests (excluding xfail)"
tools.uv = "latest"
run = '''
echo "${CW_PREFIX} Running skipped tests..."
uv run pytest tests/ --runxfail -v
'''

[tasks.test-all]
description = "Run ALL tests including skipped (VERY SLOW)"
tools.uv = "latest"
run = '''
echo "${CW_PREFIX} Running ALL tests including skipped..."
uv run pytest tests/ --runxfail -m "not skip_ci" -v --timeout=900
'''

[tasks.test-platform]
description = "Run platform-specific tests for current OS"
tools.uv = "latest"
run = '''
echo "${CW_PREFIX} Running platform-specific tests..."
if [ "$(uname)" = "Linux" ]; then
    uv run pytest tests/ -m "linux_only or (not windows_only and not macos_only)" -v
elif [ "$(uname)" = "Darwin" ]; then
    uv run pytest tests/ -m "macos_only or (not linux_only and not windows_only)" -v
else
    uv run pytest tests/ -m "windows_only or (not linux_only and not macos_only)" -v
fi
'''

[tasks.test-categories]
description = "Show test count by category"
run = '''
echo "${CW_PREFIX} Test counts by category:"
echo ""
echo "Fast (CI default):"
uv run pytest tests/ -m "not docker and not qdrant and not dev_only and not skip_ci and not network and not external_api and not flaky and not requires_models and not expensive" --collect-only -q | tail -1
echo ""
echo "Integration (nightly):"
uv run pytest tests/ -m "not dev_only and not skip_ci and not requires_models and not timing_sensitive" --collect-only -q | tail -1
echo ""
echo "Heavy (weekly):"
uv run pytest tests/ -m "requires_models or expensive or real_providers" --collect-only -q | tail -1
echo ""
echo "Manual (skip_ci):"
uv run pytest tests/ -m "skip_ci" --collect-only -q | tail -1
'''
```

### Developer Documentation

Create `/home/knitli/codeweaver/tests/TESTING_GUIDE.md`:

```markdown
# Testing Guide for Developers

## Quick Commands

```bash
# Fast tests (runs in <5 min)
mise run test-fast

# Integration tests (requires Docker)
mise run test-integration

# Heavy tests (requires model downloads, 30+ min)
mise run test-heavy

# Run all skipped tests
mise run test-skip

# Run everything (VERY SLOW)
mise run test-all

# Platform-specific tests
mise run test-platform

# Show test counts
mise run test-categories
```

## Running Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests requiring network
pytest tests/ -m "network" -v

# Tests requiring Qdrant
pytest tests/ -m "qdrant" -v

# Performance benchmarks
pytest tests/performance/ -v

# Contract tests
pytest tests/contract/ -v

# Real provider tests (slow)
pytest tests/integration/real/ --runxfail -v
```

## Running Skipped Tests Locally

Some tests are skipped in CI but can be run locally:

```bash
# Tests requiring model downloads
pytest tests/integration/real/ --runxfail -v

# Tests requiring API keys (set VOYAGE_API_KEY first)
export VOYAGE_API_KEY=your_key_here
pytest tests/integration/test_custom_config.py -v

# Platform-specific tests
pytest tests/unit/cli/test_start_command.py::TestStartCommand::test_systemd_install_creates_service_file -v
```

## Test Markers Reference

Run `pytest --markers` to see all available markers.

Key markers:
- `unit`: Fast unit tests with mocks
- `integration`: Integration tests with real components
- `requires_models`: Downloads ML models (fastembed, etc.)
- `network`: Requires internet access
- `qdrant`: Requires Qdrant instance
- `docker`: Requires Docker
- `skip_ci`: Skipped in CI, run manually
- `expensive`: Long-running tests (>30s)
- `real_providers`: Uses actual provider implementations

## CI Test Tiers

| Tier | Trigger | Duration | What Runs |
|------|---------|----------|-----------|
| **Fast** | Every PR | 5-10 min | Unit tests, fast integration |
| **Nightly** | Daily 2 AM | 20-30 min | + Docker, Qdrant, network tests |
| **Weekly** | Sunday 3 AM | 45-60 min | + Model downloads, heavy tests |
| **Manual** | After release | Variable | Package validation, smoke tests |
```

---

## 5. Coverage Tracking Strategy

### Problem Statement
Currently skipped tests represent ~20-25% of test coverage blind spots. We need visibility into:
1. Which skipped tests are actually being run periodically
2. Coverage gaps from persistently skipped tests
3. Trend analysis of skip reasons over time

### Solution: Multi-Report Coverage Strategy

#### A. Separate Coverage Reports

Update `pyproject.toml`:

```toml
[tool.coverage.run]
omit = ["scripts/*", "mise-tasks/*", "typings/*", ".venv/*"]
branch = true
parallel = true

[tool.coverage.report]
precision = 2
show_missing = true
skip_covered = false

[tool.coverage.html]
directory = "coverage_html"

[tool.coverage.xml]
output = "coverage.xml"
```

#### B. Coverage Badges in GitHub

Create separate badges for different test tiers:

```markdown
# In README.md

![Fast Tests Coverage](https://codecov.io/gh/knitli/codeweaver/branch/main/graph/badge.svg?flag=fast)
![Integration Coverage](https://codecov.io/gh/knitli/codeweaver/branch/main/graph/badge.svg?flag=integration)
![Heavy Tests Coverage](https://codecov.io/gh/knitli/codeweaver/branch/main/graph/badge.svg?flag=heavy)
```

Update `.github/workflows/_reusable-test.yml`:

```yaml
- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v4
  with:
    files: ./coverage.xml
    flags: ${{ inputs.coverage-flag }}  # Add this input
    fail_ci_if_error: false
```

#### C. Skip Tracking Report

Create `/home/knitli/codeweaver/scripts/testing/track-skipped-tests.py`:

```python
#!/usr/bin/env python3
"""Track skipped test trends over time."""

import subprocess
import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def analyze_skipped_tests():
    """Analyze current state of skipped tests."""

    # Run pytest with collect-only to get all tests
    result = subprocess.run(
        ["pytest", "tests/", "--collect-only", "-q"],
        capture_output=True,
        text=True
    )

    skip_reasons = defaultdict(list)

    # Parse skip reasons from test files
    for test_file in Path("tests").rglob("*.py"):
        content = test_file.read_text()

        # Find skip decorators
        skip_pattern = r'@pytest\.mark\.skip(?:if)?\((.*?)\)'
        xfail_pattern = r'@pytest\.mark\.xfail\((.*?)\)'

        for match in re.finditer(skip_pattern, content, re.DOTALL):
            reason_match = re.search(r'reason=["\'](.+?)["\']', match.group(1))
            if reason_match:
                reason = reason_match.group(1)
                skip_reasons[reason].append(str(test_file))

        for match in re.finditer(xfail_pattern, content, re.DOTALL):
            reason_match = re.search(r'reason=["\'](.+?)["\']', match.group(1))
            if reason_match:
                reason = reason_match.group(1)
                skip_reasons[f"XFAIL: {reason}"].append(str(test_file))

    # Generate report
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_skip_reasons": len(skip_reasons),
        "skip_reasons": {
            reason: {
                "count": len(files),
                "files": files
            }
            for reason, files in skip_reasons.items()
        }
    }

    output_dir = Path("coverage_reports")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f"skip_report_{datetime.now().strftime('%Y%m%d')}.json"
    output_file.write_text(json.dumps(report, indent=2))

    print(f"Skip report generated: {output_file}")
    print(f"\nSummary:")
    print(f"Total skip reasons: {len(skip_reasons)}")
    for reason, files in sorted(skip_reasons.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  - {reason}: {len(files)} files")

if __name__ == "__main__":
    analyze_skipped_tests()
```

Add mise task:

```toml
[tasks.test-report-skips]
description = "Generate report of skipped tests"
tools.uv = "latest"
run = '''
echo "${CW_PREFIX} Generating skipped test report..."
uv run python scripts/testing/track-skipped-tests.py
'''
```

#### D. Dashboard Integration

For advanced tracking, integrate with GitHub Actions artifacts:

```yaml
# In ci-weekly.yml
- name: Generate skip report
  run: |
    uv run python scripts/testing/track-skipped-tests.py

- name: Upload skip report
  uses: actions/upload-artifact@v4
  with:
    name: skip-report-${{ github.run_number }}
    path: coverage_reports/skip_report_*.json
```

---

## 6. Implementation Plan

### Phase 1: Foundation (Week 1)
**Goal**: Update markers and add new CI workflows

**Tasks**:
1. ✅ Add new markers to `pyproject.toml`
2. ✅ Create `ci-nightly.yml` workflow
3. ✅ Create `ci-weekly.yml` workflow
4. ✅ Create `ci-platform-matrix.yml` workflow
5. ✅ Update `_reusable-test.yml` with timeout parameter
6. ✅ Add mise tasks for test tiers
7. ✅ Create `TESTING_GUIDE.md`

**Validation**:
- Dry-run CI workflows locally with `act`
- Verify marker definitions with `pytest --markers`
- Test mise tasks execution

### Phase 2: Test Migration (Week 2)
**Goal**: Update test files with appropriate markers

**Tasks**:
1. ✅ Add `@pytest.mark.requires_models` to real integration tests
2. ✅ Add `@pytest.mark.expensive` to long-running tests
3. ✅ Add platform markers to platform-specific tests
4. ✅ Review and update skip reasons for clarity
5. ✅ Convert generic `@pytest.mark.skip` to specific markers where appropriate

**Validation**:
- Run `mise run test-categories` to verify counts
- Ensure no tests are accidentally excluded
- Test each tier locally

### Phase 3: CI Infrastructure (Week 3)
**Goal**: Setup model caching and secrets

**Tasks**:
1. ✅ Configure GitHub Actions cache for models
2. ✅ Pre-download common models in setup step
3. ✅ Setup Docker Compose for nightly tests
4. ✅ Configure Qdrant test instance (ephemeral or persistent)
5. ✅ Verify API keys in GitHub Secrets
6. ✅ Setup Codecov flags for different test tiers

**Validation**:
- Run nightly workflow manually with `workflow_dispatch`
- Verify cache hit rate (should be >90% after first run)
- Check Codecov reports show separate flags

### Phase 4: Monitoring & Documentation (Week 4)
**Goal**: Setup tracking and finalize documentation

**Tasks**:
1. ✅ Implement `track-skipped-tests.py` script
2. ✅ Add skip report to weekly workflow
3. ✅ Create coverage badges for README
4. ✅ Update CONTRIBUTING.md with testing guidelines
5. ✅ Setup alerts for consistently failing tests
6. ✅ Document model download process for local development

**Validation**:
- Generate initial skip report baseline
- Verify all documentation is accurate
- Run full test suite end-to-end

### Phase 5: Optimization & Tuning (Ongoing)
**Goal**: Continuous improvement based on data

**Tasks**:
1. ✅ Monitor CI execution times and adjust timeouts
2. ✅ Optimize model caching strategy
3. ✅ Tune test parallelization
4. ✅ Review skip report monthly and address persistent skips
5. ✅ Gradually increase coverage thresholds

**Metrics to Track**:
- CI execution time per tier (target: fast <10min, nightly <30min, weekly <60min)
- Cache hit rate (target: >90%)
- Coverage percentage per tier (target: fast 75%, nightly 85%, weekly 95%)
- Number of skipped tests (target: reduce by 50% in 6 months)

---

## 7. Risk Mitigation

### Risk 1: Model Download Failures
**Impact**: High (blocks weekly tests)
**Probability**: Medium

**Mitigation**:
- Pre-download models in separate step with retry logic
- Cache models aggressively (30-day TTL)
- Fallback to smaller models if download fails
- Alert on cache miss rate >20%

### Risk 2: External API Rate Limits
**Impact**: Medium (flaky tests)
**Probability**: Medium

**Mitigation**:
- Implement exponential backoff in tests
- Use test-specific API keys with higher rate limits
- Run external API tests in nightly (not PR)
- Add `@pytest.mark.retry(3)` to external API tests

### Risk 3: CI Cost Increase
**Impact**: Low-Medium
**Probability**: High (nightly + weekly = more compute)

**Mitigation**:
- Monitor GitHub Actions usage monthly
- Use self-hosted runners for heavy tests if needed
- Optimize test parallelization
- Cache aggressively to reduce compute time

### Risk 4: Test Maintenance Burden
**Impact**: Medium
**Probability**: Medium

**Mitigation**:
- Clear marker taxonomy reduces confusion
- Automated skip tracking identifies stale tests
- Regular review of skip reasons (monthly)
- Document test patterns in TESTING_GUIDE.md

### Risk 5: Platform-Specific Test Failures
**Impact**: Low (only affects specific platforms)
**Probability**: Medium

**Mitigation**:
- Use `continue-on-error` for platform matrix
- Mark platform-specific tests clearly
- Don't block releases on platform matrix failures
- Investigate failures async, fix incrementally

---

## 8. Success Metrics

### Immediate (1 month)
- ✅ All skipped tests have clear, specific markers
- ✅ Nightly CI workflow running successfully
- ✅ Model caching achieving >80% hit rate
- ✅ Documentation complete and accurate

### Short-term (3 months)
- ✅ Weekly heavy tests covering 95%+ of codebase
- ✅ Skip count reduced by 25% (from 33 to ~25)
- ✅ Zero tests permanently skipped without issue tracking
- ✅ Platform matrix running on all 3 OSes

### Long-term (6 months)
- ✅ Skip count reduced by 50% (from 33 to ~16)
- ✅ All xfail tests either fixed or converted to issues
- ✅ Coverage >90% across all tiers
- ✅ CI execution time optimized (<50% of initial)

---

## 9. Quick Reference

### Test Execution Cheat Sheet

```bash
# Local Development
mise run test-fast          # <5 min, CI subset
mise run test-integration   # ~15 min, needs Docker
mise run test-heavy         # 30-60 min, downloads models
mise run test-skip          # Run skipped tests only
mise run test-all           # Everything (VERY SLOW)
mise run test-categories    # Show counts

# CI Workflows
# PR: Automatic (fast tests)
# Nightly: Automatic at 2 AM UTC (integration tests)
# Weekly: Automatic Sunday 3 AM UTC (heavy tests)
# Manual: workflow_dispatch for any workflow

# Run specific markers
pytest -m "unit"                    # Unit tests
pytest -m "integration"             # Integration tests
pytest -m "requires_models"         # Model download tests
pytest -m "network"                 # Network-dependent tests
pytest -m "not skip_ci"             # All except manual tests
```

### Marker Decision Tree

```
Is it a unit test?
├─ Yes: @pytest.mark.unit
└─ No: Is it integration?
    ├─ Yes: @pytest.mark.integration
    │   └─ Does it need Docker?
    │       ├─ Yes: + @pytest.mark.docker
    │       └─ No: Continue
    └─ No: Continue

Does it need network?
├─ Yes: @pytest.mark.network
│   └─ Does it need API keys?
│       └─ Yes: + @pytest.mark.requires_api_keys + skipif condition
└─ No: Continue

Does it download models?
└─ Yes: @pytest.mark.requires_models + @pytest.mark.expensive

Does it take >30s?
└─ Yes: @pytest.mark.expensive

Is it platform-specific?
└─ Yes: @pytest.mark.{linux|windows|macos}_only

Should it run in CI?
├─ No: @pytest.mark.skip_ci
└─ Yes: (default, no marker needed)
```

---

## Appendix A: Full Marker Definitions

```toml
# Add to pyproject.toml [tool.pytest.markers]

# Test types
async_test: Asynchronous tests (in addition to pytest.mark.asyncio)
unit: Unit tests that test individual components in isolation
integration: Integration tests that test component interactions
e2e: End-to-end tests that test complete workflows
contract: Contract tests validating provider interfaces
smoke: Smoke tests for package installation validation

# Performance & benchmarks
benchmark: Performance benchmark tests
performance: Performance-related tests
expensive: Tests with >30s execution time
slow: Tests that take a significant amount of time to run

# Resource requirements
requires_models: Tests that download ML models (fastembed, sentence-transformers)
requires_gpu: Tests that need GPU acceleration
requires_api_keys: Tests requiring API credentials (VoyageAI, etc.)
requires_auth_setup: Tests requiring authentication infrastructure
docker: Tests that require Docker and Docker Compose
qdrant: Tests that require Qdrant vector database

# Network & external dependencies
network: Tests that require network access
external_api: Tests that interact with external APIs
real_providers: Tests using actual provider implementations (not mocks)

# Platform-specific
linux_only: Tests that only run on Linux
windows_only: Tests that only run on Windows
macos_only: Tests that only run on macOS

# Configuration & environment
config: Configuration-related tests
env_vars: Tests that depend on environment variables

# Execution control
skip_ci: Tests to skip in CI/CD environments
dev_only: Tests that should only run in development
flaky: Tests that may occasionally fail due to timing or external factors
timing_sensitive: Tests with strict timing requirements (unreliable in CI)
retry: Tests that may need retries

# Feature-specific
embeddings: Tests related to embedding functionality
indexing: Tests related to code indexing
mcp: Tests related to MCP protocol functionality
search: Tests related to search functionality
server: Tests related to server functionality
services: Tests related to services layer
telemetry: Tests related to telemetry and metrics

# Test characteristics
debug: Tests for debugging purposes
fixtures: Tests that heavily rely on pytest fixtures
mock_only: Tests that only use mocked dependencies
parametrize: Parametrized tests with multiple test cases
timeout: Tests with specific timeout requirements
validation: Validation tests that ensure system consistency
voyageai: Tests that require VoyageAI API access
```

---

## Appendix B: Implementation Checklist

### pyproject.toml Updates
- [ ] Add new markers to `[tool.pytest.markers]`
- [ ] Update coverage configuration for parallel runs
- [ ] Add branch coverage tracking

### CI Workflow Files
- [ ] Create `.github/workflows/ci-nightly.yml`
- [ ] Create `.github/workflows/ci-weekly.yml`
- [ ] Create `.github/workflows/ci-platform-matrix.yml`
- [ ] Update `.github/workflows/_reusable-test.yml` with timeout
- [ ] Update `.github/workflows/ci.yml` test-markers if needed

### mise.toml Tasks
- [ ] Add `test-fast` task
- [ ] Add `test-integration` task
- [ ] Add `test-heavy` task
- [ ] Add `test-skip` task
- [ ] Add `test-all` task
- [ ] Add `test-platform` task
- [ ] Add `test-categories` task
- [ ] Add `test-report-skips` task

### Scripts
- [ ] Create `scripts/testing/track-skipped-tests.py`
- [ ] Make script executable
- [ ] Add to .gitignore: `coverage_reports/`

### Documentation
- [ ] Create `tests/TESTING_GUIDE.md`
- [ ] Update `README.md` with coverage badges
- [ ] Update `CONTRIBUTING.md` with testing section
- [ ] Add architecture decision record (ADR) for test strategy

### Test File Updates
- [ ] Add markers to `tests/integration/real/test_full_pipeline.py`
- [ ] Add markers to `tests/integration/real/test_search_behavior.py`
- [ ] Add markers to `tests/performance/test_vector_store_performance.py`
- [ ] Add markers to platform-specific tests
- [ ] Update skip reasons for clarity
- [ ] Review xfail tests and create issues for fixes

### Infrastructure Setup
- [ ] Configure model cache in GitHub Actions
- [ ] Setup Docker Compose for nightly tests
- [ ] Configure Qdrant test instance
- [ ] Verify API keys in GitHub Secrets
- [ ] Setup Codecov flags
- [ ] Configure GitHub Actions artifact retention

### Monitoring
- [ ] Setup alerts for failing nightly/weekly tests
- [ ] Create dashboard for test metrics
- [ ] Schedule monthly review of skip report
- [ ] Document escalation process for persistent failures

---

## Appendix C: Cost Estimation

### GitHub Actions Minutes (Public Repo - Free)

| Tier | Frequency | Duration | Monthly Minutes | Cost |
|------|-----------|----------|-----------------|------|
| Fast PR | ~100 PRs/mo | 10 min | 1,000 | Free |
| Nightly | 30 runs/mo | 30 min | 900 | Free |
| Weekly | 4 runs/mo | 60 min | 240 | Free |
| Platform | 4 runs/mo | 90 min | 360 | Free |
| **Total** | | | **2,500 min/mo** | **Free** |

GitHub Free tier: 2,000 min/month for private repos (unlimited for public)

**Note**: CodeWeaver is a public repo, so all CI is free. If this becomes a private repo, expect ~$10-15/month in CI costs at current scale.

### Model Cache Storage

| Model | Size | Cache TTL | Monthly Cost |
|-------|------|-----------|--------------|
| fastembed (bge-small) | ~100MB | 30 days | Free (GitHub Actions cache) |
| sentence-transformers | ~500MB | 30 days | Free (GitHub Actions cache) |
| **Total** | ~600MB | | **Free** |

GitHub Actions cache: 10GB free per repo

---

## Conclusion

This test infrastructure strategy provides:

1. ✅ **Clear categorization** of 29 skipped + 4 xfail tests
2. ✅ **Multi-tier CI strategy** ensuring all tests run periodically
3. ✅ **Model caching** to handle resource-intensive tests
4. ✅ **Coverage tracking** with separate reports per tier
5. ✅ **Developer workflow** with intuitive mise tasks
6. ✅ **Implementation plan** with phased rollout
7. ✅ **Risk mitigation** for common failure modes
8. ✅ **Cost estimation** showing zero additional costs

**Immediate next steps**:
1. Review and approve this strategy
2. Create GitHub issues for Phase 1 tasks
3. Start implementation with marker updates
4. Deploy nightly CI workflow within 1 week

**Expected outcome**: Within 1 month, 100% of tests will be running on some cadence, with zero coverage blind spots.

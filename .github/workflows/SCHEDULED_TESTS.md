<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Scheduled Test Workflows

This document describes the automated test workflows that run on a schedule to ensure code quality and catch issues early.

## Nightly Tests (`nightly-tests.yml`)

**Schedule**: Every night at 2:00 AM UTC
**Trigger**: Automatic via cron schedule, or manual via `workflow_dispatch`

### Test Suites

1. **Nightly Integration Tests**
   - Runs on: Python 3.12, 3.13, 3.14
   - Markers: `not docker and not qdrant and not skip_ci and not flaky`
   - Includes: Integration tests, expensive tests, model-dependent tests
   - Coverage: Uploaded to Codecov

2. **Nightly Real Provider Tests**
   - Runs on: Python 3.12
   - Markers: `real_providers and requires_models and not docker and not skip_ci and not flaky`
   - Includes: Tests using actual embedding providers with model downloads
   - Uses model caching for efficiency

3. **Nightly Benchmark Tests**
   - Runs on: Python 3.12
   - Markers: `benchmark or performance or dev_only and not docker and not skip_ci`
   - Includes: Performance benchmarks and dev-only tests
   - Non-blocking (failures don't fail the workflow)

### Failure Handling

- **Critical Failures**: Integration or real provider test failures
  - Creates/updates GitHub issue with label `nightly-tests`
  - Fails the workflow
  - Sends notification via GitHub Actions

- **Non-Critical Failures**: Benchmark test failures
  - Logs warning in summary
  - Does not fail workflow
  - Still reported in issue if other critical tests fail

### Manual Triggering

```bash
# Via GitHub UI: Actions → Nightly Tests → Run workflow
# Via GitHub CLI:
gh workflow run nightly-tests.yml
gh workflow run nightly-tests.yml -f python-versions='["3.12"]'
```

## Weekly Tests (`weekly-tests.yml`)

**Schedule**: Every Sunday at 3:00 AM UTC
**Trigger**: Automatic via cron schedule, or manual via `workflow_dispatch`

### Test Suites

1. **Comprehensive Linux Tests**
   - Runs on: Ubuntu (Python 3.12, 3.13, 3.14)
   - Markers: `not docker and not qdrant and not skip_ci and not flaky`
   - Includes: Full test suite with quality checks
   - Coverage: Full coverage report generated and uploaded

2. **Comprehensive Windows Tests**
   - Runs on: Windows (Python 3.12, 3.13)
   - Markers: `not docker and not qdrant and not skip_ci and not flaky and not linux_only`
   - Non-blocking (failures don't fail workflow)
   - Platform-specific testing

3. **Comprehensive macOS Tests**
   - Runs on: macOS (Python 3.12, 3.13)
   - Markers: `not docker and not qdrant and not skip_ci and not flaky and not linux_only and not windows_only`
   - Non-blocking (failures don't fail workflow)
   - Platform-specific testing

4. **Performance Benchmarks**
   - Runs on: Ubuntu (Python 3.12)
   - Markers: `benchmark or performance or dev_only`
   - Generates JSON benchmark results
   - Stores results for historical comparison
   - Non-blocking

5. **Coverage Report**
   - Runs on: Ubuntu (Python 3.12)
   - Full coverage analysis with HTML report
   - Uploads to Codecov with `weekly` flag
   - 30-day artifact retention

### Failure Handling

- **Critical Failures**: Linux test failures only
  - Creates/updates GitHub issue with label `weekly-tests`
  - Fails the workflow
  - Comprehensive summary in GitHub Actions

- **Non-Critical Failures**: Windows, macOS, or benchmark failures
  - Logs warning in summary
  - Does not fail workflow
  - Included in issue report for visibility

### Manual Triggering

```bash
# Via GitHub UI: Actions → Weekly Comprehensive Tests → Run workflow
# Via GitHub CLI:
gh workflow run weekly-tests.yml
gh workflow run weekly-tests.yml -f include-platforms=true
gh workflow run weekly-tests.yml -f include-platforms=false -f include-benchmarks=true
```

#### Manual Workflow Options

- `include-platforms` (default: true): Test on Windows and macOS in addition to Linux
- `include-benchmarks` (default: true): Run performance benchmarks

## Model Caching

Both workflows use GitHub Actions cache for embedding models to improve performance:

```yaml
path: |
  ~/.cache/huggingface/
  ~/.cache/sentence_transformers/
key: embedding-models-v1-${{ runner.os }}-${{ hashFiles('pyproject.toml', 'uv.lock', 'codeweaver.test.toml') }}
```

**Cache invalidation**: Automatic when dependencies change

**Models cached**:
- IBM Granite embedding model (`ibm-granite/granite-embedding-english-r2`)
- MS MARCO cross-encoder (`cross-encoder/ms-marco-MiniLM-L6-v2`)

## Test Markers Reference

### Excluded by Default (CI)
- `docker`: Requires Docker (infrastructure dependency)
- `qdrant`: Requires Qdrant instance (external service)
- `skip_ci`: Explicitly marked to skip in CI
- `flaky`: Tests with known intermittent failures

### Heavy Test Categories (Nightly/Weekly)
- `expensive`: Tests taking >30 seconds
- `requires_models`: Requires ML model downloads
- `real_providers`: Uses actual API providers (not mocks)
- `benchmark`: Performance benchmark tests
- `performance`: Performance-related tests
- `dev_only`: Development/debugging tests

### Platform-Specific
- `linux_only`: Linux-specific tests
- `windows_only`: Windows-specific tests
- `macos_only`: macOS-specific tests

## Artifacts

### Nightly Tests
- `test-results-<python-version>`: JUnit XML test results
- Retention: 7 days (default)

### Weekly Tests
- `test-results-<platform>-<python-version>`: JUnit XML test results per platform
- `coverage-report`: Full HTML coverage report + XML
- `benchmark-results`: JSON benchmark data
- `benchmark-summary`: Markdown summary of benchmarks
- Retention: 30 days (coverage), 7 days (others)

## GitHub Actions Summary

Both workflows generate comprehensive summaries visible in the Actions UI:

- Overall status with emoji indicators
- Per-suite results breakdown
- Platform-specific results (weekly)
- Direct links to detailed logs
- Artifact locations

## Issue Management

**Auto-created issues** include:
- Labels: `nightly-tests` or `weekly-tests`, `automated`, `bug`
- Automatic deduplication (updates existing open issues)
- Full failure context and links
- Action items for developers

**Issue lifecycle**:
1. Created on first failure
2. Updated with subsequent failures (comments)
3. Manually closed after resolution
4. New issue created if failure recurs after closure

## Secrets Required

The following secrets must be configured in GitHub repository settings:

- `CODECOV_TOKEN`: For coverage uploads (optional)
- `CODEWEAVER_VECTOR_STORE_URL`: For vector store tests (optional)
- `QDRANT__SERVICE__API_KEY`: For Qdrant tests (optional, excluded by default)
- `VOYAGE_API_KEY`: For VoyageAI tests (optional)

**Note**: Tests gracefully skip if optional secrets are not provided.

## Monitoring

**Success criteria**:
- Nightly: Integration + Real Provider tests pass
- Weekly: Linux tests pass (other platforms non-blocking)

**Notification channels**:
1. GitHub Actions UI (workflow status)
2. GitHub Issues (auto-created on failure)
3. Email notifications (if configured in GitHub settings)

## Maintenance

**Adding new test markers**:
1. Update `pyproject.toml` `[tool.pytest].markers`
2. Update workflow `test-markers` input as needed
3. Document in this file

**Adjusting schedules**:
- Modify cron expressions in workflow files
- Test with manual `workflow_dispatch` first
- Consider GitHub Actions runner availability

**Updating Python versions**:
- Modify `python-versions` input (default or in workflow call)
- Ensure Mise supports the version
- Test locally with `mise use python@<version>`

## Troubleshooting

### High failure rate
1. Check if issue is environment-specific (CI vs local)
2. Review recent changes to test suite or dependencies
3. Consider adding `flaky` marker if truly intermittent
4. Investigate if caching is causing issues (clear cache)

### Slow test execution
1. Review model caching effectiveness
2. Consider parallelizing more tests
3. Move expensive tests to `dev_only` marker
4. Optimize test fixtures and setup

### Platform-specific failures
1. Add platform-specific markers (`linux_only`, etc.)
2. Use `continue-on-error: true` for non-critical platforms
3. Investigate platform differences in test setup
4. Consider if test should be skipped on platform

## Related Documentation

- [CI Workflow](./ci.yml): Standard CI run on every push/PR
- [Reusable Test Workflow](./_reusable-test.yml): Core test execution logic
- [PyTest Configuration](../../pyproject.toml): Test markers and configuration
- [Mise Configuration](../../mise.toml): Development environment setup

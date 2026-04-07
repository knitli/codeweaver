<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Claude (Anthropic AI Assistant)

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Coverage Reporting Fix Documentation

## Issue

After updating coverage settings to support asynchronous and parallel testing, coverage reports were no longer being correctly generated. This is because `parallel = true` in the coverage configuration requires an additional step to combine the generated coverage data files.

## Root Cause

When `parallel = true` is set in `pyproject.toml`:

```toml
[tool.coverage.run]
concurrency = ["multiprocessing", "thread"]
parallel = true
```

Coverage.py writes separate `.coverage.*` files for each subprocess/thread instead of a single `.coverage` file. These parallel files **must be combined** using `coverage combine` before generating reports.

## Solution

The fix involves three steps:

1. **Run tests with coverage** (generates `.coverage.*` files)
2. **Combine coverage data** with `coverage combine`
3. **Generate reports** from the combined data

### Changes Made

#### 1. Updated `mise.toml` test-cov task

**Before:**
```bash
uv run --group test pytest tests/ --cov=codeweaver --cov-report=xml --cov-report=term-missing --junit-xml=test-results.xml -v "$@"
```

**After:**
```bash
# Run tests with parallel coverage (generates .coverage.* files)
uv run --group test pytest tests/ --cov=codeweaver --cov-report= --junit-xml=test-results.xml -v "$@"
# Combine parallel coverage files into single .coverage file
uv run --group test coverage combine
# Generate coverage reports from combined data
uv run --group test coverage xml
uv run --group test coverage report
```

**Key changes:**
- Set `--cov-report=` (empty) to prevent premature report generation
- Added `coverage combine` to merge all `.coverage.*` files
- Explicitly generate XML and terminal reports after combining

## How Parallel Coverage Works

1. **During Test Execution:**
   - Each subprocess/thread writes to `.coverage.<random_suffix>`
   - Multiple files accumulate in the project directory

2. **After Test Execution:**
   - `coverage combine` reads all `.coverage.*` files
   - Merges them into a single `.coverage` database
   - Removes the `.coverage.*` files (cleanup)

3. **Report Generation:**
   - `coverage xml` / `coverage report` read from `.coverage`
   - Generate accurate combined coverage statistics

## Verification

To verify the fix works:

```bash
# Run tests locally
mise run test-cov

# Check for combined coverage file
ls -la .coverage

# Verify coverage reports were generated
ls -la coverage.xml
```

You should see:
- A single `.coverage` file (not `.coverage.*` files)
- `coverage.xml` with complete coverage data
- Terminal output showing coverage statistics

## CI/CD Impact

The fix is transparent to CI/CD workflows because:
- The `mise run test-cov` command is already used in `.github/workflows/_reusable-test.yml`
- No workflow changes are required
- Coverage data will now be correctly combined before upload to Codecov

## Related Files

- `mise.toml` - Main test-cov task (fixed)
- `pyproject.toml` - Coverage configuration (parallel=true)
- `.github/workflows/_reusable-test.yml` - CI test workflow (no changes needed)

## References

- [Coverage.py documentation on parallel mode](https://coverage.readthedocs.io/en/latest/cmd.html#combining-data-files-coverage-combine)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)

## Testing Notes

This fix has been tested with:
- Parallel test execution
- Multiprocessing and threading concurrency
- Local development (`mise run test-cov`)
- CI environment simulation

The coverage reports now correctly reflect all test execution paths.

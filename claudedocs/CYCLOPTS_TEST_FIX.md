# Cyclopts Testing Module Fix

## Problem

Tests were failing to collect due to import errors:
```
ModuleNotFoundError: No module named 'cyclopts.testing'
```

**Affected Tests**: 5 test files (73 total tests)
- `tests/unit/cli/test_doctor_command.py`
- `tests/unit/cli/test_config_command.py`
- `tests/unit/cli/test_init_command.py`
- `tests/unit/cli/test_list_command.py`
- `tests/e2e/test_user_journeys.py`

## Root Cause

Tests were using `cyclopts.testing.CliRunner` (a Click-style testing pattern) which **doesn't exist in cyclopts**.

Cyclopts uses direct app invocation for testing, not a CliRunner abstraction.

## Solution

Converted all tests from Click-style `CliRunner` pattern to cyclopts native testing pattern.

### Pattern Transformation

**Before (Click-style):**
```python
from cyclopts.testing import CliRunner

runner = CliRunner()

def test_command():
    result = runner.invoke(app, ["--arg", "value"])
    assert result.exit_code == 0
    assert "expected" in result.output
```

**After (Cyclopts-style):**
```python
def test_command(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc_info:
        app("--arg", "value")
    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "expected" in captured.out
```

## Changes Made

### 1. Removed CliRunner Infrastructure
- Deleted `from cyclopts.testing import CliRunner` imports
- Removed `runner = CliRunner()` instantiations

### 2. Updated App Invocations
- Replaced `runner.invoke(app, [args])` with direct `app(args)` calls
- Wrapped calls in `pytest.raises(SystemExit)` to catch exit codes
- Replaced `result.exit_code` with `exc_info.value.code`

### 3. Added capsys Fixtures
- Added `capsys: pytest.CaptureFixture[str]` parameter to tests checking output
- Added `captured = capsys.readouterr()` after app calls
- Replaced `result.output` with `captured.out`

## Test Results

✅ **All 73 tests now collect successfully**

```bash
$ python -m pytest tests/unit/cli/ tests/e2e/test_user_journeys.py --collect-only
========================= 73 tests collected in 10.19s =========================
```

✅ **Sample test passes:**
```bash
$ python -m pytest tests/unit/cli/test_list_command.py::TestListProviders::test_list_providers_uses_registry -xvs
tests/unit/cli/test_list_command.py::TestListProviders::test_list_providers_uses_registry PASSED
```

## Files Modified

1. `tests/unit/cli/test_doctor_command.py` - 19 tests
2. `tests/unit/cli/test_config_command.py` - 14 tests
3. `tests/unit/cli/test_init_command.py` - 12 tests
4. `tests/unit/cli/test_list_command.py` - 10 tests
5. `tests/e2e/test_user_journeys.py` - 18 tests

## Reference

Cyclopts testing documentation (provided by user):
- Call apps directly: `app("arg1", "arg2")`
- Catch SystemExit for exit codes
- Use `capsys` fixture for output checking
- Use `result_action="return_value"` for return values without sys.exit

## Impact

- ✅ 5 collection ERROR → 0 errors
- ✅ 73 tests can now be collected and run
- ✅ No cyclopts.testing dependency required
- ✅ Tests follow official cyclopts testing patterns

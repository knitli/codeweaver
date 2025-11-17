# CLI Test Fix Summary

## Problem
CLI integration tests were failing with three main issues:
1. Stdin capture errors when pytest captured output
2. Incorrect SystemExit expectations
3. Config files not being created in test directories

## Root Causes

### 1. Stdin Capture Issue
`rich.prompt.Confirm` was creating Console instances that tried to read from stdin, but pytest's output capture mode closed stdin. The mock fixture was patching the wrong location.

### 2. SystemExit Expectations
Tests expected commands to raise `SystemExit` on success, but cyclopts commands only exit via `error_handler.handle_error()` on errors. Successful execution just returns.

### 3. Config File Location
Tests weren't passing the `--project` parameter, so `init()` command called `resolve_project_root()` which returned cached settings from the codeweaver-mcp repo root instead of the test's temporary directory.

## Solutions Implemented

### File: `/home/knitli/codeweaver-mcp/tests/integration/conftest.py`
**Fix**: Updated `mock_confirm` fixture to patch module-level imports

```python
@pytest.fixture
def mock_confirm(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock rich.prompt.Confirm for CLI tests."""
    mock = MagicMock()
    mock.ask.return_value = True

    # Patch the module-level import in init.py (imported at line 27)
    monkeypatch.setattr("codeweaver.cli.commands.init.Confirm", mock)
    # Also patch the base location to catch any other imports
    monkeypatch.setattr("rich.prompt.Confirm", mock)

    return mock
```

### File: `/home/knitli/codeweaver-mcp/tests/integration/cli/test_init_workflows.py`
**Fixes**:
1. Removed `pytest.raises(SystemExit)` blocks from successful command executions
2. Added `--project` parameter to all `init_app.parse_args()` calls

**Example changes**:
```python
# Before (WRONG)
with pytest.raises(SystemExit) as exc_info:
    func, bound_args, _ = init_app.parse_args(
        ["--quickstart", "--client", "claude_code"], exit_on_error=False
    )
    func(**bound_args.arguments)
assert exc_info.value.code == 0 or exc_info.value.code is None

# After (CORRECT)
func, bound_args, _ = init_app.parse_args(
    ["--quickstart", "--client", "claude_code", "--project", str(project)],
    exit_on_error=False,
)
func(**bound_args.arguments)
```

## Results

**Before**: 8 failed, 2 passed
**After**: 10 passed, 0 failed ✅

### Tests Fixed:
1. ✅ `test_full_init_creates_both_configs`
2. ✅ `test_http_streaming_architecture`
3. ✅ `test_config_only_flag`
4. ✅ `test_mcp_only_flag`
5. ✅ `test_init_then_config_show`
6. ✅ `test_init_then_doctor`
7. ✅ `test_init_respects_existing_config`
8. ✅ `test_init_claude_code`
9. ✅ `test_init_claude_desktop` (was already passing)
10. ✅ `test_init_multiple_clients_sequentially` (was already passing)

## Key Learnings

1. **Mock at import location**: When mocking imported functions, patch where they're imported, not just the original module
2. **Understand framework behavior**: Cyclopts commands don't exit on success, only on error
3. **Explicit parameters in tests**: Don't rely on command defaults that use cached/global state - pass explicit parameters
4. **Test isolation**: Ensure tests don't depend on the execution environment (like current working directory) being set correctly by framework-level code

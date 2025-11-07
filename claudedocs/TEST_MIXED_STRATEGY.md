<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Mixed Testing Strategy - Direct App Calling + Subprocess

**Date**: 2025-11-06
**Goal**: Optimize test suite with best-of-both-worlds approach
**Approach**: Unit/Integration tests use direct app calling, E2E tests use subprocess

---

## Testing Philosophy

### Three-Tier Testing Strategy

**Unit Tests** → Direct app calling (Fast, mockable, debuggable)
**Integration Tests** → Direct app calling (Component interaction, still in-process)
**E2E Tests** → Subprocess (Full CLI workflow, user experience)

---

## Pattern 1: Direct App Calling (Unit/Integration)

### Benefits
- ✅ **10-100x faster** - No subprocess overhead
- ✅ **Better debugging** - In-process stack traces
- ✅ **Rich assertions** - Check return values, mock internals
- ✅ **Easy mocking** - Use pytest-mock for dependencies

### Pattern Implementation

```python
from pypi_checker import app  # Import the app directly
import pytest

def test_command_with_return_value(capsys):
    """Test using direct app call with return value."""
    # Call app directly with result_action="return_value"
    result = app("arg1", "--flag", result_action="return_value")

    # Assert return value directly
    assert result is True

    # Check stdout using capsys
    captured = capsys.readouterr()
    assert "expected output" in captured.out

def test_command_with_sys_exit(capsys):
    """Test using direct app call that exits."""
    # Without result_action, app calls sys.exit()
    with pytest.raises(SystemExit) as exc_info:
        app("arg1", "--flag")

    # Check exit code
    assert exc_info.value.code == 0

    # Check stdout
    captured = capsys.readouterr()
    assert "success" in captured.out

def test_command_with_mocking(capsys, mocker):
    """Test with internal function mocking."""
    # Mock internal function
    mock_func = mocker.patch("module.internal_function")
    mock_func.return_value = {"status": "success"}

    # Call app
    result = app("arg1", result_action="return_value")

    # Verify mock was called correctly
    mock_func.assert_called_once_with("arg1")

    # Check result
    assert result == {"status": "success"}
```

### Key Concepts

**result_action Parameter**:
- `result_action="return_value"` - Returns value directly (no sys.exit)
- `result_action=None` (default) - Calls sys.exit() with appropriate code

**Exit Code Mapping**:
- `True` → exit code 0 (success)
- `False` → exit code 1 (failure)
- `None` → exit code 0
- Integer → exit code as-is

**Output Capture**:
- Use `capsys.readouterr()` to capture stdout/stderr
- `.out` for normal output (console)
- `.err` for error output (error_console)

---

## Pattern 2: Subprocess (E2E Only)

### When to Use
- ✅ Testing actual CLI entry point (`python -m codeweaver.cli`)
- ✅ Testing environment variable handling
- ✅ Testing cwd behavior and file system interaction
- ✅ Simulating real user workflows

### Pattern Implementation

```python
import subprocess
import sys
from pathlib import Path

def test_full_user_workflow(tmp_path):
    """E2E test using subprocess."""
    # Run actual CLI command
    result = subprocess.run(
        [sys.executable, "-m", "codeweaver.cli", "init", "--quick"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        input="\n" * 10,  # Provide input for prompts
        timeout=30,
    )

    # Assert exit code
    assert result.returncode == 0

    # Assert stdout
    assert "success" in result.stdout

    # Assert files created
    assert (tmp_path / "codeweaver.toml").exists()
```

---

## File-by-File Conversion Plan

### Unit Tests (Direct App Calling)

#### test_config_command.py (16 tests)
**Commands to import**: `from codeweaver.cli.commands.config import app as config_app`

**Example conversion**:
```python
# BEFORE (subprocess)
def test_quick_flag_creates_config(temp_project, cli_runner):
    result = cli_runner("config", "init", "--quick", cwd=temp_project)
    assert result.returncode == 0
    assert (temp_project / "codeweaver.toml").exists()

# AFTER (direct calling)
def test_quick_flag_creates_config(temp_project, capsys, monkeypatch):
    monkeypatch.chdir(temp_project)
    result = config_app.parse_args(["init", "--quick"])
    assert result is None or result == 0  # Success
    assert (temp_project / "codeweaver.toml").exists()
```

#### test_doctor_command.py (3 tests)
**Commands to import**: `from codeweaver.cli.commands.doctor import app as doctor_app`

```python
# AFTER (direct calling)
def test_doctor_checks_environment(capsys, monkeypatch):
    result = doctor_app(result_action="return_value")
    captured = capsys.readouterr()
    assert "Checking environment" in captured.out
```

#### test_init_command.py (22 tests)
**Commands to import**: `from codeweaver.cli.commands.init import app as init_app`

```python
# AFTER (direct calling with prompts)
def test_init_interactive_prompts(temp_project, capsys, monkeypatch):
    monkeypatch.chdir(temp_project)
    # Mock user input
    monkeypatch.setattr('builtins.input', lambda _: 'y')

    result = init_app(result_action="return_value")
    assert (temp_project / "codeweaver.toml").exists()
```

#### test_list_command.py (18 tests)
**Commands to import**: `from codeweaver.cli.commands.list import app as list_app`

```python
# AFTER (direct calling with subcommands)
def test_list_providers_embedding(capsys):
    result = list_app.parse_args(["providers", "--kind", "embedding"])
    captured = capsys.readouterr()
    assert "voyage" in captured.out.lower()
```

#### test_cli_helpers.py (2 tests)
**Direct function imports**: Import and test helper functions directly

```python
from codeweaver.cli.utils.helpers import some_helper

def test_helper_function():
    result = some_helper("input")
    assert result == "expected"
```

### Integration Tests (Direct App Calling)

#### test_init_workflows.py (10 tests)
**Multi-step workflows with direct calling**

```python
def test_full_init_workflow(temp_project, capsys, monkeypatch):
    monkeypatch.chdir(temp_project)

    # Step 1: Create config
    result1 = init_app("--config-only", "--quick", result_action="return_value")
    assert (temp_project / "codeweaver.toml").exists()

    # Step 2: Create MCP config
    result2 = init_app("--mcp-only", result_action="return_value")
    # Verify MCP config
```

### E2E Tests (Keep Subprocess)

#### test_user_journeys.py (12 tests) ✅ NO CHANGES
**Keep subprocess approach** - These test full user workflows

---

## Updated conftest.py Patterns

### Add Direct App Calling Fixtures

```python
@pytest.fixture
def mock_console(monkeypatch):
    """Mock Rich console to avoid interactive prompts."""
    from unittest.mock import MagicMock
    mock = MagicMock()
    monkeypatch.setattr("rich.console.Console", lambda: mock)
    return mock

@pytest.fixture
def mock_prompt(monkeypatch):
    """Mock Rich prompts for testing interactive commands."""
    from unittest.mock import MagicMock
    mock = MagicMock()
    mock.ask.return_value = "default_answer"
    monkeypatch.setattr("rich.prompt.Prompt", mock)
    return mock

@pytest.fixture
def mock_confirm(monkeypatch):
    """Mock Rich confirm for yes/no prompts."""
    from unittest.mock import MagicMock
    mock = MagicMock()
    mock.ask.return_value = True
    monkeypatch.setattr("rich.prompt.Confirm", mock)
    return mock
```

### Keep cli_runner for E2E Tests

```python
@pytest.fixture
def cli_runner():
    """Fixture for E2E tests using subprocess."""
    # ... existing implementation ...
```

---

## Testing Checklist

### For Each Unit Test Conversion:
- [ ] Import app directly from command module
- [ ] Replace `cli_runner()` with direct `app()` call
- [ ] Add `result_action="return_value"` if checking return value
- [ ] Use `with pytest.raises(SystemExit)` if testing exit behavior
- [ ] Add `capsys` fixture for stdout/stderr assertions
- [ ] Change `result.returncode` → `exc_info.value.code` (for exit tests)
- [ ] Change `result.stdout` → `capsys.readouterr().out`
- [ ] Add `monkeypatch.chdir()` if test needs specific directory

### For Each Integration Test Conversion:
- [ ] Same as unit test checklist
- [ ] Verify multi-step workflows still work in-process
- [ ] Check file system state between steps

### For E2E Tests:
- [ ] Keep subprocess approach unchanged
- [ ] Verify they still test full CLI entry point

---

## Validation Criteria

### Performance Improvement
- Unit tests should run <1s total (vs ~10-30s with subprocess)
- Integration tests should run <5s total
- E2E tests will still take ~10-30s (subprocess overhead)

### Test Coverage
- All 83 tests should pass
- No loss of coverage from conversion
- Better debugging experience for unit/integration tests
- Full CLI validation maintained in E2E tests

### Quality Standards
- Clear separation: Unit (fast) vs E2E (comprehensive)
- Easy to understand which pattern to use for new tests
- Better error messages and stack traces for unit tests

---

## Execution Plan

### Phase 1: Setup (30 min)
1. Update conftest.py with new fixtures
2. Document patterns in this file
3. Create example conversions

### Phase 2: Unit Tests (2-3 hours)
**Parallel execution with 3 agents:**
- Agent 1: test_config_command.py (16 tests)
- Agent 2: test_doctor_command.py (3) + test_cli_helpers.py (2)
- Agent 3: test_init_command.py (22) + test_list_command.py (18)

### Phase 3: Integration Tests (1 hour)
**Single agent:**
- Agent 4: test_init_workflows.py (10 tests)

### Phase 4: Validation (30 min)
- Run full test suite
- Verify performance improvements
- Check test output quality

**Total Estimated Time**: 4-5 hours

---

## Benefits Summary

### Unit Tests (61 tests)
- **Speed**: 10-100x faster execution
- **Debugging**: In-process stack traces
- **Assertions**: Direct return value checking
- **Mocking**: Easy internal function mocking

### Integration Tests (10 tests)
- **Speed**: Faster than subprocess
- **Workflow Testing**: Multi-step component interaction
- **Maintainability**: Easier to debug than subprocess

### E2E Tests (12 tests)
- **Authenticity**: Tests actual CLI entry point
- **Confidence**: Validates real user experience
- **Coverage**: Catches subprocess-specific issues

---

**End of Strategy**

<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Test Rewrite Strategy

**Date**: 2025-11-06
**Goal**: Fix cyclopts.testing import errors in all CLI test files
**Approach**: Rewrite using subprocess + pytest fixtures

---

## Test Files to Fix

### Unit Tests (5 files)
1. `tests/unit/cli/test_config_command.py` (~298 lines, 25 tests)
2. `tests/unit/cli/test_doctor_command.py` (~367 lines, 30 tests)
3. `tests/unit/cli/test_init_command.py` (~285 lines, 22 tests)
4. `tests/unit/cli/test_list_command.py` (~220 lines, 18 tests)
5. `tests/unit/cli/test_cli_helpers.py` (~180 lines, 15 tests)

### Integration Tests (1 file)
6. `tests/integration/cli/test_init_workflows.py` (~404 lines, 15 tests)

**Total**: 6 files, ~1,754 lines, 125 tests

---

## Rewrite Strategy

### Pattern 1: Subprocess for CLI Invocation (E2E Style)

**Use for**: Commands that need full CLI behavior

```python
import subprocess
import sys
from pathlib import Path

def run_cli(*args, cwd=None, input_text=None):
    """Helper to run codeweaver CLI and capture output."""
    result = subprocess.run(
        [sys.executable, "-m", "codeweaver.cli"] + list(args),
        cwd=cwd or Path.cwd(),
        capture_output=True,
        text=True,
        input=input_text,
        timeout=30,
    )
    return result

def test_init_quick_flag(tmp_path):
    """Test --quick flag creates config."""
    result = run_cli("init", "--quick", cwd=tmp_path, input_text="\n" * 10)
    assert result.returncode == 0
    assert (tmp_path / "codeweaver.toml").exists()
```

### Pattern 2: Direct Function Calls (Unit Style)

**Use for**: Testing specific functions/logic without CLI layer

```python
from unittest.mock import patch, MagicMock
from codeweaver.cli.commands.config import _validate_project_path

def test_validate_project_path_exists(tmp_path):
    """Test path validation for existing directory."""
    result = _validate_project_path(tmp_path)
    assert result == tmp_path

def test_validate_project_path_missing(tmp_path):
    """Test path validation for non-existent directory."""
    with pytest.raises(FileNotFoundError):
        _validate_project_path(tmp_path / "nonexistent")
```

### Pattern 3: Mixed Approach (Integration Style)

**Use for**: Multi-step workflows

```python
def test_full_init_workflow(tmp_path):
    """Test complete init workflow: config + MCP setup."""
    # Step 1: Create config
    result1 = run_cli("init", "--config-only", "--quick", cwd=tmp_path)
    assert result1.returncode == 0

    # Step 2: Verify config
    config_path = tmp_path / "codeweaver.toml"
    assert config_path.exists()

    # Step 3: Create MCP config
    result2 = run_cli("init", "--mcp-only", cwd=tmp_path)
    assert result2.returncode == 0
```

---

## Common Fixtures

### Create Shared Fixtures File

**Location**: `tests/conftest.py` (add to existing)

```python
import subprocess
import sys
from pathlib import Path
import pytest

@pytest.fixture
def cli_runner():
    """Fixture for running CLI commands."""
    def _run(*args, cwd=None, input_text=None, check=False):
        result = subprocess.run(
            [sys.executable, "-m", "codeweaver.cli"] + list(args),
            cwd=cwd or Path.cwd(),
            capture_output=True,
            text=True,
            input=input_text,
            timeout=30,
        )
        if check and result.returncode != 0:
            raise RuntimeError(f"CLI failed: {result.stderr}")
        return result
    return _run

@pytest.fixture
def mock_console():
    """Fixture for mocking Rich console."""
    from unittest.mock import MagicMock
    return MagicMock()

@pytest.fixture
def mock_prompt():
    """Fixture for mocking user prompts."""
    from unittest.mock import patch
    with patch('rich.prompt.Prompt.ask') as mock:
        yield mock

@pytest.fixture
def isolated_project(tmp_path):
    """Fixture for isolated project directory."""
    project = tmp_path / "test-project"
    project.mkdir()
    return project
```

---

## Parallel Execution Plan

### Batch 1: Unit Tests (3 agents in parallel)

**Agent 1**: Rewrite `test_config_command.py`
- Focus on subprocess pattern for CLI tests
- Direct calls for validation functions
- Use cli_runner fixture

**Agent 2**: Rewrite `test_doctor_command.py` + `test_cli_helpers.py`
- Subprocess for full command tests
- Direct calls for check functions
- Mock providers where needed

**Agent 3**: Rewrite `test_init_command.py` + `test_list_command.py`
- Subprocess for CLI tests
- Direct calls for helper functions
- Test MCP config generation

### Batch 2: Integration Tests (1 agent)

**Agent 4**: Rewrite `test_init_workflows.py`
- Multi-step subprocess workflows
- Verify file system state between steps
- Test error recovery

---

## Test Categories

### Must Preserve

All existing test scenarios must be preserved:
- ✅ Quick setup workflows
- ✅ Interactive prompts (mock or provide input)
- ✅ Registry integration
- ✅ Provider validation
- ✅ Error handling
- ✅ Config file generation
- ✅ MCP config generation
- ✅ Git detection

### Can Simplify

Some test implementations can be simplified:
- Remove complex CliRunner mocking
- Use actual subprocess instead of mocking CLI layer
- Simpler assertions on file contents

---

## Implementation Order

1. **Add fixtures to conftest.py** (5 minutes)
2. **Batch 1 - Parallel rewrite** (3 agents, 30-45 min each)
3. **Batch 2 - Integration tests** (1 agent, 45-60 min)
4. **Run tests and fix issues** (30-60 min)
5. **Add regression tests** (30 min)

**Total Estimated Time**: 2.5-3.5 hours

---

## Validation Criteria

Tests must:
- ✅ Run without import errors
- ✅ Preserve all original test scenarios
- ✅ Pass with current implementation
- ✅ Use proper fixtures and patterns
- ✅ Have clear, descriptive test names
- ✅ Include docstrings

---

## Next Steps

1. Add shared fixtures to `tests/conftest.py`
2. Launch 3 parallel task agents for Batch 1
3. Launch 1 task agent for Batch 2
4. Run test suite and validate
5. Add regression tests for new fixes

---

**End of Strategy**

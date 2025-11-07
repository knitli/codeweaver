<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CLI Validation Report

**Date**: 2025-11-06
**Status**: ❌ Critical Issues Found
**Previous Work**: CLI_CORRECTIONS_PLAN.md implementation (3 phases completed)

## Executive Summary

Validation testing revealed **3 critical implementation issues** that block basic CLI functionality:

1. **Test Import Error**: All tests fail with `ModuleNotFoundError: No module named 'cyclopts.testing'`
2. **Git Requirement**: Commands fail outside git repositories with "No .git directory found"
3. **Command Routing**: List command subcommands not properly accessible

**Impact**: None of the implemented corrections can be validated until these issues are fixed.

---

## Critical Issues

### Issue 1: Test Import Error ❌ BLOCKING

**Severity**: Critical
**Files Affected**: All 16 test files
**Impact**: Entire test suite cannot run

**Error**:
```
ModuleNotFoundError: No module named 'cyclopts.testing'
```

**Root Cause**: Tests were written assuming Cyclopts provides a `testing` module like Click or Typer, but it doesn't.

**Affected Test Files**:
- `tests/unit/cli/test_config_command.py` (line 23)
- `tests/unit/cli/test_doctor_command.py` (line 22)
- `tests/unit/cli/test_init_command.py` (line 22)
- `tests/unit/cli/test_list_command.py` (line 18)
- `tests/integration/cli/test_init_workflows.py` (line 22)
- All other CLI test files

**Example Problematic Code**:
```python
# Line 23 in multiple test files
from cyclopts.testing import CliRunner  # ❌ Module doesn't exist
```

**Solution Required**:
Cyclopts doesn't provide testing utilities. Tests must use one of:
1. **subprocess**: Invoke CLI via subprocess and check stdout/stderr
2. **Direct function calls**: Import and call command functions directly
3. **pytest capsys**: Capture stdout/stderr from direct calls

**Recommended Fix**:
```python
# Option 1: subprocess approach
import subprocess

def test_quick_flag_creates_config(tmp_path):
    result = subprocess.run(
        ["codeweaver", "init", "--quick"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert (tmp_path / "codeweaver.toml").exists()

# Option 2: Direct function call approach
from codeweaver.cli.commands.init import init
import sys
from io import StringIO

def test_quick_flag_creates_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sys.argv = ["codeweaver", "init", "--quick"]

    # Capture output
    captured_output = StringIO()
    monkeypatch.setattr('sys.stdout', captured_output)

    init(quick=True, config_only=True, mcp_only=False, client="claude_code")

    assert (tmp_path / "codeweaver.toml").exists()
```

---

### Issue 2: Git Requirement ❌ BLOCKING

**Severity**: Critical
**Files Affected**: `doctor.py`, `config.py`, `init.py`
**Impact**: Commands fail when run outside git repositories

**Error**:
```bash
$ cd /tmp/test-codeweaver && codeweaver init --quick
CodeWeaver Fatal error: No .git directory found in the path hierarchy.
```

**Root Cause**: `get_project_path()` in `common/utils/git.py` raises `FileNotFoundError` when no git repo found (line 78-79):

```python
def _walk_up_to_git_root(path: Path | None = None) -> Path:
    path = path or Path.cwd()
    # ... walk up directories ...
    msg = "No .git directory found in the path hierarchy."
    raise FileNotFoundError(msg)  # ❌ Always raises if no git
```

**Problematic Usage in Commands**:

**doctor.py** (line 182):
```python
default_path = (
    settings.project_path
    if not isinstance(settings.project_path, Unset)
    else get_project_path()  # ❌ Raises if no git
)
```

**config.py** (lines 211, 674, 728):
```python
# Line 211
default_path = str(get_project_path())  # ❌ Raises if no git

# Line 674
default_path = get_project_path()  # ❌ Raises if no git

# Line 728
default_path = get_project_path()  # ❌ Raises if no git
```

**Impact on User Workflows**:
- ❌ Cannot run `codeweaver init --quick` to create config outside git repo
- ❌ Cannot run `codeweaver doctor` to diagnose issues outside git repo
- ❌ Cannot use CodeWeaver for non-git projects

**Solution Required**:
Make git requirement **optional** with graceful fallback to `Path.cwd()`:

```python
# Option 1: Modify get_project_path() to return cwd as fallback
def get_project_path(root_path: Path | None = None) -> Path:
    """Get the root directory of the project.

    Falls back to current working directory if not in a git repository.
    """
    try:
        if (
            root_path is None
            and (git_root := try_git_rev_parse())
            and (_root_path_checks_out(git_root))
        ):
            return git_root
        return (
            root_path
            if isinstance(root_path, Path) and _root_path_checks_out(root_path)
            else _walk_up_to_git_root(root_path)
        )
    except FileNotFoundError:
        # Not in git repo, use current working directory
        return Path.cwd()

# Option 2: Commands catch FileNotFoundError
try:
    default_path = get_project_path()
except FileNotFoundError:
    default_path = Path.cwd()
```

**Recommended Approach**: Option 1 (modify `get_project_path()`) because:
- Fixes issue in one place vs fixing in every command
- Aligns with user expectation (cwd is sensible default)
- Constitutional principle: **Simplicity** - one fix vs many

---

### Issue 3: List Command Routing ⚠️ HIGH PRIORITY

**Severity**: High
**Files Affected**: `list.py`, `__main__.py`
**Impact**: List command subcommands not accessible

**Error**:
```bash
$ codeweaver list providers --kind embedding
Error: Unknown option: "--kind".

$ codeweaver list embedding
Error: Unused Tokens: ['embedding'].
```

**Expected Behavior**:
```bash
$ codeweaver list providers --kind embedding
# Should show embedding providers

$ codeweaver list embedding
# Shortcut should work
```

**Root Cause Analysis**:

**list.py** structure (lines 92-346):
```python
app = App("list", help="List available providers and models.", console=console)

@app.command
def providers(*, kind: Annotated[str | None, ...] = None) -> None:
    """List all available providers."""
    # ... implementation

@app.command
def models(provider_name: Annotated[str, ...]) -> None:
    """List available models for a specific provider."""
    # ... implementation

@app.command
def embedding() -> None:
    """List all embedding providers (shortcut)."""
    providers(kind="embedding")

@app.command
def reranking() -> None:
    """List all reranking providers (shortcut)."""
    providers(kind="reranking")
```

**__main__.py** registration (line 45-46):
```python
app.command(
    "codeweaver.cli.commands.list:main",
    name="list",
    alias="ls",
    help="List available providers, models, and more.",
)
```

**The Problem**: The main app registers `list:main`, which calls the list app's `app()`. This should work, but the error messages suggest the subcommands aren't being recognized. This might be a Cyclopts versioning issue or incorrect app nesting.

**Validation Test** (run from git repo):
```bash
cd /home/knitli/codeweaver-mcp
python3 -m codeweaver.cli.commands.list providers --kind embedding
```

If this works directly but fails through main app, it's a registration issue.

**Solution Required**:
1. Verify Cyclopts version compatibility
2. Test direct module invocation vs main app routing
3. May need to change how list app is registered in __main__.py

---

## Validation Testing Performed

### Test Environment
- **Platform**: Linux (WSL2)
- **Python**: 3.13.9
- **Working Directory**: Multiple (git repo and /tmp)
- **Cyclopts Version**: (check with `pip show cyclopts`)

### Tests Executed

1. **Test Suite Execution** ❌ FAILED
   ```bash
   pytest tests/unit/cli/ -v
   # Result: 4 import errors (cyclopts.testing)

   pytest tests/integration/cli/ -v
   # Result: 1 import error (cyclopts.testing)
   ```

2. **CLI Entry Point** ✅ PASSED
   ```bash
   codeweaver --help
   # Result: Displays help with all commands listed
   ```

3. **Init Command** ❌ FAILED
   ```bash
   cd /tmp/test-codeweaver && codeweaver init --quick
   # Result: Fatal error: No .git directory found
   ```

4. **Doctor Command** ❌ FAILED
   ```bash
   cd /tmp/test-codeweaver && codeweaver doctor
   # Result: Fatal error: No .git directory found
   ```

5. **List Command** ❌ FAILED
   ```bash
   codeweaver list providers --kind embedding
   # Result: Error: Unknown option: "--kind"

   codeweaver list embedding
   # Result: Error: Unused Tokens: ['embedding']
   ```

### Summary of Test Results

| Test Category | Tests Attempted | Passed | Failed | Status |
|--------------|----------------|--------|--------|--------|
| Unit Tests | 4 files | 0 | 4 | ❌ Import Error |
| Integration Tests | 1 file | 0 | 1 | ❌ Import Error |
| CLI Entry Point | 1 | 1 | 0 | ✅ Working |
| Init Command | 1 | 0 | 1 | ❌ Git Required |
| Doctor Command | 1 | 0 | 1 | ❌ Git Required |
| List Command | 2 | 0 | 2 | ❌ Routing Issue |

**Overall Status**: 1/10 tests passed (10%)

---

## Impact Assessment

### User Workflows Affected

**New User Quickstart** ❌ BROKEN
```bash
# Expected workflow
cd ~/my-project  # Non-git directory
codeweaver init --quick
codeweaver doctor
# ❌ Both commands fail with git requirement
```

**Offline Developer** ❌ BROKEN
```bash
# Expected workflow
codeweaver list providers --kind embedding
# ❌ Command routing doesn't work
```

**All Testing** ❌ BROKEN
```bash
# Expected workflow
pytest tests/unit/cli/
# ❌ All tests fail with import error
```

### Constitutional Compliance Check

**Evidence-Based Development** ❌ VIOLATED
- Tests were written without verifying Cyclopts testing APIs exist
- Git requirement added without testing outside git repos
- No validation testing performed during implementation

**Proven Patterns** ⚠️ PARTIAL
- Using Cyclopts is proven ✅
- But implementation doesn't follow Cyclopts patterns ❌

**Simplicity** ❌ VIOLATED
- Complex command structure that doesn't work simply
- Git requirement adds unnecessary constraint
- Tests require non-existent module

---

## Required Corrections

### Priority 1: Fix Git Requirement (CRITICAL)

**File**: `src/codeweaver/common/utils/git.py`
**Function**: `get_project_path()`
**Change**: Add fallback to `Path.cwd()` when not in git repo

```python
def get_project_path(root_path: Path | None = None) -> Path:
    """Get the root directory of the project.

    Falls back to current working directory if not in a git repository.
    """
    try:
        if (
            root_path is None
            and (git_root := try_git_rev_parse())
            and (_root_path_checks_out(git_root))
        ):
            return git_root
        return (
            root_path
            if isinstance(root_path, Path) and _root_path_checks_out(root_path)
            else _walk_up_to_git_root(root_path)
        )
    except FileNotFoundError:
        # Not in a git repository, fall back to current working directory
        return Path.cwd()
```

**Validation**:
```bash
cd /tmp/test-dir
codeweaver init --quick  # Should work now
codeweaver doctor         # Should work now
```

---

### Priority 2: Fix Test Import Issues (CRITICAL)

**Files**: All 16 test files
**Change**: Replace `cyclopts.testing.CliRunner` with subprocess or direct calls

**Approach A: subprocess** (Recommended for E2E tests)
```python
import subprocess
from pathlib import Path

def test_quick_flag_creates_config(tmp_path):
    """Test --quick flag creates config with recommended defaults."""
    result = subprocess.run(
        ["codeweaver", "init", "--quick"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Configuration created" in result.stdout
    assert (tmp_path / "codeweaver.toml").exists()

    # Validate config content
    import tomli
    config = tomli.loads((tmp_path / "codeweaver.toml").read_text())
    assert config["embedding"]["provider"] == "voyage"
    assert config["vector_store"]["type"] == "qdrant"
```

**Approach B: Direct calls** (Recommended for unit tests)
```python
from codeweaver.cli.commands.config import init_config
from codeweaver.config.settings import CodeWeaverSettings
import sys
from pathlib import Path

def test_registry_integration(tmp_path, monkeypatch):
    """Test config command uses ProviderRegistry correctly."""
    monkeypatch.chdir(tmp_path)

    # Mock user input for interactive prompts
    from unittest.mock import patch
    with patch('rich.prompt.Prompt.ask', side_effect=["1", "1", "y"]):
        with patch('rich.prompt.Confirm.ask', return_value=True):
            init_config(
                quick=False,
                profile=None,
                user=False,
                local=True,
            )

    # Verify config created
    assert (tmp_path / "codeweaver.toml").exists()
```

**Validation**:
```bash
pytest tests/unit/cli/test_config_command.py::test_quick_flag_creates_config -v
# Should pass now
```

---

### Priority 3: Fix List Command Routing (HIGH)

**Investigation Steps**:
1. Test direct module invocation:
   ```bash
   python3 -m codeweaver.cli.commands.list providers --kind embedding
   ```

2. If direct invocation works, issue is in __main__.py registration

3. Check Cyclopts version:
   ```bash
   pip show cyclopts
   ```

4. Review Cyclopts docs for nested app registration

**Potential Fix** (if registration is the issue):
```python
# __main__.py - Instead of string import
from codeweaver.cli.commands import list as list_cmd

app.meta.add_command(list_cmd.app)  # Add the app, not just main function
```

---

## Recommendations

### Immediate Actions

1. **Fix git requirement** (15 minutes)
   - Modify `get_project_path()` to fallback to `Path.cwd()`
   - Test commands outside git repos

2. **Fix test imports** (2-4 hours)
   - Rewrite all 16 test files to use subprocess or direct calls
   - Create helper fixtures for common test patterns
   - Update CLI_TESTS_README.md with new patterns

3. **Fix list command routing** (1-2 hours)
   - Investigate Cyclopts nested app behavior
   - Test direct module invocation
   - Fix __main__.py registration if needed

### Process Improvements

**Evidence-Based Development**:
- ✅ Always verify external APIs exist before using them
- ✅ Test CLI commands outside development environment (non-git dirs)
- ✅ Run validation tests immediately after implementation

**Testing Standards**:
- ✅ Create test helpers/fixtures for common CLI testing patterns
- ✅ Use subprocess for E2E tests (actual CLI invocation)
- ✅ Use direct calls for unit tests (faster, easier mocking)
- ✅ Always test in multiple environments (git repo, tmp dir, different cwd)

**Constitutional Compliance**:
- ✅ Simplicity: Minimize assumptions (git repo requirement)
- ✅ Proven Patterns: Verify patterns work before implementing
- ✅ Evidence-Based: Test everything, assume nothing

---

## Next Steps

1. **Create fixing task plan** (use TodoWrite)
2. **Implement fixes** (use task agents if beneficial)
3. **Validate fixes** (run comprehensive test suite)
4. **Update documentation** (reflect actual working behavior)

---

## Appendix: Environment Details

```bash
# Python Version
python3 --version
# Python 3.13.9

# Cyclopts Version
pip show cyclopts
# (need to check)

# CodeWeaver Installation
pip show codeweaver
# (development mode)

# Git Status
git status
# On branch 003-our-aim-to
# Modified files: coverage.xml, validate-lazy-imports.py
```

---

**End of Validation Report**

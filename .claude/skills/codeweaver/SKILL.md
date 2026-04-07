```markdown
# codeweaver Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill teaches the core development patterns, coding conventions, and common workflows for contributing to the `codeweaver` Python codebase. It covers dependency management, import guarding for optional dependencies, workspace formatting, and test suite expansion, with practical examples and step-by-step instructions for each workflow. The repository is Python-based, with no framework detected, and emphasizes maintainable, robust dependency handling and test-driven development.

## Coding Conventions

- **File Naming:**  
  Use `camelCase` for file names.  
  _Example:_  
  ```
  src/codeweaver/providers/config/clients/multi.py
  ```

- **Import Style:**  
  Use relative imports within packages.  
  _Example:_  
  ```python
  from .baseClient import BaseClient
  ```

- **Export Style:**  
  Use default exports (i.e., expose main classes/functions by default).  
  _Example:_  
  ```python
  class MultiClient:
      ...
  ```

- **Commit Messages:**  
  Freeform style, average length ~78 characters.  
  _Example:_  
  ```
  Fix lazy import guards for optional dependencies in embedding categories
  ```

## Workflows

### Dependency Group Refactor and Lock Update
**Trigger:** When reorganizing, deduplicating, or restructuring dependency groups/extras in the workspace or packages.  
**Command:** `/refactor-deps`

1. Edit `pyproject.toml` at the root and/or in `packages/*/pyproject.toml` to update dependency groups, extras, or dynamic metadata.
2. Update `uv.lock` to reflect the new dependency structure.
3. Optionally update related test markers or comments.
4. Commit all changes together.

_Example:_  
```toml
# pyproject.toml
[project.optional-dependencies]
dev = ["pytest", "mypy"]
docs = ["sphinx"]
```

### Test Suite Expansion or Regression Test Addition
**Trigger:** When adding new regression or smoke tests to verify import, dependency, or installation behavior, especially for optional dependencies.  
**Command:** `/add-regression-test`

1. Create or update test files under `tests/unit/` (e.g., `test_lazy_imports.py`, `test_install_smoke.py`) to add new checks.
2. Optionally update `pyproject.toml` to register new pytest markers or test configuration.
3. Verify tests pass locally and in CI.

_Example:_  
```python
# tests/unit/test_lazy_imports.py
def test_import_guard():
    try:
        import some_optional_dep
    except ImportError:
        assert True
```

### Optional Dependency Import Guard Fix
**Trigger:** When CI or local tests fail due to missing optional dependencies not being properly guarded in import logic.  
**Command:** `/fix-optional-imports`

1. Identify files where optional dependency imports are not properly guarded.
2. Update those files to wrap imports in `has_package` checks, `TYPE_CHECKING`, or `try/except ImportError` blocks, providing fallback types (e.g., `Any`) as needed.
3. Update `pyproject.toml` to suppress type checker warnings for intentional fallbacks.
4. Verify the test suite passes in both full and minimal dependency environments.

_Example:_  
```python
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from optional_package import OptionalType
else:
    OptionalType = Any
```

### Pyproject.toml Formatting Across Workspace
**Trigger:** When enforcing consistent formatting of `pyproject.toml` files after dependency or metadata changes.  
**Command:** `/format-pyproject`

1. Run a formatting tool (e.g., `tombi`) on `pyproject.toml` files at the root and in packages.
2. Commit the reordered/cleaned files.
3. No semantic changes should be made.

_Example:_  
```sh
tombi pyproject.toml
tombi packages/*/pyproject.toml
```

## Testing Patterns

- **Test Framework:** Unknown (likely `pytest` based on file naming and conventions).
- **Test File Pattern:** `*.test.ts` (note: Python tests are under `tests/unit/`).
- **Typical Test Location:**  
  ```
  tests/unit/test_lazy_imports.py
  tests/unit/test_install_smoke.py
  ```
- **Test Example:**  
  ```python
  def test_install_smoke():
      assert some_install_check()
  ```

## Commands

| Command             | Purpose                                                                            |
|---------------------|------------------------------------------------------------------------------------|
| /refactor-deps      | Refactor dependency groups or extras and update the lockfile.                      |
| /add-regression-test| Add new regression or smoke tests for import, dependency, or install-time behavior.|
| /fix-optional-imports| Fix import guards for optional dependencies and provide fallbacks.                |
| /format-pyproject   | Format all pyproject.toml files for consistency.                                   |
```
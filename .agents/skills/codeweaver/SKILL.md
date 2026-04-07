<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

```markdown
# codeweaver Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill teaches the development conventions and workflows used in the `codeweaver` Python codebase. The repository is organized as a monorepo with multiple packages and focuses on robust dependency management, standardized metadata, and subprocess-isolated testing. You'll learn how to maintain dependencies, format project metadata, and extend install-profile smoke tests, all while following the project's coding conventions.

## Coding Conventions

- **Language:** Python
- **Framework:** None detected
- **File Naming:** Uses snake_case for filenames.
  - Example: `code_weaver_core.py`, `tokenizer_utils.py`
- **Import Style:** Relative imports are preferred.
  - Example:
    ```python
    from .utils import parse_config
    ```
- **Export Style:** Default exports (no explicit `__all__` unless necessary).
  - Example:
    ```python
    def main():
        pass
    ```
- **Commit Patterns:** Freeform commit messages, average length ~95 characters, no strict prefixing.

## Workflows

### python-dependency-metadata-refactor

**Trigger:** When you need to restructure, deduplicate, or centralize dependency definitions and extras in the Python monorepo.

**Command:** `/refactor-deps`

1. Edit the root `pyproject.toml` to update `[project.dependencies]`, `[project.optional-dependencies]`, or `[tool.*]` sections.
2. Edit member package `pyproject.toml` files, such as:
   - `packages/codeweaver-daemon/pyproject.toml`
   - `packages/codeweaver-tokenizers/pyproject.toml`
   Synchronize or update dependency metadata as needed.
3. Update `uv.lock` to reflect new dependency resolutions.
4. Verify changes by building wheels or running dependency-related commands:
   ```bash
   python -m build
   ```
5. Optionally, add or update tests to verify import behavior or dependency isolation.

### dependency-group-maintenance

**Trigger:** When you want to add, remove, or reorganize dependency groups (e.g., 'dev', 'test', 'lint', 'build').

**Command:** `/edit-dep-groups`

1. Edit `pyproject.toml` to update `[dependency-groups]` or equivalent sections.
2. Update member package `pyproject.toml` files if group changes affect them.
3. Update `uv.lock` to reflect group changes.
4. Document or communicate the new group structure if needed.

### dependency-formatting-standardization

**Trigger:** When you want to enforce or update formatting standards for project metadata files.

**Command:** `/format-pyproject`

1. Run a formatter (e.g., `tombi`) on all `pyproject.toml` files:
   ```bash
   tombi pyproject.toml
   tombi packages/codeweaver-daemon/pyproject.toml
   tombi packages/codeweaver-tokenizers/pyproject.toml
   ```
2. Commit the reformatted files (no semantic change).

### install-profile-smoke-test-suite-extension

**Trigger:** When you want to ensure that minimal or custom installs do not import or require optional dependencies, and that public APIs are importable under all install profiles.

**Command:** `/add-install-smoke-test`

1. Add or update tests in `tests/unit/` (e.g., `test_lazy_imports.py`, `test_install_smoke.py`) to verify import behavior in subprocesses.
   - Example (pytest subprocess test):
     ```python
     import subprocess

     def test_import_minimal():
         result = subprocess.run(
             ["python", "-c", "import codeweaver"],
             capture_output=True
         )
         assert result.returncode == 0
     ```
2. Tag tests with custom pytest markers (e.g., `@pytest.mark.install_smoke`).
3. Update `pyproject.toml` if new test dependencies or markers are added.
4. Run tests locally and/or in CI to verify behavior:
   ```bash
   pytest -m install_smoke
   ```

## Testing Patterns

- **Framework:** Unknown (likely pytest based on file patterns and markers).
- **Test File Pattern:** Files named `test_*.py` (e.g., `test_lazy_imports.py`, `test_install_smoke.py`).
- **Best Practices:**
  - Use subprocesses to verify import behavior under different install profiles.
  - Tag install-profile tests with custom markers for selective running.
  - Update dependencies in `pyproject.toml` if new test requirements are introduced.

## Commands

| Command                | Purpose                                                                                 |
|------------------------|-----------------------------------------------------------------------------------------|
| /refactor-deps         | Refactor or reorganize Python project dependencies and metadata across the workspace.   |
| /edit-dep-groups       | Add, remove, or reorganize dependency groups in the project configuration.              |
| /format-pyproject      | Apply formatting tools to pyproject.toml files for consistency.                         |
| /add-install-smoke-test| Add or extend subprocess-isolated smoke/regression tests for install profiles.          |
```
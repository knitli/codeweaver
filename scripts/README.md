<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Scripts Directory

This directory contains development and build scripts for the CodeWeaver project. Scripts are organized by purpose and referenced by various build tools.

## Quick Reference

### Referenced by Build Tools

These scripts are called by project tooling (pyproject.toml, mise.toml, hk.pkl, or GitHub workflows):

- **[fix-ruff-patterns.sh](#fix-ruff-patternssh)** - Auto-fix ruff violations (TRY401, G004, TRY300)
  - Referenced in: `mise.toml`, `hk.pkl`
- **[apply_test_marks.py](#apply_test_markspy)** - Apply pytest marks to test files
  - Referenced in: `hk.pkl`
- **[update-licenses.py](#update-licensespy)** - Update REUSE license headers
  - Referenced in: `mise.toml`, `hk.pkl`
- **[install-mise.sh](#install-misesh)** - Install mise task runner
  - Referenced in: `.github/workflows/copilot-setup-steps.yml`

### Script Categories

- **[Development & Environment](#development--environment)** - Shell initialization and setup
- **[Code Quality & Linting](#code-quality--linting)** - Formatting, linting, and fixing code
- **[Testing](#testing)** - Test marking and organization
- **[Language Support](#language-support)** - Tree-sitter grammar and language mapping
- **[Documentation](#documentation)** - API docs and markdown processing
- **[Model & Data](#model--data)** - Model metadata and data conversion
- **[Utilities](#utilities)** - Analysis and debugging tools

---

## Development & Environment

### install-mise.sh

Installs or updates the mise task runner (version 2025.7.0).

**Usage:**
```bash
./scripts/install-mise.sh           # Install mise
./scripts/install-mise.sh version   # Check version
```

**Referenced in:** 
- `.github/workflows/copilot-setup-steps.yml`
- `.vscode/terminal.extra.zsh`

### dev-shell-init.zsh

Zsh initialization script for development shells. Idempotently activates the project's `.venv` and sources workspace-specific commands.

**Usage:**
- Automatically sourced by configured shells
- Manual: `source scripts/dev-shell-init.zsh`

**Features:**
- Idempotent venv activation
- Resolves repo root from multiple locations
- Only runs once per shell session

### vscode-terminal-bootstrap.sh

Launches an interactive zsh terminal with dev-shell-init pre-sourced for VS Code terminal integration.

**Usage:**
- Automatically called by VS Code terminal configuration

---

## Code Quality & Linting

### fix-ruff-patterns.sh

Main orchestration script that automatically fixes common ruff linting violations that can't be auto-fixed by ruff itself.

**Fixes:**
- **G004**: F-strings in logging calls → `%` format
- **TRY401**: Redundant exception references in `logging.exception()` calls
- **TRY300**: Return statements in try blocks → moved to else blocks

**Usage:**
```bash
# Fix patterns in current directory
./scripts/fix-ruff-patterns.sh

# Fix specific files/directories
./scripts/fix-ruff-patterns.sh src/ tests/ main.py

# Skip verification (if ruff hangs)
./scripts/fix-ruff-patterns.sh --skip-verify src/

# Dry run mode
./scripts/fix-ruff-patterns.sh --dry-run src/

# Debug mode
./scripts/fix-ruff-patterns.sh --debug src/
```

**Referenced in:** `mise.toml`, `hk.pkl`

**See also:** [ruff_fixes/README.md](ruff_fixes/README.md) for detailed architecture and examples.

### update-licenses.py

Updates REUSE-compliant license headers for files in the repository.

**Usage:**
```bash
# Add/update licenses interactively
uv run python scripts/update-licenses.py add --interactive

# Add licenses to specific files
uv run python scripts/update-licenses.py add file1.py file2.py

# Add licenses to staged git files
uv run python scripts/update-licenses.py add --staged

# Use specific contributors
uv run python scripts/update-licenses.py add --contributor "Name <email>"
```

**Referenced in:** `mise.toml`, `hk.pkl`

**Features:**
- PEP 723 inline script metadata
- Supports multiple contributors
- Filters files using rignore (respects .gitignore)
- Concurrent processing

---

## Testing

### apply_test_marks.py

Automatically applies pytest marks to test files based on their location and naming patterns.

**Usage:**
```bash
# Process all test files
./scripts/apply_test_marks.py

# Process specific test files
./scripts/apply_test_marks.py tests/unit/test_config.py

# Run tests with marks
pytest -m unit                    # Run only unit tests
pytest -m integration             # Run only integration tests
pytest -m 'not slow'              # Skip slow tests
pytest -m config                  # Configuration tests only
```

**Referenced in:** `hk.pkl`

**Mark Patterns:**
- `tests/unit/` → `@pytest.mark.unit`
- `tests/integration/` → `@pytest.mark.integration`
- `test_benchmark` → `@pytest.mark.benchmark`, `@pytest.mark.performance`
- `test_config` → `@pytest.mark.config`
- `test_telemetry` → `@pytest.mark.telemetry`
- And more...

---

## Language Support

### get_langs.py

Fetches tree-sitter grammars from their repositories and updates local grammar files.

**Usage:**
```bash
uv run scripts/get_langs.py [languages...]
```

**Features:**
- PEP 723 inline dependencies: `httpx`, `cyclopts`, `pydantic`, `rich`
- Fetches from GitHub repositories
- Updates tree-sitter grammar files

### build_language_mappings.py

Builds language mapping files from tree-sitter `node-types.json` files.

**Usage:**
```bash
uv run -s scripts/build_language_mappings.py
```

**Features:**
- PEP 723 inline dependencies: `pydantic`
- Generates language-specific mappings

### generate_supported_languages.py

Generates the list of supported languages for the build system and documentation.

**Usage:**
```bash
uv run scripts/generate_supported_languages.py
```

**Features:**
- PEP 723 inline dependencies: `black`, `textcase`
- Updates build configuration

### analyze_grammar_structure.py

Analyzes grammar structure patterns across all supported languages.

**Usage:**
```bash
./scripts/analyze_grammar_structure.py
```

### generate_delimiters.py

Generates language delimiter definitions from patterns.

**Usage:**
```bash
uv run -s scripts/generate_delimiters.py
```

**Features:**
- PEP 723 inline dependencies: `rich`

### compare_delimiters.py

Compares manually-defined delimiters with pattern-generated ones to ensure consistency.

**Usage:**
```bash
uv run -s scripts/compare_delimiters.py
```

**Features:**
- PEP 723 inline dependencies: `rich`

---

## Documentation

### gen_ref_pages.py

Generates API documentation pages and navigation for CodeWeaver. Triggered by `mkdocs-gen-files` during the documentation build process.

**Usage:**
- Automatically called by MkDocs build
- Manual: `./scripts/gen_ref_pages.py`

**Features:**
- Generates docs from source code
- Creates navigation structure
- Skips `__init__.py` and `__main__.py`

### add_plaintext_to_codeblock.py

Finds codeblocks in Markdown files with no language specified and adds 'plaintext' to them.

**Usage:**
```bash
./scripts/add_plaintext_to_codeblock.py [files...]
```

---

## Model & Data

### mteb_to_codeweaver.py

Converts MTEB (Massive Text Embedding Benchmark) model metadata to CodeWeaver embedding capabilities format.

**Usage:**
```bash
uv run -s scripts/mteb_to_codeweaver.py
```

### hf_models.json

Contains Hugging Face model metadata. Used for embedding model configuration.

**Note:** Has accompanying `.license` file for REUSE compliance.

---

## Utilities

### benchmark_detection.py

Benchmarks language family detection performance.

**Usage:**
```bash
uv run -s scripts/benchmark_detection.py
```

**Features:**
- PEP 723 inline dependencies: `rich`
- Performance profiling for language detection

### get_all_exceptions.py

Retrieves all exceptions available in the CodeWeaver codebase and all used exceptions.

**Usage:**
```bash
./scripts/get_all_exceptions.py
```

**Features:**
- Scans codebase for exception definitions
- Lists used exceptions

### check_imports.py

Simple import checker to identify missing dependencies.

**Usage:**
```bash
./scripts/check_imports.py
```

**Features:**
- Tests module imports
- Reports failed imports
- Exit code 1 if any imports fail

**Note:** Currently has empty `MODULES_TO_CHECK` tuple - add modules to check as needed.

---

## Subdirectories

### ruff_fixes/

Contains scripts and rules for fixing ruff linting violations. See [ruff_fixes/README.md](ruff_fixes/README.md) for detailed documentation.

**Contents:**
- `f_string_converter.py` - AST-based f-string to `%` format converter
- `punctuation_cleaner.py` - Smart punctuation cleanup for exception logging
- `ruff_fixer.py` - Core ruff fixing logic
- `try_return_fixer.py` - Fixes TRY300 violations
- `test_fix_patterns.py` - Tests for pattern fixing
- `rules/` - AST-grep rule definitions (10 YAML files)

---

## Script Naming Conventions

- **Python scripts**: Use `snake_case.py`
- **Shell scripts**: Use `kebab-case.sh`
- **Executable scripts**: Should have shebang and execute permission
- **PEP 723 scripts**: Use `#!/usr/bin/env -S uv run -s` for inline dependencies

## Contributing

When adding new scripts:

1. **Add appropriate license header** (use `update-licenses.py`)
2. **Include docstring** explaining purpose and usage
3. **Update this README** in the appropriate category
4. **Add to Quick Reference** if called by build tools
5. **Document CLI arguments** and examples
6. **Use PEP 723** for scripts with external dependencies

## Running Scripts

### With uv (PEP 723 scripts)

Many scripts use PEP 723 inline script metadata and should be run with `uv`:

```bash
uv run -s scripts/script_name.py
```

### Direct execution

Scripts with proper shebangs can be run directly:

```bash
./scripts/script_name.py
./scripts/script-name.sh
```

### Through mise/hk

Some scripts are designed to be called through mise or hk tasks:

```bash
mise run fix
hk fix
```

---

## Maintenance

Last Updated: 2025-10-13

For issues or questions about specific scripts, refer to inline comments or contact Adam.

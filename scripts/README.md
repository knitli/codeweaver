<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Scripts Directory

This directory contains development and build scripts for the CodeWeaver project, organized by functional area for improved discoverability and maintainability.

## Directory Organization

Scripts are organized into functional categories:

```
scripts/
├── code-quality/          # Code formatting, linting, and licensing
├── dev-env/              # Development environment setup
├── docs/                 # Documentation generation
├── language-support/     # Tree-sitter grammars and language mappings
├── model-data/          # Model metadata and data conversions
├── testing/             # Test management and benchmarking
└── utils/               # Shared utilities and debugging tools
```

## Quick Reference

### Scripts Referenced by Build Tools

These scripts are called by project tooling (pyproject.toml, mise.toml, hk.pkl, or GitHub workflows):

| Script | Purpose | Referenced By |
|--------|---------|---------------|
| **[code-quality/fix-ruff-patterns.sh](#fix-ruff-patternssh)** | Auto-fix ruff violations (TRY401, G004, TRY300) | mise.toml, hk.pkl |
| **[code-quality/update-licenses.py](#update-licensespy)** | Update REUSE license headers | mise.toml, hk.pkl |
| **[testing/apply-test-marks.py](#apply-test-markspy)** | Apply pytest marks to test files | hk.pkl |
| **[dev-env/install-mise.sh](#install-misesh)** | Install mise task runner | .github/workflows |

---

## Code Quality

### fix-ruff-patterns.sh

**Location:** `scripts/code-quality/fix-ruff-patterns.sh`

Main orchestration script that automatically fixes common ruff linting violations that can't be auto-fixed by ruff itself.

**Fixes:**
- **G004**: F-strings in logging calls → `%` format
- **TRY401**: Redundant exception references in `logging.exception()` calls
- **TRY300**: Return statements in try blocks → moved to else blocks

**Usage:**
```bash
# Fix patterns in current directory
./scripts/code-quality/fix-ruff-patterns.sh

# Fix specific files/directories
./scripts/code-quality/fix-ruff-patterns.sh src/ tests/ main.py

# Skip verification (if ruff hangs)
./scripts/code-quality/fix-ruff-patterns.sh --skip-verify src/

# Dry run mode
./scripts/code-quality/fix-ruff-patterns.sh --dry-run src/

# Debug mode
./scripts/code-quality/fix-ruff-patterns.sh --debug src/
```

**Referenced in:** `mise.toml`, `hk.pkl`

**See also:** [code-quality/ruff-fixes/README.md](code-quality/ruff-fixes/README.md) for detailed architecture and examples.

### update-licenses.py

**Location:** `scripts/code-quality/update-licenses.py`

Updates REUSE-compliant license headers for files in the repository.

**Usage:**
```bash
# Add/update licenses interactively
uv run python scripts/code-quality/update-licenses.py add --interactive

# Add licenses to specific files
uv run python scripts/code-quality/update-licenses.py add file1.py file2.py

# Add licenses to staged git files
uv run python scripts/code-quality/update-licenses.py add --staged

# Use specific contributors
uv run python scripts/code-quality/update-licenses.py add --contributor "Name <email>"
```

**Referenced in:** `mise.toml`, `hk.pkl`

**Features:**
- PEP 723 inline script metadata
- Supports multiple contributors
- Filters files using rignore (respects .gitignore)
- Concurrent processing

### ruff-fixes/

**Location:** `scripts/code-quality/ruff-fixes/`

Contains scripts and rules for fixing ruff linting violations. See [ruff-fixes/README.md](code-quality/ruff-fixes/README.md) for detailed documentation.

**Contents:**
- `f_string_converter.py` - AST-based f-string to `%` format converter
- `punctuation_cleaner.py` - Smart punctuation cleanup for exception logging
- `ruff_fixer.py` - Core ruff fixing logic
- `try_return_fixer.py` - Fixes TRY300 violations
- `test_fix_patterns.py` - Tests for pattern fixing
- `rules/` - AST-grep rule definitions (YAML files)

---

## Development Environment

### install-mise.sh

**Location:** `scripts/dev-env/install-mise.sh`

Installs or updates the mise task runner (version 2025.7.0).

**Usage:**
```bash
./scripts/dev-env/install-mise.sh           # Install mise
./scripts/dev-env/install-mise.sh version   # Check version
```

**Referenced in:** 
- `.github/workflows/copilot-setup-steps.yml`
- `.vscode/terminal.extra.zsh`

### dev-shell-init.zsh

**Location:** `scripts/dev-env/dev-shell-init.zsh`

Zsh initialization script for development shells. Idempotently activates the project's `.venv` and sources workspace-specific commands.

**Usage:**
- Automatically sourced by configured shells
- Manual: `source scripts/dev-env/dev-shell-init.zsh`

**Features:**
- Idempotent venv activation
- Resolves repo root from multiple locations
- Only runs once per shell session

### vscode-terminal-bootstrap.sh

**Location:** `scripts/dev-env/vscode-terminal-bootstrap.sh`

Launches an interactive zsh terminal with dev-shell-init pre-sourced for VS Code terminal integration.

**Usage:**
- Automatically called by VS Code terminal configuration

---

## Testing

### apply-test-marks.py

**Location:** `scripts/testing/apply-test-marks.py`

Automatically applies pytest marks to test files based on their location and naming patterns.

**Usage:**
```bash
# Process all test files
./scripts/testing/apply-test-marks.py

# Process specific test files
./scripts/testing/apply-test-marks.py tests/unit/test_config.py

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

### benchmark-detection.py

**Location:** `scripts/testing/benchmark-detection.py`

Benchmarks language family detection performance.

**Usage:**
```bash
uv run -s scripts/testing/benchmark-detection.py
```

**Features:**
- PEP 723 inline dependencies: `rich`
- Performance profiling for language detection

---

## Language Support

### download-ts-grammars.py

**Location:** `scripts/language-support/download-ts-grammars.py`

Fetches tree-sitter grammars from their repositories and updates local grammar files.

**Usage:**
```bash
uv run scripts/language-support/get-langs.py [languages...]
```

**Features:**
- PEP 723 inline dependencies: `httpx`, `cyclopts`, `pydantic`, `rich`
- Fetches from GitHub repositories
- Updates tree-sitter grammar files

### build-language-mappings.py

**Location:** `scripts/language-support/build-language-mappings.py`

Builds language mapping files from tree-sitter `node-types.json` files.

**Usage:**
```bash
uv run -s scripts/language-support/build-language-mappings.py
```

**Features:**
- PEP 723 inline dependencies: `pydantic`
- Generates language-specific mappings

### generate-supported-languages.py

**Location:** `scripts/language-support/generate-supported-languages.py`

Generates the list of supported languages for the build system and documentation.

**Usage:**
```bash
uv run scripts/language-support/generate-supported-languages.py
```

**Features:**
- PEP 723 inline dependencies: `black`, `textcase`
- Updates build configuration

### analyze-grammar-structure.py

**Location:** `scripts/language-support/analyze-grammar-structure.py`

Analyzes grammar structure patterns across all supported languages.

**Usage:**
```bash
./scripts/language-support/analyze-grammar-structure.py
```

### generate-delimiters.py

**Location:** `scripts/language-support/generate-delimiters.py`

Generates language delimiter definitions from patterns.

**Usage:**
```bash
uv run -s scripts/language-support/generate-delimiters.py
```

**Features:**
- PEP 723 inline dependencies: `rich`

### compare-delimiters.py

**Location:** `scripts/language-support/compare-delimiters.py`

Compares manually-defined delimiters with pattern-generated ones to ensure consistency.

**Usage:**
```bash
uv run -s scripts/language-support/compare-delimiters.py
```

**Features:**
- PEP 723 inline dependencies: `rich`

---

## Documentation

### gen-ref-pages.py

**Location:** `scripts/docs/gen-ref-pages.py`

Generates API documentation pages and navigation for CodeWeaver. Triggered by `mkdocs-gen-files` during the documentation build process.

**Usage:**
- Automatically called by MkDocs build
- Manual: `./scripts/docs/gen-ref-pages.py`

**Features:**
- Generates docs from source code
- Creates navigation structure
- Skips `__init__.py` and `__main__.py`

**Referenced in:** `mkdocs.yml`

### add-plaintext-to-codeblock.py

**Location:** `scripts/docs/add-plaintext-to-codeblock.py`

Finds codeblocks in Markdown files with no language specified and adds 'plaintext' to them.

**Usage:**
```bash
./scripts/docs/add-plaintext-to-codeblock.py [files...]
```

---

## Model & Data

### mteb-to-codeweaver.py

**Location:** `scripts/model-data/mteb-to-codeweaver.py`

Converts MTEB (Massive Text Embedding Benchmark) model metadata to CodeWeaver embedding capabilities format.

**Usage:**
```bash
uv run -s scripts/model-data/mteb-to-codeweaver.py
```

### hf-models.json

**Location:** `scripts/model-data/hf-models.json`

Contains Hugging Face model metadata. Used for embedding model configuration.

**Note:** Has accompanying `.license` file for REUSE compliance.

---

## Utilities

### ansi-color-tests.py

**Location:** `scripts/utils/ansi-color-tests.py`

Shared color definitions for script output formatting.

### check-imports.py

**Location:** `scripts/utils/check-imports.py`

Simple import checker to identify missing dependencies.

**Usage:**
```bash
./scripts/utils/check-imports.py
```

**Features:**
- Tests module imports
- Reports failed imports
- Exit code 1 if any imports fail

**Note:** Currently has empty `MODULES_TO_CHECK` tuple - add modules to check as needed.

### get-all-exceptions.py

**Location:** `scripts/utils/get-all-exceptions.py`

Retrieves all exceptions available in the CodeWeaver codebase and all used exceptions.

**Usage:**
```bash
./scripts/utils/get-all-exceptions.py
```

**Features:**
- Scans codebase for exception definitions
- Lists used exceptions

### lazy-import-demo.py

**Location:** `scripts/utils/lazy-import-demo.py`

Demonstrates the new LazyImport functionality for deferred module loading. Shows how the LazyImport class solves problems with the old lazy_importer pattern.

**Usage:**
```bash
python scripts/utils/lazy-import-demo.py
```

**Features:**
- Demonstrates basic lazy import patterns
- Shows attribute chaining without import
- Examples for settings and type patterns
- Thread safety demonstration
- Comparison with old implementation

**See also:** [utils/LAZY_IMPORT_GUIDE.md](utils/LAZY_IMPORT_GUIDE.md) for complete usage guide and migration instructions.

### LAZY_IMPORT_GUIDE.md

**Location:** `scripts/utils/LAZY_IMPORT_GUIDE.md`

Complete usage guide for the new LazyImport class in `src/codeweaver/common/utils/lazy_importer.py`.

**Contents:**
- Quick reference and basic usage
- Solution to specific use cases (settings functions, TYPE_CHECKING patterns)
- Advanced patterns (chaining, global-level usage)
- Comparison with old lazy_importer
- Migration guide
- Best practices and performance considerations

---

## Script Naming Conventions

- **Python scripts**: Use `kebab-case.py` for executables
- **Shell scripts**: Use `kebab-case.sh`
- **Directories**: Use `kebab-case/`
- **Executable scripts**: Should have shebang and execute permission
- **PEP 723 scripts**: Use `#!/usr/bin/env -S uv run -s` for inline dependencies

## Contributing

When adding new scripts:

1. **Choose the appropriate category directory** based on the script's primary purpose
2. **Add appropriate license header** (use `update-licenses.py` or copy/paste from another file)
3. **Include docstring** explaining purpose and usage
4. **Update this README** in the appropriate category section
5. **Add to Quick Reference** if called by build tools
6. **Document CLI arguments** and examples
7. **Use PEP 723** for scripts with external dependencies
8. **Follow naming conventions** (kebab-case for executable scripts)
9. **Add a `mise run` alias (task) definition to `mise.toml` using the filename as the name of the task (e.g. the task for `language-support/generate-delimiters.py` is `mise run generate-delimiters`)

## Running Scripts

### Primary -- Through Mise Alias/Task

All scripts have a corresponding mise task matching the name of the file without its extension. This is the primary way to run them -- removing any thoughts about what tool to use and how to call it.

### With uv (PEP 723 scripts)

Many scripts use PEP 723 inline script metadata and should be run with `uv`:

```bash
uv run -s scripts/<category>/<script-name>.py
```

### Direct execution

Scripts with proper shebangs can be run directly:

```bash
./scripts/<category>/<script-name>.py
./scripts/<category>/<script-name>.sh
```

### Through mise/hk

Some scripts are primarily intended for use in a parent mise or hk task workflow, like `mise run format-fix`:

```bash
mise run fix
hk fix
```

But **all** scripts have a mise alias (e.g. `mise run download-ts-grammars`)

---

## Organization Design

See [ORGANIZATION.md](ORGANIZATION.md) for the detailed design rationale and migration mapping.

## Maintenance

Last Updated: 2025-10-15

For issues or questions about specific scripts, refer to inline comments or contact the team.

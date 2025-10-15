<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Scripts Directory Organization System

## Design Principles

Following CodeWeaver's constitutional principles (Simplicity Through Architecture):

1. **Flat grouping**: One level of subdirectories by functional area
2. **Obvious purpose**: Directory names clearly indicate contents
3. **Minimal disruption**: Preserve build tool references with clear mappings
4. **Consistent naming**: 
   - Python scripts: `snake_case.py`
   - Shell scripts: `kebab-case.sh`
   - Directories: `kebab-case/`

## Directory Structure

```
scripts/
├── README.md                          # Main documentation
├── ORGANIZATION.md                    # This file - organization design
│
├── dev-env/                           # Development environment setup
│   ├── dev-shell-init.zsh
│   ├── install-mise.sh
│   └── vscode-terminal-bootstrap.sh
│
├── code-quality/                      # Code formatting, linting, licensing
│   ├── fix-ruff-patterns.sh
│   ├── update-licenses.py
│   └── ruff-fixes/                    # Ruff fixing implementation
│       ├── README.md
│       ├── f_string_converter.py
│       ├── punctuation_cleaner.py
│       ├── ruff_fixer.py
│       ├── try_return_fixer.py
│       ├── test_fix_patterns.py
│       └── rules/                     # AST-grep rules
│           └── *.yml
│
├── testing/                           # Test management and benchmarking
│   ├── apply-test-marks.py
│   └── benchmark-detection.py
│
├── language-support/                  # Tree-sitter and language mappings
│   ├── get-langs.py
│   ├── build-language-mappings.py
│   ├── generate-supported-languages.py
│   ├── generate-delimiters.py
│   ├── compare-delimiters.py
│   └── analyze-grammar-structure.py
│
├── docs/                              # Documentation generation
│   ├── gen-ref-pages.py
│   └── add-plaintext-to-codeblock.py
│
├── model-data/                        # Model metadata and conversions
│   ├── mteb-to-codeweaver.py
│   ├── hf-models.json
│   └── hf-models.json.license
│
├── utils/                             # Shared utilities and debugging
│   ├── colors.py
│   ├── check-imports.py
│   └── get-all-exceptions.py
│
└── [deprecated/]                      # Optional: for phased removal
```

## Category Definitions

### dev-env/
Scripts for setting up and managing development environments.
- Shell initialization
- Tool installation
- IDE/editor integration

### code-quality/
Scripts for code formatting, linting, and license management.
- Automated fixing tools
- License header management
- Linting orchestration

### testing/
Scripts for test management, marking, and benchmarking.
- Test mark application
- Performance benchmarking
- Test utilities

### language-support/
Scripts for managing tree-sitter grammars and language mappings.
- Grammar fetching/updating
- Language mapping generation
- Delimiter generation
- Grammar analysis

### docs/
Scripts for documentation generation and processing.
- API documentation generation
- Markdown processing
- Documentation utilities

### model-data/
Scripts for model metadata and data format conversions.
- MTEB conversions
- Model metadata files
- Data transformations

### utils/
Shared utilities and debugging tools.
- Common functions (colors, formatting)
- Import checking
- Exception analysis
- Other diagnostic tools

## Migration Mapping

### Files to Move

| Current Path | New Path | Referenced By |
|--------------|----------|---------------|
| `fix-ruff-patterns.sh` | `code-quality/fix-ruff-patterns.sh` | mise.toml, hk.pkl |
| `update-licenses.py` | `code-quality/update-licenses.py` | mise.toml, hk.pkl |
| `apply_test_marks.py` | `testing/apply-test-marks.py` | hk.pkl |
| `install-mise.sh` | `dev-env/install-mise.sh` | .github/workflows |
| `dev-shell-init.zsh` | `dev-env/dev-shell-init.zsh` | .vscode config |
| `vscode-terminal-bootstrap.sh` | `dev-env/vscode-terminal-bootstrap.sh` | .vscode config |
| `gen_ref_pages.py` | `docs/gen-ref-pages.py` | mkdocs-gen-files |
| `add_plaintext_to_codeblock.py` | `docs/add-plaintext-to-codeblock.py` | - |
| `get_langs.py` | `language-support/get-langs.py` | - |
| `build_language_mappings.py` | `language-support/build-language-mappings.py` | - |
| `generate_supported_languages.py` | `language-support/generate-supported-languages.py` | - |
| `generate_delimiters.py` | `language-support/generate-delimiters.py` | - |
| `compare_delimiters.py` | `language-support/compare-delimiters.py` | - |
| `analyze_grammar_structure.py` | `language-support/analyze-grammar-structure.py` | - |
| `mteb_to_codeweaver.py` | `model-data/mteb-to-codeweaver.py` | - |
| `hf_models.json` | `model-data/hf-models.json` | - |
| `hf_models.json.license` | `model-data/hf-models.json.license` | - |
| `benchmark_detection.py` | `testing/benchmark-detection.py` | - |
| `check_imports.py` | `utils/check-imports.py` | - |
| `get_all_exceptions.py` | `utils/get-all-exceptions.py` | - |
| `_utils/colors.py` | `utils/colors.py` | ruff_fixes scripts |
| `ruff_fixes/*` | `code-quality/ruff-fixes/*` | fix-ruff-patterns.sh |

### Naming Convention Changes

To align with repository conventions (kebab-case for directories, consistency):

| Old Name | New Name | Reason |
|----------|----------|--------|
| `apply_test_marks.py` | `apply-test-marks.py` | Consistency (executable scripts use kebab-case) |
| `add_plaintext_to_codeblock.py` | `add-plaintext-to-codeblock.py` | Consistency |
| `analyze_grammar_structure.py` | `analyze-grammar-structure.py` | Consistency |
| `benchmark_detection.py` | `benchmark-detection.py` | Consistency |
| `build_language_mappings.py` | `build-language-mappings.py` | Consistency |
| `check_imports.py` | `check-imports.py` | Consistency |
| `compare_delimiters.py` | `compare-delimiters.py` | Consistency |
| `generate_delimiters.py` | `generate-delimiters.py` | Consistency |
| `generate_supported_languages.py` | `generate-supported-languages.py` | Consistency |
| `gen_ref_pages.py` | `gen-ref-pages.py` | Consistency |
| `get_all_exceptions.py` | `get-all-exceptions.py` | Consistency |
| `get_langs.py` | `get-langs.py` | Consistency |
| `mteb_to_codeweaver.py` | `mteb-to-codeweaver.py` | Consistency |
| `hf_models.json` | `hf-models.json` | Consistency |
| `hf_models.json.license` | `hf-models.json.license` | Consistency |
| `_utils/` | `utils/` | Remove leading underscore (not a private package) |
| `ruff_fixes/` | `ruff-fixes/` | Consistency with kebab-case |

**Note on naming**: While Python packages typically use snake_case, executable scripts in this repository follow kebab-case convention (as seen in existing shell scripts). This change makes all executable scripts consistent.

## Files to Update

### Configuration Files
1. **mise.toml** - Update script paths for:
   - `fix-ruff-patterns.sh`
   - `update-licenses.py`

2. **hk.pkl** - Update script paths for:
   - `fix-ruff-patterns.sh`
   - `update-licenses.py`
   - `apply_test_marks.py` → `apply-test-marks.py`

3. **.github/workflows/copilot-setup-steps.yml** - Update:
   - `install-mise.sh`

4. **mkdocs.yml** - Check if `gen_ref_pages.py` is referenced

5. **.vscode/** - Check for references to dev-env scripts

### Documentation Files
1. **scripts/README.md** - Complete rewrite to reflect new structure
2. **scripts/code-quality/ruff-fixes/README.md** - Update relative paths

### Internal Script References
1. **fix-ruff-patterns.sh** - Update paths to ruff_fixes/ scripts
2. **ruff-fixes/* scripts** - Update imports from `_utils/colors.py`

## Implementation Strategy

1. **Create directory structure** - Create all new subdirectories
2. **Move and rename files** - Use git mv to preserve history
3. **Update internal references** - Fix imports and path references within scripts
4. **Update configuration files** - Update build tool configurations
5. **Update documentation** - Rewrite README.md
6. **Verification** - Test that all referenced scripts work
7. **Cleanup** - Remove old empty directories

## Benefits

1. **Improved Discoverability**: Related scripts grouped together
2. **Clear Purpose**: Directory names indicate functionality
3. **Easier Maintenance**: Category-based organization
4. **Consistent Naming**: All scripts follow kebab-case convention
5. **Better Scaling**: Room to add more scripts without clutter
6. **Alignment with Constitution**: Follows Principle V (Simplicity Through Architecture)

## Future Considerations

- Consider adding `__init__.py` files if scripts need to be imported as modules
- May add `bin/` or `cli/` directory for user-facing command-line tools
- Could add `internal/` for scripts not meant for direct execution

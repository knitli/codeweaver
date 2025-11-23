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
   - Python executable scripts: `kebab-case.py`
   - Python modules: `snake_case.py`
   - Shell scripts: `kebab-case.sh`
   - Directories: `kebab-case/`

## Directory Structure

```
scripts/
├── README.md                          # Main documentation
├── ORGANIZATION.md                    # This file - organization design
│
├── build/                           # Packaging and background scripts (scripts run by other scripts)
│   ├── generate-supported-languages.py
│   ├── git-merge-latest-version.py
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
│   ├── download-ts-grammars.py
│   ├── build-language-mappings.py
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
│   ├── ansi-color-tests.py
│   ├── check-imports.py
│   └── get-all-exceptions.py
│
└── [deprecated/]                      # Optional: for phased removal
```

## Category Definitions

### build/
Scripts used in the packaging process or otherwise aren't directly used by devs.
- Build automation
- Git drivers/resolution

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

## Future Considerations

- May add `bin/` or `cli/` directory for user-facing command-line tools
- Could add `internal/` for scripts not meant for direct execution

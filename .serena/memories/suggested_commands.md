<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Development Commands Reference

All commands use `mise` task runner. Run commands from project root.

## Environment Setup

### First-Time Setup
```bash
mise run setup          # Complete dev environment setup
mise run sync           # Sync/install dependencies
mise run activate       # Activate virtual environment
```

### Environment Management
```bash
mise run source         # Source virtual environment
mise run venv           # Create/refresh virtual environment
mise run info           # Show project information
```

## Code Quality

### Quick Fixes (Run Before Committing)
```bash
mise run fix            # Fix all code issues (formatting + linting + patterns)
mise run fix-python     # Fix Python files (ruff format + check --fix)
mise run fix-other      # Fix non-Python files (hk fix)
```

### Quality Checks
```bash
mise run check          # Run all quality checks (hk check - includes type checking)
mise run lint           # Run linting checks (ruff check)
mise run format         # Check formatting (hk check)
mise run format-fix     # Apply formatting to all files
```

### Type Checking
```bash
# Type checking is included in `mise run check`
# Manual type checking:
uv run ty check .       # Run ty (pyright) type checker
```

## Testing

### Basic Testing
```bash
mise run test           # Run all tests
mise run test-cov       # Run tests with coverage report
mise run test-watch     # Run tests in watch mode
```

### Targeted Testing (use pytest directly)
```bash
pytest -m "unit"                    # Unit tests only
pytest -m "integration"             # Integration tests only
pytest -m "not network"             # Skip network-dependent tests
pytest -m "not external_api"        # Skip external API tests
pytest tests/specific_test.py       # Run specific test file
```

## Build and Package

```bash
mise run build          # Build package distribution
mise run clean          # Remove build artifacts
mise run ci             # Run complete CI pipeline (check+lint+format+test+build)
```

## Documentation

```bash
mise run docs-serve     # Start local documentation server (http://localhost:8000)
mise run docs-build     # Build documentation for deployment
```

## Git Workflow

### Pre-Commit
```bash
mise run pre-commit     # Run all pre-commit checks and auto-fix issues
```

**Important**: Always run `mise run fix` or `mise run pre-commit` before committing!

### Git Configuration
The project sets up git aliases automatically on `mise run enter`:
```bash
git root                # Show repository root path
```

## Dependency Management

```bash
mise run sync                   # Install/sync all dependencies
mise run update-dependencies    # Update all dependencies
mise run update                 # Update mise tools
```

## Project Information

```bash
mise run version        # Show version information (package, Python, UV)
mise run changelog      # Generate changelog from commits
```

## Specialized Scripts

### Code Quality
```bash
mise run fix-ruff-patterns      # Fix unfixable ruff patterns
mise run update-licenses        # Update license headers
mise run check-imports          # Check import statements
```

### Testing Utilities
```bash
mise run apply-test-marks       # Apply pytest markers to tests
mise run benchmark-detection    # Run benchmark detection
```

### Language Support
```bash
mise run download-ts-grammars          # Download tree-sitter grammars
mise run generate-delimiters           # Generate language delimiters
mise run generate-supported-languages  # Generate supported languages list
```

### Documentation Utilities
```bash
mise run gen-ref-pages                  # Generate API reference pages
mise run add-plaintext-to-codeblock     # Fix markdown code blocks
```

## Common Workflows

### Starting Development
```bash
cd /path/to/codeweaver-mcp
mise run activate       # Activate environment (automatic on cd if mise hook enabled)
```

### Before Committing Changes
```bash
mise run pre-commit     # Auto-fix and check everything
git add .
git commit -m "Your commit message"
```

### Running Full Quality Checks
```bash
mise run ci             # Complete CI pipeline locally
```

### Adding New Dependencies
```bash
# Edit pyproject.toml to add dependency
mise run sync           # Install new dependencies
```

### Testing Changes
```bash
mise run test           # Quick test run
mise run test-cov       # Detailed coverage report
```

## Entry Points

### MCP Server
```bash
codeweaver server --config ./codeweaver.toml
codeweaver server --project /path/to/codebase --port 9328
codeweaver server --debug
```

### CLI Search
```bash
codeweaver search "query text" --limit 5
codeweaver search "query" --intent understand
codeweaver search "query" --output-format json
```

### Configuration
```bash
codeweaver config --show
codeweaver config --project ./my-project
```

### Version Check
```bash
codeweaver --version
cw --version            # Short alias
```

## Environment Variables

Key environment variables (set in mise.toml or shell):
- `VOYAGE_API_KEY`: VoyageAI API key for embeddings/reranking
- `CODEWEAVER_PROJECT_PATH`: Default project path for indexing
- `CI`: Set to "true" in CI environments for special formatting

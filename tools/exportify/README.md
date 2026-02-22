<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Lazy Import System CLI

Command-line interface for managing lazy imports and auto-generated `__init__.py` files in CodeWeaver.

## Overview

The lazy import system provides tools to:
- Generate `__init__.py` files automatically from export manifests
- Validate that imports match exports
- Analyze export patterns across the codebase
- Migrate from old hardcoded systems to declarative YAML rules

## Commands

All commands are accessed via:
```bash
exportify <command> [options]
```

### `validate` - Validate Imports

Checks that all lazy imports are valid and consistent:
- All `lazy_import()` calls resolve to real modules
- `__all__` declarations match `_dynamic_imports`
- `TYPE_CHECKING` imports exist
- No broken imports

```bash
# Validate all imports
exportify validate

# Auto-fix issues
exportify validate --fix

# Strict mode (fail on warnings)
exportify validate --strict

# Validate specific module
exportify validate --module src/codeweaver/core
```

**Output:**
- Lists errors and warnings
- Shows file locations and line numbers
- Provides suggestions for fixes

### `generate` - Generate __init__.py Files

Analyzes the codebase and generates `__init__.py` files with proper exports:

```bash
# Generate all exports
exportify generate

# Dry run (show changes without writing)
exportify generate --dry-run

# Generate for specific module
exportify generate --module src/codeweaver/core
```

**What it generates:**
- `__all__` declarations
- `lazy_import()` calls for dynamic imports
- `TYPE_CHECKING` imports where appropriate

### `analyze` - Analyze Export Patterns

Generates statistics about exports across the codebase:

```bash
# Table format (default)
exportify analyze

# JSON output
exportify analyze --format json

# Detailed report
exportify analyze --format report
```

**Shows:**
- Export counts by module
- Propagation patterns
- Rule usage statistics
- Cache effectiveness

### `doctor` - Health Check

Runs diagnostic checks and provides actionable advice:

```bash
exportify doctor
```

**Checks:**
- Cache health and validity
- Rule configuration status
- Export conflicts
- Performance issues

**Provides:**
- Recommendations for improvements
- Warnings about potential issues
- Suggestions for optimization

### `migrate` - Migrate from Old System

Converts old hardcoded system to new YAML rules:

```bash
# Migrate with backup
exportify migrate

# Migrate without backup
exportify migrate --no-backup

# Custom output path
exportify migrate --rules-output custom/path.yaml
```

**What it does:**
- Extracts hardcoded rules from old Python script
- Converts to declarative YAML format
- Creates backup of old configuration
- Generates documentation for rules

### `status` - Show Status

Displays current system status:

```bash
# Brief status
exportify status

# Detailed information
exportify status --verbose
```

**Shows:**
- Cache statistics
- Validation status
- Rule configuration
- Recent activity

### `clear-cache` - Clear Cache

Removes all cached analysis results:

```bash
exportify clear-cache
```

**Use when:**
- Cache is corrupted
- Schema version changed
- Performance issues suspected

The cache will be automatically rebuilt on the next validation or generation run.

## Configuration

The lazy import system is configured via:
- `.codeweaver/lazy_import_rules.yaml` - Export rules
- `.codeweaver/exportify.toml` - System configuration

## Examples

### Daily Development Workflow

```bash
# After adding new code
exportify generate

# Verify everything works
exportify validate

# Check status
exportify status
```

### Debugging Missing Exports

```bash
# Generate with dry run to see what would happen
exportify generate --dry-run

# Analyze patterns to understand current state
exportify analyze

# Run health check
exportify doctor
```

### CI/CD Integration

```bash
# In CI pipeline - strict validation
exportify validate --strict

# Check if exports are up to date
exportify generate --dry-run
# (fails if files would be modified)
```

## Exit Codes

All commands use standard exit codes:
- `0` - Success
- `1` - Error or validation failure

## Implementation Status

**Current Status:** CLI interface implemented, core components are placeholders.

**Implemented:**
- All CLI commands and help text
- Output formatting with rich tables and panels
- Error handling and user feedback

**Pending:**
- Export manager implementation
- Rule engine and YAML parsing
- Propagation graph building
- Validation logic
- Auto-fixer implementation
- Migration tool

See `.specify/designs/` for implementation plans.

## Related Documentation

- [Workflows](../../../.specify/designs/lazy-import-workflows.md) - User workflows and scenarios
- [Interfaces](../../../.specify/designs/lazy-import-interfaces.md) - API contracts
- [System Design](../../../.specify/designs/lazy-import-system-redesign.md) - Architecture overview

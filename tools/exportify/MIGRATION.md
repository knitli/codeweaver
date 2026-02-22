<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Migration Tool Documentation

## Overview

The migration tool converts the legacy hardcoded lazy import validation system (in `mise-tasks/validate-lazy-imports.py`) to the new declarative YAML-based rule system.

## Purpose

The old system used hardcoded if/else logic spread across ~800 lines of Python. The new system uses:
- **Declarative YAML rules** that are easier to understand and modify
- **Priority-based evaluation** with clear conflict resolution
- **Manual overrides** for edge cases
- **Extensible architecture** that can grow with the codebase

## What Gets Migrated

### 1. Hardcoded Rules → YAML Rules

The tool extracts these patterns from the old script:

| Old Pattern | New Rule | Priority |
|------------|----------|----------|
| `name.startswith('_')` → exclude | `exclude-private-members` | 900 |
| Exception/Error suffix → propagate | `propagate-exceptions` | 800 |
| `name.isupper()` → include constants | `include-constants` | 700 |
| Type aliases detection | `include-type-aliases` | 650 |
| Public classes (CamelCase) | `include-public-classes` | 500 |
| Public functions (snake_case) | `include-public-functions` | 500 |

### 2. Module Exceptions → Overrides

The `IS_EXCEPTION` list (16+ items) becomes manual overrides:

```yaml
overrides:
  include:
    codeweaver.core.utils:
      - LazyImport
      - create_lazy_getattr
    codeweaver.providers.agent:
      - AgentProfile
      - AgentProfileSpec
```

## Usage

### Basic Migration

```bash
# Run migration (writes to .codeweaver/lazy_import_rules.yaml)
python -m codeweaver.tools.exportify.migration

# Or use dry-run mode
python -c "
from codeweaver.tools.exportify import migrate_to_yaml
from pathlib import Path

result = migrate_to_yaml(
    output_path=Path('.codeweaver/lazy_import_rules.yaml'),
    dry_run=True  # Don't write files
)

print(result.yaml_content)
"
```

### Custom Output Location

```python
from pathlib import Path
from codeweaver.tools.exportify import migrate_to_yaml

result = migrate_to_yaml(
    output_path=Path('my-custom-rules.yaml'),
    old_script=Path('mise-tasks/validate-lazy-imports.py')
)

if result.success:
    print(f"✅ Generated {len(result.rules_extracted)} rules")
else:
    print(f"❌ Errors: {result.errors}")
```

### Verification

After migration, verify equivalence:

```python
from pathlib import Path
from codeweaver.tools.exportify import verify_migration

success, errors = verify_migration(
    yaml_path=Path('.codeweaver/lazy_import_rules.yaml')
)

if success:
    print("✅ Migration verified - behavior is equivalent")
else:
    for error in errors:
        print(f"⚠️  {error}")
```

## Output Files

The migration generates two files:

### 1. `lazy_import_rules.yaml`

The main YAML configuration:

```yaml
schema_version: "1.0"

metadata:
  generated_by: migration tool
  source: mise-tasks/validate-lazy-imports.py

rules:
  - name: exclude-private-members
    priority: 900
    description: Exclude private members (starting with underscore)
    match:
      name_pattern: ^_.*
    action: exclude

  - name: propagate-exceptions
    priority: 800
    description: Propagate exception classes to root package
    match:
      name_pattern: .*Error$|.*Exception$|.*Warning$
      member_type: class
    action: include
    propagate: root

overrides:
  include:
    codeweaver.core.utils:
      - LazyImport
      - create_lazy_getattr
```

### 2. `lazy_import_rules.migration.md`

A detailed equivalence report showing:
- What rules were extracted
- How they map to old patterns
- Override conversions
- Validation notes

## Rule Priority System

Rules are evaluated in priority order (highest first):

- **900**: Exclusions (private members)
- **800**: Special propagation (exceptions)
- **700**: Constants
- **650**: Type aliases
- **500**: Default inclusion (classes, functions)

**Overrides** have implicit priority **9999** (highest).

## Behavioral Equivalence

The migration tool ensures the new system behaves identically to the old:

| Scenario | Old Behavior | New Behavior |
|----------|-------------|--------------|
| `_private_func` | Excluded by `startswith('_')` | Excluded by `exclude-private-members` rule |
| `MAX_SIZE` | Included by `isupper()` | Included by `include-constants` rule |
| `ValidationError` | Propagated to root | Propagated by `propagate-exceptions` rule |
| `LazyImport` | In `IS_EXCEPTION` list | In `overrides.include` |

## Testing the Migration

The migration includes built-in verification:

```python
from codeweaver.tools.exportify import verify_migration
from pathlib import Path

# Test with default cases
success, errors = verify_migration(
    yaml_path=Path('.codeweaver/lazy_import_rules.yaml')
)

# Test with custom cases
test_cases = [
    ("_private", "test.module", MemberType.FUNCTION),  # Should exclude
    ("MAX_SIZE", "test.config", MemberType.CONSTANT),   # Should include
    ("CustomError", "test.exceptions", MemberType.CLASS), # Should propagate
]

success, errors = verify_migration(
    yaml_path=Path('.codeweaver/lazy_import_rules.yaml'),
    test_cases=test_cases
)
```

## Troubleshooting

### "Old script not found"

The migration tool looks for `mise-tasks/validate-lazy-imports.py`. If you've moved it:

```python
from pathlib import Path
from codeweaver.tools.exportify import migrate_to_yaml

result = migrate_to_yaml(
    old_script=Path('path/to/old-script.py')
)
```

### "Migration failed with errors"

Check `result.errors`:

```python
result = migrate_to_yaml(...)

if not result.success:
    print("Errors:")
    for error in result.errors:
        print(f"  - {error}")
```

### "Verification failed"

The verification compares behavior. If it fails, review the errors:

```python
success, errors = verify_migration(...)

if not success:
    for error in errors:
        print(f"⚠️  {error}")
    # Review and adjust rules manually
```

## Next Steps After Migration

1. **Review the generated YAML**: Check `.codeweaver/lazy_import_rules.yaml`
2. **Read the report**: Review `.codeweaver/lazy_import_rules.migration.md`
3. **Run verification**: Ensure behavioral equivalence
4. **Test with your codebase**: Run the new system
5. **Customize rules**: Add project-specific rules as needed

## Integration with CLI

Once the CLI is implemented, you'll be able to:

```bash
# Run migration
exportify migrate

# Dry run (preview only)
exportify migrate --dry-run

# Custom output
exportify migrate --output custom-rules.yaml

# Verify migration
exportify verify-migration
```

## Architecture

The migration tool consists of:

- **`RuleMigrator`**: Main migration class
  - `_extract_hardcoded_rules()`: Analyzes old script
  - `_extract_module_exceptions()`: Converts exception list
  - `_generate_yaml()`: Creates YAML output
  - `_generate_equivalence_report()`: Creates documentation

- **`migrate_to_yaml()`**: Main entry point
- **`verify_migration()`**: Verification function
- **`cli_migrate()`**: CLI integration point

## Future Enhancements

Potential improvements:

1. **Auto-detection of custom patterns** in old script
2. **Rule optimization** (merge similar rules)
3. **A/B testing** (run both systems in parallel)
4. **Migration statistics** (coverage analysis)
5. **Interactive mode** (review each rule conversion)

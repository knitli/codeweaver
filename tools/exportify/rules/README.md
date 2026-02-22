# Export Rules Configuration

This directory contains YAML configuration files that define the rules for determining which Python symbols should be exported from `__init__.py` files using the lazy loading pattern.

## Overview

The exportify tool uses a **priority-based rule engine** to decide which symbols to export. Rules are evaluated in priority order (highest first), and the **first matching rule** determines the action.

## File Structure

```
rules/
├── README.md             # This file - documentation
├── default_rules.yaml    # Built-in rules (required)
└── custom_rules.yaml     # User-defined rules (optional)

overrides/
└── codeweaver_overrides.yaml  # Project-specific overrides
```

## Rule Schema

### Schema Version

All rule files must declare a schema version for compatibility:

```yaml
schema_version: "1.0"
```

**Supported versions**: `["1.0"]`

### Rule Structure

Each rule has the following structure:

```yaml
- name: "RuleName"           # Unique identifier (required)
  priority: 700              # 0-1000, higher = evaluated first (required)
  description: "What this rule does"  # Human-readable explanation (optional)
  match:                     # Match criteria (required)
    # ... matching conditions (see below)
  action: include            # include | exclude | no_decision (required)
  propagate: parent          # none | parent | root | custom (optional)
```

### Match Criteria

Match criteria specify when a rule applies. Multiple criteria can be combined:

#### Simple Matching

```yaml
match:
  name_exact: "SymbolName"           # Exact name match
  name_pattern: "^public_.*"         # Regex pattern
  module_exact: "codeweaver.core"    # Exact module path
  module_pattern: ".*\\.types$"      # Regex pattern
  member_type: class                 # class | function | constant | variable | type_alias | imported
  provenance: imported               # defined_here | imported | alias_imported | unknown
```

#### Logical Combinations

```yaml
match:
  any_of:  # OR logic - at least one must match
    - name_pattern: ".*Error$"
    - name_pattern: ".*Exception$"

match:
  all_of:  # AND logic - all must match
    - member_type: class
    - module_pattern: ".*\\.core\\..*"
```

### Actions

- **`include`**: Export this symbol and propagate per `propagate` setting
- **`exclude`**: Do not export this symbol at all
- **`no_decision`**: Let lower-priority rules handle this (default fallback)

### Propagation Levels

When `action: include`, the `propagate` field controls how far up the package hierarchy the export travels:

- **`none`**: Export only in the defining module's `__init__.py`
- **`parent`**: Export in the parent module's `__init__.py`  *(default)*
- **`root`**: Propagate all the way to the package root
- **`custom`**: Reserved for future advanced use cases

**Example**: If `codeweaver.core.types.models` defines `BasedModel`:
- `propagate: none` → Only in `codeweaver/core/types/models/__init__.py`
- `propagate: parent` → In `codeweaver/core/types/__init__.py`
- `propagate: root` → In `codeweaver/__init__.py`

## Priority System

Rules are evaluated in priority order (highest first):

| Priority Range | Purpose | Examples |
|---------------|---------|----------|
| 1000 | Critical exclusions | Private symbols, dunders |
| 900 | Infrastructure exclusions | lazy_importer components |
| 800 | Framework exclusions | Test fixtures, dev utilities |
| 700 | Defined symbols (exports) | Classes, functions, constants |
| 600 | Import handling | Aliased imports |
| 500 | Import exclusions | Non-aliased imports |
| 400 | Variable handling | Public variables |
| 300 | Propagation overrides | Root-level types |
| 0-200 | Catch-all defaults | Fallback behaviors |

**Note**: If multiple rules have the same priority, they are evaluated alphabetically by `name`.

## Default Rules

The `default_rules.yaml` file contains the standard rule set:

1. **ExcludePrivateSymbols** (1000): Skip `_private` symbols
2. **ExcludeDunderSymbols** (1000): Skip `__dunder__` symbols
3. **ExcludeLazyImporter** (900): Prevent circular dependency on lazy_importer
4. **ExcludeTestFixtures** (800): Skip pytest fixtures
5. **ExportDefinedClasses** (700): Export defined classes
6. **ExportDefinedFunctions** (700): Export defined functions
7. **ExportDefinedConstants** (700): Export SCREAMING_SNAKE constants
8. **ExportTypeAliases** (700): Export type aliases
9. **ExportAliasedImports** (600): Export `from x import y as z`
10. **SkipNonAliasedImports** (500): Skip `from x import y`
11. **ExportPublicVariables** (400): Export module-level variables
12. **PropagateToRoot** (300): Errors/types go to root
13. **DefaultNoDecision** (0): Fallback

## Overrides

Override files provide **manual control** that bypasses all rules. Overrides are the **highest priority**.

### Override Structure

```yaml
schema_version: "1.0"

overrides:
  include:
    "module.path":
      - "SymbolName"
      - "AnotherSymbol"
  exclude:
    "module.path":
      - "ExcludedSymbol"
```

**Include overrides**: Force export even if rules would exclude
**Exclude overrides**: Force exclusion even if rules would include

### When to Use Overrides

- **Special cases**: Symbols that need custom handling
- **Backward compatibility**: Keep deprecated exports without advertising them
- **Public API control**: Explicitly mark public vs internal symbols
- **Bug workarounds**: Temporary fixes while rules are refined

## Creating Custom Rules

You can create `custom_rules.yaml` to add project-specific rules without modifying `default_rules.yaml`.

**Example** - Export all symbols with "Public" prefix:

```yaml
schema_version: "1.0"

rules:
  - name: "ExportPublicPrefix"
    priority: 750  # Between defined symbols (700) and imports (600)
    description: "Export symbols explicitly marked public"
    match:
      name_pattern: "^Public.*"
    action: include
    propagate: root  # Make available at package root
```

**Example** - Exclude experimental features:

```yaml
schema_version: "1.0"

rules:
  - name: "ExcludeExperimental"
    priority: 850  # High priority to override later rules
    description: "Skip experimental features"
    match:
      any_of:
        - name_pattern: "^experimental_.*"
        - module_pattern: ".*\\.experimental\\..*"
    action: exclude
```

**Example** - Export only aliased imports (likely re-exports):

```yaml
schema_version: "1.0"

rules:
  - name: "ExportAliasedImportsOnly"
    priority: 600
    description: "Export imports with aliases (likely intentional re-exports)"
    match:
      all_of:
        - member_type: imported
        - provenance: alias_imported
    action: include
    propagate: parent
```

## Member Types

The `member_type` criterion recognizes these symbol types:

| Member Type | Description | Example |
|------------|-------------|---------|
| `class` | Class definitions | `class Provider(Enum):` |
| `function` | Functions and async functions | `def get_provider():` |
| `constant` | SCREAMING_SNAKE_CASE variables | `MAX_SIZE = 1000` |
| `variable` | Module-level variables | `config = {}` |
| `type_alias` | Type aliases | `type StrDict = dict[str, str]` |
| `imported` | Imported symbols | `from x import y` |

## Symbol Provenance

The `provenance` criterion distinguishes where symbols come from:

| Provenance | Description | Example |
|-----------|-------------|---------|
| `defined_here` | Defined in the current module | `class MyClass: ...` |
| `imported` | Regular imports | `from x import y` |
| `alias_imported` | Imports with aliases (likely re-exports) | `from x import y as z` |
| `unknown` | Provenance cannot be determined | Edge cases |

**Use cases**:
- Exclude all imported symbols: `provenance: imported`
- Only export aliased imports (likely re-exports): `provenance: alias_imported`
- Distinguish between defined and imported types: `provenance: defined_here`

## Regex Pattern Reference

Patterns use Python's `re` module syntax. Common patterns:

| Pattern | Matches | Example |
|---------|---------|---------|
| `^_.*` | Starts with underscore | `_private`, `__dunder` |
| `.*Error$` | Ends with "Error" | `ValueError`, `ImportError` |
| `^[A-Z_]+$` | All caps (constants) | `MAX_SIZE`, `API_KEY` |
| `.*\\.types$` | Module ending in "types" | `codeweaver.core.types` |
| `.*\\.tests?\\..*` | Test modules | `codeweaver.tests.unit` |

**Tip**: Use [regex101.com](https://regex101.com/) to test patterns with Python flavor.

## Validation

The rule engine validates rules when loaded:

**Schema validation**:
- `schema_version` must be present and supported
- All required fields must be present
- Actions must be valid (`include`, `exclude`, `no_decision`)
- Propagation levels must be valid (`none`, `parent`, `root`, `custom`)

**Pattern validation**:
- Regex patterns must compile successfully
- Invalid patterns raise `ValueError` with helpful messages

**Priority validation**:
- Priority must be 0-1000 inclusive
- Out-of-range priorities raise `ValueError`

## Loading Rules

Rules are loaded in this order:

1. **Default rules** (`default_rules.yaml`) - Always loaded
2. **Custom rules** (`custom_rules.yaml`) - If present
3. **Project overrides** (`../overrides/*.yaml`) - If present

Rules from later files are **merged** with earlier ones. Same-priority rules are evaluated alphabetically by name.

## Best Practices

### Rule Design

1. **Use descriptive names**: `ExportPublicAPI`, not `Rule1`
2. **Document intent**: Clear `description` fields help debugging
3. **Prefer specificity**: Narrow patterns over broad catches
4. **Test incrementally**: Add rules one at a time and verify behavior

### Priority Assignment

- **1000**: Only for absolute exclusions (private, dunders)
- **900-800**: Framework/infrastructure exclusions
- **700**: Primary export rules
- **600-500**: Import handling
- **400-300**: Special cases and overrides
- **0-200**: Defaults and fallbacks

### Pattern Writing

- **Start simple**: Test with exact matches before adding patterns
- **Escape regex**: Use `\\.` for literal dots in module paths
- **Anchor patterns**: Use `^` and `$` to prevent partial matches
- **Test thoroughly**: Verify patterns match expected symbols only

### Overrides

- **Use sparingly**: Overrides bypass rule logic - prefer fixing rules
- **Document reasons**: Comment why each override exists
- **Plan deprecation**: Mark temporary overrides with TODO/FIXME
- **Keep organized**: Group by category (public API, deprecated, etc.)

## Troubleshooting

### Symbol not exported

1. Check if matching exclude rule (use `--verbose` with analyze command)
2. Check if member_type is recognized correctly
3. Verify module path matches expected pattern
4. Add override if rule fix is complex

### Symbol exported incorrectly

1. Check which rule matched (analysis output shows matched rule)
2. Verify priority order is correct
3. Add higher-priority exclusion rule if needed
4. Use override as temporary fix

### Pattern not matching

1. Test regex at regex101.com with Python flavor
2. Check for escaping issues (dots, brackets)
3. Verify member_type and module_path are correct
4. Enable debug logging to see match attempts

## Examples

### Complete Rule Example

```yaml
schema_version: "1.0"

rules:
  # High-priority exclusion
  - name: "ExcludeInternalAPI"
    priority: 950
    description: "Hide internal implementation details"
    match:
      all_of:
        - module_pattern: ".*\\.internal\\..*"
        - member_type: function
    action: exclude

  # Standard export with parent propagation
  - name: "ExportProviderClasses"
    priority: 700
    description: "Export all provider implementations"
    match:
      all_of:
        - name_pattern: ".*Provider$"
        - member_type: class
    action: include
    propagate: parent

  # Root propagation for core types
  - name: "ExportCoreExceptions"
    priority: 300
    description: "Make exceptions available at package root"
    match:
      any_of:
        - name_pattern: ".*Error$"
        - name_pattern: ".*Exception$"
    action: include
    propagate: root
```

## Schema Evolution

When schema versions change, the rule engine handles migration automatically:

- **Backward compatible**: New versions support old configs
- **Automatic migration**: Configs upgraded during load
- **Deprecation warnings**: Old patterns get warnings before removal

**Current version**: `1.0`
**Supported versions**: `["1.0"]`

### Planned Enhancements (v1.1)

- **Docstring matching**: Match symbols based on docstring content or presence
- **Metadata matching**: Match on custom metadata fields
- **Conditional propagation**: Propagation level based on symbol characteristics

## Additional Resources

- **Main documentation**: `../README.md`
- **Requirements spec**: `../.specify/deliverables/exportify-requirements-v1.0.md`
- **Type definitions**: `../common/types.py`
- **Rule engine**: `../export_manager/rules.py`

## Contributing

When adding new rules:

1. Understand existing rule priorities
2. Write clear, specific match criteria
3. Document the rule's purpose
4. Test with real codebase examples
5. Consider backward compatibility
6. Update this README if adding new patterns

---

**Version**: 1.0
**Last Updated**: 2026-02-15
**Schema Version**: 1.0

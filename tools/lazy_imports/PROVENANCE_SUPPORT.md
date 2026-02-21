# Provenance Checking Support

**Date**: 2026-02-15
**Feature**: Symbol provenance matching in rule engine
**Status**: ✅ Complete

## Summary

Added support for distinguishing between different import types in the rule engine through `SymbolProvenance` matching. This enables rules to make decisions based on whether a symbol is defined locally, imported, or imported with an alias (likely re-export).

## Changes Made

### 1. Updated `RuleMatchCriteria` Type

**File**: `tools/lazy_imports/common/types.py`

Added `provenance` field to `RuleMatchCriteria`:

```python
@dataclass(frozen=True)
class RuleMatchCriteria:
    """Criteria for matching exports."""

    name_exact: str | None = None
    name_pattern: str | None = None  # Regex
    module_exact: str | None = None
    module_pattern: str | None = None  # Regex
    member_type: MemberType | None = None
    provenance: SymbolProvenance | None = None  # NEW
    any_of: list[RuleMatchCriteria] | None = None  # OR conditions
    all_of: list[RuleMatchCriteria] | None = None  # AND conditions
```

### 2. Updated Rule Engine

**File**: `tools/lazy_imports/export_manager/rules.py`

#### Added provenance checking in `_matches_criteria()`

```python
def _matches_criteria(
    self, symbol: DetectedSymbol, module_path: str, criteria: RuleMatchCriteria
) -> bool:
    # ... existing checks ...

    if criteria.provenance and symbol.provenance != criteria.provenance:
        return False

    return True
```

#### Updated YAML parsing

Modified `_parse_rule()` and `_parse_criteria()` to parse provenance from YAML:

```python
provenance=SymbolProvenance(match_data["provenance"]) if "provenance" in match_data else None
```

#### Added import

```python
from tools.lazy_imports.common.types import (
    # ... existing imports ...
    SymbolProvenance,  # NEW
)
```

### 3. Updated Documentation

**File**: `tools/lazy_imports/rules/README.md`

#### Added provenance to match criteria examples

```yaml
match:
  name_exact: "SymbolName"
  name_pattern: "^public_.*"
  module_exact: "codeweaver.core"
  module_pattern: ".*\\.types$"
  member_type: class
  provenance: imported  # NEW
```

#### Added new section: "Symbol Provenance"

Documents the four provenance types:
- `defined_here`: Defined in the current module
- `imported`: Regular imports (`from x import y`)
- `alias_imported`: Imports with aliases (`from x import y as z`)
- `unknown`: Provenance cannot be determined

#### Removed "Known Limitations" section

The section about provenance not being supported was removed as this feature is now implemented.

#### Added example rule using provenance

```yaml
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

### 4. Created Comprehensive Tests

**File**: `tools/lazy_imports/tests/test_rules.py` (new)

Created test suite with 10 test cases covering:

#### `TestProvenanceMatching` class:
1. `test_match_defined_here_provenance` - Match symbols defined locally
2. `test_match_imported_provenance` - Match regular imports
3. `test_match_alias_imported_provenance` - Match aliased imports (re-exports)
4. `test_provenance_with_other_criteria` - Combine provenance with member_type
5. `test_provenance_with_any_of` - Provenance in OR conditions
6. `test_provenance_priority_order` - Verify priority system works with provenance
7. `test_no_provenance_criteria_matches_all` - Rules without provenance match all

#### `TestProvenanceRuleLoading` class:
8. `test_load_rule_with_provenance` - Load rules with provenance from YAML
9. `test_invalid_provenance_value` - Reject invalid provenance values
10. `test_nested_provenance_in_any_of` - Nested provenance in any_of/all_of

All tests pass ✅

## Usage Examples

### Exclude all regular imports (keep only aliased)

```yaml
- name: "ExcludeRegularImports"
  priority: 500
  match:
    provenance: imported  # Regular imports without aliases
  action: exclude
```

### Export only aliased imports (likely re-exports)

```yaml
- name: "ExportAliasedImports"
  priority: 600
  match:
    provenance: alias_imported  # Imports with aliases
  action: include
  propagate: parent
```

### Export defined classes only (exclude imported classes)

```yaml
- name: "ExportDefinedClasses"
  priority: 700
  match:
    all_of:
      - member_type: class
      - provenance: defined_here  # Only locally defined
  action: include
  propagate: parent
```

### Export either defined symbols or aliased imports

```yaml
- name: "ExportDefinedOrAliased"
  priority: 650
  match:
    any_of:
      - provenance: defined_here
      - provenance: alias_imported
  action: include
  propagate: parent
```

## Benefits

1. **Precise Control**: Rules can now distinguish between different import types
2. **Re-export Detection**: Identify likely re-exports (aliased imports) automatically
3. **Backward Compatible**: Existing rules without provenance continue to work
4. **Composable**: Provenance works with all other criteria (member_type, patterns, etc.)
5. **Well-Tested**: Comprehensive test suite ensures correctness

## Integration with AST Parser

The AST parser (`tools/lazy_imports/analysis/ast_parser.py`) already sets provenance correctly:

- **DEFINED_HERE**: Classes, functions, constants, variables defined in the file
- **IMPORTED**: Regular imports (`from x import y`)
- **ALIAS_IMPORTED**: Aliased imports (`from x import y as z`)

The rule engine now uses this information for matching.

## Validation

✅ Type checking passes
✅ All 10 tests pass
✅ Documentation updated
✅ Example rules provided
✅ Backward compatible

## Next Steps (Optional Enhancements)

While the core feature is complete, potential future enhancements:

1. **Stdlib Detection**: Add provenance filter for stdlib vs third-party imports
2. **Provenance Patterns**: Support regex patterns for original_source matching
3. **Composite Filters**: Combine provenance with import path patterns
4. **Default Rule Updates**: Update default_rules.yaml to leverage provenance

## Related Files

- `tools/lazy_imports/common/types.py` - Type definitions
- `tools/lazy_imports/export_manager/rules.py` - Rule engine
- `tools/lazy_imports/analysis/ast_parser.py` - AST parser (sets provenance)
- `tools/lazy_imports/rules/README.md` - Rule schema documentation
- `tools/lazy_imports/tests/test_rules.py` - Test suite

## Requirements Satisfied

From `exportify-requirements-v1.0.md` Section 4:

> Rules need to check `SymbolProvenance` to distinguish:
> - `DEFINED_HERE` - symbols defined in the module
> - `IMPORTED` - regular imports
> - `ALIASED_IMPORT` - imports with aliases (likely re-exports)

✅ All requirements met. The rule engine can now check provenance to distinguish between these three types.

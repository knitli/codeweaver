# Exportify - Python Package Export Management Tool

**Version**: 1.0.0
**Status**: Requirements Specification
**Author**: System Architecture Agent
**Date**: 2026-02-15

---

## Executive Summary

**exportify** is an automated Python package export management tool designed to generate and maintain `__init__.py` files using lazy import patterns. The tool automates the creation of type-safe, efficient package exports while preserving custom code, validating imports, and enforcing consistent patterns across large codebases.

### Primary Objectives

1. **Automation**: Generate complete `__init__.py` files with lazy loading infrastructure
2. **Code Preservation**: Intelligently preserve user-written code while managing exports
3. **Validation**: Detect and report broken imports across the codebase
4. **Consistency**: Enforce standardized export patterns following CodeWeaver conventions
5. **Type Safety**: Maintain full type checking support via TYPE_CHECKING blocks

### Target Users

- **Primary**: CodeWeaver project and similar codebases using lazy import patterns
- **Secondary**: Python projects wanting to adopt lazy loading for performance optimization

---

## 1. Core Functionality

### 1.1 `__init__.py` Generation Pattern

#### 1.1.1 Required File Structure

Every generated `__init__.py` MUST follow this exact structure:

```python
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Package docstring."""
# Note: imports may include other imports for user-preserved code in the module. Those imports, by default, should not be in the __all__, but should be included by rule override
from __future__ import annotations

from typing import TYPE_CHECKING
from types import MappingProxyType

from codeweaver.core.utils.lazy_importer import create_lazy_getattr

# [Optional: User-preserved code section]

if TYPE_CHECKING:
    # [TYPE_CHECKING imports grouped by module]
    # example for a fictional somepath package
    from codeweaver.somepath.bar import FooType

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    # [Export mappings]
    # ONLY contains TYPE_CHECKING defined exports
    # example:
    "FooType": (__spec__.parent, "bar")
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    # [Sorted export list]
    "FooType",
)

def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
```

#### 1.1.2 Required Imports (Always Present)

These imports MUST appear in every generated file:

```python
from __future__ import annotations
from typing import TYPE_CHECKING
from types import MappingProxyType
from codeweaver.core.utils.lazy_importer import create_lazy_getattr
```

**Rationale**: These imports provide the infrastructure for lazy loading and type checking.

NOTE: There are some known exceptions:
    1) __init__ modules with no lazy_imports should have none of these elements
    2) To avoid namespace conflicts, `codeweaver.core.types.__init__` imports `import types as _types` then in the _dynamic_imports block uses `_types.MappingProxyType`. This should be the standard for any root `types` package.
    3) lazy_importer.py's members are `create_lazy_getattr`, `LazyImport` and `lazy_import`. **these members should never be lazily exported** (by rule, they will be in __any__ blocks for their parent packages, codeweaver/core/utils/__init__ and codeweaver/core/__init__)

#### 1.1.3 Section Order (STRICT)

Sections MUST appear in this order:

1. SPDX license headers
2. Module docstring (PRESERVE, not generated unless by exception, such as for a generate command)
3. Required imports + optional imports for user-defined code
4. Optional: User-preserved code section (with comment markers)
5. TYPE_CHECKING block
6. `_dynamic_imports` assignment
7. `__getattr__` assignment
8. `__all__` tuple
9. `__dir__()` function

**Deviation**: Any deviation from this order is a validation error.


### 1.2 TYPE_CHECKING Block

#### 1.2.1 Purpose

The TYPE_CHECKING block provides import statements for static type checkers while avoiding circular imports at runtime.

#### 1.2.2 Format Specification

```python
if TYPE_CHECKING:
    from codeweaver.package1.module1 import (
        SymbolA,
        SymbolB,
    )
    from codeweaver.package1.module2 import (
        SymbolC,
        SymbolD,
    )
    from codeweaver.package1.subpackage1 import ( # child package imports driven by rule definitions
        SymbolE,
        SymbolF
    )
```

#### 1.2.3 Grouping Rules

- **Group by source module**: All imports from same module together
- **One group per module**: Never split imports from same module
- **Sort modules**: By first export's sort key (SCREAMING_SNAKE → CamelCase → snake_case)
- **Sort symbols within module**: By custom sort key

#### 1.2.4 Custom Sort Key Algorithm

```python
from typing import Literal

import textcase # already a CodeWeaver requirement

def export_sort_key(name: str) -> tuple[Literal[0, 1, 2], str]:
    """Sort key: SCREAMING_SNAKE (0), PascalCase (1), snake_case (2)."""
    if textcase.constant.match(name):
        group = 0  # SCREAMING_SNAKE_CASE
    elif textcase.pascal.match(name)
        group = 1  # PascalCase
    else:
        group = 2  # snake_case
    return (group, name.lower())
```

#### 1.2.5 Consistency Requirements

- ALL exports in `_dynamic_imports` MUST appear in TYPE_CHECKING
- ALL exports in `__all__` that are lazy-loaded MUST appear in TYPE_CHECKING
- Above sort-key must be applied to *both* `_dynamic_imports` keys and `__all__`
- No duplicates allowed
- **always absolute imports**

### 1.3 `_dynamic_imports` Block

#### 1.3.1 Type Annotation (REQUIRED)

```python
_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    # entries
})
```

**Critical**: The type annotation MUST be `MappingProxyType[str, tuple[str, str]]`

#### 1.3.2 Entry Format

```python
"SymbolName": (__spec__.parent, "relative_module_name"),
```

**Components**:
- Key: Export name (string literal)
- Value tuple[0]: Always `__spec__.parent` (represents package path)
- Value tuple[1]: Relative module name (string literal)

#### 1.3.3 Example

```python
_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "MISSING": (__spec__.parent, "sentinel"),
    "BasedModel": (__spec__.parent, "models"),
    "Provider": (__spec__.parent, "provider"),
})
```

#### 1.3.4 Sorting

Entries MUST be sorted by key using `export_sort_key()`.

#### 1.3.5 Validation Rules

- Every key MUST exist in `__all__`
- Every key MUST exist in TYPE_CHECKING block
- Every referenced module MUST exist
- Every symbol MUST exist in referenced module
- No duplicate keys allowed

### 1.4 `__getattr__` Assignment

#### 1.4.1 Fixed Format

```python
__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)
```

**This is invariant** - no customization allowed.

**Purpose**: Implements lazy loading by intercepting attribute access.

### 1.5 `__all__` Tuple

#### 1.5.1 Type Requirement

MUST be a **tuple**, not a list:

```python
__all__ = (
    "Symbol1",
    "Symbol2",
)
```

**Rationale**: Tuples are immutable and signal intent that this is fixed.

#### 1.5.2 Content Rules

The `__all__` tuple MUST contain:

1. All symbols in `_dynamic_imports`
2. Additional non-lazy exports (if rules permit)
3. Manual imports that should be public
4. Type aliases defined in the module

**MUST NOT contain**:
- Private symbols (leading `_`)
- Symbols marked as excluded by rules

#### 1.5.3 Sorting

Sorted using `export_sort_key()` - SCREAMING_SNAKE → PascalCase → snake_case

#### 1.5.4 Example

```python
__all__ = (
    "MISSING",              # SCREAMING_SNAKE (group 0)
    "UNSET",                # SCREAMING_SNAKE (group 0)
    "BasedModel",           # PascalCase (group 1)
    "Provider",             # PascalCase (group 1)
    "get_provider",         # snake_case (group 2)
)
```

### 1.6 `__dir__()` Function

#### 1.6.1 Fixed Implementation

```python
def __dir__() -> list[str]:
    """List available attributes for the package. Enables tab completion for lazy imports."""
    return list(__all__)
```

**Purpose**: Enables tab completion and introspection.

**Docstring**: Optional but recommended. Should describe the package's exports.

---

## 2. Code Preservation System

### 2.1 Managed vs. Preserved Sections

#### 2.1.1 Managed Sections (Regenerated)

These sections are ALWAYS regenerated and never preserved:

1. SPDX headers (standardized)
2. Module docstring (regenerated or preserved based on policy)
3. Required imports block
4. TYPE_CHECKING block
5. `_dynamic_imports` assignment
6. `__getattr__` assignment
7. `__all__` tuple
8. `__dir__()` function

#### 2.1.2 Preserved Sections (Never Touched)

All code NOT in managed sections:

1. Non-TYPE_CHECKING imports
2. Regular imports (non-lazy)
3. Class definitions
4. Function definitions (except `__dir__()`)
5. Variable assignments (except `_dynamic_imports`, `__all__`, `__getattr__`)
6. Type aliases (`type X = Y`)
7. Constants
8. Comments (outside managed sections)

### 2.2 Detection Strategy

#### 2.2.1 AST-Based Section Identification

Use Python's `ast` module to parse existing `__init__.py`:

1. Parse file to AST
2. Identify managed sections by pattern:
   - `if TYPE_CHECKING:` blocks
   - `_dynamic_imports = ...` assignments
   - `__getattr__ = create_lazy_getattr(...)` assignments
   - `__all__ = (...)` assignments
   - `def __dir__():` function definitions

3. Extract preserved sections:
   - All top-level nodes NOT matching managed patterns
   - Preserve line numbers and formatting where possible

#### 2.2.2 Comment Markers (Optional Enhancement)

For clarity, optionally insert comment markers:

```python
# --- BEGIN MODULE CODE ---
# User-written code preserved across regeneration
from codeweaver.core.utils import helper_function

type SpecialAlias = dict[str, Any]
# --- END MODULE CODE ---
```

### 2.3 Preservation Examples

#### Example 1: Manual Imports

**Original `__init__.py`**:
```python
from types import MappingProxyType  # Re-export
from codeweaver.core.utils import create_lazy_getattr

# Manual non-lazy import
from codeweaver.core.types import BasedModel as BaseModel

if TYPE_CHECKING:
    from codeweaver.core.types.provider import Provider
```

**Preserved in regeneration**:
```python
# Standard headers and imports...

# --- BEGIN PRESERVED CODE ---
from codeweaver.core.types.models import BasedModel as BaseModel  # re-export
# --- END PRESERVED CODE ---

if TYPE_CHECKING:
    from codeweaver.core.types.provider import Provider
    # ...rest of TYPE_CHECKING
```

#### Example 2: Type Aliases

**Original `__init__.py`**:
```python
type LiteralProviderType = ProviderLiteralString | LiteralProvider
type LiteralSDKClientType = SDKClientLiteralString | LiteralSDKClient
```

**Preserved**:
```python
# Standard sections...

# --- BEGIN PRESERVED CODE ---
type LiteralProviderType = ProviderLiteralString | LiteralProvider
type LiteralSDKClientType = SDKClientLiteralString | LiteralSDKClient
# --- END PRESERVED CODE ---

if TYPE_CHECKING:
    # ...
```

#### Example 3: Functions and Classes

If user defines custom functions/classes in `__init__.py`, they MUST be preserved:

```python
def custom_factory() -> Provider:
    """User-defined factory function."""
    return Provider()
```

### 2.4 First Run vs. Subsequent Runs

#### 2.4.1 First Run (No existing `__init__.py`)

1. Generate from scratch, use standard/generated docstring or user-provided docstring
2. No preservation needed
3. All sections generated fresh

#### 2.4.2 Subsequent Runs (Existing `__init__.py`)

1. Parse existing file
2. Extract managed sections (for comparison/validation)
3. Extract preserved sections
4. Regenerate managed sections
5. Inject preserved sections in designated location
6. Write atomically with backup

---

## 3. Symbol Detection and Classification

### 3.1 Symbol Types

#### 3.1.1 Detectable Symbol Types

The tool MUST detect these symbol types in Python modules:

| Symbol Type | Detection Pattern | Example |
|-------------|------------------|---------|
| Class | `class ClassName:` | `class Provider(Enum):` |
| Function | `def function_name():` | `def get_provider():` |
| Async Function | `async def function_name():` | `async def fetch_data():` |
| Constant | `NAME = value` (SCREAMING_SNAKE) | `MISSING = Sentinel()` |
| Variable | `name = value` (snake_case/camelCase) | `default_config = {}` |
| Type Alias (3.12+) | `type Alias = Type` | `type StrDict = dict[str, str]` |
| Type Alias (pre-3.12) | `Alias: TypeAlias = Type` | `StrDict: TypeAlias = dict[str, str]` |
| Imported Symbol | `from x import y` | `from codeweaver.core.utils import helper` |
| Aliased Import | `from x import y as z` | `from codeweaver.core.utils import helper as h` |

#### 3.1.2 Detection Method

Use Python's `ast` module:

```python
import ast

def detect_symbols(file_path: Path) -> list[DetectedSymbol]:
    tree = ast.parse(file_path.read_text())
    symbols = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            symbols.append(DetectedSymbol(name=node.name, member_type=MemberType.CLASS, ...))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            # Handle @overload specially
            if has_overload_decorator(node):
                # Group overloads, export once
                pass
            symbols.append(DetectedSymbol(name=node.name, member_type=MemberType.FUNCTION, ...))
        # ... continue for other types
```

### 3.2 Symbol Metadata

#### 3.2.1 Required Metadata Fields

Each detected symbol MUST be represented by the `DetectedSymbol` class:

```python
@dataclass(frozen=True)
class DetectedSymbol:
    name: str
    member_type: MemberType  # Enum: CLASS, FUNCTION, CONSTANT, VARIABLE, TYPE_ALIAS, IMPORT
    provenance: SymbolProvenance  # Enum: DEFINED_HERE, IMPORTED, ALIASED_IMPORT
    location: SourceLocation  # File/line info
    is_private: bool  # inferred from name (leading underscore)
    original_source: str | None  # For imports: module path
    original_name: str | None  # For aliased imports: original name
```

#### 3.2.2 Enums

```python
class MemberType(StrEnum):
    CLASS = "class"
    FUNCTION = "function"
    CONSTANT = "constant"
    VARIABLE = "variable"
    TYPE_ALIAS = "type_alias"
    IMPORT = "import"

class SymbolProvenance(StrEnum):
    DEFINED_HERE = "defined_here"
    IMPORTED = "imported"
    ALIASED_IMPORT = "aliased_import"
```

#### 3.2.2 Classification Logic

```python
def classify_symbol(node: ast.AST, module_path: str) -> DetectedSymbol:
    """Classify an AST node as a symbol with metadata."""

    # Defined in this module
    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        is_defined_here = True
        is_aliased = False

    # Import without alias
    elif isinstance(node, ast.ImportFrom) and not node.names[0].asname:
        is_defined_here = False
        is_aliased = False

    # Import with alias (explicit public API)
    elif isinstance(node, ast.ImportFrom) and node.names[0].asname:
        is_defined_here = False
        is_aliased = True

    return DetectedSymbol(...)
```

### 3.3 Edge Case: @overload Functions

#### 3.3.1 Detection Pattern

```python
from typing import overload

@overload
def foo(x: int) -> int: ...

@overload
def foo(x: str) -> str: ...

def foo(x):
    return x
```

#### 3.3.2 Handling Strategy

1. Detect all `@overload` decorated functions
2. Group by function name
3. Export name ONCE (not N times for N overloads)
4. Include all overloaded functions in TYPE_CHECKING (ONCE each)

**Example Output**:

```python
if TYPE_CHECKING:
    from codeweaver.core.module import foo  # Includes all overloads

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "foo": (__spec__.parent, "module"),  # Once only
})

__all__ = (
    "foo",  # Once only
)
```

---

## 4. Export Decision Rules

### 4.1 Rule Engine Architecture

#### 4.1.1 Rule-Based System

Export decisions MUST be driven by a configurable rule engine that produces `ExportDecision` objects:

```python
@dataclass(frozen=True)
class ExportDecision:
    module_path: str
    action: RuleAction  # Enum: INCLUDE, EXCLUDE, NO_DECISION
    export_name: str
    propagation: PropagationLevel  # Enum: NONE, PARENT, ROOT, EXPORT_AS_IS
    priority: int
    reason: str
    source_symbol: DetectedSymbol

class RuleAction(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    NO_DECISION = "no_decision"

class ExportRule:
    """Base class for export rules."""

    def evaluate(self, symbol: DetectedSymbol, context: RuleContext) -> ExportDecision | None:
        """Evaluate rule against symbol."""
        pass

@dataclass(frozen=True)
class LazyExport:
    """Final export definition for generation."""
    name: str
    source_module: str
    is_type_checking: bool
    priority: int
```

#### 4.1.2 Rule Context

```python
class RuleContext:
    """Context for evaluating export rules."""

    module_path: str
    package_path: str
    symbol: DetectedSymbol
    config: ExportConfig
```

### 4.2 Default Rule Set

#### 4.2.1 Built-in Rules (Priority Order)

Rules evaluated in order; first match wins:

1. **PrivateSymbolRule**: Skip symbols starting with `_`
2. **DefinedSymbolRule**: Export all defined symbols (classes, functions, constants)
3. **AliasedImportRule**: Export aliased imports (`from x import y as z`)
4. **TypeAliasRule**: Export type aliases
5. **NonAliasedImportRule**: Skip non-aliased imports (unless overridden)
6. **ManualExportRule**: Check manual `__all__` list if present

#### 4.2.2 Rule Implementation Examples

```python
class PrivateSymbolRule(ExportRule):
    """Skip private symbols (leading underscore)."""

    def evaluate(self, symbol: DetectedSymbol, context: RuleContext) -> ExportDecision | None:
        if symbol.name.startswith("_"):
             return ExportDecision(
                module_path=context.module_path,
                action=RuleAction.EXCLUDE,
                export_name=symbol.name,
                propagation=PropagationLevel.NONE,
                priority=self.priority,
                reason="Private symbol",
                source_symbol=symbol
            )
        return None

class AliasedImportRule(ExportRule):
    """Export explicitly aliased imports."""

    def evaluate(self, symbol: DetectedSymbol, context: RuleContext) -> ExportDecision | None:
        if symbol.provenance == SymbolProvenance.ALIASED_IMPORT:
             return ExportDecision(
                module_path=context.module_path,
                action=RuleAction.INCLUDE,
                export_name=symbol.name,
                propagation=PropagationLevel.PARENT,
                priority=self.priority,
                reason="Aliased import",
                source_symbol=symbol
            )
        return None
```

### 4.3 Rule Configuration

#### 4.3.1 Configuration File Format

`.codeweaver/exports_config.json`:

```json
{
  "rules": [
    {"type": "private_symbol", "action": "skip"},
    {"type": "defined_symbol", "action": "export"},
    {"type": "aliased_import", "action": "export"},
    {"type": "type_alias", "action": "export"}
  ],
  "exclusions": {
    "codeweaver.core.types": ["_internal_helper"]
  },
  "module_exclusions": {
    "codeweaver.server.mcp": ["dev_only_function"]
  }
}
```

#### 4.3.2 Per-Module Overrides

Rules can be overridden per-module via config or CLI flags.

### 4.4 Special Cases

#### 4.4.1 Manual `__all__` Preservation

If existing `__init__.py` has manual `__all__`:

1. Parse existing `__all__`
2. Preserve those exports in new `__all__` **if the symbols are imported or defined in the module**
3. Merge with rule-based exports
4. Remove duplicates
5. Sort final list

#### 4.4.2 Exceptions and Overrides

Some modules may need special handling:

- **Root `__init__.py`**: Often has version strings, metadata
- **MCP server `__init__.py`**: May have middleware configuration
- **Test package `__init__.py`**: May export fixtures

These should be configurable via exclusion lists.

---

## 5. Validation Features

### 5.1 Function Call Validation

#### 5.1.1 Purpose

Detect broken `lazy_import()` function calls in codebase.

#### 5.1.2 Detection Method

Scan all `.py` files for pattern:

```python
lazy_import("module.path", "ObjectName")
```

#### 5.1.3 Validation Checks

For each `lazy_import()` call:

1. **Module exists**: Can the module be imported?
2. **Object exists**: Does the module have that attribute?
3. **Report broken imports**: Display file, line, error

#### 5.1.4 Output Format

```
[ERROR] src/codeweaver/foo.py:42: MISSING OBJECT (codeweaver.bar.BazClass)
[ERROR] src/codeweaver/qux.py:15: IMPORT ERROR (codeweaver.nonexistent)
```

### 5.2 Package-Level Validation

#### 5.2.1 Consistency Checks

For each `__init__.py` with lazy imports:

1. **`__all__` exists**: MUST be present
2. **`_dynamic_imports` exists**: MUST be present if lazy loading
3. **Keys match**: All `_dynamic_imports` keys MUST be in `__all__`
4. **TYPE_CHECKING match**: All `_dynamic_imports` keys MUST be in TYPE_CHECKING
5. **Import resolution**: All lazy imports MUST resolve to real modules/objects

#### 5.2.2 Validation Errors vs. Warnings

**Errors** (MUST fix):
- Missing `__all__` when `_dynamic_imports` present
- Lazy import doesn't resolve
- KEY in `_dynamic_imports` but not in `__all__`

**Warnings** (SHOULD fix):
- `__all__` present but no `_dynamic_imports`
- KEY in `_dynamic_imports` but not in TYPE_CHECKING

#### 5.2.3 Example Output

```
[WARNING] codeweaver.core.types: No __all__ defined
[ERROR] codeweaver.providers: Broken lazy import: Provider from provider_module
[WARNING] codeweaver.server: 'middleware' in _dynamic_imports but not in __all__
```

### 5.3 Import Resolution

#### 5.3.1 Non-Executing Resolution

Import resolution MUST NOT execute code:

1. Use `importlib.util.find_spec()` to check module exists
2. Use AST parsing to check symbol exists in module
3. Handle relative imports by resolving module paths
4. Traverse re-exports through `_dynamic_imports` chains

#### 5.3.2 Re-Export Traversal

If `moduleA` re-exports from `moduleB`:

```python
# moduleA/__init__.py
_dynamic_imports = {
    "Symbol": (__spec__.parent, "moduleB"),
}
```

Validation MUST:
1. Check `moduleB` exists
2. Check `moduleB.__init__.py` has `Symbol` in TYPE_CHECKING or `_dynamic_imports`
3. Recursively resolve until finding definition

#### 5.3.3 Relative Import Handling

```python
# In codeweaver.core.types.__init__.py
from .models import BasedModel  # Relative import

# Resolve to:
# codeweaver.core.types.models.BasedModel
```

Algorithm:
1. Get current module path from file path
2. Count leading dots in import
3. Walk up package hierarchy N levels (N = dot count - 1)
4. Append module name
5. Check resolved path

---

## 6. CLI Commands

### 6.1 `analyze` Command

#### 6.1.1 Purpose

Analyze package structure and show what WOULD be generated (dry-run analysis).

#### 6.1.2 Usage

```bash
exportify analyze [OPTIONS] [MODULE]

Options:
  --module TEXT       Target specific module (e.g., codeweaver.core.types)
  --source PATH       Source directory (default: src)
  --verbose          Show detailed analysis
  --json             Output in JSON format
```

#### 6.1.3 Output

```
Package: codeweaver.core.types
Status: Ready for generation

Detected Symbols (12):
  Classes: BasedModel, Provider, Sentinel
  Functions: get_provider, create_instance
  Constants: MISSING, UNSET
  Type Aliases: LiteralProviderType

Export Rules Applied:
  ✓ BasedModel      [DefinedSymbolRule]
  ✓ Provider        [DefinedSymbolRule]
  ✓ MISSING         [DefinedSymbolRule]
  ✗ _internal       [PrivateSymbolRule - SKIP]
  ✓ get_provider    [DefinedSymbolRule]

Would Generate:
  TYPE_CHECKING: 12 imports from 5 modules
  _dynamic_imports: 12 entries
  __all__: 12 exports

Preserved Code:
  3 type aliases
  1 manual import (MappingProxyType)

Warnings:
  None

Ready: Yes
```

### 6.2 `generate` Command

#### 6.2.1 Purpose

Generate or update `__init__.py` files with lazy imports.

#### 6.2.2 Usage

```bash
exportify generate [OPTIONS] [MODULE]

Options:
  --module TEXT       Target specific module
  --source PATH       Source directory (default: src)
  --dry-run          Show what would be written without writing
  --force            Overwrite without confirmation
  --backup           Create .bak files (default: true)
  --no-backup        Skip backup creation
```

#### 6.2.3 Behavior

**Normal Mode**:
1. Analyze module
2. Generate `__init__.py` content
3. Create backup (`.bak` file)
4. Write atomically (temp file + rename)
5. Report success/failure

**Dry-Run Mode**:
1. Analyze module
2. Generate content
3. Display to stdout
4. Exit without writing

**Interactive Mode** (default when not `--force`):
1. Show proposed content
2. Ask for confirmation
3. Write if confirmed

#### 6.2.4 Example

```bash
$ exportify generate --module codeweaver.core.types

Generating __init__.py for codeweaver.core.types...

Preview:
─────────────────────────────────────────────────
[Generated content displayed]
─────────────────────────────────────────────────

Write to src/codeweaver/core/types/__init__.py? [y/N]: y

✓ Backup created: __init__.py.bak  # ensure src/codeweaver/**/*.bak in .gitiginore
✓ File written: __init__.py
✓ Validation passed
```

### 6.3 `validate` Command

#### 6.3.1 Purpose

Validate existing lazy imports without generating new files.

#### 6.3.2 Usage

```bash
exportify validate [OPTIONS] [MODULE]

Options:
  --module TEXT       Target specific module
  --source PATH       Source directory (default: src)
  --functions        Check lazy_import() function calls
  --packages         Check package-level __init__.py files
  --imports          Check all import statements
  --all              Run all validation checks (default)
  --json             Output in JSON format
```

#### 6.3.3 Output Modes

**Text Mode** (default):
```
CodeWeaver Import Validator
════════════════════════════

Section 1: lazy_import() Function Calls
  ✓ No broken function calls found

Section 2: Package-Level Lazy Imports
  [WARNING] codeweaver.core: No __all__ defined
  [ERROR] codeweaver.providers: Broken lazy import: Provider from provider_module

Section 3: Global Import Scan
  [ERROR] src/codeweaver/foo.py:42: Missing import codeweaver.bar.BazClass

Summary:
  2 errors, 1 warning
  Status: FAILED
```

**JSON Mode** (`--json`):
```json
{
  "timestamp": "2026-02-15T10:30:00Z",
  "errors": [
    {
      "type": "broken_lazy_import",
      "module": "codeweaver.providers",
      "message": "Broken lazy import: Provider from provider_module"
    }
  ],
  "warnings": [
    {
      "type": "missing_all",
      "module": "codeweaver.core",
      "message": "No __all__ defined"
    }
  ],
  "summary": {
    "total_errors": 2,
    "total_warnings": 1,
    "status": "FAILED"
  }
}
```

---

## 7. Edge Cases and Special Handling

### 7.1 Code Preservation Edge Cases

#### 7.1.1 Non-TYPE_CHECKING Imports

**Scenario**: Module has regular imports that should stay as-is.

```python
# Existing __init__.py
from types import MappingProxyType
from codeweaver.core.utils.lazy_importer import create_lazy_getattr

if TYPE_CHECKING:
    from .models import BasedModel
```

**Handling**:
- Preserve `from types import MappingProxyType` as manual import
- DON'T add `MappingProxyType` to `_dynamic_imports`
- MAY add to `__all__` if rules permit
- Keep import in preserved section

#### 7.1.2 Module-Defined vs. Imported Symbols

**Scenario**: Distinguishing between defined symbols and imports.

```python
# module.py
class Foo:  # is_defined_here=True
    pass

from codeweaver.providers.other import Bar  # is_defined_here=False, is_aliased=False
from somelibrary.types import Baz as Qux  # is_defined_here=False, is_aliased=True
```

**Handling**:
- `Foo`: Export by default (DefinedSymbolRule)
- `Bar`: Skip by default (NonAliasedImportRule)
- `Qux`: Export by default (AliasedImportRule)

#### 7.1.3 Type Aliases

**Scenario**: Detecting and preserving type aliases.

**Python 3.12+ syntax**:
```python
type StrDict = dict[str, str]
```

**Pre-3.12 syntax**:
```python
from typing import TypeAlias

StrDict: TypeAlias = dict[str, str]
```

**Detection**:
- Python 3.12+: Check for `ast.TypeAlias` nodes
- Pre-3.12: Check for `ast.AnnAssign` with `TypeAlias` annotation

**Handling**:
- Preserve type alias in preserved code section
- Export in `__all__` by default
- Include in TYPE_CHECKING if used elsewhere

#### 7.1.4 @overload Decorated Functions

**Scenario**: Multiple function signatures with same name.

```python
from typing import overload

@overload
def process(x: int) -> int: ...

@overload
def process(x: str) -> str: ...

def process(x):
    return x
```

**Detection**:
1. Scan for `@overload` decorator in AST
2. Group all overloads by function name
3. Identify implementation (no `@overload`)

**Handling**:
- Include ALL overload signatures in TYPE_CHECKING
- Export function name ONCE in `__all__`
- Export function name ONCE in `_dynamic_imports`

**Generated Output**:
```python
if TYPE_CHECKING:
    from .module import process  # Imports all signatures

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "process": (__spec__.parent, "module"),  # Once
})

__all__ = (
    "process",  # Once
)
```

### 7.2 Complex Module Scenarios

#### 7.2.1 Root `__init__.py` (Special Case)

**Characteristics**:
- Often contains version strings
- May have conditional imports
- Frequently has docstrings and metadata
- May configure logging or other infrastructure

**Handling Strategy**:
- DO NOT regenerate by default
- Require explicit `--force-root` flag
- Preserve ALL existing code
- Only generate if file doesn't exist

#### 7.2.2 MCP Server `__init__.py`

**Example**: `codeweaver.server.mcp.__init__.py`

**Characteristics**:
- May configure middleware
- May have conditional logic

**Handling**:
- Add to exclusion list by default
- Preserve middleware configuration
- Only manage exports, not logic

#### 7.2.3 Test Package `__init__.py`

**Characteristics**:
- May export pytest fixtures
- Often has test utilities
- May configure test environment

**Handling**:
- Add `*/tests/__init__.py` to exclusions
- Preserve fixture definitions
- Don't auto-generate unless explicitly requested

### 7.3 Import Resolution Edge Cases

#### 7.3.1 Circular Imports

**Scenario**: `moduleA` imports from `moduleB` which imports from `moduleA`.

**Detection**:
- Track visited modules during resolution
- Detect when revisiting a module in same resolution chain

**Handling**:
- Report as warning, not error
- TYPE_CHECKING blocks prevent runtime circular imports
- Lazy loading breaks circular dependency at runtime

#### 7.3.2 Conditional Imports

**Scenario**: Imports within `if` blocks.

```python
from typing import Any

if TYPE_CHECKING:
    from codeweaver.core.types import BasedModel
else:
    BasedModel = Any
```

**Handling**:
- Parse TYPE_CHECKING block only for exports
- Preserve conditional logic in preserved section
- Don't try to validate runtime conditional imports
- In this example, BasedModel should *not* be in the __all__ exports

#### 7.3.3 Star Imports

**Scenario**: `from module import *`

**Handling**:
- Skip star imports during symbol detection
- Don't add to `_dynamic_imports`
- Preserve in preserved code section
- Warn about star imports (bad practice)

---

## 8. File Writing Strategy

### 8.1 Backup Strategy

#### 8.1.1 Backup File Naming

```
original:  __init__.py
backup:    __init__.py.bak
```

#### 8.1.2 Backup Behavior

- **Always create backup** (unless `--no-backup` flag)
- Overwrite existing `.bak` file
- Keep only one generation of backup

#### 8.1.3 Backup Restoration

Provide `exportify restore` command:

```bash
exportify restore --module codeweaver.core.types
```

Restores `__init__.py.bak` → `__init__.py`

### 8.2 Atomic Write Strategy

#### 8.2.1 Write Process

```python
def atomic_write(target_path: Path, content: str) -> None:
    """Write file atomically to prevent corruption."""
    temp_path = target_path.with_suffix(".tmp")

    try:
        # Write to temp file
        temp_path.write_text(content, encoding="utf-8")

        # Atomic rename
        temp_path.replace(target_path)
    except Exception:
        # Clean up temp file on error
        temp_path.unlink(missing_ok=True)
        raise
```

#### 8.2.2 Error Handling

- If write fails, temp file is removed
- Original file remains untouched
- Backup is preserved
- Error message indicates rollback occurred

### 8.3 First Run vs. Subsequent Runs

#### 8.3.1 First Run Detection

```python
def is_first_run(module_path: Path) -> bool:
    """Check if this is first generation."""
    init_file = module_path / "__init__.py"
    return not init_file.exists()
```

#### 8.3.2 First Run Behavior

1. No backup needed
2. Generate from scratch
3. No preservation needed
4. Write directly

#### 8.3.3 Subsequent Run Behavior

1. Parse existing `__init__.py`
2. Extract managed sections
3. Extract preserved sections
4. Create backup
5. Generate new managed sections
6. Inject preserved sections
7. Write atomically

### 8.4 Rollback on Failure

#### 8.4.1 Validation Failure

If generated file fails validation:

1. Don't write file
2. Report validation errors
3. Keep original file intact
4. Exit with error code

#### 8.4.2 Write Failure

If write operation fails:

1. Remove temp file
2. Keep original file
3. Keep backup intact
4. Report error with details

---

## 9. Non-Functional Requirements

### 9.1 Performance

#### 9.1.1 File Scanning Performance

- **Requirement**: Scan 1000+ Python files in <5 seconds
- **Strategy**: Parallel file processing with ThreadPoolExecutor
- **Optimization**: Cache AST parsing results by file hash

#### 9.1.2 Generation Performance

- **Requirement**: Generate `__init__.py` for package with 50 modules in <1 second
- **Strategy**: Template-based generation with minimal computation

#### 9.1.3 Validation Performance

- **Requirement**: Validate entire CodeWeaver codebase (1000+ files) in <30 seconds
- **Strategy**: Early exit on first error, parallel validation

### 9.2 Reliability

#### 9.2.1 Atomic Operations

- ALL file writes MUST be atomic (temp + rename)
- No partial updates allowed
- Rollback on any failure

#### 9.2.2 Data Integrity

- Generated files MUST be valid Python syntax
- Generated files MUST pass validation before write
- AST parsing MUST succeed before write

#### 9.2.3 Error Recovery

- Backup files preserved on error
- Clear error messages with file/line numbers
- Suggested fixes where possible

### 9.3 Maintainability

#### 9.3.1 Modular Architecture

```
exportify/
├── core/
│   ├── ast_parser.py      # AST parsing and symbol detection
│   ├── classifier.py      # Symbol classification
│   └── rules.py           # Export rule engine
├── generator/
│   ├── builder.py         # Template-based generation
│   ├── formatter.py       # Code formatting
│   └── preserver.py       # Code preservation
├── validator/
│   ├── function_calls.py  # lazy_import() validation
│   ├── packages.py        # Package-level validation
│   └── imports.py         # Import resolution
├── cli/
│   ├── analyze.py         # analyze command
│   ├── generate.py        # generate command
│   └── validate.py        # validate command
└── config/
    ├── rules.py           # Rule configuration
    └── settings.py        # Global settings
```

#### 9.3.2 Plugin Architecture

Support for custom rules:

```python
class CustomExportRule(ExportRule):
    """User-defined export rule."""

    def matches(self, symbol: Symbol, context: RuleContext) -> bool:
        # Custom logic
        return symbol.name.startswith("public_")

    def action(self) -> Literal["export", "skip", "ask"]:
        return "export"

# Register custom rule
ExportRuleRegistry.register(CustomExportRule())
```

#### 9.3.3 Extensibility

- Support for custom templates
- Pluggable formatters (black, ruff)
- Configurable validation rules

### 9.4 Usability

#### 9.4.1 Clear Error Messages

**BAD**:
```
Error: Invalid import
```

**GOOD**:
```
[ERROR] src/codeweaver/core/types/__init__.py:42
  Broken lazy import: 'Provider' from 'provider_module'

  The module 'codeweaver.core.types.provider_module' does not exist.

  Suggestion:
    - Check if module name is correct
    - Ensure module file exists
    - Verify module is not excluded from build
```

#### 9.4.2 Progress Feedback

For long operations:
```
Analyzing codebase...
  ✓ Scanned 234 modules (23.4%)
  ✓ Scanned 468 modules (46.8%)
  ✓ Scanned 702 modules (70.2%)
  ✓ Scanned 1000 modules (100%)

Analysis complete in 4.2s
```

#### 9.4.3 Helpful Defaults

- Sensible default rules
- Automatic backup creation
- Dry-run mode by default for destructive operations
- Interactive confirmation for overwrites

---

## 10. Testing Strategy

### 10.1 Unit Tests

#### 10.1.1 Core Components

- **AST Parser**: Symbol detection accuracy
- **Classifier**: Correct classification of all symbol types
- **Rules Engine**: Rule matching and action execution
- **Generator**: Correct template rendering
- **Preserver**: Code preservation accuracy

#### 10.1.2 Test Coverage Target

- Minimum 90% line coverage
- 100% coverage for critical paths (file writing, validation)

### 10.2 Integration Tests

#### 10.2.1 End-to-End Scenarios

1. **Fresh Generation**: Generate `__init__.py` from scratch
2. **Regeneration**: Update existing `__init__.py` preserving code
3. **Validation**: Validate generated files against real CodeWeaver
4. **Rollback**: Test backup and restore functionality

#### 10.2.2 Real Codebase Testing

- Run against actual CodeWeaver codebase
- Verify no data loss on regeneration
- Validate all generated files parse correctly

### 10.3 Test Data

#### 10.3.1 Fixtures

Create test fixtures covering:
- Simple packages (3-5 modules)
- Complex packages (20+ modules, nested)
- Edge cases (circular imports, @overload, type aliases)
- Existing `__init__.py` with preserved code

#### 10.3.2 Golden Files

Maintain golden reference files:
- Expected `__init__.py` for each fixture
- Compare generated output byte-for-byte

---

## 11. Success Criteria

### 11.1 Functional Requirements

- ✅ Generates valid Python `__init__.py` files
- ✅ Files match CodeWeaver pattern exactly
- ✅ Preserves existing code without data loss
- ✅ Handles all 5 documented edge cases
- ✅ Validates lazy imports correctly
- ✅ Can regenerate without data loss (idempotent)
- ✅ Passes validation on real CodeWeaver codebase
- ✅ No manual intervention needed for 95%+ of files

### 11.2 Performance Requirements

- ✅ Scan 1000+ files in <5 seconds
- ✅ Generate package `__init__.py` in <1 second
- ✅ Validate entire codebase in <30 seconds
- ✅ Support parallel processing for large codebases

### 11.3 Quality Requirements

- ✅ 90%+ test coverage
- ✅ All generated files pass ruff formatting (`ruff format /path/to/file`)
- ✅ All generated files pass ruff linting (`ruff check /path/to/file`)
- ✅ All generated files pass `ty` type checking (`ty check /path/to/file`)
- ✅ Zero regressions on CodeWeaver codebase

### 11.4 Usability Requirements

- ✅ Clear, actionable error messages
- ✅ Interactive mode for destructive operations
- ✅ Dry-run mode for all commands
- ✅ Progress feedback for long operations
- ✅ Comprehensive CLI help text

---

## 12. Implementation Phases

### Phase 1: Core Infrastructure (Week 1-2)

**Deliverables**:
- AST parser for symbol detection
- Symbol classifier with metadata
- Basic rule engine
- Template-based generator
- File writing with backup

**Exit Criteria**:
- Can generate simple `__init__.py` from scratch
- Passes basic validation tests

### Phase 2: Code Preservation (Week 3)

**Deliverables**:
- Existing file parsing
- Managed vs. preserved section detection
- Code preservation in regeneration
- Backup and restore functionality

**Exit Criteria**:
- Can regenerate existing files without data loss
- Preserves type aliases, manual imports, functions

### Phase 3: Validation System (Week 4)

**Deliverables**:
- `lazy_import()` function call validation
- Package-level consistency validation
- Import resolution engine
- `validate` CLI command

**Exit Criteria**:
- Detects all broken imports in CodeWeaver
- Validates existing `__init__.py` files

### Phase 4: Advanced Features (Week 5-6)

**Deliverables**:
- @overload handling
- Circular import detection
- Custom rule support
- Configuration file system
- `analyze` CLI command

**Exit Criteria**:
- Handles all edge cases correctly
- Supports custom rules via config

### Phase 5: Testing & Refinement (Week 7-8)

**Deliverables**:
- Comprehensive test suite
- Performance optimization
- Documentation
- Integration with CodeWeaver CI

**Exit Criteria**:
- 90%+ test coverage
- All success criteria met
- Ready for production use

---

## 13. Dependencies and Prerequisites

### 13.1 Required Dependencies

```toml
[project]
name = "
requires-python = ">=3.12"

[dependencies]
textcase = ">=4.10.0"

# Core functionality
ast-grep-py = "*"  # Advanced AST operations (optional)

# CLI
cyclopts = ">=4.5.0"  # CLI framework
rich = "^13.0"  # Terminal formatting

# Code formatting
ruff = ">=0.15.0"    # Linter and formatter

# type checking
ty = ">=0.0.17"
```

### 13.2 Development Dependencies

```toml
[dev-dependencies]
pytest = "^9.0.0"
pytest-cov = ">=7.0.0"
pytest-asyncio = ">=1.3.0"
hypothesis = "^6.122.0"  # Property-based testing
```

### 13.3 Python Version

- **Minimum**: Python 3.12 (for `type` keyword support)
- **Recommended**: Python 3.13

---

## 14. Documentation Requirements

### 14.1 User Documentation

1. **README.md**: Quick start, installation, basic usage
2. **CLI Reference**: Complete command documentation
3. **Configuration Guide**: Rule configuration, exclusions
4. **Migration Guide**: Adopting exportify in existing projects

### 14.2 Developer Documentation

1. **Architecture Overview**: System design, component interaction
2. **Rule System**: Creating custom rules
3. **Extension Points**: Plugins, custom templates
4. **Contributing Guide**: Development setup, testing

### 14.3 API Documentation

1. **Module Documentation**: Docstrings for all public APIs
2. **Type Annotations**: Complete type hints
3. **Examples**: Code examples in docstrings

---

## Appendix A: Real-World Examples

### Example A1: `codeweaver.core.types.__init__.py`

**Features Demonstrated**:
- Manual imports preserved (MappingProxyType)
- Type aliases preserved
- Large `_dynamic_imports` (100+ entries)
- Complex TYPE_CHECKING block
- Sorted exports

### Example A2: `codeweaver.server.agent_api.search.__init__.py`

**Features Demonstrated**:
- Minimal exports
- Custom function definitions preserved
- Docstring preservation
- Small, focused package

---

## Appendix B: Configuration Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Exportify Configuration",
  "type": "object",
  "properties": {
    "rules": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "type": {"type": "string"},
          "action": {"enum": ["export", "skip", "ask"]}
        },
        "required": ["type", "action"]
      }
    },
    "exclusions": {
      "type": "object",
      "additionalProperties": {
        "type": "array",
        "items": {"type": "string"}
      }
    },
    "module_exclusions": {
      "type": "object",
      "additionalProperties": {
        "type": "array",
        "items": {"type": "string"}
      }
    },
    "special_packages": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Packages that require special handling (root, mcp, tests)"
    }
  }
}
```

---

## Appendix C: Test Scenarios

### Scenario 1: Fresh Package Generation

**Given**: New package with 3 modules, no existing `__init__.py`
**When**: Run `exportify generate --module mypackage`
**Then**:
- `__init__.py` created
- Contains all public symbols
- Passes validation
- No backup created (first run)

### Scenario 2: Regeneration with Preservation

**Given**: Existing `__init__.py` with type aliases and manual imports
**When**: Run `exportify generate --module mypackage`
**Then**:
- Type aliases preserved
- Manual imports preserved
- Exports updated
- Backup created
- Original code intact

### Scenario 3: Validation with Errors

**Given**: Package with broken lazy import
**When**: Run `exportify validate --module mypackage`
**Then**:
- Error reported with file and line
- Suggestion provided
- Exit code 1

### Scenario 4: Edge Case - @overload

**Given**: Module with @overload functions
**When**: Generate `__init__.py`
**Then**:
- Function exported once
- All signatures in TYPE_CHECKING
- Validation passes

---

**End of Requirements Document**

**Next Steps**:
1. Review and approve requirements
2. Set up project structure
3. Begin Phase 1 implementation
4. Iterate based on feedback from real CodeWeaver testing

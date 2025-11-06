<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Pydantic Warning Investigation Report

## Executive Summary

**Warning Message:**
```
UnsupportedFieldAttributeWarning: The 'default_factory' attribute with value <class 'list'> 
was provided to the `Field()` function, which has no effect in the context it was used. 
'default_factory' is field-specific metadata, and can only be attached to a model field 
using `Annotated` metadata or by assignment. This may have happened because an `Annotated` 
type alias using the `type` statement was used, or if the `Field()` function was attached 
to a single member of a union type.
```

**Root Cause:** The warning is triggered by the `subtypes` field in `NodeTypeDTO` class located at `src/codeweaver/semantic/types.py` (lines 109-118).

**Problematic Pattern:** Using `Field(default_factory=list)` inside an `Annotated` type that is part of a union with `None`.

---

## Investigation Process

### 1. Initial Reproduction

The warning was successfully reproduced by importing the `codeweaver.common.statistics` module:

```python
python -W all -c "from codeweaver.common import statistics"
```

### 2. Systematic Dataclass Testing

Tested each dataclass individually in the statistics module:

| Dataclass | Warning Present |
|-----------|----------------|
| TimingStatistics | ⚠️ Yes |
| _LanguageStatistics | ✓ No |
| _CategoryStatistics | ✓ No |
| FileStatistics | ✓ No |
| SessionStatistics | ⚠️ Yes |
| TokenCounter | ✓ No |
| TokenCategory | ✓ No |

**Finding:** The warning appears when importing `TimingStatistics` or `SessionStatistics`, but NOT when these classes are recreated in isolation.

### 3. Module Import Chain Analysis

Used stack trace analysis to determine the actual source:

```
statistics.py:1202 → SessionStatistics() instantiation
  ↓
SessionStatistics.__post_init__() (line 897)
  ↓
Import: codeweaver.semantic.classifications.UsageMetrics
  ↓
Import: codeweaver.semantic.grammar
  ↓
Import: codeweaver.semantic.types
  ↓
NodeTypeDTO class definition (line 70)
  ↓
⚠️ WARNING TRIGGERED
```

The warning is NOT from `TimingStatistics` itself, but from `NodeTypeDTO` which gets loaded during the `SessionStatistics` initialization process.

### 4. Identified Problematic Field

**File:** `src/codeweaver/semantic/types.py`  
**Line:** 109-118  
**Field:** `subtypes`

```python
subtypes: (
    Annotated[
        list[SimpleNodeTypeDTO],
        Field(
            description="List of subtype objects if this is an abstract node type.",
            default_factory=list,  # ⚠️ PROBLEM: default_factory inside Annotated in union
        ),
    ]
    | None
) = None
```

### 5. Pattern Verification

Tested various field patterns to confirm the exact issue:

| Pattern | Warning |
|---------|---------|
| `Annotated[list, Field(default_factory=list)]` | ✓ No |
| `Annotated[list, Field(...)] \| None = None` | ✓ No |
| `Annotated[list, Field(default_factory=list)] \| None = None` | ⚠️ **YES** |
| `Annotated[list, Field(...)] = Field(default_factory=list)` | ✓ No |

**Confirmed:** The warning is specifically triggered by the pattern where `Field(default_factory=...)` is used inside an `Annotated` type that is part of a union with `None`.

---

## Technical Explanation

### Why This Pattern Causes Issues

In Pydantic v2, when you have a union type like `Annotated[...] | None`:

1. The `Field()` metadata inside the `Annotated` applies to the annotated type, not the union
2. When Pydantic processes the union, it tries to apply the field metadata to both branches
3. The `default_factory` inside the `Annotated` becomes ambiguous in the union context
4. Pydantic warns because the `default_factory` won't have the intended effect

### Correct Patterns

**Option 1: Move default to field level**
```python
subtypes: Annotated[
    list[SimpleNodeTypeDTO],
    Field(description="List of subtype objects if this is an abstract node type."),
] | None = None
```

**Option 2: Use Field assignment syntax**
```python
subtypes: Annotated[
    list[SimpleNodeTypeDTO] | None,
    Field(description="List of subtype objects if this is an abstract node type."),
] = Field(default_factory=list)
```

**Option 3: Don't use union for optional fields with default_factory**
```python
subtypes: Annotated[
    list[SimpleNodeTypeDTO],
    Field(
        default_factory=list,
        description="List of subtype objects if this is an abstract node type.",
    ),
]
```

---

## Additional Context

### Why It Wasn't Found Earlier

The problem statement mentioned:
> "I isolated the first two data classes in the module with their dependencies and **did not** reproduce it."

This is because:
1. Testing `TimingStatistics` and `_LanguageStatistics` in isolation doesn't trigger the warning
2. The warning only appears during the **full module import chain**
3. The actual problematic field is in a different module (`semantic/types.py`)
4. It's only loaded lazily during `SessionStatistics.__post_init__()`

### Import Chain Trigger

The module-level code in `statistics.py` creates a global `_statistics` instance:

```python
_statistics: SessionStatistics = SessionStatistics(
    index_statistics=FileStatistics(),
    token_statistics=TokenCounter(),
    semantic_statistics=None,  # This triggers the import chain in __post_init__
    # ...
)
```

When `SessionStatistics.__post_init__()` tries to create the semantic statistics:

```python
def __post_init__(self) -> None:
    if not self.semantic_statistics:
        try:
            from codeweaver.semantic.classifications import UsageMetrics
            # ↑ This import eventually loads NodeTypeDTO, triggering the warning
```

---

## Recommendations

### For Users

The warning is cosmetic and doesn't affect functionality. The `default_factory` in the problematic field is being ignored (as Pydantic warns), but the field already has `= None` as a default, so it works correctly.

### For Developers

**Primary Issue:** `src/codeweaver/semantic/types.py`, line 109-118, `NodeTypeDTO.subtypes` field

**Suggested Fix:** Choose one of the correct patterns shown above. Option 1 (move default to field level) is the simplest:

```python
subtypes: (
    Annotated[
        list[SimpleNodeTypeDTO],
        Field(description="List of subtype objects if this is an abstract node type."),
    ]
    | None
) = None
```

Since `= None` is already present, the `default_factory=list` is redundant and can be removed.

---

## Test Evidence

All test scripts used in this investigation are available in `/tmp/`:
- `test_warning.py` - Tests each dataclass individually
- `test_fields.py` - Tests different field patterns
- `test_combinations.py` - Tests field combinations
- `test_computed_field.py` - Tests computed field interaction
- `test_imports.py` - Tests import patterns
- `test_instantiation.py` - Tests instantiation patterns  
- `test_union_pattern.py` - **Confirms the exact problematic pattern**

---

## Conclusion

The Pydantic warning about `default_factory=list` is **NOT** caused by any fields in the `codeweaver.common.statistics` module. It is caused by the `subtypes` field in `NodeTypeDTO` class in `src/codeweaver/semantic/types.py`, which uses an unsupported pattern where `Field(default_factory=list)` is inside an `Annotated` that is part of a union type.

The fix is straightforward: remove the `default_factory=list` from inside the `Annotated` in the `NodeTypeDTO.subtypes` field, as the field already has `= None` as its default value.

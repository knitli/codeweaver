# Delimiter Architecture Analysis and Recommendations

**Date**: 2025-10-04
**Scope**: `src/codeweaver/_constants.py` delimiter implementation (lines 8-2698)

## Executive Summary

The current delimiter implementation has significant opportunities for improvement across five key areas:

1. **Richer definitions** from inference patterns (70%+ more patterns available)
2. **Special case handling** for paragraph delimiters (`\n\n`)
3. **Cross-platform support** for Windows line separators
4. **Code organization** to reduce ~2000 lines to ~500 lines
5. **Unknown language support** through pattern reuse and language families

## Current Architecture Issues

### Issue 1: Rich Inference vs Sparse Definitions

**Problem**: The inference methods contain 70%+ more delimiter patterns than exist in the pre-assembled definitions.

**Evidence**:
- `_infer_code_element`: 32 function keyword patterns
- `_infer_control_flow`: 24 control flow patterns
- `_infer_commentary`: 17 comment patterns
- Pre-assembled definitions: Only subset implemented

**Impact**: Missing delimiters for less common languages and edge cases.

### Issue 2: Paragraph Delimiter Priority

**Problem**: `("\n\n", "\n\n")` classified as WHITESPACE (priority 1) but should try earlier.

**Analysis**:
- Double newlines often indicate semantic boundaries (paragraphs, sections)
- Priority 1 means tried last, after even STRING (priority 10)
- Should try around priority 40 (between COMMENT_BLOCK:45 and BLOCK:30)
- Likely to yield semantically coherent chunks despite no explicit semantic marker

**Current**: `DelimiterKind.WHITESPACE = 1`
**Proposed**: New `DelimiterKind.PARAGRAPH = 40`

### Issue 3: Windows Line Separator Support

**Problem**: Inference handles `\r\n` but pre-assembled definitions may not.

**Evidence** from inference:
```python
case (
    ("\n\n", "\n\n")
    | ("\n", "\n")
    | ("\r\n", "\r\n")  # Windows - in inference
    | ("\r", "\r")      # Old Mac - in inference
)
```

**Impact**: Incorrect chunking on Windows-authored files if definitions lack `\r\n` variants.

### Issue 4: Code Verbosity and Repetition

**Problem**: ~2000 lines of delimiter definitions with significant repetition.

**Examples of repetition**:
- Match case wildcards: `("def", _y) | ("function", _y) | ("fn", _y) | ...`
- Shared delimiters across languages: `{}/}`, `//`, `/**/` repeated per language
- DelimiterDict construction: Same pattern for each delimiter

**Impact**:
- Maintenance burden (update in multiple places)
- Error-prone (inconsistencies across similar definitions)
- Difficult to extend (add new language = copy-paste-modify)

### Issue 5: Inference Reuse for Unknown Languages

**Problem**: Robust inference logic exists but not architected for reuse.

**Current limitations**:
- Inference methods tightly coupled to match statements
- Cannot extract patterns as testable predicates
- No mechanism to apply patterns to undefined languages
- Unknown languages fall back to generic delimiters only

**Opportunity**: Separate pattern definitions from matching logic for reuse.

### Issue 6: Language Family Classification

**Problem**: Only "C-style" mentioned; no systematic family taxonomy.

**Missing families**:
- Python-style (significant whitespace)
- ML-style (let/in, pattern matching)
- Lisp-style (S-expressions)
- Markup-style (HTML, XML, JSX)
- Shell-style (bash, zsh)
- Functional-style (Haskell, Elm)
- LaTeX-style (TeX, ConTeXt)

**Impact**: Unknown languages cannot leverage family-level defaults.

## Recommended Architecture

### Three-Tier Delimiter System

```
┌─────────────────────────────────────────┐
│ Tier 1: Pattern Definitions             │
│ - Canonical source of truth             │
│ - Language-agnostic delimiter patterns  │
│ - Reusable across all tiers             │
└─────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│ Tier 2: Language Families               │
│ - Reusable delimiter groups             │
│ - C-style, Python-style, Markup, etc.   │
│ - Composed from Tier 1 patterns         │
└─────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│ Tier 3: Language-Specific Sets          │
│ - Composed from family + custom         │
│ - Generated from Tier 1 & 2             │
│ - Used by chunking pipeline             │
└─────────────────────────────────────────┘
```

### New File Structure

```
src/codeweaver/
├── _constants.py (current - will be refactored)
├── _delimiter_patterns.py (NEW - Tier 1)
├── _language_families.py (NEW - Tier 2)
└── _supported_languages.py (UPDATED - Tier 3)
```

### Pattern-Based DSL (Tier 1)

**File**: `src/codeweaver/_delimiter_patterns.py`

```python
from __future__ import annotations

from typing import Literal, NamedTuple

from codeweaver._constants import DelimiterKind

class DelimiterPattern(NamedTuple):
    """A reusable delimiter pattern definition.

    Attributes:
        starts: List of possible start delimiters
        ends: List of possible end delimiters, or "ANY" for wildcard
        kind: Semantic classification of delimiter
        priority_override: Optional priority override (None = use kind.default_priority)
        inclusive: Whether to include delimiters in chunk (None = infer from kind)
        take_whole_lines: Whether to expand to whole lines (None = infer from kind)
        nestable: Whether delimiter can nest (None = infer from kind)
    """
    starts: list[str]
    ends: list[str] | Literal["ANY"]
    kind: DelimiterKind
    priority_override: int | None = None
    inclusive: bool | None = None
    take_whole_lines: bool | None = None
    nestable: bool | None = None

# Code element patterns
FUNCTION_PATTERN = DelimiterPattern(
    starts=["def", "function", "fn", "fun", "method", "sub", "proc",
            "procedure", "func", "lambda", "subroutine", "macro",
            "init", "main", "entry", "constructor", "destructor",
            "ctor", "dtor", "define", "functor"],
    ends="ANY",
    kind=DelimiterKind.FUNCTION,
)

CLASS_PATTERN = DelimiterPattern(
    starts=["class"],
    ends="ANY",
    kind=DelimiterKind.CLASS,
)

STRUCT_PATTERN = DelimiterPattern(
    starts=["struct", "type"],
    ends="ANY",
    kind=DelimiterKind.STRUCT,
)

# Control flow patterns
CONDITIONAL_PATTERN = DelimiterPattern(
    starts=["if", "else", "elif", "unless", "switch", "case",
            "select", "when", "match", "where", "select case", "ifelse"],
    ends="ANY",
    kind=DelimiterKind.CONDITIONAL,
)

LOOP_PATTERN = DelimiterPattern(
    starts=["for", "while", "do", "until", "loop", "foreach",
            "pareach", "parfor"],
    ends="ANY",
    kind=DelimiterKind.LOOP,
)

# Special case: Paragraph delimiter with priority override
PARAGRAPH_PATTERN = DelimiterPattern(
    starts=["\n\n", "\r\n\r\n"],  # Platform-aware
    ends=["\n\n", "\r\n\r\n"],
    kind=DelimiterKind.PARAGRAPH,  # NEW KIND
    priority_override=40,  # Between COMMENT_BLOCK:45 and BLOCK:30
    inclusive=False,
    take_whole_lines=False,
    nestable=False,
)

# Comment patterns with line ending variants
HASH_COMMENT_PATTERN = DelimiterPattern(
    starts=["#"],
    ends=["\n", "\r\n", "\r"],  # Cross-platform
    kind=DelimiterKind.COMMENT_LINE,
)

SLASH_COMMENT_PATTERN = DelimiterPattern(
    starts=["//"],
    ends=["\n", "\r\n", "\r"],
    kind=DelimiterKind.COMMENT_LINE,
)

C_BLOCK_COMMENT_PATTERN = DelimiterPattern(
    starts=["/*", "/**"],
    ends=["*/"],
    kind=DelimiterKind.COMMENT_BLOCK,
)

# ... additional patterns
```

### Language Family System (Tier 2)

**File**: `src/codeweaver/_language_families.py`

```python
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from codeweaver._delimiter_patterns import DelimiterPattern

class LanguageFamily(str, Enum):
    """Major language family classifications based on syntax patterns."""

    C_STYLE = "c_style"              # C, C++, Java, JavaScript, Rust, Go
    PYTHON_STYLE = "python_style"    # Python, CoffeeScript
    ML_STYLE = "ml_style"            # OCaml, F#, Standard ML
    LISP_STYLE = "lisp_style"        # Lisp, Scheme, Clojure
    MARKUP_STYLE = "markup_style"    # HTML, XML, JSX, Vue
    SHELL_STYLE = "shell_style"      # Bash, Zsh, Fish
    FUNCTIONAL_STYLE = "functional"  # Haskell, Elm, PureScript
    LATEX_STYLE = "latex_style"      # TeX, LaTeX, ConTeXt
    UNKNOWN = "unknown"

# Family delimiter patterns
from codeweaver._delimiter_patterns import (
    FUNCTION_PATTERN,
    CLASS_PATTERN,
    CONDITIONAL_PATTERN,
    LOOP_PATTERN,
    SLASH_COMMENT_PATTERN,
    C_BLOCK_COMMENT_PATTERN,
    PARAGRAPH_PATTERN,
    # ... more patterns
)

FAMILY_PATTERNS: dict[LanguageFamily, list[DelimiterPattern]] = {
    LanguageFamily.C_STYLE: [
        FUNCTION_PATTERN,
        CLASS_PATTERN,
        STRUCT_PATTERN,
        CONDITIONAL_PATTERN,
        LOOP_PATTERN,
        SLASH_COMMENT_PATTERN,
        C_BLOCK_COMMENT_PATTERN,
        PARAGRAPH_PATTERN,
        # ... C-style specific patterns
    ],

    LanguageFamily.PYTHON_STYLE: [
        FUNCTION_PATTERN,
        CLASS_PATTERN,
        CONDITIONAL_PATTERN,
        LOOP_PATTERN,
        HASH_COMMENT_PATTERN,
        PARAGRAPH_PATTERN,
        # ... Python-style specific patterns
    ],

    # ... other families
}

def detect_language_family(content: str) -> LanguageFamily:
    """Detect language family from code sample.

    Uses characteristic delimiter presence scoring.
    """
    from collections import Counter

    scores: Counter[LanguageFamily] = Counter()

    for family, patterns in FAMILY_PATTERNS.items():
        for pattern in patterns:
            for start in pattern.starts:
                if start in content:
                    scores[family] += 1

    if not scores:
        return LanguageFamily.UNKNOWN

    return scores.most_common(1)[0][0]
```

### Pattern Expansion (Build Step)

**Updated**: `scripts/build_language_mappings.py`

```python
def expand_pattern(pattern: DelimiterPattern) -> list[DelimiterDict]:
    """Expand a DelimiterPattern into concrete DelimiterDict entries."""
    from itertools import product

    results = []

    ends = pattern.ends if pattern.ends != "ANY" else [""]

    for start, end in product(pattern.starts, ends):
        # Use pattern overrides if provided, else infer from kind
        priority = pattern.priority_override or pattern.kind.default_priority

        if pattern.inclusive is not None:
            inclusive = pattern.inclusive
            take_whole_lines = pattern.take_whole_lines or False
        else:
            inclusive, take_whole_lines = pattern.kind.infer_inline_strategy()

        nestable = pattern.nestable if pattern.nestable is not None else pattern.kind.infer_nestable()

        results.append(DelimiterDict(
            start=start,
            end=end,
            kind=pattern.kind,
            priority=priority,
            inclusive=inclusive,
            take_whole_lines=take_whole_lines,
            nestable=nestable,
        ))

    return results

def generate_language_delimiters(language: Language) -> list[DelimiterDict]:
    """Generate delimiter set for a language from patterns."""
    from codeweaver._language_families import FAMILY_PATTERNS

    # Get base patterns from language family
    family = language.family  # New Language attribute
    base_patterns = FAMILY_PATTERNS.get(family, [])

    # Get language-specific custom patterns
    custom_patterns = LANGUAGE_CUSTOM_PATTERNS.get(language, [])

    # Expand all patterns to concrete delimiters
    all_patterns = base_patterns + custom_patterns
    delimiters = []
    for pattern in all_patterns:
        delimiters.extend(expand_pattern(pattern))

    # Sort by priority (descending)
    return sorted(delimiters, key=lambda d: d['priority'], reverse=True)
```

## New DelimiterKind: PARAGRAPH

Add to `DelimiterKind` enum in `_constants.py`:

```python
class DelimiterKind(str, BaseEnum):
    # ... existing kinds

    PARAGRAPH = "paragraph"  # NEW: paragraph/section boundaries

    # ... rest of class

    @property
    def default_priority(self) -> PositiveInt:
        """Return the default priority for the delimiter kind."""
        return {
            DelimiterKind.MODULE_BOUNDARY: 90,
            # ...
            DelimiterKind.COMMENT_BLOCK: 45,
            DelimiterKind.PARAGRAPH: 40,  # NEW: between comment blocks and structural blocks
            DelimiterKind.BLOCK: 30,
            # ...
        }[self]
```

**Rationale**:
- Paragraph breaks (`\n\n`) are semantically meaningful boundaries
- More likely to yield coherent chunks than arbitrary whitespace
- Should be tried before structural delimiters but after code elements
- Distinct from generic WHITESPACE (priority 1)

## Unknown Language Handling

### Pattern-Based Inference

```python
def infer_delimiters_for_unknown_language(
    content: str,
    sample_delimiters: list[tuple[str, str]] | None = None
) -> list[DelimiterDict]:
    """Infer delimiters for unknown/undefined language.

    Strategy:
    1. Detect language family from content
    2. Apply family delimiter patterns
    3. If sample delimiters provided, classify them using pattern matching
    4. Fallback to generic structural delimiters
    """
    from codeweaver._language_families import detect_language_family, FAMILY_PATTERNS
    from codeweaver._delimiter_patterns import ALL_PATTERNS

    # Step 1: Detect family
    family = detect_language_family(content)

    # Step 2: Get family patterns
    if family != LanguageFamily.UNKNOWN:
        family_patterns = FAMILY_PATTERNS[family]
        delimiters = []
        for pattern in family_patterns:
            delimiters.extend(expand_pattern(pattern))
        return delimiters

    # Step 3: Pattern-based classification of sample delimiters
    if sample_delimiters:
        classified = []
        for start, end in sample_delimiters:
            # Try to match against known patterns
            matched = False
            for pattern in ALL_PATTERNS:
                if matches_pattern(start, end, pattern):
                    classified.extend(expand_pattern(pattern))
                    matched = True
                    break

            if not matched:
                # Fallback: create unknown delimiter
                classified.append(DelimiterKind.create_delimiter(start, end))

        return classified

    # Step 4: Generic fallback
    return get_generic_delimiters()

def matches_pattern(start: str, end: str, pattern: DelimiterPattern) -> bool:
    """Test if delimiter matches a pattern."""
    start_match = start.lower() in (s.lower() for s in pattern.starts)

    if pattern.ends == "ANY":
        end_match = True
    else:
        end_match = end.lower() in (e.lower() for e in pattern.ends)

    return start_match and end_match
```

## Implementation Phases

### Phase 1: Foundation (2-3 hours)
- [ ] Add `DelimiterKind.PARAGRAPH` with priority 40
- [ ] Create `_delimiter_patterns.py` with pattern DSL
- [ ] Extract 10-15 core patterns from inference methods
- [ ] Test pattern expansion to DelimiterDict

**Validation**: Pattern expansion produces equivalent DelimiterDict to manual definitions

### Phase 2: Language Families (3-4 hours)
- [ ] Create `_language_families.py` with family enum
- [ ] Define 5-7 major language families
- [ ] Map existing languages to families
- [ ] Implement family detection algorithm
- [ ] Add family-based delimiter sets

**Validation**: Family detection correctly classifies code samples

### Phase 3: Pattern Migration (4-6 hours)
- [ ] Extract all patterns from inference methods
- [ ] Create comprehensive pattern library
- [ ] Update `build_language_mappings.py` to use patterns
- [ ] Regenerate language delimiter definitions
- [ ] Verify output equivalence to current definitions

**Validation**: Generated delimiters match current behavior

### Phase 4: Unknown Language Support (2-3 hours)
- [ ] Implement pattern matching for unknown languages
- [ ] Add family-based fallback
- [ ] Update chunking pipeline to use inference
- [ ] Add tests for unknown language handling

**Validation**: Unknown languages get reasonable delimiters via family detection

### Phase 5: Cross-Platform Support (1-2 hours)
- [ ] Add line ending detection utility
- [ ] Update patterns with `\r\n` variants
- [ ] Test on Windows-authored files
- [ ] Add platform normalization fallback

**Validation**: Correct chunking on Windows, Mac, Unix line endings

## Benefits Summary

### Code Reduction
- **Before**: ~2000 lines of delimiter definitions
- **After**: ~500 lines of patterns + generation logic
- **Reduction**: 75% fewer lines to maintain

### Functionality Gains
1. **Richer definitions**: 70%+ more delimiters from inference patterns
2. **Special cases**: Paragraph delimiter priority handling
3. **Cross-platform**: Windows/Mac/Unix line ending support
4. **Unknown languages**: Family-based inference
5. **Extensibility**: Add new language = compose from patterns

### Maintenance Benefits
- Single source of truth (patterns)
- Automatic consistency (generated definitions)
- Easier testing (patterns testable in isolation)
- Clear taxonomy (language families)

## Risks and Mitigations

### Risk 1: Breaking Changes
**Impact**: Generated delimiters differ from current definitions
**Mitigation**:
- Phase 3 includes output equivalence validation
- Keep both systems during migration
- Comprehensive test suite for chunking behavior

### Risk 2: Performance
**Impact**: Pattern expansion at build time adds overhead
**Mitigation**:
- One-time cost at build, not runtime
- Generated definitions cached as before
- Pattern expansion is O(starts × ends), typically small

### Risk 3: Complexity
**Impact**: Three-tier system more complex than current
**Mitigation**:
- Better separation of concerns
- Each tier independently testable
- Clear documentation and examples

## Next Steps

1. **Review and discuss** this analysis
2. **Prioritize phases** based on immediate needs
3. **Create implementation tickets** for chosen phases
4. **Set up feature branch** for delimiter refactoring
5. **Begin Phase 1** with PARAGRAPH kind and pattern DSL

## References

- Current implementation: `src/codeweaver/_constants.py:8-2698`
- Build script: `scripts/build_language_mappings.py`
- Language definitions: `src/codeweaver/_supported_languages.py`

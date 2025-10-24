<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Semantic Classification Terminology Analysis & Redesign Proposal

## Executive Summary

**Problem**: The current semantic classification system suffers from three major terminology conflicts:

1. **"Category" Overload**: `SemanticNodeCategory` enum vs `Category` class (abstract node types from grammar)
2. **"Structural" Ambiguity**: Used to mean both "very important" (Tier 1) and "meaningless syntax" (Tier 5)
3. **Disconnected Systems**: `TokenSignificance` classification exists but isn't integrated with `SemanticNodeCategory`

**Solution**: Unified terminology framework that is clear, consistent, and integrates all classification dimensions.

---

## Current State Analysis

### Conflict 1: "Category" Term Collision

**Grammar Domain** (node_type_parser.py):
- `Category` = Abstract grouping of Things in tree-sitter grammar
- Example: `expression` Category contains `binary_expression`, `unary_expression`, etc.
- Does NOT appear in parse trees

**Semantic Domain** (categories.py):
- `SemanticNodeCategory` = Classification enum for AI importance
- Example: `DEFINITION_CALLABLE`, `FLOW_BRANCHING`, etc.
- Used for ranking nodes by semantic value

**Problem**: Same word ("category") refers to completely different concepts in different contexts.

### Conflict 2: "Structural" Meaning Reversal

**Tier 1 Usage** (`SemanticTier.STRUCTURAL_DEFINITIONS`):
- Means: "Most important code structures"
- Includes: Function definitions, class definitions, type definitions
- Importance: Highest tier (Tier 1)

**Tier 5 Usage** (`SemanticNodeCategory.SYNTAX_STRUCTURAL`):
- Means: "Syntactic punctuation with minimal semantic value"
- Includes: Braces, parentheses, semicolons, commas
- Importance: Lowest tier (Tier 5)

**TokenSignificance Usage** (`TokenSignificance.STRUCTURAL`):
- Means: "Structurally important keywords"
- Includes: Keywords like `if`, `class`, `def`
- Importance: High significance

**Problem**: Same word ("structural") has opposite meanings depending on context.

### Conflict 3: TokenSignificance Integration Gap

**TokenSignificance** (node_type_parser.py lines 364-434):
- Classification: `STRUCTURAL`, `OPERATOR`, `IDENTIFIER`, `LITERAL`, `TRIVIAL`, `COMMENT`
- Applied to: All Token objects via `significance` attribute
- Used for: Token-level filtering and importance

**SemanticNodeCategory** (categories.py):
- Classification: 20 categories across 5 tiers
- Applied to: All Things via grammar classifier
- Used for: AI context ranking

**Problem**: Two parallel classification systems that should be unified but aren't.

---

## Proposed Solution: Unified Terminology Framework

### Principle 1: Domain-Specific Prefixes

**Grammar Domain** → Keep existing clear names:
- `Category` (abstract grammar grouping)
- `Thing`, `Token`, `CompositeThing` (concrete parse tree nodes)
- `Connection`, `Role` (relationships)

**Semantic Domain** → Rename to avoid collision:
- `SemanticClass` (was: `SemanticNodeCategory`)
- `ImportanceRank` (was: `SemanticTier`)

### Principle 2: Clarity Over Brevity

**Replace ambiguous "structural"**:

1. **For Tier 1** (high importance):
   - OLD: `SemanticTier.STRUCTURAL_DEFINITIONS`
   - NEW: `ImportanceRank.PRIMARY_DEFINITIONS`

2. **For Tier 5** (low importance):
   - OLD: `SemanticNodeCategory.SYNTAX_STRUCTURAL`
   - NEW: `SemanticClass.SYNTAX_PUNCTUATION`

3. **For TokenSignificance** (keywords):
   - OLD: `TokenSignificance.STRUCTURAL`
   - NEW: `TokenSignificance.KEYWORD`

### Principle 3: Integrate TokenSignificance

**Unified Classification Approach**:
- `TokenSignificance` → Token-specific layer (leaf nodes only)
- `SemanticClass` → Universal layer (all nodes)
- Classes map to TokenSignificance where applicable

Example mapping:
```python
# Token with TokenSignificance.KEYWORD → SemanticClass.SYNTAX_KEYWORD
# Token with TokenSignificance.OPERATOR → SemanticClass.OPERATION_OPERATOR
# Token with TokenSignificance.LITERAL → SemanticClass.LITERAL_VALUE
```

---

## Complete Redesign: Semantic Classification System

### Layer 1: ImportanceRank (was: SemanticTier)

Five importance tiers, renamed for clarity:

```python
class ImportanceRank(int, BaseEnum):
    """Importance ranking from highest to lowest priority."""

    PRIMARY_DEFINITIONS = 1      # was: STRUCTURAL_DEFINITIONS
    BOUNDARY_CONTRACTS = 2       # unchanged
    CONTROL_FLOW_LOGIC = 3       # unchanged
    OPERATIONS_EXPRESSIONS = 4   # unchanged
    SYNTAX_ELEMENTS = 5          # was: SYNTAX_REFERENCES
```

**Rationale**:
- "PRIMARY" clearly indicates highest importance
- "DEFINITIONS" preserved (accurate and clear)
- "SYNTAX_ELEMENTS" more general than "SYNTAX_REFERENCES"

### Layer 2: SemanticClass (was: SemanticNodeCategory)

Renamed categories with consistent, intuitive names:

#### Rank 1: PRIMARY_DEFINITIONS

```python
# UNCHANGED (names are clear)
DEFINITION_CALLABLE = "definition_callable"
DEFINITION_TYPE = "definition_type"
DEFINITION_DATA = "definition_data"
DEFINITION_TEST = "definition_test"
```

#### Rank 2: BOUNDARY_CONTRACTS

```python
# UNCHANGED (names are clear)
BOUNDARY_MODULE = "boundary_module"
BOUNDARY_ERROR = "boundary_error"
BOUNDARY_RESOURCE = "boundary_resource"
DOCUMENTATION_STRUCTURED = "documentation_structured"
```

#### Rank 3: CONTROL_FLOW_LOGIC

```python
# UNCHANGED (names are clear)
FLOW_BRANCHING = "flow_branching"
FLOW_ITERATION = "flow_iteration"
FLOW_CONTROL = "flow_control"
FLOW_ASYNC = "flow_async"
```

#### Rank 4: OPERATIONS_EXPRESSIONS

```python
# RENAMED for consistency
OPERATION_INVOCATION = "operation_invocation"   # unchanged
OPERATION_DATA = "operation_data"               # unchanged
OPERATION_COMPUTATION = "operation_computation" # unchanged
OPERATION_OPERATOR = "operation_operator"       # NEW (split from OPERATION_COMPUTATION)
EXPRESSION_ANONYMOUS = "expression_anonymous"   # unchanged
```

**New**: `OPERATION_OPERATOR` - Dedicated class for operators (was mixed into COMPUTATION)

#### Rank 5: SYNTAX_ELEMENTS

```python
# RENAMED for clarity
SYNTAX_IDENTIFIER = "syntax_identifier"         # was: SYNTAX_IDENTIFIER
SYNTAX_LITERAL = "syntax_literal"               # was: LITERAL_VALUE
SYNTAX_KEYWORD = "syntax_keyword"               # NEW (split from SYNTAX_PUNCTUATION)
SYNTAX_PUNCTUATION = "syntax_punctuation"       # was: SYNTAX_STRUCTURAL
SYNTAX_ANNOTATION = "syntax_annotation"         # was: ANNOTATION_METADATA
SYNTAX_COMMENT = "syntax_comment"               # NEW (split from DOCUMENTATION)
```

**Rationale**:
- Consistent `SYNTAX_*` prefix for all Tier 5 classes
- "PUNCTUATION" replaces ambiguous "STRUCTURAL"
- "KEYWORD" gets dedicated class (important for Token integration)
- "COMMENT" separated from structured documentation
- "IDENTIFIER" and "LITERAL" get SYNTAX prefix for consistency

### Layer 3: TokenSignificance (Enhanced)

Refined token-specific classification:

```python
class TokenSignificance(BaseEnum):
    """Token-level significance classification."""

    KEYWORD = "keyword"          # was: STRUCTURAL
    OPERATOR = "operator"        # unchanged
    IDENTIFIER = "identifier"    # unchanged
    LITERAL = "literal"          # unchanged
    PUNCTUATION = "punctuation"  # was: TRIVIAL (partial)
    COMMENT = "comment"          # unchanged
    WHITESPACE = "whitespace"    # NEW (split from TRIVIAL)
```

**Changes**:
- `STRUCTURAL` → `KEYWORD` (matches common terminology)
- `TRIVIAL` split into `PUNCTUATION` + `WHITESPACE`
- Clear 1:1 mapping to SemanticClass for Tokens

### Integration: TokenSignificance ↔ SemanticClass

**Automatic mapping for Token objects**:

```python
TOKEN_TO_SEMANTIC_CLASS = {
    TokenSignificance.KEYWORD: SemanticClass.SYNTAX_KEYWORD,
    TokenSignificance.OPERATOR: SemanticClass.OPERATION_OPERATOR,
    TokenSignificance.IDENTIFIER: SemanticClass.SYNTAX_IDENTIFIER,
    TokenSignificance.LITERAL: SemanticClass.SYNTAX_LITERAL,
    TokenSignificance.PUNCTUATION: SemanticClass.SYNTAX_PUNCTUATION,
    TokenSignificance.COMMENT: SemanticClass.SYNTAX_COMMENT,
    TokenSignificance.WHITESPACE: SemanticClass.SYNTAX_PUNCTUATION,  # both low importance
}
```

**Usage in GrammarClassifier**:

```python
def classify_thing(self, thing_name: ThingName, language: SemanticSearchLanguage):
    thing = registry.get_thing_by_name(thing_name, language=language)

    # For Tokens: use TokenSignificance → SemanticClass mapping
    if isinstance(thing, Token):
        semantic_class = TOKEN_TO_SEMANTIC_CLASS[thing.significance]
        rank = ImportanceRank.from_class(semantic_class)
        return ClassificationResult(
            semantic_class=semantic_class,
            rank=rank,
            confidence=0.99,
            method=ClassificationMethod.TOKEN_SIGNIFICANCE,
            evidence=f"Token with significance {thing.significance.value}"
        )

    # For CompositeThings: use existing grammar-based classification
    # ... (Category, DirectConnection, Positional methods unchanged)
```

---

## Migration Path

### Phase 1: Add New Names (Backward Compatible)

1. Add `ImportanceRank` as alias to `SemanticTier`
2. Add `SemanticClass` as alias to `SemanticNodeCategory`
3. Add new enum members with updated names
4. Keep old names with deprecation warnings

### Phase 2: Update Internal Usage

1. Update `grammar_classifier.py` to use new names
2. Update `categories.py` internal references
3. Add TokenSignificance → SemanticClass integration
4. Update tests to use new terminology

### Phase 3: Remove Old Names

1. Remove deprecated aliases after 2 releases
2. Update all documentation
3. Final migration guide for external users

---

## Complete Terminology Reference

### Quick Translation Guide

| Old Term | New Term | Context |
|----------|----------|---------|
| `SemanticNodeCategory` | `SemanticClass` | Enum for node classification |
| `SemanticTier` | `ImportanceRank` | Enum for importance levels |
| `STRUCTURAL_DEFINITIONS` | `PRIMARY_DEFINITIONS` | Tier 1 name |
| `SYNTAX_REFERENCES` | `SYNTAX_ELEMENTS` | Tier 5 name |
| `SYNTAX_STRUCTURAL` | `SYNTAX_PUNCTUATION` | Low-importance syntax |
| `SYNTAX_IDENTIFIER` | `SYNTAX_IDENTIFIER` | Identifier references |
| `LITERAL_VALUE` | `SYNTAX_LITERAL` | Literal values |
| `ANNOTATION_METADATA` | `SYNTAX_ANNOTATION` | Metadata annotations |
| `TokenSignificance.STRUCTURAL` | `TokenSignificance.KEYWORD` | Keywords |
| `TokenSignificance.TRIVIAL` | `TokenSignificance.PUNCTUATION` | Punctuation (or WHITESPACE) |

### Domain Vocabulary Summary

**Grammar Domain** (tree-sitter parsing):
- `Category` - Abstract grouping in grammar
- `Thing` - Concrete parse tree node
- `Token` - Leaf node (no children)
- `CompositeThing` - Non-leaf node (has children)
- `Connection` - Edge between nodes
- `Role` - Semantic function of edge

**Semantic Domain** (AI importance):
- `SemanticClass` - Classification of node type
- `ImportanceRank` - Tier of importance (1-5)
- `TokenSignificance` - Token-specific subclassification
- `ImportanceScores` - Multi-dimensional scoring

**No Overlap**: Each term has exactly one meaning in its domain.

---

## Benefits of Proposed System

### 1. **Zero Ambiguity**
- "Category" only refers to grammar abstraction
- "Structural" removed entirely from semantic layer
- "Class" clearly distinct from "Category"

### 2. **Intuitive Hierarchy**
```
ImportanceRank (5 tiers)
  ├─ SemanticClass (21 classes)
  │   └─ TokenSignificance (7 types, for Tokens only)
  └─ ImportanceScores (multi-dimensional, per class)
```

### 3. **Natural Integration**
- TokenSignificance automatically maps to SemanticClass
- Grammar classifier can use Token.significance directly
- Consistent classification across all node types

### 4. **Clear Communication**
- `ImportanceRank.PRIMARY_DEFINITIONS` - immediately understood
- `SemanticClass.SYNTAX_PUNCTUATION` - self-explanatory
- `TokenSignificance.KEYWORD` - matches industry terminology

### 5. **Extensible Design**
- Easy to add new SemanticClass values
- TokenSignificance can grow independently
- ImportanceRank structure supports future refinement

---

## Implementation Checklist

### Core Renames
- [ ] `SemanticTier` → `ImportanceRank`
- [ ] `SemanticNodeCategory` → `SemanticClass`
- [ ] `STRUCTURAL_DEFINITIONS` → `PRIMARY_DEFINITIONS`
- [ ] `SYNTAX_REFERENCES` → `SYNTAX_ELEMENTS`

### SemanticClass Updates
- [ ] `SYNTAX_STRUCTURAL` → `SYNTAX_PUNCTUATION`
- [ ] `SYNTAX_IDENTIFIER` → `SYNTAX_IDENTIFIER`
- [ ] `LITERAL_VALUE` → `SYNTAX_LITERAL`
- [ ] `ANNOTATION_METADATA` → `SYNTAX_ANNOTATION`
- [ ] Add `SYNTAX_KEYWORD` (new)
- [ ] Add `SYNTAX_COMMENT` (new)
- [ ] Add `OPERATION_OPERATOR` (new)

### TokenSignificance Updates
- [ ] `STRUCTURAL` → `KEYWORD`
- [ ] `TRIVIAL` → split into `PUNCTUATION` + `WHITESPACE`
- [ ] Add mapping: `TOKEN_TO_SEMANTIC_CLASS`

### Integration Work
- [ ] Update `GrammarClassifier.classify_thing()` to use TokenSignificance
- [ ] Add `ClassificationMethod.TOKEN_SIGNIFICANCE`
- [ ] Update tier mappings in `categories.py`
- [ ] Update importance scores for new classes

### Testing & Documentation
- [ ] Update all tests with new terminology
- [ ] Update docstrings and module documentation
- [ ] Add migration guide
- [ ] Update CLAUDE.md and other project docs

---

## Conclusion

This redesign eliminates all terminology conflicts while preserving the sophisticated multi-dimensional classification system. The new names are:

1. **Unambiguous** - Each term has one meaning
2. **Intuitive** - Self-documenting and easy to understand
3. **Consistent** - Parallel structure across layers
4. **Integrated** - TokenSignificance naturally maps to SemanticClass
5. **Professional** - Matches industry terminology where appropriate

The migration can be done gradually with backward compatibility, ensuring zero breaking changes during the transition period.

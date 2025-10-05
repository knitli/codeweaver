# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Parser for tree-sitter node-types.json files with intuitive terminology.

This module provides functionality to parse tree-sitter `node-types.json` files and extract
grammar information using clear, intuitive terminology instead of tree-sitter's confusing vocabulary.

## Background

tl;dr: **This is the parser we wish we had when we started working with tree-sitter. We hope it
makes your experience with tree-sitter grammars smoother and more intuitive.**

When developing CodeWeaver and our rust-based future backend, Thread, we spent a lot of time
with tree-sitter and its quirks. While tree-sitter is a powerful tool, its vocabulary and structure,
combined with the lack of comprehensive documentation, can make it challenging to work with.
Simply put: it's not intuitive.

This is on full display in the `node-types.json` file, which describes the various node types
in a grammar. This file is crucial for understanding how to interact with parse trees, but its
structure and terminology are confusing. It conflates several distinct concepts:
- It doesn't clearly differentiate between **nodes** (vertices) and **edges** (relationships)
- It uses "named" to describe both nodes and edges, meaning "has a grammar rule", not "has a name"
  (everything has a name!)
- It flattens hierarchies and structural patterns in ways that obscure their meaning

When I originally wrote this parser, my misunderstandings of these concepts led to a week of
lost time and incorrect assumptions. After that, I decided to write this parser using terminology
and structure that more intuitively describes the concepts at play -- completely departing from
tree-sitter's terminology.

Knitli is fundamentally about making complex systems more intuitive and accessible, and this is
a perfect example of that philosophy in action. By using clearer terminology and structure, we're
making it easier for developers to understand and work with tree-sitter grammars. This saves time,
reduces frustration, and empowers developers to build better tools.

**For tree-sitter experts:** We provide a translation guide below to help bridge the gap between
the two terminologies. If you find this frustrating, we understand -- but we believe clarity for
newcomers is more important than tradition.

## CodeWeaver's Terminology

We clarify and separate concepts that tree-sitter conflates: nodes vs edges, abstract vs concrete,
structural roles vs semantic meaning. Here's our approach:

### Abstract Groupings

**Category** - Abstract classification that groups Things with shared characteristics.
- Do NOT appear in parse trees (abstract only)
- Used for polymorphic type constraints and classification
- Example: `expression` is a Category containing `binary_expression`, `unary_expression`, etc.
- **Tree-sitter equivalent**: Nodes with `subtypes` field (abstract types)
- **Empirical finding**: ~110 unique Categories across 25 languages

**Multi-Category Membership:**
- Things can belong to multiple Categories (uncommon but important)
- **13.5%** of Things belong to 2+ Categories
- **86.5%** belong to exactly 1 Category
- Common in C/C++ (declarators serving multiple roles)
- Example: `identifier` → `[_declarator, expression]`

### Concrete Parse Tree Nodes

**Thing** - A concrete element that appears in the parse tree.
- Two kinds: **Token** (leaf) or **Composite** (non-leaf)
- What you actually see when you parse code
- **Tree-sitter equivalent**: Named or unnamed "nodes"
- Name chosen for clarity: "it's a thing in your code" (considered: Entity, Element, Construct)

**Token** - Leaf Thing with no structural children.
- Represents keywords, identifiers, literals, punctuation
- What you literally **see** in the source code
- Classified by significance: structural, identifier, literal, trivia, comment
- **Tree-sitter equivalent**: Node with no `fields` or `children`

**Composite Node** - Non-leaf Thing with structural children.
- Has Direct and/or Positional connections to child Things
- Represents complex structures: functions, classes, expressions
- **Tree-sitter equivalent**: Node with `fields` and/or `children`

### Structural Relationships

**Connection** - Directed relationship from parent Thing to child Thing(s).
- Graph terminology: an "edge"
- Three classes: Direct, Positional, Loose
- **Tree-sitter equivalent**: `fields` (Direct), `children` (Positional), `extras` (Loose)

**ConnectionClass** - Classification of connection types:

1. **DIRECT** - Named semantic relationship with a **Role**
   - Has a specific semantic function (e.g., "condition", "body", "parameters")
   - Most precise type of structural relationship
   - **Tree-sitter equivalent**: Grammar "fields"
   - **Empirical finding**: 9,606 Direct connections across all languages

2. **POSITIONAL** - Ordered structural relationship without semantic naming
   - Position matters but no explicit role name
   - Example: function arguments in some languages
   - **Tree-sitter equivalent**: Grammar "children"
   - **Empirical finding**: 6,029 Positional connections across all languages

3. **LOOSE** - Permissive relationship allowing appearance anywhere
   - Can appear in any context without explicit declaration
   - Used for comments, whitespace, ambient elements
   - **Tree-sitter equivalent**: "extra" nodes
   - **Empirical finding**: ~2-3 Loose types per language (typically comments, whitespace)

*Note: Direct and Positional Connections describe **structure**, while Loose Connections
describe **permission**.*

**Role** - Named semantic function of a Direct connection.
- Only Direct connections have Roles (Positional and Loose do not)
- Describes **what purpose** a child serves, not just that it exists
- Examples: "condition", "body", "parameters", "left", "right", "operator"
- **Tree-sitter equivalent**: Field name in grammar
- **Empirical finding**: ~90 unique role names across all languages

### Connection Target References

**Polymorphic Type Constraints:**
Connections can reference either Categories (abstract) OR concrete Things, enabling flexible
type constraints:

**Category References** (polymorphic constraints):
- Connection accepts ANY member of a Category
- Example: `condition` field → `expression` (accepts any expression type)
- **Empirical finding**:
  - **7.9%** of field references are to Categories
  - **10.3%** of children references are to Categories
- Common pattern: `argument_list.children → expression` (any expression type accepted)

**Concrete Thing References** (specific constraints):
- Connection accepts only specific Thing types
- Example: `operator` field → `["+", "-", "*", "/"]` (specific operators only)
- **Empirical finding**:
  - **92.1%** of field references are to concrete Things
  - **89.7%** of children references are to concrete Things
- Common pattern: Structural components like `parameter_list`, `block`, specific tokens

**Mixed References** (both in same connection):
- Single connection can reference both Categories AND concrete Things
- Example: `body` field → `[block, expression]` (either concrete type)
- Design principle: Store references as-is, provide resolution utilities when needed

### Attributes

**Thing Attributes:**

- **is_explicit_rule** (bool)
  - Whether the Thing has a dedicated named production rule in the grammar
  - True: Named grammar rule (appears with semantic name)
  - False: Anonymous grammar construct or synthesized node
  - **Tree-sitter equivalent**: `named = True/False`
  - **Note**: Included for completeness; limited practical utility for semantic analysis

- **is_significant** (bool, Token only)
  - Whether the Token carries semantic/structural meaning vs formatting trivia
  - True: keywords, identifiers, literals, operators, comments
  - False: whitespace, line continuations, formatting tokens
  - Practically similar to `is_explicit_rule` but focuses on semantic importance
  - Used for filtering during semantic analysis vs preserving for formatting

**Connection Attributes:**

- **allows_multiple** (bool)
  - Whether the Connection permits multiple children of specified type(s)
  - Defines cardinality upper bound (0 or 1 vs 0 or many)
  - **Tree-sitter equivalent**: `multiple = True/False`
  - **Note**: Specifies CAN have multiple, not MUST have multiple

- **requires_presence** (bool)
  - Whether at least one child of specified type(s) MUST be present
  - Defines cardinality lower bound (0 or more vs 1 or more)
  - **Tree-sitter equivalent**: `required = True/False`
  - **Note**: Doesn't require a specific Connection, just ≥1 from the allowed list

**Cardinality Matrix:**

| requires_presence | allows_multiple | Meaning |
|------------------|-----------------|---------|
| False | False | 0 or 1 (optional single) |
| False | True | 0 or more (optional multiple) |
| True | False | exactly 1 (required single) |
| True | True | 1 or more (required multiple) |

## Tree-sitter Translation Guide

For developers familiar with tree-sitter terminology:

| Tree-sitter Term | CodeWeaver Term | Notes |
|-----------------|-----------------|-------|
| Abstract type (with subtypes) | Category | Doesn't appear in parse trees |
| Named/unnamed node | Thing | Concrete parse tree node |
| Node with no fields | Token | Leaf node |
| Node with fields/children | Composite Node | Non-leaf node |
| Field | Direct Connection | Has semantic Role |
| Child | Positional Connection | Ordered, no Role |
| Extra | Loose Connection | Can appear anywhere |
| Field name | Role | Semantic function |
| `named` attribute | `is_explicit_rule` | Has named grammar rule |
| `multiple` attribute | `allows_multiple` | Upper cardinality bound |
| `required` attribute | `requires_presence` | Lower cardinality bound |

## Design Rationale

**Why these names?**
- **Thing**: Simple, clear, unpretentious. "It's a thing in your code."
- **Category**: Universally understood as abstract grouping
- **Connection**: Graph theory standard; clearer than conflating fields/children/extras
- **Role**: Describes purpose, not just presence
- **ConnectionClass**: Explicit enumeration of relationship types

**Empirical validation:**
- Analysis of 25 languages, 5,000+ node types
- ~110 unique Categories, ~736 unique Things with category membership
- 7.9-10.3% of references are polymorphic (Category references)
- 13.5% of Things have multi-category membership
- Patterns consistent across language families

**Benefits:**
- **Clearer mental model**: Separate nodes, edges, and attributes explicitly
- **Easier to learn**: Intuitive names reduce cognitive load
- **Better tooling**: Explicit types enable better type checking and validation
- **Future-proof**: Accommodates real-world patterns (multi-category, polymorphic references)
"""

from typing import NewType

from codeweaver._common import BaseEnum, LiteralStringT


Role = NewType("Role", LiteralStringT)


class ConnectionClass(BaseEnum):
    """Classification of connection types between Things.

    This enum defines the three classes of connections that can exist between Things in a parse tree:
    - DIRECT: Named semantic relationship **with a Role**
    - POSITIONAL: Ordered structural relationship without semantic naming
    - LOOSE: Permissive relationship allowing appearance anywhere
    """

    DIRECT = "direct"
    POSITIONAL = "positional"
    LOOSE = "loose"


class ThingKind(BaseEnum):
    """Classification of Thing types in a parse tree.

    This enum defines the two kinds of Things that can appear in a parse tree:
    - TOKEN: Leaf Thing with no structural children
    - COMPOSITE: Non-leaf Thing with structural children
    """

    TOKEN = "token"  # noqa: S105  # false positive: "token" is not a hardcoded security token
    COMPOSITE = "composite"

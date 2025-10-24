<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Node Type Parser Framework Review and Recommendations

## Executive Summary

Your new framework represents a significant conceptual improvement over the tree-sitter terminology. The core abstractions (Category, Thing, Connection, Role) are intuitive and well-chosen. However, there are terminology inconsistencies and conceptual gaps that need resolution before implementation.

**Key Findings**:
- ✅ **Strong Foundation**: Category/Thing/Connection abstraction is excellent
- ⚠️ **Terminology Issues**: "Type" is overloaded and ambiguous
- ⚠️ **Conceptual Gaps**: Missing attributes, unclear hierarchies
- ✅ **Clarity Improvements**: Much clearer than tree-sitter's original terminology

---

## 1. Terminology Analysis & Recommendations

### 1.1 The "Type" Problem

**Current Usage** (inconsistent):
- "Connection types" (Direct, Positional, Loose)
- "node_type" (the name/identifier)
- "Thing types" (implicit: Token vs non-Token)

**Issue**: The word "type" is doing too much work and creates confusion.

**Recommendation**: Use distinct terms for each concept

```python
# Instead of "Connection types"
class ConnectionClass(BaseEnum):
    """Classification of edge relationships between Things."""
    DIRECT = "direct"      # Named structural relationship (has a Role)
    POSITIONAL = "positional"  # Ordered structural relationship (no Role)
    LOOSE = "loose"         # Permissive relationship (can appear anywhere)

# Instead of "node_type"
node_name: str          # The actual identifier (e.g., "function_definition")

# Instead of "Thing types"
class ThingKind(BaseEnum):
    """Classification of Things by their structural characteristics."""
    TOKEN = "token"        # Leaf node (no fields/children)
    COMPOSITE = "composite"  # Non-leaf node (has structure)
```

**Rationale**:
- `ConnectionClass` clarifies we're categorizing connection relationships
- `node_name` is what it actually is - a name/identifier
- `ThingKind` distinguishes structural categories of Things

### 1.2 "Role" Clarity

**Current**: Role is described as "the specific function or purpose of a direct Connection"

**Issue**: This could be clearer about what "role" means in practice.

**Recommendation**: Enhance definition and provide explicit examples

```python
class Role(str):
    """Named semantic function of a Direct connection.

    Roles describe WHAT PURPOSE a child Thing serves for its parent,
    not just that a connection exists.

    Examples:
        - "condition" in an if_statement Thing
        - "body" in a function_definition Thing
        - "parameters" in a function_call Thing
        - "left" and "right" in a binary_expression Thing

    Note: Only Direct connections have Roles. Positional and Loose
    connections do not have semantic role names.
    """
    pass
```

### 1.3 Attribute Naming Consistency

**Current Inconsistencies**:
- `is_explicit_rule` - uses "is_" prefix
- `is_significant` - uses "is_" prefix
- `can_connect_multiple` - uses "can_" prefix (different pattern)
- `requires_connection` - uses "requires_" prefix (different pattern)

**Recommendation**: Establish consistent prefix conventions

```python
class ThingAttributes:
    """Attributes describing Thing characteristics and constraints."""

    # Intrinsic properties (what it IS)
    is_explicit_rule: bool      # Has named grammar rule
    is_significant: bool        # Semantically meaningful (not whitespace/trivial)

    # Structural properties (what it HAS)
    has_multiple_allowed: bool  # Can connect to multiple children
    has_required_connection: bool  # Must have ≥1 connection of specified types

class ConnectionAttributes:
    """Attributes describing Connection characteristics."""

    # Connection properties
    allows_multiple: bool       # Can connect to multiple Things
    requires_presence: bool     # At least one must be present
```

**Rationale**:
- `is_*` for intrinsic properties
- `has_*` for structural capabilities
- `allows_*` / `requires_*` for constraints
- Consistent grammar (no mixing of "can" and "allows")

---

## 2. Conceptual Gaps & Missing Elements

### 2.1 Category-Thing Relationship

**Current**: Categories are abstract groupings, Things are concrete nodes

**Gap**: How do we represent the relationship between a Category and its member Things?

**Recommendation**: Add explicit relationship modeling

```python
class Category(BasedModel):
    """Abstract grouping of related Things sharing characteristics.

    Categories do NOT appear in parse trees but classify Things that do.
    """
    name: str                    # e.g., "expression", "statement"
    member_things: frozenset[str]  # Thing names that belong to this Category
    language: SemanticSearchLanguage

    def includes(self, thing_name: str) -> bool:
        """Check if a Thing belongs to this Category."""
        return thing_name in self.member_things

class Thing(BasedModel):
    """Concrete node that appears in parse trees."""
    name: str                     # The identifier (e.g., "binary_expression")
    categories: frozenset[str]    # Categories this Thing belongs to
    kind: ThingKind              # TOKEN or COMPOSITE
    # ... other attributes

    def is_in_category(self, category_name: str) -> bool:
        """Check if this Thing belongs to a Category."""
        return category_name in self.categories
```

### 2.2 Connection Directionality

**Current**: Connections described as "parent to child"

**Gap**: Should this be explicit in the model?

**Recommendation**: Add explicit source/target

```python
class Connection(BasedModel):
    """Relationship between two Things in the parse tree."""

    connection_class: ConnectionClass  # DIRECT, POSITIONAL, or LOOSE
    source_thing: str                  # Parent Thing name
    target_thing: str | None           # Child Thing name (None for Loose)
    role: str | None                   # Only for DIRECT connections

    # Constraints
    allows_multiple: bool = False      # Can connect to multiple targets
    requires_presence: bool = False    # Must be present

    # Significance
    is_significant: bool = True        # Meaningful vs whitespace/trivia
```

### 2.3 Token Classification

**Current**: "Tokens can be significant (like keywords and identifiers) or insignificant (like whitespace)"

**Gap**: Need clearer taxonomy of token types

**Recommendation**: Explicit token classification

```python
class TokenSignificance(BaseEnum):
    """Classification of token semantic importance."""
    STRUCTURAL = "structural"      # Keywords, operators, delimiters
    IDENTIFIER = "identifier"      # Variable/function/class names
    LITERAL = "literal"           # String/number/boolean values
    TRIVIA = "trivia"             # Whitespace, line continuations
    COMMENT = "comment"           # Code comments (significant but not code)

class Token(Thing):
    """Specialized Thing representing leaf nodes in the parse tree."""
    kind: Literal[ThingKind.TOKEN] = ThingKind.TOKEN
    significance: TokenSignificance

    # Tokens have no fields or children by definition
    connections: frozenset[Connection] = frozenset()
```

---

## 3. Hierarchy & Organization Issues

### 3.1 Thing Hierarchy

**Current**: Thing → Token (implied subtype)

**Recommendation**: Explicit hierarchy with clear distinction

```python
class Thing(BasedModel):
    """Base class for all concrete nodes in parse trees."""
    name: str
    kind: ThingKind
    categories: frozenset[str] = frozenset()
    is_explicit_rule: bool = True
    language: SemanticSearchLanguage

class Token(Thing):
    """Leaf node with no structural children."""
    kind: Literal[ThingKind.TOKEN] = ThingKind.TOKEN
    significance: TokenSignificance

    # Tokens cannot have Direct or Positional connections
    # (they can only appear as targets, or be Loose)

class CompositeNode(Thing):
    """Non-leaf node with structural children."""
    kind: Literal[ThingKind.COMPOSITE] = ThingKind.COMPOSITE
    direct_connections: frozenset[Connection]
    positional_connections: frozenset[Connection]

    @property
    def all_connections(self) -> frozenset[Connection]:
        """All Direct and Positional connections for this Thing."""
        return self.direct_connections | self.positional_connections
```

### 3.2 Connection Organization

**Current**: All three connection types treated equally in description

**Issue**: Direct connections are fundamentally different (have Roles)

**Recommendation**: Distinguish structurally

```python
class DirectConnection(BasedModel):
    """Named semantic relationship with a specific Role."""
    connection_class: Literal[ConnectionClass.DIRECT] = ConnectionClass.DIRECT
    role: str                          # REQUIRED - what makes it Direct
    source_thing: str
    target_things: frozenset[str]      # Allowed targets
    allows_multiple: bool = False
    requires_presence: bool = False

class PositionalConnection(BasedModel):
    """Ordered structural relationship without semantic naming."""
    connection_class: Literal[ConnectionClass.POSITIONAL] = ConnectionClass.POSITIONAL
    position: int | None               # Order in sequence (if known)
    source_thing: str
    target_things: frozenset[str]      # Allowed targets
    allows_multiple: bool = False
    requires_presence: bool = False

class LooseConnection(BasedModel):
    """Permissive relationship allowing appearance anywhere."""
    connection_class: Literal[ConnectionClass.LOOSE] = ConnectionClass.LOOSE
    thing_name: str                    # The Thing that can appear loosely
    is_significant: bool               # Comment vs whitespace
    # No source/target - can appear anywhere
```

---

## 4. Attribute Definitions Review

### 4.1 `is_explicit_rule`

**Current**: "Whether the Thing or Category has a corresponding named rule in the grammar"

**Issues**:
1. What does "corresponding" mean precisely?
2. How does this differ for Category vs Thing?

**Recommendation**: Split by context with precise definitions

```python
class Thing(BasedModel):
    """Concrete node in parse tree."""
    is_explicit_rule: Annotated[
        bool,
        Field(description="""
            Whether this Thing has a dedicated named production rule in the grammar.

            True: Defined via named grammar rule (appears in parse tree with semantic name)
            False: Anonymous grammar construct or synthesized node (may appear as unnamed)

            Example:
            - "function_definition" → True (named rule)
            - ";" punctuation → False (anonymous terminal)
        """)
    ]

class Category(BasedModel):
    """Abstract grouping of Things."""
    # Categories don't have is_explicit_rule - they're always abstract
    # The Things they contain may or may not have explicit rules
```

### 4.2 `is_significant`

**Current**: "Whether the Connection is significant"

**Issues**:
1. Significance applies to Things (tokens), not Connections
2. Needs clearer definition of "significant"

**Recommendation**: Move to Thing/Token level

```python
class Token(Thing):
    """Leaf node representing terminal in grammar."""
    is_significant: Annotated[
        bool,
        Field(description="""
            Whether this Token carries semantic or structural meaning.

            Significant (True): Keywords, identifiers, literals, operators, comments
            Insignificant (False): Whitespace, line continuations, formatting

            Insignificant tokens are often filtered during semantic analysis
            but required for precise code formatting/reconstruction.
        """)
    ]
```

### 4.3 `can_connect_multiple` → `allows_multiple`

**Current**: "Whether the Connection can connect to multiple child Things"

**Recommendation**: Clarify cardinality semantics

```python
allows_multiple: Annotated[
    bool,
    Field(description="""
        Whether this Connection permits multiple child Things of the specified type(s).

        True: Can have 0, 1, or many children (e.g., function parameters)
        False: Can have at most 1 child (e.g., function return_type)

        Note: This specifies the UPPER bound. For LOWER bounds, see requires_presence.
    """)
]
```

### 4.4 `requires_connection` → `requires_presence`

**Current**: "Whether the Thing must have at least one Connection from the list of possible Connections"

**Recommendation**: Clarify constraint semantics

```python
requires_presence: Annotated[
    bool,
    Field(description="""
        Whether at least one Connection of this type MUST be present.

        True: Parse tree MUST contain ≥1 of the specified child types
        False: Parse tree MAY contain 0 or more (optional)

        Combined with allows_multiple:
        - requires=True, multiple=False → exactly 1
        - requires=True, multiple=True → 1 or more
        - requires=False, multiple=False → 0 or 1
        - requires=False, multiple=True → 0 or more
    """)
]
```

---

## 5. Examples & Clarifications Needed

### 5.1 Complete Example: If Statement

```python
# Category
expression_category = Category(
    name="expression",
    member_things=frozenset([
        "binary_expression",
        "unary_expression",
        "identifier",
        "literal",
        # ... more
    ]),
    language=SemanticSearchLanguage.PYTHON
)

# Composite Thing
if_statement = CompositeNode(
    name="if_statement",
    kind=ThingKind.COMPOSITE,
    categories=frozenset(["statement"]),
    language=SemanticSearchLanguage.PYTHON,
    direct_connections=frozenset([
        DirectConnection(
            role="condition",
            source_thing="if_statement",
            target_things=frozenset(["expression"]),  # Category reference
            allows_multiple=False,
            requires_presence=True
        ),
        DirectConnection(
            role="consequence",
            source_thing="if_statement",
            target_things=frozenset(["block"]),
            allows_multiple=False,
            requires_presence=True
        ),
        DirectConnection(
            role="alternative",
            source_thing="if_statement",
            target_things=frozenset(["block", "if_statement"]),  # else or elif
            allows_multiple=False,
            requires_presence=False  # else is optional
        )
    ]),
    positional_connections=frozenset()  # No positional children
)

# Token Thing
if_keyword = Token(
    name="if",
    kind=ThingKind.TOKEN,
    significance=TokenSignificance.STRUCTURAL,
    language=SemanticSearchLanguage.PYTHON
)
```

### 5.2 Loose Connection Example

```python
# Loose connection for comments
comment_loose = LooseConnection(
    thing_name="comment",
    is_significant=True  # Comments are significant (vs whitespace)
)

# This means "comment" Things can appear as children of ANY parent Thing
# without being explicitly listed in that parent's connections
```

---

## 6. Recommended Revisions to Documentation

### 6.1 Opening Summary (Lines 10-20)

**Current**: Good background but terminology introduced too early

**Recommendation**: Lead with the problem, then the solution

```markdown
## Background

tl;dr: **This parser uses intuitive terminology for tree-sitter concepts that we found
confusing. If you're familiar with tree-sitter, see the translation guide below.**

Tree-sitter's `node-types.json` conflates several concepts in ways that aren't immediately
clear. It doesn't clearly differentiate between nodes and edges, and uses "named" to describe
both (meaning "has a grammar rule", not "has a name", which everything does). For AST/graph
work, this terminology creates unnecessary cognitive overhead.

We redesigned the terminology to clearly separate:
- **Things** (nodes/vertices) vs **Connections** (edges)
- **Categories** (abstract groupings) vs **Things** (concrete parse tree nodes)
- **Roles** (semantic function) vs structural position

This approach saved us weeks of confusion and makes the grammar structure intuitively clear.
```

### 6.2 Core Concepts Section (Lines 20-47)

**Recommendation**: Organize by abstraction level

```markdown
## Core Concepts

### Abstract Groupings

**Category** - High-level classification of Things with shared characteristics.
- Examples: `expression`, `statement`, `declaration`
- Do NOT appear in parse trees (abstract only)
- Used for type checking and classification
- Tree-sitter equivalent: nodes with `subtypes` field

### Concrete Parse Tree Nodes

**Thing** - A concrete element that appears in the parse tree.
- Two kinds: **Token** (leaf) or **Composite** (non-leaf)
- Tree-sitter equivalent: named or unnamed "nodes"

**Token** - Leaf Thing with no structural children.
- Represents keywords, identifiers, literals, punctuation
- Classified by significance: structural, identifier, literal, trivia, comment
- Tree-sitter equivalent: node with no fields

**Composite Node** - Non-leaf Thing with structural children.
- Has Direct and/or Positional connections to child Things
- Represents complex structures like functions, classes, expressions
- Tree-sitter equivalent: node with fields or children

### Structural Relationships

**Connection** - Relationship between a parent Thing and child Thing(s).
- Three classes: Direct, Positional, Loose
- Tree-sitter equivalent: fields (Direct), children (Positional), extras (Loose)

**ConnectionClass.DIRECT** - Named semantic relationship.
- Has a **Role** describing the child's purpose
- Examples: `condition` in if_statement, `parameters` in function_definition
- Tree-sitter equivalent: grammar "fields"

**ConnectionClass.POSITIONAL** - Ordered structural relationship.
- Position matters but no semantic role name
- Example: function arguments in some languages
- Tree-sitter equivalent: grammar "children"

**ConnectionClass.LOOSE** - Permissive relationship.
- Can appear anywhere in the tree without explicit declaration
- Used for comments, whitespace, other ambient elements
- Tree-sitter equivalent: "extra" nodes

**Role** - Named semantic function of a Direct connection.
- Only Direct connections have Roles
- Examples: "condition", "body", "parameters", "left", "right"
- Tree-sitter equivalent: field name in grammar
```

### 6.3 Attributes Section (Lines 38-47)

**Recommendation**: Group by what they describe

```markdown
## Attributes

### Thing Attributes

**is_explicit_rule** (bool)
- Whether the Thing has a dedicated named production rule in the grammar
- Tree-sitter equivalent: `named = True`
- **Note**: We nearly excluded this (limited utility) but kept for completeness

**is_significant** (bool, Token only)
- Whether the Token carries semantic/structural meaning vs formatting trivia
- True: keywords, identifiers, literals, operators, comments
- False: whitespace, line continuations
- Practically equivalent to `is_explicit_rule` but focuses on semantic importance

### Connection Attributes

**allows_multiple** (bool)
- Whether the Connection permits multiple children of specified type(s)
- Defines cardinality upper bound (0 or 1 vs 0 or many)
- Tree-sitter equivalent: `multiple = True/False`

**requires_presence** (bool)
- Whether at least one child of specified type(s) MUST be present
- Defines cardinality lower bound (0 or more vs 1 or more)
- Tree-sitter equivalent: `required = True/False`

### Cardinality Combinations

| requires | allows_multiple | Meaning |
|----------|----------------|---------|
| False | False | 0 or 1 (optional single) |
| False | True | 0 or more (optional multiple) |
| True | False | exactly 1 (required single) |
| True | True | 1 or more (required multiple) |
```

---

## 7. Implementation Checklist

### Phase 1: Core Types
- [ ] Define `ConnectionClass` enum (DIRECT, POSITIONAL, LOOSE)
- [ ] Define `ThingKind` enum (TOKEN, COMPOSITE)
- [ ] Define `TokenSignificance` enum (STRUCTURAL, IDENTIFIER, LITERAL, TRIVIA, COMMENT)
- [ ] Implement `Category` model
- [ ] Implement `Thing` base model
- [ ] Implement `Token` specialized model
- [ ] Implement `CompositeNode` specialized model

### Phase 2: Connection Models
- [ ] Implement `Connection` base (if using inheritance)
- [ ] Implement `DirectConnection` model with role
- [ ] Implement `PositionalConnection` model
- [ ] Implement `LooseConnection` model
- [ ] Add attribute validation (e.g., Direct must have role)

### Phase 3: Relationships
- [ ] Add Category → Things mapping
- [ ] Add Thing → Categories mapping (reverse)
- [ ] Add parent → child connection tracking
- [ ] Add connection cardinality validation

### Phase 4: Parsing Logic
- [ ] Parse tree-sitter `subtypes` → Categories
- [ ] Parse tree-sitter `fields` → DirectConnections
- [ ] Parse tree-sitter `children` → PositionalConnections
- [ ] Parse tree-sitter `extras` → LooseConnections
- [ ] Handle `named` attribute → `is_explicit_rule`
- [ ] Infer `TokenSignificance` from context

### Phase 5: Documentation
- [ ] Complete docstrings for all models
- [ ] Add usage examples for each concept
- [ ] Create tree-sitter translation guide
- [ ] Document cardinality semantics clearly

---

## 8. Questions to Resolve

1. **Category References**: When a Connection specifies target_things, can it reference Category names or only concrete Thing names?
   - **Recommendation**: Allow both, make it explicit in the type

2. **Multiple Categories**: Can a Thing belong to multiple Categories?
   - **Observation**: Yes, based on tree-sitter (e.g., some things are both `expression` and `statement`)

3. **Connection Storage**: Where should connections be stored?
   - **Recommendation**: On the source Thing (parent) as shown in CompositeNode

4. **Language-Specific**: Should models be language-aware?
   - **Recommendation**: Yes, include `language: SemanticSearchLanguage` field

5. **Validation**: Should we validate connection constraints (requires_presence, allows_multiple)?
   - **Recommendation**: Yes, add pydantic validators

6. **Token Hierarchy**: Should Token be separate class or Thing with kind=TOKEN?
   - **Recommendation**: Separate class (as shown) for type safety and clarity

---

## 9. Summary of Key Changes

### Terminology Improvements
| Old Term | Issue | New Term |
|----------|-------|----------|
| "Connection types" | Overloads "type" | `ConnectionClass` |
| "node_type" | Conflates name with type | `node_name` or `thing_name` |
| "Thing types" | Implicit, unclear | `ThingKind` enum |
| "role" | Underspecified | Enhanced with clear examples |
| Mixed attribute prefixes | Inconsistent | `is_*`, `has_*`, `allows_*`, `requires_*` |

### Conceptual Additions
- Explicit Category ↔ Thing relationship
- `ThingKind` enum (TOKEN, COMPOSITE)
- `TokenSignificance` classification
- `ConnectionClass` enum
- Separate DirectConnection/PositionalConnection/LooseConnection models
- Cardinality table (requires × allows_multiple)

### Structural Improvements
- Thing → Token/CompositeNode hierarchy
- Explicit connection directionality (source → target)
- Organized attributes by what they describe
- Clear examples for each concept

---

## 10. Final Recommendation

Your framework is **fundamentally sound** and significantly clearer than tree-sitter's terminology.
The main issues are:

1. **Terminology consistency** - Resolve "type" overloading
2. **Conceptual completeness** - Add missing classifications and relationships
3. **Documentation clarity** - Enhance definitions with examples and constraints

Implementing the recommendations above will create a robust, intuitive system that achieves
your goal of making tree-sitter grammars accessible and clear.

**Priority Order**:
1. Fix terminology (Section 1) - Critical for avoiding future confusion
2. Add missing concepts (Section 2) - Essential for completeness
3. Clarify attributes (Section 4) - Important for correct usage
4. Update documentation (Section 6) - Helps all users
5. Implement models (Section 7) - Follow the checklist

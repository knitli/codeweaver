<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Node Type Parser Implementation Specification

**Version**: 1.0.0
**Status**: IMPLEMENTED WITH MODIFICATIONS
**Based On**: Empirical analysis of 25 languages, 5,000+ node types

---

## 1. Overview

### 1.1 Purpose

Implement a parser for tree-sitter `node-types.json` files that uses intuitive terminology and explicitly models the relationships and constraints found in real grammar files.

### 1.2 Design Principles

1. **Clarity over Tradition** - Use intuitive names (Thing, Category, Connection) over tree-sitter jargon
2. **Explicit over Implicit** - Separate concepts that tree-sitter conflates (nodes vs edges, abstract vs concrete)
3. **Evidence-Based** - Design informed by empirical analysis, not assumptions
4. **Type-Safe** - Leverage Python's type system for validation and IDE support
5. **Bidirectional** - Maintain consistent relationships in both directions (Thing ↔ Category)

### 1.3 Empirical Foundations

**Category References** (Q1):
- 7.9% of field references are to Categories (761/9,606)
- 10.3% of children references are to Categories (621/6,029)
- **Design decision**: Support both Category and Concrete references in connections

**Multi-Category Membership** (Q2):
- 13.5% of Things belong to 2+ Categories (99/736)
- 86.5% belong to exactly 1 Category (637/736)
- Maximum: 5 categories (C++ `qualified_identifier`)
- **Design decision**: Use `frozenset[str]` for categories, optimize for single-category case

---

## 2. Core Type System

### 2.1 Enumerations

#### ConnectionClass

```python
class ConnectionClass(BaseEnum):
    """Classification of connection relationships between Things.

    Tree-sitter mapping:
    - DIRECT → fields (named semantic relationships)
    - POSITIONAL → children (ordered structural relationships)
    - LOOSE → extras (permissive relationships)
    """
    DIRECT = "direct"
    POSITIONAL = "positional"
    LOOSE = "loose"
```

**Rationale**: Replaces overloaded "field/children/extra" terminology with clear classification.

#### ThingKind

```python
class ThingKind(BaseEnum):
    """Classification of Things by structural characteristics.

    Tree-sitter mapping:
    - TOKEN → nodes with no fields/children (leaf nodes)
    - COMPOSITE → nodes with fields/children (non-leaf nodes)
    """
    TOKEN = "token"
    COMPOSITE = "composite"
```

**Rationale**: Makes the structural distinction explicit rather than inferred.

#### TokenSignificance

```python
class TokenSignificance(BaseEnum):
    """Semantic importance classification for Tokens.

    Used for filtering during semantic analysis vs preserving for formatting.
    """
    STRUCTURAL = "structural"    # Keywords, operators, delimiters
    IDENTIFIER = "identifier"    # Variable/function/class names
    LITERAL = "literal"          # String/number/boolean values
    TRIVIA = "trivia"            # Whitespace, line continuations
    COMMENT = "comment"          # Code comments
```

**Rationale**: Provides semantic classification beyond tree-sitter's binary "named" attribute.

### 2.2 Core Models

#### Category

```python
class Category(BasedModel):
    """Abstract grouping that doesn't appear in parse trees.

    Tree-sitter equivalent: Nodes with `subtypes` field.

    Attributes:
        name: Category identifier (e.g., "expression", "statement")
        language: Programming language this Category belongs to
        member_things: Set of concrete Thing names in this Category

    Relationships:
        - One Category → Many Things (via member_things)
        - Things reference Categories via their `categories` attribute

    Empirical findings:
        - ~110 unique Categories across 25 languages
        - Common across languages: expression (72%), statement (56%)
    """
    model_config = ConfigDict(frozen=True)

    name: Annotated[
        str,
        Field(description="Category identifier (e.g., 'expression', 'statement')")
    ]
    language: Annotated[
        SemanticSearchLanguage,
        Field(description="Programming language this Category belongs to")
    ]
    member_things: Annotated[
        frozenset[str],
        Field(
            description="""
            Set of concrete Thing names that belong to this Category.

            Note: A Thing can appear in multiple Categories' member_things sets.
            Average: 6.6 Things per Category.
            Range: 1-40 Things per Category.
            """,
            default_factory=frozenset
        )
    ]

    def includes(self, thing_name: str) -> bool:
        """Check if a Thing belongs to this Category."""
        return thing_name in self.member_things

    def overlap_with(self, other: Category) -> frozenset[str]:
        """Find Things that belong to both this Category and another.

        Used for analyzing multi-category membership patterns.
        """
        return self.member_things & other.member_things
```

#### Thing (Base)

```python
class Thing(BasedModel):
    """Base class for concrete nodes that appear in parse trees.

    Tree-sitter equivalent: Named or unnamed "nodes".

    Attributes:
        name: Thing identifier (e.g., "if_statement", "identifier")
        kind: Structural classification (TOKEN or COMPOSITE)
        language: Programming language this Thing belongs to
        categories: Set of Category names this Thing belongs to
        is_explicit_rule: Whether has named grammar rule

    Relationships:
        - Thing → Many Categories (via categories attribute)
        - Categories reference Things via their `member_things` attribute

    Empirical findings:
        - 736 Things with category membership
        - 13.5% belong to multiple Categories (99/736)
        - 86.5% belong to single Category (637/736)
    """
    model_config = ConfigDict(frozen=True)

    name: Annotated[
        str,
        Field(description="Thing identifier (e.g., 'if_statement', 'identifier')")
    ]
    kind: Annotated[
        ThingKind,
        Field(description="Structural classification: TOKEN or COMPOSITE")
    ]
    language: Annotated[
        SemanticSearchLanguage,
        Field(description="Programming language this Thing belongs to")
    ]
    categories: Annotated[
        frozenset[str],
        Field(
            description="""
            Set of Category names this Thing belongs to.

            Most Things (86.5%) belong to a single Category.
            Some Things (13.5%) belong to multiple Categories.
            Empty set indicates no category membership.

            Multi-category is common in C/C++ (declarators serving multiple roles).
            """,
            default_factory=frozenset
        )
    ]
    is_explicit_rule: Annotated[
        bool,
        Field(
            description="""
            Whether this Thing has a dedicated named production rule in the grammar.

            Tree-sitter: `named = True/False`
            True: Named grammar rule (appears with semantic name)
            False: Anonymous construct or synthesized node

            Note: Limited utility for semantic analysis; included for completeness.
            """,
            default=True
        )
    ]

    def is_in_category(self, category_name: str) -> bool:
        """Check if this Thing belongs to a specific Category."""
        return category_name in self.categories

    def is_multi_category(self) -> bool:
        """Check if this Thing belongs to multiple Categories."""
        return len(self.categories) > 1

    @property
    def primary_category(self) -> str | None:
        """Get primary (first alphabetically) category.

        Note: This is a heuristic. There's no inherent "primary" category
        in the grammar - all category memberships are equal.
        """
        return min(self.categories) if self.categories else None
```

#### Token

```python
class Token(Thing):
    """Leaf Thing with no structural children.

    Tree-sitter equivalent: Node with no `fields` or `children`.

    Attributes:
        kind: Always ThingKind.TOKEN
        significance: Semantic importance classification

    Characteristics:
        - What you literally see in source code
        - No Direct or Positional connections (only appears as target)
        - Can appear as Loose connection (e.g., comments, whitespace)
    """
    kind: Literal[ThingKind.TOKEN] = ThingKind.TOKEN

    significance: Annotated[
        TokenSignificance,
        Field(description="""
            Semantic importance classification.

            STRUCTURAL: Keywords, operators, delimiters (if, {, +)
            IDENTIFIER: Variable/function/class names
            LITERAL: String/number/boolean values
            TRIVIA: Whitespace, line continuations (insignificant)
            COMMENT: Code comments (significant but not code)

            Used for filtering: include STRUCTURAL/IDENTIFIER/LITERAL for semantic analysis,
            include all for formatting/reconstruction.
        """)
    ]
```

#### CompositeNode

```python
class CompositeNode(Thing):
    """Non-leaf Thing with structural children.

    Tree-sitter equivalent: Node with `fields` and/or `children`.

    Attributes:
        kind: Always ThingKind.COMPOSITE
        direct_connections: Named semantic relationships (fields)
        positional_connections: Ordered structural relationships (children)

    Characteristics:
        - Represents complex structures (functions, classes, expressions)
        - Has one or both types of connections to child Things

    Empirical findings:
        - Average 3-5 Direct connections per Composite
        - Average 1-2 Positional connections per Composite
    """
    kind: Literal[ThingKind.COMPOSITE] = ThingKind.COMPOSITE

    direct_connections: Annotated[
        frozenset[DirectConnection],
        Field(
            description="Named semantic relationships with Roles",
            default_factory=frozenset
        )
    ]

    positional_connections: Annotated[
        frozenset[PositionalConnection],
        Field(
            description="Ordered structural relationships without Roles",
            default_factory=frozenset
        )
    ]

    @property
    def all_connections(self) -> frozenset[Connection]:
        """All Direct and Positional connections for this Thing."""
        return self.direct_connections | self.positional_connections

    @property
    def roles(self) -> frozenset[str]:
        """All semantic Roles from Direct connections."""
        return frozenset(conn.role for conn in self.direct_connections)

    def get_connection_by_role(self, role: str) -> DirectConnection | None:
        """Get Direct connection by its Role name."""
        for conn in self.direct_connections:
            if conn.role == role:
                return conn
        return None
```

### 2.3 Connection Models

#### Connection (Base)

```python
class Connection(BasedModel):
    """Base class for relationships between Things.

    Represents directed edges in the parse tree graph: parent → child(ren).

    Attributes:
        connection_class: Classification (DIRECT, POSITIONAL, LOOSE)
        source_thing: Parent Thing name
        target_things: Set of allowed child Thing/Category names
        allows_multiple: Upper cardinality bound
        requires_presence: Lower cardinality bound

    Empirical findings:
        - Total connections: 15,635 across all languages
        - Direct (fields): 9,606 (61.4%)
        - Positional (children): 6,029 (38.6%)
        - Loose (extras): ~50-75 unique total
    """
    model_config = ConfigDict(frozen=True)

    connection_class: Annotated[
        ConnectionClass,
        Field(description="Classification: DIRECT, POSITIONAL, or LOOSE")
    ]

    source_thing: Annotated[
        str,
        Field(description="Parent Thing name (where connection originates)")
    ]

    target_things: Annotated[
        frozenset[str],
        Field(
            description="""
            Set of allowed child Thing or Category names.

            Can reference:
            - Category names (abstract) for polymorphic constraints
            - Concrete Thing names for specific requirements
            - Mix of both

            Empirical findings:
            - Fields: 7.9% Category refs, 92.1% Concrete refs
            - Children: 10.3% Category refs, 89.7% Concrete refs

            Examples:
            - frozenset(["expression"]) → Any expression type (polymorphic)
            - frozenset(["+", "-", "*", "/"]) → Specific operators (concrete)
            - frozenset(["block", "expression"]) → Either type (mixed)
            """
        )
    ]

    allows_multiple: Annotated[
        bool,
        Field(
            description="""
            Whether connection permits multiple children of specified types.

            Defines upper cardinality bound:
            - False: at most 1 child (0 or 1)
            - True: any number of children (0 or many)

            Tree-sitter: `multiple = True/False`
            """,
            default=False
        )
    ]

    requires_presence: Annotated[
        bool,
        Field(
            description="""
            Whether at least one child of specified types MUST be present.

            Defines lower cardinality bound:
            - False: child is optional (0 or more)
            - True: child is required (1 or more)

            Tree-sitter: `required = True/False`
            Note: Requires ≥1 from allowed list, not a specific child.
            """,
            default=False
        )
    ]

    @property
    def cardinality(self) -> tuple[int, int | None]:
        """Get cardinality as (min, max) tuple.

        Returns:
            (0, 1): optional single
            (0, None): optional multiple
            (1, 1): required single
            (1, None): required multiple
        """
        min_card = 1 if self.requires_presence else 0
        max_card = None if self.allows_multiple else 1
        return (min_card, max_card)
```

#### DirectConnection

```python
class DirectConnection(Connection):
    """Named semantic relationship with a Role.

    Tree-sitter equivalent: Grammar "fields".

    Attributes:
        connection_class: Always ConnectionClass.DIRECT
        role: Semantic function name (e.g., "condition", "body")

    Characteristics:
        - Most precise type of structural relationship
        - Role describes what purpose the child serves
        - Only Direct connections have Roles

    Empirical findings:
        - ~90 unique role names across all languages
        - Most common: name (381), body (281), type (217), condition (102)
        - Average 3-5 Direct connections per Composite Thing
    """
    connection_class: Literal[ConnectionClass.DIRECT] = ConnectionClass.DIRECT

    role: Annotated[
        str,
        Field(
            description="""
            Semantic function name describing child's purpose.

            Examples:
            - "condition": in if_statement (what to evaluate)
            - "body": in function_definition (what to execute)
            - "parameters": in function_definition (what arguments)
            - "left", "right": in binary_expression (operands)
            - "operator": in binary_expression (operation type)

            Only Direct connections have Roles.
            Positional and Loose connections do not.
            """
        )
    ]
```

#### PositionalConnection

```python
class PositionalConnection(Connection):
    """Ordered structural relationship without semantic naming.

    Tree-sitter equivalent: Grammar "children".

    Attributes:
        connection_class: Always ConnectionClass.POSITIONAL
        position: Optional order in sequence

    Characteristics:
        - Order matters but no explicit role name
        - Common in languages with positional syntax
        - Less precise than Direct connections

    Empirical findings:
        - 6,029 Positional connections across all languages
        - 10.3% reference Categories (polymorphic)
        - Average 1-2 Positional connections per Composite Thing
    """
    connection_class: Literal[ConnectionClass.POSITIONAL] = ConnectionClass.POSITIONAL

    position: Annotated[
        int | None,
        Field(
            description="""
            Optional position in ordered sequence.

            None if order is enforced by grammar but not explicitly numbered.
            Used when position has semantic meaning (e.g., first argument vs second).
            """,
            default=None
        )
    ]
```

#### LooseConnection

```python
class LooseConnection(BasedModel):
    """Permissive relationship allowing appearance anywhere.

    Tree-sitter equivalent: "extra" nodes.

    Attributes:
        connection_class: Always ConnectionClass.LOOSE
        thing_name: The Thing that can appear loosely
        is_significant: Whether semantically meaningful

    Characteristics:
        - Describes permission, not structure
        - Can appear in any context without explicit declaration
        - Typically: comments, whitespace, ambient elements

    Empirical findings:
        - ~2-3 Loose types per language
        - Most common: comment, whitespace variants
        - Pattern: 1 significant (comment), 1-2 insignificant (whitespace)
    """
    model_config = ConfigDict(frozen=True)

    connection_class: Literal[ConnectionClass.LOOSE] = ConnectionClass.LOOSE

    thing_name: Annotated[
        str,
        Field(description="Thing name that can appear anywhere in parse tree")
    ]

    is_significant: Annotated[
        bool,
        Field(
            description="""
            Whether this Loose Thing carries semantic meaning.

            True: Comments (significant but not code)
            False: Whitespace, line continuations (formatting only)

            Used for filtering in semantic analysis.
            """
        )
    ]
```

---

## 3. Type Aliases and Utilities

### 3.1 Type Aliases

```python
# Convenient type aliases for common patterns
type CategoryMap = dict[str, Category]
type ThingMap = dict[str, Thing]
type ConnectionSet = frozenset[DirectConnection | PositionalConnection]

# For cardinality specifications
type Cardinality = tuple[int, int | None]  # (min, max)
```

### 3.2 Utility Functions

#### Reference Resolution

```python
def resolve_target_types(
    target_refs: frozenset[str],
    category_map: CategoryMap
) -> frozenset[str]:
    """Resolve Category references to concrete Thing names.

    Expands Categories to their member Things, leaves concrete references as-is.

    Args:
        target_refs: Set of Category or Thing names
        category_map: Mapping of Category names to Category objects

    Returns:
        Set of all concrete Thing names that satisfy the target references

    Example:
        >>> resolve_target_types(
        ...     frozenset(["expression", "identifier"]),
        ...     {"expression": Category(members=["binary_expr", "unary_expr"])}
        ... )
        frozenset(["binary_expr", "unary_expr", "identifier"])
    """
    concrete_types = set()
    for ref in target_refs:
        if ref in category_map:
            # Category reference - expand to all members
            concrete_types.update(category_map[ref].member_things)
        else:
            # Concrete Thing reference
            concrete_types.add(ref)
    return frozenset(concrete_types)


def classify_reference(
    ref_name: str,
    category_map: CategoryMap
) -> Literal["category", "concrete"]:
    """Classify a reference as Category or Concrete Thing.

    Args:
        ref_name: Name to classify
        category_map: Mapping of Category names to Category objects

    Returns:
        "category" if ref_name is a Category, "concrete" otherwise
    """
    return "category" if ref_name in category_map else "concrete"
```

#### Validation

```python
def validate_category_consistency(
    things: ThingMap,
    categories: CategoryMap
) -> list[str]:
    """Validate bidirectional Thing ↔ Category relationships.

    Checks:
    1. Thing → Category references are valid (Category exists)
    2. Category → Thing references are valid (Thing exists)
    3. Bidirectional consistency (if A→B then B→A)

    Args:
        things: Mapping of Thing names to Thing objects
        categories: Mapping of Category names to Category objects

    Returns:
        List of validation errors (empty if consistent)

    Example errors:
        - "Thing 'foo' references unknown Category 'bar'"
        - "Category 'expr' references unknown Thing 'baz'"
        - "Inconsistency: Category 'expr' lists 'foo', but 'foo' doesn't list 'expr'"
    """
    errors = []

    # Check Thing → Category references are valid
    for thing_name, thing in things.items():
        for cat_name in thing.categories:
            if cat_name not in categories:
                errors.append(f"Thing '{thing_name}' references unknown Category '{cat_name}'")

    # Check Category → Thing references are valid and consistent
    for cat_name, category in categories.items():
        for thing_name in category.member_things:
            if thing_name not in things:
                errors.append(f"Category '{cat_name}' references unknown Thing '{thing_name}'")
            elif cat_name not in things[thing_name].categories:
                errors.append(
                    f"Inconsistency: Category '{cat_name}' lists '{thing_name}' as member, "
                    f"but '{thing_name}' doesn't list '{cat_name}' in its categories"
                )

    return errors


def validate_connection_references(
    connections: ConnectionSet,
    things: ThingMap,
    categories: CategoryMap
) -> list[str]:
    """Validate that connection target references are valid.

    Checks:
    1. Source Thing exists
    2. Target references exist (as Thing or Category)
    3. Connections from Tokens are invalid (Tokens can't have children)

    Args:
        connections: Set of connections to validate
        things: Mapping of Thing names to Thing objects
        categories: Mapping of Category names to Category objects

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    for conn in connections:
        # Check source exists
        if conn.source_thing not in things:
            errors.append(f"Connection source '{conn.source_thing}' not found")
            continue

        # Check source is not a Token (Tokens can't have children)
        if things[conn.source_thing].kind == ThingKind.TOKEN:
            errors.append(f"Token '{conn.source_thing}' cannot have connections")

        # Check targets exist
        for target in conn.target_things:
            if target not in things and target not in categories:
                errors.append(
                    f"Connection target '{target}' not found "
                    f"(from '{conn.source_thing}')"
                )

    return errors
```

---

## 4. Parsing Logic

### 4.1 Parser Structure

```python
class NodeTypeParser(BasedModel):
    """Parser for tree-sitter node-types.json files.

    Converts tree-sitter's flattened JSON structure into our explicit,
    typed model with Categories, Things, and Connections.
    """

    node_types_dir: DirectoryPath

    # Parsed data
    _categories: dict[SemanticSearchLanguage, CategoryMap] = PrivateAttr(default_factory=dict)
    _things: dict[SemanticSearchLanguage, ThingMap] = PrivateAttr(default_factory=dict)
    _loose_connections: dict[SemanticSearchLanguage, set[LooseConnection]] = PrivateAttr(default_factory=dict)

    def parse_language(self, language: SemanticSearchLanguage) -> None:
        """Parse node-types.json for a specific language.

        Populates _categories, _things, and _loose_connections for the language.
        """
        # Implementation in next section
        pass
```

### 4.2 Parsing Steps

#### Step 1: Load and Identify Language

```python
def _load_node_types_json(self, language: SemanticSearchLanguage) -> list[dict[str, Any]]:
    """Load node-types.json file for a language.

    Returns:
        List of raw node type dictionaries from JSON
    """
    file_path = self.node_types_dir / f"{language.value}-node-types.json"
    with file_path.open() as f:
        return json.load(f)
```

#### Step 2: First Pass - Identify Categories

```python
def _extract_categories(
    self,
    raw_nodes: list[dict[str, Any]],
    language: SemanticSearchLanguage
) -> CategoryMap:
    """Extract Categories from nodes with 'subtypes' field.

    First pass: Identify all abstract types (Categories).

    Args:
        raw_nodes: Raw node type dictionaries
        language: Programming language

    Returns:
        Mapping of Category names to Category objects
    """
    categories = {}

    for node in raw_nodes:
        if "subtypes" in node:
            # This is a Category (abstract type)
            cat_name = node["type"]
            member_names = frozenset(
                subtype["type"]
                for subtype in node["subtypes"]
            )

            categories[cat_name] = Category(
                name=cat_name,
                language=language,
                member_things=member_names
            )

    return categories
```

#### Step 3: Build Category Membership Map

```python
def _build_category_membership(
    self,
    categories: CategoryMap
) -> dict[str, frozenset[str]]:
    """Build reverse mapping: Thing name → Category names.

    Args:
        categories: Mapping of Category names to Category objects

    Returns:
        Mapping of Thing names to set of Category names they belong to
    """
    membership = defaultdict(set)

    for cat_name, category in categories.items():
        for thing_name in category.member_things:
            membership[thing_name].add(cat_name)

    return {
        thing_name: frozenset(cats)
        for thing_name, cats in membership.items()
    }
```

#### Step 4: Second Pass - Extract Things

```python
def _extract_things(
    self,
    raw_nodes: list[dict[str, Any]],
    language: SemanticSearchLanguage,
    category_membership: dict[str, frozenset[str]]
) -> ThingMap:
    """Extract Things from node entries.

    Second pass: Create Thing objects for concrete types.

    Args:
        raw_nodes: Raw node type dictionaries
        language: Programming language
        category_membership: Thing name → Category names mapping

    Returns:
        Mapping of Thing names to Thing objects
    """
    things = {}

    for node in raw_nodes:
        # Skip Categories (already processed)
        if "subtypes" in node:
            continue

        thing_name = node["type"]
        is_named = node.get("named", False)
        categories = category_membership.get(thing_name, frozenset())

        # Determine if Token or Composite
        has_structure = "fields" in node or "children" in node

        if not has_structure:
            # Token (leaf node)
            significance = self._infer_token_significance(thing_name, is_named)
            things[thing_name] = Token(
                name=thing_name,
                language=language,
                categories=categories,
                is_explicit_rule=is_named,
                significance=significance
            )
        else:
            # Composite Node
            direct_conns = self._extract_direct_connections(node, thing_name)
            pos_conns = self._extract_positional_connections(node, thing_name)

            things[thing_name] = CompositeNode(
                name=thing_name,
                language=language,
                categories=categories,
                is_explicit_rule=is_named,
                direct_connections=frozenset(direct_conns),
                positional_connections=frozenset(pos_conns)
            )

    return things
```

#### Step 5: Extract Connections

```python
def _extract_direct_connections(
    self,
    node: dict[str, Any],
    source_name: str
) -> list[DirectConnection]:
    """Extract Direct connections from 'fields' in node.

    Tree-sitter: fields = {role_name: {types: [...], required: bool, multiple: bool}}
    """
    connections = []

    fields = node.get("fields", {})
    for role, field_info in fields.items():
        target_types = frozenset(
            t["type"]
            for t in field_info.get("types", [])
        )

        connections.append(DirectConnection(
            role=role,
            source_thing=source_name,
            target_things=target_types,
            requires_presence=field_info.get("required", False),
            allows_multiple=field_info.get("multiple", False)
        ))

    return connections


def _extract_positional_connections(
    self,
    node: dict[str, Any],
    source_name: str
) -> list[PositionalConnection]:
    """Extract Positional connections from 'children' in node.

    Tree-sitter: children = {types: [...], required: bool, multiple: bool}
    """
    children = node.get("children")
    if not children:
        return []

    target_types = frozenset(
        t["type"]
        for t in children.get("types", [])
    )

    return [PositionalConnection(
        source_thing=source_name,
        target_things=target_types,
        requires_presence=children.get("required", False),
        allows_multiple=children.get("multiple", False),
        position=None  # Tree-sitter doesn't specify position
    )]
```

#### Step 6: Extract Loose Connections

```python
def _extract_loose_connections(
    self,
    raw_nodes: list[dict[str, Any]]
) -> set[LooseConnection]:
    """Extract Loose connections from nodes with 'extra' field.

    Tree-sitter: {type: "...", extra: true, named: bool}
    """
    loose = set()

    for node in raw_nodes:
        if node.get("extra", False):
            thing_name = node["type"]
            is_significant = self._is_significant_loose(thing_name)

            loose.add(LooseConnection(
                thing_name=thing_name,
                is_significant=is_significant
            ))

    return loose
```

### 4.3 Inference Heuristics

```python
def _infer_token_significance(
    self,
    token_name: str,
    is_named: bool
) -> TokenSignificance:
    """Infer TokenSignificance from token name and tree-sitter 'named' flag.

    Heuristics based on common patterns across languages.
    """
    # Comment patterns
    if "comment" in token_name.lower():
        return TokenSignificance.COMMENT

    # Whitespace patterns
    if any(w in token_name.lower() for w in ["whitespace", "newline", "line_continuation"]):
        return TokenSignificance.TRIVIA

    # Identifier patterns
    if "identifier" in token_name.lower() or token_name == "name":
        return TokenSignificance.IDENTIFIER

    # Literal patterns
    if any(lit in token_name.lower() for lit in ["literal", "string", "number", "boolean"]):
        return TokenSignificance.LITERAL

    # Operators and keywords (usually not named)
    if not is_named or len(token_name) <= 2:
        return TokenSignificance.STRUCTURAL

    # Default for named tokens
    return TokenSignificance.IDENTIFIER if is_named else TokenSignificance.STRUCTURAL


def _is_significant_loose(self, thing_name: str) -> bool:
    """Determine if a Loose connection Thing is semantically significant.

    True: comments
    False: whitespace, line continuations
    """
    return "comment" in thing_name.lower()
```

---

## 5. API Design

### 5.1 Primary Interface

```python
class NodeTypeParser:
    """Public API for accessing parsed grammar information."""

    def get_category(
        self,
        category_name: str,
        language: SemanticSearchLanguage
    ) -> Category | None:
        """Get Category by name for a language."""
        return self._categories.get(language, {}).get(category_name)

    def get_thing(
        self,
        thing_name: str,
        language: SemanticSearchLanguage
    ) -> Thing | None:
        """Get Thing by name for a language."""
        return self._things.get(language, {}).get(thing_name)

    def get_loose_connections(
        self,
        language: SemanticSearchLanguage
    ) -> frozenset[LooseConnection]:
        """Get all Loose connections for a language."""
        return frozenset(self._loose_connections.get(language, set()))

    def get_all_categories(
        self,
        language: SemanticSearchLanguage
    ) -> frozenset[Category]:
        """Get all Categories for a language."""
        return frozenset(self._categories.get(language, {}).values())

    def get_all_things(
        self,
        language: SemanticSearchLanguage
    ) -> frozenset[Thing]:
        """Get all Things for a language."""
        return frozenset(self._things.get(language, {}).values())

    def find_things_in_category(
        self,
        category_name: str,
        language: SemanticSearchLanguage
    ) -> frozenset[Thing]:
        """Find all Things belonging to a Category."""
        category = self.get_category(category_name, language)
        if not category:
            return frozenset()

        things = self._things.get(language, {})
        return frozenset(
            things[name]
            for name in category.member_things
            if name in things
        )

    def find_multi_category_things(
        self,
        language: SemanticSearchLanguage
    ) -> frozenset[Thing]:
        """Find all Things belonging to multiple Categories.

        Based on empirical finding: 13.5% of Things are multi-category.
        """
        return frozenset(
            thing
            for thing in self.get_all_things(language)
            if thing.is_multi_category()
        )
```

### 5.2 Query Interface

```python
class NodeTypeParser:
    """Advanced query methods."""

    def resolve_connection_targets(
        self,
        connection: DirectConnection | PositionalConnection,
        language: SemanticSearchLanguage
    ) -> frozenset[Thing]:
        """Resolve connection targets to concrete Thing objects.

        Expands Category references to their member Things.
        """
        categories = self._categories.get(language, {})
        things = self._things.get(language, {})

        concrete_names = resolve_target_types(
            connection.target_things,
            categories
        )

        return frozenset(
            things[name]
            for name in concrete_names
            if name in things
        )

    def get_connections_by_role(
        self,
        role: str,
        language: SemanticSearchLanguage
    ) -> frozenset[DirectConnection]:
        """Find all Direct connections with a specific Role.

        Useful for analyzing role usage patterns across Things.
        """
        connections = set()
        for thing in self.get_all_things(language):
            if isinstance(thing, CompositeNode):
                for conn in thing.direct_connections:
                    if conn.role == role:
                        connections.add(conn)
        return frozenset(connections)

    def get_polymorphic_connections(
        self,
        language: SemanticSearchLanguage
    ) -> frozenset[DirectConnection | PositionalConnection]:
        """Find all connections that reference Categories (polymorphic).

        Based on empirical finding: 7.9% of field refs, 10.3% of children refs.
        """
        categories = self._categories.get(language, {})
        connections = set()

        for thing in self.get_all_things(language):
            if isinstance(thing, CompositeNode):
                for conn in thing.all_connections:
                    # Check if any target is a Category
                    if any(target in categories for target in conn.target_things):
                        connections.add(conn)

        return frozenset(connections)
```

---

## 6. Validation and Testing

### 6.1 Validation Rules

**Category Validation**:
1. All `member_things` must reference existing Things
2. No Category should be empty (unless explicitly allowed)

**Thing Validation**:
1. All `categories` must reference existing Categories
2. Bidirectional consistency: if Thing→Category then Category→Thing
3. Tokens cannot have connections (only Composites)
4. Composite must have at least one connection (direct or positional)

**Connection Validation**:
1. `source_thing` must exist
2. All `target_things` must exist (as Thing or Category)
3. At least one target must be specified
4. Direct connections must have non-empty `role`

**Cardinality Validation**:
1. If `requires_presence=True`, at least one target must be possible
2. `allows_multiple=True` typically means `len(target_things) > 1` or Category reference

### 6.2 Test Cases

```python
def test_category_thing_bidirectional():
    """Test bidirectional Category ↔ Thing consistency."""
    # Setup
    category = Category(name="expression", language=PYTHON, member_things=frozenset(["binary_expr"]))
    thing = CompositeNode(name="binary_expr", language=PYTHON, categories=frozenset(["expression"]))

    # Verify
    assert "binary_expr" in category.member_things
    assert "expression" in thing.categories
    assert category.includes("binary_expr")
    assert thing.is_in_category("expression")


def test_multi_category_thing():
    """Test Thing belonging to multiple Categories."""
    # C identifier: both declarator and expression
    thing = Token(
        name="identifier",
        language=C,
        categories=frozenset(["_declarator", "expression"]),
        significance=TokenSignificance.IDENTIFIER
    )

    assert thing.is_multi_category()
    assert len(thing.categories) == 2


def test_polymorphic_connection():
    """Test connection referencing Category (polymorphic constraint)."""
    conn = DirectConnection(
        role="condition",
        source_thing="if_statement",
        target_things=frozenset(["expression"]),  # Category reference
        requires_presence=True
    )

    # Should accept any expression type
    assert "expression" in conn.target_things


def test_cardinality_matrix():
    """Test all four cardinality combinations."""
    # (0, 1) - optional single
    conn1 = DirectConnection(role="alternative", source_thing="if_statement",
                            target_things=frozenset(["block"]),
                            requires_presence=False, allows_multiple=False)
    assert conn1.cardinality == (0, 1)

    # (0, None) - optional multiple
    conn2 = PositionalConnection(source_thing="array",
                                 target_things=frozenset(["expression"]),
                                 requires_presence=False, allows_multiple=True)
    assert conn2.cardinality == (0, None)

    # (1, 1) - required single
    conn3 = DirectConnection(role="condition", source_thing="if_statement",
                            target_things=frozenset(["expression"]),
                            requires_presence=True, allows_multiple=False)
    assert conn3.cardinality == (1, 1)

    # (1, None) - required multiple
    conn4 = DirectConnection(role="parameters", source_thing="function_def",
                            target_things=frozenset(["parameter"]),
                            requires_presence=True, allows_multiple=True)
    assert conn4.cardinality == (1, None)
```

---

## 7. Implementation Plan

### Phase 1: Core Types (Week 1)
- [ ] Define all enums (ConnectionClass, ThingKind, TokenSignificance)
- [ ] Implement Category model
- [ ] Implement Thing base, Token, CompositeNode
- [ ] Implement Connection base, DirectConnection, PositionalConnection, LooseConnection
- [ ] Unit tests for model instantiation and basic methods

### Phase 2: Parsing Logic (Week 2)
- [ ] Implement NodeTypeParser structure
- [ ] Implement Category extraction (first pass)
- [ ] Implement Thing extraction (second pass)
- [ ] Implement Connection extraction
- [ ] Implement inference heuristics
- [ ] Integration tests with sample node-types.json

### Phase 3: Validation (Week 3)
- [ ] Implement `validate_category_consistency()`
- [ ] Implement `validate_connection_references()`
- [ ] Add validation to parser workflow
- [ ] Comprehensive validation tests

### Phase 4: API & Utilities (Week 4)
- [ ] Implement query interface methods
- [ ] Implement `resolve_target_types()`
- [ ] Implement analysis utilities
- [ ] API documentation and examples

### Phase 5: Testing & Documentation (Week 5)
- [ ] Test against all 25 language grammars
- [ ] Verify empirical findings (Q1 & Q2 percentages)
- [ ] Performance benchmarks
- [ ] Complete API documentation
- [ ] Usage examples and cookbook

---

## 8. Success Criteria

### Functional Requirements
- ✅ Parse all 25 language grammars without errors
- ✅ Correctly identify Categories (abstract types with subtypes)
- ✅ Correctly classify Things (Token vs Composite)
- ✅ Extract all Direct, Positional, and Loose connections
- ✅ Maintain bidirectional Category ↔ Thing consistency
- ✅ Support both Category and Concrete target references

### Empirical Validation
- ✅ Category references: ~7-10% of total (matches Q1 findings)
- ✅ Multi-category Things: ~13.5% of total (matches Q2 findings)
- ✅ ~110 unique Categories across all languages
- ✅ ~90 unique role names across all languages

### Quality Requirements
- ✅ 100% type-checked with pyright (strict mode)
- ✅ All validation rules enforced
- ✅ Comprehensive test coverage (focus on behavior, not lines)
- ✅ Clear error messages for malformed input
- ✅ Performance: parse all 25 languages in <5 seconds

### Documentation Requirements
- ✅ Complete API documentation with examples
- ✅ Translation guide for tree-sitter experts
- ✅ Design rationale explaining terminology choices
- ✅ Cookbook with common usage patterns

---

## 9. Open Questions

1. **Caching Strategy**: Should we cache parsed results? Where?
   - **Decision needed**: In-memory only, or serialize to disk?

2. **Versioning**: How to handle different tree-sitter grammar versions?
   - **Decision needed**: Include version in model? Warn on mismatch?

3. **Extensibility**: Should users be able to add custom attributes to models?
   - **Decision needed**: Use `extra="allow"` in ConfigDict? Or strict?

4. **Performance**: Is frozen/immutable required, or can we use mutable for speed?
   - **Current**: frozen=True for safety
   - **Alternative**: Mutable with validation

5. **Language Detection**: Should we auto-detect language from filename?
   - **Current**: Explicit language parameter
   - **Alternative**: Auto-detect from "typescript-node-types.json"

---

## 10. References

- **Empirical Analysis**: `claudedocs/grammar_structure_analysis.md`
- **Q1 & Q2 Findings**: `claudedocs/q1_q2_analysis_and_recommendations.md`
- **Original Review**: `claudedocs/new_node_type_parser_review.md`
- **Module Documentation**: `src/codeweaver/semantic/new_node_type_parser.py` (docstring)
- **Tree-sitter Docs**: https://tree-sitter.github.io/tree-sitter/using-parsers#static-node-types

---

**Document Status**: Ready for implementation review and refinement.
**Next Steps**: Review with team, address open questions, begin Phase 1 implementation.

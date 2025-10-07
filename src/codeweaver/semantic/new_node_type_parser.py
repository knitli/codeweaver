# sourcery skip: lambdas-should-be-short
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
- **Tree-sitter equivalent**: Named or unnamed "nodes" (named does not correlate to our Composite vs Token distinction)
- Name chosen for clarity: "it's a thing in your code" (considered: Entity, Element, Construct)

**Token** - Leaf Thing with no structural children.
- Represents keywords, identifiers, literals, punctuation
- What you literally **see** in the source code
- Classified by significance: structural, identifier, literal, trivial, comment
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
   - If a thing has fields, it can also have children, but not vice versa (all things with children have fields)
   - All children are named (is_explicit_rule = True)
   - **Empirical finding**: 6,029 Positional connections across all languages


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

- **can_be_anywhere** (bool)
    - Whether the Thing can appear anywhere in the parse tree (usually comments)
    - **Tree-sitter equivalent**: the `extra` attribute
    Data notes:
   - Only used in a plurality of languages (11 of 25)
   - *almost always* a **comment**. Two exceptions:
        - Python: `line_continuation` token (1/2, other is `comment`)
        - PHP: `text_interpolation` (1/2, other is `comment`)
   - **Empirical finding**: 1 or 2 Loose types per language ('comment' is one for all 11)

- **is_explicit_rule** (bool)
  - Whether the Thing has a dedicated named production rule in the grammar
  - True: Named grammar rule (appears with semantic name)
  - False: Anonymous grammar construct or synthesized node
  - **Tree-sitter equivalent**: `named = True/False`
  - **Note**: Included for completeness; limited practical utility for semantic analysis

- **kind** (ThingKind enum)
  - Classification of Thing type: TOKEN or COMPOSITE
  - TOKEN: Leaf Thing with no structural children
  - COMPOSITE: Non-leaf Thing with structural children

- **is_start** (bool, Composite only)
  - Whether this Composite is the root of the parse tree (i.e., the start symbol)

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
| 'root' attribute | `is_start` | The starting node of the parse tree |

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

from __future__ import annotations

import logging

from enum import Flag, auto
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Any, ClassVar, Literal, NewType, TypedDict

from pydantic import (
    ConfigDict,
    DirectoryPath,
    Field,
    FilePath,
    NonNegativeInt,
    computed_field,
    field_validator,
)
from pydantic_core import from_json

from codeweaver._common import BasedModel, BaseEnum, LiteralStringT
from codeweaver.language import SemanticSearchLanguage


logger = logging.getLogger()

Role = NewType("Role", LiteralStringT)
CategoryName = NewType("CategoryName", LiteralStringT)
ThingName = NewType("ThingName", LiteralStringT)
TokenName = NewType("TokenName", LiteralStringT)

NAMED_NODE_COUNTS = MappingProxyType({
    231: SemanticSearchLanguage.C_PLUS_PLUS,
    221: SemanticSearchLanguage.C_SHARP,
    192: SemanticSearchLanguage.TYPESCRIPT,
    188: SemanticSearchLanguage.HASKELL,
    183: SemanticSearchLanguage.SWIFT,
    170: SemanticSearchLanguage.RUST,
    162: SemanticSearchLanguage.PHP,
    152: SemanticSearchLanguage.JAVA,
    150: SemanticSearchLanguage.RUBY,
    149: SemanticSearchLanguage.SCALA,
    133: SemanticSearchLanguage.C_LANG,
    130: SemanticSearchLanguage.PYTHON,
    125: SemanticSearchLanguage.SOLIDITY,
    121: SemanticSearchLanguage.KOTLIN,
    120: SemanticSearchLanguage.JAVASCRIPT,
    113: SemanticSearchLanguage.GO,
    65: SemanticSearchLanguage.CSS,
    63: SemanticSearchLanguage.BASH,
    51: SemanticSearchLanguage.LUA,
    46: SemanticSearchLanguage.ELIXIR,
    43: SemanticSearchLanguage.NIX,
    20: SemanticSearchLanguage.HTML,
    14: SemanticSearchLanguage.JSON,
    6: SemanticSearchLanguage.YAML,
})
"""Count of top-level named nodes in each language's grammar. It took me awhile to come to this approach, but it's fast, reliable, and way less complicated than anything else I tried.

The only potential issue is if the nodes are not a complete set.
"""


class AllThingsDict(TypedDict):
    """TypedDict for all Things and Tokens in a grammar."""

    composite_things: dict[ThingName, CompositeThing]
    tokens: dict[TokenName, Token]


class ConnectionClass(BaseEnum):
    """Classification of connections between Things in a parse tree.

    Tree-Sitter mapping:
    - DIRECT -> fields: Named semantic relationship **with a Role**
    - POSITIONAL -> children: Ordered structural relationship without semantic naming
    """

    DIRECT = "direct"
    POSITIONAL = "positional"

    @property
    def is_direct(self) -> bool:
        """Whether this connection class is DIRECT (fields)."""
        return self is ConnectionClass.DIRECT

    @property
    def is_positional(self) -> bool:
        """Whether this connection class is POSITIONAL (children)."""
        return self is ConnectionClass.POSITIONAL

    @property
    def allows_role(self) -> bool:
        """Whether this connection class allows a Role.

        Only DIRECT connections have Roles; POSITIONAL does not.
        """
        return self.is_direct


class ThingKind(BaseEnum):
    """Classification of Thing types in a parse tree. Things are concrete nodes, that is, what actually exists in the parse tree.

    Tree-Sitter mapping:
    - TOKEN -> nodes with no fields/children (leaf nodes): Leaf Thing with no structural children
    - COMPOSITE -> nodes with fields/children (non-leaf nodes): Non-leaf Thing with structural children

    A TOKEN represents keywords, identifiers, literals, and punctuation -- what you literally see in the source code. A COMPOSITE node represents complex structures like functions, classes, and expressions, which have direct and/or positional connections to child Things.
    """

    TOKEN = "token"  # noqa: S105  # false positive: "token" is not a hardcoded security token
    COMPOSITE = "composite"


class TokenSignificance(BaseEnum):
    """Classification of Token significance.

    Tree-Sitter mapping:
    - STRUCTURAL: keywords, operators, punctuation
    - IDENTIFIER: variable/function/type names
    - LITERAL: string/number/boolean literals
    - TRIVIAL: whitespace, formatting tokens
    - COMMENT: comments

    A Token can be classified by its significance, indicating whether it carries semantic or structural meaning versus being mere formatting trivia. This classification helps in filtering Tokens during semantic analysis while preserving them for formatting purposes.
    """

    STRUCTURAL = "structural"
    IDENTIFIER = "identifier"
    LITERAL = "literal"
    TRIVIAL = "trivial"
    COMMENT = "comment"

    @property
    def is_significant(self) -> bool:
        """Whether this TokenSignificance indicates a significant Token.

        Significant Tokens carry semantic/structural meaning, while trivial ones do not.
        """
        return self in {
            TokenSignificance.STRUCTURAL,
            TokenSignificance.IDENTIFIER,
            TokenSignificance.LITERAL,
            TokenSignificance.COMMENT,
        }

    @property
    def is_trivial(self) -> bool:
        """Whether this TokenSignificance indicates a trivial Token.

        Trivial Tokens do not carry semantic/structural meaning.
        """
        return self is TokenSignificance.TRIVIAL

    @property
    def identifies(self) -> bool:
        """Whether this TokenSignificance indicates an identifying Token.

        Identifying Tokens are used for names of variables, functions, types, etc.
        """
        return self in {TokenSignificance.IDENTIFIER, TokenSignificance.LITERAL}


class Thing(BasedModel):
    """Base class for Things (Things and Tokens -- also called Composites and Tokens)).

    There are two kinds of Things: Token (leaf) or Composite (non-leaf). Things are what you actually see in the AST produced by parsing code. A token is what you literally see in the source code (keywords, identifiers, literals, punctuation). A Composite represents complex structures like functions, classes, and expressions, which have direct and/or positional connections to child Things.

    We keep Token as a separate class for clarity, type safety, and to enforce that Tokens cannot have children.

    """

    model_config = BasedModel.model_config | ConfigDict(frozen=True)

    name: Annotated[ThingName | TokenName, Field(description="The name of the Thing.")]

    language: Annotated[
        SemanticSearchLanguage, Field(description="The programming language this Thing belongs to.")
    ]

    categories: Annotated[
        frozenset[CategoryName],
        Field(
            default_factory=frozenset,
            description="""
            Set of Category names this Thing belongs to.

            Most Things (86.5%) belong to a single Category.
            Some Things (13.5%) belong to multiple Categories.
            Empty set indicates no category membership, which is the case for:
            - CSS
            - Elixir
            - HTML
            - Solidity
            - Swift
            - Yaml

            Multi-category is common in C/C++ (declarators serving multiple roles).
            """,
        ),
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
            """
        ),
    ] = True

    _kind: ClassVar[Literal[ThingKind.TOKEN, ThingKind.COMPOSITE]]

    @property
    def is_multi_category(self) -> bool:
        """Check if this Thing belongs to multiple Categories."""
        return len(self.categories) > 1

    @property
    def is_single_category(self) -> bool:
        """Check if this Thing belongs to exactly one Category."""
        return len(self.categories) == 1

    @property
    def primary_category(self) -> CategoryName | None:
        """Get the primary Category of this Thing, if it exists.

        Returns the single Category if the Thing belongs to exactly one; otherwise, returns None.
        """
        return next(iter(self.categories)) if self.is_single_category else None

    @property
    def kind(self) -> Literal[ThingKind.TOKEN, ThingKind.COMPOSITE]:
        """The kind of this Thing (TOKEN or COMPOSITE)."""
        return self._kind

    @property
    def is_token(self) -> bool:
        """Whether this Thing is a Token."""
        return self._kind == ThingKind.TOKEN

    @property
    def is_composite(self) -> bool:
        """Whether this Thing is a Composite."""
        return self._kind == ThingKind.COMPOSITE

    def __str__(self) -> str:
        """String representation of the Thing."""
        if self.primary_category:
            return f"Thing: {self.name}, Category: {self.primary_category}, Language: {self.language.variable}"
        return f"Thing: {self.name}, Categories: {list(self.categories)}, Language: {self.language.variable}"


class CompositeThing(Thing):
    """A CompositeThing is a concrete element that appears in the parse tree. A Token is a Thing, but a CompositeThing (this class) is not a Token.

    Tree-sitter equivalent: Node with fields and/or children

    Attributes:
        name: Thing identifier (e.g., "if_statement", "identifier")
        kind: Structural classification (always COMPOSITE)
        language: Programming language this Thing belongs to
        categories: Set of Category names this Thing belongs to
        is_explicit_rule: Whether has named grammar rule

    Relationships:
        - Thing → Many Categories (via categories attribute)
        - Categories reference Things via their `member_things` attribute

    A CompositeThing represents complex structures like functions, classes, and expressions, which have direct and/or positional connections to child Things.

    Empirical findings:
        - Average 3-5 Direct Connections per CompositeThing
        - Average 1-2 Positional Connections per CompositeThing
    """

    direct_connections: Annotated[
        frozenset[DirectConnection],
        Field(
            default_factory=frozenset,
            description="""
        Named semantic relationships to child Things with specific Roles.
        Tree-sitter equivalent: Grammar "fields"
        """,
        ),
    ]

    positional_connections: Annotated[
        frozenset[PositionalConnection],
        Field(
            default_factory=frozenset,
            description="""
        Ordered structural relationships to child Things without Roles (may have an implied role from its position).
        Tree-sitter equivalent: Grammar "children"
        """,
        ),
    ]

    can_be_anywhere: Annotated[
        bool,
        Field(
            description="""
            Whether the target Thing can appear anywhere in the parse tree. Corresponds to tree-sitter's `extra` attribute.
            """
        ),
    ] = False

    is_start: Annotated[
        bool,
        Field(
            description="Whether this Composite is the root of the parse tree (i.e., the start symbol)."
        ),
    ] = False

    _kind: ClassVar[Literal[ThingKind.COMPOSITE]] = ThingKind.COMPOSITE  # type: ignore

    @property
    def kind(self) -> Literal[ThingKind.COMPOSITE]:
        """The kind of this Thing (always COMPOSITE)."""
        return self._kind

    @property
    def is_token(self) -> Literal[False]:
        """Whether this Thing is a Token (always False)."""
        return False

    @property
    def is_composite(self) -> Literal[True]:
        """Whether this Thing is a Composite (always True)."""
        return True

    @property
    def is_multi_category(self) -> bool:
        """Check if this Thing belongs to multiple Categories."""
        return len(self.categories) > 1

    @property
    def is_single_category(self) -> bool:
        """Check if this Thing belongs to exactly one Category."""
        return len(self.categories) == 1

    @property
    def primary_category(self) -> CategoryName | None:
        """Get the primary Category of this Thing, if it exists.

        Returns the single Category if the Thing belongs to exactly one; otherwise, returns None.
        """
        return next(iter(self.categories)) if self.is_single_category else None

    def is_in_category(self, category: CategoryName) -> bool:
        """Check if this Thing belongs to the specified Category."""
        return category in self.categories

    def __str__(self) -> str:
        """String representation of the CompositeThing."""
        if self.primary_category:
            return f"CompositeThing: {self.name}, Category: {self.primary_category}, Language: {self.language.variable}"
        return f"CompositeThing: {self.name}, Categories: {list(self.categories)}, Language: {self.language.variable}"


class Token(Thing):
    """A Token is a leaf Thing with no structural children.

    A Token represents keywords, identifiers, literals, and punctuation -- what you literally see in the source code. Tokens are classified by their significance, indicating whether they carry semantic or structural meaning versus being mere formatting trivia.
    """

    significance: Annotated[
        TokenSignificance,
        Field(
            description="""
            Semantic importance classification.

            STRUCTURAL: Keywords, operators, delimiters (if, {, +)
            IDENTIFIER: Variable/function/class names
            LITERAL: String/number/boolean values
            TRIVIAL: Whitespace, line continuations (insignificant)
            COMMENT: Code comments (significant but not code)

            Used for filtering: include STRUCTURAL/IDENTIFIER/LITERAL for semantic analysis,
            include all for formatting/reconstruction.
        """
        ),
    ]

    _kind: ClassVar[Literal[ThingKind.TOKEN]] = ThingKind.TOKEN  # type: ignore

    @property
    def kind(self) -> Literal[ThingKind.TOKEN]:
        """The kind of this Thing (always TOKEN)."""
        return self._kind

    @property
    def is_token(self) -> Literal[True]:
        """Whether this Thing is a Token (always True)."""
        return True

    @property
    def is_composite(self) -> Literal[False]:
        """Whether this Thing is a Composite (always False)."""
        return False

    def __str__(self) -> str:
        """String representation of the Token."""
        return f"Token: {self.name}, Significance: {self.significance.value}, Language: {self.language.variable}"


class Category(BasedModel):
    """A Category is an abstract classification that groups Things with shared characteristics.

    Categories do not appear in parse trees. They are primarily for classification of related Things. For example, `expression` is a Category containing `binary_expression`,
    `unary_expression`, etc.
    """

    model_config = BasedModel.model_config | ConfigDict(frozen=True)

    name: Annotated[Role, Field(description="The name of the Category.")]

    language: Annotated[
        SemanticSearchLanguage,
        Field(description="The programming language this Category belongs to."),
    ]

    member_things: Annotated[
        frozenset[ThingName],
        Field(
            default_factory=frozenset, description="The *names* of this category's member Things."
        ),
    ]

    @field_validator("language", mode="after")
    def _validate_language(self, value: Any) -> SemanticSearchLanguage:
        """Validate that the language is a SemanticSearchLanguage that has defined Categories in its grammar."""
        if not isinstance(value, SemanticSearchLanguage):
            raise TypeError("Invalid language")
        if value in (
            SemanticSearchLanguage.CSS,
            SemanticSearchLanguage.ELIXIR,
            SemanticSearchLanguage.HTML,
            SemanticSearchLanguage.SOLIDITY,
            SemanticSearchLanguage.SWIFT,
            SemanticSearchLanguage.YAML,
        ):
            logger.warning(
                """Something doesn't look right here. You provided %s and that language has no Categories. We're going to let it go because the grammar could have changed. Please submit an issue at https://github.com/knitli/codeweaver-mcp/issues/ to let us look into it more deeply.""",
                value.variable,
            )
        return value

    def __str__(self) -> str:
        """String representation of the Category."""
        return f"Category: {self.name}, Language: {self.language.variable}, Members: {list(self.member_things)}"

    @property
    def short_str(self) -> str:
        """Short string representation of the Category."""
        return f"{self.name} {self.language.variable}"

    def includes(self, thing_name: ThingName | TokenName) -> bool:
        """Check if this Category includes the specified Thing name."""
        return thing_name in self.member_things

    def overlap_with(self, other: Category) -> frozenset[ThingName | TokenName]:
        """Check if this Category shares any member Things with another Category. Returns the overlapping member Thing names.

        Used for analyzing multi-category membership.
        """
        return self.member_things & other.member_things


class ConnectionConstraint(Flag, BaseEnum):  # type:ignore  # we intentionally override BaseEnum where there's overlap with Flag
    """Flags for Connection constraints."""

    ZERO_OR_ONE = auto()
    """May have zero or one child of the specified type(s)."""
    ZERO_OR_MANY = auto()
    """May have zero or many children of the specified type(s) (unconstrained)."""
    ONLY_ONE = auto()
    """Must have exactly one child of the specified type(s)."""
    ONE_OR_MANY = auto()
    """Must have one or many children of the specified type(s)."""

    ALL = ZERO_OR_ONE | ZERO_OR_MANY | ONLY_ONE | ONE_OR_MANY

    @classmethod
    def from_cardinality(cls, min_card: int, max_card: int) -> ConnectionConstraint:
        """Create ConnectionConstraint from cardinality tuple."""
        match (min_card, max_card):
            case (0, 1):
                return cls.ZERO_OR_ONE
            case (0, -1):
                return cls.ZERO_OR_MANY
            case (1, 1):
                return cls.ONLY_ONE
            case (1, -1):
                return cls.ONE_OR_MANY
            case _:
                raise ValueError(f"Invalid cardinality: ({min_card}, {max_card})")


class Connection(BasedModel):
    """Base class for Connections between Things in a parse tree.

    A Connection is a relationship from a parent Thing to child Thing(s) (an 'edge' in graph terminology). There are three classes of Connections: Direct or Positional. Direct and Positional Connections describe structure.

    Attributes:
        connection_class: Classification of connection type (DIRECT, POSITIONAL)
        target_names: Set of names of target Things this Connection can point to
        allows_multiple: Whether this Connection permits multiple children of specified type(s)
        requires_presence: Whether at least one child of specified type(s) MUST be present

    Relationships:
        - Connection → Many Things (via target_names attribute)
        - Things reference Connections via their `direct_connections` or `positional_connections` attributes

    Empirical findings:
        - Average 3-5 Direct Connections per CompositeThing
        - Average 1-2 Positional Connections per CompositeThing
    """

    model_config = BasedModel.model_config | ConfigDict(frozen=True)

    source_thing: Annotated[
        ThingName,
        Field(description="The name of the source Thing this Connection originates from."),
    ]

    target_things: Annotated[
        frozenset[ThingName | TokenName],
        Field(
            default_factory=frozenset,
            description="""
            Set of names of target Things this Connection can point to.

            Can reference either Categories (abstract) OR concrete Things, enabling flexible type constraints:
            - Category References (polymorphic constraints): Accepts ANY member of a Category.
            """,
        ),
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
            """
        ),
    ] = False

    requires_presence: Annotated[
        bool,
        Field(
            description="""
            Whether at least one child of specified types MUST be present.

            Defines lower cardinality bound (0 or 1 vs 1 or many).

            Tree-sitter: `required = True/False`
            """
        ),
    ] = False

    language: Annotated[
        SemanticSearchLanguage,
        Field(description="The programming language this Connection belongs to."),
    ]

    _connection_class: ClassVar[Literal[ConnectionClass.DIRECT, ConnectionClass.POSITIONAL]]

    @property
    def _cardinality(self) -> tuple[Literal[0, 1], Literal[-1, 1]]:
        """Get human-readable cardinality description."""
        min_card = 1 if self.requires_presence else 0
        max_card = -1 if self.allows_multiple else 1  # -1 indicates unbounded
        return (min_card, max_card)

    @computed_field
    @property
    def constraints(self) -> ConnectionConstraint:
        """Get ConnectionConstraint flags for this Connection."""
        return ConnectionConstraint.from_cardinality(*self._cardinality)


class DirectConnection(Connection):
    """A DirectConnection is a named semantic relationship with a Role.

    Tree-sitter equivalent: Grammar "fields".

    Attributes:
        role: Semantic function name (e.g., "condition", "body")
        _connection_class: Always ConnectionClass.DIRECT


    Characteristics:
        - Most precise type of structural relationship
        - Role describes what purpose the child serves
        - Only Direct connections have Roles

    Empirical findings:
        - ~90 unique role names across all languages
        - Most common: name (381), body (281), type (217), condition (102)
        - Average 3-5 Direct connections per Composite Thing
    """

    role: Annotated[
        Role,
        Field(
            description="""
            The semantic function of this DirectConnection.

            Describes what purpose a child serves, not just that it exists.
            Examples: "condition", "body", "parameters", "left", "right", "operator"

            Tree-sitter equivalent: Field name in grammar
            """,
            default_factory=Role,
        ),
    ]

    _connection_class: ClassVar[Literal[ConnectionClass.DIRECT]] = ConnectionClass.DIRECT  # type: ignore


class PositionalConnection(Connection):
    """A PositionalConnection is an ordered structural relationship without a Role.

    Tree-sitter equivalent: Grammar "children".

    Characteristics:
        - Less precise than DirectConnection (no Role)
        - Ordered relationship (position may imply role)
        - No Role; may have implied role from position

    Empirical findings:
        - Average 1-2 Positional connections per Composite Thing
    """

    position: Annotated[
        NonNegativeInt | None,
        Field(
            description="The position index of this PositionalConnection among its siblings, starting from 0."
        ),
    ] = None

    _connection_class: ClassVar[  # type: ignore
        Literal[ConnectionClass.POSITIONAL]
    ] = ConnectionClass.POSITIONAL  # type: ignore


def _get_types_files_in_directory(directory: DirectoryPath) -> list[FilePath]:
    """Get list of node types files in a directory.

    Args:
        directory: Directory to search for node types files

    Returns:
        List of node types file paths
    """
    return [
        path
        for path in directory.iterdir()
        if path.is_file() and path.name.endswith("node-types.json")
    ]

# ===========================================================================
#  Translating Node Types Files to CodeWeaver
#
# - The downside of adopting your own vocabulary and structure is that you
#   have to translate between your internal representation and the external
#   format.
# - Once the JSON for each language is loaded, we need to translate it into
#   our internal representation.
#
# node-types.json Structure:
# - An array of 'node type' objects with:
#   - Always: `type` (str), `named` (bool)
#   - Sometimes: `root` (bool), `fields` (object), `children` (object),
#     `subtypes` (array), `extra` (bool)
#
#   Field Details:
#   - subtypes: array of objects with `type` (str) and `named` (bool)
#   - children: a 'child type' object with `multiple` (bool), `required`
#     (bool), and `types` (array of objects with `type` and `named`)
#   - fields: object mapping field names (strings) to child type objects
#     (same structure as children)
#   - extra: boolean indicating this node can appear anywhere in the tree
#
# Mapping to CodeWeaver:
#
# Node Classification:
#  - Categories: node types that HAVE `subtypes` (abstract groupings like
#    "expression"); the nodes listed in the subtypes array become the
#    Category's member_things
#  - Tokens: nodes with NO fields AND NO children (leaf nodes)
#  - Composites: nodes with fields OR children (non-leaf nodes)
#  - Note: Categories, Tokens, and Composites can ALL have `extra: true`
#
# Connection Types:
#  - Direct connections: derived from `fields` (semantic relationships with
#    named Roles)
#  - Positional connections: derived from `children` (ordered relationships,
#    no semantic Role)
#  - Note: The `extra` flag doesn't create connections; it marks Things that
#    can appear as children anywhere in the tree
#
# Field Mappings:
#  - Role: the key name in the `fields` object (e.g., "condition", "body")
#  - is_explicit_rule: maps from `named`
#  - allows_multiple: maps from `multiple` (in child type objects)
#  - requires_presence: maps from `required` (in child type objects)
#  - target_things: the `types` array in fields/children
#  - source_thing: the `type` of the containing node
#  - is_start: maps from `root`
#  - can_appear_anywhere: maps from `extra` (marks Things that can appear
#    as children of any node)
#
# Translation Algorithm:
#  1. First pass: Identify Categories (nodes with `subtypes`)
#  2. Second pass: Create Things (Tokens vs Composites based on fields/children)
#  3. Third pass: Create Connections from fields/children on each Thing
#  4. Mark Things with `can_appear_anywhere: true` where applicable
# ===========================================================================

class NodeTypeFileLoader:
    """Container for node types files in a directory structure.

    Attributes:
        directory: Directory containing node types files
        root: List of node types file paths
    """

    directory: Annotated[
        DirectoryPath, Field(description="""Directory containing node types files.""")
    ] = Path(__file__).parent.parent.parent.parent / "node_types"

    root: Annotated[
        list[FilePath],
        Field(
            description="""List of node types file paths.""",
            default_factory=lambda data: _get_types_files_in_directory(data["directory"]),
            init=False,
        ),
    ]

    _data: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, **data: Any) -> None:
        """Initialize NodeTypesFiles, auto-populating root if not provided."""
        super().__init__(**data)
        if not self.root:
            self.root = _get_types_files_in_directory(self.directory)

    def _load_data(self) -> list[dict[str, Any]]:
        """Load data (list of node types file paths)."""
        return [from_json(file.read_bytes()) for file in self.root]

    def get_all_types(self) -> list[dict[str, Any]]:
        """Get all types from the node types files.

        Returns:
            List of dictionaries containing raw data from node types files. This is in the tree-sitter node-types.json format.
        """
        if not type(self)._data:
            type(self)._data = self._load_data()
        return type(self)._data


# ==========================================================================
#                       Other Notes from Grammar Analysis
# ==========================================================================
#   - Most 'unnamed' *fields* (direct connections) are punctuation or operator symbols (e.g., "=", "+", ";", ",") (81%). The unnamed fields with alpha characters are keywords (e.g., "else", "catch", "finally", "return").
#  - **All** 'named' *fields* (direct connections) are alpha characters (keywords or semantic names).
#  - All *children* (positional connections) are 'named' (is_explicit_rule = True).
#
# ==========================================================================

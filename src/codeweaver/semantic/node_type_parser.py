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
import re

from collections import defaultdict
from collections.abc import Generator, Iterable, Iterator, Sequence
from enum import Flag, auto
from functools import cache, cached_property
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Any, ClassVar, Literal, NamedTuple, NewType, TypedDict, cast, override

from pydantic import (
    ConfigDict,
    DirectoryPath,
    Field,
    FilePath,
    NonNegativeInt,
    PositiveInt,
    PrivateAttr,
    computed_field,
    field_validator,
)
from pydantic_core import from_json

from codeweaver._common import BasedModel, BaseEnum, LiteralStringT, RootedRoot
from codeweaver._utils import lazy_importer
from codeweaver.language import SemanticSearchLanguage


type ConstantsGroup = tuple[
    MappingProxyType[PositiveInt, SemanticSearchLanguage],
    MappingProxyType[
        SemanticSearchLanguage,
        dict[LiteralStringT, Literal["structural", "operator", "identifier"]],
    ],
    re.Pattern[str],
    re.Pattern[str],
    re.Pattern[str],
    re.Pattern[str],
]


@cache
def get_constants() -> ConstantsGroup:
    """Retrieves constants from the _constants module. Uses lazy importing to avoid compiling regexes until needed."""
    _constants_module = lazy_importer("codeweaver.semantic._constants")
    return tuple(
        getattr(_constants_module, key)
        for key in (
            "named_node_counts",
            "language_specific_token_exceptions",
            "is_operator",
            "not_symbol",
            "is_literal",
            "is_keyword",
        )
    )


logger = logging.getLogger()

Role = NewType("Role", LiteralStringT)
CategoryName = NewType("CategoryName", LiteralStringT)
ThingName = NewType("ThingName", LiteralStringT)
TokenName = NewType("TokenName", LiteralStringT)


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
    - STRUCTURAL: keywords
    - OPERATOR: operators
    - IDENTIFIER: variable/function/type names
    - LITERAL: string/number/boolean literals
    - TRIVIAL: whitespace, punctuation, formatting tokens
    - COMMENT: comments

    A Token can be classified by its significance, indicating whether it carries semantic or structural meaning versus being mere formatting trivia. This classification helps in filtering Tokens during semantic analysis while preserving them for formatting purposes.
    """

    STRUCTURAL = "structural"
    OPERATOR = "operator"
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

    @classmethod
    def from_node_dto(cls, node_dto: NodeTypeDTO) -> TokenSignificance:
        """Create TokenSignificance from NodeTypeDTO."""
        if node_dto.is_composite or node_dto.is_category:
            raise ValueError("Cannot determine TokenSignificance for Composite or Category nodes")
        _, language_specific_exceptions, is_operator, _, is_literal, is_keyword = get_constants()
        if (
            node_dto.language in language_specific_exceptions
            and node_dto.node in language_specific_exceptions[node_dto.language]
        ):
            return cls.from_string(language_specific_exceptions[node_dto.language][node_dto.node])
        if "comment" in node_dto.node.lower() or node_dto.node.lower() == "comment":
            return cls.COMMENT
        if "identifier" in node_dto.node.lower() or node_dto.node.lower() == "identifier":
            return cls.IDENTIFIER
        if is_keyword.match(node_dto.node):
            return cls.STRUCTURAL
        if is_operator.match(node_dto.node):
            return cls.OPERATOR
        return cls.LITERAL if is_literal.match(node_dto.node) else cls.TRIVIAL


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

    can_be_anywhere: Annotated[
        bool,
        Field(
            description="""
            Whether the target Thing can appear anywhere in the parse tree. Corresponds to tree-sitter's `extra` attribute.
            """
        ),
    ] = False

    _categories: Annotated[CategoryGenerator, PrivateAttr()]

    _kind: ClassVar[Literal[ThingKind.TOKEN, ThingKind.COMPOSITE]]

    @computed_field
    @cached_property
    def categories(self) -> frozenset[Category]:
        """Get the Categories this Thing belongs to."""
        return frozenset(self._categories)

    @classmethod
    def from_node_dto(cls, node_dto: NodeTypeDTO, categories: Iterable[CategoryName]) -> Thing:
        """Create a Thing (Token or Composite) from a NodeTypeDTO and its Categories."""
        if node_dto.is_category:
            raise ValueError("Cannot create Thing from Category node")
        thing_cls: type[Thing] = CompositeThing if node_dto.is_composite else Token
        thing_kwargs: dict[str, Any] = {
            "name": ThingName(node_dto.node),
            "language": node_dto.language,
            "is_explicit_rule": node_dto.named,
            "can_be_anywhere": node_dto.extra,
            "_categories": categories,
        }
        if not node_dto.is_composite:
            thing_kwargs["significance"] = TokenSignificance.from_node_dto(node_dto)
        if thing_cls is CompositeThing:
            thing_kwargs["is_start"] = node_dto.root
        return thing_cls(**thing_kwargs)  # type: ignore[call-arg]

    @property
    def is_multi_category(self) -> bool:
        """Check if this Thing belongs to multiple Categories."""
        return len(self.categories) > 1

    @property
    def is_single_category(self) -> bool:
        """Check if this Thing belongs to exactly one Category."""
        return len(self.categories) == 1

    @property
    def primary_category(self) -> Category | None:
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

    is_start: Annotated[
        bool,
        Field(
            description="Whether this Composite is the root of the parse tree (i.e., the start symbol)."
        ),
    ] = False

    _direct_connections: Annotated[DirectConnectionGenerator, PrivateAttr()]

    _positional_connections: Annotated[PositionalConnectionGenerator, PrivateAttr()]

    _kind: ClassVar[Literal[ThingKind.COMPOSITE]] = ThingKind.COMPOSITE  # type: ignore

    @computed_field
    @cached_property
    def direct_connections(self) -> frozenset[DirectConnection]:
        """Get the set of DirectConnections from this CompositeThing to its child Things."""
        return frozenset(self._direct_connections)

    @computed_field
    @cached_property
    def positional_connections(self) -> frozenset[PositionalConnection]:
        """Get the set of PositionalConnections from this CompositeThing to its child Things."""
        return frozenset(self._positional_connections)

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

    _member_things: Annotated[ThingGenerator, PrivateAttr()]

    @classmethod
    def from_node_dto(
        cls, node_dto: NodeTypeDTO, member_things: Iterable[ThingName | TokenName]
    ) -> Category:
        """Create a Category from the given node DTOs."""
        return cls.model_validate({
            "name": Role(node_dto.node),
            "language": node_dto.language,
            "_member_things": member_things,
        })

    @computed_field
    @cached_property
    def member_things(self) -> frozenset[ThingType]:
        """Get the set of member Things in this Category."""
        return frozenset(self._member_things)

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
        return f"Category: {self.name}, Language: {self.language.variable}, Members: [{', '.join(sorted(thing.name for thing in self.member_things), key=str.lower)}]"  # pyright: ignore[reportCallIssue]

    @property
    def short_str(self) -> str:
        """Short string representation of the Category."""
        return f"Category: {self.name} <<{self.language!s}>>"

    def __contains__(self, thing: CompositeThing | Token) -> bool:
        """Check if this Category contains the specified Thing."""
        return thing in self.member_things

    @override
    def __iter__(self) -> Iterator[CompositeThing | Token]:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Iterate over the member Things in this Category."""
        return iter(self.member_things)

    def __len__(self) -> int:
        """Get the number of member Things in this Category."""
        return len(self.member_things)

    def includes(self, thing_name: ThingName | TokenName) -> bool:
        """Check if this Category includes the specified Thing name."""
        return (
            next((thing for thing in self.member_things if thing.name == thing_name), None)
            is not None
        )

    def overlap_with(self, other: Category) -> frozenset[CompositeThing | Token | Category]:
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
        return next(member for member in cls if member.as_cardinality == (min_card, max_card))

    @property
    def as_cardinality(self) -> tuple[Literal[0, 1], Literal[-1, 1]]:
        """Get cardinality tuple from ConnectionConstraint."""
        match self:
            case ConnectionConstraint.ZERO_OR_ONE:
                return (0, 1)
            case ConnectionConstraint.ZERO_OR_MANY:
                return (0, -1)
            case ConnectionConstraint.ONLY_ONE:
                return (1, 1)
            case ConnectionConstraint.ONE_OR_MANY:
                return (1, -1)
            case _:
                raise ValueError(f"Invalid ConnectionConstraint: {self}")

    @property
    def allows_multiple(self) -> bool:
        """Check if this ConnectionConstraint allows multiple children (ZERO_OR_MANY or ONE_OR_MANY)."""
        return self in {ConnectionConstraint.ZERO_OR_MANY, ConnectionConstraint.ONE_OR_MANY}

    @property
    def is_unconstrained(self) -> bool:
        """Check if this ConnectionConstraint is unconstrained (ZERO_OR_MANY)."""
        return self is ConnectionConstraint.ZERO_OR_MANY

    @property
    def requires_at_least_one(self) -> bool:
        """Check if this ConnectionConstraint requires at least one child (ONLY_ONE or ONE_OR_MANY)."""
        return self in {ConnectionConstraint.ONLY_ONE, ConnectionConstraint.ONE_OR_MANY}

    @property
    def must_be_single(self) -> bool:
        """Check if this ConnectionConstraint requires exactly one child (ONLY_ONE)."""
        return self is ConnectionConstraint.ONLY_ONE


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

    _target_things: Annotated[ThingOrCategoryGenerator, PrivateAttr()]

    _connection_class: ClassVar[Literal[ConnectionClass.DIRECT, ConnectionClass.POSITIONAL]]

    @computed_field
    @cached_property
    def target_things(self) -> frozenset[ThingOrCategoryType]:
        """Get the set of target Things this Connection can point to."""
        return frozenset(self._target_things)

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

    def can_connect_to(self, thing: Thing | Token | Category) -> bool:
        """Check if this Connection can point to the specified Thing."""
        if hasattr(thing, "can_be_anywhere") and cast(Thing | Token, thing).can_be_anywhere:
            return True
        return thing in self.target_things

    @computed_field
    @property
    def connection_count(self) -> NonNegativeInt:
        """Get the number of target Things this Connection can point to."""
        return len(self.target_things)

    @computed_field
    @property
    def connection_class(self) -> Literal[ConnectionClass.DIRECT, ConnectionClass.POSITIONAL]:
        """Get the connection class of this Connection (DIRECT or POSITIONAL)."""
        return self._connection_class


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
    # pylance complains because the base class is a union of both DIRECT and POSITIONAL, but this is exactly what we want
    # We have clear segregation between DirectConnection and PositionalConnection via this class variable and separate subclasses

    @classmethod
    def from_node_dto(cls, node_dto: NodeTypeDTO) -> list[DirectConnection]:
        """Create DirectConnections from the given node DTOs."""
        if not node_dto.fields:
            return []
        return [
            cls.model_validate({
                "source_thing": ThingName(node_dto.node),
                "role": Role(role),
                "allows_multiple": child_type.multiple,
                "requires_presence": child_type.required,
                "language": node_dto.language,
                "_target_things": ThingGenerator(
                    [ThingName(t.node) for t in child_type.types], language=node_dto.language
                ),
            })
            for role, child_type in node_dto.fields.items()
        ]


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
    # pylance complains because the base class is a union of both DIRECT and POSITIONAL, but this is exactly what we want

    @classmethod
    def from_node_dto(cls, node_dto: NodeTypeDTO) -> list[PositionalConnection]:
        """Create PositionalConnections from the given node DTOs."""
        if not node_dto.children:
            return []
        child_type = node_dto.children
        target_things = tuple(ThingName(t.node) for t in child_type.types)
        return [
            cls.model_validate({
                "source_thing": ThingName(node_dto.node),
                "position": index,
                "allows_multiple": child_type.multiple,
                "requires_presence": child_type.required,
                "language": node_dto.language,
                "target": ThingName(node),
                "_target_things": ThingGenerator(list(target_things), language=node_dto.language),
            })
            for index, node in enumerate(target_things)
        ]


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


type ThingType = CompositeThing | Token
type ThingNameType = ThingName | TokenName

type ThingOrCategoryType = CompositeThing | Token | Category
type ThingOrCategoryNameType = ThingName | TokenName | CategoryName


class BaseGenerator[Name, T]:
    """Base class for generators of Things."""

    _items: list[Name]
    _language: SemanticSearchLanguage
    _registry: _ThingRegistry

    def __init__(self, items: list[Name], language: SemanticSearchLanguage) -> None:
        """Initialize the BaseGenerator.

        Args:
            items: List of items to generate
        """
        self._items = items
        self._language = language
        self._registry = _get_registry()

    def __iter__(self) -> Generator[T, None, None]:
        """Iterate over the items in this generator."""
        raise NotImplementedError("Subclasses must implement __iter__")

    def __len__(self) -> int:
        """Get the number of items in this generator."""
        return len(self._items)


class CategoryGenerator(BaseGenerator[CategoryName, Category]):
    """Generator for Categories in a specific programming language.

    Provides lazy access to Categories by name, constructing them on demand.
    """

    _items: list[CategoryName]

    def __iter__(self) -> Generator[Category, None, None]:
        """Iterate over the Categories in this generator."""
        for name in self._items:
            category = self._registry.get_category_by_name(name, language=self._language)
            if category is not None:
                yield category  # type: ignore


class ThingGenerator(BaseGenerator[ThingNameType, ThingType]):
    """Generator for Things (Things and Tokens) in a specific programming language.

    Provides lazy access to Things by name, constructing them on demand.
    """

    _items: list[ThingNameType]

    def __iter__(self) -> Generator[ThingType, None, None]:
        """Iterate over the Things in this generator."""
        for name in self._items:
            thing = self._registry.get_thing_by_name(name, language=self._language)
            if thing is not None and not isinstance(thing, Category):
                yield thing  # type: ignore


class ThingOrCategoryGenerator(BaseGenerator[ThingOrCategoryNameType, ThingOrCategoryType]):
    """Generator for Things (Things and Tokens) in a specific programming language.

    Provides lazy access to Things by name, constructing them on demand.
    """

    _items: list[ThingOrCategoryNameType]

    def __iter__(self) -> Generator[ThingOrCategoryType, None, None]:
        """Iterate over the Things in this generator."""
        for name in self._items:
            thing = self._registry.get_thing_by_name(name)
            if thing is not None:
                yield thing  # type: ignore


class DirectConnectionGenerator(BaseGenerator[ThingName, DirectConnection]):
    """Generator for DirectConnections in a specific programming language.

    Provides lazy access to DirectConnections by source Thing name, constructing them on demand.
    """

    _items: list[ThingName]

    _source: ThingName

    def __init__(
        self, items: list[ThingName], source: ThingName, language: SemanticSearchLanguage
    ) -> None:
        """Initialize the DirectConnectionGenerator."""
        super().__init__(items, language)
        self._source = source

    def __iter__(self) -> Generator[DirectConnection, None, None]:
        """Iterate over the DirectConnections in this generator."""
        for name in self._items:
            direct_connections, _ = self._registry.get_connections_by_source(
                name, language=self._language, direct=True
            )
            yield from direct_connections


class PositionalConnectionGenerator(BaseGenerator[ThingName, PositionalConnection]):
    """Generator for PositionalConnections in a specific programming language.

    Provides lazy access to PositionalConnections by source Thing name, constructing them on demand.
    """

    _items: list[ThingName]

    _source: ThingName

    def __init__(
        self, items: list[ThingName], source: ThingName, language: SemanticSearchLanguage
    ) -> None:
        """Initialize the PositionalConnectionGenerator."""
        super().__init__(items, language)
        self._source = source

    def __iter__(self) -> Generator[PositionalConnection, None, None]:
        """Iterate over the PositionalConnections in this generator."""
        for name in self._items:
            _, positional_connections = self._registry.get_connections_by_source(
                name, language=self._language, direct=False
            )
            yield from positional_connections


type _TokenDict = dict[TokenName, Token]
type _CompositeThingDict = dict[ThingName, CompositeThing]
type _CategoryDict = dict[CategoryName, Category]

_registry: _ThingRegistry | None = None


def _get_registry() -> _ThingRegistry:
    """Get the ThingRegistry instance."""
    global _registry
    if _registry is None:
        _registry = _ThingRegistry()
    return _registry


class _ThingRegistry:
    """Registry for managing Things and Categories for programming languages.

    Responsibilities:
        - A simple store for constructed Things and Categories
        - Along with ThingGenerator, provides lazy access to Things by name

    """

    _tokens: dict[SemanticSearchLanguage, _TokenDict]
    _composite_things: dict[SemanticSearchLanguage, _CompositeThingDict]
    _categories: dict[SemanticSearchLanguage, _CategoryDict]

    _contents: tuple[
        dict[SemanticSearchLanguage, _TokenDict],
        dict[SemanticSearchLanguage, _CompositeThingDict],
        dict[SemanticSearchLanguage, _CategoryDict],
    ]

    _direct_connections: dict[SemanticSearchLanguage, dict[ThingName, list[DirectConnection]]]
    """Direct connections by source Thing name."""
    _positional_connections: dict[
        SemanticSearchLanguage, dict[ThingName, list[PositionalConnection]]
    ]
    """Positional connections by source Thing name."""

    def __init__(self) -> None:
        """Initialize the ThingRegistry."""
        (
            self._tokens,
            self._categories,
            self._composite_things,
            self._direct_connections,
            self._positional_connections,
        ) = {}, {}, {}, {}, {}
        for lang in SemanticSearchLanguage:
            # pylance complains because the defaultdict isn't the TypedDict
            self._tokens[lang] = defaultdict(dict)  # type: ignore
            self._composite_things[lang] = defaultdict(dict)  # type: ignore
            self._categories[lang] = defaultdict(dict)  # type: ignore
            self._direct_connections[lang] = defaultdict(dict)  # type: ignore
            self._positional_connections[lang] = defaultdict(dict)  # type: ignore

        self._contents = self._tokens, self._composite_things, self._categories
        self._connections = self._direct_connections, self._positional_connections

    def _language_content(
        self, language: SemanticSearchLanguage
    ) -> MappingProxyType[ThingOrCategoryNameType, ThingOrCategoryType]:
        """Provides a combined read-only view of all Things for a specific language."""
        return MappingProxyType(
            self._tokens[language] | self._composite_things[language] | self._categories[language]
        )

    def register_thing(self, thing: ThingOrCategoryType) -> None:
        """Register a Thing in the appropriate category."""
        self_attr = (
            self._tokens
            if isinstance(thing, Token)
            else self._composite_things
            if isinstance(thing, CompositeThing)
            else self._categories
        )
        self_attr[thing.language][thing.name] = thing  # type: ignore
        logger.debug("Registered %s", thing)

    def register_connection(self, connection: Connection) -> None:
        """Register a Connection in the appropriate category."""
        self_attr = (
            self._direct_connections
            if connection.connection_class.is_direct
            else self._positional_connections
        )
        if connection.source_thing not in self_attr[connection.language]:
            self_attr[connection.language][connection.source_thing] = []
        self_attr[connection.language][connection.source_thing].append(connection)  # type: ignore
        logger.debug("Registered %s", connection)
    
    def register_connections(self, connections: Iterable[Connection]) -> None:
        """Register multiple Connections."""
        for connection in connections:
            self.register_connection(connection)

    def get_thing_by_name(
        self, name: ThingOrCategoryNameType, *, language: SemanticSearchLanguage | None = None
    ) -> ThingOrCategoryType | None:
        """Get a Thing by its name across all languages."""
        if language and name in (content := self._language_content(language)):
            return content[name]
        if not language:
            for content in self._contents:
                for language in content:
                    if name in content[language]:
                        return content[language][name]  # type: ignore
        return None

    def get_category_by_name(
        self, name: CategoryName, *, language: SemanticSearchLanguage | None = None
    ) -> Category | None:
        """Get a Category by its name across all languages."""
        if language and name in (content := self._categories[language]):
            return content[name]
        if not language:
            for content in self._categories:
                for language, cats in self._categories.items():
                    if name in cats:
                        return content[language][name]  # type: ignore
        return None

    def get_direct_connections_by_source(
        self, source: ThingName, *, language: SemanticSearchLanguage | None = None
    ) -> list[DirectConnection]:
        """Get DirectConnections by their source Thing name across all languages."""
        if language:
            return self.direct_connections[language].get(source, [])
        return (
            next(
                conns
                for content in self._direct_connections.values()
                for con_name, conns in content.items()
                if con_name == source
            )
            if any(
                conns
                for content in self._direct_connections.values()
                for con_name, conns in content.items()
                if con_name == source
            )
            else []
        )

    def _get_positional_connections_by_source(
        self, source: ThingName, *, language: SemanticSearchLanguage | None = None
    ) -> list[PositionalConnection]:
        """Get PositionalConnections by their source Thing name across all languages."""
        if language:
            return self.positional_connections[language].get(source, [])
        return (
            next(
                conns
                for content in self._positional_connections.values()
                for con_name, conns in content.items()
                if con_name == source
            )
            if any(
                conns
                for content in self._positional_connections.values()
                for con_name, conns in content.items()
                if con_name == source
            )
            else []
        )

    def get_connections_by_source(
        self,
        source: ThingName,
        *,
        language: SemanticSearchLanguage | None = None,
        direct: bool = True,
    ) -> list[DirectConnection] | list[PositionalConnection]:
        """Get Connections by their source Thing name across all languages."""
        if direct:
            return self.get_direct_connections_by_source(source, language=language)
        return self._get_positional_connections_by_source(source, language=language)

    def register_things(self, things: Iterable[ThingOrCategoryType]) -> None:
        """Register multiple Things."""
        for thing in things:
            self.register_thing(thing)

    @property
    def tokens(self) -> MappingProxyType[SemanticSearchLanguage, _TokenDict]:
        """Get all registered Tokens."""
        return MappingProxyType(self._tokens)

    def composite_things(self) -> MappingProxyType[SemanticSearchLanguage, _CompositeThingDict]:
        """Get all registered CompositeThings."""
        return MappingProxyType(self._composite_things)

    def categories(self) -> MappingProxyType[SemanticSearchLanguage, _CategoryDict]:
        """Get all registered Categories."""
        return MappingProxyType(self._categories)

    @property
    def connections(
        self,
    ) -> tuple[
        MappingProxyType[SemanticSearchLanguage, dict[ThingName, list[DirectConnection]]],
        MappingProxyType[SemanticSearchLanguage, dict[ThingName, list[PositionalConnection]]],
    ]:
        """Get all registered Connections."""
        return (
            MappingProxyType(self._direct_connections),
            MappingProxyType(self._positional_connections),
        )

    @property
    def direct_connections(
        self,
    ) -> MappingProxyType[SemanticSearchLanguage, dict[ThingName, list[DirectConnection]]]:
        """Get all registered DirectConnections."""
        return MappingProxyType(self._direct_connections)

    @property
    def positional_connections(
        self,
    ) -> MappingProxyType[SemanticSearchLanguage, dict[ThingName, list[PositionalConnection]]]:
        """Get all registered PositionalConnections."""
        return MappingProxyType(self._positional_connections)


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
#  - We use a lazy registry pattern to manage Things and Categories, so they can hold references to each other while being constructed and immutable.
#  - First pass: parse the JSON into intermediate DTO structures (NamedTuples and BasedModels)
#    that mirror the JSON structure but are easier to work with in Python.
#  - Second pass: convert the DTOs into our internal Thing and Category classes,
#    using the registry to resolve references by name.
#
# Approach: DTO classes for JSON structure, then conversion functions to keep pydantic validation
# cleanly separated from parsing logic. We'll use NamedTuple for DTOs to keep them lightweight, but allow for methods if needed (unlike TypedDict).
# ===========================================================================


class SimpleNodeTypeDTO(NamedTuple):
    """NamedTuple for a simple node type object in the node types file (objects with no attributes besides `type` and `named`). While these appear in the node-types file at the top level (all Tokens are of this form unless only 'extra' is present without fields [majority of extra cases, which are rare themselves]), they also appear nested within `subtypes`, `fields`, and `children`. We only use it for nested objects, not top-level ones.

    Note: This is an intermediate structure used during parsing and conversion. It is not part of the final internal representation.

    Attributes:
        node: Name of the node type (alias for `type`)
        named: Whether the node type is named (true) or anonymous (false)
    """

    # node is a Python keyword, so we use 'node' here and map it in the Field to prevent shadowing
    node: Annotated[
        LiteralStringT,
        Field(description="Name of the node type.", validation_alias="type", default_factory=str),
    ]
    named: Annotated[
        bool, Field(description="Whether the node type is named (true) or anonymous (false).")
    ]


class ChildTypeDTO(NamedTuple):
    """NamedTuple for a child type object in the node types file.


    Note: This is an intermediate structure used during parsing and conversion. It is not part of the final internal representation.

    Attributes:
        multiple: Whether multiple children of this type are allowed
        required: Whether at least one child of this type is required
        types: List of type objects for the allowed child types
    """

    multiple: Annotated[
        bool, Field(description="Whether multiple children of this type are allowed.")
    ]
    required: Annotated[
        bool, Field(description="Whether at least one child of this type is required.")
    ]
    types: Annotated[
        list[SimpleNodeTypeDTO],
        Field(description="List of type objects for the allowed child types."),
    ]


class NodeTypeDTO(BasedModel):
    """BasedModel for a single node type object in the node types file. This is the main structure we need to parse and convert into our internal representation. All subordinate structures (subtypes, fields, children) are represented using the SimpleNodeTypeDTO and ChildTypeDTO NamedTuples defined above.

    Attributes:
        node: Name of the node type (alias for `type`)
        named: Whether the node type is named (true) or anonymous (false)
        root: Whether the node type is the root of the parse tree
        fields: Mapping of field names to child type objects
        children: Child type object for positional children
        subtypes: List of subtype objects if this is an abstract node type
        extra: Whether this node type can appear anywhere in the parse tree
    """

    model_config = BasedModel.model_config | ConfigDict(frozen=True)

    language: Annotated[SemanticSearchLanguage, PrivateAttr()]

    # type is a Python keyword, so we use 'node' here and map it in the Field to prevent shadowing
    node: Annotated[
        LiteralStringT,
        Field(description="Name of the node type.", validation_alias="type", default_factory=str),
    ]
    named: Annotated[
        bool, Field(description="Whether the node type is named (true) or anonymous (false).")
    ]
    root: Annotated[bool, Field(description="Whether the node type is the root of the parse tree.")]
    fields: (
        Annotated[
            dict[LiteralStringT, ChildTypeDTO],
            Field(description="Mapping of field names to child type objects."),
        ]
        | None
    ) = None
    children: (
        Annotated[ChildTypeDTO, Field(description="Child type object for positional children.")]
        | None
    ) = None
    subtypes: (
        Annotated[
            list[SimpleNodeTypeDTO],
            Field(
                description="List of subtype objects if this is an abstract node type.",
                default_factory=list,
            ),
        ]
        | None
    ) = None
    extra: Annotated[
        bool | None,
        Field(description="Whether this node type can appear anywhere in the parse tree."),
    ] = None

    # ===============================
    # * Translation Helper Methods *
    # ===============================

    @computed_field
    @property
    def is_category(self) -> bool:
        """Check if this node type is a Category (has subtypes)."""
        return bool(self.subtypes)

    @computed_field
    @property
    def is_token(self) -> bool:
        """Check if this node type is a Token (no fields and no children)."""
        return not self.fields and not self.children and not self.subtypes

    @computed_field
    @property
    def is_symbol_token(self) -> bool:
        """Check if this node type is a Symbol Token (a Token that is not an identifier or literal)."""
        if not self.is_token:
            return False
        not_symbol = get_constants()[3]
        return self.is_token and not not_symbol.match(self.node)

    @computed_field
    @property
    def is_operator_token(self) -> bool:
        """Check if this node type is an Operator Token (a Token that is an operator)."""
        return self.is_symbol_token and get_constants()[2].match(self.node) is not None

    @computed_field
    @property
    def is_keyword_token(self) -> bool:
        """Check if this node type is a Keyword Token (a Token that is a keyword)."""
        return not self.is_symbol_token

    @computed_field
    @property
    def is_composite(self) -> bool:
        """Check if this node type is a Composite (has fields or children)."""
        return bool(self.fields) or bool(self.children)

    @computed_field
    @property
    def positional_children(self) -> tuple[SimpleNodeTypeDTO, ...]:
        """Extract positional children from a ChildTypeDTO."""
        return tuple(self.children.types) if self.children else ()

    @computed_field
    @property
    def direct_field_children(self) -> dict[LiteralStringT, tuple[SimpleNodeTypeDTO, ...]]:
        """Extract direct field children from the fields mapping."""
        return (
            {role: tuple(child.types) for role, child in self.fields.items()} if self.fields else {}
        )

    @computed_field
    @property
    def cardinality(self) -> tuple[Literal[0, 1], Literal[-1, 1]] | None:
        """Get human-readable cardinality description for positional children."""
        if self.children:
            min_card = 1 if self.children.required else 0
            max_card = -1 if self.children.multiple else 1  # -1 indicates unbounded
            return (min_card, max_card)
        return None

    @computed_field
    @property
    def constraints(self) -> ConnectionConstraint | None:
        """Get ConnectionConstraint flags for positional children."""
        if self.children:
            return ConnectionConstraint.from_cardinality(*self.cardinality)  # type: ignore
        return None


class NodeArray(RootedRoot[list[NodeTypeDTO]]):
    """Root object for node types file containing array of node type objects.

    Attributes:
        nodes: List of node type objects
    """

    root: Annotated[
        list[NodeTypeDTO],
        Field(
            description="List of node type objects from the node types file.", default_factory=list
        ),
    ]

    language = Annotated[SemanticSearchLanguage, PrivateAttr()]

    @classmethod
    def from_json_data(cls, data: dict[SemanticSearchLanguage, list[dict[str, Any]]]) -> NodeArray:
        """Create NodeArray from JSON data."""
        return cls(
            root=[
                NodeTypeDTO.model_validate({"language": language, **node})
                for language, nodes in data.items()
                for node in nodes
            ]
        )


class NodeTypeFileLoader:
    """Container for node types files in a directory structure.

    Attributes:
        directory: Directory containing node types files
        files: List of node types file paths
    """

    directory: Annotated[
        DirectoryPath, Field(description="""Directory containing node types files.""")
    ] = Path(__file__).parent.parent.parent.parent / "node_types"

    files: Annotated[
        list[FilePath],
        Field(
            description="""List of node types file paths.""",
            default_factory=lambda data: _get_types_files_in_directory(data["directory"]),
            init=False,
        ),
    ]

    _data: ClassVar[dict[SemanticSearchLanguage, list[dict[str, Any]]]] = {}

    _nodes: ClassVar[list[NodeArray]] = []

    def __init__(
        self, directory: DirectoryPath | None = None, files: list[FilePath] | None = None
    ) -> None:
        """Initialize NodeTypesFiles, auto-populating files if not provided."""
        # Optionally override directory
        if directory is not None:
            self.directory = directory
        # Initialize files list deterministically
        if files is not None:
            self.files = files
        else:
            self.files = _get_types_files_in_directory(self.directory)
        # We keep actual file loading lazy to avoid unnecessary I/O during initialization

    def _load_data(self) -> dict[SemanticSearchLanguage, list[dict[str, Any]]]:
        """Load data (list of node types file paths)."""
        return {
            SemanticSearchLanguage.from_string(file.stem.replace("-node-types", "")): from_json(
                file.read_bytes()
            )
            for file in self.files
        }

    def get_all_types(self) -> dict[SemanticSearchLanguage, list[dict[str, Any]]]:
        """Get all types from a node types files.

        Returns:
            List of dictionaries containing raw data from node types files. This is in the tree-sitter node-types.json format.
        """
        if not type(self)._data:
            type(self)._data = self._load_data()
        return type(self)._data

    def get_all_nodes(self) -> list[NodeArray]:
        """Get all nodes from the node types files.

        Returns:
            List of dictionaries containing the language and list of NodeTypeDTOs for that language.
        """
        data = type(self)._data or self.get_all_types()
        if not type(self)._data:
            type(self)._data = data
        node_arrays = [
            NodeArray.from_json_data({language: lang_nodes})
            for language, lang_nodes in data.items()
        ]
        if not type(self)._nodes:
            type(self)._nodes = node_arrays
        return type(self)._nodes


class NodeTypeParser:
    """Parses and translates node types files into CodeWeaver's internal representation."""

    def __init__(self, nodes: Sequence[NodeArray] | None = None) -> None:
        """Initialize NodeTypeParser with an optional NodeTypeFileLoader.

        Args:
            nodes: Optional pre-loaded list of NodeArray to parse; if None, will load from NodeTypeFileLoader
        """
        self.nodes = nodes or NodeTypeFileLoader().get_all_nodes()

        self._registry: _ThingRegistry = _get_registry()

    # we don't start the process until explicitly called

    def parse_all_nodes(self) -> None:
        """Parse and translate all node types files into internal representation."""
        for node_array in self.nodes:
            self._parse_node_array(node_array)

    def _create_category(self, node_dto: NodeTypeDTO) -> None:
        """Create a Category from a NodeTypeDTO and add it to the internal mapping.

        Args:
            node_dto: NodeTypeDTO representing the category to create.
        """
        member_things = frozenset(ThingName(subtype.node) for subtype in node_dto.subtypes or [])
        category = Category.from_node_dto(node_dto, member_things=member_things)
        self._registry.register_thing(category)

    def _create_token(self, node_dto: NodeTypeDTO) -> None:
        """Create a Token from a NodeTypeDTO and add it to the internal mapping.

        Args:
            node_dto: NodeTypeDTO representing the token to create.
        """
        categories = self._get_node_categories(node_dto)
        token = Token.from_node_dto(
            node_dto, categories=CategoryGenerator(list(categories), language=node_dto.language)
        )
        self._registry.register_thing(cast(Token, token))

    def _get_node_categories(self, node_dto: NodeTypeDTO) -> frozenset[CategoryName]:
        """Get the set of Categories a node belongs to based on its name and language.

        Args:
            node_dto: NodeTypeDTO representing the node to check.

        Returns:
            Set of Categories the node belongs to.
        """
        return frozenset(
            cat_name
            for cat_name, category in self._registry.categories().get(node_dto.language, {}).items()
            if category.includes(ThingName(node_dto.node))
        )

    def _create_composite(self, node_dto: NodeTypeDTO) -> None:
        """Create a CompositeThing from a NodeTypeDTO and add it to the internal mapping.

        Args:
            node_dto: NodeTypeDTO representing the composite to create.
        """
        categories = self._get_node_categories(node_dto)

        composite = CompositeThing.from_node_dto(
            node_dto, categories=ThingGenerator(list(categories))
        )
        self._registry.register_thing(cast(CompositeThing, composite))
        # Create and register DirectConnections
        if fields := node_dto.fields:
            for role, child in fields.items():
                direct_conns = DirectConnection.from_node_dto(node_dto, role, child)
                self._registry.register_connections(direct_conns)
        # Create and register PositionalConnections
        if children := node_dto.children:
            positional_conns = PositionalConnection.from_node_dto(node_dto, children)
            self._registry.register_connections(positional_conns)

    def _parse_node_array(self, node_array: NodeArray) -> None:
        """Parse and translate a single node types file into internal representation.

        Args:
            node_array: NodeArray containing the list of NodeTypeDTOs to parse.
        """
        for node_dto in node_array.root:
            if node_dto.is_category:
                self._create_category(node_dto)
        for node_dto in node_array.root:
            if node_dto.is_token:
                self._create_token(node_dto)
            elif node_dto.is_composite:
                self._create_composite(node_dto)


# ==========================================================================
#                       Other Notes from Grammar Analysis
# ==========================================================================
#   - Most 'unnamed' *fields* (direct connections) are punctuation or operator symbols (e.g., "=", "+", ";", ",") (81%). The unnamed fields with alpha characters are keywords (e.g., "else", "catch", "finally", "return").
#  - **All** 'named' *fields* (direct connections) are alpha characters (keywords or semantic names).
#  - All *children* (positional connections) are 'named' (is_explicit_rule = True).
#
# ==========================================================================

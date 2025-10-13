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

This is on full display in the `node-types.json` file, which describes the different node types
in a grammar. The `node-types.json` file is crucial for understanding how to interact with parse trees, but its
structure and terminology are confusing. It *conflates* several distinct concepts (meaning it treats them as if they are the same):
- It doesn't clearly differentiate between **nodes** (vertices) and **edges** (relationships)
- It uses "named" to describe both nodes and edges, meaning "has a grammar rule", not "has a name"
  (everything has a name!)
- It flattens hierarchies and structural patterns in ways that obscure their meaning

When I originally wrote the last version of this parser, my misunderstandings of these concepts led to a week of lost time and incorrect assumptions. After that, I decided to write this parser using terminology
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
- Categories do NOT appear in parse trees (abstract only)
- Used for polymorphic type constraints and classification (identifying what something can be used as)
- Example: `expression` is a Category containing `binary_expression`, `unary_expression`, etc.
- **Tree-sitter equivalent**: Nodes with `subtypes` field (abstract types)
- **Empirical finding**: ~110 unique Categories across 25 languages, but much smaller number when normalized (across languages) ~ 16 categories with members across many languages

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
- Classified by purpose: keyword, identifier, literal, punctuation, comment
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
   - **Empirical finding**: 1 or 2 things with 'can_be_anywhere' attribute per language ('comment' is one for all 11, others with 2 are other types of comment like 'html_comment' for javascript (for jsx))

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
| Node with fields/children | Composite Thing | Non-leaf node |
| Field | Direct Connection | Has semantic Role |
| Child | Positional Connection | Ordered, no Role |
| Field name | Role | Semantic function |
| Extra | `can_be_anywhere`  | Can be anywhere in the AST |
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

from collections import defaultdict
from collections.abc import Generator, Iterable, Iterator, Sequence
from functools import cached_property
from itertools import groupby
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Any, ClassVar, Literal, TypedDict, cast, overload, override

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

from codeweaver._common import BasedModel, LiteralStringT, RootedRoot
from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic._types import (
    CategoryName,
    ConnectionClass,
    ConnectionConstraint,
    NodeTypeDTO,
    Role,
    SimpleNodeTypeDTO,
    ThingKind,
    ThingName,
    ThingOrCategoryNameType,
    TokenPurpose,
)


logger = logging.getLogger()


def name_normalizer(name: str) -> str:
    """Normalize names by stripping leading underscores."""
    return name.lower().strip().lstrip("_")


def cat_name_normalizer(name: LiteralStringT | CategoryName) -> CategoryName:
    """Normalize category names by stripping leading underscores."""
    return CategoryName(name_normalizer(str(name)))  # pyright: ignore[reportArgumentType]


def thing_name_normalizer(name: LiteralStringT | ThingName) -> ThingName:
    """Normalize thing names by stripping leading underscores."""
    return ThingName(name_normalizer(str(name)))  # pyright: ignore[reportArgumentType]


def role_name_normalizer(name: LiteralStringT | Role) -> Role:
    """Normalize role names by stripping leading underscores."""
    return Role(name_normalizer(str(name)))  # pyright: ignore[reportArgumentType]


class AllThingsDict(TypedDict):
    """TypedDict for all Things and Tokens in a grammar."""

    composite_things: dict[ThingName, CompositeThing]
    tokens: dict[ThingName, Token]


class Thing(BasedModel):
    """Base class for Things (Things and Tokens -- also called Composites and Tokens)).

    There are two kinds of Things: Token (leaf) or Composite (non-leaf). Things are what you actually see in the AST produced by parsing code. A token is what you literally see in the source code (keywords, identifiers, literals, punctuation). A Composite represents complex structures like functions, classes, and expressions, which have direct and/or positional connections to child Things.

    We keep Token as a separate class for clarity, type safety, and to enforce that Tokens cannot have children.

    """

    model_config = BasedModel.model_config | ConfigDict(frozen=True)

    name: Annotated[ThingName, Field(description="The name of the Thing.")]

    language: Annotated[
        SemanticSearchLanguage, Field(description="The programming language this Thing belongs to.")
    ]

    category_names: Annotated[
        frozenset[CategoryName],
        Field(description="Names of Categories this Thing belongs to.", default_factory=frozenset),
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
            validation_alias="named",
        ),
    ] = True

    can_be_anywhere: (
        Annotated[
            bool,
            Field(
                description="""
            Whether the target Thing can appear anywhere in the parse tree. Corresponds to tree-sitter's `extra` attribute.
            """
            ),
        ]
        | None
    ) = None

    _kind: ClassVar[Literal[ThingKind.TOKEN, ThingKind.COMPOSITE]]

    def __init__(self, **data: Any) -> None:
        """Initialize a Thing (Token or Composite)."""
        for key in ("is_explicit_rule", "can_be_anywhere"):
            if key not in data or data[key] is None:
                data[key] = False
        if not data.get("category_names"):
            data["category_names"] = frozenset()
        super().__init__(**data)

    @property
    def categories(self) -> frozenset[Category]:
        """Resolve Categories from registry by name."""
        registry = get_registry()
        return frozenset(
            cat
            for name in self.category_names
            if (cat := registry.get_category_by_name(name, language=self.language))
        )

    @classmethod
    def from_node_dto(cls, node_dto: NodeTypeDTO, category_names: frozenset[CategoryName]) -> Thing:
        """Create a Thing (Token or Composite) from a NodeTypeDTO and category names."""
        if node_dto.is_category:
            raise ValueError("Cannot create Thing from Category node")
        thing_cls: type[Thing] = CompositeThing if node_dto.is_composite else Token
        thing_kwargs: dict[str, Any] = {
            "name": ThingName(node_dto.node),
            "language": node_dto.language,
            "is_explicit_rule": node_dto.named,
            "can_be_anywhere": node_dto.extra,
            "category_names": category_names,
        }
        if not node_dto.is_composite:
            thing_kwargs["purpose"] = TokenPurpose.from_node_dto(node_dto)
        if thing_cls is CompositeThing:
            thing_kwargs["is_start"] = node_dto.root
        return thing_cls.model_validate(thing_kwargs)

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

    is_start: (
        Annotated[
            bool,
            Field(
                description="Whether this Composite is the root of the parse tree (i.e., the start symbol).",
                validation_alias="root",
            ),
        ]
        | None
    ) = None

    _kind: ClassVar[Literal[ThingKind.COMPOSITE]] = ThingKind.COMPOSITE  # type: ignore

    def __init__(self, **data: Any) -> None:
        """Initialize a CompositeThing."""
        if "is_start" not in data or data["is_start"] is None:
            data["is_start"] = False
        super().__init__(**data)

    @property
    def direct_connections(self) -> frozenset[DirectConnection]:
        """Resolve DirectConnections from registry by source Thing name."""
        registry = get_registry()
        connections = registry.get_direct_connections_by_source(self.name, language=self.language)
        return frozenset(connections)

    @property
    def positional_connections(self) -> PositionalConnection | None:
        """Resolve PositionalConnections from registry by source Thing name.

        Note: There can be at most one PositionalConnection per CompositeThing, since children are ordered. The PositionalConnection itself can reference multiple target Things. **Not all CompositeThings have PositionalConnections.**
        """
        registry = get_registry()
        # direct=False guarantees PositionalConnection
        return registry.get_positional_connections_by_source(self.name, language=self.language)

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

    A Token represents keywords, identifiers, literals, and punctuation -- what you literally see in the source code. Tokens are classified by their purpose, indicating whether they carry semantic or structural meaning versus being mere formatting trivia.
    """

    purpose: Annotated[
        TokenPurpose,
        Field(
            description="""
            Semantic importance classification.

            KEYWORD: Keywords, operators, delimiters (if, {, +)
            IDENTIFIER: Variable/function/class names
            LITERAL: String/number/boolean values
            PUNCTUATION: Whitespace, line continuations (insignificant)
            COMMENT: Code comments (significant but not code)

            Used for filtering: include KEYWORD/IDENTIFIER/LITERAL for semantic analysis,
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
        return f"Token: {self.name}, Purpose: {self.purpose.as_title}, Language: {self.language.as_title}"


class Category(BasedModel):
    """A Category is an abstract classification that groups Things with shared characteristics.

    Categories do not appear in parse trees. They are primarily for classification of related Things. For example, `expression` is a Category containing `binary_expression`,
    `unary_expression`, etc.
    """

    model_config = BasedModel.model_config | ConfigDict(frozen=True)

    name: Annotated[
        CategoryName,
        Field(
            description="The name of the Category.",
            default_factory=lambda name: cat_name_normalizer(name)
            if isinstance(name, str)
            else cat_name_normalizer(name["name"]),  # type: ignore
        ),
    ]

    language: Annotated[
        SemanticSearchLanguage,
        Field(description="The programming language this Category belongs to."),
    ]

    member_thing_names: Annotated[
        frozenset[ThingName],
        Field(
            description="Names of Things that are members of this Category.",
            default_factory=frozenset,
        ),
    ]

    @classmethod
    def from_node_dto(cls, node_dto: NodeTypeDTO) -> Category:
        """Create a Category from the given node DTOs."""
        member_names = frozenset(
            ThingName(node["node"]) for node in cast(list[SimpleNodeTypeDTO], node_dto.subtypes)
        )
        return cls.model_validate({
            "name": CategoryName(node_dto.node),
            "language": node_dto.language,
            "member_thing_names": member_names,
        })

    @field_validator("language", mode="after")
    @classmethod
    def _validate_language(cls, value: Any) -> SemanticSearchLanguage:
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

    @cached_property
    def member_things(self) -> frozenset[CompositeThing | Token]:
        """Resolve member Things from registry by name."""
        registry = get_registry()
        return frozenset(
            thing
            for name in self.member_thing_names
            if (thing := registry.get_thing_by_name(name, language=self.language))
            and not isinstance(thing, Category)
        )

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

    def includes(self, thing_name: ThingName) -> bool:
        """Check if this Category includes the specified Thing name."""
        return thing_name in self.member_thing_names

    def overlap_with(self, other: Category) -> frozenset[ThingOrCategoryType]:
        """Check if this Category shares any member Things with another Category. Returns the overlapping member Thing names.

        Used for analyzing multi-category membership.
        """
        return self.member_things & other.member_things


class Connection(BasedModel):
    """Base class for Connections between Things in a parse tree.

    A Connection is a relationship from a parent Thing to child Thing(s) (an 'edge' in graph terminology). There are three classes of Connections: Direct or Positional. Direct and Positional Connections describe structure.

    Attributes:
        connection_class: Classification of connection type (DIRECT, POSITIONAL)
        target_thing_names: Set of names of target Things this Connection can point to
        allows_multiple: Whether this Connection permits multiple children of specified type(s)
        requires_presence: Whether at least one child of specified type(s) MUST be present

    Relationships:
        - Connection → Many Things (via target_thing_names attribute)
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

    target_thing_names: Annotated[
        tuple[ThingOrCategoryNameType, ...],
        Field(
            description="Names of target Things or Categories this Connection can point to.",
            default_factory=tuple,
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
    def target_things(self) -> frozenset[ThingOrCategoryType]:
        """Resolve target Things/Categories from registry by name."""
        registry = get_registry()
        return frozenset(
            thing
            for name in self.target_thing_names
            if (thing := registry.get_thing_by_name(name, language=self.language))
        )

    def __contains__(self, thing: ThingOrCategoryType | ThingOrCategoryNameType) -> bool:
        """Check if this Connection can point to the specified Thing or Category by name or instance."""
        if isinstance(thing, CompositeThing | Token | Category):
            return thing in self.target_things
        return thing in self.target_thing_names

    def __len__(self) -> int:
        """Get the number of target Things/Categories this Connection can point to."""
        return len(self.target_thing_names)

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

    def can_connect_to(self, thing: ThingOrCategoryType | ThingOrCategoryNameType) -> bool:
        """Check if this Connection can point to the specified Thing.

        This method differs slightly from using __contains__ because it treats Things that can be anywhere (extra) as always connectable.
        """
        if (
            not isinstance(thing, str)
            and hasattr(thing, "can_be_anywhere")
            and cast(Thing | Token, thing).can_be_anywhere
        ):
            return True
        return thing in self

    @computed_field
    @property
    def connection_count(self) -> NonNegativeInt:
        """Get the number of target Things this Connection can point to."""
        return len(self)

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
            default_factory=lambda name: role_name_normalizer(name)  # type: ignore
            if isinstance(name, str)
            else role_name_normalizer(name["role"]),  # type: ignore
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
                "target_thing_names": tuple(ThingName(t["node"]) for t in child_type.types),
                "allows_multiple": child_type.multiple,
                "requires_presence": child_type.required,
                "language": node_dto.language,
            })
            for role, child_type in node_dto.fields.items()
        ]

    def __str__(self) -> str:
        """String representation of the DirectConnection."""
        targets = ", ".join(sorted(str(name) for name in self.target_thing_names))
        return f"DirectConnection: {self.source_thing} --[{self.role}]--{self.constraints.variable}--> [{targets}] (Language: {self.language.variable})"


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

    _connection_class: ClassVar[  # type: ignore
        Literal[ConnectionClass.POSITIONAL]
    ] = ConnectionClass.POSITIONAL  # type: ignore
    # pylance complains because the base class is a union of both DIRECT and POSITIONAL, but this is exactly what we want

    @classmethod
    def from_node_dto(cls, node_dto: NodeTypeDTO) -> PositionalConnection | None:
        """Create PositionalConnections from the given node DTOs."""
        if not node_dto.children:
            return None
        child_type = node_dto.children
        target_names = tuple(ThingName(t["node"]) for t in child_type.types)
        # Create a single PositionalConnection with all targets
        # Position indices are managed at parse-time, not stored per connection
        return cls.model_validate({
            "source_thing": ThingName(node_dto.node),
            "target_thing_names": target_names,
            "allows_multiple": child_type.multiple,
            "requires_presence": child_type.required,
            "language": node_dto.language,
        })

    def __str__(self) -> str:
        """String representation of the PositionalConnection."""
        targets = ", ".join(sorted(str(name) for name in self.target_thing_names))
        return f"PositionalConnections: {self.source_thing} --{self.constraints.variable}--> [{targets}] (Language: {self.language.variable})"


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


_registry: _ThingRegistry | None = None

type ThingType = CompositeThing | Token

type ThingOrCategoryType = CompositeThing | Token | Category

type _TokenDict = dict[ThingName, Token]
type _CompositeThingDict = dict[ThingName, CompositeThing]
type _CategoryDict = dict[CategoryName, Category]


def get_registry() -> _ThingRegistry:
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
    _positional_connections: dict[SemanticSearchLanguage, dict[ThingName, PositionalConnection]]
    """Positional connections by source Thing name."""

    _connections: tuple[
        dict[SemanticSearchLanguage, dict[ThingName, list[DirectConnection]]],
        dict[SemanticSearchLanguage, dict[ThingName, PositionalConnection]],
    ]

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

    def _register_category(self, category: Category) -> None:
        """Register a Category."""
        self._categories[category.language][category.name] = category
        if category.language == SemanticSearchLanguage.JAVASCRIPT:
            self._categories[SemanticSearchLanguage.JSX][category.name] = Category.model_construct(
                category.model_fields_set,
                **(
                    category.model_dump(mode="python", exclude={"language", "member_things"})
                    | {"language": SemanticSearchLanguage.JSX}
                ),
            )
        logger.debug("Registered %s", category)

    def _register_token(self, token: Token) -> None:
        """Register a Token."""
        self._tokens[token.language][token.name] = token
        if token.language == SemanticSearchLanguage.JAVASCRIPT:
            self._tokens[SemanticSearchLanguage.JSX][token.name] = Token.model_construct(
                token.model_fields_set,
                **(
                    token.model_dump(mode="python", exclude={"language", "categories"})
                    | {"language": SemanticSearchLanguage.JSX}
                ),
            )
        logger.debug("Registered %s", token)

    def lookup_normalized_category_name(
        self,
        name: CategoryName | str | LiteralStringT,
        language: SemanticSearchLanguage | None = None,
    ) -> Category | None:
        """Lookup a Category by its normalized name across all languages or a specific language.

        Normalized means we consider it a match regardless of leading underscores.
        """
        if language:
            content = self._categories[language]
            for cat in content.values():
                if cat.name.normalized == name or cat.name == name:
                    return cat
            return None
        for content in self._categories.values():
            for cat in content.values():
                if cat.name.normalized == name or cat.name == name:
                    return cat
        return None

    def register_thing(self, thing: ThingOrCategoryType) -> None:
        """Register a Thing in the appropriate category."""
        if isinstance(thing, Category):
            self._register_category(thing)
            return
        if isinstance(thing, Token):
            self._register_token(thing)
            return
        self._composite_things[thing.language][thing.name] = thing
        if thing.language == SemanticSearchLanguage.JAVASCRIPT:
            self._composite_things[SemanticSearchLanguage.JSX][thing.name] = (
                CompositeThing.model_construct(  # type: ignore
                    thing.model_fields_set,
                    **(
                        thing.model_dump(
                            mode="python",
                            exclude={
                                "language",
                                "direct_connections",
                                "positional_connections",
                                "categories",
                            },
                        )
                        | {"language": SemanticSearchLanguage.JSX}
                    ),
                )
            )
        logger.debug("Registered %s", thing)

    def _register_positional_connection(self, connection: PositionalConnection) -> None:
        """Register a PositionalConnection."""
        if connection.source_thing in self._positional_connections[connection.language]:
            return
        self._positional_connections[connection.language][connection.source_thing] = connection
        logger.debug("Registered %s", connection)
        if connection.language == SemanticSearchLanguage.JAVASCRIPT:
            js_connection = PositionalConnection.model_construct(
                connection.model_fields_set,
                **(
                    connection.model_dump(
                        mode="python",
                        exclude={
                            "language",
                            "constraints",
                            "target_things",
                            "connection_count",
                            "connection_class",
                        },
                    )
                    | {"language": SemanticSearchLanguage.JSX}
                ),
            )
            if (
                connection.source_thing
                not in self._positional_connections[SemanticSearchLanguage.JSX]
            ):
                self._positional_connections[SemanticSearchLanguage.JSX][
                    js_connection.source_thing
                ] = js_connection
                logger.debug("Registered %s", js_connection)

    def register_connection(self, connection: DirectConnection | PositionalConnection) -> None:
        """Register a Connection in the appropriate category."""
        if isinstance(connection, PositionalConnection):
            self._register_positional_connection(connection)
            return
        assert isinstance(connection, DirectConnection)  # noqa: S101
        if connection.source_thing not in self._direct_connections[connection.language]:
            self._direct_connections[connection.language][connection.source_thing] = []
        self._direct_connections[connection.language][connection.source_thing].append(connection)  # type: ignore
        logger.debug("Registered %s", connection)
        if connection.language == SemanticSearchLanguage.JAVASCRIPT:
            js_connection = DirectConnection.model_construct(
                connection.model_fields_set,
                **(
                    connection.model_dump(
                        mode="python",
                        exclude={
                            "language",
                            "constraints",
                            "target_things",
                            "connection_count",
                            "connection_class",
                        },
                    )
                    | {"language": SemanticSearchLanguage.JSX}
                ),
            )
            if (
                not self._direct_connections[SemanticSearchLanguage.JSX]
                or js_connection.source_thing
                not in self._direct_connections[SemanticSearchLanguage.JSX]
            ):
                self._direct_connections[SemanticSearchLanguage.JSX][
                    js_connection.source_thing
                ] = []
            self._direct_connections[SemanticSearchLanguage.JSX][js_connection.source_thing].append(
                js_connection
            )  # type: ignore
            logger.debug("Registered %s", js_connection)

    def register_connections(
        self, connections: Iterable[DirectConnection] | PositionalConnection | None
    ) -> None:
        """Register multiple Connections."""
        if connections is None:
            return
        if isinstance(connections, Connection):
            self.register_connection(connections)
            return
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

    def _get_direct_connections_by_source(
        self, source: ThingName, *, language: SemanticSearchLanguage | None = None
    ) -> Generator[DirectConnection]:
        """Get DirectConnections by their source Thing name across all languages."""
        if language:
            yield from self.direct_connections[language].get(source, [])
        yield from (
            next(
                (
                    conns
                    for content in self._direct_connections.values()
                    for con_name, conns in content.items()
                    if con_name == source
                ),
                [],  # type: ignore
            )
        )

    def _get_positional_connections_by_source(
        self, source: ThingName, *, language: SemanticSearchLanguage | None = None
    ) -> PositionalConnection | None:
        """Get PositionalConnections by their source Thing name across all languages."""
        if language:
            return self.positional_connections[language].get(source)
        return next(
            (
                conn
                for content in self._positional_connections.values()
                for con_name, conn in content.items()
                if con_name == source
            ),
            None,
        )

    def get_positional_connections_by_source(
        self, source: ThingName, *, language: SemanticSearchLanguage | None = None
    ) -> PositionalConnection | None:
        """Get PositionalConnections by their source Thing name across all languages."""
        return self._get_positional_connections_by_source(source, language=language)

    def get_direct_connections_by_source(
        self, source: ThingName, *, language: SemanticSearchLanguage | None = None
    ) -> Generator[DirectConnection]:
        """Get DirectConnections by their source Thing name across all languages."""
        yield from self._get_direct_connections_by_source(source, language=language)

    def register_things(self, things: Iterable[ThingOrCategoryType]) -> None:
        """Register multiple Things."""
        for thing in things:
            self.register_thing(thing)

    @property
    def tokens(self) -> MappingProxyType[SemanticSearchLanguage, _TokenDict]:
        """Get all registered Tokens."""
        return MappingProxyType(self._tokens)

    @property
    def composite_things(self) -> MappingProxyType[SemanticSearchLanguage, _CompositeThingDict]:
        """Get all registered CompositeThings."""
        return MappingProxyType(self._composite_things)

    @property
    def categories(self) -> MappingProxyType[SemanticSearchLanguage, _CategoryDict]:
        """Get all registered Categories."""
        return MappingProxyType(self._categories)

    @property
    def connections(
        self,
    ) -> tuple[
        MappingProxyType[SemanticSearchLanguage, dict[ThingName, list[DirectConnection]]],
        MappingProxyType[SemanticSearchLanguage, dict[ThingName, PositionalConnection]],
    ]:
        """Get all registered Connections."""
        return (
            MappingProxyType(self._direct_connections),
            MappingProxyType(self._positional_connections),
        )

    @property
    def all_cats_and_things(
        self,
    ) -> MappingProxyType[
        SemanticSearchLanguage, MappingProxyType[ThingOrCategoryNameType, ThingOrCategoryType]
    ]:
        """Get all registered Things and Categories combined."""
        return MappingProxyType({
            lang: self._language_content(lang)
            for lang in SemanticSearchLanguage
            if self.has_language(lang)
        })

    @property
    def direct_connections(
        self,
    ) -> MappingProxyType[SemanticSearchLanguage, dict[ThingName, list[DirectConnection]]]:
        """Get all registered DirectConnections."""
        return MappingProxyType(self._direct_connections)

    @property
    def positional_connections(
        self,
    ) -> MappingProxyType[SemanticSearchLanguage, dict[ThingName, PositionalConnection]]:
        """Get all registered PositionalConnections."""
        return MappingProxyType(self._positional_connections)

    def has_language(self, language: SemanticSearchLanguage) -> bool:
        """Check if the registry has any Things or Categories for the specified language."""
        return bool(
            self._tokens.get(language)
            or self._composite_things.get(language)
            or self._categories.get(language)
        )


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
#  - For composite things, we create DirectConnections and PositionalConnections using the same registry and generator system we use for thing and category membership.
#
# Approach: DTO classes for JSON structure, then conversion functions to keep pydantic validation
# cleanly separated from parsing logic. We'll use NamedTuple for DTOs to keep them lightweight, but allow for methods if needed (unlike TypedDict).
# ===========================================================================


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

    @classmethod
    def from_json_data(cls, data: dict[SemanticSearchLanguage, list[dict[str, Any]]]) -> NodeArray:
        """Create NodeArray from JSON data."""
        if len(data) != 1:
            raise ValueError("NodeArray JSON data must contain exactly one language entry.")
        language, nodes_data = next(iter(data.items()))
        nodes = [NodeTypeDTO.model_validate({**node, "language": language}) for node in nodes_data]
        return cls.model_validate(nodes)


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

    def _load_file(self, language: SemanticSearchLanguage) -> list[dict[str, Any]] | None:
        """Load a single node types file for a specific language."""
        if language == SemanticSearchLanguage.JSX:
            language = SemanticSearchLanguage.JAVASCRIPT
        file_path = next(
            (
                file
                for file in self.files
                if SemanticSearchLanguage.from_string(file.stem.replace("-node-types", ""))
                == language
            ),
            None,
        )
        if file_path and file_path.exists():
            return from_json(file_path.read_bytes())
        return None

    def get_all_types(self) -> dict[SemanticSearchLanguage, list[dict[str, Any]]]:
        """Get all types from a node types files.

        Returns:
            List of dictionaries containing raw data from node types files. This is in the tree-sitter node-types.json format.
        """
        if not type(self)._data:
            type(self)._data = self._load_data()
        return type(self)._data

    def get_node(self, language: SemanticSearchLanguage) -> NodeArray | None:
        """Get the NodeArray for a specific language.

        Args:
            language: The language to get the NodeArray for.

        Returns:
            The NodeArray for the specified language, or None if not found.
        """
        if data := self._load_file(language):
            self._data[language] = data
            return NodeArray.from_json_data({language: data})
        return None

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

    def __init__(self, languages: Sequence[SemanticSearchLanguage] | None = None) -> None:
        """Initialize NodeTypeParser with an optional NodeTypeFileLoader.

        Args:
            languages: Optional pre-loaded list of languages to parse; if None, will load all available languages.
        """
        self._languages: frozenset[SemanticSearchLanguage] = frozenset(
            languages or SemanticSearchLanguage
        )

        self._loader = NodeTypeFileLoader()

        self._registry: _ThingRegistry = get_registry()

    # we don't start the process until explicitly called

    @cached_property
    def nodes(self) -> list[NodeArray]:
        """Get the list of NodeArray to parse."""
        if len(self._languages) == len(SemanticSearchLanguage):
            return self._loader.get_all_nodes()
        return cast(
            list[NodeArray],
            [
                self._loader.get_node(lang)
                for lang in self._languages
                if self._loader.get_node(lang)
            ],
        )

    def parse_all_nodes(self) -> list[ThingOrCategoryType]:
        """Parse and translate all node types files into internal representation."""
        assembled_things: list[ThingOrCategoryType] = []
        for node_array in self.nodes:
            assembled_things.extend(self._parse_node_array(node_array) or [])
        return assembled_things

    def parse_for_language(self, language: SemanticSearchLanguage) -> list[ThingOrCategoryType]:
        """Parse and translate node types files for a specific language into internal representation.

        Args:
            language: The language to parse node types for.

        Returns:
            List of parsed and translated node types for the specified language.
        """
        array = self._loader.get_node(language)
        return self._parse_node_array(array) if array else []

    def parse_languages(
        self, languages: Sequence[SemanticSearchLanguage] | None = None
    ) -> list[ThingOrCategoryType]:
        """Parse and translate node types files for a specific set of languages into internal representation.

        Args:
            languages: The languages to parse node types for. If None, will use internal self._languages or all languages if self._languages is empty.

        Returns:
            List of parsed and translated node types for the specified languages.
        """
        assembled_things: list[ThingOrCategoryType] = []
        for language in languages or self._languages:
            if array := self._loader.get_node(language):
                assembled_things.extend(self._parse_node_array(array) or [])
        return assembled_things

    def _create_category(self, node_dto: NodeTypeDTO) -> Category:
        """Create a Category from a NodeTypeDTO and add it to the internal mapping.

        Args:
            node_dto: NodeTypeDTO representing the category to create.
        """
        category = Category.from_node_dto(node_dto)
        self._registry.register_thing(category)
        return category

    def _create_token(self, node_dto: NodeTypeDTO) -> Token:
        """Create a Token from a NodeTypeDTO and add it to the internal mapping.

        Args:
            node_dto: NodeTypeDTO representing the token to create.
        """
        return self._build_thing(node_dto, Token)

    def _get_node_categories(self, node_dto: NodeTypeDTO) -> frozenset[CategoryName]:
        """Get the set of Categories a node belongs to based on its name and language.

        Args:
            node_dto: NodeTypeDTO representing the node to check.

        Returns:
            Set of Categories the node belongs to.
        """
        return frozenset(
            cat_name
            for cat_name, category in self._registry.categories.get(node_dto.language, {}).items()
            if category.includes(ThingName(node_dto.node))
        )

    def _create_composite(self, node_dto: NodeTypeDTO) -> CompositeThing:
        """Create a CompositeThing from a NodeTypeDTO and add it to the internal mapping.

        Args:
            node_dto: NodeTypeDTO representing the composite to create.
        """
        composite = self._build_thing(node_dto, CompositeThing)
        # Create and register DirectConnections
        if node_dto.fields:
            direct_conns = DirectConnection.from_node_dto(node_dto)
            self._registry.register_connections(direct_conns)
        # Create and register PositionalConnections
        if node_dto.children:
            positional_conns = PositionalConnection.from_node_dto(node_dto)
            self._registry.register_connections(positional_conns)
        return composite  # type: ignore

    @overload
    def _build_thing(self, node_dto: NodeTypeDTO, thing: type[Token]) -> Token: ...
    @overload
    def _build_thing(
        self, node_dto: NodeTypeDTO, thing: type[CompositeThing]
    ) -> CompositeThing: ...
    def _build_thing(self, node_dto: NodeTypeDTO, thing: type[ThingType]) -> ThingType:
        category_names = self._get_node_categories(node_dto)
        result = thing.from_node_dto(node_dto, category_names=category_names)
        self._registry.register_thing(cast(ThingOrCategoryType, result))
        return result  # type: ignore

    def _parse_node_array(self, node_array: NodeArray) -> list[ThingOrCategoryType]:
        """Parse and translate a single node types file into internal representation.

        Args:
            node_array: NodeArray containing the list of NodeTypeDTOs to parse.
        """
        assembled_things: list[ThingOrCategoryType] = []
        category_nodes: list[NodeTypeDTO] = []
        token_nodes: list[NodeTypeDTO] = []
        composite_nodes: list[NodeTypeDTO] = []
        for key, group in groupby(
            sorted(node_array.root, key=lambda n: (n.is_category, n.is_token, n.is_composite)),
            key=lambda n: (n.is_category, n.is_token, n.is_composite),
        ):
            match key:
                case True, False, False:
                    category_nodes.extend(group)
                case False, True, False:
                    token_nodes.extend(group)
                case False, False, True:
                    composite_nodes.extend(group)
                case _:
                    logger.warning("Skipping unclassified node types: %s", list(group))
        if category_nodes:
            assembled_things.extend(self._create_category(node_dto) for node_dto in category_nodes)
        if token_nodes:
            assembled_things.extend(self._create_token(node_dto) for node_dto in token_nodes)
        if composite_nodes:
            assembled_things.extend(
                self._create_composite(node_dto) for node_dto in composite_nodes
            )
        return assembled_things


def get_things(
    *, languages: Sequence[SemanticSearchLanguage] | None = None
) -> list[ThingOrCategoryType]:
    """Get all Things and Categories from the registry, optionally filtered by language.

    Args:
        languages: Optional list of languages to filter by; if None, returns all Things and Categories.

    Returns:
        List of Things and Categories matching the specified languages.
    """

    def fetch_for_lang(language: SemanticSearchLanguage) -> list[ThingOrCategoryType]:
        parser = NodeTypeParser(languages=[language])
        return parser.parse_for_language(language)

    things: list[ThingOrCategoryType] = []
    registry = get_registry()
    languages = languages or list(SemanticSearchLanguage)
    if any(registry.has_language(lang) for lang in languages):
        cached_languages = {lang for lang in languages if registry.has_language(lang)}
        if remaining_languages := set(languages) - cached_languages:
            things.extend([thing for lang in remaining_languages for thing in fetch_for_lang(lang)])
        things.extend(
            thing
            for lang in cached_languages
            for thing in registry.all_cats_and_things.get(lang, {}).values()
        )
    else:
        for language in languages:
            things.extend(fetch_for_lang(language))
    return things


# ==========================================================================
#                       Other Notes from Grammar Analysis
# ==========================================================================
#   - Most 'unnamed' *fields* (direct connections) are punctuation or operator symbols (e.g., "=", "+", ";", ",") (81%). The unnamed fields with alpha characters are keywords (e.g., "else", "catch", "finally", "return").
#  - **All** 'named' *fields* (direct connections) are alpha characters (keywords or semantic names).
#  - All *children* (positional connections) are 'named' (is_explicit_rule = True).
#
# ==========================================================================


# Debug harness

# sourcery skip: avoid-builtin-shadow
if __name__ == "__main__":
    has_rich = False
    from importlib.util import find_spec

    if find_spec("rich"):
        from rich.console import Console

        console = Console(markup=True)
        print = console.print  # type: ignore  # noqa: A001
        has_rich = True
    parser = NodeTypeParser()
    all_things = parser.parse_all_nodes()
    print("Parsed Things and Categories:")
    for thing in sorted(
        all_things,
        key=lambda x: (
            x.language.as_title,
            x.is_composite if hasattr(x, "is_composite") else False,  # type: ignore
            x.name,
        ),
    ):
        print(
            f" - [bold dark_orange]{thing.language.as_title}[/bold dark_orange]: [cyan]{thing.name}[/cyan] [green]({thing.kind if hasattr(thing, 'kind') else 'Category'})[/green]"  # type: ignore
            if has_rich
            else f" - {thing.language.as_title}: {thing.name} ({thing.kind if True else 'Category'})"  # type: ignore
        )
    print(
        f"[magenta]Total: {len(all_things)} Things and Categories[/magenta]"
        if has_rich
        else f"Total: {len(all_things)} Things and Categories"
    )  # type: ignore

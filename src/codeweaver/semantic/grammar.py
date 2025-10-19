# sourcery skip: avoid-builtin-shadow, lambdas-should-be-short, no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Parser for tree-sitter node-types.json files with intuitive terminology.

This module provides CodeWeaver's internal representation and API for tree-sitter grammars. After some frustrating experiences with tree-sitter's terminology and structure, we created these types to make working with tree-sitter grammars more intuitive.

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

- **is_file** (bool, Composite only)
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
| 'root' attribute | `is_file` | The starting node of the parse tree |

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
from collections.abc import Iterator
from functools import cached_property
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Literal, TypedDict, cast, override

from pydantic import (
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    computed_field,
    field_validator,
)
from pydantic.dataclasses import dataclass

from codeweaver._common import (
    DATACLASS_CONFIG,
    BasedModel,
    DataclassSerializationMixin,
    LiteralStringT,
)
from codeweaver._utils import lazy_importer
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


if TYPE_CHECKING:
    from codeweaver.semantic.classifications import ThingClass
    from codeweaver.semantic.classifier import GrammarBasedClassifier, GrammarClassificationResult
    from codeweaver.semantic.registry import ThingRegistry
else:
    ThingRegistry = lazy_importer("codeweaver.semantic.registry", "ThingRegistry")
    ThingClass = lazy_importer("codeweaver.semantic.classifications", "ThingClass")
    GrammarBasedClassifier = lazy_importer(
        "codeweaver.semantic.classifier", "GrammarBasedClassifier"
    )
    GrammarClassificationResult = lazy_importer(
        "codeweaver.semantic.classifier", "GrammarClassificationResult"
    )

logger = logging.getLogger()


type ThingType = CompositeThing | Token

type ThingOrCategoryType = CompositeThing | Token | Category

_classifier: GrammarBasedClassifier | None = None


def _get_classifier() -> GrammarBasedClassifier:
    """Lazily import and return the global GrammarBasedClassifier instance."""
    global _classifier
    if _classifier is None:
        from codeweaver.semantic.classifier import GrammarBasedClassifier

        _classifier = GrammarBasedClassifier()
    return _classifier


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
        if not (cat_names := data.get("category_names")):
            data["category_names"] = frozenset()
        else:
            data["category_names"] = frozenset(cat_name_normalizer(name) for name in cat_names)
        super().__init__(**data)

    def __contains__(self, category: Category | CategoryName) -> bool:
        """Check if this Thing belongs to the specified Category."""
        if isinstance(category, Category):
            return category in self.categories if self.has_categories else False
        return category in self.category_names if self.has_categories else False

    @property
    def categories(self) -> frozenset[Category]:
        """Resolve Categories from registry by name."""
        registry_module = lazy_importer("codeweaver.semantic.registry")
        registry = registry_module.get_registry()
        return frozenset(
            cat
            for name in self.category_names
            if (cat := registry.get_category_by_name(name, language=self.language))
        )

    @property
    def has_categories(self) -> bool:
        """Check if this Thing belongs to any Categories."""
        return bool(self.category_names)

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
        if node_dto.is_composite:
            thing_kwargs["is_file"] = node_dto.root
        else:
            thing_kwargs["purpose"] = TokenPurpose.from_node_dto(node_dto)

        return thing_cls.model_validate(thing_kwargs)

    @cached_property
    def classification_result(self) -> GrammarClassificationResult | None:
        """Get the GrammarClassificationResult of this Thing based on its Categories."""
        classifier = _get_classifier()
        return classifier.classify_thing(self.name, self.language)

    @computed_field
    @property
    def classification(self) -> ThingClass | None:
        """Get the ThingClass of this Thing based on its Categories."""
        if classification := self.classification_result:
            return classification.classification.category
        return None

    @computed_field
    def classification_confidence(self) -> NonNegativeFloat | None:
        """Get the confidence score of this Thing's classification."""
        if classification := self.classification_result:
            return classification.confidence
        return None

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
        can_be_anywhere: Whether can appear anywhere in parse tree (usually comments)
        is_file: Whether this Composite is the root of the parse tree (i.e., the start symbol).

    Relationships:
        - Thing → Many Categories (via categories attribute)
        - Categories reference Things via their `member_things` attribute

    A CompositeThing represents complex structures like functions, classes, and expressions, which have direct and/or positional connections to child Things.

    Empirical findings:
        - Average 3-5 possible Direct Connections per CompositeThing
        - Average 1-2 possible Positional Connections per CompositeThing
    """

    is_file: (
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
        if "is_file" not in data or data["is_file"] is None:
            data["is_file"] = False
        super().__init__(**data)

    @property
    def direct_connections(self) -> frozenset[DirectConnection]:
        """Resolve DirectConnections from registry by source Thing name."""
        from codeweaver.semantic.registry import get_registry

        registry = get_registry()
        connections = registry.get_direct_connections_by_source(self.name, language=self.language)
        return frozenset(connections)

    @property
    def positional_connections(self) -> PositionalConnections | None:
        """Resolve PositionalConnections from registry by source Thing name.

        Note: There can be at most one PositionalConnections per CompositeThing, since children are ordered. The PositionalConnections itself can reference multiple target Things. **Not all CompositeThings have PositionalConnections.**
        """
        from codeweaver.semantic.registry import get_registry

        registry = get_registry()
        # direct=False guarantees PositionalConnections
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

    Tree-sitter equivalent: Node with no fields or children (i.e., a leaf node)

    Attributes:
        name: Thing identifier (e.g., "if", "identifier", "string")
        language: Programming language this Token belongs to.
        categories: Set of Category names this Token belongs to, if any.
        kind: Structural classification (always TOKEN)
        purpose: Semantic purpose of the Token (e.g., KEYWORD, IDENTIFIER)
        can_be_anywhere: Whether can appear anywhere in parse tree (usually comments)
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

    name: Annotated[CategoryName, Field(description="The name of the Category.")]

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

    def __init__(self, **data: Any) -> None:
        """Initialize a Category."""
        if members := data.get("member_thing_names"):
            data["member_thing_names"] = frozenset(thing_name_normalizer(name) for name in members)
        data["name"] = cat_name_normalizer(data["name"])
        super().__init__(**data)

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

    @property
    def member_things(self) -> frozenset[CompositeThing | Token]:
        """Resolve member Things from registry by name."""
        from codeweaver.semantic.registry import get_registry

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

    def __init__(self, **data: Any) -> None:
        """Initialize a Connection."""
        from codeweaver.semantic.registry import get_registry

        registry = get_registry()
        if data["target_thing_names"]:
            data["target_thing_names"] = tuple(
                cat_name_normalizer(name)
                if name in registry.categories[data["language"]]
                or cat_name_normalizer(name) in registry.categories[data["language"]]
                else thing_name_normalizer(name)
                for name in data["target_thing_names"]
            )

        super().__init__(**data)

    @property
    def target_things(self) -> frozenset[ThingOrCategoryType]:
        """Resolve target Things/Categories from registry by name."""
        from codeweaver.semantic.registry import get_registry

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

    @property
    def requires_specific_target(self) -> bool:
        """Check if this PositionalConnections requires a specific target Thing."""
        return (
            len(self.target_thing_names) == 1 and self.constraints == ConnectionConstraint.ONLY_ONE
        )


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
    # We have clear segregation between DirectConnection and PositionalConnections via this class variable and separate subclasses

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

    @property
    def specific_target(self) -> ThingOrCategoryType | None:
        """Get the specific target Thing if this DirectConnection requires exactly one specific target; otherwise, return None."""
        if self.requires_specific_target:
            from codeweaver.semantic.registry import get_registry

            registry = get_registry()
            target_name = self.target_thing_names[0]
            return registry.get_thing_by_name(target_name, language=self.language)
        return None


class PositionalConnections(Connection):
    """A PositionalConnections is an ordered structural relationship without a Role.

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
    def from_node_dto(cls, node_dto: NodeTypeDTO) -> PositionalConnections | None:
        """Create PositionalConnections from the given node DTOs."""
        if not node_dto.children:
            return None
        child_type = node_dto.children
        target_names = tuple(ThingName(t["node"]) for t in child_type.types)
        # Create a single PositionalConnections with all targets
        # Position indices are managed at parse-time, not stored per connection
        return cls.model_validate({
            "source_thing": ThingName(node_dto.node),
            "target_thing_names": target_names,
            "allows_multiple": child_type.multiple,
            "requires_presence": child_type.required,
            "language": node_dto.language,
        })

    def __str__(self) -> str:
        """String representation of the PositionalConnections."""
        targets = ", ".join(sorted(str(name) for name in self.target_thing_names))
        return f"PositionalConnections: {self.source_thing} --{self.constraints.variable}--> [{targets}] (Language: {self.language.variable})"


@dataclass(frozen=True, config=DATACLASS_CONFIG, slots=True)
class Grammar(DataclassSerializationMixin):
    """Grammar provides the primary API for evaluating defined grammar rules for a language. We use grammars to analyze observed AST nodes and determine their semantic meaning.

    A grammar represents the complete set of Things, Categories, and Connections for a specific programming language.

    Grammars are the primary objects for semantic analysis and code understanding (comparing observed ASTs to expected structures -- grammars are the expected structure half).
    """

    language: Annotated[
        SemanticSearchLanguage,
        Field(description="The programming language this Grammar represents."),
    ]

    _tokens: Annotated[frozenset[Token], Field(exclude=True, default_factory=frozenset)]

    _composite_things: Annotated[
        frozenset[CompositeThing], Field(exclude=True, default_factory=frozenset)
    ]
    _categories: Annotated[frozenset[Category], Field(exclude=True, default_factory=frozenset)]

    _direct_connections: Annotated[
        frozenset[DirectConnection], Field(exclude=True, default_factory=frozenset)
    ]
    _positional_connections: Annotated[
        frozenset[PositionalConnections], Field(exclude=True, default=frozenset)
    ]

    def __iter__(self) -> Iterator[ThingType]:
        """Iterate over all Things (CompositeThings and Tokens) in this Grammar."""
        yield from self.things

    def __len__(self) -> int:
        """Get the total number of Things (CompositeThings and Tokens) in this Grammar."""
        return self.total_thing_count

    def __contains__(
        self,
        thing: ThingType
        | Category
        | DirectConnection
        | PositionalConnections
        | ThingName
        | CategoryName
        | Role,
    ) -> bool:
        """Check if this Grammar contains the specified Thing by instance or name."""
        if isinstance(thing, CompositeThing | Token):
            return thing in self.things
        if isinstance(thing, Category):
            return thing in self.categories
        if isinstance(thing, DirectConnection | PositionalConnections):
            return thing in self.direct_connections or thing in self.positional_connections
        return (
            any(t.name == thing for t in self.things)
            or any(c.name == thing for c in self.categories)
            or any(dc.role == thing for dc in self.direct_connections)
        )

    @classmethod
    def from_registry(cls, language: SemanticSearchLanguage) -> Grammar:
        """Create a Grammar for the specified language from the ThingRegistry.

        Args:
            language: The programming language for the Grammar.

        Returns:
            A Grammar instance for the specified language.
        """
        try:
            from codeweaver.semantic.registry import get_registry

            registry: ThingRegistry = get_registry()

        except Exception:
            from codeweaver.semantic._node_type_parser import NodeTypeParser

            parser = NodeTypeParser()
            results = parser.parse_languages([language])
            direct: list[DirectConnection] = []
            positional: list[PositionalConnections] = []
            for result in results:
                if isinstance(result, CompositeThing):
                    direct.extend(iter(result.direct_connections))
                    if result.positional_connections:
                        positional.append(result.positional_connections)
            return cls(
                language=language,
                _tokens=frozenset(t for t in results if isinstance(t, Token)),
                _composite_things=frozenset(t for t in results if isinstance(t, CompositeThing)),
                _categories=frozenset(t for t in results if isinstance(t, Category)),
                _direct_connections=frozenset(direct),
                _positional_connections=frozenset(positional),
            )
        else:
            # Manually construct Grammar bypassing validation since registry objects are already validated
            # For pydantic dataclasses, we use object.__new__ and manually set attributes
            instance = object.__new__(cls)
            object.__setattr__(instance, "language", language)
            object.__setattr__(instance, "_tokens", frozenset(registry.tokens[language].values()))
            object.__setattr__(
                instance,
                "_composite_things",
                frozenset(registry.composite_things[language].values()),
            )
            object.__setattr__(
                instance, "_categories", frozenset(registry.categories[language].values())
            )
            object.__setattr__(
                instance,
                "_direct_connections",
                frozenset(
                    conn for lst in registry.direct_connections[language].values() for conn in lst
                ),
            )
            object.__setattr__(
                instance,
                "_positional_connections",
                frozenset(registry.positional_connections[language].values()),
            )
            return instance

    def get_category_by_name(self, name: CategoryName) -> Category | None:
        """Get a Category by its name in this Grammar.

        Args:
            name: The name of the Category to retrieve.

        Returns:
            The Category instance if found; otherwise, None.
        """
        return next((cat for cat in self.categories if cat.name == name), None)

    def get_thing_by_name(self, name: ThingName) -> ThingType | None:
        """Get a Thing (CompositeThing or Token) by its name in this Grammar.

        Args:
            name: The name of the Thing to retrieve.

        Returns:
            The Thing instance if found; otherwise, None.
        """
        return next((thing for thing in self.things if thing.name == name), None)

    @computed_field(repr=False)
    @property
    def tokens(self) -> frozenset[Token]:
        """Get all Tokens in this Grammar."""
        return self._tokens

    @computed_field(repr=False)
    @property
    def composite_things(self) -> frozenset[CompositeThing]:
        """Get all CompositeThings in this Grammar."""
        return self._composite_things

    @computed_field(repr=False)
    @property
    def categories(self) -> frozenset[Category]:
        """Get all Categories in this Grammar."""
        return self._categories

    @computed_field(repr=False)
    @property
    def direct_connections(self) -> frozenset[DirectConnection]:
        """Get all DirectConnections in this Grammar."""
        return self._direct_connections

    @computed_field(repr=False)
    @property
    def positional_connections(self) -> frozenset[PositionalConnections]:
        """Get all PositionalConnections in this Grammar."""
        return self._positional_connections

    @computed_field
    @property
    def things(self) -> frozenset[ThingType]:
        """Get all Things (CompositeThings and Tokens) in this Grammar."""
        return self._composite_things | self._tokens

    @property
    def direct_connections_by_source(self) -> MappingProxyType[ThingName, list[DirectConnection]]:
        """Get DirectConnections grouped by source Thing name."""
        from codeweaver.semantic.registry import get_registry

        return MappingProxyType(get_registry().direct_connections[self.language])

    @property
    def positional_connections_by_source(
        self,
    ) -> MappingProxyType[ThingName, PositionalConnections]:
        """Get PositionalConnections grouped by source Thing name."""
        from codeweaver.semantic.registry import get_registry

        return MappingProxyType(get_registry().positional_connections[self.language])

    @property
    def category_groups(self) -> MappingProxyType[CategoryName, frozenset[ThingType]]:
        """Get Things grouped by Category name."""
        if not self.has_categories:
            return MappingProxyType({})
        category_map: dict[CategoryName, frozenset[ThingType]] = defaultdict(frozenset)
        for category in self._categories:
            category_map[category.name] |= category.member_things

        return MappingProxyType(category_map)

    @computed_field
    @property
    def file_thing(self) -> CompositeThing:
        """Get the grammar's file-CompositeThing (the root or starter CompositeThing)."""
        return next(thing for thing in self._composite_things if thing.is_file)

    @computed_field
    @property
    def total_thing_count(self) -> NonNegativeInt:
        """Get the total number of Things (CompositeThings and Tokens) in this Grammar."""
        return len(self.things)

    @computed_field
    @property
    def composite_count(self) -> NonNegativeInt:
        """Get the number of CompositeThings in this Grammar."""
        return len(self._composite_things)

    @computed_field
    @property
    def token_count(self) -> NonNegativeInt:
        """Get the number of Tokens in this Grammar."""
        return len(self._tokens)

    @computed_field
    @property
    def category_count(self) -> NonNegativeInt:
        """Get the number of Categories in this Grammar."""
        return len(self._categories)

    @computed_field
    @property
    def direct_connection_count(self) -> NonNegativeInt:
        """Get the number of DirectConnections in this Grammar."""
        return len(self._direct_connections)

    @computed_field
    @property
    def positional_connection_count(self) -> NonNegativeInt:
        """Get the number of PositionalConnections in this Grammar."""
        return len(self._positional_connections)

    @computed_field
    @property
    def anywhere_things(self) -> frozenset[ThingType]:
        """Get all Things (CompositeThings and Tokens) that can be anywhere in this Grammar."""
        return frozenset(thing for thing in self.things if thing.can_be_anywhere)

    @computed_field
    @property
    def has_categories(self) -> bool:
        """Check if this Grammar has any Categories."""
        return bool(self._categories)

    def __repr__(self) -> str:
        """String representation of the Grammar."""
        return (
            f"Grammar(Language: {self.language.as_title}, "
            f"CompositeThings: {self.composite_count}, "
            f"Tokens: {self.token_count}, "
            f"AnywhereThings: {self.anywhere_things}, "
            f"Categories: {self.category_count}, "
            f"DirectConnections: {self.direct_connection_count}, "
            f"PositionalConnections: {self.positional_connection_count})"
        )

    def __str__(self) -> str:
        """String representation of the Grammar."""
        return (
            f"Grammar for {self.language.as_title}:\n"
            f"- CompositeThings: {self.composite_count!s}\n"
            f"- Tokens: {self.token_count!s}\n"
            f"- AnywhereThings: {len(self.anywhere_things)!s}\n"
            f"- Categories: {self.category_count!s}\n"
            f"- DirectConnections: {self.direct_connection_count!s}\n"
            f"- PositionalConnections: {self.positional_connection_count!s}\n"
        )

    @property
    def print(self) -> None:
        """Prints a detailed, pretty-formatted, human-readable summary of the Grammar."""
        rich_console = lazy_importer("rich.console").Console(markup=True, emoji=True)
        table = lazy_importer("rich.table").Table(title=f"Grammar for {self.language.as_title}")
        table.add_column("Aspect", style="cyan", no_wrap=True)
        table.add_column("Count", style="magenta")
        table.add_row("CompositeThings", str(self.composite_count))
        table.add_row("Tokens", str(self.token_count))
        table.add_row("AnywhereThings", str(len(self.anywhere_things)))
        table.add_row("Categories", str(self.category_count))
        table.add_row("DirectConnections", str(self.direct_connection_count))
        table.add_row("PositionalConnections", str(self.positional_connection_count))

        all_data: list[str] = []
        if self.categories:
            all_data.append(f"[bold]Categories:[/bold] {self.category_count}")
            all_data.extend(
                f"  - {category.short_str} ({len(category)} members)"
                for category in sorted(self.categories, key=lambda c: c.name)
            )
        if self.composite_things:
            all_data.append(f"\n[bold]CompositeThings:[/bold] {self.composite_count}")
            all_data.extend(
                f"  - {thing.name} ({len(thing.direct_connections)} direct,\n  - {len(thing.positional_connections.target_thing_names) if thing.positional_connections else 0} positional connections)"
                for thing in sorted(self.composite_things, key=lambda t: t.name)
            )
        if self.tokens:
            all_data.append(f"\n[bold]Tokens:[/bold] {self.token_count}")
            all_data.extend(
                f"  - {token.name} ({token.purpose.as_title})"
                for token in sorted(self.tokens, key=lambda t: t.name)
            )
        rich_console.print(table)
        if all_data:
            rich_console.print("\n".join(all_data))


def get_grammar(language: SemanticSearchLanguage) -> Grammar:
    """Get the Grammar for the specified programming language.

    Args:
        language (SemanticSearchLanguage): The programming language to get the Grammar for.

    Returns:
        Grammar: The Grammar for the specified programming language.
    """
    return Grammar.from_registry(language)


def get_all_grammars() -> MappingProxyType[SemanticSearchLanguage, Grammar]:
    """Get all available Grammars for all supported programming languages.

    Returns:
        dict: A dictionary mapping each SemanticSearchLanguage to its corresponding Grammar.
    """
    return MappingProxyType({
        language: get_grammar(language) for language in SemanticSearchLanguage
    })


if __name__ == "__main__":
    grammars = get_all_grammars()
    rich_console = lazy_importer("rich.console").Console(markup=True, emoji=True)
    for language, grammar in grammars.items():
        print(f"\n=== Grammar for {language.as_title} ===")
        rich_console.print(grammar.print)

__all__ = (
    "Category",
    "CompositeThing",
    "Connection",
    "DirectConnection",
    "Grammar",
    "PositionalConnections",
    "Thing",
    "ThingOrCategoryNameType",
    "ThingOrCategoryType",
    "ThingType",
    "Token",
    "get_all_grammars",
    "get_grammar",
)


# ==========================================================================
#                       Other Notes from Grammar Analysis
# ==========================================================================
#   - Most 'unnamed' *fields* (direct connections) are punctuation or operator symbols (e.g., "=", "+", ";", ",") (81%). The unnamed fields with alpha characters are keywords (e.g., "else", "catch", "finally", "return").
#  - **All** 'named' *fields* (direct connections) are alpha characters (keywords or semantic names).
#  - All *children* (positional connections) are 'named' (is_explicit_rule = True).
#
# ==========================================================================

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# sourcery skip: comment:docstrings-for-functions
"""Common internal types for semantic analysis.

Overview:
- Data transfer objects (DTOs) for parsing node types files. These are intermediate structures used during parsing and conversion before converting to CodeWeaver's internal representation (CompositeThing, Token, Category, Direct and Positional Connections).
"""

from __future__ import annotations

import re

from enum import Flag, auto
from typing import Annotated, Literal, NamedTuple, NewType, TypedDict, cast

from pydantic import ConfigDict, Field, PrivateAttr, computed_field

from codeweaver.core import BasedModel, BaseEnum, LiteralStringT
from codeweaver.core.language import SemanticSearchLanguage


Role = NewType("Role", LiteralStringT)
CategoryName = NewType("CategoryName", LiteralStringT)
ThingName = NewType("ThingName", LiteralStringT)

type ThingOrCategoryNameType = ThingName | CategoryName


class SimpleNodeTypeDTO(TypedDict):
    """TypedDict for a simple node type object in the node types file (objects with no attributes besides `type` and `named`). While these appear in the node-types file at the top level (all Tokens are of this form unless only 'extra' is present without fields [majority of extra cases, which are rare themselves]), they also appear nested within `subtypes`, `fields`, and `children`. We only use it for nested objects, not top-level ones.

    Note: This is an intermediate structure used during parsing and conversion. It is not part of the final internal representation.

    Attributes:
        node: Name of the node type (alias for `type`)
        named: Whether the node type is named (true) or anonymous (false)
    """

    # type is a Python keyword, so we use 'node' here and map it in the Field to prevent shadowing
    node: Annotated[
        LiteralStringT, Field(description="Name of the node type.", validation_alias="type")
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
        Field(
            description="List of type objects for the allowed child types.", default_factory=list
        ),
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

    model_config = BasedModel.model_config | ConfigDict(frozen=True, populate_by_name=True)

    language: Annotated[SemanticSearchLanguage, PrivateAttr()]

    # type is a Python keyword, so we use 'node' here and map it in the Field to prevent shadowing
    node: Annotated[
        LiteralStringT, Field(description="Name of the node type.", validation_alias="type")
    ]
    named: Annotated[
        bool, Field(description="Whether the node type is named (true) or anonymous (false).")
    ]
    root: (
        Annotated[bool, Field(description="Whether the node type is the root of the parse tree.")]
        | None
    ) = None
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
        from codeweaver.semantic.constants import get_token_patterns_sync

        patterns = get_token_patterns_sync()
        not_symbol = patterns["not_symbol"]
        if not_symbol is None:
            raise ValueError("Token patterns have not been initialized.")
        return self.is_token and not not_symbol.match(self.node)

    @computed_field
    @property
    def is_operator_token(self) -> bool:
        """Check if this node type is an Operator Token (a Token that is an operator)."""
        from codeweaver.semantic.constants import get_token_patterns_sync

        patterns = get_token_patterns_sync()
        if patterns["operator"] is None:
            raise ValueError("Token patterns have not been initialized.")
        return self.is_symbol_token and patterns["operator"].match(self.node) is not None

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


__all__ = ("ChildTypeDTO", "NodeTypeDTO", "SimpleNodeTypeDTO")


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


class TokenPurpose(BaseEnum):
    """Classification of Token purpose or semantic use.

    - KEYWORD: keywords
    - OPERATOR: operators
    - IDENTIFIER: variable/function/type names
    - LITERAL: string/number/boolean literals
    - PUNCTUATION: whitespace, punctuation, formatting tokens
    - COMMENT: comments

    A Token can be classified by its purpose, indicating whether it carries semantic or structural meaning versus being mere formatting trivia. This classification helps in filtering Tokens during semantic analysis while preserving them for formatting purposes.
    """

    KEYWORD = "keyword"
    """Keyword literals like 'break', 'if', 'return'. Also includes type literals like 'int', 'string', 'float'. (Literal here meaning the actual word, but different from LITERAL because these are words with built-in semantic meaning for the language.)"""
    OPERATOR = "operator"
    """Operators like '+', '-', '==', '&&', etc."""
    IDENTIFIER = "identifier"
    """Variable/function/type names."""
    LITERAL = "literal"
    """String/number/boolean literals."""
    PUNCTUATION = "punctuation"
    """Whitespace, punctuation, formatting tokens."""
    COMMENT = "comment"
    """Comments, both single-line and multi-line."""

    @property
    def is_significant(self) -> bool:
        """Whether this TokenPurpose indicates a significant Token.

        Significant Tokens carry semantic/structural meaning, while punctuation ones do not.
        """
        return self in {
            TokenPurpose.KEYWORD,
            TokenPurpose.IDENTIFIER,
            TokenPurpose.LITERAL,
            TokenPurpose.COMMENT,
        }

    @property
    def is_trivial(self) -> bool:
        """Whether this TokenPurpose indicates a punctuation Token.

        Trivial Tokens do not carry semantic/structural meaning.
        """
        return self is TokenPurpose.PUNCTUATION

    @property
    def identifies(self) -> bool:
        """Whether this TokenPurpose indicates an identifying Token.

        Identifying Tokens are used for names of variables, functions, types, etc.
        """
        return self in {TokenPurpose.IDENTIFIER, TokenPurpose.LITERAL}

    @classmethod
    def from_node_dto(cls, node_dto: NodeTypeDTO) -> TokenPurpose:
        """Create TokenPurpose from NodeTypeDTO."""
        if node_dto.is_composite or node_dto.is_category:
            raise ValueError("Cannot determine TokenPurpose for Composite or Category nodes")
        from codeweaver.semantic.constants import (
            LANGUAGE_SPECIFIC_TOKEN_EXCEPTIONS,
            get_token_patterns_sync,
        )

        if (
            node_dto.language in LANGUAGE_SPECIFIC_TOKEN_EXCEPTIONS
            and node_dto.node in LANGUAGE_SPECIFIC_TOKEN_EXCEPTIONS[node_dto.language]
        ):
            return cls.from_string(
                LANGUAGE_SPECIFIC_TOKEN_EXCEPTIONS[node_dto.language][node_dto.node]
            )
        if "comment" in node_dto.node.lower() or node_dto.node.lower() == "comment":
            return cls.COMMENT
        patterns = get_token_patterns_sync()
        if any(pattern for pattern in patterns.values() if pattern is None):
            raise ValueError("Token patterns have not been initialized.")
        if (
            "identifier" in node_dto.node.lower()
            or node_dto.node.lower() == "identifier"
            or cast(re.Pattern[str], patterns["identifier"]).match(node_dto.node)
        ):
            return cls.IDENTIFIER
        if cast(re.Pattern[str], patterns["keyword"]).match(node_dto.node):
            return cls.KEYWORD
        if cast(re.Pattern[str], patterns["operator"]).match(node_dto.node):
            return cls.OPERATOR
        return (
            cls.LITERAL
            if cast(re.Pattern[str], patterns["literal"]).match(node_dto.node)
            else cls.PUNCTUATION
        )


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

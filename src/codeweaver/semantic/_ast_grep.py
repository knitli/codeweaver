# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# sourcery skip: comment:docstrings-for-functions
"""Custom wrappers around ast-grep's core types to add functionality and serialization."""

from __future__ import annotations

import contextlib

from collections.abc import Iterator
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, NamedTuple, Unpack, cast, overload

from ast_grep_py import (
    Config,
    CustomLang,
    NthChild,
    Pattern,
    Pos,
    PosRule,
    RangeRule,
    Relation,
    Rule,
    RuleWithoutNot,
)
from ast_grep_py import Range as SgRange
from ast_grep_py import SgNode as AstGrepNode
from ast_grep_py import SgRoot as AstGrepRoot
from pydantic import UUID7, ConfigDict, Field, NonNegativeInt, PositiveInt, computed_field

from codeweaver._common import BasedModel, BaseEnum
from codeweaver._utils import uuid7
from codeweaver.language import SemanticSearchLanguage
from codeweaver.services.textify import humanize


# Lazy imports to avoid circular dependencies
if TYPE_CHECKING:
    from codeweaver.semantic.classifications import ImportanceScores, SemanticClass


# re-export Ast Grep's rules and config types:
AstGrepSearchTypes = (
    Config,
    Pattern,
    NthChild,
    PosRule,
    RangeRule,
    RuleWithoutNot,
    Rule,
    Relation,
    CustomLang,
)


class MetaVar(str, BaseEnum):
    """Represents a meta variable in the AST."""

    CAPTURE = "$"
    NON_CAPTURE = "$_"
    UNNAMED_CAPTURE = "$$"
    MULTI_CAPTURE = "$$$"

    __slots__ = ()

    def __str__(self) -> str:
        """Return the string representation of the meta variable."""
        return self.value

    def to_metavar(
        self,
        variable_name: Annotated[
            str, Field(description="""The name of the variable", pattern="[A-Z0-9_]+""")
        ],
    ) -> str:
        """Return the pattern representation of the meta variable."""
        return f"{self!s}{variable_name.upper()}"


class Strictness(str, BaseEnum):
    """Represents the strictness level for code analysis."""

    CST = "cst"
    SMART = "smart"
    AST = "ast"
    RELAXED = "relaxed"
    SIGNATURE = "signature"

    __slots__ = ()


class Position(NamedTuple):
    """Represents a `Pos` from ast-grep with pydantic validation. The position of the node in the source code."""

    line: PositiveInt
    column: PositiveInt
    idx: Annotated[
        NonNegativeInt,
        Field(serialization_alias="index", description="""Byte index in the source"""),
    ]

    @classmethod
    def from_pos(cls, pos: Pos) -> Position:
        """Create a Position from an ast-grep Pos."""
        return Position(line=pos.line, column=pos.column, idx=pos.index)


class Range(NamedTuple):
    """Represents a `Range` from ast-grep with pydantic validation. The range of the node in the source code."""

    start: Position
    end: Position

    @classmethod
    def from_sg_range(cls, sg_range: SgRange) -> Range:
        """Create a Range from an ast-grep range."""
        start = Position.from_pos(sg_range.start)
        end = Position.from_pos(sg_range.end)
        return Range(start=start, end=end)


# This may not be the doctrinal way to use a generic,
# but: 1) It makes type checkers happy, 2) It makes it very clear what's going on.
class RootAstNode[SgRoot: (AstGrepRoot)](BasedModel):
    """Wrapper for SgRoot to make it serializable and provide additional functionality."""

    model_config = BasedModel.model_config | ConfigDict(arbitrary_types_allowed=True)

    _root: Annotated[AstGrepRoot, Field(description="""The underlying SgRoot""", exclude=True)]

    @classmethod
    def from_sg_root(cls, sg_root: AstGrepRoot) -> RootAstNode[SgRoot]:
        """Create a RootAstNode from an ast-grep SgRoot."""
        return cls(_root=sg_root)

    @classmethod
    def from_sg_node(cls, sg_node: AstGrepNode) -> RootAstNode[SgRoot]:
        """Create a RootAstNode from an ast-grep SgNode."""
        return cls(_root=sg_node.get_root())

    @computed_field
    @cached_property
    def filename(self) -> str:
        """Get the filename from the SgRoot."""
        return self._root.filename()

    @computed_field()
    @cached_property
    def root(self) -> RootAstNode[SgRoot]:
        """Return the parent root node, also wrapped as a RootAstNode."""
        return type(self).from_sg_node(self._root.root())

    @classmethod
    def from_file(cls, file_path: Path) -> RootAstNode[SgRoot]:
        """Create a RootAstNode from a file."""
        from codeweaver.language import SemanticSearchLanguage

        content = file_path.read_text()
        language = SemanticSearchLanguage.from_extension(file_path.suffix)
        return cls.from_sg_root(AstGrepRoot(content, str(language)))


class AstNode[SgNode: (AstGrepNode)](BasedModel):
    """Wrapper for `SgNode` to make it serializable and give it extra functionality."""

    model_config = BasedModel.model_config | ConfigDict(arbitrary_types_allowed=True)

    language: Annotated[SemanticSearchLanguage, Field(description="""The language of the node""")]

    _node: Annotated[AstGrepNode, Field(description="""The underlying SgNode""", exclude=True)]

    node_id: Annotated[UUID7, Field(description="""The unique ID of the node""")] = uuid7()

    parent_node_id: Annotated[UUID7 | None, Field(description="""The ID of the parent node""")] = (
        None
    )

    def __init__(
        self,
        node: AstGrepNode,
        language: SemanticSearchLanguage | None = None,
        node_id: UUID7 | None = None,
        parent_node_id: UUID7 | None = None,
    ) -> None:
        """Initialize the AstNode and set the parent_node_id if applicable."""
        node_id = node_id or uuid7()
        if parent_node_id is None and (parent_node := self.parent):
            parent_node_id = getattr(parent_node, "node_id", None)
            if parent_node_id is None:
                parent_node_id = uuid7()
                parent_node.node_id = parent_node_id
        if language is None:
            with contextlib.suppress(Exception):
                language = SemanticSearchLanguage.from_extension(
                    Path(node.get_root().filename()).suffix
                )
        if language is None:
            raise ValueError(
                "Language must be provided or inferable from the node's root filename."
            )
        self.language = language
        self._node = node
        self.node_id = node_id
        self.parent_node_id = parent_node_id
        super().__init__()

    @classmethod
    def from_sg_node(
        cls, sg_node: AstGrepNode, language: SemanticSearchLanguage
    ) -> AstNode[SgNode]:
        """Create a AstNode from an ast-grep `SgNode`."""
        return cls(language=language, node=sg_node)

    @computed_field
    @cached_property
    def symbol(self) -> str:
        """Get a symbolic representation of the node."""
        raise NotImplementedError("Symbol generation is not implemented yet.")

    @computed_field
    @cached_property
    def title(self) -> str:
        """Get a human-readable title for the node."""
        kind = humanize(self.kind)
        language = humanize(str(self.language))
        text_snippet = humanize(self.text.strip().splitlines()[0])
        if len(text_snippet) > 25:
            text_snippet = f"{text_snippet[:22]}..."
        return f"{language}-{kind}: '{text_snippet}'"

    @computed_field
    @cached_property
    def range(self) -> Range:
        """Get the range of the node."""
        node_range: SgRange = self._node.range()
        return Range.from_sg_range(node_range)

    @computed_field
    @cached_property
    def is_leaf(self) -> bool:
        """Check if the node is a leaf."""
        return self._node.is_leaf()

    @computed_field
    @cached_property
    def is_named(self) -> bool:
        """Check if the node is named."""
        return self._node.is_named()

    @computed_field
    @cached_property
    def is_named_leaf(self) -> bool:
        """Check if the node is a named leaf."""
        return self._node.is_named_leaf()

    @computed_field
    @cached_property
    def kind(self) -> str:
        """Get the kind of the node."""
        return self._node.kind()

    @computed_field
    @cached_property
    def text(self) -> str:
        """Get the text of the node."""
        return self._node.text()

    @computed_field
    @cached_property
    def _root(self) -> RootAstNode[AstGrepRoot]:
        """Get the root of the node."""
        return cast(RootAstNode[AstGrepRoot], RootAstNode.from_sg_root(self._node.get_root()))

    def __getitem__(self, meta_var: str) -> AstNode[SgNode]:
        """Get the child node for the given meta variable."""
        return type(self).from_sg_node(cast(SgNode, self._node[meta_var]), self.language)

    # Refinement API

    def matches(self, **rule: Unpack[Rule]) -> bool:
        """Check if the node matches the given rule."""
        return self._node.matches(**rule)

    def inside(self, **rule: Unpack[Rule]) -> bool:
        """Check if the node is inside the given rule."""
        return self._node.inside(**rule)

    def has(self, **rule: Unpack[Rule]) -> bool:
        """Check if the node has the given rule."""
        return self._node.has(**rule)

    def precedes(self, **rule: Unpack[Rule]) -> bool:
        """Check if the node precedes the given rule."""
        return self._node.precedes(**rule)

    def follows(self, **rule: Unpack[Rule]) -> bool:
        """Check if the node follows the given rule."""
        return self._node.follows(**rule)

    def get_match(self, meta_var: str) -> AstNode[SgNode] | None:
        """Get the match for the given meta variable."""
        return (
            type(self).from_sg_node(cast(SgNode, self._node.get_match(meta_var)), self.language)
            if self._node.get_match(meta_var)
            else None
        )

    def get_multiple_matches(self, meta_var: str) -> list[AstNode[SgNode]]:
        """Get the matches for the given meta variable."""
        return [
            type(self).from_sg_node(cast(SgNode, match), self.language)
            for match in self._node.get_multiple_matches(meta_var)
        ]

    def get_transformed(self, meta_var: str) -> str | None:
        """Get the transformed text for the given meta variable."""
        return self._node.get_transformed(meta_var)

    # Search API

    @overload
    def find(self, config: None, **rule: Unpack[Rule]) -> AstNode[SgNode]: ...
    @overload
    def find(self, config: Config) -> AstNode[SgNode]: ...
    def find(self, config: Config | None = None, **rule: Any) -> AstNode[SgNode]:
        """Find a node using a config."""
        if config:
            return type(self).from_sg_node(cast(SgNode, self._node.find(config)), self.language)
        return type(self).from_sg_node(cast(SgNode, self._node.find(**rule)), self.language)

    @overload
    def find_all(self, config: None, **rule: Unpack[Rule]) -> tuple[AstNode[SgNode], ...]: ...
    @overload
    def find_all(self, config: Config) -> tuple[AstNode[SgNode], ...]: ...
    def find_all(self, config: Config | None = None, **rule: Any) -> tuple[AstNode[SgNode], ...]:
        """Find all nodes using a config."""
        if config:
            return tuple(
                type(self).from_sg_node(node, self.language) for node in self._node.find_all(config)
            )
        return tuple(
            type(self).from_sg_node(node, self.language) for node in self._node.find_all(**rule)
        )

    # traversal API
    def get_root(self) -> RootAstNode[AstGrepRoot]:
        """Get the root of the node."""
        return self._root

    def child(self, nth: NonNegativeInt) -> AstNode[SgNode] | None:
        """Get the nth child of the node."""
        return tuple(self.children)[nth] if nth < len(tuple(self.children)) else None

    @computed_field
    @cached_property
    def _ancestor_list(self) -> tuple[AstNode[SgNode], ...]:
        """Get the ancestors of the node."""
        return tuple(
            type(self).from_sg_node(ancestor, self.language)
            for ancestor in self._node.ancestors()
            if self._node.ancestors() and ancestor
        )

    def ancestors(self) -> Iterator[AstNode[SgNode]]:
        """Get the ancestors of the node."""
        yield from self._ancestor_list

    @computed_field
    @cached_property
    def children(self) -> Iterator[AstNode[SgNode]]:
        """Get the children of the node."""
        yield from (
            type(self).from_sg_node(child, self.language) for child in self._node.children()
        )

    @computed_field
    @cached_property
    def parent(self) -> AstNode[SgNode] | None:
        """Get the parent of the node."""
        parent_node = self._node.parent()
        return type(self).from_sg_node(parent_node, self.language) if parent_node else None

    def next(self) -> AstNode[SgNode] | None:
        """Get the next sibling of the node."""
        if not self._node.next():
            return None
        return type(self).from_sg_node(cast(SgNode, self._node.next()), self.language)

    def next_all(self) -> Iterator[AstNode[SgNode]]:
        """Get all next siblings of the node."""
        yield from (type(self).from_sg_node(n, self.language) for n in self._node.next_all())

    def prev(self) -> AstNode[SgNode] | None:
        """Get the previous sibling of the node."""
        if not self._node.prev():
            return None
        return type(self).from_sg_node(cast(SgNode, self._node.prev()), self.language)

    def prev_all(self) -> Iterator[AstNode[SgNode]]:
        """Get all previous siblings of the node."""
        yield from (type(self).from_sg_node(p, self.language) for p in self._node.prev_all())

    # Semantic classification and scoring methods

    @cached_property
    def semantic_category(self) -> SemanticClass:
        """Get the semantic category for this node using the global mapper."""
        from codeweaver.semantic import get_node_mapper

        mapper = get_node_mapper()
        return mapper.classify_node_type(self.kind, self.language)

    @computed_field
    @cached_property
    def importance_score(self) -> ImportanceScores:
        """Calculate the importance score for this node."""
        from codeweaver.semantic import SemanticScorer

        scorer = SemanticScorer(
            depth_penalty_factor=0.02,
            size_bonus_threshold=50,
            size_bonus_factor=0.1,
            root_bonus=0.07,
        )
        return scorer.calculate_importance_score(self.semantic_category, self)  # pyright: ignore[reportArgumentType]

    def get_classification_confidence(self) -> float:
        """Get the confidence level for the semantic classification of this node."""
        from codeweaver.semantic import get_node_mapper

        mapper = get_node_mapper()
        return mapper.get_classification_confidence(self.kind, self.language)

    def replace(self, _new_text: str) -> str:
        """Replace the text of the node with new_text."""
        raise NotImplementedError("Edit functionality is not implemented yet.")

    def commit_edits(self, _edits: list[str]) -> str:
        """Commit a list of edits to the source code."""
        raise NotImplementedError("Edit functionality is not implemented yet.")


__all__ = (
    "AstNode",
    "Config",
    "CustomLang",
    "NthChild",
    "Pattern",
    "Pos",
    "PosRule",
    "Position",
    "Range",
    "RangeRule",
    "Relation",
    "RootAstNode",
    "Rule",
    "RuleWithoutNot",
)

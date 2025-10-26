# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# sourcery skip: comment:docstrings-for-functions
"""Custom wrappers around ast-grep's core types to add functionality and serialization.

Like the rest of CodeWeaver, we use our specific vocabulary for concepts to make roles and relationships more clear. See [codeweaver.semantic.grammar_things] for more details.

## The Short(er) Version

### Translation Table

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
| 'root' attribute | `is_file` | It's the file. |

### What These Things Are

- **Thing**: A concrete node in the parse tree. Everything in the tree is a Thing. Things can be Token things or CompositeThings.
- **Token**: A Token is a solitary thing -- in tree-sitter terms, it is a leaf node with no fields or children. Tokens are the "words" of the programming language, like keywords, operators, and identifiers.
- **CompositeThing**: A CompositeThing is a thing that has fields and/or children (direct or positional connections). CompositeThings are the "phrases" of the programming language, like expressions, statements, and declarations. CompositeThings are always made up of other Things (Tokens or CompositeThings).
- **Category**: A Category is an abstract type that can have multiple subtypes. Categories do not appear in the parse tree, but they are used to group related Things together. For example, the Category "expression" might include the subtypes "binary_expression", "call_expression", and "literal". While they don't appear in the parse tree, they can be used in search patterns to match any of their subtypes. Since there aren't very many categories, they can be an easy way to write patterns that target specific functional parts of the code.
- **Direct Connection**: A Direct Connection is a named field in a CompositeThing that has a specific semantic Role. For example, in a function declaration, the "name" field is a Direct Connection with the Role "function_name". Direct Connections are not ordered, and they can be optional or required (the `constraints` attribute provides this information, which is based on the `allows_multiple` and `requires_presence` attributes). A CompositeThing can have multiple Direct Connections, and each connection can be to more than one target (its `target_things` attribute), and they can be of different types (Token, CompositeThing, and even Category), but it must have at least one *possible* Direct Connection. Depending on constraints, a CompositeThing may appear in the AST without an connections of any kind.
- **Positional Connection**: A Positional Connection is a child of a CompositeThing that does not have a specific semantic Role. Positional Connections are ordered, and they can be optional or required (the `constraints` attribute provides this information, which is based on the `allows_multiple` and `requires_presence` attributes). Because of their ordered nature, a CompositeThing will either have 1 or none of a PositionalConnections type. A PositionalConnections may reference multiple types (its `target_things` attribute), which is ordered.
- **Role**: A Role is the semantic function of a Direct Connection, like 'name' for a function's name, or 'condition' for an if statement's condition.
- **Meta Variable**: A Meta Variable is a special syntax used in search patterns to capture nodes in the AST. Meta Variables are prefixed with a `$` symbol, and they can be named or unnamed. Named Meta Variables are used to capture specific nodes, while unnamed Meta Variables are used to capture any node. There are also Multi-Capture Meta Variables that can capture multiple nodes. See [the ast-grep documentation](https://ast-grep.github.io/docs/patterns/metavars/) for more details.
- **Rules** - Ast-grep provides a rich rule system for defining more complex search patterns than what you can do with just meta variables. See [the ast-grep documentation](https://ast-grep.github.io/guide/rule-config.html) for more details.

## Connections and Navigation

**All connections defined in the grammar are optional.** Sort of. For direct connections, about 36% of them require exactly one target with only one possible target type, so if one of those is present, then so will its target (and probably vice versa). Only about 8% of positional connections require exactly one target with only one possible target type, so positional connections are much more likely to be absent. But in general, you should always code defensively and assume that any connection may be absent.

A common way to move ("traverse") through the AST is to start at the root node (the FileThing) and then move down through its children, and then their children, and so on. You can also move up the tree to a node's parent, or sideways to its siblings. Each AstThing has methods for moving in these directions, as well as properties for accessing its connections.
"""

from __future__ import annotations

import contextlib
import logging

from collections.abc import Iterator, Sequence
from functools import cached_property
from pathlib import Path
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    LiteralString,
    NamedTuple,
    Unpack,
    cast,
    overload,
)

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
    SgNode,
)
from ast_grep_py import Range as SgRange
from ast_grep_py import SgNode as AstGrepNode
from ast_grep_py import SgRoot as AstGrepRoot
from pydantic import (
    UUID7,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    PrivateAttr,
    computed_field,
)

from codeweaver.common.utils import LazyImport, lazy_import, uuid7
from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.core.types.aliases import FileExt, LiteralStringT, ThingName, ThingNameT
from codeweaver.core.types.enum import AnonymityConversion, BaseEnum
from codeweaver.core.types.models import BasedModel
from codeweaver.engine import humanize

# Runtime imports needed for cast operations and type checking
from codeweaver.semantic.grammar import Category, CompositeThing, Token


# type-only imports
if TYPE_CHECKING:
    from codeweaver.core.types.aliases import FilteredKey
    from codeweaver.core.types.enum import AnonymityConversion
    from codeweaver.semantic.classifications import AgentTask, ImportanceScores, ThingClass

logger = logging.getLogger(__name__)

registry_module: LazyImport[ModuleType] = lazy_import("codeweaver.semantic.registry")

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
    """Concrete Syntax Tree - strictest. All things in the pattern and target code must match; doesn't skip things."""
    SMART = "smart"
    """Smart - default. Must match all things in the pattern, but skips unnamed things in the target code."""
    AST = "ast"
    """Abstract Syntax Tree - more flexible. Skips unnamed things in both the pattern and target code."""
    RELAXED = "relaxed"
    """Relaxed - like AST, but also ignores comments."""
    SIGNATURE = "signature"
    """Signature - *only* matches named things' *names* (kinds) and ignores everything else."""

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

    @classmethod
    def to_pos(cls, position: Position) -> Pos:
        """Convert a Position to an ast-grep Pos."""
        # I'm not sure why pylance says these fields don't exist, they clearly do.
        return Pos(line=position.line, column=position.column, index=position.idx)  # type: ignore


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

    @classmethod
    def to_sg_range(cls, sg_range: Range) -> SgRange:
        """Convert a Range to an ast-grep Range."""
        start = Position.to_pos(sg_range.start)
        end = Position.to_pos(sg_range.end)
        # again, not sure why pylance complains about these fields not existing
        return SgRange(start=start, end=end)  # type: ignore


# This may not be the doctrinal way to use a generic,
# but: 1) It makes type checkers happy, 2) It makes it very clear what's going on.
class FileThing[SgRoot: (AstGrepRoot)](BasedModel):
    """Wrapper for SgRoot to make it serializable and provide additional functionality.

    `FileThing` is the root node of an AST, representing the entire source file. It provides access to the filename and the root node of the AST. We call it a FileThing to make its role as the start of a file's syntax tree more explicit (because... root... of what?). It is a file, and a Thing.
    """

    model_config = BasedModel.model_config | ConfigDict(arbitrary_types_allowed=True)

    _root: AstGrepRoot = PrivateAttr()

    _id: UUID7 = PrivateAttr(default_factory=uuid7)

    _file_path: Path | None = PrivateAttr(default=None)

    def _telemetry_keys(self) -> dict[FilteredKey, AnonymityConversion]:
        from codeweaver.core.types.aliases import FilteredKey
        from codeweaver.core.types.enum import AnonymityConversion

        return {
            FilteredKey("_root"): AnonymityConversion.HASH,
            FilteredKey("filename"): AnonymityConversion.HASH,
        }

    @classmethod
    def from_sg_root(cls, sg_root: AstGrepRoot, file_path: Path | None = None) -> FileThing[SgRoot]:
        """Create a FileThing from an ast-grep SgRoot."""
        instance = cls.model_construct()
        instance._root = sg_root
        instance._file_path = file_path
        return instance

    @classmethod
    def from_sg_node(cls, sg_node: AstGrepNode) -> FileThing[SgRoot]:
        """Create a FileThing from an ast-grep SgNode."""
        instance = cls.model_construct()
        instance._root = sg_node.get_root()
        return instance

    @computed_field
    @cached_property
    def filename(self) -> Path:
        """Get the filename from the SgRoot or the stored file path."""
        if self._file_path is not None:
            return self._file_path
        return Path(self._root.filename())

    @property
    def id(self) -> UUID7:
        """Return the unique ID of the file thing."""
        return self._id

    @property
    def root(self) -> AstThing[SgNode]:
        """Return the parent root node, also wrapped as a FileThing."""
        if language := SemanticSearchLanguage.from_extension(
            FileExt(cast(LiteralStringT, (self.filename.suffix or self.filename.name)))
        ):
            return cast(
                AstThing[SgNode],
                AstThing.from_sg_node(
                    self._root.root(), language, thing_id=self._id, parent_thing_id=self._id
                ),
            )
        raise ValueError(
            "Language could not be inferred from the file extension. Please provide a valid file. Received: %s",
            self.filename.suffix or self.filename.name,
        )

    @classmethod
    def from_file(cls, file_path: Path) -> FileThing[SgRoot]:
        """Create a FileThing from a file."""
        from codeweaver.core.language import SemanticSearchLanguage

        content = file_path.read_text()
        language = SemanticSearchLanguage.from_extension(
            FileExt(cast(LiteralStringT, file_path.suffix or file_path.name))
        )
        return cls.from_sg_root(
            AstGrepRoot(content, cast(SemanticSearchLanguage, language).variable)
        )


class AstThing[SgNode: (AstGrepNode)](BasedModel):
    """Wrapper for `SgNode` to make it serializable and give it extra functionality.

    AstThing represents a node in the AST, which can be a Token (leaf node) or a CompositeThing (non-leaf node). It provides methods for traversing the AST, searching for nodes, and classifying nodes semantically. Each AstThing is associated with a specific programming language, which helps in semantic classification and importance scoring.

    Other notable improvements over raw `SgNode`:
    - Serialization support via Pydantic
    - Unique identifiers for nodes (`thing_id` and `parent_thing_id`)
    - Cached properties for potentially expensive operations (like `text`, `kind`, `range`, etc.)
    - Integration with CodeWeaver's semantic classification and scoring system
        - Each Thing can determine its semantic classification and importance score, providing richer context for search and analysis.
        - Allows prioritization of Things based on their semantic importance, the goal of the search, and the task at hand.
    - Clearer terminology aligned with CodeWeaver's vocabulary (e.g., Thing, Token, CompositeThing)
    - Stronger typing and generics for better developer experience
    - Each AstThing holds references to its "pure" grammar Thing, which provides information about *what it can be* in the AST, not just what we see in this particular instance.
    """

    model_config = BasedModel.model_config | ConfigDict(arbitrary_types_allowed=True)

    _node: Annotated[AstGrepNode, Field(description="""The underlying SgNode""", exclude=True)]

    language: Annotated[
        SemanticSearchLanguage,
        Field(
            description="""The language of the node""",
            default_factory=lambda data: SemanticSearchLanguage.from_extension(
                data["_node"].get_root().filename().suffix
                or data["_node"].get_root().filename().name
            ),
        ),
    ]

    thing_id: Annotated[UUID7, Field(description="""The unique ID of the node""")] = uuid7()

    parent_thing_id: Annotated[UUID7 | None, Field(description="""The ID of the parent node""")] = (
        None
    )

    def _telemetry_keys(self) -> dict[FilteredKey, AnonymityConversion]:
        from codeweaver.core.types.aliases import FilteredKey
        from codeweaver.core.types.enum import AnonymityConversion

        return {
            FilteredKey("_node"): AnonymityConversion.HASH,
            FilteredKey("text"): AnonymityConversion.TEXT_COUNT,
        }

    def __init__(
        self,
        node: AstGrepNode,
        language: SemanticSearchLanguage | None = None,
        thing_id: UUID7 | None = None,
        parent_thing_id: UUID7 | None = None,
    ) -> None:
        """Initialize the AstThing and set the parent_thing_id if applicable."""
        # Resolve thing_id first
        if thing_id is None:
            thing_id = uuid7()
        self.thing_id = thing_id
        self.language = cast(
            SemanticSearchLanguage,
            language
            or SemanticSearchLanguage.from_extension(
                FileExt(cast(LiteralStringT, Path(node.get_root().filename()).suffix))
            ),
        )
        self._node = node
        self.parent_thing_id = parent_thing_id or self.parent.thing_id if self.parent else None

        # Resolve language if needed
        if language is None:
            with contextlib.suppress(Exception):
                language = SemanticSearchLanguage.from_extension(
                    FileExt(cast(LiteralStringT, Path(node.get_root().filename()).suffix))
                )
        if language is None:
            raise ValueError(
                "Language must be provided or inferable from the node's root filename."
            )

    @classmethod
    def from_sg_node(
        cls,
        sg_node: AstGrepNode,
        language: SemanticSearchLanguage,
        *,
        thing_id: UUID7 | None = None,
        parent_thing_id: UUID7 | None = None,
    ) -> AstThing[SgNode]:
        """Create an AstThing from an ast-grep `SgNode`."""
        return cls.model_construct(
            _node=sg_node,
            language=language,
            thing_id=thing_id or uuid7(),
            parent_thing_id=parent_thing_id,
        )

    # ================================================
    # *      Identity and Metadata Properties       *
    # ================================================

    @computed_field
    @property
    def thing(self) -> CompositeThing | Token | Category | None:
        """Get the grammar Thing that this node represents."""
        thing_name: ThingName = self.name  # type: ignore
        # Handle ERROR nodes from ast-grep (syntax errors)
        if thing_name == ThingName("ERROR"):
            return None
        registry = registry_module  # Access the module, don't call it
        if thing := registry.get_registry().get_thing_by_name(thing_name, language=self.language):
            return cast(CompositeThing | Token | Category, thing)
        # Return None for unknown things rather than raising
        return None

    @computed_field
    @property
    def is_file_thing(self) -> bool:
        """Check if the node is the root file thing."""
        if isinstance(self.thing, Category):
            return False
        if self.thing and self.thing.is_token:
            return False
        return (isinstance(self.thing, CompositeThing) and self.thing.is_file) or (
            self.thing_id == self.parent_thing_id
        )

    @computed_field
    @property
    def classification(self) -> ThingClass | None:
        """Get the classification of this node."""
        thing = self.thing
        if thing is None or isinstance(thing, Category):
            return None
        return thing.classification

    @cached_property
    def importance(self) -> ImportanceScores | None:
        """Get the base importance scores of the node."""
        return self.classification.importance_scores if self.classification else None

    @computed_field
    @property
    def symbol(self) -> str:
        """Get a symbolic representation of the node."""
        # Return the node's text as a simple symbol representation
        return self.text

    @computed_field
    @cached_property
    def title(self) -> str:
        """Get a human-readable title for the node."""
        name = humanize(self.name)
        language = humanize(str(self.language))
        classification = (
            humanize(self.classification.name.as_title) if self.classification else "Not classified"
        )
        text_snippet = humanize(self.text.strip().splitlines()[0])
        if len(text_snippet) > 25:
            text_snippet = f"{text_snippet[:22]}..."
        return f"{language}-{name}-{classification}: '{text_snippet}'"

    @computed_field
    @property
    def range(self) -> Range:
        """Get the range of the node."""
        node_range: SgRange = self._node.range()
        return Range.from_sg_range(node_range)

    @computed_field
    @cached_property
    def is_token(self) -> bool:
        """Check if the node is a token(leaf)."""
        return self._node.is_leaf()

    @computed_field
    @property
    def is_composite(self) -> bool:
        """Check if the node is a composite (non-leaf)."""
        return not self.is_token

    @computed_field
    @cached_property
    def has_explicit_rule(self) -> bool:
        """Check if the node is named."""
        return self._node.is_named()

    @computed_field
    @cached_property
    def is_explicit_rule_token(self) -> bool:
        """Check if the node is a token defined with a specific rule (a named leaf)."""
        return self._node.is_named_leaf()

    @computed_field
    @cached_property
    def name(self) -> ThingNameT:
        """Get the name (kind - the name in the grammar) of the node."""
        return ThingName(cast(LiteralString, self._node.kind()))

    @computed_field
    @cached_property
    def primary_category(self) -> str | None:
        """Get the primary category of the node, if any."""
        if not self.thing or isinstance(self.thing, Category):
            return None
        return self.thing.primary_category.name if self.thing.primary_category else None

    @computed_field
    @cached_property
    def text(self) -> str:
        """Get the text of the node."""
        return self._node.text()

    @computed_field
    @property
    def _root(self) -> FileThing[AstGrepRoot]:
        """Get the root of the node."""
        return cast(FileThing[AstGrepRoot], FileThing.from_sg_root(self._node.get_root()))

    # Semantic classification and scoring methods

    @computed_field
    @property
    def base_score(self) -> ImportanceScores:
        """Calculate the importance score for this node."""
        from codeweaver.semantic.scoring import SemanticScorer

        scorer = SemanticScorer()
        return scorer.calculate_importance_score(self)  # pyright: ignore[reportArgumentType]

    def importance_for_task(self, task: AgentTask) -> ImportanceScores:
        """Calculate the importance score for this node for a specific task."""
        return self.base_score.weighted_score(task.profile)

    def importance_for_context(
        self,
        context: Literal[
            "discovery", "comprehension", "modification", "debugging", "documentation"
        ],
        task: AgentTask,
    ) -> PositiveFloat:
        """Calculate the importance score for this node for a specific context."""
        return self.importance_for_task(task).as_dict()[context]

    def __getitem__(self, meta_var: str) -> AstThing[SgNode]:
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

    def get_match(self, meta_var: str) -> AstThing[SgNode] | None:
        """Get the match for the given meta variable."""
        return (
            type(self).from_sg_node(cast(SgNode, self._node.get_match(meta_var)), self.language)
            if self._node.get_match(meta_var)
            else None
        )

    def get_multiple_matches(self, meta_var: str) -> list[AstThing[SgNode]]:
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
    def find(self, config: None, **rule: Unpack[Rule]) -> AstThing[SgNode]: ...
    @overload
    def find(self, config: Config) -> AstThing[SgNode]: ...
    def find(self, config: Config | None = None, **rule: Any) -> AstThing[SgNode]:
        """Find a node using a config."""
        if config:
            return type(self).from_sg_node(cast(SgNode, self._node.find(config)), self.language)
        return type(self).from_sg_node(cast(SgNode, self._node.find(**rule)), self.language)

    @overload
    def find_all(self, config: None, **rule: Unpack[Rule]) -> tuple[AstThing[SgNode], ...]: ...
    @overload
    def find_all(self, config: Config) -> tuple[AstThing[SgNode], ...]: ...
    def find_all(self, config: Config | None = None, **rule: Any) -> tuple[AstThing[SgNode], ...]:
        """Find all nodes using a config."""
        if config:
            return tuple(
                type(self).from_sg_node(node, self.language) for node in self._node.find_all(config)
            )
        return tuple(
            type(self).from_sg_node(node, self.language) for node in self._node.find_all(**rule)
        )

    # traversal API
    def get_root(self) -> FileThing[AstGrepRoot]:
        """Get the root of the node. Alias for `get_file`."""
        return self._root

    def get_file(self) -> FileThing[AstGrepRoot]:
        """Get the root of the node."""
        return self._root

    def child(self, nth: NonNegativeInt) -> AstThing[SgNode] | None:
        """Get the nth child of the node."""
        return (
            tuple(self.positional_connections)[nth]
            if nth < len(tuple(self.positional_connections))
            else None
        )

    @computed_field
    @property
    def _ancestor_list(self) -> tuple[AstThing[SgNode], ...]:
        """Get the ancestors of the node."""
        return tuple(
            type(self).from_sg_node(ancestor, self.language)
            for ancestor in self._node.ancestors()
            if self._node.ancestors() and ancestor
        )

    def ancestors(self) -> Iterator[AstThing[SgNode]]:
        """Get the ancestors of the node."""
        yield from self._ancestor_list

    @computed_field
    @cached_property
    def positional_connections(self) -> Iterator[AstThing[SgNode]]:
        """Get the things positionally connected to this thing (its children)."""
        yield from (
            type(self).from_sg_node(child, self.language) for child in self._node.children()
        )

    @computed_field
    @cached_property
    def parent(self) -> AstThing[SgNode] | None:
        """Get the parent of the thing."""
        parent_node = self._node.parent()
        return type(self).from_sg_node(parent_node, self.language) if parent_node else None

    def next(self) -> AstThing[SgNode] | None:
        """Get the next sibling of the thing."""
        if not self._node.next():
            return None
        return type(self).from_sg_node(cast(SgNode, self._node.next()), self.language)

    def next_all(self) -> Iterator[AstThing[SgNode]]:
        """Get all next siblings of the node."""
        yield from (type(self).from_sg_node(n, self.language) for n in self._node.next_all())

    def prev(self) -> AstThing[SgNode] | None:
        """Get the previous sibling of the node."""
        if not self._node.prev():
            return None
        return type(self).from_sg_node(cast(SgNode, self._node.prev()), self.language)

    def prev_all(self) -> Iterator[AstThing[SgNode]]:
        """Get all previous siblings of the node."""
        yield from (type(self).from_sg_node(p, self.language) for p in self._node.prev_all())

    def replace(self, _new_text: str) -> str:
        """Replace the text of the node with new_text."""
        raise NotImplementedError("Edit functionality is not implemented yet.")

    def commit_edits(self, _edits: list[str]) -> str:
        """Commit a list of edits to the source code."""
        raise NotImplementedError("Edit functionality is not implemented yet.")

    def serialize_as_child(self) -> str:
        """Serialize the AstThing as a child for output."""
        return f"{self.title}: {self.get_file().filename} [{self.range.start.line}:{self.range.start.column}-{self.range.end.line}:{self.range.end.column}]"

    def serialize_for_cli(self) -> dict[str, Any]:
        """Serialize the AstThing for CLI output."""
        as_python = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={
                "_node",
                "_registry",
                "has_explicit_rule",
                "is_explicit_rule_token",
                "range",
                "importance",
                "thing_id",
                "parent_thing_id",
                "language",
                "text",
            },
        )
        for k, v in as_python.items():
            if isinstance(v, Sequence | Iterator) and not isinstance(v, str):
                as_python[k] = [
                    item.serialize_as_child()  # type: ignore
                    if hasattr(item, "serialize_as_child")  # type: ignore
                    else item.serialize_for_cli()  # type: ignore
                    if hasattr(item, "serialize_for_cli")  # type: ignore
                    else item
                    for item in v  # type: ignore
                ]
        return {
            k: v.serialize_as_child()
            if hasattr(v, "serialize_as_child")
            else v.serialize_for_cli()
            if hasattr(v, "serialize_for_cli")
            else v
            for k, v in as_python.items()
        }


__all__ = (
    "AstThing",
    "Config",
    "CustomLang",
    "FileThing",
    "NthChild",
    "Pattern",
    "Pos",
    "PosRule",
    "Position",
    "Range",
    "RangeRule",
    "Relation",
    "Rule",
    "RuleWithoutNot",
)

# Rebuild models to resolve forward references
with contextlib.suppress(Exception):
    from codeweaver.core.chunks import CodeChunk
    from codeweaver.core.metadata import SemanticMetadata

    for model in (FileThing, AstThing, SemanticMetadata, CodeChunk):
        if not model.model_rebuild():
            logger.warning("Model %s failed to rebuild in ast_grep.py", model.__name__)
        else:
            logger.debug("Model %s rebuilt successfully in ast_grep.py", model.__name__)

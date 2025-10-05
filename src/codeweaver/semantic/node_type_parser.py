# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Parser for tree-sitter node-types.json files to extract node type information."""

from __future__ import annotations

import logging

from collections import defaultdict
from collections.abc import KeysView, Mapping, Sequence
from functools import cached_property
from pathlib import Path
from textwrap import dedent
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Any, Literal, NamedTuple, TypedDict, cast

from pydantic import DirectoryPath, Discriminator, Field, FilePath, PrivateAttr, Tag, computed_field

from codeweaver._common import AbstractNodeName, BasedModel, LiteralStringT, RootedRoot
from codeweaver.language import SemanticSearchLanguage

if TYPE_CHECKING:
    from codeweaver.semantic.grammar_types import FieldInfo, NodeSemanticInfo


logger = logging.getLogger(__name__)

type EmptyList = list[
    None
]  # technically not true -- it has nothing, not None, but... as good as we can do

type NodeNameT = LiteralStringT

# ===========================================================================
# *                  Node Field Type Definitions                  *
# ===========================================================================
# Could we just use one TypedDict with optional fields? Yes.
# But this way, we get better validation and documentation.
# Also, it can help us narrow down the language if we don't know it.

# ================================================
# *          Base Types for Node Type Info
# ================================================


FIELD_KEYS = ("children", "extra", "fields", "root", "subtypes", "named", "type_name")


class SimpleNodeField(NamedTuple):
    """A simple field in a node type entry."""

    name: NodeNameT
    named: bool

    @property
    def is_named(self) -> bool:
        """Check if the field is named."""
        return self.named


class NodeField(NamedTuple):
    """A field in a node type entry."""

    named: bool
    root: bool
    extra: bool
    subtypes: Annotated[tuple[SimpleNodeField, ...] | None, Field(default_factory=tuple)]
    name: Annotated[
        NodeNameT | AbstractNodeName,
        Field(
            description="""The name of the node field.""",
            default_factory=lambda data: AbstractNodeName if data.get("subtypes") else str,
        ),
    ]
    fields: Annotated[
        tuple[tuple[SimpleNodeField, ...] | None],
        Field(default_factory=lambda data: None if data.get("subtypes") else tuple),
    ]
    children: Annotated[
        SimpleNodeField | None,
        Field(default_factory=lambda data: tuple if data.get("fields") else None),
    ]

    @property
    def has_children(self) -> bool:
        """Check if the field has children."""
        return self.children is not None

    @property
    def is_abstract(self) -> bool:
        """Check if the field is abstract (has subtypes)."""
        return self.subtypes is not None

    @property
    def is_extra(self) -> bool:
        """Check if the field is extra. (...aren't we all?)."""
        return self.extra

    @property
    def is_root(self) -> bool:
        """Check if the field is a root node."""
        return self.root


class ChildInfo(TypedDict):
    """`ChildInfo` is used for `children` and `fields` entries in raw node type information from JSON.

    The tree-sitter documentation refers to these as `child types`. They describe the types of nodes
    that can be children of a given node, either as direct children (`children`) or as a type of an abstract field (`fields`).
    """

    multiple: Annotated[
        bool,
        Field(
            description="""If true, there can be multiple children associated with the parent node."""
        ),
    ]
    required: Annotated[
        bool,
        Field(
            description="""If true, at least one of the node types in `types` must accompany the parent node."""
        ),
    ]
    types: list[SimpleField] | EmptyList


class FieldsField(TypedDict):
    """The `fields` entry in raw node type information from JSON with fields."""

    fields: Annotated[
        dict[
            Annotated[
                NodeNameT,
                Field(
                    description="""A field is a way to group related child nodes under a parent node, or represent a node with a unique name to simplify searches (or both). The grammar author explicitly defines fields in the grammar. Usually they represent a structural or semantic relationship between the parent node and its children, and they can help you find nodes more easily. (Basically, the grammar author is giving you a hint about how to interpret the syntax tree.)

                    Fields are different from `children` because `children` are just a list of child nodes, which are positionally related (so you they have an index, but no name you can use to access them directly in the syntax tree). Fields, on the other hand, are named and can group multiple child nodes together under a single name. This makes it easier to find and work with specific parts of the syntax tree.
                    """
                ),
            ],
            ChildInfo,
        ],
        Field(
            description="""For a field, the `ChildInfo` describes the types of nodes that can be associated with that field."""
        ),
    ]


class ChildrenFieldMixin(FieldsField):
    """Mixin for `children` entry in raw node type information from JSON with children.

    You will only find `children` in combination with the `fields` field in a node type entry. Note that `ChildrenFieldMixin` extends `FieldsField`, so any node type with `children` will also have `fields`.
    """

    children: Annotated[
        ChildInfo,
        Field(
            description="Information about the child nodes associated with this field. The `ChildInfo` describes the types of nodes that can be children of the parent node, but without a specific field name."
        ),
    ]


class SimpleField(TypedDict):
    """`SimpleField` is the base entry for raw node type information from JSON.

    *Every* node type entry has these fields, and the pattern is often also nested in `subtypes`, `fields`, and `children` entries.
    """

    type_name: Annotated[
        NodeNameT, Field(validation_alias="type", description="The node type name")
    ]
    named: Annotated[
        bool,
        Field(
            description=dedent("""
            `named` indicates that the node has a defined *rule* name in the language's grammar. Most nodes that represent significant language constructs are named, while nodes representing punctuation or operators are often unnamed.

            This field can help filter out syntactic information. Generally, if your search is focused on code understanding or relationships between constructs, you can ignore unnamed nodes (i.e., those with `named: false`). For editing, formatting, code highlighting, and debugging tasks, the unnamed nodes may be relevant.""")
        ),
    ]


class SubtypeField(TypedDict):
    """When the `subtypes` field is present, `type_name` takes on a slightly different meaning, which is why we have a separate TypedDict for it.

    `subtypes` is a list of node type entries that are considered subtypes of the parent node type. The parent node type itself is an abstract type that does not appear directly in the syntax tree, but its subtypes do. This is useful for representing polymorphic relationships in the syntax tree, where a parent node type can have multiple concrete implementations (subtypes) that share common characteristics. For example, a parent node type `expression` might have subtypes like `binary_expression`, `unary_expression`, and `literal`, each representing different kinds of expressions in the language.

    In practical terms, the `subtypes` field is generated when the grammar defines a `supertypes list`, which is a way to group related node types under a common abstract type. You can use the `subtypes` parent type to search for all its subtypes in one go, which is particularly useful for tasks like code analysis or transformation where you want to operate on a broad category of nodes without specifying each subtype individually.
    """

    type_name: Annotated[
        AbstractNodeName,
        Field(
            validation_alias="type",
            description="The node type name",
            default_factory=AbstractNodeName,
        ),
    ]
    named: Annotated[
        bool,
        Field(
            description=dedent("""
            `named` indicates that the node has a defined *rule* name in the language's grammar. Most nodes that represent significant language constructs are named, while nodes representing punctuation or operators are often unnamed.

            This field can help filter out syntactic information. Generally, if your search is focused on code understanding or relationships between constructs, you can ignore unnamed nodes (i.e., those with `named: false`). For editing, formatting, code highlighting, and debugging tasks, the unnamed nodes may be relevant.""")
        ),
    ]
    subtypes: Annotated[list[SimpleField], Field()]


class ExtraField(SimpleField):
    """Fields entry with `extra`."""

    extra: Annotated[
        bool,
        Field(
            description="""`extra` indicates that the node in `type_name` and its children, if any, have no structural requirements or constraints -- meaning they can appear *anywhere* in the syntax tree. Most nodes with `extra` are syntactic elements like comments, whitespace, or punctuation that can be interspersed throughout the code without affecting its structure or meaning."""
        ),
    ]


class ExtraFieldsField(ExtraField, FieldsField):
    """Fields entry with `extra` and `fields`."""


class ExtraChildrenField(ExtraField, ChildrenFieldMixin):
    """Fields entry with `extra`, `fields`, and `children`."""


class SimpleFieldFields(SimpleField, FieldsField):
    """Fields entry with `fields`."""


class SimpleFieldChildren(SimpleField, ChildrenFieldMixin):
    """Fields entry with `fields` and `children`."""


class RootField(SimpleField, ChildrenFieldMixin):
    """Fields entry with `root`, `fields`, and `children`. `root` only appears with `fields` and `children` and is always True."""

    root: Annotated[
        Literal[True],
        Field(
            description="""Indicates that the node in `type_name` is a root node. Root nodes are top-level constructs in the syntax tree, such as entire files or modules. They serve as entry points for parsing and analyzing code."""
        ),
    ]


type NodeTypeInfo = (
    Annotated[SimpleField, Tag("simple")]
    | Annotated[SimpleFieldFields, Tag("fields")]
    | Annotated[SimpleFieldChildren, Tag("children")]
    | Annotated[SubtypeField, Tag("subtypes")]
    | Annotated[ExtraField, Tag("extra")]
    | Annotated[ExtraFieldsField, Tag("extra_fields")]
    | Annotated[ExtraChildrenField, Tag("extra_children")]
    | Annotated[RootField, Tag("root")]
)

type WithFieldsT = (
    Annotated[SimpleFieldFields, Tag("fields")]
    | Annotated[ExtraFieldsField, Tag("extra_fields")]
    | Annotated[SimpleFieldChildren, Tag("children")]
    | Annotated[ExtraChildrenField, Tag("extra_children")]
    | Annotated[RootField, Tag("root")]
)
type WithChildrenT = (
    Annotated[SimpleFieldChildren, Tag("children")]
    | Annotated[ExtraChildrenField, Tag("extra_children")]
    | Annotated[RootField, Tag("root")]
)

type LanguageNodeType = dict[LiteralStringT, NodeTypeInfo]

type NodeInfoKey = Literal["children", "extra", "fields", "root", "subtypes", "named", "type"]


def get_discriminator_value(
    data: Any,
) -> Literal[
    "simple", "fields", "children", "subtypes", "extra", "extra_fields", "extra_children", "root"
]:
    """Get the discriminator value for NodeTypeInfo based on the presence of keys."""
    keys: tuple[NodeInfoKey, ...] = tuple(
        sorted(cast(KeysView[NodeInfoKey], data.keys()))
        if isinstance(data, dict)
        else tuple(
            sorted(
                t
                for t in ("type", "named", "subtypes", "extra", "fields", "children", "root")
                if t in data
            )
        )
    )
    match keys:
        case ("named", "type"):
            return "simple"
        case ("fields", "named", "type"):
            return "fields"
        case ("children", "fields", "named", "type"):
            return "children"
        case ("named", "subtypes", "type"):
            return "subtypes"
        case ("extra", "named", "type"):
            return "extra"
        case ("extra", "fields", "named", "type"):
            return "extra_fields"
        case ("children", "extra", "fields", "named", "type"):
            return "extra_children"
        case ("children", "fields", "named", "root", "type"):
            return "root"
        case _:
            raise ValueError("Cannot determine discriminator value for NodeTypeInfo")


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


def lang_from_named_node_count(nodes: list[NodeTypeInfo]) -> SemanticSearchLanguage:
    """Get the language from the count of named nodes, if possible."""
    return NAMED_NODE_COUNTS[sum(1 for node in nodes if node["named"] for node in nodes)]


class RootNodeTypes(RootedRoot[tuple[NodeTypeInfo, ...]]):
    """Root model for list of node type information."""

    root: list[  # type: ignore # yes, we are overriding the name 'root' from `RootedRoot`
        Annotated[
            Annotated[SimpleField, Tag("simple")]
            | Annotated[SimpleFieldFields, Tag("fields")]
            | Annotated[SimpleFieldChildren, Tag("children")]
            | Annotated[SubtypeField, Tag("subtypes")]
            | Annotated[ExtraField, Tag("extra")]
            | Annotated[ExtraFieldsField, Tag("extra_fields")]
            | Annotated[ExtraChildrenField, Tag("extra_children")]
            | Annotated[RootField, Tag("root")],
            Field(description="List of node type information"),
            Discriminator(get_discriminator_value),
        ]
    ]
    _source_file: Annotated[FilePath | None, PrivateAttr(init=False)] = None

    @computed_field
    @cached_property
    def language(self) -> SemanticSearchLanguage:
        """Get the language for the root node types."""
        if self._source_file and "-node-types" in self._source_file.stem:
            return SemanticSearchLanguage.from_string(
                self._source_file.stem.replace("-node-types", "")
            )
        if self._source_file and (
            lang := next(
                (
                    semlang
                    for semlang in SemanticSearchLanguage
                    if any(a for a in semlang.aka if cast(str, a) in self._source_file.stem)
                ),
                None,
            )
        ):
            return lang
        try:
            lang = lang_from_named_node_count(self.root)
        except KeyError as e:
            logger.exception(
                "Could not determine language from node counts. Most likely because there are no nodes. Node count: %d",
                len(self.root),
                extra={"nodes": self.root},
            )
            from codeweaver.exceptions import InitializationError

            raise InitializationError(
                "Could not determine language from node counts in `RootNodeTypes`.",
                details={
                    "source_file": str(self._source_file) if self._source_file else "unknown",
                    "node_count": len(self.root),
                },
            ) from e
        else:
            return lang

    @property
    def concrete_types(self) -> frozenset[NodeNameT]:
        """Get a set of all concrete node type names in the root list."""
        return cast(
            frozenset[NodeNameT],
            frozenset(
                sorted({
                    *(t["type_name"] for t in self.named_types),
                    *(t["type_name"] for val in self.subtype_map.values() for t in val),
                })
            ),
        )

    @property
    def concrete_to_abstract(self) -> MappingProxyType[NodeNameT, tuple[AbstractNodeName, ...]]:
        """Get a mapping of concrete node types to their abstract parent types."""
        subs = self.subtype_map
        concrete_to_abstract: dict[NodeNameT, set[AbstractNodeName]] = defaultdict(set)
        for concrete_type in self.concrete_types:
            for abstract_type, subtypes in subs.items():
                if any(concrete_type == t["type_name"] for t in subtypes):
                    concrete_to_abstract[concrete_type].add(abstract_type)
        return MappingProxyType({k: tuple(sorted(v)) for k, v in concrete_to_abstract.items()})

    @property
    def flattened(self) -> list[NodeTypeInfo]:
        """Get a flattened list of all NodeTypeInfo entries."""
        return self.root.copy()

    @property
    def named_types(self) -> list[NodeTypeInfo]:
        """Get a list of all named NodeTypeInfo entries."""
        return [node for node in self if node["named"]]

    @property
    def flat_map(self) -> MappingProxyType[SemanticSearchLanguage, list[NodeTypeInfo]]:
        """Get a mapping of language to its NodeTypeInfo entries."""
        return MappingProxyType({self.language: self.flattened})

    @property
    def subtypes(self) -> frozenset[NodeNameT]:
        """Get a set of all node type names that are subtypes."""
        return frozenset({t["type_name"] for val in self.subtype_map.values() for t in val})

    @property
    def subtype_map(self) -> MappingProxyType[AbstractNodeName, list[SimpleField]]:
        """Get a mapping of all subtypes to their SimpleField."""
        subtypes: dict[AbstractNodeName, list[SimpleField]] = defaultdict(list)
        for entry in self:
            if "subtypes" in entry:
                subtypes[AbstractNodeName(entry["type_name"])].extend(entry["subtypes"])
        return MappingProxyType(subtypes)

    @property
    def abstracts(self) -> frozenset[AbstractNodeName]:
        """Get a set of all abstract node type names in the root list."""
        return frozenset({
            AbstractNodeName(entry["type_name"]) for entry in self if "subtypes" in entry
        })

    @property
    def fields(self) -> MappingProxyType[NodeNameT, ChildInfo]:
        """Get a mapping of all field names to their ChildInfo."""
        fields: dict[NodeNameT, ChildInfo] = {}
        for entry in self:
            if "fields" in entry:
                fields |= entry["fields"]
        return MappingProxyType(fields)

    @property
    def children(self) -> MappingProxyType[NodeNameT, ChildInfo]:
        """Get a mapping of all child names to their ChildInfo."""
        return MappingProxyType({
            entry["type_name"]: entry["children"] for entry in self if "children" in entry
        })

    @classmethod
    def from_node_type_file(cls, file_path: FilePath) -> RootNodeTypes:
        """Load and parse a node-types.json file.

        It normalizes nested "type" keys to "type_name" for validation, validates
        each node into NodeTypeInfo, and constructs a LanguageNodeType whose
        `node_type` is a mapping of type_name -> NodeTypeInfo instances.

        On first validation failure for a file, log the error and re-raise.
        """
        from pydantic_core import from_json

        try:
            raw_data: Any = from_json(file_path.read_bytes())
            instance = cls.model_validate(raw_data, by_alias=True)
            instance._source_file = file_path
        except Exception:
            # Handle validation errors
            logger.exception("Failed to load or validate %s", file_path)
            raise
        else:
            return instance


class NodeTypeParser(BasedModel):
    """Parser for processing multiple tree-sitter node_type files."""

    node_types_dir: Annotated[
        DirectoryPath, Field(description="""Directory containing node_type files""")
    ] = Path(__file__).parent.parent.parent.parent / "node_types"

    def parse_all_node_types(self) -> Sequence[Mapping[SemanticSearchLanguage, RootNodeTypes]]:
        """Parse all node-types.json files in the node_types directory.

        Returns:
            Dictionary mapping language names to their parsed node_types
        """
        node_types: Sequence[Mapping[SemanticSearchLanguage, RootNodeTypes]] = []

        for node_type_file in self.node_types_dir.glob("*-node-types.json"):
            try:
                nodes = RootNodeTypes.from_node_type_file(node_type_file)
                node_types.append({nodes.language: nodes})
            except Exception as e:
                # Log error but continue processing other files
                print(f"Warning: Failed to parse {node_type_file}: {e}")

        return node_types

    def flatten(self) -> MappingProxyType[SemanticSearchLanguage, list[NodeTypeInfo]]:
        """Flatten the parsed node types into a mapping of language to list of NodeTypeInfo."""
        nodes = self.parse_all_node_types()
        flattened = [v.flat_map for val in nodes for v in val.values()]
        return MappingProxyType({
            lang: types for mapping in flattened for lang, types in mapping.items()
        })

    @cached_property
    def nodes(self) -> tuple[RootNodeTypes, ...]:
        """Get all parsed node types."""
        return tuple(node for mapping in self.parse_all_node_types() for node in mapping.values())

    @staticmethod
    def _add_node_group(types: list[SimpleField]) -> set[NodeNameT]:
        """Extract node type names from a list of SimpleField entries."""
        assembled_types = {t.get("type_name", t.get("type")) for t in types}
        return {cast(NodeNameT, t) for t in assembled_types if t}

    @staticmethod
    def _get_node_types_from_info_values(info: NodeTypeInfo) -> set[NodeNameT]:  # noqa: C901
        """Extract node type names from NodeTypeInfo values."""
        all_types: set[NodeNameT] = set()
        for key, value in info.items():
            match key:
                case "type_name" | "type":
                    if "subtypes" in info:
                        all_types.add(AbstractNodeName(value))  # pyright: ignore[reportArgumentType]
                    else:
                        all_types.add(cast(NodeNameT, value))
                case "subtypes":
                    if isinstance(value, str):
                        all_types.add(AbstractNodeName(value))  # pyright: ignore[reportArgumentType]
                    else:
                        all_types |= NodeTypeParser._add_node_group(cast(list[SimpleField], value))
                case "fields":
                    all_types |= cast(set[LiteralStringT], set(cast(WithFieldsT, value).keys()))
                    for field_info in cast(WithFieldsT, value).values():
                        if types := cast(ChildInfo, field_info).get("types"):
                            all_types |= NodeTypeParser._add_node_group(
                                cast(list[SimpleField], types)
                            )
                case "children":
                    if types := cast(ChildInfo, value).get("types"):
                        all_types |= NodeTypeParser._add_node_group(cast(list[SimpleField], types))
                case _:
                    continue
        return all_types

    def get_all_node_types(self) -> set[NodeNameT]:
        """Get all unique node type names across all languages.

        Returns:
            Set of all node type names found in node_types
        """
        all_types: set[NodeNameT] = set()
        node_types = self.parse_all_node_types()

        # Iterate explicitly and extract a string type name from each node entry.
        for language_node_types in node_types:
            for language_entries in language_node_types.values():
                for entry in language_entries:
                    all_types |= self._get_node_types_from_info_values(entry)
        return all_types

    # ===========================================================================
    # Enhanced API: Grammar-Based Semantic Extraction
    # ===========================================================================

    @cached_property
    def abstract_type_map(self) -> dict[str, dict[str, AbstractTypeInfo]]:
        """Map of abstract types to their info across all languages.

        Returns:
            Dictionary structure:
            {
                "expression": {
                    "python": AbstractTypeInfo(...),
                    "javascript": AbstractTypeInfo(...),
                    ...
                },
                "statement": {...},
                ...
            }

        Example:
            >>> parser = NodeTypeParser()
            >>> expr_map = parser.abstract_type_map.get("expression", {})
            >>> python_expr = expr_map.get("python")
            >>> python_expr.is_subtype("binary_expression")
            True
        """
        from codeweaver.semantic.grammar_types import AbstractTypeInfo

        type_map: dict[str, dict[str, AbstractTypeInfo]] = defaultdict(dict)

        for language_mapping in self.parse_all_node_types():
            for language, root_nodes in language_mapping.items():
                for node_info in root_nodes:
                    # Check if this node has subtypes (is abstract)
                    if subtypes := node_info.get("subtypes"):
                        # Get abstract type name
                        abstract_name = str(node_info.get("type_name", node_info.get("type", "")))
                        # Normalize: remove leading underscore
                        normalized = abstract_name.lstrip("_")

                        # Extract subtype names
                        subtype_names = tuple(
                            str(st.get("type_name", st.get("type", "")))
                            for st in subtypes
                            if isinstance(st, dict)
                        )

                        if normalized and subtype_names:
                            type_map[normalized][language.value] = AbstractTypeInfo(
                                abstract_type=normalized,
                                language=language.value,
                                concrete_subtypes=subtype_names,
                            )

        return dict(type_map)

    @cached_property
    def field_semantic_patterns(self) -> dict[str, dict[str, int]]:
        """Map field names to their common semantic categories.

        Based on empirical analysis of grammar structures across 21 languages.
        This data is pre-computed from the grammar structure analysis.

        Returns:
            Dictionary mapping field names to category usage counts:
            {
                "name": {"type_def": 65, "callable": 32, "control_flow": 24},
                "body": {"control_flow": 52, "type_def": 27, "callable": 26},
                ...
            }

        Example:
            >>> parser = NodeTypeParser()
            >>> name_patterns = parser.field_semantic_patterns.get("name", {})
            >>> sorted(name_patterns.items(), key=lambda x: x[1], reverse=True)
            [('type_def', 65), ('callable', 32), ('control_flow', 24)]
        """
        # Pre-computed from grammar analysis (claudedocs/grammar_structure_analysis.md)
        return {
            "name": {"type_def": 65, "callable": 32, "control_flow": 24},
            "body": {"control_flow": 52, "type_def": 27, "callable": 26},
            "type": {"type_def": 57, "callable": 8, "control_flow": 6},
            "condition": {"control_flow": 60},
            "operator": {"operation": 39, "boundary": 2, "type_def": 1},
            "right": {"operation": 30, "control_flow": 4, "type_def": 2},
            "parameters": {"callable": 34, "type_def": 3},
            "left": {"operation": 30, "control_flow": 3, "type_def": 2},
            "type_parameters": {"type_def": 18, "callable": 10},
            "alternative": {"control_flow": 26},
            "value": {"control_flow": 13, "type_def": 9, "callable": 2},
            "arguments": {"operation": 10, "callable": 5, "type_def": 2},
            "return_type": {"callable": 16, "type_def": 1},
            "consequence": {"control_flow": 14},
            "declarator": {"callable": 7, "type_def": 5, "control_flow": 1},
            "type_arguments": {"type_def": 6, "callable": 3, "operation": 1},
            "initializer": {"control_flow": 8, "type_def": 1},
            "function": {"operation": 6, "callable": 3},
            "argument": {"operation": 9},
            "result": {"callable": 6, "type_def": 2, "operation": 1},
            "pattern": {"pattern_match": 20, "control_flow": 10},
            "patterns": {"pattern_match": 15, "control_flow": 5},
        }

    def get_node_semantic_info(
        self,
        node_type: str,
        language: SemanticSearchLanguage | str,
    ) -> NodeSemanticInfo | None:
        """Get comprehensive semantic information for a node type.

        This is the primary method for grammar-based classification, extracting
        all structural and semantic information available from the grammar.

        Args:
            node_type: The node type name (e.g., "function_definition")
            language: The programming language

        Returns:
            NodeSemanticInfo with all extracted semantic data, or None if not found

        Example:
            >>> parser = NodeTypeParser()
            >>> info = parser.get_node_semantic_info("function_definition", "python")
            >>> info.has_fields
            True
            >>> "parameters" in info.field_map
            True
            >>> info.infer_semantic_category()
            'callable'
        """
        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)

        # Find node info in parsed data
        node_info = self._find_node_info(node_type, language)
        if not node_info:
            return None

        # Extract semantic information
        return self._extract_semantic_info(node_info, language.value)

    def _find_node_info(
        self,
        node_type: str,
        language: SemanticSearchLanguage,
    ) -> NodeTypeInfo | None:
        """Find node info for a specific type in a language.

        Args:
            node_type: Node type name to find
            language: Programming language

        Returns:
            NodeTypeInfo dict if found, None otherwise
        """
        for language_mapping in self.parse_all_node_types():
            if language not in language_mapping:
                continue

            root_nodes = language_mapping[language]
            for node_info in root_nodes:
                type_name = node_info.get("type_name", node_info.get("type"))
                if type_name == node_type:
                    return node_info

        return None

    def _extract_semantic_info(
        self,
        node_info: NodeTypeInfo,
        language: str,
    ) -> NodeSemanticInfo:
        """Extract semantic information from node type info.

        Args:
            node_info: Raw node type info from JSON
            language: Programming language name

        Returns:
            NodeSemanticInfo with all extracted data
        """
        from codeweaver.semantic.grammar_types import NodeSemanticInfo

        # Extract fields
        fields = self._extract_fields(node_info)

        # Extract children constraints
        children = self._extract_children_types(node_info)

        # Check if abstract (has subtypes)
        subtypes_data = node_info.get("subtypes", [])
        is_abstract = bool(subtypes_data)
        subtypes = tuple(
            str(st.get("type_name", st.get("type", "")))
            for st in subtypes_data
            if isinstance(st, dict)
        ) if is_abstract else ()

        # Find supertype if this is a concrete type
        node_type_name = str(node_info.get("type_name", node_info.get("type", "")))
        supertype = self._find_supertype(node_type_name, language)

        return NodeSemanticInfo(
            node_type=node_type_name,
            language=language,
            is_named=node_info.get("named", False),
            is_abstract=is_abstract,
            is_extra=node_info.get("extra", False),
            is_root=node_info.get("root", False),
            abstract_category=supertype,
            concrete_subtypes=subtypes,
            fields=fields,
            children_types=children,
        )

    def _extract_fields(self, node_info: NodeTypeInfo) -> tuple[FieldInfo, ...]:
        """Extract field information from node type info.

        Args:
            node_info: Raw node type info from JSON

        Returns:
            Tuple of FieldInfo objects
        """
        from codeweaver.semantic.grammar_types import FieldInfo

        fields_data = node_info.get("fields")
        if not isinstance(fields_data, dict):
            return ()

        fields: list[FieldInfo] = []
        for field_name, field_data in fields_data.items():
            if not isinstance(field_data, dict):
                continue

            types_data = field_data.get("types", [])
            types = tuple(
                str(t.get("type_name", t.get("type", "")))
                for t in types_data
                if isinstance(t, dict)
            )

            fields.append(FieldInfo(
                name=str(field_name),
                required=field_data.get("required", False),
                multiple=field_data.get("multiple", False),
                types=types,
            ))

        return tuple(fields)

    def _extract_children_types(self, node_info: NodeTypeInfo) -> tuple[str, ...]:
        """Extract allowed children types from node type info.

        Args:
            node_info: Raw node type info from JSON

        Returns:
            Tuple of allowed child type names
        """
        children_data = node_info.get("children")
        if not isinstance(children_data, dict):
            return ()

        types_data = children_data.get("types", [])
        return tuple(
            str(t.get("type_name", t.get("type", "")))
            for t in types_data
            if isinstance(t, dict)
        )

    def _find_supertype(self, node_type: str, language: str) -> str | None:
        """Find supertype (abstract category) for a concrete node type.

        Args:
            node_type: Concrete node type name
            language: Programming language name

        Returns:
            Abstract type name if found, None otherwise
        """
        for abstract_name, lang_map in self.abstract_type_map.items():
            if language in lang_map:
                type_info = lang_map[language]
                if type_info.is_subtype(node_type):
                    return abstract_name
        return None

    def get_supertype_hierarchy(
        self,
        node_type: str,
        language: SemanticSearchLanguage | str,
    ) -> list[str]:
        """Get hierarchy of supertypes for a node type.

        Walks up the abstract type hierarchy from most specific to most general.

        Args:
            node_type: Node type name
            language: Programming language

        Returns:
            List of supertypes from most specific to most general.
            E.g., ["binary_expression", "expression", "primary_expression"]

        Example:
            >>> parser = NodeTypeParser()
            >>> parser.get_supertype_hierarchy("binary_expression", "python")
            ['expression']
        """
        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)

        hierarchy = []
        current = node_type

        # Walk up the hierarchy
        max_depth = 10  # Prevent infinite loops
        for _ in range(max_depth):
            supertype = self._find_supertype(current, language.value)
            if not supertype:
                break

            hierarchy.append(supertype)
            current = supertype

        return hierarchy

    def find_common_patterns(self) -> dict[NodeNameT, list[SemanticSearchLanguage]]:
        """Find common node type patterns across languages.

        Returns:
            Dictionary mapping patterns to languages that have them
        """
        node_types = self.parse_all_node_types()
        pattern_languages: dict[NodeNameT, list[SemanticSearchLanguage]] = {}

        # Build mapping keyed by the node type name (string), collecting all node types per language
        for language_node_types in node_types:
            for language_name, entries in language_node_types.items():
                # Collect all unique node types for this language
                language_node_type_names: set[str] = set()
                for entry in entries:
                    if type_name := entry.get("type_name", entry.get("type")):
                        language_node_type_names.add(str(type_name))

                # Add this language to the pattern mapping for each node type it has
                for node_type_name in language_node_type_names:
                    if node_type_name not in pattern_languages:
                        pattern_languages[cast(NodeNameT, node_type_name)] = []
                    pattern_languages[cast(NodeNameT, node_type_name)].append(language_name)

        # Sort by frequency (most common patterns first)
        return dict(sorted(pattern_languages.items(), key=lambda x: len(x[1]), reverse=True))

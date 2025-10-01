# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Parser for tree-sitter node-types.json files to extract node type information."""

from __future__ import annotations

import logging

from collections.abc import KeysView, Mapping, Sequence
from pathlib import Path
from textwrap import dedent
from typing import Annotated, Any, Literal, NewType, TypedDict, cast

from pydantic import DirectoryPath, Discriminator, Field, FilePath, PrivateAttr, Tag, computed_field

from codeweaver._common import BasedModel, LiteralStringT, RootedRoot
from codeweaver._utils import lazy_importer
from codeweaver.language import SemanticSearchLanguage


logger = logging.getLogger(__name__)

type EmptyList = list[
    None
]  # technically not true -- it has nothing, not None, but... as good as we can do

type NodeNameT = LiteralStringT

AbstractNodeName = NewType("AbstractNodeName", LiteralStringT)


# ===========================================================================
# *                  Node Field Type Definitions                  *
# ===========================================================================
# Could we just use one TypedDict with optional fields? Yes.
# But this way, we get better validation and documentation.
# Also, it can help us narrow down the language if we don't know it.

# ================================================
# *          Base Types for Node Type Info
# ================================================


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
    @property
    def language(self) -> SemanticSearchLanguage | None:
        """Get the language if there's exactly one in the root mapping."""
        if self._source_file:
            return SemanticSearchLanguage.from_string(
                self._source_file.stem.replace("-node-types", "")
            )
        if self.root:
            deduction = lazy_importer("codeweaver.semantic._language_deduction")
            if (deduced := deduction.from_node_types_info(self.root)) and isinstance(
                deduced, SemanticSearchLanguage
            ):
                return deduced
            if deduced:
                logger.warning("Deduction was unable to determine a single language: %s", deduced)
                # TODO: We can try to reduce possibilities by what we see in the repo.
        return None

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
                node_types.append({cast(SemanticSearchLanguage, nodes.language): nodes})
            except Exception as e:
                # Log error but continue processing other files
                print(f"Warning: Failed to parse {node_type_file}: {e}")

        return node_types

    @staticmethod
    def _add_node_group(types: list[SimpleField]) -> set[NodeNameT]:
        """Extract node type names from a list of SimpleField entries."""
        assembled_types = {t.get("type_name", t.get("type")) for t in types}
        return {cast(NodeNameT, t) for t in assembled_types if t}

    @staticmethod
    def _get_node_types_from_info_values(info: NodeTypeInfo) -> set[NodeNameT]:
        """Extract node type names from NodeTypeInfo values."""
        all_types: set[NodeNameT] = set()
        for key, value in info.items():
            match key:
                case "type_name" | "type":
                    all_types.add(cast(LiteralStringT, value))
                case "subtypes":
                    if isinstance(value, str):
                        all_types.add(cast(LiteralStringT, value))
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

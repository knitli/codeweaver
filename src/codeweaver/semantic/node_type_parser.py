# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Parser for tree-sitter node-types.json files to extract node type information."""

from __future__ import annotations

import logging

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated, Any, NotRequired, Required, TypedDict

from pydantic import Field, PrivateAttr, RootModel

from codeweaver._common import BasedModel, LiteralStringT
from codeweaver.language import SemanticSearchLanguage


logger = logging.getLogger(__name__)

type EmptyList = list[
    None
]  # technically not true -- it has nothing, not None, but... as good as we can do


class EmptyDict(TypedDict, total=False):
    """An empty dictionary type."""


class FieldsTypesDict(TypedDict):
    """`types` entry in raw node type information from JSON."""

    type_name: Annotated[str, Field(serialization_alias="type")]
    named: bool


class FieldsInfoDict(TypedDict):
    """`Fields` entry in raw node type information from JSON."""

    multiple: bool
    required: bool
    types: list[FieldsTypesDict] | EmptyList


class NodeTypeInfoDict(TypedDict):
    """TypedDict for raw node type information from JSON."""

    type_name: Required[Annotated[str, Field(serialization_alias="type")]]
    named: Required[bool]
    subtypes: NotRequired[list[dict[str, Any]] | EmptyList]
    fields: NotRequired[dict[LiteralStringT, FieldsInfoDict] | EmptyDict]
    children: NotRequired[FieldsInfoDict | EmptyDict]


class NodeTypeInfo(BasedModel):
    """Information about a tree-sitter node type."""

    type_name: Annotated[str, Field(description="The node type name", serialization_alias="type")]
    named: Annotated[bool, Field(description="Whether the node is named")]
    subtypes: Annotated[
        list[FieldsTypesDict] | None,
        Field(default_factory=list, description="Subtype information if any"),
    ] = None
    fields: Annotated[
        dict[LiteralStringT, FieldsInfoDict] | EmptyDict | None,
        Field(default_factory=dict, description="Node fields if any"),
    ] = None
    children: Annotated[
        FieldsInfoDict | EmptyDict | None,
        Field(default_factory=dict, description="Node children if any"),
    ] = None


class LanguageNodeType(BasedModel):
    """Parsed node_type information for a specific language."""

    node_type: Annotated[
        dict[str, NodeTypeInfo], Field(description="Mapping of node type names to their info")
    ]


class RootNodeTypes(RootModel[dict[SemanticSearchLanguage, list[LanguageNodeType]]]):
    """Root model for list of node type information."""

    root: dict[SemanticSearchLanguage, list[LanguageNodeType]]
    _source_file: Annotated[Path | None, PrivateAttr(init=False)] = None

    @classmethod
    def from_node_type_file(cls, file_path: Path) -> RootNodeTypes:
        """Load and parse a node-types.json file.

        Args:
            file_path: Path to the node-types.json file

        Returns:
            Dictionary mapping language to list of LanguageNodeType instances
        """
        from pydantic_core import from_json

        data = from_json(file_path.read_bytes())
        language = SemanticSearchLanguage.from_string(file_path.stem.replace("-node-types", ""))
        future_self = RootNodeTypes.model_validate({
            language: [LanguageNodeType.model_validate(item) for item in data]
        })
        future_self._source_file = file_path
        return future_self


class NodeTypeParser(BasedModel):
    """Parser for processing multiple tree-sitter node_type files."""

    node_types_dir: Annotated[Path, Field(description="Directory containing node_type files")]

    def parse_all_node_types(
        self,
    ) -> Sequence[Mapping[SemanticSearchLanguage, Sequence[LanguageNodeType]]]:
        """Parse all node-types.json files in the node_types directory.

        Returns:
            Dictionary mapping language names to their parsed node_types
        """
        node_types: list[dict[SemanticSearchLanguage, list[LanguageNodeType]]] = []

        for node_type_file in self.node_types_dir.glob("*-node-types.json"):
            try:
                nodes = RootNodeTypes.from_node_type_file(node_type_file)
                node_types.append(nodes.root)
            except Exception as e:
                # Log error but continue processing other files
                print(f"Warning: Failed to parse {node_type_file}: {e}")

        return node_types

    def get_all_node_types(self) -> set[str]:
        """Get all unique node type names across all languages.

        Returns:
            Set of all node type names found in node_types
        """
        all_types: set[str] = set()
        node_types = self.parse_all_node_types()

        # Iterate explicitly and extract a string type name from each node entry.
        for language_node_types in node_types:
            for language_entries in language_node_types.values():
                for entry in language_entries:
                    for type_name in entry.node_type:
                        all_types.add(type_name)

        return all_types

    def find_common_patterns(self) -> dict[str, list[SemanticSearchLanguage]]:
        """Find common node type patterns across languages.

        Returns:
            Dictionary mapping patterns to languages that have them
        """
        node_types = self.parse_all_node_types()
        pattern_languages: dict[str, list[SemanticSearchLanguage]] = {}

        # Build mapping keyed by the node type name (string), not by the whole node object.
        for language_node_types in node_types:
            for language_name, entries in language_node_types.items():
                raw_key = None
                if entries:
                    # Use the first entry's first node type as the pattern key
                    first_entry = entries[0]
                    if first_entry.node_type:
                        raw_key = next(iter(first_entry.node_type.keys()), None)
                # Skip entries without a usable key
                if not raw_key:
                    continue

                # Ensure we have a string key for the mapping (type-checker friendly)
                serialized_key: str = raw_key

                if serialized_key not in pattern_languages:
                    pattern_languages[serialized_key] = []
                pattern_languages[serialized_key].append(language_name)

        # Sort by frequency (most common patterns first)
        return dict(sorted(pattern_languages.items(), key=lambda x: len(x[1]), reverse=True))

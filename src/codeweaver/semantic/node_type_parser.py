# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Parser for tree-sitter node-types.json files to extract node type information."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, NotRequired, Required, TypedDict

from pydantic import Field

from codeweaver._common import BasedModel, LiteralStringT
from codeweaver.language import SemanticSearchLanguage


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


class LanguageGrammar(BasedModel):
    """Parsed node_type information for a specific language."""

    language: Annotated[SemanticSearchLanguage | str, Field(description="The language identifier")]
    node_types: Annotated[
        dict[str, NodeTypeInfo], Field(description="Mapping of node type names to their info")
    ]

    @classmethod
    def from_node_type_file(cls, node_type_file: Path) -> LanguageGrammar:
        """Parse a node-types.json file into a LanguageGrammar.

        Args:
            node_type_file: Path to the node-types.json file

        Returns:
            Parsed language node_type
        """
        # Extract language from filename (e.g., "python-node-types.json" -> "python")
        language_name = node_type_file.stem.replace("-node-types", "")

        language = SemanticSearchLanguage.from_string(language_name)
        if language is None:  # type: ignore
            language = language_name  # Fallback to string if not recognized
        return cls.model_validate_json(
            f'"{language!s}": "{node_type_file.read_text()}"', by_alias=True
        )


class NodeTypeParser(BasedModel):
    """Parser for processing multiple tree-sitter node_type files."""

    node_types_dir: Annotated[Path, Field(description="Directory containing node_type files")]

    def parse_all_node_types(self) -> dict[SemanticSearchLanguage, LanguageGrammar]:
        """Parse all node-types.json files in the node_types directory.

        Returns:
            Dictionary mapping language names to their parsed node_types
        """
        node_types: dict[SemanticSearchLanguage, LanguageGrammar] = {}

        for node_type_file in self.node_types_dir.glob("*-node-types.json"):
            try:
                node_type = LanguageGrammar.from_node_type_file(node_type_file)
                language_key = (
                    node_type.language
                    if isinstance(node_type.language, SemanticSearchLanguage)
                    else SemanticSearchLanguage.from_string(str(node_type.language))
                )
                node_types[language_key] = node_type
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

        for node_type in node_types.values():
            all_types.update(node_type.node_types.keys())

        return all_types

    def find_common_patterns(self) -> dict[str, list[SemanticSearchLanguage]]:
        """Find common node type patterns across languages.

        Returns:
            Dictionary mapping patterns to languages that have them
        """
        node_types = self.parse_all_node_types()
        pattern_languages: dict[str, list[SemanticSearchLanguage]] = {}

        for language_name, node_type in node_types.items():
            for node_t in node_type.node_types:
                if node_t not in pattern_languages:
                    pattern_languages[node_t] = []
                pattern_languages[node_t].append(language_name)

        # Sort by frequency (most common patterns first)
        return dict(sorted(pattern_languages.items(), key=lambda x: len(x[1]), reverse=True))

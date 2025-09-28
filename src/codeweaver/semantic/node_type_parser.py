# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Parser for tree-sitter node-types.json files to extract node type information."""

from __future__ import annotations

import logging

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict, cast

from pydantic import Discriminator, Field, PrivateAttr, RootModel, Tag, computed_field

from codeweaver._common import BasedModel, LiteralStringT
from codeweaver._utils import lazy_importer
from codeweaver.language import SemanticSearchLanguage


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


class EmptyDict(TypedDict, total=False):
    """An empty dictionary type."""


class ChildInfo(TypedDict):
    """`Fields` entry in raw node type information from JSON."""

    multiple: bool
    required: bool
    types: list[SimpleField] | EmptyList


type FieldInfoT = dict[NodeNameT, ChildInfo]


class FieldsField(TypedDict):
    """`types` entry in raw node type information from JSON with fields."""

    fields: FieldInfoT


class ChildrenFieldMixin(FieldsField):
    """`types` entry in raw node type information from JSON with fields and children."""

    children: ChildInfo  # fields MUST be present if children is present


class SimpleField(TypedDict):
    """`types` entry in raw node type information from JSON."""

    type_name: Annotated[str, Field(serialization_alias="type", validation_alias="type")]
    named: bool


class SubtypeField(SimpleField):
    """Fields entry with `subtypes`."""

    subtypes: NodeNameT | list[SimpleField]


class ExtraField(SimpleField):
    """Fields entry with `extra`."""

    extra: bool


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

    root: Literal[True]


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


"""
Notes:

('type', 'named'): ALL LANGS

('type', 'named', 'subtypes'): ALL BUT SIX: {<SemanticSearchLanguage.CSS: 'css'>, <SemanticSearchLanguage.HTML: 'html'>, <SemanticSearchLanguage.ELIXIR: 'elixir'>, <SemanticSearchLanguage.SWIFT: 'swift'>, <SemanticSearchLanguage.YAML: 'yaml'>, <SemanticSearchLanguage.SOLIDITY: 'solidity'>}

('type', 'named', 'extra'): JUST 10: {<SemanticSearchLanguage.C_LANG: 'c'>, <SemanticSearchLanguage.PHP: 'php'>, <SemanticSearchLanguage.GO: 'go'>, <SemanticSearchLanguage.SWIFT: 'swift'>, <SemanticSearchLanguage.C_PLUS_PLUS: 'cpp'>, <SemanticSearchLanguage.PYTHON: 'python'>, <SemanticSearchLanguage.BASH: 'bash'>, <SemanticSearchLanguage.SOLIDITY: 'solidity'>, <SemanticSearchLanguage.JAVASCRIPT: 'javascript'>, <SemanticSearchLanguage.JSX: 'jsx'>}

('type', 'named', 'fields'): ALL BUT {<SemanticSearchLanguage.YAML: 'yaml'>}
('type', 'named', 'fields', 'children'): ALL BUT {<SemanticSearchLanguage.YAML: 'yaml'>}
('type', 'named', 'root', 'fields', 'children'): ALL BUT {<SemanticSearchLanguage.NIX: 'nix'>}

('type', 'named', 'extra', 'fields'): ONLY {<SemanticSearchLanguage.LUA: 'lua'>}

('type', 'named', 'extra', 'fields', 'children'): ONLY {<SemanticSearchLanguage.PHP: 'php'>}

`fields` is always empty for `CSS`, `HTML`, `YAML` (but is sometimes empty for all others)

'children' ALWAYS has 'multiple', 'required', 'types' keys when present.

`type` is always a string
`named` is always a bool
`extra` is always a bool
`root` is always a bool

if present, `subtypes` is either a string or a list of dicts with 'type' and 'named' keys -- never empty or None

`fields` is a dict of field name -> dict with 'multiple', 'required', 'types' keys -- never None, sometimes empty

if `named` is False, `fields` can be present, but not `children`, `extra`, or `root`. `fields` will be empty if present.
  this only happens for:
  - SWIFT: `?`
  - PYTHON: `is not` and `not in`
  - HASKELL: `(#`
"""
type LanguageNodeType = dict[LiteralStringT, NodeTypeInfo]

type NodeInfoKey = Literal["children", "extra", "fields", "root", "subtypes", "named", "type"]


def get_discriminator_value(data: Any) -> str:
    """Get the discriminator value for NodeTypeInfo based on the presence of keys."""
    keys: tuple[NodeInfoKey, ...] = (
        tuple(sorted(data.keys()))
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


class RootNodeTypes(RootModel[list[NodeTypeInfo]]):
    """Root model for list of node type information."""

    root: list[
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
    _source_file: Annotated[Path | None, PrivateAttr(init=False)] = None

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
    def from_node_type_file(cls, file_path: Path) -> RootNodeTypes:
        """Load and parse a node-types.json file.

        This method tolerates the two common tree-sitter node-types.json shapes:
        - A list of node dicts (common)
        - A mapping of type_name -> node dict (less common)

        It normalizes nested "type" keys to "type_name" for validation, validates
        each node into NodeTypeInfo, and constructs a LanguageNodeType whose
        `node_type` is a mapping of type_name -> NodeTypeInfo instances.

        On first validation failure for a file, write a diagnostic JSON to /tmp
        to make inspection easy without altering behavior.
        """
        from pydantic_core import from_json

        try:
            raw_data: Any = from_json(file_path.read_text(encoding="utf-8"))
            instance = cls.model_validate(raw_data)
            instance._source_file = file_path
        except Exception:
            # Handle validation errors
            logger.exception("Failed to load or validate %s", file_path)
            raise
        else:
            return instance


class NodeTypeParser(BasedModel):
    """Parser for processing multiple tree-sitter node_type files."""

    node_types_dir: Annotated[Path, Field(description="""Directory containing node_type files""")]

    def parse_all_node_types(
        self,
    ) -> Sequence[Mapping[SemanticSearchLanguage, Sequence[NodeTypeInfo]]]:
        """Parse all node-types.json files in the node_types directory.

        Returns:
            Dictionary mapping language names to their parsed node_types
        """
        node_types: list[dict[SemanticSearchLanguage, list[NodeTypeInfo]]] = []

        for node_type_file in self.node_types_dir.glob("*-node-types.json"):
            try:
                nodes = RootNodeTypes.from_node_type_file(node_type_file)
                node_types.append({cast(SemanticSearchLanguage, nodes.language): nodes.root})
            except Exception as e:
                # Log error but continue processing other files
                print(f"Warning: Failed to parse {node_type_file}: {e}")

        return node_types

    @staticmethod
    def _get_node_types_from_info_values(info: NodeTypeInfo) -> set[LiteralStringT]:
        """Extract node type names from NodeTypeInfo values."""
        all_types: set[LiteralStringT] = set()
        for key, value in info.items():
            match key:
                case "type_name" | "type":
                    all_types.add(cast(LiteralStringT, value))
                case "subtypes":
                    if isinstance(value, str):
                        all_types.add(cast(LiteralStringT, value))
                    else:
                        all_types |= {
                            cast(LiteralStringT, v.get("type_name", v.get("type")))
                            for v in cast(list[SubtypeField], value)
                            if v.get("type_name") or v.get("type")
                        }
                case "fields":
                    all_types |= cast(set[LiteralStringT], set(cast(WithFieldsT, value).keys()))
                    for field_info in cast(WithFieldsT, value).values():
                        if types := cast(ChildInfo, field_info).get("types"):
                            all_types |= {
                                cast(LiteralStringT, t.get("type_name", t.get("type")))
                                for t in cast(list[SimpleField], types)
                                if t.get("type_name") or t.get("type")
                            }
                case "children":
                    if types := cast(ChildInfo, value).get("types"):
                        all_types |= {
                            cast(LiteralStringT, t.get("type_name", t.get("type")))
                            for t in cast(list[SimpleField], types)
                            if t.get("type_name") or t.get("type")
                        }
                case _:
                    continue
        return all_types

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
                    for info_key, info_values in entry.items():
                        all_types.add(info_key)
                        all_types |= self._get_node_types_from_info_values(
                            cast(NodeTypeInfo, info_values)
                        )
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
                    raw_key = next(iter(first_entry.keys()), None)
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

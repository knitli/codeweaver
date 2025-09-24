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

    multiple: Required[bool]
    required: Required[bool]
    types: Required[list[FieldsTypesDict] | EmptyList]


class NodeTypeInfoDict(TypedDict):
    """TypedDict for raw node type information from JSON."""

    type_name: Required[Annotated[str, Field(serialization_alias="type", validation_alias="type")]]
    named: Required[bool]
    subtypes: NotRequired[list[dict[str, Any]] | EmptyList]
    fields: NotRequired[dict[LiteralStringT, FieldsInfoDict] | EmptyDict]
    children: NotRequired[FieldsInfoDict | EmptyDict]


class NodeTypeInfo(BasedModel):
    """Information about a tree-sitter node type."""

    type_name: Annotated[
        str,
        Field(
            description="The node type name", serialization_alias="type", validation_alias="type"
        ),
    ]
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
    root: Annotated[bool | None, Field(description="Whether this node can be a root node")] = None
    extra: Annotated[bool | None, Field(description="Whether this is an extra node")] = None


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

        This method tolerates the two common tree-sitter node-types.json shapes:
        - A list of node dicts (common)
        - A mapping of type_name -> node dict (less common)

        It normalizes nested "type" keys to "type_name" for validation, validates
        each node into NodeTypeInfo, and constructs a LanguageNodeType whose
        `node_type` is a mapping of type_name -> NodeTypeInfo instances.

        On first validation failure for a file, write a diagnostic JSON to /tmp
        to make inspection easy without altering behavior.
        """
        import json

        from pydantic_core import from_json

        raw = from_json(file_path.read_bytes())
        language = SemanticSearchLanguage.from_string(file_path.stem.replace("-node-types", ""))

        def _normalize(obj: Any) -> Any:
            """Recursively replace dict keys named 'type' -> 'type_name'."""
            if isinstance(obj, dict):
                new: dict[str, Any] = {}
                for k, v in obj.items():
                    nk = "type_name" if k == "type" else k
                    new[nk] = _normalize(v)
                return new
            if isinstance(obj, list):
                return [_normalize(i) for i in obj]
            return obj

        nodes_by_name: dict[str, dict] = {}
        diagnostics_written = False
        diagnostics_path = Path(f"/tmp/{file_path.stem}-first-failing-normalized.json")

        try:
            if isinstance(raw, dict):
                # mapping keyed by type name
                for key, value in raw.items():
                    if not isinstance(value, dict):
                        logger.debug("Skipping non-dict entry for key %s in %s", key, file_path)
                        continue
                    normalized = _normalize(value)
                    # ensure type_name is present
                    if "type_name" not in normalized:
                        normalized["type_name"] = key
                    try:
                        nti = NodeTypeInfo.model_validate(normalized)
                        nodes_by_name[str(nti.type_name)] = nti.model_dump()
                    except Exception as e:
                        logger.warning(
                            "Validation failed for node entry (key=%s) in %s: %s\nentry_keys=%s normalized_keys=%s",
                            key,
                            file_path,
                            e,
                            [str(k) for k in value] if value else None,
                            [str(k) for k in normalized]
                            if isinstance(normalized, Mapping)
                            else None,
                        )
                        if not diagnostics_written:
                            try:
                                payload = {
                                    "file": str(file_path),
                                    "key": key,
                                    "entry_keys": [str(k) for k in value] if value else None,
                                    "normalized_keys": [str(k) for k in normalized]
                                    if isinstance(normalized, Mapping)
                                    else None,
                                    "normalized": normalized,
                                }
                                diagnostics_path.write_text(
                                    json.dumps(payload, indent=2, default=str)
                                )
                                logger.error(
                                    "Wrote failing normalized entry to %s", diagnostics_path
                                )
                            except Exception as write_err:
                                logger.exception(
                                    "Failed to write diagnostics file %s: %s",
                                    diagnostics_path,
                                    write_err,
                                )
                            diagnostics_written = True
                        continue
            elif isinstance(raw, list):
                # list of node dicts
                for idx, item in enumerate(raw):
                    if not isinstance(item, dict):
                        logger.debug("Skipping non-dict list item %s in %s", idx, file_path)
                        continue
                    normalized = _normalize(item)
                    try:
                        nti = NodeTypeInfo.model_validate(normalized)
                        nodes_by_name[str(nti.type_name)] = nti.model_dump()
                    except Exception as e:
                        logger.warning(
                            "Validation failed for node list item %s in %s: %s\nitem_keys=%s normalized_keys=%s",
                            idx,
                            file_path,
                            e,
                            [str(k) for k in item] if item else None,
                            [str(k) for k in normalized]
                            if isinstance(normalized, Mapping)
                            else None,
                        )
                        if not diagnostics_written:
                            try:
                                payload = {
                                    "file": str(file_path),
                                    "index": idx,
                                    "item_keys": [str(k) for k in item] if item else None,
                                    "normalized_keys": [str(k) for k in normalized]
                                    if isinstance(normalized, Mapping)
                                    else None,
                                    "normalized": normalized,
                                }
                                diagnostics_path.write_text(
                                    json.dumps(payload, indent=2, default=str)
                                )
                                logger.error(
                                    "Wrote failing normalized entry to %s", diagnostics_path
                                )
                            except Exception as write_err:
                                logger.exception(
                                    "Failed to write diagnostics file %s: %s",
                                    diagnostics_path,
                                    write_err,
                                )
                            diagnostics_written = True
                        continue
            else:
                logger.warning("Unexpected JSON root type (%s) in %s", type(raw), file_path)

            # Construct LanguageNodeType using validated NodeTypeInfo instances.
            logger.debug(
                "Preparing to build LanguageNodeType for %s: nodes=%d keys=%s",
                file_path,
                len(nodes_by_name),
                list(nodes_by_name.keys())[:10],
            )
            sample_key = next(iter(nodes_by_name), None)
            sample_repr = None
            if sample_key:
                sample_item = nodes_by_name[sample_key]
                # nodes_by_name now stores plain serialized dicts (node.model_dump())
                if isinstance(sample_item, dict):
                    sample_repr = sample_item
                else:
                    try:
                        sample_repr = sample_item.model_dump()
                    except Exception:
                        sample_repr = repr(sample_item)
            try:
                lang_node = LanguageNodeType.model_validate({"node_type": nodes_by_name})
                future_self = RootNodeTypes.model_validate({language: [lang_node]})
                future_self._source_file = file_path
            except Exception as wrap_exc:
                # Write a safe diagnostic with partial state to help debug
                fallback_path = Path(f"/tmp/{file_path.stem}-language-validation-failure.json")
                try:
                    fallback = {
                        "file": str(file_path),
                        "error": repr(wrap_exc),
                        "nodes_by_name_count": len(nodes_by_name),
                        "nodes_by_name_keys": list(nodes_by_name.keys())[:50],
                        "sample_node": sample_repr,
                    }
                    # json was imported earlier in this function scope
                    diagnostics_written_here = False
                    try:
                        fallback_path.write_text(json.dumps(fallback, indent=2, default=str))
                        logger.error(
                            "Wrote language validation failure diagnostic to %s", fallback_path
                        )
                        diagnostics_written_here = True
                    except Exception:
                        logger.exception(
                            "Failed to write language validation fallback for %s", file_path
                        )
                finally:
                    # Re-raise the original exception to preserve behavior
                    raise
        except Exception as exc:
            # Attempt to write a fallback diagnostic when parsing fails before
            # per-item diagnostics could be written (e.g., validation in later
            # stages raising pydantic-core errors). This helps capture the raw
            # payload and the partial state for investigation without changing
            # parsing behaviour.
            try:
                if not diagnostics_written:
                    payload = {
                        "file": str(file_path),
                        "error": repr(exc),
                        "raw_type": type(raw).__name__ if "raw" in locals() else None,
                        "nodes_by_name_count": len(nodes_by_name)
                        if "nodes_by_name" in locals()
                        else None,
                        "nodes_by_name_keys": list(nodes_by_name.keys())[:50]
                        if "nodes_by_name" in locals()
                        else None,
                    }
                    diagnostics_path.write_text(json.dumps(payload, indent=2, default=str))
                    logger.error("Wrote fallback diagnostics to %s", diagnostics_path)
            except Exception:
                logger.exception("Failed to write fallback diagnostics for %s", file_path)
            raise RuntimeError(f"Failed to parse node-types file {file_path}: {exc}") from exc
        else:
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

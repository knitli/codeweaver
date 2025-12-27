# SPDX-FileCopyrightText: 2024-2025 Qdrant Solutions GmbH
# SPDX-License-Identifier: Apache-2.0
# This file was adapted from Qdrant's example MCP server, [mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant/)
#
# Modification/changes:
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Filter related functionality for searching and processing data, primarily with vector stores, but also for other data providers.

Nearly all of this file and its contents were adapted from Qdrant's example MCP server, [mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant/), and fall under Qdrant's copyright and Apache 2.0 license. Any modifications or changes made to the original code are copyrighted by Knitli Inc. and are licensed under MIT OR Apache-2.0, whichever you want.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from codeweaver.core.file_extensions import METADATA_PATH
from codeweaver.providers.vector_stores.search.condition import (
    FieldCondition,
    Filter,
    FilterableField,
)
from codeweaver.providers.vector_stores.search.match import MatchAny, MatchExcept, MatchValue
from codeweaver.providers.vector_stores.search.payload import PayloadSchemaType
from codeweaver.providers.vector_stores.search.range import Range


ArbitraryFilter = dict[str, Any]


def _validate_field_value(raw_field_name: str, field: FilterableField, field_value: Any) -> None:
    """Validate field value and raise errors if invalid."""
    if field_value is None and field.required:
        raise ValueError(f"Field {raw_field_name} is required")


def _should_skip_field(field: FilterableField, field_value: Any) -> bool:
    """Check if field should be skipped during filter processing."""
    return field_value is None or field.condition is None


def _match_value(field_name: str, v: Any) -> FieldCondition:
    """Match a specific value for a field."""
    return FieldCondition(key=field_name, match=MatchValue(value=v))


def _match_any(field_name: str, v: Any) -> FieldCondition:
    """Match any value for a field."""
    return FieldCondition(key=field_name, match=MatchAny(any=v))


def _match_except(field_name: str, v: Any) -> FieldCondition:
    """Match all values except the specified one for a field."""
    return FieldCondition(key=field_name, match=MatchExcept(**{"except": v}))


def _handle_keyword(
    field_name: str,
    condition: str,
    v: Any,
    must_conditions: list[FieldCondition],
    must_not_conditions: list[FieldCondition],
) -> None:
    """Handle keyword field conditions."""
    actions = {
        "==": lambda: must_conditions.append(_match_value(field_name, v)),
        "!=": lambda: must_not_conditions.append(_match_value(field_name, v)),
        "any": lambda: must_conditions.append(_match_any(field_name, v)),
        "except": lambda: must_conditions.append(_match_except(field_name, v)),
    }
    if condition not in actions:
        raise ValueError(f"Invalid condition {condition} for keyword field {field_name}")
    actions[condition]()


def _handle_integer(
    field_name: str,
    condition: str,
    v: Any,
    must_conditions: list[FieldCondition],
    must_not_conditions: list[FieldCondition],
) -> None:
    """Handle integer field conditions."""
    range_builders = {
        ">": lambda: FieldCondition(key=field_name, range=Range(gt=v)),
        ">=": lambda: FieldCondition(key=field_name, range=Range(gte=v)),
        "<": lambda: FieldCondition(key=field_name, range=Range(lt=v)),
        "<=": lambda: FieldCondition(key=field_name, range=Range(lte=v)),
    }
    actions: dict[str, Callable[[], None]] = {
        "==": lambda: must_conditions.append(_match_value(field_name, v)),
        "!=": lambda: must_not_conditions.append(_match_value(field_name, v)),
        "any": lambda: must_conditions.append(_match_any(field_name, v)),
        "except": lambda: must_conditions.append(_match_except(field_name, v)),
        **{
            op: (lambda builder=builder: must_conditions.append(builder()))
            for op, builder in range_builders.items()
        },
    }
    if condition not in actions:
        raise ValueError(f"Invalid condition {condition} for integer field {field_name}")
    actions[condition]()


def _handle_float(
    field_name: str,
    condition: str,
    v: Any,
    must_conditions: list[FieldCondition],
    _must_not_conditions: list[FieldCondition],
) -> None:
    """Handle float field conditions."""
    range_actions = {
        ">": lambda: must_conditions.append(FieldCondition(key=field_name, range=Range(gt=v))),
        ">=": lambda: must_conditions.append(FieldCondition(key=field_name, range=Range(gte=v))),
        "<": lambda: must_conditions.append(FieldCondition(key=field_name, range=Range(lt=v))),
        "<=": lambda: must_conditions.append(FieldCondition(key=field_name, range=Range(lte=v))),
    }
    if condition not in range_actions:
        raise ValueError(
            f"Invalid condition {condition} for float field {field_name}. Only range comparisons (>, >=, <, <=) are supported for float values."
        )
    range_actions[condition]()


def _handle_boolean(
    field_name: str,
    condition: str,
    v: Any,
    must_conditions: list[FieldCondition],
    must_not_conditions: list[FieldCondition],
) -> None:
    """Handle boolean field conditions."""
    actions = {
        "==": lambda: must_conditions.append(_match_value(field_name, v)),
        "!=": lambda: must_not_conditions.append(_match_value(field_name, v)),
    }
    if condition not in actions:
        raise ValueError(f"Invalid condition {condition} for boolean field {field_name}")
    actions[condition]()


def _create_condition_handlers(
    must_conditions: list[FieldCondition], must_not_conditions: list[FieldCondition]
) -> dict[str, Callable[[str, str, Any], None]]:
    """Create handlers for different field types."""
    return {
        "keyword": lambda field_name, condition, v: _handle_keyword(
            field_name, condition, v, must_conditions, must_not_conditions
        ),
        "integer": lambda field_name, condition, v: _handle_integer(
            field_name, condition, v, must_conditions, must_not_conditions
        ),
        "float": lambda field_name, condition, v: _handle_float(
            field_name, condition, v, must_conditions, must_not_conditions
        ),
        "boolean": lambda field_name, condition, v: _handle_boolean(
            field_name, condition, v, must_conditions, must_not_conditions
        ),
    }


def make_filter(
    filterable_fields: dict[str, FilterableField], values: dict[str, Any]
) -> ArbitraryFilter:
    """
    Create a filter dict from provided raw values mapped against declared filterable fields.
    """
    must_conditions: list[FieldCondition] = []
    must_not_conditions: list[FieldCondition] = []
    handlers = _create_condition_handlers(must_conditions, must_not_conditions)

    for raw_field_name, field_value in values.items():
        field = filterable_fields.get(raw_field_name)
        if field is None:
            raise ValueError(f"Field {raw_field_name} is not a filterable field")

        _validate_field_value(raw_field_name, field, field_value)

        if _should_skip_field(field, field_value):
            continue

        field_name = f"{METADATA_PATH}.{raw_field_name}"
        handler = handlers.get(field.field_type)
        if handler is None:
            raise ValueError(f"Unsupported field type {field.field_type} for field {field_name}")

        handler(field_name, field.condition, field_value)  # type: ignore

    return Filter(must=must_conditions, must_not=must_not_conditions).model_dump()


def make_indexes(filterable_fields: dict[str, FilterableField]) -> dict[str, PayloadSchemaType]:
    """
    Create a mapping of field names to their payload schema types.
    """
    return {
        f"{METADATA_PATH}.{field_name}": field.field_type
        for field_name, field in filterable_fields.items()
    }


def to_qdrant_filter(filter_obj: Filter | None) -> Filter | None:
    """Convert CodeWeaver Filter to Qdrant-compatible Filter format.

    Translates CodeWeaver's Filter objects into Qdrant's filter format with
    proper field conditions for file paths, languages, line ranges, and metadata.

    Args:
        filter_obj: CodeWeaver Filter object with conditions to translate.

    Returns:
        Qdrant-compatible Filter object or None if input is None.

    Note:
        The current implementation passes through the Filter object as-is since
        CodeWeaver's Filter model (from engine.search.condition) is already compatible
        with Qdrant's filter format. This function serves as an integration point
        for future filter transformations or field mapping customizations.

    Examples:
        >>> from codeweaver.providers.vector_stores.search import (
        ...     Filter,
        ...     FieldCondition,
        ...     MatchAny,
        ... )
        >>> # Filter by file paths
        >>> filter_obj = Filter(
        ...     must=[
        ...         FieldCondition(
        ...             key="file_path", match=MatchAny(any=["src/main.py", "src/utils.py"])
        ...         )
        ...     ]
        ... )
        >>> qdrant_filter = to_qdrant_filter(filter_obj)
        >>> assert qdrant_filter == filter_obj

        >>> # Filter by language
        >>> filter_obj = Filter(
        ...     must=[
        ...         FieldCondition(
        ...             key="language", match=MatchAny(any=["python", "javascript"])
        ...         )
        ...     ]
        ... )
        >>> qdrant_filter = to_qdrant_filter(filter_obj)
        >>> assert qdrant_filter is not None

        >>> # Filter by line range
        >>> from codeweaver.providers.vector_stores.search import Range
        >>> filter_obj = Filter(
        ...     must=[FieldCondition(key="line_start", range=Range(gte=10, lte=100))]
        ... )
        >>> qdrant_filter = to_qdrant_filter(filter_obj)
        >>> assert qdrant_filter is not None

        >>> # No filter
        >>> assert to_qdrant_filter(None) is None
    """
    return None if filter_obj is None else filter_obj


__all__ = ("ArbitraryFilter", "make_filter", "to_qdrant_filter")

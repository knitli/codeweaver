# SPDX-FileCopyrightText: 2024-2025 Qdrant Solutions GmbH
# SPDX-License-Identifier: Apache-2.0
# This file was adapted from Qdrant's example MCP server, [mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant/)
# Modification/changes:
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Filter related functionality for searching and processing data, primarily with vector stores, but also for other data providers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

from codeweaver._constants import METADATA_PATH
from codeweaver.services._match_models import (
    FieldCondition,
    Filter,
    MatchAny,
    MatchExcept,
    MatchValue,
    Range,
)
from codeweaver.vector_stores.base import PayloadSchemaType


Metadata = dict[str, Any]
ArbitraryFilter = dict[str, Any]


class FilterableField(BaseModel):
    """Represents a field that can be filtered."""

    name: str = Field(description="""The name of the field payload field to filter on""")
    description: str = Field(
        description="""A description for the field used in the tool description"""
    )
    field_type: Literal["keyword", "integer", "float", "boolean"] = Field(
        description="""The type of the field"""
    )
    condition: Literal["==", "!=", ">", ">=", "<", "<=", "any", "except"] | None = Field(
        default=None,
        description=(
            "The condition to use for the filter. If not provided, the field will be indexed, but no "
            "filter argument will be exposed to MCP tool."
        ),
    )
    required: bool = Field(
        default=False, description="""Whether the field is required for the filter."""
    )


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
    must_not_conditions: list[FieldCondition],
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
    indexes: dict[str, PayloadSchemaType] = {}

    for field_name, field in filterable_fields.items():
        if field.field_type == "keyword":
            indexes[f"{METADATA_PATH}.{field_name}"] = PayloadSchemaType.KEYWORD
        elif field.field_type == "integer":
            indexes[f"{METADATA_PATH}.{field_name}"] = PayloadSchemaType.INTEGER
        elif field.field_type == "float":
            indexes[f"{METADATA_PATH}.{field_name}"] = PayloadSchemaType.FLOAT
        elif field.field_type == "boolean":
            indexes[f"{METADATA_PATH}.{field_name}"] = PayloadSchemaType.BOOL
        else:
            raise ValueError(f"Unsupported field type {field.field_type} for field {field_name}")

    return indexes

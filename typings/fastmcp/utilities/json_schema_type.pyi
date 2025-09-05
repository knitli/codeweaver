# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from collections.abc import Mapping
from typing import Any, NotRequired

from typing_extensions import TypedDict

"""Convert JSON Schema to Python types with validation.

The json_schema_to_type function converts a JSON Schema into a Python type that can be used
for validation with Pydantic. It supports:

- Basic types (string, number, integer, boolean, null)
- Complex types (arrays, objects)
- Format constraints (date-time, email, uri)
- Numeric constraints (minimum, maximum, multipleOf)
- String constraints (minLength, maxLength, pattern)
- Array constraints (minItems, maxItems, uniqueItems)
- Object properties with defaults
- References and recursive schemas
- Enums and constants
- Union types

Example:
    ```python
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "age": {"type": "integer", "minimum": 0},
            "email": {"type": "string", "format": "email"}
        },
        "required": ["name", "age"]
    }

    # Name is optional and will be inferred from schema's "title" property if not provided
    Person = json_schema_to_type(schema)
    # Creates a validated dataclass with name, age, and optional email fields
    ```
"""
__all__ = ["JSONSchema", "json_schema_to_type"]
FORMAT_TYPES: dict[str, Any] = ...
_classes: dict[tuple[str, Any], type | None] = ...

class JSONSchema(TypedDict):
    type: NotRequired[str | list[str]]
    properties: NotRequired[dict[str, JSONSchema]]
    required: NotRequired[list[str]]
    additionalProperties: NotRequired[bool | JSONSchema]
    items: NotRequired[JSONSchema | list[JSONSchema]]
    enum: NotRequired[list[Any]]
    const: NotRequired[Any]
    default: NotRequired[Any]
    description: NotRequired[str]
    title: NotRequired[str]
    examples: NotRequired[list[Any]]
    format: NotRequired[str]
    allOf: NotRequired[list[JSONSchema]]
    anyOf: NotRequired[list[JSONSchema]]
    oneOf: NotRequired[list[JSONSchema]]
    not_: NotRequired[JSONSchema]
    definitions: NotRequired[dict[str, JSONSchema]]
    dependencies: NotRequired[dict[str, JSONSchema | list[str]]]
    pattern: NotRequired[str]
    minLength: NotRequired[int]
    maxLength: NotRequired[int]
    minimum: NotRequired[int | float]
    maximum: NotRequired[int | float]
    exclusiveMinimum: NotRequired[int | float]
    exclusiveMaximum: NotRequired[int | float]
    multipleOf: NotRequired[int | float]
    uniqueItems: NotRequired[bool]
    minItems: NotRequired[int]
    maxItems: NotRequired[int]
    additionalItems: NotRequired[bool | JSONSchema]

def json_schema_to_type(schema: Mapping[str, Any], name: str | None = ...) -> type:
    ...

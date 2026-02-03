# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: no-complex-if-expressions
"""Common utilities for type handling."""

import platform

from enum import Enum
from types import DynamicClassAttribute
from typing import Any, cast

import textcase

from pydantic.fields import ComputedFieldInfo, FieldInfo


def clean_sentinel_from_schema(schema: dict[str, Any]) -> None:  # noqa: C901
    """Remove Sentinel/Unset artifacts from JSON schema.

    Use this as a `json_schema_extra` callback in models that use Sentinel/Unset
    as default values. This function:
    - Removes 'Unset' default values
    - Fixes empty anyOf arrays (invalid JSON Schema)
    - Simplifies single-item anyOf arrays

    Example:
        model_config = ConfigDict(
            json_schema_extra=clean_sentinel_from_schema,
            ...
        )
    """

    def _clean_property(prop_schema: dict[str, Any]) -> None:
        """Clean a single property schema."""
        # Remove 'Unset' default values
        if prop_schema.get("default") == "Unset":
            del prop_schema["default"]

        # Handle anyOf arrays
        if "anyOf" in prop_schema:
            any_of = prop_schema["anyOf"]
            if any_of == []:
                # Empty anyOf is invalid JSON Schema, remove it
                del prop_schema["anyOf"]
            elif len(any_of) == 1:
                # Single item anyOf can be simplified - merge the schema
                single_schema = any_of[0]
                del prop_schema["anyOf"]
                # Preserve existing keys like title, description, default
                for key, value in single_schema.items():
                    if key not in prop_schema:
                        prop_schema[key] = value

        # Recursively clean nested properties
        if "properties" in prop_schema:
            for nested_prop in prop_schema["properties"].values():
                _clean_property(nested_prop)

        # Also clean items in arrays
        if "items" in prop_schema and isinstance(prop_schema["items"], dict):
            _clean_property(prop_schema["items"])

    # Clean top-level properties
    if "properties" in schema:
        for prop_schema in schema["properties"].values():
            _clean_property(prop_schema)

    # Clean $defs for nested model definitions
    if "$defs" in schema:
        for def_schema in schema["$defs"].values():
            if "properties" in def_schema:
                for prop_schema in def_schema["properties"].values():
                    _clean_property(prop_schema)


def generate_title(model: type[Any]) -> str:
    """Generate a title for a model."""
    model_name = (
        model.__name__
        if hasattr(model, "__name__")
        else (
            model.__class__.__name__
            if hasattr(model, "__class__") and hasattr(model.__class__, "__name__")
            else str(model)
        )
    )
    return textcase.title(model_name.replace("Model", ""))


def generate_field_title(name: str, info: FieldInfo | ComputedFieldInfo) -> str:
    """Generate a title for a model field."""
    if hasattr(info, "title") and (titled := info.title):
        return titled
    if aliased := info.alias or (
        hasattr(info, "serialization_alias") and cast(FieldInfo, info).serialization_alias
    ):
        return textcase.sentence(aliased)
    return textcase.sentence(name)


def add_enum_member[EnumT: Enum](
    enum_cls: type[EnumT], member_name: str, member_value: Any
) -> None:
    """Add a new member to an Enum class."""
    if platform.python_version_tuple() >= ("3", "13"):
        enum_cls._add_member_(member_name, member_value)  # ty:ignore[unresolved-attribute]
    else:
        add_enum_alias(enum_cls(member_value), member_name)


def add_enum_alias[EnumT: Enum](enum_instance_member: EnumT, alias_name: str) -> None:
    """Add an alias to an Enum member."""
    if platform.python_version_tuple() >= ("3", "13"):
        enum_instance_member._add_alias_(alias_name)  # ty:ignore[unresolved-attribute]
    # life will be simpler when we can drop support for <3.13
    else:
        enum_cls = type(enum_instance_member)
        found_descriptor = None
        descriptor_type = None
        class_type = None
        for base in enum_cls.__mro__[1:]:
            attr = base.__dict__.get(alias_name)
            if attr is not None:
                if isinstance(attr, (property, DynamicClassAttribute)):
                    found_descriptor = attr
                    class_type = base
                    descriptor_type = "enum"
                    break
                if (
                    hasattr(attr, "__get__")
                    or hasattr(attr, "__set__")
                    or hasattr(attr, "__delete__")
                ):
                    found_descriptor = attr
                    descriptor_type = descriptor_type or "desc"
                    class_type = class_type or base
                    continue
                descriptor_type = "attr"
                class_type = base
        if found_descriptor:
            redirect = property()
            redirect.member = enum_instance_member  # ty:ignore[unresolved-attribute]
            redirect.__set_name__(enum_cls, alias_name)  # ty:ignore[unresolved-attribute]
            if descriptor_type in ("enum", "desc"):
                # earlier descriptor found; copy fget, fset, fdel to this one.
                redirect.fget = getattr(found_descriptor, "fget", None)
                redirect._get = getattr(found_descriptor, "__get__", None)  # ty:ignore[unresolved-attribute]
                redirect.fset = getattr(found_descriptor, "fset", None)
                redirect._set = getattr(found_descriptor, "__set__", None)  # ty:ignore[unresolved-attribute]
                redirect.fdel = getattr(found_descriptor, "fdel", None)
                redirect._del = getattr(found_descriptor, "__delete__", None)  # ty:ignore[unresolved-attribute]
            redirect._attr_type = descriptor_type  # ty:ignore[unresolved-attribute]
            redirect._cls_type = class_type  # ty:ignore[unresolved-attribute]
            setattr(enum_cls, alias_name, redirect)
        else:
            setattr(enum_cls, alias_name, enum_instance_member)
        enum_cls._member_map_[alias_name] = enum_instance_member  # ty:ignore[unresolved-attribute]


__all__ = (
    "add_enum_alias",
    "add_enum_member",
    "clean_sentinel_from_schema",
    "generate_field_title",
    "generate_title",
)

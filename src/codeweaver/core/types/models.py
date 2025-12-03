# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Base dataclass and model implementations for CodeWeaver."""

from __future__ import annotations

import abc
import sys as _sys

from collections.abc import Callable, Generator, Iterator, Sequence
from enum import Enum
from functools import cached_property
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    NamedTuple,
    NotRequired,
    Self,
    TypedDict,
    Unpack,
    cast,
    override,
)

import textcase

from pydantic import BaseModel, ConfigDict, PrivateAttr, RootModel, TypeAdapter
from pydantic.fields import ComputedFieldInfo, FieldInfo
from pydantic.main import IncEx

from codeweaver.core.types.aliases import FilteredKey, FilteredKeyT, LiteralStringT


if TYPE_CHECKING:
    from codeweaver.core.types.enum import AnonymityConversion


FILTERED_KEYS: frozenset[FilteredKey] = frozenset({FilteredKey("api_key")})

# ================================================
# *       Dataclass Serialization
# ================================================


class SerializationKwargs(TypedDict, total=False):
    """A TypedDict for TypeAdapter serialization keyword arguments."""

    by_alias: NotRequired[bool | None]
    context: NotRequired[dict[str, Any] | None]
    exclude: NotRequired[IncEx | None]
    exclude_defaults: NotRequired[bool]
    exclude_none: NotRequired[bool]
    exclude_unset: NotRequired[bool]
    fallback: NotRequired[Callable[[Any], Any] | None]
    include: NotRequired[IncEx | None]
    round_trip: NotRequired[bool]
    serialize_as_any: NotRequired[bool]
    warnings: NotRequired[bool | Literal["none", "warn", "error"]]


class DeserializationKwargs(TypedDict, total=False):
    """A TypedDict for TypeAdapter deserialization keyword arguments."""

    by_alias: NotRequired[bool | None]
    by_name: NotRequired[bool | None]
    context: NotRequired[dict[str, Any] | None]
    experimental_allow_partial: NotRequired[bool | Literal["off", "on", "trailing-strings"]]
    strict: NotRequired[bool | None]


class DataclassSerializationMixin:
    """A mixin class that provides serialization and deserialization methods for dataclasses using Pydantic's TypeAdapter."""

    _module: Annotated[str | None, PrivateAttr()] = None
    _adapter: Annotated[TypeAdapter[Self] | None, PrivateAttr()] = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """Get telemetry keys for the dataclass."""
        return None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the mixin and set the module name and adapter."""
        object.__setattr__(
            self,
            "_module",
            self.__module__
            if hasattr(self, "__module__")
            else self.__class__.__module__ or _sys.modules[__name__].__name__,
        )
        object.__setattr__(self, "_adapter", TypeAdapter(type(self), module=self._module))

    @cached_property
    def _adapted_self(self) -> TypeAdapter[Self]:
        """Get a Pydantic TypeAdapter for the SessionStatistics instance."""
        object.__setattr__(
            self, "_adapter", self._adapter or TypeAdapter(type(self), module=self._module)
        )
        if not self._adapter:
            raise RuntimeError("TypeAdapter is not initialized.")
        if self._adapter.pydantic_complete:
            return cast(TypeAdapter[Self], self._adapter)
        try:
            _ = self._adapter.rebuild()
        except Exception as e:
            raise RuntimeError("Failed to rebuild the TypeAdapter.") from e
        else:
            return cast(TypeAdapter[Self], self._adapter)

    @classmethod
    def _get_module(cls) -> str | None:
        """Get the module name for the current class."""
        return (
            cls.__module__
            if hasattr(cls, "__module__")
            else cls.__class__.__module__
            if hasattr(cls, "__class__")
            else _sys.modules[__name__].__name__
        )

    def dump_json(self, **kwargs: Unpack[SerializationKwargs]) -> bytes:
        """Serialize the session statistics to JSON bytes."""
        return self._adapted_self.dump_json(self, **kwargs)

    def dump_python(self, **kwargs: Unpack[SerializationKwargs]) -> dict[str, Any]:
        """Serialize the session statistics to a Python dictionary."""
        return self._adapted_self.dump_python(self, **kwargs)

    @classmethod
    def validate_json(cls, data: bytes, **kwargs: Unpack[DeserializationKwargs]) -> Self:
        """Deserialize the session statistics from JSON bytes."""
        adapter = TypeAdapter(cls, module=cls._get_module())
        return adapter.validate_json(data, **kwargs)

    @classmethod
    def validate_python(cls, data: dict[str, Any], **kwargs: Unpack[DeserializationKwargs]) -> Self:
        """Deserialize the session statistics from a Python dictionary."""
        adapter = TypeAdapter(cls, module=cls._get_module())
        return adapter.validate_python(data, **kwargs)

    def serialize_for_cli(self) -> dict[str, Any]:
        """Serialize the model for CLI output."""
        self_map: dict[str, Any] = {}
        if hasattr(type(self), "__pydantic_fields__"):
            # ty won't like this because the attributes only exist on the inherited subclasses
            fields: dict[str, Any] = type(self).__pydantic_fields__  # type: ignore
            if hasattr(self, "__pydantic_decorators__") and (
                computed_field_names := type(self).__pydantic_decorators__.computed_fields.keys()  # type: ignore
            ):
                # Add computed fields to the fields dict (keys only, values don't matter for iteration)
                fields = {**fields, **dict.fromkeys(computed_field_names)}  # type: ignore
            for field in cast(dict[str, Any], self.__pydantic_fields__):  # type: ignore
                if (attr := getattr(self, field, None)) and hasattr(attr, "serialize_for_cli"):
                    self_map[field] = attr.serialize_for_cli()
                elif isinstance(attr, Sequence | Iterator) and not isinstance(attr, str):
                    self_map[field] = [
                        item.serialize_for_cli()  # type: ignore
                        if hasattr(item, "serialize_for_cli")  # type: ignore
                        else item
                        for item in attr  # type: ignore
                    ]
        return self.dump_python(round_trip=True, exclude_none=True) | self_map

    def _telemetry_handler(self, _serialized_self: dict[str, Any], /) -> dict[str, Any]:
        """An optional handler for subclasses to modify telemetry serialization. By default, it returns an empty dict.

        We use any returned keys as overrides for the serialized_self.
        """
        return {}

    def serialize_for_telemetry(self) -> dict[str, Any]:
        """Serialize the model for telemetry output, filtering sensitive keys."""
        from codeweaver.core.types.enum import AnonymityConversion

        excludes: set[str] = set()
        default_group: dict[FilteredKeyT, Any] = {}
        if telemetry_keys := (self._telemetry_keys() or {}):
            excludes = {
                str(key)
                for key, conversion in telemetry_keys.items()
                if conversion == AnonymityConversion.FORBIDDEN
            }
            default_group = {
                key: conversion.filtered(getattr(self, str(key), None))
                for key, conversion in telemetry_keys.items()
                if conversion != AnonymityConversion.FORBIDDEN
            }
        data = self.dump_python(round_trip=True, exclude_none=True, exclude=excludes)
        filtered_group: dict[str, Any] = self._telemetry_handler(data)
        return {
            key: (
                # First priority: handler override
                filtered_group[key]
                if key in filtered_group
                # Second priority: filtered conversion from telemetry_keys
                else default_group.get(FilteredKey(cast(LiteralStringT, key)), value)
            )
            for key, value in data.items()
        }


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


DATACLASS_CONFIG = ConfigDict(
    arbitrary_types_allowed=True,
    cache_strings="keys",
    field_title_generator=generate_field_title,
    model_title_generator=generate_title,
    serialize_by_alias=True,
    str_strip_whitespace=True,
    use_attribute_docstrings=True,
    validate_by_alias=True,
    validate_by_name=True,
)

# ================================================
# *      Pydantic Base Implementations
# ================================================

BASEDMODEL_CONFIG = DATACLASS_CONFIG | ConfigDict(
    cache_strings="all", json_schema_extra=clean_sentinel_from_schema
)
FROZEN_BASEDMODEL_CONFIG = BASEDMODEL_CONFIG | ConfigDict(frozen=True)


class RootedRoot[RootType: Sequence[Any]](RootModel[Sequence[Any]]):
    """A pre-customized pydantic RootModel with common configuration for CodeWeaver."""

    model_config = BASEDMODEL_CONFIG

    root: RootType

    @override
    def __iter__(self) -> Generator[Any]:
        """Iterate over the root items."""
        yield from self.root

    def __getitem__(self, index: int) -> Any:
        """Get an item by index."""
        return self.root[index]

    def __len__(self) -> int:
        """Get the length of the root."""
        return len(self.root)

    def __contains__(self, item: Any) -> bool:
        """Check if an item is in the root."""
        return item in self.root

    def __next__(self) -> Any:
        """Get the next item in the root."""
        return next(iter(self.root))

    def serialize_for_cli(self) -> list[Any]:
        """Serialize the model for CLI output."""
        return [
            item.serialize_for_cli() if hasattr(item, "serialize_for_cli") else item
            for item in self.root
        ]


class BasedModel(BaseModel):
    """A baser `BaseModel` for all models in the CodeWeaver project."""

    model_config = BASEDMODEL_CONFIG

    def serialize_for_cli(self) -> dict[str, Any]:
        """Serialize the model for CLI output."""
        fields = set(type(self).model_fields.keys()) | set(type(self).model_computed_fields.keys())
        self_map: dict[str, Any] = {}
        for field in fields:
            if (attr := getattr(self, field, None)) and hasattr(attr, "serialize_for_cli"):
                self_map[field] = attr.serialize_for_cli()
            elif isinstance(attr, Sequence | Iterator) and not isinstance(attr, str):
                self_map[field] = [
                    item.serialize_for_cli()  # type: ignore
                    if hasattr(item, "serialize_for_cli")  # type: ignore
                    else item
                    for item in attr  # type: ignore
                ]
        # Get model dump, handling potential Missing/Undefined values
        base_dict = self.model_dump(mode="python", round_trip=True, exclude_none=True)
        # If model_dump returns a non-dict (like Missing), use empty dict
        if not isinstance(base_dict, dict):
            base_dict = {}
        return base_dict | self_map

    @abc.abstractmethod
    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """Get telemetry keys for the dataclass."""
        raise NotImplementedError("Subclasses must implement _telemetry_keys method.")

    def _telemetry_handler(self, _serialized_self: dict[str, Any], /) -> dict[str, Any]:
        """An optional handler for subclasses to modify telemetry serialization. By default, it returns an empty dict.

        We use any returned keys as overrides for the serialized_self.
        """
        return {}

    def serialize_for_telemetry(self) -> dict[str, Any]:
        """Serialize the model for telemetry output, filtering sensitive keys."""
        from codeweaver.core.types.enum import AnonymityConversion

        excludes: set[str] = set()
        default_group: dict[FilteredKeyT, Any] = {}
        if telemetry_keys := (self._telemetry_keys() or {}):
            excludes = {
                str(key)
                for key, conversion in telemetry_keys.items()
                if conversion == AnonymityConversion.FORBIDDEN
            }
            default_group = {
                key: conversion.filtered(getattr(self, str(key), None))
                for key, conversion in telemetry_keys.items()
                if conversion != AnonymityConversion.FORBIDDEN
            }
        data = self.model_dump(round_trip=True, exclude_none=True, exclude=excludes)
        filtered_group: dict[str, Any] = self._telemetry_handler(data)
        return {
            key: (
                # First priority: handler override
                filtered_group[key]
                if key in filtered_group
                # Second priority: filtered conversion from telemetry_keys
                else default_group.get(FilteredKey(cast(LiteralStringT, key)), value)
            )
            for key, value in data.items()
        }


class EnvFormat(Enum):
    """Supported data formats for MCP server inputs and outputs."""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    FILEPATH = "filepath"

    def __str__(self) -> str:
        """String representation of the EnvFormat."""
        return self.value


class EnvVarInfo(NamedTuple):
    """Describes an environment variable and its description.

    An optional variable name, if given, provides the key if the variable's value is passed to the provider's client (if different).
    """

    env: str
    description: str
    is_required: bool = False
    is_secret: bool = False
    fmt: EnvFormat = EnvFormat.STRING
    default: str | None = None
    """A default value that CodeWeaver uses if not set in the environment."""
    choices: set[str] | None = None
    variable_name: str | None = None

    def as_mcp_info(self) -> dict[str, Any]:
        """Convert to MCP server JSON format."""
        return {
            k: v
            for k, v in self._asdict().items()
            if k not in {"variable_name", "env"} and v is not None
        } | {"name": self.env}

    def as_kwarg(self) -> dict[str, str | None]:
        """Convert to a keyword argument string."""
        import os

        return {f"{self.variable_name or self.env}": os.getenv(self.env)}

    def as_docker_yaml(self) -> None:
        """TODO: Convert to Docker MCP Registry YAML format."""


__all__ = (
    "BASEDMODEL_CONFIG",
    "DATACLASS_CONFIG",
    "FROZEN_BASEDMODEL_CONFIG",
    "BasedModel",
    "DataclassSerializationMixin",
    "DeserializationKwargs",
    "EnvVarInfo",
    "RootedRoot",
    "SerializationKwargs",
    "generate_field_title",
    "generate_title",
)

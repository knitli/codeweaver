# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dataclass types and serialization mixins."""

# sourcery skip: no-complex-if-expressions
import sys as _sys

from collections.abc import Callable, Iterator, Sequence
from functools import cached_property
from typing import Annotated, Any, Literal, NotRequired, Self, TypedDict, Unpack, cast

from pydantic import ConfigDict, Field, PrivateAttr, TypeAdapter, computed_field
from pydantic.dataclasses import dataclass
from pydantic.main import IncEx

from codeweaver.core.types.aliases import FilteredKeyT
from codeweaver.core.types.enum import AnonymityConversion
from codeweaver.core.types.utils import generate_field_title, generate_title


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
        from codeweaver.core.types.aliases import FilteredKey, FilteredKeyT, LiteralStringT
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


@dataclass(config=DATACLASS_CONFIG, order=True, frozen=True)
class BaseEnumData(DataclassSerializationMixin):
    """A dataclass to hold enum member data.

    `BaseEnumData` provides a standard structure for enum member data, including name, value, aliases, and description. Subclasses can extend this dataclass to include additional fields as needed.

    `BaseEnumData` is intended to be used in conjunction with `BaseDataclassEnum` to create enums with rich metadata. See `codeweaver.core.types.enum.BaseDataclassEnum` for more details.

    For an implementation example, see `codeweaver.semantic.classifications.BaseAgentTask` (the type) and `codeweaver.semantic.classifications.AgentTask` (the enum).
    """

    aliases: tuple[str, ...] = Field(
        description="A tuple of alternative names or aliases for the enum member.",
        default_factory=tuple,
    )
    _description: (
        Annotated[
            str | None, Field(description="The description of the enum member.", exclude=True)
        ]
        | None
    ) = None

    # These are just generic fields, define more in subclasses as needed.

    def __init__(
        self, aliases: Sequence[str] | None = None, description: str | None = None, **kwargs: Any
    ) -> None:
        """Initialize the BaseEnumData dataclass."""
        object.__setattr__(self, "aliases", tuple(aliases) if aliases is not None else ())
        object.__setattr__(self, "_description", description)
        for key, val in kwargs.items():
            object.__setattr__(self, key, val)
        super().__init__()

    @computed_field
    @property
    def description(self) -> str | None:
        """Get the description of the enum member."""
        return self._description


__all__ = (
    "DATACLASS_CONFIG",
    "BaseEnumData",
    "DataclassSerializationMixin",
    "DeserializationKwargs",
    "SerializationKwargs",
)

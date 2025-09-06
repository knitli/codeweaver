# sourcery skip: snake-case-variable-declarations
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""A foundational enum class for the CodeWeaver project for common functionality."""

from __future__ import annotations

import sys as _sys

from collections.abc import Callable, Generator, Iterator
from enum import Enum, unique
from threading import Lock as _Lock
from types import FrameType
from typing import Annotated, Any, LiteralString, Self, cast

import textcase

from aenum import extend_enum  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]
from pydantic import GetCoreSchemaHandler, GetPydanticSchema
from pydantic_core import core_schema


type LiteralStringT = Annotated[
    LiteralString, GetPydanticSchema(lambda _schema, handle: handle(str))
]
type EnumExtend = Callable[[Enum, str], Enum]
extend_enum: EnumExtend = extend_enum  # pyright: ignore[reportUnknownVariableType]


@unique
class BaseEnum(Enum):
    """An enum class that provides common functionality for all enums in the CodeWeaver project. Enum members must be unique and either all strings or all integers.

    `aenum.extend_enum` allows us to dynamically add members, such as for plugin systems.

    BaseEnum provides convenience methods for converting between strings and enum members, checking membership, and retrieving members and members' values, and adding new members dynamically.
    """

    @staticmethod
    def _deconstruct_string(value: str) -> list[str]:
        """Deconstruct a string into its component parts."""
        value = value.strip().lower()
        for underscore_length in range(4, 0, -1):
            value = value.replace("_" * underscore_length, "_")
        return [v for v in value.split("_") if v]

    def _multiply_variations(self, s: str) -> set[str]:
        """Generate multiple variations of a string."""
        return {
            s,
            textcase.snake(s),
            textcase.kebab(s),
            textcase.sentence(s),
            textcase.middot(s),
            textcase.camel(s),
            *self._encode_name(s),
        }

    @property
    def aka(self) -> tuple[str, ...] | tuple[int, ...]:
        """Return the alias for the enum member, if one exists."""
        if isinstance(self.value, str):
            return tuple(
                sorted({
                    v.lower()
                    for v in set(  # type: ignore
                        *(self._multiply_variations(self.name)),
                        *(self._multiply_variations(self.value)),
                    )
                    if v and isinstance(v, str)
                })
            )
        return (self.value,)

    @property
    def encoded_value(self) -> str:
        """Return the encoded value for the enum member."""
        return self._encode_name(self.value) if self.value_type is str else str(self.value)

    @property
    def encoded_name(self) -> str:
        """Return the encoded name for the enum member."""
        return self._encode_name(self.name) if self.value_type is str else self.name

    @property
    def decoded_value(self) -> str:
        """Return the decoded value for the enum member."""
        return self._decode_name(self.value) if self.value_type is str else str(self.value)

    @property
    def decoded_name(self) -> str:
        """Return the decoded name for the enum member."""
        return self._decode_name(self.name) if self.value_type is str else self.name

    @classmethod
    def aliases(cls) -> dict[str, Self] | dict[int, Self]:
        """Provides a way to identify alternate names for a member, used in string conversion and identification."""
        alias_map: dict[str | int, Self] = {}
        if cls._value_type() is int:
            for member in cls:
                alias_map[member.value] = member
            return cast(dict[int, Self], alias_map)
        for member in cls:
            for alias in member.aka:
                if alias not in alias_map:
                    alias_map[alias] = member
        return cast(dict[str, Self], alias_map)

    @classmethod
    def from_string(cls, value: str) -> Self:
        # sourcery skip: remove-unnecessary-cast
        """Convert a string to the corresponding enum member. Flexibly handles different cases, dashes vs underscores, and some common variations."""
        if cls._value_type() is int and str(value).isdigit():
            return cls(int(value))
        if cls._value_type() is int:
            raise ValueError(f"{value} is not a valid {cls.__qualname__}")
        if literal_value := next(
            (
                member
                for member in cls
                if member.value.lower() == str(value).lower()
                or member.name.lower() == str(value).lower()
            ),
            None,
        ):
            return cast(Self, literal_value)
        if (aliases := cls.aliases()) and (
            found_member := next(
                (
                    member
                    for alias, member in aliases.items()
                    if cast(str, alias).lower() == str(value).lower()
                ),
                None,
            )
        ):
            return found_member
        value_parts = cls._deconstruct_string(value)
        if found_member := next(
            (member for member in cls if cls._deconstruct_string(member.name) == value_parts), None
        ):
            return found_member
        raise ValueError(f"{value} is not a valid {cls.__qualname__} member")

    @staticmethod
    def _encode_name(value: str) -> str:
        """
        Encode a string for use as an enum member name.

        Provides a fully reversible encoding to normalize enum members and values. Doesn't handle all possible cases (by a long shot), but works for what we need without harming readability.
        """
        return value.lower().replace("-", "__").replace(":", "___").replace(" ", "____")

    @staticmethod
    def _decode_name(value: str, *, for_pydantic_ai: bool = False) -> str:
        """Decodes an enum member or value into its original form."""
        return value.lower().replace("____", " ").replace("___", ":").replace("__", "-")

    @classmethod
    def _value_type(cls) -> type[int | str]:
        """Return the type of the enum values."""
        if all(isinstance(member.value, str) for member in cls.__members__.values() if member):
            return str
        if all(
            isinstance(member.value, int)
            for member in cls.__members__.values()
            if member and member.value
        ):
            return int
        raise TypeError(
            f"All members of {cls.__qualname__} must have the same value type and must be either str or int."
        )

    def __lt__(self, other: Self) -> bool:
        """Less than comparison for enum members."""
        if not isinstance(other, self.__class__) and (
            not isinstance(other, str | int)
            or (isinstance(other, int) and self.value_type is str)
            or (isinstance(other, str) and self.value_type is int)
        ):
            return NotImplemented
        if self.value_type is str and isinstance(other, str):
            return str(self).lower() < other.lower()
        return self.value < other

    def __le__(self, other: Self) -> bool:
        """Less than or equal to comparison for enum members."""
        if not isinstance(other, self.__class__) and (
            not isinstance(other, str | int)
            or (isinstance(other, int) and self.value_type is str)
            or (isinstance(other, str) and self.value_type is int)
        ):
            return NotImplemented
        if self.value_type is str and isinstance(other, str):
            return str(self).lower() <= other.lower()
        return self.value <= other

    def __len__(self) -> int:
        """Return the number of members in the enum."""
        return len(self.__class__.__members__)

    @classmethod
    def __iter__(cls) -> Iterator[Self]:
        """Return an iterator over the enum members."""
        yield from cls.__members__.values()

    @classmethod
    def is_member(cls, value: str | int) -> bool:
        """Check if a value is a member of the enum."""
        if isinstance(value, int) and cls._value_type() is int:
            return value in cls.__members__
        return (
            value in cls.aliases()
            or any(member.value for member in cls if member.value == value)
            or any(member.name for member in cls if member.name == value)
        )

    @property
    def value_type(self) -> type[int | str]:
        """Return the type of the enum member's value."""
        return type(self)._value_type()

    @property
    def as_variable(self) -> str:
        """Return the string representation of the enum member as a variable name."""
        return self.value if self.value_type is str else str(self.name.lower())

    @classmethod
    def members(cls) -> Generator[Self]:
        """Return all members of the enum as a tuple."""
        yield from cls

    @classmethod
    def values(cls) -> Generator[str | int]:
        """Return all enum member names as a tuple."""
        yield from (member.value for member in cls)

    def __str__(self) -> str:
        """Return the string representation of the enum member."""
        return self.name.replace("_", " ").lower()

    @classmethod
    def members_to_values(cls) -> dict[Self, str | int]:
        """Return a dictionary mapping member names to their values."""
        return {member: member.value for member in cls.members()}

    @classmethod
    def add_member(cls, name: str, value: str | int) -> Self:
        """Dynamically add a new member to the enum."""
        if isinstance(value, str):
            name = cls._encode_name(name).upper()
            value = name.lower()
        extend_enum(cls, name, value)  # pyright: ignore[reportCallIssue, reportUnknownVariableType]
        return cls(value)


def _get_parent_frame() -> FrameType:
    """Get the parent frame of the caller."""
    return _sys._getframe(2)  # pyright: ignore[reportPrivateUsage]


type Name = LiteralStringT


class Sentinel:
    """Create a unique sentinel object.
    ...
    """

    _name: Name
    _repr: str
    _module_name: str

    def __new__(cls, name: Name, repr_: str | None = None, module_name: str | None = None) -> Self:
        """Create a new sentinel."""
        # sourcery skip: avoid-builtin-shadow
        name = name.strip()
        repr_ = str(repr_) if repr_ else f"<Sentinel<{name.split('.')[-1]}>>"
        if not module_name:
            parent_frame = _get_parent_frame()
            module_name = (
                parent_frame.f_globals.get("__name__", "__main__") if parent_frame else __name__
            )

        # Include the class's module and fully qualified name in the
        # registry key to support sub-classing.
        registry_key = _sys.intern(f"{cls.__module__}-{cls.__qualname__}-{module_name}-{name}")
        sentinel: Sentinel | None = _registry.get(registry_key)
        if sentinel is not None:
            return cast(Self, sentinel)
        sentinel = super().__new__(cls)
        sentinel._name = name
        sentinel._repr = repr_
        sentinel._module_name = module_name or __name__
        with _lock:
            return cast(Self, _registry.setdefault(registry_key, sentinel))

    def __init__(
        self, name: Name, repr_: str | None = None, module_name: str | None = None
    ) -> None:
        """Initialize a new sentinel."""
        self._name = name
        self._repr = repr_ or f"<Sentinel<{name.split('.')[-1]}>>"
        self._module_name = module_name  # pyright: ignore[reportAttributeAccessIssue]

    @classmethod
    def __call__(cls, name: Name, repr_: str | None = None, module_name: str | None = None) -> Self:
        """Create a new sentinel."""
        return cls(name, repr_, module_name)

    def __str__(self) -> str:
        """Return a string representation of the sentinel."""
        return self._name

    def __repr__(self) -> str:
        """Return a string representation of the sentinel."""
        return self._repr

    def __reduce__(self) -> tuple[type[Self], tuple[str, str, str]]:
        """Return state information for pickling."""
        return (self.__class__, (self._name, self._repr, self._module_name))

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        """Return the Pydantic core schema for the sentinel."""
        return core_schema.with_info_after_validator_function(
            cls._validate,
            core_schema.str_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls._serialize, when_used="json"
            ),
        )

    @staticmethod
    def _validate(value: str, _info: core_schema.ValidationInfo) -> Sentinel:
        """Validate that a value is a sentinel."""
        name, repr_, module_name = value.split(" ")
        return Sentinel(name.strip(), repr_, module_name.strip())

    @staticmethod
    def _serialize(sentinel: Sentinel) -> str:
        """Serialize a sentinel to a string."""
        return f"{sentinel._name} {sentinel._repr} {sentinel._module_name}"


_lock = _Lock()
_registry: dict[str, Sentinel] = {}


class Unset(Sentinel):
    """
    A sentinel value to indicate that a value is unset.
    """


UNSET: Unset = Unset("UNSET")

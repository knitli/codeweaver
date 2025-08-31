# sourcery skip: snake-case-variable-declarations
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""A foundational enum class for the CodeWeaver project for common functionality."""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterator
from enum import Enum, unique
from typing import Self, cast

from aenum import extend_enum  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]


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

    @property
    def aka(self) -> tuple[str, ...] | tuple[int, ...]:
        """Return the alias for the enum member, if one exists."""
        if isinstance(self.value, str):
            baseline_variations = {
                val.lower()
                for val in (
                    self.value,
                    self.name,
                    self.value.replace("-", "_"),
                    self.name.replace("_", "-"),
                    self.value,
                )
            }
            return tuple(baseline_variations)
        return (self.value,)

    @classmethod
    def aliases(cls) -> dict[str, BaseEnum] | dict[int, BaseEnum]:
        """Optionally provides a way to identify alternate names for a member, used in string conversion and identification."""
        keys = {alias: member for member in cls for alias in member.aka if member}
        return {k: v for k, v in keys.items() if k and v}  # pyright: ignore[reportReturnType]

    @classmethod
    def from_string(cls, value: str) -> BaseEnum:
        """Convert a string to the corresponding enum member."""
        try:
            if cls._value_type() is int and value.isdigit():
                return cls(int(value))
            normalized_value = cls._encode_name(value).upper()
            cls.__members__: dict[str, type[BaseEnum]]  # noqa: B032
            if normalized_value in cls.__members__:
                return cast(Self, cls.__members__[normalized_value])
            if (aliases := cls.aliases()) and (
                found_member := next(
                    (member for alias, member in aliases.items() if alias == normalized_value)
                )
            ):
                return found_member
        except (KeyError, StopIteration) as e:
            value_parts = cls._deconstruct_string(value)
            if found_member := next(
                (member for member in cls if cls._deconstruct_string(member.name) == value_parts),
                None,
            ):
                return found_member
            raise ValueError(f"{value} is not a valid {cls.__qualname__} member") from e
        raise ValueError(f"{value} is not a valid {cls.__qualname__} member")

    @staticmethod
    def _encode_name(value: str) -> str:
        """
        Encode a string for use as an enum member name.

        Provides a fully reversible encoding to normalize enum members and values. Doesn't handle all possible cases (by a long shot), but works for what we need without harming readability.
        """
        if value.lower() == "grok":
            return "x_ai"  # Pydantic-AI uses "grok", but we found that confusing since there's also a `groq` provider, and because it doesn't follow the pattern of using the company name and not the model series names.
        return value.lower().replace("-", "__").replace(":", "___").replace(" ", "____")

    @staticmethod
    def _decode_name(value: str, *, for_pydantic_ai: bool = False) -> str:
        """Decodes an enum member or value into its original form."""
        if for_pydantic_ai and value.lower() == "x_ai":
            return "grok"  # handles the special case where we use "x_ai" for the "grok" provider in Pydantic-AI
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

    @classmethod
    def __iter__(cls) -> Iterator[Self]:
        """Return an iterator over the enum members."""
        yield from cls.__members__.values()

    @classmethod
    def is_member(cls, value: str | int) -> bool:
        """Check if a value is a member of the enum."""
        return (
            ((cls._encode_name(value) if isinstance(value, str) else value) in cls.values())
            or (value == "grok")
            or value == "x_ai"
            or value == "hf-inference"
            or value in cls.aliases()
            or (
                isinstance(value, str)
                and any(
                    cls._deconstruct_string(member.name.lower()) == cls._deconstruct_string(value)
                    for member in cls
                )
            )
        )

    @property
    def value_type(self) -> type[int | str]:
        """Return the type of the enum member's value."""
        return type(self)._value_type()

    @property
    def as_variable(self) -> str:
        """Return the string representation of the enum member as a variable name."""
        return self.value if self.value_type is str else str(self.value)

    @classmethod
    def members(cls) -> Generator[Self]:
        """Return all members of the enum as a tuple."""
        yield from cls.__members__.values()

    @classmethod
    def values(cls) -> Generator[str | int]:
        """Return all enum member names as a tuple."""
        yield from (member.value for member in cls.members())

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
            value = cls._encode_name(value).lower()
        extend_enum(cls, cls._encode_name(name).upper(), value)  # pyright: ignore[reportCallIssue, reportUnknownVariableType]
        return cls(value)

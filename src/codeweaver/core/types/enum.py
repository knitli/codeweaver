# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Base enum classes for the CodeWeaver project."""

from __future__ import annotations

import contextlib

from collections.abc import Callable, Generator, Iterator, Mapping, Sequence
from enum import Enum, auto, unique
from functools import cached_property
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Any, Self, cast, override

import textcase

from aenum import extend_enum  # type: ignore
from pydantic import Field, computed_field
from pydantic.dataclasses import dataclass

from codeweaver.core.types.models import DATACLASS_CONFIG, DataclassSerializationMixin


if TYPE_CHECKING:
    from codeweaver.core.types.aliases import FilteredKeyT


type EnumExtend = Callable[[Enum, str], Enum]
extend_enum: EnumExtend = extend_enum


# ================================================
# *          Base Enum Classes
# ================================================


@dataclass(config=DATACLASS_CONFIG, order=True, frozen=True)
class BaseEnumData(DataclassSerializationMixin):
    """A dataclass to hold enum member data.

    `BaseEnumData` provides a standard structure for enum member data, including name, value, aliases, and description. Subclasses can extend this dataclass to include additional fields as needed.
    """

    aliases: Annotated[
        tuple[str, ...],
        Field(description="The aliases for the enum member.", default_factory=tuple, repr=False),
    ]
    _description: (
        Annotated[str | None, Field(description="The description of the enum member.")] | None
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


@unique
class BaseDataclassEnum(Enum):
    """A base enum class for enums with dataclass members. Does not come with its 'type' -- you must define that with `BaseEnumData` and subclass your implementation, like: `class MyDataclassEnum(MyCustomBaseEnumDataDataclass, BaseDataclassEnum): ...`."""

    @staticmethod
    def _multiply_variations(s: str) -> set[str]:
        """Generate multiple variations of a string."""
        return {
            s,
            textcase.upper(s),
            textcase.lower(s),
            textcase.title(s),
            textcase.pascal(s),
            textcase.snake(s),
            textcase.kebab(s),
            textcase.sentence(s),
            textcase.middot(s),
            textcase.camel(s),
        }

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """Return a mapping of telemetry keys to their anonymity conversion methods."""
        raise NotImplementedError("Subclasses must implement _telemetry_keys method.")

    @classmethod
    def aliases(cls) -> MappingProxyType[str, Enum]:
        """Return a mapping of aliases to enum members."""
        values = {
            alias: member
            for member in cls
            for alias in {
                alias
                for name in (
                    member.value._name,
                    member.value._value,
                    *(
                        member.value.aliases
                        if hasattr(member.value, "aliases") and member.value.aliases is not None
                        else ()
                    ),
                )
                for alias in cls._multiply_variations(name)
            }
        }
        return MappingProxyType(values)

    @classmethod
    def from_string(cls, value: str) -> Self:
        """Convert a string to the corresponding enum member."""
        if value in cls.__members__:
            return cls.__members__[value]
        if (aliases := cls.aliases()) and (found_member := aliases.get(value)):
            assert isinstance(found_member, cls)  # noqa: S101
            return found_member
        raise ValueError(f"{value} is not a valid {cls.__qualname__} member")

    @classmethod
    @override
    def _missing_(cls, value: object) -> Enum | None:
        """Handle missing values when converting from string to enum member."""
        if not isinstance(value, str):
            return None
        with contextlib.suppress(ValueError):
            return cls.from_string(value)
        return None

    @classmethod
    def members(cls) -> Generator[Self]:
        """Return all members of the enum as a tuple."""
        yield from cls

    @classmethod
    def values(cls) -> Generator[BaseEnumData]:
        """Return all enum member values as a tuple."""
        yield from cls._value2member_map_

    @classmethod
    def __len__(cls) -> int:
        """Return the number of members in the enum."""
        return len(cls.__members__)

    @computed_field
    @property
    def description(self) -> str | None:
        """Return the description of the enum member."""
        return self.value._description if hasattr(self.value, "_description") else None

    @computed_field
    @property
    def variable(self) -> str:
        """Return the string representation of the enum member as a variable name."""
        return (
            textcase.snake(self.value._value)
            if hasattr(self.value, "_value")
            else textcase.snake(self.name)
        )

    @computed_field
    @property
    def as_title(self) -> str:
        """Return the title-cased representation of the enum member."""
        return textcase.title(self.name)

    @classmethod
    def add_member(cls, name: str, value: BaseEnumData) -> Self:
        """Dynamically add a new member to the enum."""
        # The type stub signature is (cls, name, *args, **kwargs), but the function applies a tuple to single args (value -> (value,)). Bottom line: it works fine. This is much more clear.
        extend_enum(cls, textcase.upper(name), value)  # ty: ignore[too-many-positional-arguments]
        return cls(value)


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
            textcase.upper(s),
            textcase.lower(s),
            textcase.title(s),
            textcase.pascal(s),
            textcase.snake(s),
            textcase.kebab(s),
            textcase.sentence(s),
            textcase.middot(s),
            textcase.camel(s),
            *self._encode_name(s),
        }

    @cached_property
    def aka(self) -> tuple[str, ...] | tuple[int, ...]:
        """Return the alias for the enum member, if one exists."""
        if isinstance(self.value, str):
            names: set[str] = {
                self.value,
                self.name,
                self.decoded_value,
                self.decoded_name,
                self.variable,
                self.as_title,
            }
            if hasattr(self, "alias") and (alias := getattr(self, "alias", None)):
                if isinstance(alias, str):
                    names.add(alias)
                elif isinstance(alias, list | tuple):
                    names |= set(alias)  # type: ignore
            names |= {n for name in names.copy() for n in self._multiply_variations(name)}
            return tuple(sorted(names))
        return (self.value, self.name, self.variable, self.as_title)

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
    @override
    def _missing_(cls, value: object) -> Self | None:
        """Handle missing values when converting from string or int to enum member."""
        if not isinstance(value, str | int):
            return None
        with contextlib.suppress(ValueError):
            return cls.from_string(str(value))
        return None

    @classmethod
    def _alias_map(cls) -> MappingProxyType[int, Enum] | MappingProxyType[str, Enum]:
        """Return a mapping of aliases to enum members."""
        if next(iter(cls))._value_type is int:
            return MappingProxyType(cls._value2member_map_)
        alias_map: Mapping[str, Enum] = cls._value2member_map_.copy()
        alias_map.update({
            alias: member for member in cls for alias in member.aka if alias not in alias_map
        })
        return MappingProxyType(alias_map)

    @classmethod
    def aliases(cls) -> MappingProxyType[int, Enum] | MappingProxyType[str, Enum]:
        """Provides a way to identify alternate names for a member, used in string conversion and identification."""
        return cls._alias_map()

    @classmethod
    def from_string(cls, value: str) -> Self:
        # sourcery skip: remove-unnecessary-cast
        """Convert a string to the corresponding enum member. Flexibly handles different cases, dashes vs underscores, and some common variations.

        `from_string` assumes that it's usually getting valid input, so it tries to find a match in several ways before giving up and raising a `ValueError`. We're taking a "people are messy" approach here to make it easier to work with user settings. There are probably some unknown edge cases that could cause problems, such as when two members have very similar names, but we can address those as they arise (for example, if 'JAVA' didn't match on its value or name for some reason (won't happen), then the heuristic here could assign it to "JAVASCRIPT" as a last resort).
        """
        if cls._value_type() is int and str(value).isdigit():
            return cls(int(value))
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
            assert isinstance(found_member, cls)  # noqa: S101
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

        The result isn't very human-friendly, but it's reversible and avoids collisions with common characters. We only use this for internal normalization purposes and as a fallback -- users should never see these encoded values.
        """
        return value.lower().replace("-", "__").replace(":", "___").replace(" ", "____")

    @staticmethod
    def _decode_name(value: str) -> str:
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
        # When comparing with another enum, extract its value
        other_value = other.value if isinstance(other, self.__class__) else other
        return self.value < other_value

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
    def variable(self) -> str:
        """Return the string representation of the enum member as a variable name."""
        return textcase.snake(self.value) if self.value_type is str else textcase.snake(self.name)

    @property
    def as_title(self) -> str:
        """Return the title-cased representation of the enum member."""
        return textcase.title(self.value) if self.value_type is str else textcase.title(self.name)

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
        # the signature here is (cls, name, *args, **kwargs), but the function applies a tuple to single args (value -> (value,)). Bottom line: it works fine. This is much more clear.
        extend_enum(cls, name, value)  # ty: ignore[too-many-positional-arguments]
        return cls(value)

    def serialize_for_cli(self) -> str:
        """Serialize the enum member for CLI display."""
        return f"{self.as_title})"


type FilteredCallable = Callable[[Any], bool] | Callable[[Any], int] | Callable[[], None]
type FilteredReturn = bool | int | dict[Any, int] | None


def _hash_it(value: Any) -> int:
    """Hash a value using Blake3 and return as integer."""
    from codeweaver.core.stores import get_blake_hash

    # get_blake_hash already returns the hex digest string
    hash_hex = get_blake_hash(str(value))
    # Convert to int for anonymized but consistent representation
    return int(hash_hex, 16)


class AnonymityConversion(BaseEnum):
    """Enumeration of anonymity conversion methods for telemetry data.

    These methods define how telemetry data should be anonymized or aggregated
    to protect user privacy. Only applies to filtered fields.
    """

    BOOLEAN = auto()
    """Convert to boolean presence/absence."""
    COUNT = auto()
    """Convert to count of occurrences."""
    DISTRIBUTION = auto()
    """Convert to distribution of values."""
    AGGREGATE = auto()
    """Aggregate values."""
    HASH = auto()
    """Hash values for anonymity."""
    TEXT_COUNT = auto()
    """Convert text to count of characters."""

    FORBIDDEN = auto()

    def filtered(self, values: Any) -> FilteredReturn:
        """Process values according to the anonymity conversion method."""
        functions: MappingProxyType[AnonymityConversion, FilteredCallable] = MappingProxyType({
            AnonymityConversion.BOOLEAN: lambda v: bool(v),
            AnonymityConversion.COUNT: lambda v: len(v) if isinstance(v, list) else 1,
            AnonymityConversion.DISTRIBUTION: lambda v: {item: v.count(item) for item in set(v)}  # type: ignore
            if (isinstance(v, Sequence) and not isinstance(v, str))
            else {v: 1},  # type: ignore
            AnonymityConversion.AGGREGATE: lambda v: sum(v) if isinstance(v, list) else v,  # type: ignore
            AnonymityConversion.HASH: lambda v: _hash_it(v),
            AnonymityConversion.TEXT_COUNT: lambda v: len(v) if isinstance(v, str) else 0,
            AnonymityConversion.FORBIDDEN: lambda v: None,  # Accept value but return None
        })
        return functions.get(self, lambda v: v)(values)


__all__ = ("AnonymityConversion", "BaseDataclassEnum", "BaseEnum", "BaseEnumData")

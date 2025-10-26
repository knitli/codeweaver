# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Defines a unique sentinel object for use as a default value in function arguments and other scenarios."""

from __future__ import annotations

import sys as _sys

from threading import Lock as _Lock
from types import FrameType
from typing import Self, cast

from pydantic_core import core_schema

from codeweaver.core.types.aliases import LiteralStringT, SentinelName
from codeweaver.core.types.models import BasedModel


def _get_parent_frame() -> FrameType:
    """Get the parent frame of the caller."""
    return _sys._getframe(2)  # pyright: ignore[reportPrivateUsage]


_lock = _Lock()
_registry: dict[SentinelName, Sentinel] = {}


class Sentinel(BasedModel):
    """Create a unique sentinel object.
    ...
    """

    _name: SentinelName
    _repr: str
    _module_name: str

    def __new__(
        cls, name: SentinelName, repr_: str | None = None, module_name: str | None = None
    ) -> Self:
        """Create a new ."""
        # sourcery skip: avoid-builtin-shadow
        name = SentinelName(name.strip())
        repr_ = str(repr_) if repr_ else f"<<{name.split('.')[-1]}>>"
        if not module_name:
            parent_frame = _get_parent_frame()
            module_name = (
                parent_frame.f_globals.get("__name__", "__main__") if parent_frame else __name__
            )

        # Include the class's module and fully qualified name in the
        # registry key to support sub-classing.
        registry_key = SentinelName(
            _sys.intern(f"{cls.__module__}-{cls.__qualname__}-{module_name}-{name}")  # type: ignore
        )
        existing: Sentinel | None = _registry.get(registry_key)
        if existing is not None:
            return cast(Self, existing)
        existing = super().__new__(cls)
        existing._name = name
        existing._repr = repr_
        existing._module_name = module_name or __name__
        with _lock:
            return cast(Self, _registry.setdefault(registry_key, existing))

    def __init__(
        self, name: SentinelName, repr_: str | None = None, module_name: str | None = None
    ) -> None:
        """Initialize a new ."""
        self._name = name
        self._repr = repr_ or f"<<{name.split('.')[-1]}>>"
        self._module_name = module_name  # pyright: ignore[reportAttributeAccessIssue]

    @classmethod
    def __call__(
        cls, name: SentinelName, repr_: str | None = None, module_name: str | None = None
    ) -> Self:
        """Create a new ."""
        return cls(name, repr_, module_name)

    def __str__(self) -> str:
        """Return a string representation of the ."""
        return self._name

    def __repr__(self) -> str:
        """Return a string representation of the ."""
        return self._repr

    def __reduce__(self) -> tuple[type[Self], tuple[str, str, str]]:
        """Return state information for pickling."""
        return (self.__class__, (self._name, self._repr, self._module_name))

    def __hash__(self) -> int:
        """Return the hash of the ."""
        return hash((self._name, self._module_name))

    @staticmethod
    def _validate(value: str, _info: core_schema.ValidationInfo) -> tuple[LiteralStringT, str, str]:
        """Validate that a value is a ."""
        name, repr_, module_name = value.split(" ")
        return (cast(LiteralStringT, name.strip()), repr_, module_name.strip())

    @staticmethod
    def _serialize(existing: Sentinel) -> str:
        """Serialize a Sentinel to a string."""
        return f"{existing._name} {existing._repr} {existing._module_name}"

    def _telemetry_keys(self) -> None:
        return None


class Unset:
    """
    A sentinel value to indicate that a value is unset.
    """


UNSET: Unset = Unset()


__all__ = ("UNSET", "Sentinel", "SentinelName", "Unset")

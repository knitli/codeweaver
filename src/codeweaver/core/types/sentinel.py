# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Defines a unique sentinel object for use as a default value in function arguments and other scenarios."""

from __future__ import annotations

import sys as _sys

from collections.abc import Callable
from threading import Lock as _Lock
from types import FrameType
from typing import Self, cast

from pydantic import ConfigDict
from pydantic_core import core_schema

from codeweaver.core.types.aliases import LiteralStringT, SentinelName, SentinelNameT
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

    model_config = BasedModel.model_config | ConfigDict(frozen=True)

    name: SentinelName
    module_name: str

    def __new__(cls, name: SentinelName | None = None, module_name: str | None = None) -> Self:
        """Create a new ."""
        # sourcery skip: avoid-builtin-shadow
        name = SentinelName(name or cast(LiteralStringT, type(cls).__name__.upper()).strip())
        module_name = module_name or (
            cls.module_name if hasattr(cls, "module_name") else cls._get_module_name_generator()()
        )

        # Include the class's module and fully qualified name in the
        # registry key to support sub-classing.
        registry_key = SentinelName(
            _sys.intern(f"{cls.__module__}-{cls.__qualname__}-{module_name}-{name}")  # type: ignore
        )
        existing: Sentinel | None = _registry.get(registry_key)
        if existing is not None:
            return cast(Self, existing)
        newcls = super().__new__(cls)
        type(newcls).name = name
        type(newcls).module_name = module_name or __name__
        with _lock:
            return cast(Self, _registry.setdefault(registry_key, newcls))

    def __str__(self) -> str:
        """Return a string representation of the sentinel."""
        return self.name

    def __repr__(self) -> str:
        """Return a string representation of the sentinel."""
        return f"{type(self).__name__}(name={self.name}, module_name={self.module_name})"

    def __reduce__(self) -> tuple[type[Self], tuple[str, str]]:
        """Return state information for pickling."""
        return (self.__class__, (self.name, self.module_name))

    def __hash__(self) -> int:
        """Return the hash of the sentinel."""
        return hash((self.name, self.module_name))

    @staticmethod
    def _get_module_name_generator() -> Callable[[], str]:
        """Get a generator function that returns the module name of the caller."""

        def generator() -> str:
            parent_frame = _get_parent_frame()
            if parent_frame and (module_name := parent_frame.f_globals.get("__name__", None)):
                return module_name
            return __name__

        return generator

    @staticmethod
    def _validate(value: str, _info: core_schema.ValidationInfo) -> tuple[SentinelNameT, str, str]:
        """Validate that a value is a sentinel."""
        name, repr_, module_name = value.split(" ")
        return SentinelName(cast(LiteralStringT, name.strip())), repr_, module_name.strip()

    @staticmethod
    def _serialize(existing: Sentinel) -> str:
        """Serialize a Sentinel to a string."""
        return f"{existing.name} {existing.module_name}"

    def _telemetry_keys(self) -> None:
        return None


class Unset(Sentinel):
    """
    A sentinel value to indicate that a value is unset.
    """

    def __init__(self, name: SentinelName | None = None, module_name: str | None = None) -> None:
        """Initialize the UNSET sentinel."""
        super().__init__(
            name=name or SentinelName("UNSET"),
            module_name=module_name or Sentinel._get_module_name_generator()(),
        )


UNSET: Unset = Unset()


__all__ = ("UNSET", "Sentinel", "SentinelName", "Unset")

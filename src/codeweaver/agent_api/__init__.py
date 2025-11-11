# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Pydantic models for CodeWeaver."""

# re-export pydantic-ai models for codeweaver
from __future__ import annotations

from functools import cache
from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.agent_api.find_code import find_code


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "find_code": (__spec__.parent, "find_code")
})


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the agent_api package."""
    if name in _dynamic_imports:
        module_name, submodule_name = _dynamic_imports[name]
        module = import_module(f"{module_name}.{submodule_name}")
        result = getattr(module, name)
        globals()[name] = result  # Cache in globals for future access
        return result
    if globals().get(name) is not None:
        return globals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")


@cache
def get_user_agent() -> str:
    """Get the user agent string for CodeWeaver."""
    from codeweaver import __version__

    return f"CodeWeaver/{__version__}"


__all__ = ("find_code", "get_user_agent")


def __dir__() -> list[str]:
    return list(__all__)

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""FastMCP middleware for CodeWeaver."""

from __future__ import annotations

from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.middleware.statistics import StatisticsMiddleware

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "StatisticsMiddleware": (__spec__.parent, "statistics")
})


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the middleware package."""
    if name in _dynamic_imports:
        module_name, submodule_name = _dynamic_imports[name]
        module = import_module(f"{module_name}.{submodule_name}")
        result = getattr(module, name)
        globals()[name] = result  # Cache in globals for future access
        return result
    if globals().get(name) is not None:
        return globals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = ("StatisticsMiddleware",)


def __dir__() -> list[str]:
    """List available attributes for the middleware package."""
    return list(__all__)

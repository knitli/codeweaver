# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Type definitions for CodeWeaver's DI system."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Protocol


class DependencyProvider[T](Protocol):
    """Protocol for dependency providers (factories)."""

    async def __call__(self) -> T | Awaitable[T]:
        """Resolve the dependency."""
        ...


class ComponentLifecycle(Protocol):
    """Protocol for components with lifecycle hooks."""

    async def startup(self) -> None:
        """Called when the component starts."""
        ...

    async def shutdown(self) -> None:
        """Called when the component stops."""
        ...


__all__ = ("ComponentLifecycle", "DependencyProvider")

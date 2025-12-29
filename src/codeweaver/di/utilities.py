# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Utility functions for CodeWeaver's DI system."""

from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")


_providers: dict[type, Callable] = {}


def provider[Cls: T](cls: type[Cls]) -> Callable[[Callable[..., Cls]], Callable[..., Cls]]:
    """Decorator that registers a function as the provider for a type."""

    def decorator(fn: Callable[..., Cls]) -> Callable[..., Cls]:
        _providers[cls] = fn
        return fn

    return decorator


def get_provider[T](cls: type[T]) -> Callable[..., T]:
    """Get the registered provider for a type."""
    if cls not in _providers:
        raise KeyError(f"No provider registered for type {cls}")
    return _providers[cls]


def provider_bridge[T](cls: type[T]) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Alias for the provider decorator."""
    return provider(cls)


__all__ = ("get_provider", "provider")

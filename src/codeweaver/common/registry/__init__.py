# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Registry package for CodeWeaver common components. This entrypoint exposes the main registry classes and types. The package internals are not for public use."""

from __future__ import annotations

from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    # Import everything for IDE and type checker support
    # These imports are never executed at runtime, only during type checking
    from codeweaver.common.registry.models import ModelRegistry, get_model_registry
    from codeweaver.common.registry.provider import ProviderRegistry, get_provider_registry
    from codeweaver.common.registry.services import ServicesRegistry, get_services_registry
    from codeweaver.common.registry.types import Feature, ServiceCard, ServiceCardDict, ServiceName


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "Feature": (__spec__.parent, "types"),
    "ModelRegistry": (__spec__.parent, "models"),
    "ProviderRegistry": (__spec__.parent, "provider"),
    "ServiceCard": (__spec__.parent, "types"),
    "ServiceCardDict": (__spec__.parent, "types"),
    "ServiceName": (__spec__.parent, "types"),
    "ServicesRegistry": (__spec__.parent, "services"),
    "get_model_registry": (__spec__.parent, "models"),
    "get_provider_registry": (__spec__.parent, "provider"),
    "get_services_registry": (__spec__.parent, "services"),
})


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the registry package."""
    if name in _dynamic_imports:
        module_name, submodule_name = _dynamic_imports[name]
        module = import_module(f"{module_name}.{submodule_name}")
        result = getattr(module, name)
        globals()[name] = result  # Cache in globals for future access
        return result
    if globals().get(name) is not None:
        return globals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = [
    "Feature",
    "ModelRegistry",
    "ProviderRegistry",
    "ServiceCard",
    "ServiceCardDict",
    "ServiceName",
    "ServicesRegistry",
    "get_model_registry",
    "get_provider_registry",
    "get_services_registry",
]


def __dir__() -> list[str]:
    return list(__all__)

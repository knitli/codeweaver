# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Provider environment variable registry.

This package provides a declarative registry system for provider environment variables,
replacing the previous match statement-based approach with lightweight frozen dataclasses.

Main components:
- EnvVarConfig: Individual environment variable configuration
- ProviderEnvConfig: Complete provider configuration
- ProviderEnvRegistry: Central registry with lazy loading
- Builder functions: Composable helpers for common patterns

This package is part of the providers package and depends on core.
"""

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core.utils.lazy_importer import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.providers.env_registry.builders import (
        httpx_env_vars,
        multi_client_provider,
        openai_compatible_provider,
        simple_api_key_provider,
    )
    from codeweaver.providers.env_registry.models import EnvVarConfig, ProviderEnvConfig
    from codeweaver.providers.env_registry.registry import ProviderEnvRegistry


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "EnvVarConfig": (__spec__.parent, "models"),
    "ProviderEnvConfig": (__spec__.parent, "models"),
    "ProviderEnvRegistry": (__spec__.parent, "registry"),
    "httpx_env_vars": (__spec__.parent, "builders"),
    "multi_client_provider": (__spec__.parent, "builders"),
    "openai_compatible_provider": (__spec__.parent, "builders"),
    "simple_api_key_provider": (__spec__.parent, "builders"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = [
    "EnvVarConfig",
    "ProviderEnvConfig",
    "ProviderEnvRegistry",
    "httpx_env_vars",
    "multi_client_provider",
    "openai_compatible_provider",
    "simple_api_key_provider",
]


def __dir__() -> list[str]:
    return list(__all__)

# SPDX-FileCopyrightText: 2026 Knitli Inc.
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

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.providers.env_registry.builders import (
        httpx_env_vars,
        multi_client_provider,
        openai_compatible_provider,
        simple_api_key_provider,
    )
    from codeweaver.providers.env_registry.conversion import (
        env_var_config_to_info,
        get_provider_configs,
        get_provider_env_vars_from_registry,
        provider_env_config_to_vars,
    )
    from codeweaver.providers.env_registry.definitions import MappingProxyType
    from codeweaver.providers.env_registry.models import EnvVarConfig, ProviderEnvConfig
    from codeweaver.providers.env_registry.registry import ProviderEnvRegistry

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "EnvVarConfig": (__spec__.parent, "models"),
    "MappingProxyType": (__spec__.parent, "definitions"),
    "ProviderEnvConfig": (__spec__.parent, "models"),
    "ProviderEnvRegistry": (__spec__.parent, "registry"),
    "env_var_config_to_info": (__spec__.parent, "conversion"),
    "get_provider_configs": (__spec__.parent, "conversion"),
    "get_provider_env_vars_from_registry": (__spec__.parent, "conversion"),
    "httpx_env_vars": (__spec__.parent, "builders"),
    "multi_client_provider": (__spec__.parent, "builders"),
    "openai_compatible_provider": (__spec__.parent, "builders"),
    "provider_env_config_to_vars": (__spec__.parent, "conversion"),
    "simple_api_key_provider": (__spec__.parent, "builders"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "EnvVarConfig",
    "MappingProxyType",
    "ProviderEnvConfig",
    "ProviderEnvRegistry",
    "env_var_config_to_info",
    "get_provider_configs",
    "get_provider_env_vars_from_registry",
    "httpx_env_vars",
    "multi_client_provider",
    "openai_compatible_provider",
    "provider_env_config_to_vars",
    "simple_api_key_provider",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)

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
    from codeweaver.providers.env_registry.definitions.cloud_platforms import AZURE, HEROKU, VERCEL
    from codeweaver.providers.env_registry.definitions.openai_compatible import (
        ALIBABA,
        CEREBRAS,
        DEEPSEEK,
        FIREWORKS,
        GITHUB,
        GROQ,
        LITELLM,
        MOONSHOT,
        MORPH,
        NEBIUS,
        OLLAMA,
        OPENAI,
        OPENROUTER,
        OVHCLOUD,
        PERPLEXITY,
        SAMBANOVA,
        TOGETHER,
    )
    from codeweaver.providers.env_registry.definitions.specialized import (
        ANTHROPIC,
        BEDROCK,
        COHERE,
        EXA,
        GOOGLE,
        HUGGINGFACE_INFERENCE,
        MISTRAL,
        PYDANTIC_GATEWAY,
        QDRANT,
        TAVILY,
        VOYAGE,
        X_AI,
    )
    from codeweaver.providers.env_registry.models import EnvVarConfig, ProviderEnvConfig
    from codeweaver.providers.env_registry.registry import ProviderEnvRegistry

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "ALIBABA": (__spec__.parent, "definitions.openai_compatible"),
    "ANTHROPIC": (__spec__.parent, "definitions.specialized"),
    "AZURE": (__spec__.parent, "definitions.cloud_platforms"),
    "BEDROCK": (__spec__.parent, "definitions.specialized"),
    "CEREBRAS": (__spec__.parent, "definitions.openai_compatible"),
    "COHERE": (__spec__.parent, "definitions.specialized"),
    "DEEPSEEK": (__spec__.parent, "definitions.openai_compatible"),
    "EXA": (__spec__.parent, "definitions.specialized"),
    "FIREWORKS": (__spec__.parent, "definitions.openai_compatible"),
    "GITHUB": (__spec__.parent, "definitions.openai_compatible"),
    "GOOGLE": (__spec__.parent, "definitions.specialized"),
    "GROQ": (__spec__.parent, "definitions.openai_compatible"),
    "HEROKU": (__spec__.parent, "definitions.cloud_platforms"),
    "HUGGINGFACE_INFERENCE": (__spec__.parent, "definitions.specialized"),
    "LITELLM": (__spec__.parent, "definitions.openai_compatible"),
    "MISTRAL": (__spec__.parent, "definitions.specialized"),
    "MOONSHOT": (__spec__.parent, "definitions.openai_compatible"),
    "MORPH": (__spec__.parent, "definitions.openai_compatible"),
    "NEBIUS": (__spec__.parent, "definitions.openai_compatible"),
    "OLLAMA": (__spec__.parent, "definitions.openai_compatible"),
    "OPENAI": (__spec__.parent, "definitions.openai_compatible"),
    "OPENROUTER": (__spec__.parent, "definitions.openai_compatible"),
    "OVHCLOUD": (__spec__.parent, "definitions.openai_compatible"),
    "PERPLEXITY": (__spec__.parent, "definitions.openai_compatible"),
    "PYDANTIC_GATEWAY": (__spec__.parent, "definitions.specialized"),
    "QDRANT": (__spec__.parent, "definitions.specialized"),
    "SAMBANOVA": (__spec__.parent, "definitions.openai_compatible"),
    "TAVILY": (__spec__.parent, "definitions.specialized"),
    "TOGETHER": (__spec__.parent, "definitions.openai_compatible"),
    "VERCEL": (__spec__.parent, "definitions.cloud_platforms"),
    "VOYAGE": (__spec__.parent, "definitions.specialized"),
    "X_AI": (__spec__.parent, "definitions.specialized"),
    "EnvVarConfig": (__spec__.parent, "models"),
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
    "ALIBABA",
    "ANTHROPIC",
    "AZURE",
    "BEDROCK",
    "CEREBRAS",
    "COHERE",
    "DEEPSEEK",
    "EXA",
    "FIREWORKS",
    "GITHUB",
    "GOOGLE",
    "GROQ",
    "HEROKU",
    "HUGGINGFACE_INFERENCE",
    "LITELLM",
    "MISTRAL",
    "MOONSHOT",
    "MORPH",
    "NEBIUS",
    "OLLAMA",
    "OPENAI",
    "OPENROUTER",
    "OVHCLOUD",
    "PERPLEXITY",
    "PYDANTIC_GATEWAY",
    "QDRANT",
    "SAMBANOVA",
    "TAVILY",
    "TOGETHER",
    "VERCEL",
    "VOYAGE",
    "X_AI",
    "EnvVarConfig",
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

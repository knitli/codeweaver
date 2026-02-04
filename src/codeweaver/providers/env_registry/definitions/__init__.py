# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Provider environment variable definitions.

Auto-exports all provider configurations for registry discovery.

This module serves as a central collection point for all provider definitions.
The registry will automatically discover and register any uppercase module-level
variables that are ProviderEnvConfig instances or lists of ProviderEnvConfig.

Organization:
- openai_compatible.py: ~15 providers using OpenAI SDK
- cloud_platforms.py: Multi-client providers (Azure, Heroku, Vercel)
- specialized.py: Providers with unique configurations (Qdrant, Bedrock, etc.)
"""

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core.utils.lazy_importer import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.providers.env_registry.definitions.openai_compatible import (
        CEREBRAS,
        DEEPSEEK,
        FIREWORKS,
        GROQ,
        MOONSHOT,
        MORPH,
        NEBIUS,
        OPENAI,
        OPENROUTER,
        OVHCLOUD,
        SAMBANOVA,
        TOGETHER,
    )


# Phase 2-3: OpenAI-compatible providers (12 providers)
_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType(
    {
        "OPENAI": ("codeweaver.providers.env_registry.definitions", "openai_compatible"),
        "DEEPSEEK": ("codeweaver.providers.env_registry.definitions", "openai_compatible"),
        "FIREWORKS": ("codeweaver.providers.env_registry.definitions", "openai_compatible"),
        "TOGETHER": ("codeweaver.providers.env_registry.definitions", "openai_compatible"),
        "CEREBRAS": ("codeweaver.providers.env_registry.definitions", "openai_compatible"),
        "MOONSHOT": ("codeweaver.providers.env_registry.definitions", "openai_compatible"),
        "MORPH": ("codeweaver.providers.env_registry.definitions", "openai_compatible"),
        "NEBIUS": ("codeweaver.providers.env_registry.definitions", "openai_compatible"),
        "OPENROUTER": ("codeweaver.providers.env_registry.definitions", "openai_compatible"),
        "OVHCLOUD": ("codeweaver.providers.env_registry.definitions", "openai_compatible"),
        "SAMBANOVA": ("codeweaver.providers.env_registry.definitions", "openai_compatible"),
        "GROQ": ("codeweaver.providers.env_registry.definitions", "openai_compatible"),
    }
)

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

# Export explicitly for clarity (optional, but helpful for IDE)
# Phase 2-3: OpenAI-compatible providers (12 providers)
__all__: tuple[str, ...] = (
    "CEREBRAS",
    "DEEPSEEK",
    "FIREWORKS",
    "GROQ",
    "MOONSHOT",
    "MORPH",
    "NEBIUS",
    "OPENAI",
    "OPENROUTER",
    "OVHCLOUD",
    "SAMBANOVA",
    "TOGETHER",
)


def __dir__() -> list[str]:
    """Custom dir() implementation to list all provider definitions."""
    return list(__all__)

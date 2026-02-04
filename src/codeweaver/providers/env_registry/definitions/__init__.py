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
        X_AI,
    )
    from codeweaver.providers.env_registry.definitions.specialized import (
        ANTHROPIC,
        BEDROCK,
        COHERE,
        GOOGLE,
        HUGGINGFACE_INFERENCE,
        MISTRAL,
        PYDANTIC_GATEWAY,
        QDRANT,
        TAVILY,
        VOYAGE,
    )


# Phase 2-4: OpenAI-compatible providers (18 providers - complete)
# Phase 5: Cloud platforms (3 providers - complete)
# Phase 6: Specialized providers (10 providers - complete)
_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType(
    {
        # OpenAI-compatible providers
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
        "ALIBABA": ("codeweaver.providers.env_registry.definitions", "openai_compatible"),
        "GITHUB": ("codeweaver.providers.env_registry.definitions", "openai_compatible"),
        "LITELLM": ("codeweaver.providers.env_registry.definitions", "openai_compatible"),
        "OLLAMA": ("codeweaver.providers.env_registry.definitions", "openai_compatible"),
        "PERPLEXITY": ("codeweaver.providers.env_registry.definitions", "openai_compatible"),
        "X_AI": ("codeweaver.providers.env_registry.definitions", "openai_compatible"),
        # Cloud platforms
        "AZURE": ("codeweaver.providers.env_registry.definitions", "cloud_platforms"),
        "HEROKU": ("codeweaver.providers.env_registry.definitions", "cloud_platforms"),
        "VERCEL": ("codeweaver.providers.env_registry.definitions", "cloud_platforms"),
        # Specialized providers
        "VOYAGE": ("codeweaver.providers.env_registry.definitions", "specialized"),
        "ANTHROPIC": ("codeweaver.providers.env_registry.definitions", "specialized"),
        "HUGGINGFACE_INFERENCE": ("codeweaver.providers.env_registry.definitions", "specialized"),
        "BEDROCK": ("codeweaver.providers.env_registry.definitions", "specialized"),
        "COHERE": ("codeweaver.providers.env_registry.definitions", "specialized"),
        "TAVILY": ("codeweaver.providers.env_registry.definitions", "specialized"),
        "GOOGLE": ("codeweaver.providers.env_registry.definitions", "specialized"),
        "MISTRAL": ("codeweaver.providers.env_registry.definitions", "specialized"),
        "PYDANTIC_GATEWAY": ("codeweaver.providers.env_registry.definitions", "specialized"),
        "QDRANT": ("codeweaver.providers.env_registry.definitions", "specialized"),
    }
)

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

# Export explicitly for clarity (optional, but helpful for IDE)
# Phase 2-4: OpenAI-compatible providers (18 providers - complete)
# Phase 5: Cloud platforms (3 providers - complete)
# Phase 6: Specialized providers (10 providers - complete)
__all__: tuple[str, ...] = (
    # OpenAI-compatible providers
    "ALIBABA",
    # Specialized providers
    "ANTHROPIC",
    # Cloud platforms
    "AZURE",
    # Specialized providers
    "BEDROCK",
    # OpenAI-compatible providers
    "CEREBRAS",
    # Specialized providers
    "COHERE",
    # OpenAI-compatible providers
    "DEEPSEEK",
    "FIREWORKS",
    "GITHUB",
    # Specialized providers
    "GOOGLE",
    # OpenAI-compatible providers
    "GROQ",
    # Cloud platforms
    "HEROKU",
    # Specialized providers
    "HUGGINGFACE_INFERENCE",
    # OpenAI-compatible providers
    "LITELLM",
    # Specialized providers
    "MISTRAL",
    # OpenAI-compatible providers
    "MOONSHOT",
    "MORPH",
    "NEBIUS",
    "OLLAMA",
    "OPENAI",
    "OPENROUTER",
    "OVHCLOUD",
    "PERPLEXITY",
    # Specialized providers
    "PYDANTIC_GATEWAY",
    "QDRANT",
    # OpenAI-compatible providers
    "SAMBANOVA",
    # Specialized providers
    "TAVILY",
    # OpenAI-compatible providers
    "TOGETHER",
    # Cloud platforms
    "VERCEL",
    # Specialized providers
    "VOYAGE",
    # OpenAI-compatible providers
    "X_AI",
)


def __dir__() -> list[str]:
    """Custom dir() implementation to list all provider definitions."""
    return list(__all__)

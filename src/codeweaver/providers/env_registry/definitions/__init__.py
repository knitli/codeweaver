# SPDX-FileCopyrightText: 2026 Knitli Inc.
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

from __future__ import annotations


__all__: tuple[str, ...] = (
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
)

# === MANAGED EXPORTS ===

# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.

from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


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

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "ALIBABA": (__spec__.parent, "openai_compatible"),
    "ANTHROPIC": (__spec__.parent, "specialized"),
    "AZURE": (__spec__.parent, "cloud_platforms"),
    "BEDROCK": (__spec__.parent, "specialized"),
    "CEREBRAS": (__spec__.parent, "openai_compatible"),
    "COHERE": (__spec__.parent, "specialized"),
    "DEEPSEEK": (__spec__.parent, "openai_compatible"),
    "EXA": (__spec__.parent, "specialized"),
    "FIREWORKS": (__spec__.parent, "openai_compatible"),
    "GITHUB": (__spec__.parent, "openai_compatible"),
    "GOOGLE": (__spec__.parent, "specialized"),
    "GROQ": (__spec__.parent, "openai_compatible"),
    "HEROKU": (__spec__.parent, "cloud_platforms"),
    "HUGGINGFACE_INFERENCE": (__spec__.parent, "specialized"),
    "LITELLM": (__spec__.parent, "openai_compatible"),
    "MISTRAL": (__spec__.parent, "specialized"),
    "MOONSHOT": (__spec__.parent, "openai_compatible"),
    "MORPH": (__spec__.parent, "openai_compatible"),
    "NEBIUS": (__spec__.parent, "openai_compatible"),
    "OLLAMA": (__spec__.parent, "openai_compatible"),
    "OPENAI": (__spec__.parent, "openai_compatible"),
    "OPENROUTER": (__spec__.parent, "openai_compatible"),
    "OVHCLOUD": (__spec__.parent, "openai_compatible"),
    "PERPLEXITY": (__spec__.parent, "openai_compatible"),
    "PYDANTIC_GATEWAY": (__spec__.parent, "specialized"),
    "QDRANT": (__spec__.parent, "specialized"),
    "SAMBANOVA": (__spec__.parent, "openai_compatible"),
    "TAVILY": (__spec__.parent, "specialized"),
    "TOGETHER": (__spec__.parent, "openai_compatible"),
    "VERCEL": (__spec__.parent, "cloud_platforms"),
    "VOYAGE": (__spec__.parent, "specialized"),
    "X_AI": (__spec__.parent, "specialized"),
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
    "MappingProxyType",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)

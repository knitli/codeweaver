# Copyright (c) 2024 to present Pydantic Services Inc
# SPDX-License-Identifier: MIT
# Applies to original code in this directory (`src/codeweaver/embedding_providers/`) from `pydantic_ai`.
#
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# applies to new/modified code in this directory (`src/codeweaver/embedding_providers/`)
"""This module re-exports agentic model providers and associated utilities from Pydantic AI."""

from __future__ import annotations

import contextlib

from collections.abc import Generator
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

from lateimport import LateImport, lateimport
from pydantic_ai.providers import Provider as AgentProvider
from pydantic_ai.toolsets import (
    AbstractToolset,
    CombinedToolset,
    ExternalToolset,
    FilteredToolset,
    FunctionToolset,
    PrefixedToolset,
    PreparedToolset,
    RenamedToolset,
    ToolsetTool,
    WrapperToolset,
)

from codeweaver.core.exceptions import ConfigurationError
from codeweaver.core.types import LiteralProviderType


if TYPE_CHECKING:
    from codeweaver.core import Provider


AGENT_PROVIDER_CLASSES: MappingProxyType[Provider, LateImport] = MappingProxyType({
    Provider.ALIBABA: lateimport("pydantic_ai.providers.alibaba", "AlibabaProvider"),
    Provider.ANTHROPIC: lateimport("pydantic_ai.providers.anthropic", "AnthropicProvider"),
    Provider.AZURE: lateimport("pydantic_ai.providers.azure", "AzureProvider"),
    Provider.BEDROCK: lateimport("pydantic_ai.providers.bedrock", "BedrockProvider"),
    Provider.CEREBRAS: lateimport("pydantic_ai.providers.cerebras", "CerebrasProvider"),
    Provider.COHERE: lateimport("pydantic_ai.providers.cohere", "CohereProvider"),
    Provider.DEEPSEEK: lateimport("pydantic_ai.providers.deepseek", "DeepSeekProvider"),
    Provider.FIREWORKS: lateimport("pydantic_ai.providers.fireworks", "FireworksProvider"),
    Provider.GITHUB: lateimport("pydantic_ai.providers.github", "GitHubProvider"),
    Provider.GOOGLE: lateimport("pydantic_ai.providers.google", "GoogleProvider"),
    Provider.GROQ: lateimport("pydantic_ai.providers.groq", "GroqProvider"),
    Provider.HEROKU: lateimport("pydantic_ai.providers.heroku", "HerokuProvider"),
    Provider.HUGGINGFACE_INFERENCE: lateimport(
        "pydantic_ai.providers.huggingface", "HuggingFaceProvider"
    ),
    Provider.LITELLM: lateimport("pydantic_ai.providers.litellm", "LiteLLMProvider"),
    Provider.MISTRAL: lateimport("pydantic_ai.providers.mistral", "MistralProvider"),
    Provider.MOONSHOT: lateimport("pydantic_ai.providers.moonshotai", "MoonshotAIProvider"),
    Provider.NEBIUS: lateimport("pydantic_ai.providers.nebius", "NebiusProvider"),
    Provider.OLLAMA: lateimport("pydantic_ai.providers.ollama", "OllamaProvider"),
    Provider.OPENAI: lateimport("pydantic_ai.providers.openai", "OpenAIProvider"),
    Provider.OPENROUTER: lateimport("pydantic_ai.providers.openrouter", "OpenRouterProvider"),
    Provider.OVHCLOUD: lateimport("pydantic_ai.providers.ovhcloud", "OVHcloudProvider"),
    Provider.PERPLEXITY: lateimport("pydantic_ai.providers.perplexity", "PerplexityProvider"),
    Provider.TOGETHER: lateimport("pydantic_ai.providers.together", "TogetherProvider"),
    Provider.VERCEL: lateimport("pydantic_ai.providers.vercel", "VercelProvider"),
    Provider.X_AI: lateimport("pydantic_ai.providers.grok", "GrokProvider"),
})
"""Mapping of providers to their agent model provider classes."""


def get_agent_model_provider(provider: LiteralProviderType) -> type[AgentProvider[Any]]:
    # It's long, but it's not complex.
    # sourcery skip: low-code-quality, no-long-functions
    """Get the agent model provider."""
    if isinstance(provider, str):
        from codeweaver.core.types import Provider

        provider: Provider = Provider.from_string(cast(str, provider))

    if provider in AGENT_PROVIDER_CLASSES:
        return AGENT_PROVIDER_CLASSES[provider]._resolve()

    raise ConfigurationError(
        f"Unknown agent provider: {provider}",
        details={
            "provided_provider": str(provider),
            "supported_providers": [p.variable for p in AGENT_PROVIDER_CLASSES],
        },
        suggestions=[
            "Check provider name spelling in configuration",
            "Install required agent provider package",
            "Review supported providers in documentation",
        ],
    )


def infer_agent_provider_class(provider: str | Provider) -> type[AgentProvider[Provider]]:
    """Infer the provider from the provider name."""
    from codeweaver.core import Provider

    if not isinstance(provider, Provider):
        provider = Provider.from_string(provider)
    provider_class: type[AgentProvider[Provider]] = get_agent_model_provider(provider)  # type: ignore
    return provider_class


def load_default_agent_providers() -> Generator[type[AgentProvider[Provider]], None, None]:
    """Load the default providers."""
    from codeweaver.core.types import Provider, ProviderCategory, get_categories

    for provider in Provider:
        if provider == Provider.NOT_SET:
            continue
        categories = get_categories(provider)
        if ProviderCategory.AGENT in categories:
            with contextlib.suppress(ValueError, AttributeError, ImportError):
                if agent_provider := get_agent_model_provider(provider):  # type: ignore
                    yield agent_provider


__all__ = (
    "AGENT_PROVIDER_CLASSES",
    "AbstractToolset",
    "AgentProvider",
    "CombinedToolset",
    "ExternalToolset",
    "FilteredToolset",
    "FunctionToolset",
    "PrefixedToolset",
    "PreparedToolset",
    "RenamedToolset",
    "ToolsetTool",
    "WrapperToolset",
    "get_agent_model_provider",
    "infer_agent_provider_class",
    "load_default_agent_providers",
)

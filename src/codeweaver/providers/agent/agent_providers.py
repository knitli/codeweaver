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
from typing import TYPE_CHECKING, Any

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

from codeweaver.exceptions import ConfigurationError


if TYPE_CHECKING:
    from codeweaver.providers.provider import Provider


def get_agent_model_provider(provider: Provider) -> type[AgentProvider[Any]]:  # noqa: C901
    # It's long, but it's not complex.
    # sourcery skip: low-code-quality, no-long-functions
    """Get the agent model provider."""
    from codeweaver.providers.provider import Provider

    if provider == Provider.OPENAI:
        from pydantic_ai.providers.openai import OpenAIProvider as OpenAIAgentProvider

        return OpenAIAgentProvider
    if provider == Provider.DEEPSEEK:
        from pydantic_ai.providers.deepseek import DeepSeekProvider as DeepSeekAgentProvider

        return DeepSeekAgentProvider
    if provider == Provider.OPENROUTER:
        from pydantic_ai.providers.openrouter import OpenRouterProvider as OpenRouterAgentProvider

        return OpenRouterAgentProvider
    if provider == Provider.VERCEL:
        from pydantic_ai.providers.vercel import VercelProvider as VercelAgentProvider

        return VercelAgentProvider
    if provider == Provider.AZURE:
        from pydantic_ai.providers.azure import AzureProvider as AzureAgentProvider

        return AzureAgentProvider

    # NOTE: We don't test for auth because there are many ways the `boto3.client` can retrieve the credentials.
    if provider == Provider.BEDROCK:
        from pydantic_ai.providers.bedrock import BedrockProvider as BedrockAgentProvider

        return BedrockAgentProvider
    if provider == Provider.GOOGLE:
        from pydantic_ai.providers.google import GoogleProvider as GoogleAgentProvider

        return GoogleAgentProvider
    if provider == Provider.GROQ:
        from pydantic_ai.providers.groq import GroqProvider as GroqAgentProvider

        return GroqAgentProvider
    if provider == Provider.X_AI:
        from pydantic_ai.providers.grok import GrokProvider as GrokAgentProvider

        return GrokAgentProvider
    if provider == Provider.ANTHROPIC:
        from pydantic_ai.providers.anthropic import AnthropicProvider as AnthropicAgentProvider

        return AnthropicAgentProvider
    if provider == Provider.MISTRAL:
        from pydantic_ai.providers.mistral import MistralProvider as MistralAgentProvider

        return MistralAgentProvider
    if provider == Provider.COHERE:
        from pydantic_ai.providers.cohere import CohereProvider as CohereAgentProvider

        return CohereAgentProvider
    if provider == Provider.MOONSHOT:
        from pydantic_ai.providers.moonshotai import MoonshotAIProvider as MoonshotAIAgentProvider

        return MoonshotAIAgentProvider
    if provider == Provider.FIREWORKS:
        from pydantic_ai.providers.fireworks import FireworksProvider as FireworksAgentProvider

        return FireworksAgentProvider
    if provider == Provider.TOGETHER:
        from pydantic_ai.providers.together import TogetherProvider as TogetherAgentProvider

        return TogetherAgentProvider
    if provider == Provider.HEROKU:
        from pydantic_ai.providers.heroku import HerokuProvider as HerokuAgentProvider

        return HerokuAgentProvider
    if provider == Provider.HUGGINGFACE_INFERENCE:
        from pydantic_ai.providers.huggingface import (
            HuggingFaceProvider as HuggingFaceAgentProvider,
        )

        return HuggingFaceAgentProvider
    if provider == Provider.GITHUB:
        from pydantic_ai.providers.github import GitHubProvider as GitHubAgentProvider

        return GitHubAgentProvider
    if provider == Provider.OLLAMA:
        from pydantic_ai.providers.ollama import OllamaProvider as OllamaAgentProvider

        return OllamaAgentProvider
    if provider == Provider.LITELLM:
        from pydantic_ai.providers.litellm import LiteLLMProvider as LiteLLMAgentProvider

        return LiteLLMAgentProvider
    if provider == Provider.CEREBRAS:
        from pydantic_ai.providers.cerebras import CerebrasProvider as CerebrasAgentProvider

        return CerebrasAgentProvider

    # Get list of supported agent providers dynamically
    supported_providers = [
        p.variable
        for p in [
            Provider.OPENAI,
            Provider.DEEPSEEK,
            Provider.OPENROUTER,
            Provider.VERCEL,
            Provider.AZURE,
            Provider.BEDROCK,
            Provider.GOOGLE,
            Provider.GROQ,
            Provider.X_AI,
            Provider.ANTHROPIC,
            Provider.MISTRAL,
            Provider.COHERE,
            Provider.MOONSHOT,
            Provider.FIREWORKS,
            Provider.TOGETHER,
            Provider.HEROKU,
            Provider.HUGGINGFACE_INFERENCE,
            Provider.GITHUB,
            Provider.OLLAMA,
            Provider.LITELLM,
            Provider.CEREBRAS,
        ]
    ]

    raise ConfigurationError(
        f"Unknown agent provider: {provider}",
        details={"provided_provider": str(provider), "supported_providers": supported_providers},
        suggestions=[
            "Check provider name spelling in configuration",
            "Install required agent provider package",
            "Review supported providers in documentation",
        ],
    )


def infer_agent_provider_class(provider: str | Provider) -> type[AgentProvider[Provider]]:
    """Infer the provider from the provider name."""
    from codeweaver.providers.provider import Provider

    if not isinstance(provider, Provider):
        provider = Provider.from_string(provider)
    provider_class: type[AgentProvider[Provider]] = get_agent_model_provider(provider)  # type: ignore
    return provider_class


def load_default_agent_providers() -> Generator[type[AgentProvider[Provider]], None, None]:
    """Load the default providers."""
    from codeweaver.providers.capabilities import get_provider_kinds
    from codeweaver.providers.provider import Provider, ProviderKind

    for provider in Provider:
        kinds = get_provider_kinds(provider)  # type: ignore
        if ProviderKind.AGENT in kinds:
            with contextlib.suppress(ValueError, AttributeError, ImportError):
                if agent_provider := get_agent_model_provider(provider):  # type: ignore
                    yield agent_provider


__all__ = (
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

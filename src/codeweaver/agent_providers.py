# Copyright (c) 2024 to present Pydantic Services Inc
# SPDX-License-Identifier: MIT
# Applies to original code in this directory (`src/codeweaver/embedding_providers/`) from `pydantic_ai`.
#
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# applies to new/modified code in this directory (`src/codeweaver/embedding_providers/`)
"""This module re-exports agentic model providers and associated utilities from Pydantic AI."""

from typing import TYPE_CHECKING, Self

from pydantic_ai.providers import Provider as AgentProvider
from pydantic_ai.toolsets import (
    AbstractToolset,
    CombinedToolset,
    DeferredToolset,
    FilteredToolset,
    FunctionToolset,
    PrefixedToolset,
    PreparedToolset,
    RenamedToolset,
    ToolsetTool,
    WrapperToolset,
)


if TYPE_CHECKING:
    from codeweaver._settings import Provider


def get_agent_model_provider(provider: Provider) -> type[AgentProvider[Self]]:  # type: ignore  # noqa: C901
    # It's long, but it's not complex.
    # sourcery skip: low-code-quality, no-long-functions
    """Get the agent model provider."""
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
    # pragma: no cover
    raise ValueError(f"Unknown provider: {provider}")


def infer_agent_provider_class(provider: str | Provider) -> AgentProvider[Provider]:
    """Infer the provider from the provider name."""
    if not isinstance(provider, Provider):
        provider = Provider.from_string(provider)  # pyright: ignore[reportAssignmentType]
    provider_class: type[AgentProvider[Provider]] = get_agent_model_provider(provider)  # type: ignore
    return provider_class()


__all__ = (
    "AbstractToolset",
    "AgentProvider",
    "CombinedToolset",
    "DeferredToolset",
    "FilteredToolset",
    "FunctionToolset",
    "PrefixedToolset",
    "PreparedToolset",
    "RenamedToolset",
    "ToolsetTool",
    "WrapperToolset",
    "get_agent_model_provider",
    "infer_agent_provider_class",
)

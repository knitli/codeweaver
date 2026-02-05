# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""OpenAI-compatible provider definitions.

Providers that use the OpenAI SDK client for their API endpoints.
This includes OpenAI itself and ~15 other providers that follow the same API structure.
"""

from __future__ import annotations

from codeweaver.providers.env_registry.builders import httpx_env_vars, openai_compatible_provider
from codeweaver.providers.env_registry.models import EnvVarConfig, ProviderEnvConfig


# OPENAI - Base provider for OpenAI-compatible services
OPENAI = ProviderEnvConfig(
    provider="openai",
    clients=("openai",),
    note=(
        "These variables are for any OpenAI-compatible service, including OpenAI itself, "
        "Azure OpenAI, and others -- any provider that we use the OpenAI client to connect to."
    ),
    api_key=EnvVarConfig(
        env="OPENAI_API_KEY",
        description=(
            "API key for OpenAI-compatible services (not necessarily an API key *for* OpenAI). "
            "The OpenAI client also requires an API key, even if you don't actually need one for "
            "your provider (like local Ollama). So provide a dummy key if needed."
        ),
        is_secret=True,
        variable_name="api_key",
    ),
    log_level=EnvVarConfig(
        env="OPENAI_LOG",
        description="One of: 'debug', 'info', 'warning', 'error'",
        choices=frozenset({"debug", "info", "warning", "error"}),
    ),
    other=httpx_env_vars()
    | frozenset(
        [
            (
                "organization",
                EnvVarConfig(
                    env="OPENAI_ORG_ID",
                    description="Organization ID for OpenAI.",
                    variable_name="organization",
                ),
            ),
            (
                "project",
                EnvVarConfig(
                    env="OPENAI_PROJECT_ID",
                    description="An openai project id for tracking usage.",
                    variable_name="project",
                ),
            ),
            (
                "webhook_secret",
                EnvVarConfig(
                    env="OPENAI_WEBHOOK_SECRET",
                    description="Webhook secret for verifying incoming webhooks from OpenAI.",
                    is_secret=True,
                    variable_name="webhook_secret",
                ),
            ),
        ]
    ),
)

# DEEPSEEK - OpenAI-compatible provider
DEEPSEEK = openai_compatible_provider(
    "deepseek",
    api_key_env="DEEPSEEK_API_KEY",
    note="These variables are for the DeepSeek service.",
)

# FIREWORKS - OpenAI-compatible provider with custom base URL
FIREWORKS = openai_compatible_provider(
    "fireworks",
    api_key_env="FIREWORKS_API_KEY",
    base_url_env="FIREWORKS_API_URL",
    note="Fireworks AI service.",
)

# TOGETHER - OpenAI-compatible provider
TOGETHER = openai_compatible_provider(
    "together",
    api_key_env="TOGETHER_API_KEY",
    note="These variables are for the Together service.",
)

# CEREBRAS - OpenAI-compatible provider with custom base URL
CEREBRAS = openai_compatible_provider(
    "cerebras",
    api_key_env="CEREBRAS_API_KEY",
    base_url_env="CEREBRAS_API_URL",
    note="Cerebras AI inference service.",
)

# MOONSHOT - OpenAI-compatible provider
MOONSHOT = openai_compatible_provider(
    "moonshot",
    api_key_env="MOONSHOTAI_API_KEY",
    note="These variables are for the Moonshot service.",
)

# MORPH - OpenAI-compatible provider with custom base URL and default
MORPH = openai_compatible_provider(
    "morph",
    api_key_env="MORPH_API_KEY",
    base_url_env="MORPH_API_URL",
    default_url="https://api.morphllm.com/v1",
    note="Morph LLM service.",
)

# NEBIUS - OpenAI-compatible provider with custom base URL
NEBIUS = openai_compatible_provider(
    "nebius",
    api_key_env="NEBIUS_API_KEY",
    base_url_env="NEBIUS_API_URL",
    note="Nebius AI service.",
)

# OPENROUTER - OpenAI-compatible provider
OPENROUTER = openai_compatible_provider(
    "openrouter",
    api_key_env="OPENROUTER_API_KEY",
    note="These variables are for the OpenRouter service.",
)

# OVHCLOUD - OpenAI-compatible provider with custom base URL
OVHCLOUD = openai_compatible_provider(
    "ovhcloud",
    api_key_env="OVHCLOUD_API_KEY",
    base_url_env="OVHCLOUD_API_URL",
    note="OVHCloud AI service.",
)

# SAMBANOVA - OpenAI-compatible provider with custom base URL
SAMBANOVA = openai_compatible_provider(
    "sambanova",
    api_key_env="SAMBANOVA_API_KEY",
    base_url_env="SAMBANOVA_API_URL",
    note="SambaNova AI service.",
)

# GROQ - Multi-client provider (groq and openai)
GROQ = openai_compatible_provider(
    "groq",
    api_key_env="GROQ_API_KEY",
    base_url_env="GROQ_BASE_URL",
    default_url="https://api.groq.com",
    additional_clients=("groq",),
    note="Groq AI service.",
)

# ALIBABA - Simple OpenAI-compatible provider
ALIBABA = openai_compatible_provider(
    "alibaba",
    api_key_env="ALIBABA_API_KEY",
    note="Alibaba Cloud AI service.",
)

# GITHUB - Simple OpenAI-compatible provider
GITHUB = openai_compatible_provider(
    "github",
    api_key_env="GITHUB_TOKEN",
    note="GitHub Models service.",
)

# LITELLM - Simple OpenAI-compatible provider
LITELLM = openai_compatible_provider(
    "litellm",
    api_key_env="LITELLM_API_KEY",
    note="LiteLLM unified API service.",
)

# OLLAMA - Simple OpenAI-compatible provider (local/cloud)
OLLAMA = openai_compatible_provider(
    "ollama",
    api_key_env="OLLAMA_API_KEY",
    note="Ollama local/cloud LLM service.",
)

# PERPLEXITY - Simple OpenAI-compatible provider
PERPLEXITY = openai_compatible_provider(
    "perplexity",
    api_key_env="PERPLEXITY_API_KEY",
    note="Perplexity AI service.",
)

__all__ = (
    "ALIBABA",
    "CEREBRAS",
    "DEEPSEEK",
    "FIREWORKS",
    "GITHUB",
    "GROQ",
    "LITELLM",
    "MOONSHOT",
    "MORPH",
    "NEBIUS",
    "OLLAMA",
    "OPENAI",
    "OPENROUTER",
    "OVHCLOUD",
    "PERPLEXITY",
    "SAMBANOVA",
    "TOGETHER",
)

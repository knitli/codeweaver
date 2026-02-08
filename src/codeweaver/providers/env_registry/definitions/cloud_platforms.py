# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Cloud platform provider definitions.

Providers that offer multi-client services across cloud platforms like Azure, Heroku, and Vercel.
These typically support multiple SDK clients with platform-specific configuration.
"""

from __future__ import annotations

from codeweaver.core.types.env import VariableInfo
from codeweaver.providers.env_registry.builders import httpx_env_vars, multi_client_provider
from codeweaver.providers.env_registry.models import EnvVarConfig, ProviderEnvConfig


# AZURE - Multi-client cloud platform (openai, cohere, anthropic)
_azure_openai = ProviderEnvConfig(
    provider="azure",
    clients=("openai",),
    note="These variables are for the Azure OpenAI service. (OpenAI models on Azure)",
    api_key=EnvVarConfig(
        env="AZURE_OPENAI_API_KEY",
        is_secret=True,
        description="API key for Azure OpenAI service (OpenAI models on Azure)",
        variables=(
            VariableInfo(variable="api_key", dest="client"),
            VariableInfo(variable="api_key", dest="provider_settings"),
        ),
    ),
    endpoint=EnvVarConfig(
        env="AZURE_OPENAI_ENDPOINT",
        description="Endpoint for Azure OpenAI service (OpenAI models on Azure)",
        variables=(
            VariableInfo(variable="base_url", dest="client"),
            VariableInfo(variable="endpoint", dest="provider_settings"),
        ),
    ),
    region=EnvVarConfig(
        env="AZURE_OPENAI_REGION",
        description="Region for Azure OpenAI service (OpenAI models on Azure)",
        variables=(VariableInfo(variable="region_name", dest="provider"),),
    ),
    other=httpx_env_vars(),
    inherits_from="openai",
)

_azure_cohere = ProviderEnvConfig(
    provider="azure",
    clients=("cohere",),
    note="These variables are for the Azure Cohere service.",
    api_key=EnvVarConfig(
        env="AZURE_COHERE_API_KEY",
        is_secret=True,
        description="API key for Azure Cohere service (cohere models on Azure)",
        variable_name="api_key",
    ),
    endpoint=EnvVarConfig(
        env="AZURE_COHERE_ENDPOINT",
        description="Endpoint for Azure Cohere service (cohere models on Azure)",
        variable_name="base_url",
    ),
    region=EnvVarConfig(
        env="AZURE_COHERE_REGION",
        description="Region for Azure Cohere service",
        variable_name="region_name",
    ),
    other=httpx_env_vars(),
)

_azure_anthropic = ProviderEnvConfig(
    provider="azure",
    clients=("anthropic",),
    note="These variables are for the Azure Anthropic service.",
    api_key=EnvVarConfig(
        env="ANTHROPIC_FOUNDRY_API_KEY",
        is_secret=True,
        description="API key for Azure Anthropic service (Anthropic models on Azure)",
        variable_name="api_key",
    ),
    endpoint=EnvVarConfig(
        env="ANTHROPIC_FOUNDRY_BASE_URL",
        description="Endpoint for Azure Anthropic service (Anthropic models on Azure)",
        variable_name="base_url",
    ),
    region=EnvVarConfig(
        env="ANTHROPIC_FOUNDRY_REGION",
        description="Region for Azure Anthropic service",
        variable_name="region_name",
    ),
    other=httpx_env_vars()
    | frozenset([
        (
            "resource",
            EnvVarConfig(
                env="ANTHROPIC_FOUNDRY_RESOURCE",
                description="Resource name for Azure Anthropic service",
                variable_name="resource",
            ),
        )
    ]),
)

AZURE = multi_client_provider("azure", [_azure_openai, _azure_cohere, _azure_anthropic])

# HEROKU - Multi-client platform (openai, cohere)
HEROKU = [
    ProviderEnvConfig(
        provider="heroku",
        clients=("openai", "cohere"),
        note="These variables are for the Heroku service.",
        api_key=EnvVarConfig(
            env="INFERENCE_KEY",
            is_secret=True,
            description="API key for Heroku service",
            variable_name="api_key",
        ),
        host=EnvVarConfig(
            env="INFERENCE_URL", description="Host URL for Heroku service", variable_name="base_url"
        ),
        other=httpx_env_vars()
        | frozenset([
            (
                "model_id",
                EnvVarConfig(
                    env="INFERENCE_MODEL_ID",
                    description="Model ID for Heroku service",
                    variables=(VariableInfo(variable="model", dest="embed"),),
                ),
            )
        ]),
        inherits_from="openai",
    )
]

# VERCEL - Multiple configuration options (API key and OIDC token)
_vercel_api_key = ProviderEnvConfig(
    provider="vercel",
    clients=("openai",),
    note="You may also use the OpenAI-compatible environment variables with Vercel, since it uses the OpenAI client.",
    api_key=EnvVarConfig(
        env="VERCEL_AI_GATEWAY_API_KEY",
        is_secret=True,
        description="API key for Vercel service",
        variable_name="api_key",
    ),
    other=httpx_env_vars(),
    inherits_from="openai",
)

_vercel_oidc = ProviderEnvConfig(
    provider="vercel",
    clients=("openai",),
    note="OIDC token authentication for Vercel service",
    api_key=EnvVarConfig(
        env="VERCEL_OIDC_TOKEN",
        is_secret=True,
        description="OIDC token for Vercel service",
        variable_name="api_key",
    ),
    inherits_from="openai",
)

VERCEL = multi_client_provider("vercel", [_vercel_api_key, _vercel_oidc])

__all__ = ("AZURE", "HEROKU", "VERCEL")

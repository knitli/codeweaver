# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Specialized provider definitions.

Providers with unique SDK clients and specialized configurations.
These providers use their own SDK clients (not OpenAI-compatible) and have
provider-specific environment variable requirements.
"""

from __future__ import annotations

from codeweaver.core.types.env import EnvFormat
from codeweaver.providers.env_registry.builders import httpx_env_vars, simple_api_key_provider
from codeweaver.providers.env_registry.models import EnvVarConfig, ProviderEnvConfig


# VOYAGE - Simple API key provider
VOYAGE = [
    simple_api_key_provider(
        "voyage",
        client="voyage",
        api_key_env="VOYAGE_API_KEY",
        note="These variables are for the Voyage service.",
    )
]

# ANTHROPIC - Multiple authentication methods
ANTHROPIC = [
    ProviderEnvConfig(
        provider="anthropic",
        clients=("anthropic",),
        note="These variables are for the Anthropic service (API key authentication).",
        api_key=EnvVarConfig(
            env="ANTHROPIC_API_KEY",
            is_secret=True,
            description="API key for Anthropic service",
            variable_name="api_key",
        ),
        host=EnvVarConfig(
            env="ANTHROPIC_BASE_URL",
            description="Host URL for Anthropic service",
            variable_name="base_url",
        ),
        other=httpx_env_vars(),
    ),
    ProviderEnvConfig(
        provider="anthropic",
        clients=("anthropic",),
        note="These variables are for the Anthropic service (auth token authentication).",
        api_key=EnvVarConfig(
            env="ANTHROPIC_AUTH_TOKEN",
            is_secret=True,
            description="Auth token for Anthropic provider",
            variable_name="auth_token",
        ),
    ),
]

# HUGGINGFACE_INFERENCE - API key + log level
HUGGINGFACE_INFERENCE = [
    ProviderEnvConfig(
        provider="huggingface-inference",
        clients=("hf_inference",),
        note="Hugging Face allows for setting many configuration options by environment variable. See [the Hugging Face documentation](https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables) for more details.",
        api_key=EnvVarConfig(
            env="HF_TOKEN",
            description="API key/token for Hugging Face service",
            variable_name="token",
            is_secret=True,
        ),
        log_level=EnvVarConfig(
            env="HF_HUB_VERBOSITY",
            description="Log level for Hugging Face Hub client",
            choices=frozenset({"debug", "info", "warning", "error", "critical"}),
        ),
        other=httpx_env_vars(),
    )
]

# BEDROCK - AWS credentials with multi-client support
BEDROCK = [
    ProviderEnvConfig(
        provider="bedrock",
        clients=("bedrock", "anthropic"),
        note="These variables are for the AWS Bedrock service.",
        region=EnvVarConfig(
            env="AWS_REGION",
            description="AWS region for Bedrock service",
            variable_name="region_name",
        ),
        account_id=EnvVarConfig(
            env="AWS_ACCOUNT_ID",
            description="AWS Account ID for Bedrock service",
            variable_name="aws_account_id",
        ),
        api_key=EnvVarConfig(
            env="AWS_SECRET_ACCESS_KEY",
            description="AWS Secret Access Key for Bedrock service",
            is_secret=True,
            variable_name="aws_secret_access_key",
        ),
        other=frozenset([
            (
                "aws_access_key_id",
                EnvVarConfig(
                    env="AWS_ACCESS_KEY_ID",
                    description="AWS Access Key ID for Bedrock service",
                    is_secret=True,
                    variable_name="aws_access_key_id",
                ),
            ),
            (
                "aws_session_token",
                EnvVarConfig(
                    env="AWS_SESSION_TOKEN",
                    description="AWS Session Token for Bedrock service",
                    is_secret=True,
                    variable_name="aws_session_token",
                ),
            ),
        ]),
    )
]

# COHERE - API key + base URL
COHERE = [
    simple_api_key_provider(
        "tavily",
        client="cohere",
        api_key_env="COHERE_API_KEY",
        base_url_env="CO_API_URL",
        note="These variables are for the Cohere service.",
    )
]

# TAVILY - Simple API key provider
TAVILY = [
    simple_api_key_provider(
        "tavily",
        client="tavily",
        api_key_env="TAVILY_API_KEY",
        note="These variables are for the Tavily service.",
    )
]

# GOOGLE - Multiple authentication methods
GOOGLE = [
    ProviderEnvConfig(
        provider="google",
        clients=("google",),
        note="These variables are for the Google Gemini service.",
        api_key=EnvVarConfig(
            env="GEMINI_API_KEY",
            description="Your Google Gemini API Key",
            is_secret=True,
            variable_name="api_key",
        ),
        other=httpx_env_vars(),
    ),
    ProviderEnvConfig(
        provider="google",
        clients=("google",),
        note="These variables are for the Google service (generic API key).",
        api_key=EnvVarConfig(
            env="GOOGLE_API_KEY",
            description="Your Google API Key",
            is_secret=True,
            variable_name="api_key",
        ),
    ),
]

# MISTRAL - Simple API key provider
MISTRAL = [
    simple_api_key_provider(
        "mistral",
        client="mistral",
        api_key_env="MISTRAL_API_KEY",
        note="These variables are for the Mistral service.",
    )
]

# PYDANTIC_GATEWAY - Simple API key provider
PYDANTIC_GATEWAY = [
    simple_api_key_provider(
        "gateway",
        client="gateway",
        api_key_env="PYDANTIC_AI_GATEWAY_API_KEY",
        note="These variables are for the Pydantic AI Gateway service.",
    )
]

# QDRANT - Complex configuration with TLS and logging
QDRANT = [
    ProviderEnvConfig(
        provider="qdrant",
        clients=("qdrant",),
        note="Qdrant supports setting **all** configuration options using environment variables. Like with CodeWeaver, nested variables are separated by double underscores (`__`). For all options, see [the Qdrant documentation](https://qdrant.tech/documentation/guides/configuration/)",
        log_level=EnvVarConfig(
            env="QDRANT__LOG_LEVEL",
            description="Log level for Qdrant service",
            choices=frozenset({"DEBUG", "INFO", "WARNING", "ERROR"}),
        ),
        api_key=EnvVarConfig(
            env="QDRANT__SERVICE__API_KEY",
            is_secret=True,
            description="API key for Qdrant service",
            variable_name="api_key",
        ),
        tls_on_off=EnvVarConfig(
            env="QDRANT__SERVICE__ENABLE_TLS",
            description="Enable TLS for Qdrant service, expects truthy or false value (e.g. 1 for on, 0 for off).",
            fmt=EnvFormat.BOOLEAN,
            choices=frozenset({"true", "false"}),
        ),
        host=EnvVarConfig(
            env="QDRANT__SERVICE__HOST", description="Host for Qdrant service", variable_name="host"
        ),
        port=EnvVarConfig(
            env="QDRANT__SERVICE__HTTP_PORT",
            description="HTTP port for Qdrant service",
            variable_name="port",
        ),
        tls_cert_path=EnvVarConfig(
            env="QDRANT__TLS__CERT",
            description="Path to TLS certificate for Qdrant service",
            fmt=EnvFormat.FILEPATH,
            variable_name="cert",
        ),
        tls_key_path=EnvVarConfig(
            env="QDRANT__TLS__KEY",
            description="Path to TLS key for Qdrant service",
            fmt=EnvFormat.FILEPATH,
            variable_name="key",
        ),
    )
]

__all__ = (
    "ANTHROPIC",
    "BEDROCK",
    "COHERE",
    "GOOGLE",
    "HUGGINGFACE_INFERENCE",
    "MISTRAL",
    "PYDANTIC_GATEWAY",
    "QDRANT",
    "TAVILY",
    "VOYAGE",
)

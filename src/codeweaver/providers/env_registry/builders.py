# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Composable builder functions for common provider patterns.

These reduce boilerplate by providing templates for common configurations.
Typical usage: 1-2 lines per provider instead of 50+ lines.
"""

from typing import Any

from codeweaver.core.types.env import EnvFormat, VariableInfo
from codeweaver.providers.env_registry.models import EnvVarConfig, ProviderEnvConfig


def httpx_env_vars() -> frozenset[tuple[str, EnvVarConfig]]:
    """Standard httpx environment variables used by most HTTP-based providers.

    Returns:
        Frozenset of (key, EnvVarConfig) tuples for common HTTP settings

    Example:
        >>> base_vars = httpx_env_vars()
        >>> custom_vars = base_vars | frozenset([("custom", EnvVarConfig(...))])
    """
    return frozenset([
        (
            "http_proxy",
            EnvVarConfig(
                env="HTTPS_PROXY",
                description="HTTP proxy for requests",
                variables=(VariableInfo(variable="proxy", dest="httpx"),),
            ),
        ),
        (
            "ssl_cert_file",
            EnvVarConfig(
                env="SSL_CERT_FILE",
                description="Path to the SSL certificate file for requests",
                fmt=EnvFormat.FILEPATH,
                variables=(VariableInfo(variable="verify", dest="httpx"),),
            ),
        ),
    ])


def openai_compatible_provider(
    provider_name: str,
    *,
    api_key_env: str,
    base_url_env: str | None = None,
    default_url: str | None = None,
    additional_clients: tuple[str, ...] = (),
    note: str | None = None,
    extra_vars: dict[str, EnvVarConfig] | None = None,
) -> ProviderEnvConfig:
    """Build configuration for OpenAI-compatible provider.

    This template covers ~15 providers that use the OpenAI SDK client
    with provider-specific API keys and base URLs.

    Args:
        provider_name: Display name (e.g., "DeepSeek", "Fireworks")
        api_key_env: Environment variable name for API key
        base_url_env: Optional env var for base URL
        default_url: Optional default base URL
        additional_clients: Extra client names beyond "openai"
        note: Optional note about the provider
        extra_vars: Additional custom environment variables

    Returns:
        Configured ProviderEnvConfig with OpenAI inheritance

    Example:
        >>> DEEPSEEK = openai_compatible_provider(
        ...     "DeepSeek", api_key_env="DEEPSEEK_API_KEY"
        ... )
        >>> GROQ = openai_compatible_provider(
        ...     "Groq",
        ...     api_key_env="GROQ_API_KEY",
        ...     base_url_env="GROQ_BASE_URL",
        ...     default_url="https://api.groq.com",
        ...     additional_clients=("groq",),
        ... )
    """
    clients = ("openai", *additional_clients)
    other_vars = httpx_env_vars()

    if extra_vars:
        other_vars = other_vars | frozenset(extra_vars.items())

    kwargs: dict[str, Any] = {
        "provider": provider_name.lower(),
        "clients": clients,
        "note": note or f"These variables are for the {provider_name} service.",
        "api_key": EnvVarConfig(
            env=api_key_env,
            description=f"Your {provider_name} API Key",
            is_secret=True,
            variable_name="api_key",
        ),
        "other": other_vars,
        "inherits_from": "openai",
    }

    if base_url_env:
        kwargs["host"] = EnvVarConfig(
            env=base_url_env,
            description=f"Host URL for {provider_name} service",
            variable_name="base_url",
            default=default_url,
        )

    return ProviderEnvConfig(**kwargs)


def simple_api_key_provider(
    provider_name: str,
    client: str,
    api_key_env: str,
    *,
    base_url_env: str | None = None,
    additional_vars: dict[str, EnvVarConfig] | None = None,
    note: str | None = None,
) -> ProviderEnvConfig:
    """Build configuration for simple API key-based provider.

    For providers with their own SDK client (not OpenAI-compatible).

    Args:
        provider_name: Display name (e.g., "Voyage", "Cohere")
        client: Client SDK name (e.g., "voyage", "cohere")
        api_key_env: Environment variable name for API key
        base_url_env: Optional env var for base URL
        additional_vars: Additional custom environment variables
        note: Optional note about the provider

    Returns:
        Configured ProviderEnvConfig

    Example:
        >>> VOYAGE = simple_api_key_provider(
        ...     "Voyage", client="voyage", api_key_env="VOYAGE_API_KEY"
        ... )
        >>> COHERE = simple_api_key_provider(
        ...     "Cohere",
        ...     client="cohere",
        ...     api_key_env="COHERE_API_KEY",
        ...     base_url_env="COHERE_BASE_URL",
        ... )
    """
    other_vars = httpx_env_vars()
    if additional_vars:
        other_vars = other_vars | frozenset(additional_vars.items())

    kwargs: dict[str, Any] = {
        "provider": provider_name.lower(),
        "clients": (client,),
        "note": note or f"These variables are for the {provider_name} service.",
        "api_key": EnvVarConfig(
            env=api_key_env,
            description=f"Your {provider_name} API Key",
            is_secret=True,
            variable_name="api_key",
        ),
        "other": other_vars,
    }

    if base_url_env:
        kwargs["host"] = EnvVarConfig(
            env=base_url_env,
            description=f"Host URL for {provider_name} service",
            variable_name="base_url",
        )

    return ProviderEnvConfig(**kwargs)


def multi_client_provider(
    provider_name: str, configs: list[ProviderEnvConfig]
) -> list[ProviderEnvConfig]:
    """Build multi-client provider configuration (like Azure).

    Some providers (Azure, Heroku) support multiple underlying clients
    with different environment variables for each.

    Args:
        provider_name: Provider name (e.g., "azure", "heroku")
        configs: List of configs for each client

    Returns:
        List of ProviderEnvConfig with updated provider names

    Example:
        >>> _azure_openai = ProviderEnvConfig(...)
        >>> _azure_cohere = ProviderEnvConfig(...)
        >>> AZURE = multi_client_provider("azure", [_azure_openai, _azure_cohere])
    """
    # Recreate each config with updated provider name
    return [
        ProviderEnvConfig(
            provider=provider_name,
            clients=cfg.clients,
            note=cfg.note,
            api_key=cfg.api_key,
            host=cfg.host,
            endpoint=cfg.endpoint,
            region=cfg.region,
            port=cfg.port,
            log_level=cfg.log_level,
            account_id=cfg.account_id,
            tls_on_off=cfg.tls_on_off,
            tls_cert_path=cfg.tls_cert_path,
            tls_key_path=cfg.tls_key_path,
            other=cfg.other,
            inherits_from=cfg.inherits_from,
        )
        for cfg in configs
    ]


__all__ = (
    "httpx_env_vars",
    "multi_client_provider",
    "openai_compatible_provider",
    "simple_api_key_provider",
)

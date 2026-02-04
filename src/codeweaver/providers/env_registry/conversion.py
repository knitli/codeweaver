# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Conversion utilities for registry models to legacy TypedDict format.

Provides backward compatibility by converting ProviderEnvConfig to ProviderEnvVars.
"""

from __future__ import annotations

from codeweaver.core.types.env import EnvFormat, EnvVarInfo, ProviderEnvVars
from codeweaver.providers.env_registry.models import EnvVarConfig, ProviderEnvConfig


def env_var_config_to_info(config: EnvVarConfig) -> EnvVarInfo:
    """Convert EnvVarConfig (registry) to EnvVarInfo (legacy).

    Args:
        config: Registry env var configuration

    Returns:
        Legacy env var info compatible with existing code

    Example:
        >>> config = EnvVarConfig(
        ...     env="OPENAI_API_KEY",
        ...     description="API key",
        ...     is_secret=True,
        ...     variable_name="api_key"
        ... )
        >>> info = env_var_config_to_info(config)
        >>> info.env
        'OPENAI_API_KEY'
    """
    return EnvVarInfo(
        env=config.env,
        description=config.description,
        is_secret=config.is_secret,
        fmt=config.fmt or EnvFormat.STRING,
        default=config.default,
        choices=set(config.choices) if config.choices else None,
        variable_name=config.variable_name,
        variables=config.variables or (),
    )


def provider_env_config_to_vars(
    config: ProviderEnvConfig, *, resolve_inheritance: bool = True
) -> ProviderEnvVars:
    """Convert ProviderEnvConfig (registry) to ProviderEnvVars (legacy).

    Args:
        config: Registry provider configuration
        resolve_inheritance: Whether to resolve inheritance (default True)

    Returns:
        Legacy provider env vars compatible with existing code

    Example:
        >>> config = ProviderEnvConfig(
        ...     provider="deepseek",
        ...     clients=("openai",),
        ...     api_key=EnvVarConfig(env="DEEPSEEK_API_KEY", description="API key", is_secret=True),
        ...     inherits_from="openai"
        ... )
        >>> env_vars = provider_env_config_to_vars(config)
        >>> env_vars["api_key"].env
        'DEEPSEEK_API_KEY'
    """
    # Build base env vars from standard fields
    result: ProviderEnvVars = {}

    if config.note:
        result["note"] = config.note

    if config.clients:
        result["client"] = config.clients

    # Convert standard fields
    for field_name in (
        "api_key",
        "host",
        "endpoint",
        "region",
        "port",
        "log_level",
        "account_id",
        "tls_on_off",
        "tls_cert_path",
        "tls_key_path",
    ):
        if field_value := getattr(config, field_name, None):
            result[field_name] = env_var_config_to_info(field_value)  # type: ignore

    # Convert 'other' field from frozenset[tuple] to dict
    if config.other:
        other_dict: dict[str, EnvVarInfo] = {}
        for key, env_config in config.other:
            other_dict[key] = env_var_config_to_info(env_config)
        result["other"] = other_dict

    # Handle inheritance if requested
    # Note: Inheritance resolution is handled by get_provider_configs which
    # returns all configs including inherited ones

    return result


def get_provider_configs(
    provider_name: str,
) -> tuple[ProviderEnvConfig, ...] | None:
    """Get all provider configurations from registry.

    Args:
        provider_name: Provider name (e.g., "openai", "azure", "deepseek")

    Returns:
        Tuple of provider configurations, or None if not found in registry

    Example:
        >>> configs = get_provider_configs("azure")
        >>> len(configs)
        3  # Azure has 3 client configurations
    """
    try:
        from codeweaver.providers.env_registry.definitions import (
            ALIBABA,
            ANTHROPIC,
            AZURE,
            BEDROCK,
            CEREBRAS,
            COHERE,
            DEEPSEEK,
            FIREWORKS,
            GITHUB,
            GOOGLE,
            GROQ,
            HEROKU,
            HUGGINGFACE_INFERENCE,
            LITELLM,
            MISTRAL,
            MOONSHOT,
            MORPH,
            NEBIUS,
            OLLAMA,
            OPENAI,
            OPENROUTER,
            OVHCLOUD,
            PERPLEXITY,
            PYDANTIC_GATEWAY,
            QDRANT,
            SAMBANOVA,
            TAVILY,
            TOGETHER,
            VERCEL,
            VOYAGE,
            X_AI,
        )
    except ImportError:
        return None

    # Map provider names to registry definitions
    registry_map = {
        "alibaba": ALIBABA,
        "anthropic": ANTHROPIC,
        "azure": AZURE,
        "bedrock": BEDROCK,
        "cerebras": CEREBRAS,
        "cohere": COHERE,
        "deepseek": DEEPSEEK,
        "fireworks": FIREWORKS,
        "github": GITHUB,
        "google": GOOGLE,
        "groq": GROQ,
        "heroku": HEROKU,
        "hf-inference": HUGGINGFACE_INFERENCE,
        "litellm": LITELLM,
        "mistral": MISTRAL,
        "moonshot": MOONSHOT,
        "morph": MORPH,
        "nebius": NEBIUS,
        "ollama": OLLAMA,
        "openai": OPENAI,
        "openrouter": OPENROUTER,
        "ovhcloud": OVHCLOUD,
        "perplexity": PERPLEXITY,
        "gateway": PYDANTIC_GATEWAY,
        "qdrant": QDRANT,
        "sambanova": SAMBANOVA,
        "tavily": TAVILY,
        "together": TOGETHER,
        "vercel": VERCEL,
        "voyage": VOYAGE,
        "x-ai": X_AI,
    }

    if provider_name not in registry_map:
        return None

    configs = registry_map[provider_name]

    # Registry definitions are lists of ProviderEnvConfig
    if isinstance(configs, list):
        return tuple(configs)
    return None


def get_provider_env_vars_from_registry(
    provider_name: str,
) -> tuple[ProviderEnvVars, ...] | None:
    """Get provider environment variables from registry.

    Main entry point for registry integration.

    Args:
        provider_name: Provider name (e.g., "openai", "azure", "deepseek")

    Returns:
        Tuple of ProviderEnvVars compatible with existing code, or None if not in registry

    Example:
        >>> env_vars = get_provider_env_vars_from_registry("deepseek")
        >>> env_vars[0]["api_key"].env
        'DEEPSEEK_API_KEY'
    """
    configs = get_provider_configs(provider_name)

    if not configs:
        return None

    return tuple(provider_env_config_to_vars(config) for config in configs)


__all__ = (
    "env_var_config_to_info",
    "get_provider_configs",
    "get_provider_env_vars_from_registry",
    "provider_env_config_to_vars",
)

# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Utility functions for configuration providers."""

import os

from collections.abc import Sequence
from typing import Any

from pydantic import Discriminator

from codeweaver.core.exceptions import ConfigurationError
from codeweaver.core.types import Provider
from codeweaver.providers.config.types import AzureOptions


def ensure_endpoint_version(url: str, *, cohere: bool = False) -> str:
    """Ensure the URL ends with /v1 for openai or v2 for cohere."""
    ending = "v2" if cohere else "v1"
    if url.endswith(ending):
        return url
    return f"{url}{ending}" if url.endswith("/") else f"{url}/{ending}"


def _get_heroku_envs(*, cohere: bool = False) -> tuple[str, ...]:
    envs = ["INFERENCE_URL", "HEROKU_INFERENCE_URL", "HEROKU_BASE_URL"]
    if cohere:
        envs.extend(("CO_API_URL", "COHERE_BASE_URL", "COHERE_API_BASE"))
    else:
        envs.extend(("OPENAI_API_URL", "OPENAI_API_BASE_URL", "OPENAI_API_BASE"))
    return tuple(envs)


def try_for_heroku_endpoint(client_options: Any, *, cohere: bool = False) -> str | None:
    """Try to identify the Heroku endpoint."""
    if "base_url" in client_options:
        return ensure_endpoint_version(client_options["base_url"], cohere=cohere)
    if "api_base" in client_options:
        return ensure_endpoint_version(client_options["api_base"], cohere=cohere)
    if env_set := next(
        (os.getenv(env) for env in _get_heroku_envs(cohere=cohere) if os.getenv(env) is not None),
        None,
    ):
        return ensure_endpoint_version(env_set, cohere=cohere)
    return None


def _parse_endpoint(endpoint: str, region: str | None = None) -> str | None:
    """Parse the Azure endpoint URL."""
    if endpoint.startswith("http"):
        if endpoint.endswith("v1"):
            return endpoint
        endpoint = endpoint.split("//", 1)[1].split(".")[0]
        region = region or endpoint.split(".")[1]
        return f"https://{endpoint}.{region}.inference.ai.azure.com/v1"
    endpoint = endpoint.split(".")[0]
    region = region or endpoint.split(".")[1]
    return f"https://{endpoint}.{region}.inference.ai.azure.com/v1"


def try_for_azure_endpoint(options: AzureOptions, *, cohere: bool = False) -> str | None:
    """Try to identify the Azure endpoint.

    Azure uses this format: `https://<endpoint>.<region_name>.inference.ai.azure.com/v1`,
    But because people often conflate `endpoint` and `url`, we try to be flexible.
    """
    region_var = "AZURE_COHERE_REGION" if cohere else "AZURE_OPENAI_REGION"
    endpoint_var = "AZURE_COHERE_ENDPOINT" if cohere else "AZURE_OPENAI_ENDPOINT"
    endpoint = options.get("base_url") or options.get("api_base")
    endpoint, region = options.get("endpoint"), options.get("region_name")
    if endpoint and region:
        if not endpoint.startswith("http") or "azure" not in endpoint:
            # URL looks right
            return f"{endpoint}.{region}.inference.ai.azure.com/v1"
        return _parse_endpoint(endpoint, region)
    if endpoint and (region := os.getenv(region_var)):
        return f"https://{endpoint}.{region}.inference.ai.azure.com/v1"
    if region and (endpoint := os.getenv(endpoint_var)):
        return _parse_endpoint(endpoint, region)
    if base_url := options.get("base_url"):
        return ensure_endpoint_version(base_url, cohere=cohere)
    if api_base := options.get("api_base"):
        return ensure_endpoint_version(api_base, cohere=cohere)
    if env_set := (
        os.getenv("AZURE_COHERE_ENDPOINT") if cohere else os.getenv("AZURE_OPENAI_ENDPOINT")
    ) or os.getenv("AZURE_API_BASE"):
        return _parse_endpoint(env_set, region or os.getenv("AZURE_OPENAI_REGION"))
    return None


def _test_keys(keys: Sequence[str], v: dict[str, Any]) -> bool:
    """Test if any of the keys are in the dictionary."""
    return any(key for key in v if key in keys)


def _discriminate_embedding_clients_by_keys(value: dict[str, Any]) -> str | None:
    """Try to identify the provider based on unique key presence."""
    if _test_keys(
        ["model_name_or_path", "modules", "device", "prompts", "similarity_fn_name"], value
    ):
        return "sentence_transformers"
    if _test_keys(
        [
            "aws_secret_access_key",
            "aws_access_key_id",
            "aws_session_token",
            "region_name",
            "profile_name",
            "aws_account_id",
            "botocore_session",
        ],
        value,
    ):
        return "bedrock"
    if _test_keys(["vertex_ai", "credentials", "location"], value):
        return "google"
    if _test_keys(
        ["model_name", "cache_dir", "threads", "providers", "cuda", "device_ids", "lazy_load"],
        value,
    ):
        return "fastembed"
    if _test_keys(["websocket_base_url", "organization", "project", "webhook_secret"], value):
        return "openai"
    if _test_keys(
        ["model", "provider", "token", "headers", "cookies", "proxies", "bill_to"], value
    ):
        return "hf_inference"
    if _test_keys(
        [
            "server",
            "server_url",
            "url_params",
            "async_client",
            "retry_config",
            "timeout_ms",
            "trust_env",
            "url_params",
            "debug_logger",
        ],
        value,
    ):
        return "mistral"
    return None


def _discriminate_embedding_clients_by_url(value: dict[str, Any]) -> str | None:
    """Try to identify the provider based on URL patterns and key presence."""
    raw_url = value.get("base_url") or value.get("server_url")
    url = str(raw_url) if raw_url else ""
    if _test_keys(
        ["environment", "client_name", "thread_pool_executor", "log_experimental"], value
    ) or (url and ("cohere" in url or "heroku" in url)):
        return "cohere"
    if url and "v1" in url and _test_keys(["api_key"], value):
        return "openai"
    if not url and _test_keys(["api_key", "max_retries", "timeout"], value):
        return "voyage"
    if url and (
        provider := next((p.variable for p in Provider if p.variable in url.lower()), None)
    ):
        return provider
    return None


def discriminate_embedding_clients(v: Any) -> str | None:
    """Identify the provider-specific settings type for discriminator field."""
    # Client options use tag field but we may not have it in raw config
    if tag := v.get("tag") if isinstance(v, dict) else getattr(v, "tag", None):
        return tag  # Return empty string instead of None to match return type
    value = v if isinstance(v, dict) else v.model_dump()
    if found_value := _discriminate_embedding_clients_by_keys(value):
        return found_value
    if found_value := _discriminate_embedding_clients_by_url(value):
        return found_value
    if (env_var := next((k for k in os.environ if k.startswith("AZURE_")), None)) and (
        provider := "cohere" if "COHERE" in env_var else "openai" if "OPENAI" in env_var else None
    ):
        return provider
    if env_var := os.environ.get("CODEWEAVER_EMBEDDING_PROVIDER"):
        return env_var.lower().replace(" ", "_").replace("-", "_")
    raise ConfigurationError(
        "Could not discriminate embedding client options type from provided data."
    )


def simple_provider_discriminator(value: dict[str, Any]) -> str:
    """Identify the provider for simple agent model provider options based on tag or URL patterns."""
    return value["provider"].variable if isinstance(value, dict) else value.provider.variable


def _discriminate_anthropic_client_options(value: dict[str, Any]) -> str:
    """Identify if the options are for Anthropic based on key presence."""
    result = simple_provider_discriminator(value)
    return "anthropic" if result.startswith("anthropic") else "other"


ANTHROPIC_CLIENT_OPTIONS_AGENT_DISCRIMINATOR = Discriminator(_discriminate_anthropic_client_options)

__all__ = (
    "ANTHROPIC_CLIENT_OPTIONS_AGENT_DISCRIMINATOR",
    "discriminate_embedding_clients",
    "ensure_endpoint_version",
    "simple_provider_discriminator",
    "try_for_azure_endpoint",
    "try_for_heroku_endpoint",
)

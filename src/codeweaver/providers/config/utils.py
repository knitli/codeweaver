# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Utility functions for configuration providers."""

import os

from typing import Any, TypedDict

from pydantic import SecretStr

from codeweaver.core import lazy_import


create_backup_class = lazy_import("codeweaver.core.backup_factory", "create_backup_class")


class AzureOptions(TypedDict, total=False):
    """Azure-specific options."""

    model_deployment: str
    endpoint: str | None
    region_name: str | None
    api_key: SecretStr | None


def ensure_endpoint_version(url: str, *, cohere: bool = False) -> str:
    """Ensure the URL ends with /v1 for openai or v2 for cohere."""
    ending = "v2" if cohere else "v1"
    if url.endswith(ending):
        return url
    return f"{url}{ending}" if url.endswith("/") else f"{url}/{ending}"


def _get_heroku_envs(*, cohere: bool = False) -> tuple[str, ...]:
    envs = ["INFERENCE_URL", "HEROKU_INFERENCE_URL", "HEROKU_BASE_URL"]
    if cohere:
        envs.extend(["CO_API_URL", "COHERE_BASE_URL", "COHERE_API_BASE"])
    else:
        envs.extend(["OPENAI_API_URL", "OPENAI_API_BASE_URL", "OPENAI_API_BASE"])
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


def try_for_azure_endpoint(options: dict[str, Any], *, cohere: bool = False) -> str | None:
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
    if "base_url" in options:
        return ensure_endpoint_version(options["base_url"], cohere=cohere)
    if "api_base" in options:
        return ensure_endpoint_version(options["api_base"], cohere=cohere)
    if env_set := (
        os.getenv("AZURE_COHERE_ENDPOINT") if cohere else os.getenv("AZURE_OPENAI_ENDPOINT")
    ) or os.getenv("AZURE_API_BASE"):
        return _parse_endpoint(env_set, region or os.getenv("AZURE_OPENAI_REGION"))
    return None


def this_as_backup_cls[U: Any, BackupT: type[U]](
    instance: Any, *, namespace: dict[str, Any]
) -> BackupT | None:
    """Return the instance as the backup type if possible.

    This is a helper to create a backup class from an instance's type, it's only for local use in the config package to avoid circular imports.
    """
    return create_backup_class(type(instance), extra_namespace=namespace)


__all__ = (
    "AzureOptions",
    "ensure_endpoint_version",
    "this_as_backup_cls",
    "try_for_azure_endpoint",
    "try_for_heroku_endpoint",
)

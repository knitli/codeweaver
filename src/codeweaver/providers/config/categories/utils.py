# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Utility functions for provider category settings."""

import re

from typing import Any

from pydantic import Discriminator

from codeweaver.core import Provider
from codeweaver.core.utils import is_local_host
from codeweaver.providers.config.categories.base import BaseProviderCategorySettings


def is_cloud_provider(_instance: BaseProviderCategorySettings) -> bool:
    """Return True if the provider settings are for a cloud deployment."""
    if _instance.provider.always_cloud or not _instance.provider.always_local:
        return True
    return bool(
        _instance.client_options
        and (
            url := getattr(
                _instance.client_options,
                "url",
                getattr(
                    _instance.client_options,
                    "endpoint",
                    getattr(_instance.client_options, "base_url", None),
                ),
            )
        )
        is not None
        and (not is_local_host(url))
    )


def _discriminate_provider_settings(data: dict[str, Any]) -> str:
    """Discriminator function to determine the provider type from the input data."""
    provider = data["provider"] if isinstance(data, dict) else data.provider
    if not isinstance(provider, Provider):
        # this normalizes the provider value
        # The Provider class can take many variations of a name and convert it to a standard form, so we want to leverage that
        provider = Provider.from_string(provider)
    return provider.variable


PROVIDER_DISCRIMINATOR = Discriminator(_discriminate_provider_settings)
"""A generic discriminator for provider settings that determines the provider type based on the `provider` field in the input data. This can be used for any provider settings that have a `provider` field that corresponds to a member of the `Provider` enum."""


def _reranking_provider_settings_discriminator(data: dict[str, Any]) -> str:
    """Discriminator function to determine the reranking provider type from the input data."""
    result = _discriminate_provider_settings(data)
    return result if result in {"fastembed", "bedrock"} else "simple"


RERANKING_PROVIDER_DISCRIMINATOR = Discriminator(_reranking_provider_settings_discriminator)
"""A discriminator for reranking provider settings that determines the provider type based on the `provider` field in the input data, but maps any provider that is not explicitly recognized as "fastembed" or "bedrock" to "simple"."""


def _discriminate_core_embedding_provider_settings(data: dict[str, Any]) -> str:
    """Discriminator function to determine the core embedding provider type from the input data."""
    result = _discriminate_provider_settings(data)
    return result if result in {"fastembed", "azure", "bedrock"} else "simple"


CORE_EMBEDDING_PROVIDER_DISCRIMINATOR = Discriminator(
    _discriminate_core_embedding_provider_settings
)
"""A discriminator for core embedding provider settings that determines the provider type based on the `provider` field in the input data, but maps any provider that is not explicitly recognized as "fastembed", "azure", or "bedrock" to "simple"."""

_anthropic_model_pattern = re.compile(r".*anthropic.*|.*claude.*|.*opus.*|.*sonnet.*|.*haiku.*")
_anthropic_client_providers = {
    Provider.ANTHROPIC,
    Provider.AZURE,
    Provider.BEDROCK,
    Provider.GOOGLE,
}


def _discriminate_anthropic_from_other_agent_providers(data: dict[str, Any]) -> str:
    """Discriminator function to determine if the provider is an Anthropic-based agent provider or not."""
    result = _discriminate_provider_settings(data)
    # note: Not all anthropic provider members are exclusive to using the anthropic client,
    # so we also check the model name for those providers
    if result in _anthropic_client_providers:
        model_name = data["model_name"] if isinstance(data, dict) else data.model_name
        if _anthropic_model_pattern.match(model_name.lower()):
            return "anthropic"
    return "other"


ANTHROPIC_PROVIDER_DISCRIMINATOR = Discriminator(_discriminate_anthropic_from_other_agent_providers)
"""A discriminator for agent provider settings that determines if the provider is an Anthropic-based agent provider or not based on the `provider` and `model_name` fields in the input data."""


def _non_anthropic_agent_provider_settings_discriminator(data: dict[str, Any]) -> str:
    """Discriminator function to determine the type of a non-Anthropic agent provider based on the `provider` field in the input data."""
    result = _discriminate_provider_settings(data)
    if result in {
        "openrouter",
        "cerebras",
        "google",
        "cohere",
        "hf_inference",
        "mistral",
        "gateway",
    }:
        return result
    # Any remaining providers that don't have their own settings class use "openai"
    return "openai"


NON_ANTHROPIC_AGENT_PROVIDER_DISCRIMINATOR = Discriminator(
    _non_anthropic_agent_provider_settings_discriminator
)
"""A discriminator for non-Anthropic agent provider settings that determines the provider type based on the `provider` field in the input data, mapping unrecognized providers to "openai"."""

__all__ = (
    ANTHROPIC_PROVIDER_DISCRIMINATOR,
    "CORE_EMBEDDING_PROVIDER_DISCRIMINATOR",
    "PROVIDER_DISCRIMINATOR",
    "RERANKING_PROVIDER_DISCRIMINATOR",
    "is_cloud_provider",
    "NON_ANTHROPIC_AGENT_PROVIDER_DISCRIMINATOR",
)

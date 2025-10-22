# SPDX-FileCopyrightText: (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Entrypoint for CodeWeaver's embedding model system.

We wanted to mirror `pydantic-ai`'s handling of LLM models, but we had to make a lot of adjustments to fit the embedding use case.
"""

# sourcery skip: avoid-global-variables
from __future__ import annotations

from typing import Any

from codeweaver.config import EmbeddingModelSettings, EmbeddingProviderSettings
from codeweaver.providers.provider import Provider


def _add_compatible_keys(
    model_settings: EmbeddingModelSettings, compatible_keys: dict[str, str]
) -> dict[str, Any]:
    """Add any keys in settings that are compatible with the provider.

    Args:
        model_settings: The model settings to process.
        compatible_keys: A mapping of keys in the model settings to keys expected by the provider.
    """
    compatible_settings: dict[str, Any] = {
        compatible_keys[key]: value
        for key, value in model_settings.items()
        if key in compatible_keys
    }
    return compatible_settings


def _process_model_settings(model_settings: EmbeddingModelSettings) -> dict[str, Any]:
    """Process model settings to ensure they are valid."""
    provider = Provider.from_string(model_settings["model"].split(":")[0])
    processed_settings = {
        "provider": provider,
        "model": "".join(model_settings["model"].split(":")[1:]),
    }
    match provider:
        case Provider.VOYAGE:
            return processed_settings | _add_compatible_keys(
                model_settings,
                {
                    "dimension": "output_dimension",
                    "data_type": "output_dtype",
                    "client_kwargs": "kwargs",
                },
            )
        case _:
            return processed_settings | _add_compatible_keys(
                model_settings, {"client_kwargs": "kwargs"}
            )

    return processed_settings


def user_settings_to_provider_settings(
    user_settings: EmbeddingProviderSettings,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Convert user settings to provider settings."""
    model_settings: EmbeddingModelSettings | tuple[EmbeddingModelSettings, ...] = user_settings[
        "model_settings"
    ]  # type: ignore
    return (
        [_process_model_settings(ms) for ms in model_settings]
        if isinstance(model_settings, tuple)
        else _process_model_settings(model_settings)
    )


def get_embedding_model_provider() -> None:  # -> EmbeddingProvider[Any]:
    """Get embedding model provider."""


__all__ = ("get_embedding_model_provider", "user_settings_to_provider_settings")

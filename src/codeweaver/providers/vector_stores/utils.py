# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Utilities for vector store providers."""

from typing import cast

from pydantic import PositiveInt


def resolve_dimensions() -> PositiveInt:
    """Resolves embedding dimensions based on model capabilities and model settings. **Only applies to dense embeddings.**."""
    from codeweaver.common.registry.models import get_model_registry
    from codeweaver.config.settings import get_settings_map
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    registry = get_model_registry()
    capabilities = registry.configured_models_for_kind("embedding")
    model_capabilities = cast(
        EmbeddingModelCapabilities,
        (capabilities[0] if isinstance(capabilities, tuple) else capabilities),
    )
    if not model_capabilities:
        raise ValueError("No embedding model configured.")
    if (
        (model_settings := get_settings_map()["embedding"].get("model_settings", {}))
        and (dimension := model_settings.get("dimension"))
        and (dimension in model_capabilities.output_dimensions)
    ):
        return dimension
    return model_capabilities.default_dimension

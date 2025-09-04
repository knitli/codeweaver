# SPDX-FileCopyrightText: (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Entrypoint for CodeWeaver's embedding model capabilities.

This module now delegates storage and lookup to the global ModelRegistry.
It lazily registers built-in capabilities once and exposes simple helpers
to query by name/provider.
"""

from __future__ import annotations

from collections.abc import Generator, Sequence
from importlib.util import find_spec
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.embedding.capabilities.base import EmbeddingModelCapabilities


dependency_map = {
    "azure:embed": "cohere",
    "azure:text-embedding": "openai",
    "bedrock": "boto3",
    "cohere": "cohere",
    "fastembed": "fastembed",
    "fireworks": "openai",
    "github": "openai",
    "google": "genai",
    "heroku": "openai",
    "groq": "openai",
    "hf-inference": "huggingface_hub[inference]",
    "mistral": "mistralai",
    "ollama": "openai",
    "openai": "openai",
    "sentence_transformers": "sentence_transformers",
    "together": "openai",
    "vercel": "openai",
    "voyage": "voyageai",
}


def is_available(model: EmbeddingModelCapabilities) -> bool:
    """Check if a model is available for use."""
    model_string = f"{model.provider!s}:{model.name}"
    if dependency := next(
        (dep for key, dep in dependency_map.items() if model_string.startswith(key)), None
    ):
        return bool(find_spec(dependency))
    return False


def filter_unimplemented(
    models: Sequence[EmbeddingModelCapabilities],
) -> Generator[EmbeddingModelCapabilities]:
    """Removes models that are not yet implemented. Currently these are models that require the full `transformers` library."""
    unimplemented = {
        "heroku:cohere-embed-multilingual",
        "github:cohere/Cohere-embed-v3-english",
        "github:cohere/Cohere-embed-v3-multilingual",
    }
    for model in models:
        if f"{model.provider!s}:{model.name}" in unimplemented:
            model._available = False  # pyright: ignore[reportPrivateUsage]
        elif is_available(model):
            model._available = True  # pyright: ignore[reportPrivateUsage]
        else:
            model._available = False  # pyright: ignore[reportPrivateUsage]
        yield model


def _load_default_capabilities() -> Generator[EmbeddingModelCapabilities]:
    """Import and collect all built-in capabilities (once)."""
    from codeweaver.embedding.capabilities.alibaba_nlp import get_alibaba_nlp_embedding_capabilities
    from codeweaver.embedding.capabilities.amazon import get_amazon_embedding_capabilities
    from codeweaver.embedding.capabilities.baai import get_baai_embedding_capabilities
    from codeweaver.embedding.capabilities.cohere import get_cohere_embedding_capabilities
    from codeweaver.embedding.capabilities.ibm_granite import get_ibm_granite_embedding_capabilities
    from codeweaver.embedding.capabilities.intfloat import get_intfloat_embedding_capabilities
    from codeweaver.embedding.capabilities.jinaai import get_jinaai_embedding_capabilities
    from codeweaver.embedding.capabilities.mixedbread_ai import (
        get_mixedbread_ai_embedding_capabilities,
    )
    from codeweaver.embedding.capabilities.nomic_ai import get_nomic_ai_embedding_capabilities
    from codeweaver.embedding.capabilities.openai import get_openai_embedding_capabilities
    from codeweaver.embedding.capabilities.qwen import get_qwen_embedding_capabilities
    from codeweaver.embedding.capabilities.sentence_transformers import (
        get_sentence_transformers_embedding_capabilities,
    )
    from codeweaver.embedding.capabilities.snowflake import get_snowflake_embedding_capabilities
    from codeweaver.embedding.capabilities.thenlper import get_thenlper_embedding_capabilities
    from codeweaver.embedding.capabilities.voyage import get_voyage_embedding_capabilities
    from codeweaver.embedding.capabilities.whereisai import get_whereisai_embedding_capabilities

    yield from (
        item
        for item in (
            *filter_unimplemented(get_alibaba_nlp_embedding_capabilities()),
            *filter_unimplemented(get_amazon_embedding_capabilities()),
            *filter_unimplemented(get_baai_embedding_capabilities()),
            *filter_unimplemented(get_cohere_embedding_capabilities()),
            *filter_unimplemented(get_ibm_granite_embedding_capabilities()),
            *filter_unimplemented(get_intfloat_embedding_capabilities()),
            *filter_unimplemented(get_jinaai_embedding_capabilities()),
            *filter_unimplemented(get_mixedbread_ai_embedding_capabilities()),
            *filter_unimplemented(get_nomic_ai_embedding_capabilities()),
            *filter_unimplemented(get_openai_embedding_capabilities()),
            *filter_unimplemented(get_qwen_embedding_capabilities()),
            *filter_unimplemented(get_sentence_transformers_embedding_capabilities()),
            *filter_unimplemented(get_snowflake_embedding_capabilities()),
            *filter_unimplemented(get_thenlper_embedding_capabilities()),
            *filter_unimplemented(get_voyage_embedding_capabilities()),
            *filter_unimplemented(get_whereisai_embedding_capabilities()),
        )
        if item
    )


def ensure_default_capabilities_registered() -> None:
    """Populate the global registry with built-in capabilities if empty."""
    from codeweaver._settings_registry import get_model_registry, register_embedding_capabilities

    registry = get_model_registry()
    if registry.is_empty():
        register_embedding_capabilities(_load_default_capabilities())
        registry.mark_defaults_populated()


__all__ = ("ensure_default_capabilities_registered",)

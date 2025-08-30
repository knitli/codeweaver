# SPDX-FileCopyrightText: (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Entrypoint for CodeWeaver's embedding model capabilities."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from codeweaver._settings import Provider


if TYPE_CHECKING:
    from codeweaver.embedding.capabilities.base import RerankingModelCapabilities


def filter_unimplemented(
    models: Sequence[RerankingModelCapabilities],
) -> Sequence[RerankingModelCapabilities]:
    """Removes models that are not yet implemented. Currently these are models that require the full `transformers` library."""
    return models


def get_model(model: str) -> RerankingModelCapabilities:
    """Get the embedding model class by name."""
    if model.startswith("voyage"):
        from codeweaver.embedding.capabilities.voyage import get_voyage_embedding_capabilities

        return next(model for model in get_voyage_embedding_capabilities() if model.name == model)
    if model.startswith("jina"):
        from codeweaver.embedding.capabilities.jinaai import get_jinaai_embedding_capabilities

        return next(model for model in get_jinaai_embedding_capabilities() if model.name == model)
    if model.startswith("cohere"):
        from codeweaver.embedding.capabilities.cohere import get_cohere_embedding_capabilities

        return next(model for model in get_cohere_embedding_capabilities() if model.name == model)
    if model.lower().startswith("baai"):
        from codeweaver.embedding.capabilities.baai import get_baai_embedding_capabilities

        return next(model for model in get_baai_embedding_capabilities() if model.name == model)
    if model.lower().startswith(("msmarco", "ms-marco")):
        from codeweaver.embedding.capabilities.ms_marco import get_marco_embedding_capabilities

        return next(model for model in get_marco_embedding_capabilities() if model.name == model)
    if model.lower().startswith("alibaba"):
        from codeweaver.embedding.capabilities.alibaba_nlp import get_alibaba_embedding_capabilities

        return next(model for model in get_alibaba_embedding_capabilities() if model.name == model)
    if model.startswith(("openai", "text-embedding-")):
        from codeweaver.embedding.capabilities.openai import get_openai_embedding_capabilities

        return next(model for model in get_openai_embedding_capabilities() if model.name == model)
    if model.startswith("amazon"):
        from codeweaver.embedding.capabilities.amazon import get_amazon_embedding_capabilities

        return next(model for model in get_amazon_embedding_capabilities() if model.name == model)
    if model.startswith("Qwen"):
        from codeweaver.embedding.capabilities.qwen import get_qwen_embedding_capabilities

        return next(model for model in get_qwen_embedding_capabilities() if model.name == model)
    raise ValueError(f"Unknown embedding model: {model}. Maybe check your spelling or the syntax?")


def get_all_model_capabilities() -> tuple[RerankingModelCapabilities, ...]:
    """Get all available embedding models."""
    from codeweaver.embedding.capabilities.amazon import get_amazon_embedding_capabilities
    from codeweaver.embedding.capabilities.cohere import get_cohere_embedding_capabilities
    from codeweaver.embedding.capabilities.jinaai import get_jinaai_embedding_capabilities
    from codeweaver.embedding.capabilities.voyage import get_voyage_embedding_capabilities

    return tuple(
        item
        for item in (
            *filter_unimplemented(get_voyage_embedding_capabilities()),
            *filter_unimplemented(get_cohere_embedding_capabilities()),
            # *filter_unimplemented(get_baai_embedding_capabilities()),
            # *filter_unimplemented(get_marco_embedding_capabilities()),
            # *filter_unimplemented(get_alibaba_embedding_capabilities()),
            *filter_unimplemented(get_jinaai_embedding_capabilities()),
            *filter_unimplemented(get_amazon_embedding_capabilities()),
            # *filter_unimplemented(get_qwen_embedding_capabilities()),
        )
        if item
    )


def get_capabilities_by_model_and_provider(
    model: str, provider: Provider
) -> RerankingModelCapabilities:
    """Get the embedding model class by name and provider."""
    all_models = get_all_model_capabilities()
    for m in all_models:
        if m.name == model and m.provider == provider:
            return m
    raise ValueError(
        f"Unknown embedding model: {model} for provider: {provider}. Maybe check your spelling or the syntax?"
    )


__all__ = ("get_all_model_capabilities", "get_capabilities_by_model_and_provider", "get_model")

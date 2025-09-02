# SPDX-FileCopyrightText: (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Entrypoint for CodeWeaver's embedding model capabilities."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from codeweaver._settings import Provider


if TYPE_CHECKING:
    from codeweaver.embedding.capabilities.base import EmbeddingModelCapabilities


def filter_unimplemented(
    models: Sequence[EmbeddingModelCapabilities],
) -> Sequence[EmbeddingModelCapabilities]:
    """Removes models that are not yet implemented. Currently these are models that require the full `transformers` library."""
    return models


def get_model(model: str) -> tuple[EmbeddingModelCapabilities, ...]:  # noqa: C901
    # sourcery skip: no-long-functions
    """Get the embedding model class by name."""
    if ":" in model:
        model = model if (model.split(":")[1]).isnumeric() else model.split(":")[1]
    model = model.lower()

    if model.startswith("alibaba"):
        from codeweaver.embedding.capabilities.alibaba_nlp import (
            get_alibaba_nlp_embedding_capabilities,
        )

        return get_alibaba_nlp_embedding_capabilities()
    if model.startswith("amazon"):
        from codeweaver.embedding.capabilities.amazon import get_amazon_embedding_capabilities

        return get_amazon_embedding_capabilities()
    if model.startswith("baai"):
        from codeweaver.embedding.capabilities.baai import get_baai_embedding_capabilities

        return get_baai_embedding_capabilities()
    if model.startswith("cohere"):
        from codeweaver.embedding.capabilities.cohere import get_cohere_embedding_capabilities

        return get_cohere_embedding_capabilities()
    if model.startswith(("ibm", "granite")):
        from codeweaver.embedding.capabilities.ibm_granite import (
            get_ibm_granite_embedding_capabilities,
        )

        return get_ibm_granite_embedding_capabilities()
    if model.startswith("intfloat"):
        from codeweaver.embedding.capabilities.intfloat import get_intfloat_embedding_capabilities

        return get_intfloat_embedding_capabilities()
    if model.startswith(("jina", "jinaai")):
        from codeweaver.embedding.capabilities.jinaai import get_jinaai_embedding_capabilities

        return get_jinaai_embedding_capabilities()
    if model.startswith(("mixedbread", "mixedbread_ai")):
        from codeweaver.embedding.capabilities.mixedbread_ai import (
            get_mixedbread_ai_embedding_capabilities,
        )

        return get_mixedbread_ai_embedding_capabilities()
    if model.startswith(("nomic", "nomic_ai")):
        from codeweaver.embedding.capabilities.nomic_ai import get_nomic_ai_embedding_capabilities

        return get_nomic_ai_embedding_capabilities()
    if model.startswith(("openai", "chatgpt")):
        from codeweaver.embedding.capabilities.openai import get_openai_embedding_capabilities

        return get_openai_embedding_capabilities()
    if model.startswith("qwen"):
        from codeweaver.embedding.capabilities.qwen import get_qwen_embedding_capabilities

        return get_qwen_embedding_capabilities()
    if model.startswith(("sentence", "st-")):
        from codeweaver.embedding.capabilities.sentence_transformers import (
            get_sentence_transformers_embedding_capabilities,
        )

        return get_sentence_transformers_embedding_capabilities()
    if model.startswith("snowflake"):
        from codeweaver.embedding.capabilities.snowflake import get_snowflake_embedding_capabilities

        return get_snowflake_embedding_capabilities()
    if model.startswith("thenlper"):
        from codeweaver.embedding.capabilities.thenlper import get_thenlper_embedding_capabilities

        return get_thenlper_embedding_capabilities()
    if model.startswith("voyage"):
        from codeweaver.embedding.capabilities.voyage import get_voyage_embedding_capabilities

        return get_voyage_embedding_capabilities()
    if model.startswith(("whereisai", "whereis", "uae")):
        from codeweaver.embedding.capabilities.whereisai import get_whereisai_embedding_capabilities

        return get_whereisai_embedding_capabilities()
    raise ValueError(f"Unknown embedding model: {model}. Maybe check your spelling or the syntax?")


def get_all_model_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get all available embedding models."""
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

    return tuple(
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


def get_capabilities_by_model_and_provider(
    model: str, provider: Provider
) -> EmbeddingModelCapabilities:
    """Get the embedding model class by name and provider."""
    all_models = get_all_model_capabilities()
    for m in all_models:
        if m.name == model and m.provider == provider:
            return m
    raise ValueError(
        f"Unknown embedding model: {model} for provider: {provider}. Maybe check your spelling or the syntax?"
    )


__all__ = ("get_all_model_capabilities", "get_capabilities_by_model_and_provider", "get_model")

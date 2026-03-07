# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Capabilities for OpenAI embedding models."""

from __future__ import annotations

from typing import Literal

from codeweaver.core import Provider, dependency_provider
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.embedding.capabilities.types import PartialCapabilities


def _get_openai_models(
    provider: Provider,
) -> tuple[
    Literal["text-embedding-3-small", "openai/text-embedding-3-small"],
    Literal["text-embedding-3-large", "openai/text-embedding-3-large"],
]:
    match provider:
        case Provider.OPENAI | Provider.AZURE | Provider.VERCEL:
            return ("text-embedding-3-small", "text-embedding-3-large")
        case _:
            return ("openai/text-embedding-3-small", "openai/text-embedding-3-large")


def _get_providers() -> tuple[Provider, ...]:
    return (Provider.OPENAI, Provider.AZURE, Provider.GITHUB, Provider.VERCEL, Provider.LITELLM)


def _get_shared_openai_embedding_capabilities() -> PartialCapabilities:
    return {
        "version": 3,
        "preferred_metrics": ("dot", "cosine"),
        "supports_custom_prompts": False,
        "is_normalized": True,
        "tokenizer": "tiktoken",
        "max_batch_tokens": 64_000,
        "tokenizer_model": "o200k_base",
        "supports_context_chunk_embedding": False,
        "context_window": 8192,
        "default_dtype": "float",
        "output_dtypes": ("float",),
    }


class OpenaiEmbeddingCapabilities(EmbeddingModelCapabilities):
    """Capabilities for OpenAI embedding models."""


@dependency_provider(OpenaiEmbeddingCapabilities, scope="singleton", collection=True)
def get_openai_embedding_capabilities() -> tuple[OpenaiEmbeddingCapabilities, ...]:
    """Get the capabilities for OpenAI embedding models."""
    dimensions = (3072, 2560, 2048, 1536, 1024, 512, 256)
    return tuple(
        OpenaiEmbeddingCapabilities.model_validate({
            **_get_shared_openai_embedding_capabilities(),
            "name": model_name,
            "provider": provider,
            "default_dimension": 1536 if "small" in model_name else 3072,
            "output_dimensions": dimensions if "large" in model_name else dimensions[3:],
        })
        for provider in _get_providers()
        for model_name in _get_openai_models(provider)
    )


__all__ = ("OpenaiEmbeddingCapabilities", "get_openai_embedding_capabilities")

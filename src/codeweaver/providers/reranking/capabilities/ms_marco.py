# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Reranking capabilities for MS-Marco trained MiniLM models."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities


def get_marco_reranking_capabilities() -> Sequence[RerankingModelCapabilities]:
    """
    Get the MS-Marco MiniLM reranking capabilities.
    """
    from codeweaver.core.types.provider import Provider
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
    from codeweaver.providers.reranking.capabilities.types import PartialRerankingCapabilitiesDict

    # FastEmbed uses Xenova namespace, SentenceTransformers uses cross-encoder namespace
    fastembed_shared: PartialRerankingCapabilitiesDict = {
        "name": "Xenova/ms-marco-MiniLM-",
        "max_input": 512,
        "context_window": 512,
        "tokenizer": "tokenizers",
        "tokenizer_model": "Xenova/ms-marco-MiniLM-L-6-v2",
        "supports_custom_prompt": False,
        "provider": Provider.FASTEMBED,
    }

    sentence_transformers_shared: PartialRerankingCapabilitiesDict = {
        "name": "cross-encoder/ms-marco-MiniLM-",
        "max_input": 512,
        "context_window": 512,
        "tokenizer": "tokenizers",
        "tokenizer_model": "cross-encoder/ms-marco-MiniLM-L6-v2",
        "supports_custom_prompt": False,
        "provider": Provider.SENTENCE_TRANSFORMERS,
    }

    fastembed_models = ("L-6-v2", "L-12-v2")
    sentence_transformers_models = ("L6-v2", "L12-v2")

    ultra_light: PartialRerankingCapabilitiesDict = {
        "name": "cross-encoder/ms-marco-TinyBERT-L2-v2",
        "provider": Provider.SENTENCE_TRANSFORMERS,
        "max_input": 512,
        "context_window": 512,
        "tokenizer": "tokenizers",
        "tokenizer_model": "cross-encoder/ms-marco-TinyBERT-L2-v2",
        "supports_custom_prompt": False,
    }

    assembled_capabilities: list[RerankingModelCapabilities] = []

    # Add FastEmbed models (Xenova namespace)
    assembled_capabilities.extend(
        RerankingModelCapabilities.model_validate({
            **fastembed_shared,
            "name": f"{fastembed_shared['name']}{model}",
            "tokenizer_model": f"Xenova/ms-marco-MiniLM-{model}",
        })
        for model in fastembed_models
    )

    # Add SentenceTransformers models (cross-encoder namespace)
    assembled_capabilities.extend(
        RerankingModelCapabilities.model_validate({
            **sentence_transformers_shared,
            "name": f"{sentence_transformers_shared['name']}{model}",
            "tokenizer_model": f"cross-encoder/ms-marco-MiniLM-{model}",
        })
        for model in sentence_transformers_models
    )
    assembled_capabilities.append(RerankingModelCapabilities.model_validate(ultra_light))
    return assembled_capabilities


__all__ = ("get_marco_reranking_capabilities",)

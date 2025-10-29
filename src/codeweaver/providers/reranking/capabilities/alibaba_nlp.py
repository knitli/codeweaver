# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Reranking model capabilities for Alibaba NLP models."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities


def get_alibaba_reranking_capabilities() -> Sequence[RerankingModelCapabilities]:
    """
    Get the reranking capabilities for Alibaba NLP models.
    """
    from codeweaver.providers.provider import Provider
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities

    return [
        RerankingModelCapabilities.model_validate({
            "name": "Alibaba-NLP/gte-multilingual-reranking-base",
            "tokenizer": "tokenizers",
            "tokenizer_model": "Alibaba-NLP/gte-multilingual-reranking-base",
            "supports_custom_prompt": False,
            "max_input": 8192,
            "context_window": 8192,
            "provider": Provider.SENTENCE_TRANSFORMERS,
        })
    ]


__all__ = ("get_alibaba_reranking_capabilities",)

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Reranking model capabilities for Mixed Bread AI models."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities


def get_mixed_bread_reranking_capabilities() -> Sequence[RerankingModelCapabilities]:
    """
    Get the reranking capabilities for Mixed Bread AI models.
    """
    from codeweaver.core.types.provider import Provider
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities

    models = ("large-v2", "base-v2", "xsmall-v1", "base-v1")
    return [
        RerankingModelCapabilities.model_validate({
            "name": "mixedbread-ai/mxbai-rerank-",
            "tokenizer": "tokenizers",
            "supports_custom_prompt": False,
            "max_input": 8192 if model.endswith("v2") else 512,
            "context_window": 8192 if model.endswith("v2") else 512,
            "tokenizer_model": "mixedbread-ai/mxbai-rerank-",
            "provider": Provider.SENTENCE_TRANSFORMERS,
        })
        for model in models
    ]


__all__ = ("get_mixed_bread_reranking_capabilities",)

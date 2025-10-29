# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Model capabilities for Qwen reranking models."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
    from codeweaver.providers.reranking.capabilities.types import PartialRerankingCapabilities


def _get_shared_capabilities() -> PartialRerankingCapabilities:
    """Returns shared_capabilities across all Qwen reranking models."""
    from codeweaver.providers.provider import Provider
    return {
        "name": "Qwen/Qwen3-Reranker-",
        "provider": Provider.HUGGINGFACE_INFERENCE,
        "max_input": 32_000,
        "context_window": 32_000,
        "supports_custom_prompt": True,
        "custom_prompt": "Given search results containing code snippets, tree-sitter parse trees, documentation and code comments from a codebase, retrieve relevant Documents that answer the Query.",
        "tokenizer": "tokenizers",
        "other": {  # pyright: ignore[reportReturnType]  # string is Any...
            "prefix": '"<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n"',
            "suffix": '"\n<|im_start|>assistant\n<think>\n\n</think>\n\n"',
        },
    }


def get_qwen_reranking_capabilities() -> Sequence[RerankingModelCapabilities]:
    """
    Get the Qwen reranking capabilities.
    """
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
    shared_capabilities = _get_shared_capabilities()
    models = ("06B", "4B", "8B")
    assembled_capabilities: list[RerankingModelCapabilities] = []
    assembled_capabilities.extend(
        RerankingModelCapabilities.model_validate({
            **shared_capabilities,
            "name": f"{shared_capabilities['name']}{model}",
            "tokenizer_model": f"Qwen/Qwen3-Reranker-{model}",
        })
        for model in models
    )
    return assembled_capabilities


__all__ = ("get_qwen_reranking_capabilities",)

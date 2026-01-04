# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Model capabilities for Qwen reranking models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from codeweaver.core import dependency_provider
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities


if TYPE_CHECKING:
    from codeweaver.providers.reranking.capabilities.types import PartialRerankingCapabilitiesDict


class QwenRerankingCapabilities(RerankingModelCapabilities):
    """Capabilities for Qwen reranking models."""


def _get_shared_capabilities() -> PartialRerankingCapabilitiesDict:
    """Returns shared_capabilities across all Qwen reranking models."""
    from codeweaver.core import Provider

    return {  # ty: ignore[invalid-return-type]
        "name": "Qwen/Qwen3-Reranking-",
        "provider": Provider.HUGGINGFACE_INFERENCE,
        "max_input": 32_000,
        "context_window": 32_000,
        "supports_custom_prompt": True,
        "custom_prompt": "Given search results containing code snippets, tree-sitter parse trees, documentation and code comments from a codebase, retrieve relevant Documents that answer the Query.",
        "tokenizer": "tokenizers",
        "other": {  # string is Any...
            "prefix": '"<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n"',
            "suffix": '"\n<|im_start|>assistant\n<think>\n\n</think>\n\n"',
        },
    }


@dependency_provider(QwenRerankingCapabilities, scope="singleton", collection=True)
def get_qwen_reranking_capabilities() -> tuple[QwenRerankingCapabilities, ...]:
    """
    Get the Qwen reranking capabilities.
    """
    shared_capabilities = _get_shared_capabilities()
    models = ("06B", "4B", "8B")
    assembled_capabilities: list[QwenRerankingCapabilities] = []
    assembled_capabilities.extend(
        QwenRerankingCapabilities.model_validate({
            **shared_capabilities,
            "name": f"{shared_capabilities['name']}{model}",
            "tokenizer_model": f"Qwen/Qwen3-Reranking-{model}",
        })
        for model in models
    )
    return tuple(assembled_capabilities)


__all__ = ("get_qwen_reranking_capabilities", "QwenRerankingCapabilities")

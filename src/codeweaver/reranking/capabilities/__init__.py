# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Entry point for reranking models."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from codeweaver.reranking.capabilities.alibaba_nlp import get_alibaba_reranking_capabilities
from codeweaver.reranking.capabilities.amazon import get_amazon_reranking_capabilities
from codeweaver.reranking.capabilities.baai import get_baai_reranking_capabilities
from codeweaver.reranking.capabilities.cohere import get_cohere_reranking_capabilities
from codeweaver.reranking.capabilities.jinaai import get_jinaai_reranking_capabilities
from codeweaver.reranking.capabilities.ms_marco import get_marco_reranking_capabilities
from codeweaver.reranking.capabilities.qwen import get_qwen_reranking_capabilities
from codeweaver.reranking.capabilities.voyage import get_voyage_reranking_capabilities


if TYPE_CHECKING:
    from codeweaver.reranking.capabilities.base import RerankingModelCapabilities


def filter_unimplemented(
    models: Sequence[RerankingModelCapabilities],
) -> Sequence[RerankingModelCapabilities]:
    """Removes models that are not yet implemented. Currently these are models that require the full `transformers` library."""
    return models


def get_model(model: str) -> RerankingModelCapabilities:
    """Get the reranking model class by name."""
    if model.startswith("voyage"):
        return next(model for model in get_voyage_reranking_capabilities() if model.name == model)
    if model.startswith("cohere"):
        return next(model for model in get_cohere_reranking_capabilities() if model.name == model)
    if model.lower().startswith("baai"):
        return next(model for model in get_baai_reranking_capabilities() if model.name == model)
    if model.lower().startswith("xenova") or model.lower().startswith("cross-encoder"):
        return next(model for model in get_marco_reranking_capabilities() if model.name == model)
    if model.lower().startswith("alibaba"):
        return next(model for model in get_alibaba_reranking_capabilities() if model.name == model)
    if model.startswith("jina"):
        return next(model for model in get_jinaai_reranking_capabilities() if model.name == model)
    if model.startswith("amazon"):
        return next(model for model in get_amazon_reranking_capabilities() if model.name == model)
    if model.startswith("Qwen"):
        return next(model for model in get_qwen_reranking_capabilities() if model.name == model)
    raise ValueError(f"Unknown reranking model: {model}. Maybe check your spelling or the syntax?")


def get_all_model_capabilities() -> tuple[RerankingModelCapabilities, ...]:
    """Get all available reranking models."""
    return tuple(
        item
        for item in (
            *filter_unimplemented(get_voyage_reranking_capabilities()),
            *filter_unimplemented(get_cohere_reranking_capabilities()),
            *filter_unimplemented(get_baai_reranking_capabilities()),
            *filter_unimplemented(get_marco_reranking_capabilities()),
            *filter_unimplemented(get_alibaba_reranking_capabilities()),
            *filter_unimplemented(get_jinaai_reranking_capabilities()),
            *filter_unimplemented(get_amazon_reranking_capabilities()),
            *filter_unimplemented(get_qwen_reranking_capabilities()),
        )
        if item
    )


__all__ = ("get_all_model_capabilities", "get_model")

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Entry point for reranking models."""

from __future__ import annotations

import contextlib

from collections.abc import Callable, Generator
from importlib import import_module
from importlib.util import find_spec
from types import MappingProxyType
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.providers.reranking.capabilities.alibaba_nlp import (
        get_alibaba_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.amazon import get_amazon_reranking_capabilities
    from codeweaver.providers.reranking.capabilities.baai import get_baai_reranking_capabilities
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
    from codeweaver.providers.reranking.capabilities.cohere import get_cohere_reranking_capabilities
    from codeweaver.providers.reranking.capabilities.jinaai import get_jinaai_reranking_capabilities
    from codeweaver.providers.reranking.capabilities.ms_marco import (
        get_marco_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.qwen import get_qwen_reranking_capabilities
    from codeweaver.providers.reranking.capabilities.types import (
        PartialRerankingCapabilitiesDict,
        RerankingCapabilitiesDict,
    )
    from codeweaver.providers.reranking.capabilities.voyage import get_voyage_reranking_capabilities

dependency_map = {
    "bedrock": "boto3",
    "cohere": "cohere",
    "fastembed": "fastembed",
    "sentence_transformers": "sentence_transformers",
    "voyage": "voyageai",
}
"""Maps service providers to their client dependency/base class."""


def is_available(model: RerankingModelCapabilities) -> bool:
    """Check if a model is available for use."""
    model_string = f"{model.provider!s}:{model.name}"
    if dependency := next(
        (dep for key, dep in dependency_map.items() if model_string.startswith(key)), None
    ):
        return bool(find_spec(dependency))
    return False


def filter_unimplemented(
    models: tuple[RerankingModelCapabilities, ...],
) -> Generator[RerankingModelCapabilities]:
    """Sets available models that are not yet implemented or unavailable."""
    _unimplemented = {}
    for model in models:
        if is_available(model) and f"{model.provider!s}:{model.name}" not in _unimplemented:
            model._available = True  # type: ignore[attr-defined]
        # models are False by default so we don't need to set that
        yield model


def load_default_capabilities() -> Generator[RerankingModelCapabilities]:
    """Import and collect all built-in capabilities."""
    from codeweaver.providers.reranking.capabilities.alibaba_nlp import (
        get_alibaba_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.amazon import get_amazon_reranking_capabilities
    from codeweaver.providers.reranking.capabilities.baai import get_baai_reranking_capabilities
    from codeweaver.providers.reranking.capabilities.cohere import get_cohere_reranking_capabilities
    from codeweaver.providers.reranking.capabilities.jinaai import get_jinaai_reranking_capabilities
    from codeweaver.providers.reranking.capabilities.ms_marco import (
        get_marco_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.qwen import get_qwen_reranking_capabilities

    with contextlib.suppress(AttributeError, ImportError):
        from codeweaver.providers.reranking.capabilities.voyage import (
            get_voyage_reranking_capabilities,
        )

    def fetch_caps(
        caller: Callable[..., tuple[RerankingModelCapabilities, ...]],
    ) -> Generator[RerankingModelCapabilities]:
        yield from filter_unimplemented(caller())

    for item in (
        get_alibaba_reranking_capabilities,
        get_amazon_reranking_capabilities,
        get_baai_reranking_capabilities,
        get_cohere_reranking_capabilities,
        get_jinaai_reranking_capabilities,
        get_marco_reranking_capabilities,
        get_qwen_reranking_capabilities,
        get_voyage_reranking_capabilities,  # type: ignore[name-defined]
    ):
        yield from fetch_caps(item)  # type: ignore


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "RerankingModelCapabilities": (__spec__.parent, "base"),
    "get_alibaba_reranking_capabilities": (__spec__.parent, "alibaba_nlp"),
    "get_amazon_reranking_capabilities": (__spec__.parent, "amazon"),
    "get_baai_reranking_capabilities": (__spec__.parent, "baai"),
    "get_cohere_reranking_capabilities": (__spec__.parent, "cohere"),
    "get_jinaai_reranking_capabilities": (__spec__.parent, "jinaai"),
    "get_marco_reranking_capabilities": (__spec__.parent, "ms_marco"),
    "get_qwen_reranking_capabilities": (__spec__.parent, "qwen"),
    "get_voyage_reranking_capabilities": (__spec__.parent, "voyage"),
    "PartialRerankingCapabilitiesDict": (__spec__.parent, "types"),
    "RerankingCapabilitiesDict": (__spec__.parent, "types"),
})


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the semantic package."""
    if name in _dynamic_imports:
        module_name, submodule_name = _dynamic_imports[name]
        module = import_module(f"{module_name}.{submodule_name}")
        result = getattr(module, name)
        globals()[name] = result  # Cache in globals for future access
        return result
    if globals().get(name) is not None:
        return globals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = (
    "PartialRerankingCapabilitiesDict",
    "RerankingCapabilitiesDict",
    "RerankingModelCapabilities",
    "dependency_map",
    "get_alibaba_reranking_capabilities",
    "get_amazon_reranking_capabilities",
    "get_baai_reranking_capabilities",
    "get_cohere_reranking_capabilities",
    "get_jinaai_reranking_capabilities",
    "get_marco_reranking_capabilities",
    "get_qwen_reranking_capabilities",
    "get_voyage_reranking_capabilities",
    "load_default_capabilities",
)


def __dir__() -> list[str]:
    """List available attributes for the module."""
    return list(__all__)

# SPDX-FileCopyrightText: (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Entrypoint for CodeWeaver's embedding model capabilities.

Provides access to embedding model capabilities through the dependency injection system.
Use EmbeddingCapabilityResolver for capability lookup and management.
"""

from __future__ import annotations

from types import MappingProxyType

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.providers.embedding.capabilities.base import (
        EmbeddingModelCapabilities,
        SparseEmbeddingModelCapabilities,
    )
    from codeweaver.providers.embedding.capabilities.resolver import (
        EmbeddingCapabilityResolver,
        SparseEmbeddingCapabilityResolver,
    )
    from codeweaver.providers.embedding.capabilities.types import (
        EmbeddingCapabilitiesDict,
        EmbeddingSettingsDict,
        PartialCapabilities,
    )


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "EmbeddingCapabilitiesDict": (__spec__.parent, "types"),
    "EmbeddingCapabilityResolver": (__spec__.parent, "resolver"),
    "SparseEmbeddingCapabilityResolver": (__spec__.parent, "resolver"),
    "EmbeddingModelCapabilities": (__spec__.parent, "base"),
    "EmbeddingSettingsDict": (__spec__.parent, "types"),
    "PartialCapabilities": (__spec__.parent, "types"),
    "SparseCapabilities": (__spec__.parent, "base"),
    "SparseEmbeddingModelCapabilities": (__spec__.parent, "base"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "EmbeddingCapabilitiesDict",
    "EmbeddingCapabilityResolver",
    "EmbeddingModelCapabilities",
    "EmbeddingSettingsDict",
    "PartialCapabilities",
    "SparseCapabilities",
    "SparseEmbeddingCapabilityResolver",
    "SparseEmbeddingModelCapabilities",
)


def __dir__() -> list[str]:
    return list(__all__)

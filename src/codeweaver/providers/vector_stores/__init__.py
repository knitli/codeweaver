# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Vector store interfaces and implementations for CodeWeaver."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.providers.vector_stores.base import VectorStoreProvider
    from codeweaver.providers.vector_stores.inmemory import MemoryVectorStoreProvider
    from codeweaver.providers.vector_stores.metadata import CollectionMetadata, HybridVectorPayload
    from codeweaver.providers.vector_stores.qdrant import QdrantVectorStoreProvider


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "MemoryVectorStoreProvider": (__spec__.parent, "inmemory"),
    "QdrantVectorStoreProvider": (__spec__.parent, "qdrant"),
    "VectorStoreProvider": (__spec__.parent, "base"),
    "HybridVectorPayload": (__spec__.parent, "metadata"),
    "CollectionMetadata": (__spec__.parent, "metadata"),
    "resolve_dimensions": (__spec__.parent, "utils"),
})


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "CollectionMetadata",
    "HybridVectorPayload",
    "MemoryVectorStoreProvider",
    "QdrantVectorStoreProvider",
    "VectorStoreProvider",
    "get_vector_store_provider",
    "resolve_dimensions",
)


def __dir__() -> list[str]:
    """List available attributes for the module."""
    return list(__all__)

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Entrypoint for CodeWeaver's reranking model capabilities.

Provides access to reranking model capabilities through the dependency injection system.
Use RerankingCapabilityResolver for capability lookup and management.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
    from codeweaver.providers.reranking.capabilities.resolver import RerankingCapabilityResolver
    from codeweaver.providers.reranking.capabilities.types import (
        PartialRerankingCapabilitiesDict,
        RerankingCapabilitiesDict,
    )


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "PartialRerankingCapabilitiesDict": (__spec__.parent, "types"),
    "RerankingCapabilitiesDict": (__spec__.parent, "types"),
    "RerankingCapabilityResolver": (__spec__.parent, "resolver"),
    "RerankingModelCapabilities": (__spec__.parent, "base"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "PartialRerankingCapabilitiesDict",
    "RerankingCapabilitiesDict",
    "RerankingCapabilityResolver",
    "RerankingModelCapabilities",
)


def __dir__() -> list[str]:
    return list(__all__)

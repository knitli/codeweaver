# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""CodeWeaver server health monitoring and reporting package."""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.server.health.endpoint import get_health
    from codeweaver.server.health.health_service import HealthService
    from codeweaver.server.health.models import (
        EmbeddingProviderServiceInfo,
        FailoverInfo,
        HealthResponse,
        IndexingInfo,
        IndexingProgressInfo,
        RerankingServiceInfo,
        ResourceInfo,
        ServicesInfo,
        SparseEmbeddingServiceInfo,
        StatisticsInfo,
        VectorStoreServiceInfo,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "EmbeddingProviderServiceInfo": (__spec__.parent, "models"),
    "FailoverInfo": (__spec__.parent, "models"),
    "HealthResponse": (__spec__.parent, "models"),
    "HealthService": (__spec__.parent, "health_service"),
    "IndexingInfo": (__spec__.parent, "models"),
    "IndexingProgressInfo": (__spec__.parent, "models"),
    "RerankingServiceInfo": (__spec__.parent, "models"),
    "ResourceInfo": (__spec__.parent, "models"),
    "ServicesInfo": (__spec__.parent, "models"),
    "SparseEmbeddingServiceInfo": (__spec__.parent, "models"),
    "StatisticsInfo": (__spec__.parent, "models"),
    "VectorStoreServiceInfo": (__spec__.parent, "models"),
    "get_health": (__spec__.parent, "endpoint"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "EmbeddingProviderServiceInfo",
    "FailoverInfo",
    "HealthResponse",
    "HealthService",
    "IndexingInfo",
    "IndexingProgressInfo",
    "RerankingServiceInfo",
    "ResourceInfo",
    "ServicesInfo",
    "SparseEmbeddingServiceInfo",
    "StatisticsInfo",
    "VectorStoreServiceInfo",
    "get_health",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)

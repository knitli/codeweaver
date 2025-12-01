# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""CodeWeaver server package initialization."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.common.utils import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.server.health import (
        EmbeddingProviderServiceInfo,
        HealthResponse,
        HealthService,
        IndexingInfo,
        IndexingProgressInfo,
        RerankingServiceInfo,
        ServicesInfo,
        SparseEmbeddingServiceInfo,
        StatisticsInfo,
        VectorStoreServiceInfo,
        get_health,
    )
    from codeweaver.server.lifespan import background_services_lifespan, http_lifespan
    from codeweaver.server.management import ManagementServer
    from codeweaver.server.server import CodeWeaverState, get_state, lifespan


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CodeWeaverState": (__spec__.parent, "server"),
    "EmbeddingProviderServiceInfo": (__spec__.parent, "health"),
    "HealthResponse": (__spec__.parent, "health"),
    "HealthService": (__spec__.parent, "health"),
    "IndexingInfo": (__spec__.parent, "health"),
    "IndexingProgressInfo": (__spec__.parent, "health"),
    "ManagementServer": (__spec__.parent, "management"),
    "RerankingServiceInfo": (__spec__.parent, "health"),
    "ServicesInfo": (__spec__.parent, "health"),
    "SparseEmbeddingServiceInfo": (__spec__.parent, "health"),
    "StatisticsInfo": (__spec__.parent, "health"),
    "VectorStoreServiceInfo": (__spec__.parent, "health"),
    "background_services_lifespan": (__spec__.parent, "lifespan"),
    "get_health": (__spec__.parent, "health"),
    "get_state": (__spec__.parent, "server"),
    "http_lifespan": (__spec__.parent, "lifespan"),
    "lifespan": (__spec__.parent, "server"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "CodeWeaverState",
    "EmbeddingProviderServiceInfo",
    "HealthResponse",
    "HealthService",
    "IndexingInfo",
    "IndexingProgressInfo",
    "ManagementServer",
    "RerankingServiceInfo",
    "ServicesInfo",
    "SparseEmbeddingServiceInfo",
    "StatisticsInfo",
    "VectorStoreServiceInfo",
    "background_services_lifespan",
    "get_health",
    "get_state",
    "http_lifespan",
    "lifespan",
)


def __dir__() -> list[str]:
    return list(__all__)
